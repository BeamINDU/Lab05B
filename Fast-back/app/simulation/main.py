from datetime import datetime
from typing import Literal, Optional,List, TypedDict
from fastapi import Depends, FastAPI, HTTPException,APIRouter,BackgroundTasks
from pydantic import BaseModel
import multiprocessing
import requests
from sqlalchemy.orm import Session 
from fastapi.encoders import jsonable_encoder
from ..database import get_db ,SessionLocal
from ..models import Simulate,Simulatedetail
from ..crud import save_simulation_batches_internal
router = APIRouter()

from .model import (
    ContainerLoadingSolution,
    Item,
    Container,
    MultiContainerAssignGA,
    ContainerLoadingGA,
    arrangeContainer,
    arrangePallet,
)
 


# class RequestProduct(BaseModel):
#     productid: str
#     productName: str
#     productLength: float
#     productWidth: float
#     productHeight: float
#     productWeight: float
#     quantity: int
#     color: str
#     notStack: bool
#     isFragile: bool
#     isTop: bool
#     isSideUp: bool
#     maxStack: int
#     priority: int = 1


# class RequestOrder(BaseModel):
#     orderId: str
#     orderNumber: int
#     orderName: str
#     createdBy: str
#     # updateBy: Optional[str]
#     delivery_by: str
#     sendDate: datetime
#     createDate: datetime
#     updateDate: Optional[str] = None
#     products: list[RequestProduct]


# class RequestPallet(BaseModel):
#     palletId: str
#     palletName: str
#     loadLength: float
#     loadWidth: float
#     loadHeight: float
#     loadWeight: float
#     priority: int = 1

class RequestProduct(BaseModel):
    orderid: int
    productid: int
    productname: str
    productlength: float
    productwidth: float
    productheight: float
    productweight: float
    qtt: int = 1
    notstack: bool = False
    isfragile: bool = False
    istop: bool = False
    issideup: bool = False
    maxstack: int = -1
    priority: int = 1


class RequestPallet(BaseModel):
    palletid: int
    palletname: str
    palletlength: float
    palletwidth: float
    palletheight: float
    palletweight: float
    loadlength: float
    loadwidth: float
    loadheight: float
    loadweight: float
    qtt: int = 1
    priority: int = 1


class RequestContainer(BaseModel):
    containerid: int
    containername: str
    containerlength: float
    containerwidth: float
    containerheight: float
    containerweight: float
    loadlength: float
    loadwidth: float
    loadheight: float
    loadweight: float
    qtt: int = 1
    priority: int = 1

def simulate(
    model_containers: List[Container], model_items: List[Item], centered: bool = True
) -> List[ContainerLoadingSolution]:

    solutions: List[ContainerLoadingSolution] = []

    for _ in range(50):
        # Create and run optimizer
        AssignContOptimizer = MultiContainerAssignGA(model_containers, model_items)
        AssignContSolution = AssignContOptimizer.run()
        # Print results
        # print(f"Overall Fitness Score: {AssignContSolution['fitness']:.4f}")
        # for container in AssignContSolution["containers"]:
        #     if len(container.items) > 0:
        #         print(f"container {container.id}: {len(container.items)}")

        # arrange items in containers in parallel
        pool = multiprocessing.Pool()
        temp_solutions = (
            pool.map(arrangePallet, AssignContSolution["containers"])
            if centered
            else pool.map(arrangeContainer, AssignContSolution["containers"])
        )

        # put unused items back to be re-arranged in free containers
        model_containers = []
        model_items = []
        for solution in temp_solutions:
            if len(solution["unused"]) == 0:
                model_containers.append(solution["container"])
            else:
                solutions.append(solution)
                model_items.extend(solution["unused"])
        if len(model_containers) == 0 or len(model_items) == 0:
            solutions.extend(temp_solutions)
            break
    return solutions


@router.get("/")
def read_root():
    return {"Hello": "World"}


