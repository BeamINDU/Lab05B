import os
from fastapi import APIRouter, Depends, HTTPException
from ..database import get_db
from sqlalchemy.orm import Session, joinedload
import json
from typing import List, Literal, Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from app import models, schemas, crud, route_opt_schemas, utils
from app.logger import logger
from app.model import model
from celery import group
from app.celery.tasks import simulateTask, simulateNoSaveTask
from app.celery_app import celery_app
from app.routes.tasks import get_task_running

router = APIRouter(tags=["Simulation"])


# class simulateRouteRes(BaseModel):
#     simulate_status: str
#     results: route_opt_schemas.LogisticsResponse


@router.post("/route-simulate/", response_model_exclude_none=True)
def simulate_route(
    payload: route_opt_schemas.LogisticsRequest,
) -> route_opt_schemas.LogisticsResponse:
    logger.info(f"route simulate request: {payload.model_dump_json()}")
    try:
        (
            simulation_payloads,
            jobById,
            vehicleById,
            jobVehicles,
            packageById,
            productByNo,
        ) = utils.route_opt_to_SimulationRequest(payload)

        # return vehicleById

        # print(
        #     sum(
        #         item.qty
        #         for _, request in simulation_payloads.items()
        #         for order in request.orders
        #         for item in order.products
        #     )
        # )

        task_group = group(
            [
                simulateNoSaveTask.subtask(
                    (
                        crud.prepare_simulation_payload(p).model_dump(),
                        p.simulatetype,
                        job_id,
                    )
                )
                for job_id, p in simulation_payloads.items()
            ]
        )
        group_result = task_group.apply_async()

        results: list[dict] = group_result.get()

        failed_tasks = [r for r in results if r.get("simulate_status") == models.Status.FAILURE]
        # overall_status = "completed_with_failures" if failed_tasks else "success"
        if failed_tasks:
            raise HTTPException(
                status_code=500,
                detail=f"{len(failed_tasks)} tasks failed {[task.get('error') for task in failed_tasks]}.",
            )

        result_response = route_opt_schemas.LogisticsResponse(
            **payload.model_dump(exclude={"job_selection_detail", "package"}),
            job_selection_detail=[],
        )

        # print(sum(1 for result in results for containerdict in result.get("result", []) for detail in containerdict["details"] for order in detail["orders"] for _ in order["products"]))

        for result in results:
            job_id: int | None = result.get("job_id")
            job = jobById.get(job_id)

            if not job_id or not job:
                continue

            Jobdetail = route_opt_schemas.JobSelectionDetailResponse(
                job_id=job_id, job_name=job.job_name, vehicle=[]
            )

            for containerdict in result.get("result", []):
                simbatch = schemas.SimBatch(**containerdict)
                vehicle = vehicleById.get(simbatch.batchmasterid)
                if not vehicle:
                    continue
                maxCap = vehicle.load_length * vehicle.load_width * vehicle.load_height
                vehicleRes = route_opt_schemas.VehicleResponse(
                    **vehicle.model_dump(exclude={"truck_size"}),
                    utilize_weight=f"{simbatch.total_weight:,.2f}/{vehicle.load_weight:,.2f}",
                    utilize_weight_percent=simbatch.total_weight
                    * 100
                    / vehicle.load_weight,
                    utilize_cap=f"{simbatch.total_volume:,.2f}/{maxCap:,.2f}",
                    utilize_cap_percent=simbatch.total_volume * 100 / maxCap,
                    package_opt=[],
                )

                totalWeight = 0
                totalCap = 0

                if isinstance(simbatch.details[0], schemas.SimDetail):
                    simbatch.details.sort(key=utils.container_sort)
                    simbatch.details = utils.sort_dependencies(
                        simbatch.details, utils.supported_corner
                    )

                no_package = route_opt_schemas.PackageOptimization(orders=[])
                for seq, detail in enumerate(simbatch.details):
                    if isinstance(detail, schemas.SimDetail):
                        package = packageById.get(detail.masterid)
                        if not package:
                            continue
                        totalWeight += package.package_weight
                        totalCap += (
                            package.package_length
                            * package.package_width
                            * package.package_height
                        )
                        orientation = model.getOrien(detail.rotation)
                        rotDim = model.getRotDim(
                            package.package_width,
                            package.package_length,
                            package.package_height,
                            detail.rotation,
                        )
                        rotloadDim = model.getRotDim(
                            package.load_width,
                            package.load_length,
                            package.load_height,
                            detail.rotation,
                        )
                        packageRes = route_opt_schemas.PackageOptimization(
                            **package.model_dump(
                                exclude={
                                    "package_width",
                                    "package_length",
                                    "package_height",
                                    "load_width",
                                    "load_length",
                                    "load_height",
                                }
                            ),
                            package_seq=seq + 1,
                            package_type="pallet",
                            position=route_opt_schemas.Position(
                                x=detail.x,
                                y=detail.y,
                                z=detail.z,
                            ),
                            orientation=route_opt_schemas.Orientation(
                                x=orientation[0],
                                y=orientation[1],
                                z=orientation[2],
                            ),
                            package_width=rotDim[0],
                            package_length=rotDim[1],
                            package_height=rotDim[2],
                            load_width=rotloadDim[0],
                            load_length=rotloadDim[1],
                            load_height=rotloadDim[2],
                            orders=[],
                        )

                        for order in detail.orders:
                            utils.simOrder_to_route(
                                order, packageRes.orders, productByNo
                            )
                        vehicleRes.package_opt.append(packageRes)
                    else:
                        orderWeight, orderCap = utils.simOrder_to_route(
                            detail, no_package.orders, productByNo
                        )
                        totalWeight += orderWeight
                        totalCap += orderCap
                if no_package.orders:
                    vehicleRes.package_opt.append(no_package)

                print(simbatch.total_weight, totalWeight)
                print(simbatch.total_volume, totalCap)

                Jobdetail.vehicle.append(vehicleRes)

            vehicleIds = [vehicle.vehicle_id for vehicle in Jobdetail.vehicle]

            for vehicle in jobVehicles.get(job_id, []):
                if vehicle.vehicle_id in vehicleIds:
                    continue
                maxCap = vehicle.load_length * vehicle.load_width * vehicle.load_height
                vehicleRes = route_opt_schemas.VehicleResponse(
                    **vehicle.model_dump(exclude={"truck_size"}),
                    utilize_weight=f"0/{vehicle.load_weight}",
                    utilize_weight_percent=0,
                    utilize_cap=f"0/{maxCap}",
                    utilize_cap_percent=0,
                    package_opt=[],
                )
                Jobdetail.vehicle.append(vehicleRes)

            result_response.job_selection_detail.append(Jobdetail)

        logger.info(f"route simulate response: {result_response.model_dump_json()}")
        return result_response

        # return {"simulate_status": overall_status, "results": result_response}

    except HTTPException as e:
        print(f" Unexpected Error during simulation: {e.detail}")
        raise e
    except Exception as e:
        print(f" Unexpected Error during simulation: {e}")
        raise HTTPException(
            status_code=500, detail=f"Unexpected error during simulation: {e}"
        )


