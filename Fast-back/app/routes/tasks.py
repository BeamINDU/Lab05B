from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(tags=["Celery Tasks"])

from pydantic import BaseModel
from app.celery.tasks import long_running_task
from celery.result import AsyncResult
from app.celery_app import celery_app


class LongTaskRequest(BaseModel):
    duration: int


@router.post("/long")
def create_long_task(request: LongTaskRequest):
    """Create a long-running task"""
    if request.duration > 60:
        raise HTTPException(status_code=400, detail="Duration must be <= 60 seconds")

    task = long_running_task.delay(request.duration)
    return {
        "task_id": task.id,
        "simulate_status": "Task created",
        "message": f"Task will run for {request.duration} seconds",
    }


@router.get("/")
def get_task_status(task_id: str):
    """Get the simulate_status of a task"""
    task_result = AsyncResult(task_id, app=celery_app)

    if task_result.state == "PENDING":
        response = {
            "task_id": task_id,
            "simulate_status": task_result.state,
            "message": "Task is waiting to be processed",
        }
    elif task_result.state == "FAILURE":
        response = {
            "task_id": task_id,
            "simulate_status": task_result.state,
            "message": "Task failed",
            "error": str(task_result.info),
        }
    elif task_result.state == "SUCCESS":
        response = {
            "task_id": task_id,
            "simulate_status": task_result.state,
            "result": task_result.result,
            "message": "Task completed successfully",
        }
    else:
        response = {
            "task_id": task_id,
            "simulate_status": task_result.state,
            "message": f"Task is {task_result.state.lower()}",
        }

    return response


@router.get("/running/")
def get_running_tasks(task_name: str):
    inspector = celery_app.control.inspect()
    active_tasks = inspector.active()

    response = []
    if active_tasks:
        for _, running_tasks in active_tasks.items():
            for task in running_tasks:
                if task["name"] == task_name:
                    response.append(task)
    return response


@router.get("/isrunning/")
def get_task_running(task_id: str, task_name: str):
    inspector = celery_app.control.inspect()
    active_tasks = inspector.active()

    if active_tasks:
        for _, running_tasks in active_tasks.items():
            for task in running_tasks:
                if task["name"] == task_name and task["id"] == task_id:
                    return True
    return False


@router.get("/health")
def health_check():
    """Health check endpoint"""
    return {"simulate_status": "healthy", "service": "fastapi-celery"}