# @router.post("/simulate/")
# def simulate_items(orders: List[RequestOrder], pallets: List[RequestPallet],background_tasks: BackgroundTasks,db: Session = Depends(get_db)):
#     try:
#         # --- Simulation Logic ---
#         model_item_types = [
#             ItemType(
#                 name=item.productName,
#                 id=item.productid,
#                 length=item.productLength,
#                 width=item.productWidth,
#                 height=item.productHeight,
#                 weight=item.productWeight,
#                 color=item.color,
#                 notStack=item.notStack,
#                 isFragile=item.isFragile,
#                 isTop=item.isTop,
#                 isSideUp=item.isSideUp,
#                 maxStack=item.maxStack,
#             )
#             for order in orders
#             for item in order.products
#         ]
#         model_items = [
#             Item(
#                 id=f"{id}{type_idx}{order.orderId}",
#                 order_id=order.orderId,
#                 itemType=model_item_types[type_idx],
#                 priority=item.priority,
#             )
#             for order in orders
#             for type_idx, item in enumerate(order.products)
#             for id in range(item.quantity)
#         ]
#         model_containers = [
#             Container(
#                 id=pallet.palletId,
#                 name=pallet.palletName,
#                 length=pallet.loadLength,
#                 width=pallet.loadWidth,
#                 height=pallet.loadHeight,
#                 max_weight=pallet.loadWeight,
#                 priority=pallet.priority,
#             )
#             for pallet in pallets
#         ]

#         solutions = []
#         for _ in range(50):
#             AssignContOptimizer = MultiContainerAssignGA(model_containers, model_items)
#             AssignContSolution = AssignContOptimizer.run()

#             pool = multiprocessing.Pool()
#             temp_solutions = pool.map(arrangeContainer, AssignContSolution["containers"])

#             model_containers = []
#             model_items = []
#             for solution in temp_solutions:
#                 if len(solution["unused"]) == 0:
#                     model_containers.append(solution["container"])
#                 else:
#                     solutions.append(solution)
#                     model_items.extend(solution["unused"])
#             if len(model_containers) == 0 or len(model_items) == 0:
#                 solutions.extend(temp_solutions)
#                 break

#         # --- Validate Solutions ---
#         for solution in solutions:
#             if len(solution["unused"]) > 0:
#                 return {"error": "Unable to fit all products into given pallets."}
#             if solution["fitness"] < 0:
#                 return {"error": "Unable to arrange the products."}

#         # --- Create Simulation Result ---
#         simulation_result = {
#             "data": [
#                 {
#                     "id": solution["container"].id,
#                     "name": solution["container"].name,
#                     "length": solution["container"].length,
#                     "width": solution["container"].width,
#                     "height": solution["container"].height,
#                     "max_weight": solution["container"].max_weight,
#                     "priority": solution["container"].priority,
#                     "orders": [
#                         {
#                             "orderId": order.orderId,
#                             "orderName": order.orderName,
#                             "orderNumber": order.orderNumber,
#                             "items": [
#                                 {
#                                     "id": item.id,
#                                     "name": item.itemType_name,
#                                     "itemType_id": item.itemType_name,
#                                     "length": item.length,
#                                     "width": item.width,
#                                     "height": item.height,
#                                     "weight": item.weight,
#                                     "priority": item.priority,
#                                     "position": item.position,
#                                     "rotation": item.rotation,
#                                     "color": item.color,
#                                     "notStack": item.notStack,
#                                     "isFragile": item.isFragile,
#                                     "isTop": item.isTop,
#                                     "isSideUp": item.isSideUp,
#                                     "maxStack": item.maxStack,
#                                 }
#                                 for item in solution["container"].items
#                                 if item.order_id == order.orderId
#                             ],
#                         }
#                         for order in orders
#                     ],
#                     "total_weight": solution["container"].total_weight,
#                 }
#                 for solution in solutions
#             ]
#         }
#         background_tasks.add_task(save_simulation_data, simulation_result)

#         return simulation_result

#     except Exception as e:
#         print(f"❌ Simulation Error: {e}")
#         raise HTTPException(status_code=500, detail=f"Simulation failed: {e}")