class SimulationOrderRequest(BaseModel):
    order_ids: List[int]
    pallets: Optional[List[schemas.PalletAvaliable]] = None
    containers: Optional[List[schemas.PackageAvaliable]] = None
    simulatetype: Literal["pallet", "container", "pallet_container"]


@router.post("/simulate/orders/")
def simulate_orders(
    payload: SimulationOrderRequest,
    db: Session = Depends(get_db),
):
    try:
        orders = [crud.get_order_by_id(db, orders_id) for orders_id in payload.order_ids]
        simulation_payload = schemas.SimulationRequest.model_validate(
            {**payload.model_dump(), "orders": orders}
        )

        simulate_payload = crud.prepare_simulation_payload(simulation_payload, db)

        # create simulate entry and get simulate id
        simulate_entry = models.Simulate(
            simulatetype=payload.simulatetype,
            simulate_status=models.Status.PENDING,
            simulate_by="Admin",
            start_datetime=datetime.now(timezone(timedelta(hours=7))),
            snapshot_data=simulate_payload.model_dump_json(),
        )
        db.add(simulate_entry)
        db.flush()
        # create simulatedetail
        for order in simulation_payload.orders:
            new_detail = models.Simulatedetail(
                simulate_id=simulate_entry.simulate_id, orders_id=order.orders_id
            )
            db.add(new_detail)
        db.commit()
        db.refresh(simulate_entry)

        task = simulateTask.delay(
            simulate_payload.model_dump(), simulate_entry.simulate_id
        )
        print(task.id)
        simulate_entry.task_id = task.id
        db.commit()
        db.refresh(simulate_entry)

        return {
            "simulate_by": simulate_entry.simulate_by,
            "start_datetime": simulate_entry.start_datetime,
            "simulatetype": simulate_entry.simulatetype,
            "simulate_id": simulate_entry.simulate_id,
            "task_id": task.id,
        }

    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        print(f" Unexpected Error during simulation: {e}")
        raise HTTPException(
            status_code=500, detail=f"Unexpected error during simulation: {e}"
        )


