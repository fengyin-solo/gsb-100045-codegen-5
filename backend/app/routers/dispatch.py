"""调度工作台接口：维护调度名单（排班结果），受理时核验资格状态、任务结清与版本一致。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.dispatch import DispatchService
from app.services.driver import DriverService
from app.services.suspension import SuspensionService

router = APIRouter(prefix="/api/dispatch", tags=["调度工作台"])

service = DispatchService()
driver_service = DriverService()
suspension_service = SuspensionService()


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按调度编号、司机编号或姓名检索"),
    status: str | None = Query(default=None, description="待执行、执行中、已完成、已取消"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """调度名单列表（排班结果）；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/workbench", response_model=dict)
def workbench() -> dict[str, Any]:
    """调度工作台：可调度司机、待审核司机、停运司机与在途任务一屏汇总。"""
    drivers, _ = driver_service.list_entries(page=1, size=1000)
    dispatches, _ = service.list_entries(page=1, size=1000)
    suspensions, _ = suspension_service.list_entries(page=1, size=1000)
    ready = [d for d in drivers if d.get("资格状态") == "可调度"]
    pending = [d for d in drivers if d.get("资格状态") == "待审核"]
    suspended = [d for d in drivers if d.get("资格状态") == "停运"]
    active = [d for d in dispatches if d.get("任务状态") in ("待执行", "执行中")]
    cards = [
        {"label": "可调度司机", "value": len(ready)},
        {"label": "待审核司机", "value": len(pending)},
        {"label": "停运司机", "value": len(suspended)},
        {"label": "在途任务", "value": len(active)},
    ]
    return {"cards": cards, "drivers": drivers, "active_dispatches": active, "suspensions": suspensions}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条调度记录；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"调度记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """加入调度名单：顺序错误、任务未结清、版本不一致或调度冲突都会被拦下并说明原因。"""
    entry, message = service.create_dispatch(payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/complete", response_model=ActionResult)
def complete_entry(entry_id: int) -> ActionResult:
    """完成调度任务并结清任务。"""
    entry, message = service.complete_dispatch(entry_id)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/cancel", response_model=ActionResult)
def cancel_entry(entry_id: int) -> ActionResult:
    """取消调度任务并回写任务结清状态。"""
    entry, message = service.cancel_dispatch(entry_id)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出调度名单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "dispatch", "total": total, "items": items}
