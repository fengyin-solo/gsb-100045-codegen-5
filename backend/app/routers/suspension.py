"""停运记录接口：查询司机停运记录，记录与司机档案保持同一资格版本。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import PageResult
from app.services.suspension import SuspensionService

router = APIRouter(prefix="/api/suspension", tags=["停运记录"])

service = SuspensionService()


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按停运编号、司机编号或姓名检索"),
    status: str | None = Query(default=None, description="停运中、已恢复"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """停运记录列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出停运记录：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "suspension", "total": total, "items": items}