@router.post("/simulate/test/")
def simulate_test(
    payload: SimulationOrderRequest,
    db: Session = Depends(get_db),
):
    try:
        orders = [crud.get_order_by_id(db, orders_id) for orders_id in payload.order_ids]
        simulation_payload = schemas.SimulationRequest.model_validate(
            {**payload.model_dump(), "orders": orders}
        )

        simulate_payload = crud.prepare_simulation_payload(simulation_payload, db)

        return {
            "products": simulate_payload.products,
            "pallets": simulate_payload.pallets,
        }

    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        print(f" Unexpected Error during simulation: {e}")
        raise HTTPException(
            status_code=500, detail=f"Unexpected error during simulation: {e}"
        )


# get simulated data
@router.get("/", response_model_exclude_none=True)
def get_simulation_data(
    simulate_id: int, db: Session = Depends(get_db)
) -> schemas.SimulationGetResponse:
    try:
        # 1. ดึง simulate entry
        simulate_entry: models.Simulate = (
            db.query(models.Simulate)
            .filter(models.Simulate.simulate_id == simulate_id)
            .first()
        )
        
        if not simulate_entry:
            raise HTTPException(
                status_code=404, 
                detail=f"data not found for simulateId {simulate_id}"
            )
        
        # 2. ดึง simulatetype จาก snapshot_data
        simulatetype = "unknown"
        if simulate_entry.snapshot_data:
            simulatetype = simulate_entry.snapshot_data.get("simulatetype", "unknown")
        
        # 3. สร้าง response object
        ret = schemas.SimulationGetResponse(
            simulate_by=simulate_entry.simulate_by,
            start_datetime=simulate_entry.start_datetime,
            simulatetype=simulatetype,
            simulate_status=models.Status.PENDING,
        )
        
        # 4. Handle status
        match simulate_entry.simulate_status:
            case models.Status.PENDING:
                if simulate_entry.task_id and get_task_running(
                    simulate_entry.task_id, "simulate"
                ):
                    return ret
                simulate_entry.simulate_status = models.Status.FAILURE
                simulate_entry.pdf_status = models.Status.FAILURE
                simulate_entry.error_message = (
                    "This task can't be re-simulated. Please start a new simulation."
                )
                db.commit()
                db.refresh(simulate_entry)
                ret.simulate_status = models.Status.FAILURE
                ret.error = (
                    simulate_entry.error_message or "Unexpected Error During Simulation"
                )
                return ret
                
            case models.Status.FAILURE:
                ret.simulate_status = models.Status.FAILURE
                ret.error = (
                    simulate_entry.error_message or "Unexpected Error During Simulation"
                )
                return ret
        
        # ✅ 5. ใช้ Mock Data ก่อน (Phase 1)
        # TODO: เมื่อทีมทำฟังก์ชันเสร็จ ให้เปลี่ยนเป็น:
        # response_data = utils.build_lab05b_nested_data(simulate_id, db)
        
        response_data = get_mock_data()
        
        ret.data = response_data
        ret.simulate_status = models.Status.SUCCESS
        return ret
        
    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        print(e)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