# def save_simulation_data(simulation_result: dict):
#     db = SessionLocal()  # สร้าง Connection ใหม่
#     try:
#         print("🔄 Background Task: Saving Simulation Data...")

#         # --- Save Simulate Entry ---
#         simulate_entry = Simulate(
#             simulatetype="Pallet",
#             status="OK",
#             simulateby="Admin",
#             simulatedatetime=datetime.utcnow()
#         )
#         db.add(simulate_entry)
#         db.commit()
#         db.refresh(simulate_entry)  # ดึง simulateid ที่สร้างโดย Database

#         # --- Save SimBatch Entry (ใช้ข้อมูลจาก simulation_result) ---
#         for batch_data in simulation_result.get("data", []):
#             new_batch = Simbatch(
#                 simulateid=simulate_entry.simulateid
#             )
#             db.add(new_batch)
#         db.commit()

#         print(f"✅ Simulation Data Saved Successfully! SimulateID: {simulate_entry.simulateid}")

#     except Exception as e:
#         db.rollback()
#         print(f"❌ Error Saving Simulation Data: {e}")

#     finally:
#         db.close()  # ปิด Database Session

class product_detail(TypedDict):
    orderid: int
    masterid: int
    mastertype: Literal["product"]
    position: List[float]
    rotation: int


class container_detail(TypedDict):
    masterid: int
    mastertype: Literal["pallet", "container"]
    total_weight: float


class sub_sim_batch(TypedDict):
    batchtype: Literal["palletoncontainer"]
    details: List[container_detail | product_detail]


class sub_sim_batch_detail(TypedDict):
    mastertype: Literal["sim_batch"]
    total_weight: float
    position: List[float]
    rotation: int
    sim_batch: sub_sim_batch


class sim_batch(TypedDict):
    batchtype: Literal["pallet", "boxcontainer", "palletcontainer", "mixcontainer"]
    details: List[container_detail | product_detail | sub_sim_batch_detail]


class apiResponse(TypedDict):
    data: List[sim_batch]

