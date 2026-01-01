from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from sorawm.server.schemas import QueueStatusResponse, WMRemoveResults
from sorawm.schemas import CleanerType
from sorawm.server.worker import worker

router = APIRouter()


async def process_upload_and_queue(
    task_id: str, video_content: bytes, video_path: Path
):
    try:
        async with aiofiles.open(video_path, "wb") as f:
            await f.write(video_content)
        await worker.queue_task(task_id, video_path)
    except Exception as e:
        await worker.mark_task_error(task_id, str(e))


@router.get("/get_queue_status")
async def get_queue_status() -> QueueStatusResponse:
    """
    Retrieve the current status of the processing queue.

    Returns:
        QueueStatusResponse: Current queue metrics and task states (e.g., counts and statuses of queued, running, and finished tasks).
    """
    return await worker.get_queue_status()


@router.post("/submit_remove_task")
async def submit_remove_task(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    cleaner_type: CleanerType = Query(default=CleanerType.LAMA),
):
    """
    Create a watermark-removal task for the provided video and schedule the file upload and queuing to run in the background.

    Parameters:
        video (UploadFile): Incoming uploaded video file.
        cleaner_type (CleanerType): Cleaner algorithm to use for the task; defaults to `CleanerType.LAMA`.

    Returns:
        dict: A mapping containing `task_id` (the created task identifier) and `message` confirming submission.
    """
    task_id = await worker.create_task(cleaner_type)
    content = await video.read()
    upload_filename = f"{uuid4()}_{video.filename}"
    video_path = worker.upload_dir / upload_filename
    background_tasks.add_task(process_upload_and_queue, task_id, content, video_path)

    return {"task_id": task_id, "message": "Task submitted."}


@router.get("/get_results")
async def get_results(remove_task_id: str) -> WMRemoveResults:
    result = await worker.get_task_status(remove_task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Task does not exist.")

    return result


@router.get("/download/{task_id}")
async def download_video(task_id: str):
    result = await worker.get_task_status(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Task does not exist.")
    if result.status != "FINISHED":
        raise HTTPException(
            status_code=400, detail=f"Task not finish yet: {result.status}"
        )
    output_path = await worker.get_output_path(task_id)
    if output_path is None or not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file does not exits")

    return FileResponse(
        path=output_path, filename=output_path.name, media_type="video/mp4"
    )