def get_mock_data():
    """
    Mock data ตามตัวอย่างที่หัวหน้าให้มา
    TODO: ลบฟังก์ชันนี้เมื่อทีมทำฟังก์ชันจริงเสร็จ
    """
    return [
        {
            "simulate_detail_id": 1,
            "simulate_id": 1,
            "package_id": 1,
            "package_name": "Container 40ft",
            "package_code": "CNT-40",
            "package_type": "container",
            "door_position": "back",
            "have_partition": False,
            "have_stackable": True,
            "number_of_stack": 2,
            "package_width": 2350,
            "package_length": 12000,
            "package_height": 2700,
            "package_weight": 3800,
            "load_width": 2300,
            "load_length": 11800,
            "load_height": 2600,
            "load_weight": 28000,
            "is_stack": False,
            "max_stack": 0,
            "stack_weight": 0,
            "is_fragile": False,
            "is_side_up": False,
            "is_on_top": False,
            "color": "#0d9488",
            "rotation": 0,
            "position_x": 0,
            "position_y": 0,
            "position_z": 0,
            "utilize_weight": 18500,
            "utilize_weight_percent": 66.07,
            "utilize_capacity": 75.5,
            "utilize_cap_percent": 75.5,
            "orders": [],
            "child_detail": [
                {
                    "simulate_detail_id": 2,
                    "simulate_id": 1,
                    "package_id": 10,
                    "package_name": "Euro Pallet",
                    "package_code": "PLT-EUR-01",
                    "package_type": "pallet",
                    "door_position": "",
                    "package_width": 800,
                    "package_length": 1200,
                    "package_height": 1500,
                    "package_weight": 25,
                    "load_width": 780,
                    "load_length": 1180,
                    "load_height": 1350,
                    "load_weight": 1000,
                    "is_stack": False,
                    "max_stack": 0,
                    "stack_weight": 0,
                    "is_fragile": False,
                    "is_side_up": False,
                    "is_on_top": False,
                    "color": "#16a34a",
                    "rotation": 0,
                    "position_x": 0,
                    "position_y": 0,
                    "position_z": 0,
                    "utilize_weight": 850,
                    "utilize_weight_percent": 85.0,
                    "utilize_capacity": 72.3,
                    "utilize_cap_percent": 72.3,
                    "orders": [],
                    "child_detail": [
                        {
                            "simulate_detail_id": 4,
                            "simulate_id": 1,
                            "package_id": 20,
                            "package_name": "Medium Carton",
                            "package_code": "CTN-MED-01",
                            "package_type": "carton",
                            "door_position": "",
                            "package_width": 300,
                            "package_length": 400,
                            "package_height": 300,
                            "package_weight": 0.5,
                            "load_width": 290,
                            "load_length": 390,
                            "load_height": 290,
                            "load_weight": 25,
                            "is_stack": True,
                            "max_stack": 4,
                            "stack_weight": 100,
                            "is_fragile": False,
                            "is_side_up": False,
                            "is_on_top": False,
                            "color": "#ea580c",
                            "rotation": 0,
                            "position_x": 0,
                            "position_y": 0,
                            "position_z": 0,
                            "utilize_weight": 18.5,
                            "utilize_weight_percent": 74.0,
                            "utilize_capacity": 68.2,
                            "utilize_cap_percent": 68.2,
                            "child_detail": [],
                            "orders": [
                                {
                                    "orders_id": 1,
                                    "orders_number": "ORD-2024-001",
                                    "orders_name": "Customer A Order",
                                    "plan_send_date": "2024-01-15",
                                    "created_date": "2024-01-10",
                                    "created_by": "admin",
                                    "orders_detail": [
                                        {
                                            "orders_detail_id": 1,
                                            "orders_id": 1,
                                            "product_id": 101,
                                            "product_code": "PRD-A001",
                                            "product_name": "Widget A",
                                            "qty": 10,
                                            "pickup_priority": 1,
                                            "dropoff_priority": 1,
                                            "product": {
                                                "product_id": 101,
                                                "product_code": "PRD-A001",
                                                "product_name": "Widget A",
                                                "product_length": 100,
                                                "product_width": 80,
                                                "product_height": 50,
                                                "product_weight": 1.5,
                                                "is_fragile": False,
                                                "is_side_up": False,
                                                "is_on_top": False,
                                                "is_stack": True,
                                                "max_stack": 5,
                                                "stack_weight": 10,
                                                "color": "#3b82f6"
                                            }
                                        }
                                    ],
                                    "products": [
                                        {
                                            "simulate_product_id": 1,
                                            "simulate_id": 1,
                                            "simulate_detail_id": 4,
                                            "orders_id": 1,
                                            "product_id": 101,
                                            "product_code": "PRD-A001",
                                            "product_name": "Widget A",
                                            "pickup_priority": 1,
                                            "dropoff_priority": 1,
                                            "product": {
                                                "product_id": 101,
                                                "product_code": "PRD-A001",
                                                "product_name": "Widget A",
                                                "product_length": 100,
                                                "product_width": 80,
                                                "product_height": 50,
                                                "product_weight": 1.5,
                                                "is_fragile": False,
                                                "is_side_up": False,
                                                "is_on_top": False,
                                                "is_stack": True,
                                                "max_stack": 5,
                                                "stack_weight": 10,
                                                "color": "#3b82f6"
                                            },
                                            "rotation": 0,
                                            "position_x": 10,
                                            "position_y": 10,
                                            "position_z": 0
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ]

@router.get(
    "/snapshot",
)
def get_snap_shot(simulate_id: int, db: Session = Depends(get_db)):
    try:
        simulate_entry: models.Simulate = (
            db.query(models.Simulate)
            .filter(models.Simulate.simulate_id == simulate_id)
            .first()
        )
        if not simulate_entry:
            raise HTTPException(
                status_code=500, detail=f"data not found for simulateId {simulate_id}"
            )
        snapshot_data: schemas.SimulationPayloadDict | None = (
            json.loads(simulate_entry.snapshot_data)
            if simulate_entry.snapshot_data
            else None
        )
        return snapshot_data
    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get(
    "/simulate_status",
)
def get_simulation_status(simulate_id: int, db: Session = Depends(get_db)):
    try:
        simulate_entry: models.Simulate = (
            db.query(models.Simulate)
            .filter(models.Simulate.simulate_id == simulate_id)
            .first()
        )
        if not simulate_entry:
            raise HTTPException(
                status_code=500, detail=f"data not found for simulateId {simulate_id}"
            )
        return simulate_entry.simulate_status
    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.put("/simbatch")
async def update_position(
    simulate_id: int, simbatch: schemas.SimBatch, db: Session = Depends(get_db)
):
    try:
        db_simbatchs: list[models.Simbatch] = (
            db.query(models.Simbatch)
            .filter(models.Simbatch.simulate_id == simulate_id)
            .options(joinedload(models.Simbatch.details))
            .all()
        )
        if not db_simbatchs:
            raise HTTPException(status_code=404, detail="Simbatch not found")

        detailById: dict[str, schemas.SimDetail] = {}

        for detail in simbatch.details:
            if isinstance(detail, schemas.SimOrder):
                for product in detail.products:
                    if product.batchdetailid:
                        detailById[product.batchdetailid] = product
            if isinstance(detail, schemas.SimDetail):
                if not detail.batchdetailid:
                    continue
                detailById[detail.batchdetailid] = detail
                if not detail.orders:
                    continue
                for order in detail.orders:
                    for product in order.products:
                        detailById[product.batchdetailid] = product

        for db_simbatch in db_simbatchs:
            for detail in db_simbatch.details:
                new_detail = detailById.get(detail.batchdetailid)
                if not new_detail:
                    continue
                detail.x = new_detail.x
                detail.y = new_detail.y
                detail.z = new_detail.z
                detail.rotation = new_detail.rotation

        db.commit()
        db.refresh(db_simbatch)

        pdf_path = f"/pdf/{db_simbatch.simulate_id}.pdf"
        simulate_entry: models.Simulate = (
            db.query(models.Simulate)
            .filter(models.Simulate.simulate_id == db_simbatch.simulate_id)
            .first()
        )
        if not simulate_entry:
            raise HTTPException(
                status_code=500,
                detail=f"data not found for simulateId {db_simbatch.simulate_id}",
            )
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError as e:
                raise Exception(f"Error deleting file '{pdf_path}': {e}")
            if (
                simulate_entry.pdf_status == models.Status.PENDING
                and simulate_entry.pdf_task_id
                and get_task_running(simulate_entry.pdf_task_id, "pdf")
            ):
                celery_app.control.revoke(simulate_entry.pdf_task_id)
        simulate_entry.pdf_status = None
        simulate_entry.error_message = ""
        db.commit()
        db.refresh(simulate_entry)

        return {"message": "Simbatch Updated Successfully"}
    except HTTPException as e:
        print(e)
        db.rollback()
        raise e
    except Exception as e:
        print(e)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
