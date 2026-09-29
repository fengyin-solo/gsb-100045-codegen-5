"""停运记录业务规则：停运须与司机档案同一资格版本，恢复后须重新审核。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "suspension"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SuspensionService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [
                row for row in rows
                if keyword in str(row.get("停运编号", ""))
                or keyword in str(row.get("司机编号", ""))
                or keyword in str(row.get("司机姓名", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("状态") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def create_suspension(self, driver: dict[str, Any], reason: str) -> dict[str, Any]:
        """由司机办理停运时调用，记录与档案同一资格版本。"""
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry["停运编号"] = f"SUSP-{entry['id']:04d}"
        entry["司机id"] = driver.get("id")
        entry["司机编号"] = driver.get("司机编号")
        entry["司机姓名"] = driver.get("姓名")
        entry["停运原因"] = reason or "未填写"
        entry["停运时间"] = _now()
        entry["资格版本"] = int(driver.get("资格版本", 0))
        entry["状态"] = "停运中"
        entry["恢复时间"] = ""
        entry["pending"] = True
        entry["abnormal"] = True
        rows.append(entry)
        return entry

    def close_active_for_driver(self, driver_id: int) -> None:
        """恢复调度时结案该司机未结束的停运记录。"""
        for row in store.rows(MODULE):
            if int(row.get("司机id", 0)) == driver_id and row.get("状态") == "停运中":
                row["状态"] = "已恢复"
                row["恢复时间"] = _now()
                row["pending"] = False
                row["abnormal"] = False

    def sync_version(self, driver_id: int, version: int) -> None:
        """资格版本与司机档案保持一致。"""
        for row in store.rows(MODULE):
            if int(row.get("司机id", 0)) == driver_id:
                row["资格版本"] = version