@router.post("/simulate/pallet")
def simulate_pallets(products: List[RequestProduct], pallets: List[RequestPallet], background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        # convert request params into model classes
        ind_items = [item for item in products for _ in range(item.qtt)]
        ind_pallets = [pallet for pallet in pallets for _ in range(pallet.qtt)]

        model_items = [
            Item(
                id=str(id) + str(type_idx) + str(item.orderid),
                itemType_id=item.productid,
                itemType="product",
                length=item.productlength,
                width=item.productwidth,
                height=item.productheight,
                weight=item.productweight,
                isSideUp=item.issideup,
                maxStack=(
                    item.maxstack
                    if not (item.notstack or item.isfragile or item.istop)
                    else 0
                ),
                order_id=item.orderid,
                priority=item.priority,
            )
            for type_idx, item in enumerate(products)
            for id in range(item.qtt)
        ]
        model_containers = [
            Container(
                id=str(id) + str(pallet.palletid),
                type_id=pallet.palletid,
                length=pallet.loadlength,
                width=pallet.loadwidth,
                height=pallet.loadheight,
                exlength=pallet.palletlength,
                exwidth=pallet.palletwidth,
                exheight=pallet.palletheight,
                exweight=pallet.palletweight,
                max_weight=pallet.loadweight,
                priority=pallet.priority,
            )
            for id, pallet in enumerate(ind_pallets)

        ]

        solutions = simulate(model_containers=model_containers, model_items=model_items)

        for solution in solutions:
            if len(solution["unused"]) > 0:
                error_message = "❌ Unable to fit all products into given pallets."
                print(error_message)
                raise HTTPException(status_code=400, detail=error_message)

            if solution["fitness"] < 0:
                error_message = "❌ Unable to arrange the products."
                print(error_message)
                raise HTTPException(status_code=400, detail=error_message)


        simulation_result : apiResponse = {"data": []}

        for solution in solutions:
            batch: sim_batch = {
                "batchtype": "pallet",
                "details": [
                    {
                        "masterid": solution["container"].type_id,
                        "mastertype": "pallet",
                        "total_weight": solution["container"].total_weight,
                    }
                ],
            }

            for item in solution["container"].items:
                batch["details"].append(
                    {
                        "masterid": item.itemType_id,
                        "mastertype": item.itemType,
                        "orderid": item.order_id,
                        "position": item.position,
                        "rotation": item.rotation,
                    }
                )

 
            simulation_result["data"].append(batch)
        
        simulate_entry = db.query(Simulate).join(Simulatedetail).filter(
            Simulatedetail.orderid == int(products[0].orderid)

        ).first()

        if not simulate_entry:
            raise HTTPException(status_code=404, detail="ไม่พบข้อมูล simulateId สำหรับ orderId นี้")

        db_session = SessionLocal() 
        background_tasks.add_task(save_simulation_batches_internal, simulation_result, db_session)

        
        return simulation_result
 
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
 
 
@router.post("/simulate/container")
def simulate_containers(
    products: List[RequestProduct], containers: List[RequestContainer], background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    try:
        # convert request params into model classes
        ind_items = [item for item in products for _ in range(item.qtt)]
        ind_containers = [
            container for container in containers for _ in range(container.qtt)
        ]        
        model_items = [
            Item(
                id=str(id),
                itemType_id=item.productid,
                itemType="product",
                length=item.productlength,
                width=item.productwidth,
                height=item.productheight,
                weight=item.productweight,
                isSideUp=item.issideup,
                maxStack=(
                    item.maxstack
                    if not (item.notstack or item.isfragile or item.istop)
                    else 0
                ),
                order_id=item.orderid,
                priority=item.priority,
            )
            for id, item in enumerate(ind_items)
        ]
        model_containers = [
            Container(
                id=str(id),
                type_id=container.containerid,
                length=container.loadlength,
                width=container.loadwidth,
                height=container.loadheight,
                exlength=container.containerlength,
                exwidth=container.containerwidth,
                exheight=container.containerheight,
                exweight=container.containerweight,
                max_weight=container.loadweight,
                priority=container.priority,
            )
            for id, container in enumerate(ind_containers)
        ]

        solutions = simulate(
            model_containers=model_containers, model_items=model_items, centered=False
        )

        for solution in solutions:
            if len(solution["unused"]) > 0:
                return {"error": "unable to fit all products into given containers."}
            if solution["fitness"] < 0:
                return {"error": "unable to arrange the products."}

        simulation_result : apiResponse = {"data": []}

        for solution in solutions:
            batch: sim_batch = {
                "batchtype": "container",
                "details": [
                    {
                        "masterid": solution["container"].type_id,
                        "mastertype": "container",
                        "total_weight": solution["container"].total_weight,
                    }
                ],
            }

            for item in solution["container"].items:
                batch["details"].append(
                    {
                        "masterid": item.itemType_id,
                        "mastertype": item.itemType,
                        "orderid": item.order_id,
                        "position": item.position,
                        "rotation": item.rotation,
                    }
                )

            simulation_result["data"].append(batch)
        
        simulate_entry = db.query(Simulate).join(Simulatedetail).filter(
            Simulatedetail.orderid == int(products[0].orderid)

        ).first()

        if not simulate_entry:
            raise HTTPException(status_code=404, detail="ไม่พบข้อมูล simulateId สำหรับ orderId นี้")

        simulateid = simulate_entry.simulateid 

        background_tasks.add_task(save_simulation_batches_internal, simulation_result, db)

        
        return simulation_result

    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))



