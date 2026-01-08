from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from ..database import get_db
from sqlalchemy.orm import Session, joinedload, defer
from .. import models
from app.routes.simulation import get_simulation_data
from app.routes.tasks import get_task_running
from app.celery.tasks import pdfTask
import os

router = APIRouter(tags=["Reports"])


@router.get("/pdf/")
def get_pdf(simulate_id: int, db: Session = Depends(get_db)):
    pdf_path = f"/pdf/{simulate_id}.pdf"
    if not os.path.exists(pdf_path):
        simulate_entry: models.Simulate = (
            db.query(models.Simulate)
            .filter(models.Simulate.simulate_id == simulate_id)
            .first()
        )
        if not simulate_entry:
            raise HTTPException(
                status_code=500, detail=f"data not found for simulateId {simulate_id}"
            )
        match simulate_entry.pdf_status:
            case models.Status.PENDING:
                if simulate_entry.pdf_task_id and get_task_running(
                    simulate_entry.pdf_task_id, "pdf"
                ):
                    return {
                        "simulate_by": simulate_entry.simulate_by,
                        "start_datetime": simulate_entry.start_datetime,
                        "simulatetype": simulate_entry.simulatetype,
                        "simulate_status": models.Status.PENDING,
                    }
                simulate_entry.pdf_status = models.Status.FAILURE
                simulate_entry.error_message = (
                    "This task can’t be re-simulated. Please start a new simulation."
                )
                db.commit()
                db.refresh(simulate_entry)
                return {
                    "simulate_by": simulate_entry.simulate_by,
                    "start_datetime": simulate_entry.start_datetime,
                    "simulatetype": simulate_entry.simulatetype,
                    "simulate_status": models.Status.FAILURE,
                    "error": simulate_entry.error_message
                    or "Unexpected Error During Simulation",
                }
            case models.Status.FAILURE:
                return {
                    "simulate_by": simulate_entry.simulate_by,
                    "start_datetime": simulate_entry.start_datetime,
                    "simulatetype": simulate_entry.simulatetype,
                    "simulate_status": models.Status.FAILURE,
                    "error": simulate_entry.error_message
                    or "Unexpected Error During PDF Generation.",
                }
        if simulate_entry.simulate_status != models.Status.SUCCESS:
            return {
                "simulate_by": simulate_entry.simulate_by,
                "start_datetime": simulate_entry.start_datetime,
                "simulatetype": simulate_entry.simulatetype,
                "simulate_status": models.Status.FAILURE,
                "error": f"Simulation simulate_status is {simulate_entry.simulate_status.value}.",
            }

        simdata = get_simulation_data(simulate_id, db)

        task = pdfTask.delay(simdata.model_dump(), simulate_id)

        simulate_entry.pdf_status = models.Status.PENDING
        simulate_entry.pdf_task_id = task.id
        db.commit()
        return {
            "simulate_by": simulate_entry.simulate_by,
            "start_datetime": simulate_entry.start_datetime,
            "simulatetype": simulate_entry.simulatetype,
            "simulate_status": models.Status.PENDING,
        }

    if not os.path.exists(pdf_path):
        return Response(
            content="PDF file not found", media_type="text/plain", status_code=500
        )

    with open(pdf_path, "rb") as pdf_file:
        pdf_content = pdf_file.read()

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline; filename=document.pdf"
        },  # "inline" to display in browser, "attachment" to download
    )


@router.get("/")
async def get_reports(
    background_tasks: BackgroundTasks,
    skip: int = 0,
    limit: int = None,
    db: Session = Depends(get_db),
):
    try:
        total_count = db.query(models.Simulate).count()
        reports = (
            db.query(models.Simulate)
            .options(defer(models.Simulate.snapshot_data))
            .options(
                joinedload(models.Simulate.details).subqueryload(
                    models.Simulatedetail.order
                )
            )
            .order_by(models.Simulate.simulate_id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        for report in reports:
            if report.simulate_status == models.Status.FAILURE:
                if report.pdf_status != models.Status.FAILURE:
                    report.pdf_status = models.Status.FAILURE
                continue
            if report.pdf_status != models.Status.PENDING:
                continue
            if not get_task_running(report.pdf_task_id, "pdf"):
                report.pdf_status = models.Status.FAILURE
        background_tasks.add_task(db.commit)
        return {
            "items": reports,
            "total_count": total_count,
        }
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.delete("/")
async def delete_report(simulate_id: str, db: Session = Depends(get_db)):
    report_to_delete = (
        db.query(models.Simulate)
        .filter(models.Simulate.simulate_id == simulate_id)
        .first()
    )

    if not report_to_delete:
        raise HTTPException(status_code=404, detail="Report not Found")

    pdf_path = f"/pdf/{simulate_id}.pdf"

    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    db.delete(report_to_delete)
    db.commit()

    return {"message": "report delete"}


@router.get("/success")
async def get_success_simu(db: Session = Depends(get_db)):
    try:
        # ดึง simulate_id ที่มีอยู่ใน sim_batch
        batches = db.query(models.Simbatch.simulate_id).distinct().all()
        return [{"simulate_id": batch.simulate_id} for batch in batches]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
