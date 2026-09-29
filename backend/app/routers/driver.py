"""司机管理接口：维护驾驶人员档案与调度资格审核。

资格主线：登记（待审核）→ 材料核验（审核中）→ 审核通过（可调度）→ 办理停运；
停运后再次变更必须重新审核，资格版本递增。审核结论随档案返回，供调度工作台、
司机列表和详情三处展示同一版本。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.driver import CHECK_ITEMS, QUAL_ORDER, DriverService

router = APIRouter(prefix="/api/driver", tags=["司机管理"])

service = DriverService()

LIST_FIELDS = ["司机编号", "姓名", "驾驶证号", "从业资格证", "健康证有效期", "联系手机", "所属车队"]
STATUSES = list(QUAL_ORDER)


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按司机编号或姓名检索"),
    status: str | None = Query(default=None, description="待审核、审核中、可调度、停运"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按司机编号与资格状态过滤司机列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条驾驶人员；新档案资格为待审核 v1，须核验三项材料后才能流转。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="驾驶人员已登记，资格状态：待审核", entry=entry)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出司机管理清单：返回当前全量数据（含资格版本与审核结论）。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "driver", "total": total, "items": items}


@router.get("/{entry_id}/detail", response_model=dict)
def get_detail(entry_id: int) -> dict[str, Any]:
    """司机详情：档案 + 调度名单、排班结果、停运记录，并核对资格版本一致性。"""
    detail = service.detail(entry_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"驾驶人员 {entry_id} 不存在或已归档")
    return detail


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条驾驶人员档案；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"驾驶人员 {entry_id} 不存在或已归档")
    return entry


@router.post("/{entry_id}/verify", response_model=ActionResult)
def verify_docs(entry_id: int, payload: EntryPayload) -> ActionResult:
    """逐项核验驾驶证、从业资格证、任务结清证明；三项全部通过才进入审核中。"""
    raw = payload.values.get("checks", payload.values)
    checks = {item: bool(raw.get(item)) for item in CHECK_ITEMS if item in raw}
    if not checks:
        return ActionResult(
            ok=False,
            message=f"请至少勾选一项核验结果（{ '、'.join(CHECK_ITEMS) }）",
        )
    entry, message = service.verify_docs(entry_id, checks)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """执行资格动作：审核通过、审核驳回、办理停运、重新审核；跳级会被拦下并说明顺序。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
