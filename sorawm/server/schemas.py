from enum import StrEnum
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Status(StrEnum):
    UPLOADING = "UPLOADING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    FINISHED = "FINISHED"
    ERROR = "ERROR"


class WMRemoveResults(BaseModel):
    percentage: int
    status: Status
    download_url: str | None = None


class QueueSummary(BaseModel):
    is_busy: bool = Field(..., description="当前是否正在处理任务")
    queue_length: int = Field(..., description="当前排队等待的任务数量")
    total_active: int = Field(..., description="活跃任务总数 (进行中 + 排队中)")


class QueueTaskInfo(BaseModel):
    id: str
    status: str
    percentage: int
    video_path: str
    created_at: Optional[datetime] = Field(None, description="任务创建时间")  # 新增字段


class QueueStatusResponse(BaseModel):
    summary: QueueSummary
    current_task_id: Optional[str] = Field(None, description="当前正在运行的任务ID")
    waiting_queue: List[QueueTaskInfo] = Field(
        default_factory=list, description="排队中的任务列表"
    )
