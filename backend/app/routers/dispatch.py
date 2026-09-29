"""调度工作台接口：调度名单、排班选中与停运记录。

所有名单与排班记录都快照司机资格版本；顺序错误（未审核、未结清、版本过期）
或同一司机被两个调度动作同时选中时，只接受先通过审核且任务已结清的一项。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.schemas import ActionResult, PageResult
from app.services.dispatch import DispatchService

router = APIRouter(prefix="/api/dispatch", tags=["调度工作台"])

service = DispatchService()


class RosterPayload(BaseModel):
    司机ID: int


class SchedulePayload(BaseModel):
    司机ID: int
    任务名称: str = Field(..., description="调度动作名称，如：早班冷链配送")
    名单ID: int | None = None


class BatchSchedulePayload(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/roster", response_model=PageResult[dict])
def list_roster(
    keyword: str | None = Query(default=None, description="按司机编号或姓名检索"),
    status: str | None = Query(default=None, description="待排班、已排班、随资格停运"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """调度名单：实时反映司机档案的资格版本与审核结论。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_roster(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/roster", response_model=ActionResult)
def add_roster(payload: RosterPayload) -> ActionResult:
    """新增司机调度名单：先核验资格到可调度且任务已结清，否则拒绝并说明顺序。"""
    entry, message = service.add_to_roster(payload.司机ID)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/schedules")
def list_schedules(only_active: bool = False) -> dict[str, Any]:
    """排班结果：可只看当前锁定（被调度动作选中）的记录。"""
    rows = service.list_schedules(only_active=only_active)
    return {"module": "schedule", "total": len(rows), "items": rows}


@router.post("/schedules", response_model=ActionResult)
def create_schedule(payload: SchedulePayload) -> ActionResult:
    """选中司机执行调度动作；同一司机已被别的动作选中时本动作不受理。"""
    entry, message = service.select_schedule(
        payload.司机ID, payload.任务名称, roster_id=payload.名单ID
    )
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/schedules/batch")
def batch_create_schedules(payload: BatchSchedulePayload) -> dict[str, Any]:
    """批量排班：同一名司机被两个动作同时选中时，只有先通过审核且已结清的一项生效。"""
    result = service.batch_select(payload.items)
    return {
        "ok": not result["rejected"],
        "accepted_count": len(result["accepted"]),
        "rejected_count": len(result["rejected"]),
        **result,
    }


@router.post("/schedules/{schedule_id}/release", response_model=ActionResult)
def release_schedule(schedule_id: int) -> ActionResult:
    """任务完成并结清后释放排班，司机回到可调度池。"""
    entry, message = service.release_schedule(schedule_id)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/suspensions")
def list_suspensions() -> dict[str, Any]:
    """停运记录：每条绑定停运时的资格版本，重新审核不影响历史落痕。"""
    rows = service.list_suspensions()
    return {"module": "suspension", "total": len(rows), "items": rows}
