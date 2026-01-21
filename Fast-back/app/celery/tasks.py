from typing import Literal
from app.celery_app import celery_app
import time
from fastapi import HTTPException, Depends
from sqlalchemy.orm import scoped_session
from app.database import SessionLocal
from app import schemas, crud, models, pdf_mock, utils
from app.logger import logger

ScopedSession = scoped_session(SessionLocal)

__all__ = ["celery_app", "long_running_task"]


@celery_app.task(name="pdf", bind=True, pydantic=True, time_limit=1800)
def pdfTask(
    self,
    payload: dict,  # ✅ รับเป็น dict
    simulate_id: int,
) -> int:
    db = ScopedSession()
    try:
        logger.info(f"Starting Pdf Task with id: {self.request.id}")
        simulate_entry: models.Simulate = (
            db.query(models.Simulate)
            .filter(models.Simulate.simulate_id == simulate_id)
            .first()
        )
        
        if not simulate_entry:
            raise Exception(f"data not found for simulateId {simulate_id}")

        try:
            if simulate_entry.simulate_status != models.Status.SUCCESS:
                raise Exception(
                    f"simulation simulate_status is {simulate_entry.simulate_status}"
                )

            start_time = time.perf_counter()
            
            # ✅ ใช้ pdf_mock แทน pdf (สำหรับ Phase 1)
            # TODO: Phase 2 เปลี่ยนกลับเป็น pdf.create_report()
            pdf_mock.create_report(payload, simulate_id)
            
            end_time = time.perf_counter()
            
            simulate_entry.pdf_status = models.Status.SUCCESS
            db.commit()

            elapsed_time = end_time - start_time
            logger.info(f"Pdf Task completed after {elapsed_time} seconds")
            
            return {
                "simulate_status": models.Status.SUCCESS,
                "message": f"Pdf Task completed after {elapsed_time} seconds",
            }

        except Exception as e:
            db.rollback()
            simulate_entry.pdf_status = models.Status.FAILURE
            simulate_entry.error_message = str(e)
            db.commit()
            raise e
            
    except Exception as e:
        logger.info(f"Pdf Task Failed: {str(e)}")
        raise e
    finally:
        db.close()
        ScopedSession.remove()


@celery_app.task(name="simulate", bind=True, pydantic=True, time_limit=1800)
def simulateTask(
    self,
    payload: schemas.SimulationPayload,
    simulate_id: int,
):
    db = ScopedSession()
    try:
        logger.info(f"Starting Simulate Task with id: {self.request.id}")
        simulate_entry: models.Simulate = (
            db.query(models.Simulate)
            .filter(models.Simulate.simulate_id == simulate_id)
            .first()
        )
        if not simulate_entry:
            raise Exception(f"data not found for simulateId {simulate_id}")

        try:
            start_time = time.perf_counter()
            simulation_result: list[schemas.SimbatchBase] = utils.simulate(
                payload, simulate_entry.simulatetype
            )
            end_time = time.perf_counter()
            # save to database
            simulate_entry.simulate_status = models.Status.SUCCESS
            db.flush()
            crud.save_simulation_batches_internal(simulation_result, simulate_id, db)

            reformattedSnapshot_data = utils.reformatSnapshotData(payload)
            simulateData = schemas.SimulateBase.model_validate(simulate_entry)

            response_data = crud.convert_simulation_format(
                simulateData.batches, reformattedSnapshot_data, db
            )

            pdfPayload = schemas.SimulationGetResponse(
                data=response_data,
                simulate_by=simulate_entry.simulate_by,
                start_datetime=simulate_entry.start_datetime,
                simulatetype=simulate_entry.simulatetype,
                simulate_status=simulate_entry.simulate_status,
                simulate_id=simulate_entry.simulate_id,
            )

            task = pdfTask.delay(pdfPayload.model_dump(), simulate_id)

            simulate_entry.pdf_status = models.Status.PENDING
            simulate_entry.pdf_task_id = task.id
            db.commit()

            elapsed_time = end_time - start_time
            logger.info(
                f"Simulate Task with id: {self.request.id} completed after {elapsed_time} seconds"
            )
            return {
                "simulate_status": models.Status.SUCCESS,
                "result": [result.model_dump() for result in simulation_result],
                "pdf_task_id": task.id,
                "message": f"Simulate Task completed after {elapsed_time} seconds",
            }

        except HTTPException as e:
            db.rollback()
            if not simulate_entry:
                raise Exception(f"data not found for simulateId {simulate_id}")
            simulate_entry.simulate_status = models.Status.FAILURE
            simulate_entry.pdf_status = models.Status.FAILURE
            simulate_entry.error_message = e.detail
            db.commit()

            raise Exception(e.detail)
        except Exception as e:
            db.rollback()
            if not simulate_entry:
                raise Exception(f"data not found for simulateId {simulate_id}")
            simulate_entry.simulate_status = models.Status.FAILURE
            simulate_entry.pdf_status = models.Status.FAILURE
            simulate_entry.error_message = str(e)
            db.commit()

            raise e
    except Exception as e:
        logger.info(f"Simulate Task with id: {self.request.id} Failed")
        raise e
    finally:
        db.close()
        ScopedSession.remove()


@celery_app.task(name="simulateNoSave", bind=True, pydantic=True, time_limit=1800)
def simulateNoSaveTask(
    self,
    payload: schemas.SimulationPayload,
    simulatetype: Literal["pallet", "container", "pallet_container"],
    job_id: int = None,
):
    try:
        logger.info(f"Starting Simulate Task with id: {self.request.id}")
        start_time = time.perf_counter()
        simulation_result: list[schemas.SimbatchBase] = utils.simulate(
            payload, simulatetype
        )
        end_time = time.perf_counter()

        reformattedSnapshot_data = utils.reformatSnapshotData(payload)

        response_data: list[schemas.SimBatch] = crud.convert_simulation_format(
            simulation_result, reformattedSnapshot_data
        )

        elapsed_time = end_time - start_time
        logger.info(
            f"Simulate Task with id: {self.request.id} completed after {elapsed_time} seconds"
        )
        return {
            "job_id": job_id,
            "simulate_status": models.Status.SUCCESS,
            "result": [result.model_dump() for result in response_data],
            "message": f"Simulate Task completed after {elapsed_time} seconds",
        }

    except HTTPException as e:
        logger.info(f"Simulate Task with id: {self.request.id} Failed")
        return {
            "job_id": job_id,
            "simulate_status": models.Status.FAILURE,
            "error": str(e.detail),
        }
    except Exception as e:
        logger.info(f"Simulate Task with id: {self.request.id} Failed")
        return {"job_id": job_id, "simulate_status": models.Status.FAILURE, "error": str(e)}


@celery_app.task(name="long_running_task")
def long_running_task(duration: int) -> dict:
    """Simulates a long-running task"""
    time.sleep(duration)
    return {
        "simulate_status": models.Status.SUCCESS,
        "duration": duration,
        "message": f"Task completed after {duration} seconds",
    }
