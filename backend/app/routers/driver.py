"""司机档案接口：维护驾驶人员，覆盖资格审核、办理停运、恢复调度与详情回写。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.dispatch import DispatchService
from app.services.driver import DriverService
from app.services.suspension import SuspensionService

router = APIRouter(prefix="/api/driver", tags=["司机管理"])

service = DriverService()
dispatch_service = DispatchService()
suspension_service = SuspensionService()

LIST_FIELDS = ["司机编号", "姓名", "驾驶证号", "从业资格证", "健康证有效期", "联系手机", "所属车队", "司机状态"]
STATUSES = ["在岗", "出车中", "休息", "停岗"]
QUALIFICATION_STATUSES = ["待审核", "可调度", "停运"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按司机编号或姓名检索"),
    status: str | None = Query(default=None, description="在岗、出车中、休息、停岗"),
    qualification: str | None = Query(default=None, description="待审核、可调度、停运"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按司机编号/姓名、工作状态与资格状态过滤司机列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        keyword=keyword, status=status, qualification=qualification, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条驾驶人员明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"驾驶人员 {entry_id} 不存在或已归档")
    return entry


@router.get("/{entry_id}/detail", response_model=dict)
def get_detail(entry_id: int) -> dict:
    """司机详情：档案、资格信息、排班结果与停运记录一并返回，且反映同一资格版本。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"驾驶人员 {entry_id} 不存在或已归档")
    dispatches, _ = dispatch_service.list_entries(page=1, size=200)
    dispatches = [row for row in dispatches if int(row.get("司机id", 0)) == entry_id]
    suspensions, _ = suspension_service.list_entries(page=1, size=200)
    suspensions = [row for row in suspensions if int(row.get("司机id", 0)) == entry_id]
    return {"driver": entry, "dispatches": dispatches, "suspensions": suspensions}


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条驾驶人员，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="驾驶人员已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条驾驶人员执行安排出车、办理停岗、恢复在岗；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/review", response_model=ActionResult)
def submit_review(entry_id: int) -> ActionResult:
    """提交资格审核：核验驾驶证、从业资格证、任务结清证明，通过后资格状态待审核→可调度。"""
    entry, message = service.submit_review(entry_id)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/suspend", response_model=ActionResult)
def suspend_driver(entry_id: int, payload: EntryPayload) -> ActionResult:
    """办理停运：只有可调度司机可停运，生成停运记录并撤回未执行排班。"""
    reason = str((payload.values.get("reason") if payload.values else "") or "").strip()
    entry, message = service.suspend_driver(entry_id, reason)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/reinstate", response_model=ActionResult)
def reinstate_driver(entry_id: int) -> ActionResult:
    """恢复调度：停运后再次变更，须回到待审核重新提交资格审核。"""
    entry, message = service.reinstate_driver(entry_id)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/cert", response_model=ActionResult)
def set_cert(entry_id: int, payload: EntryPayload) -> ActionResult:
    """登记驾驶证 / 从业资格证核验结果。"""
    field = str(payload.values.get("field") or "").strip()
    verified = bool(payload.values.get("verified"))
    entry, message = service.set_cert_verified(entry_id, field, verified)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出司机管理清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "driver", "total": total, "items": items}