@router.post("/simulate/pallet_container")
def simulate_containers(
    products: List[RequestProduct],
    pallets: List[RequestPallet],
    containers: List[RequestContainer],
    background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    try:
        # convert request params into model classes
        ind_items = [item for item in products for _ in range(item.qtt)]
        ind_pallets = [pallet for pallet in pallets for _ in range(pallet.qtt)]
        ind_containers = [
            container for container in containers for _ in range(container.qtt)
        ]        
        model_products = [
            Item(
                id=str(id),
                itemType_id=item.productid,
                itemType="product",
                length=item.productlength,
                width=item.productwidth,
                height=item.productheight,
                weight=item.productweight,
                isSideUp=item.issideup,
                maxStack=(
                    item.maxstack
                    if not (item.notstack or item.isfragile or item.istop)
                    else 0
                ),
                order_id=item.orderid,
                priority=item.priority,
            )
            for id, item in enumerate(ind_items)

        ]
        model_pallets = [
            Container(
                id=str(id),
                type_id=pallet.palletid,
                length=pallet.loadlength,
                width=pallet.loadwidth,
                height=pallet.loadheight,
                exlength=pallet.palletlength,
                exwidth=pallet.palletwidth,
                exheight=pallet.palletheight,
                exweight=pallet.palletweight,
                max_weight=pallet.loadweight,
                priority=pallet.priority,
            )
            for id, pallet in enumerate(ind_pallets)

        ]

        pallet_solutions = simulate(
            model_containers=model_pallets, model_items=model_products
        )

        for solution in pallet_solutions:
            if len(solution["unused"]) > 0:
                return {"error": "unable to fit all products into given containers."}
            if solution["fitness"] < 0:
                return {"error": "unable to arrange the products."}

        model_items = [
            Item(
                id=solution["container"].id,
                itemType_id=solution["container"].type_id,
                itemType="sim_batch",
                length=solution["container"].exlength,
                width=solution["container"].exwidth,
                height=solution["container"].exheight + solution["container"].height,
                weight=solution["container"].exweight
                + solution["container"].total_weight,
                isSideUp=True,
                maxStack=0,
                grounded=True,
                order_id="",
                priority=solution["container"].priority,
            )
            for solution in pallet_solutions
        ]
        model_containers = [
            Container(
                id=str(id),
                type_id=container.containerid,
                length=container.loadlength,
                width=container.loadwidth,
                height=container.loadheight,
                exlength=container.containerlength,
                exwidth=container.containerwidth,
                exheight=container.containerheight,
                exweight=container.containerweight,
                max_weight=container.loadweight,
                priority=container.priority,
            )
            for id, container in enumerate(ind_containers)
        ]

        solutions = simulate(
            model_containers=model_containers, model_items=model_items, centered=False
        )

        simulation_result : apiResponse = {"data": []}

        for solution in solutions:

            batch: sim_batch = {
                "batchtype": "container",
                "details": [
                    {
                        "masterid": solution["container"].type_id,
                        "mastertype": "container",
                        "total_weight": solution["container"].total_weight,
                    }
                ],
            }

            for item in solution["container"].items:
                pallet_solution: ContainerLoadingSolution = next(
                    x for x in pallet_solutions if x["container"].id == item.id
                )

                sub_detail: sub_sim_batch_detail = {
                    "mastertype": "sim_batch",
                    "position": item.position,
                    "rotation": item.rotation,
                    "total_weight": item.weight,
                    "sim_batch": {
                        "batchtype": "palletoncontainer",
                        "details": [
                            {
                                "masterid": pallet_solution["container"].type_id,
                                "mastertype": "pallet",
                                "total_weight": pallet_solution[
                                    "container"
                                ].total_weight,
                            }
                        ],
                    },
                }

                for product in pallet_solution["container"].items:
                    sub_detail["sim_batch"]["details"].append(
                        {
                            "masterid": product.itemType_id,
                            "mastertype": product.itemType,
                            "orderid": product.order_id,
                            "position": product.position,
                            "rotation": product.rotation,
                        }
                    )

                batch["details"].append(sub_detail)

            simulation_result["data"].append(batch)
        
        simulate_entry = db.query(Simulate).join(Simulatedetail).filter(
            Simulatedetail.orderid == int(products[0].orderid)

        ).first()

        if not simulate_entry:
            raise HTTPException(status_code=404, detail="ไม่พบข้อมูล simulateId สำหรับ orderId นี้")

        simulateid = simulate_entry.simulateid 

        background_tasks.add_task(save_simulation_batches_internal, simulation_result, db)

        
        return simulation_result

    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))