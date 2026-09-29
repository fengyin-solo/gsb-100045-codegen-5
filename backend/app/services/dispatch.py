"""调度名单业务规则：先通过资格审核且任务已结清才能进入排班。

核心口径：
- 顺序错误拦截：资格状态未到「可调度」不能加入调度名单；
- 任务结清拦截：存在未结清任务不能调度；
- 资格版本一致：排班记录截取档案当前资格版本，版本不一致不予受理；
- 同一司机被两个调度动作同时选中时，只接受先通过审核（审核通过时间更早）且任务已结清的一项。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "dispatch"
DISPATCH_ACTIVE = ["待执行", "执行中"]
DISPATCH_DONE = "已完成"
DISPATCH_CANCELLED = "已取消"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class DispatchService:
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
                if keyword in str(row.get("调度编号", ""))
                or keyword in str(row.get("司机编号", ""))
                or keyword in str(row.get("司机姓名", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("任务状态") == status]
        # 实时回写司机资格状态/版本/审核结论，保证调度工作台与档案一致
        for row in rows:
            driver_id = row.get("司机id")
            if driver_id is not None:
                driver = store.find("driver", int(driver_id))
                if driver:
                    row["资格状态"] = driver.get("资格状态")
                    row["资格版本"] = driver.get("资格版本")
                    row["审核结论"] = driver.get("审核结论")
                    row["任务结清证明"] = driver.get("任务结清证明")
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_dispatch(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        raw_id = values.get("司机id") if values.get("司机id") is not None else values.get("driver_id")
        try:
            driver_id = int(raw_id)
        except (TypeError, ValueError):
            return None, "请选择要调度的司机"
        driver = store.find("driver", driver_id)
        if driver is None:
            return None, f"司机 {driver_id} 不存在或已归档"

        # 顺序错误拦截：资格状态必须已审核通过至可调度
        if driver.get("资格状态") != "可调度":
            return None, (
                f"顺序错误：司机「{driver.get('姓名')}」资格状态为「{driver.get('资格状态')}」，"
                f"须审核通过至「可调度」后才能加入调度名单"
            )
        version = int(driver.get("资格版本", 0))
        review_time = str(driver.get("审核通过时间") or "")

        # 资格版本一致性：提交的版本必须与档案当前版本一致
        submitted = values.get("资格版本")
        if submitted not in (None, "", version, str(version)):
            return None, f"资格版本不一致：档案当前为 v{version}，提交为 v{submitted}，请刷新后重试"

        # 并发/重复调度拦截：同一司机只接受先通过审核且任务已结清的一项
        conflict = None
        for existing in store.rows(MODULE):
            if int(existing.get("司机id", 0)) != driver_id:
                continue
            if existing.get("任务状态") not in DISPATCH_ACTIVE:
                continue
            # 已存在有效排班：只接受审核通过时间更早（先通过审核）且任务已结清的一项
            if str(existing.get("审核通过时间") or "") <= review_time:
                conflict = (
                    f"同一司机调度冲突：司机「{driver.get('姓名')}」已有先通过审核且任务已结清的排班"
                    f"（{existing.get('调度编号')}），本次调度不予受理"
                )
            else:
                conflict = "同一司机调度冲突：本次调度晚于已受理排班，不予受理"
            break
        if conflict:
            return None, conflict

        # 任务结清拦截
        if driver.get("任务结清证明") != "已结清":
            return None, (
                f"任务未结清：司机「{driver.get('姓名')}」尚有未结清任务，"
                f"任务结清后才能调度"
            )

        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry["调度编号"] = str(values.get("调度编号") or f"DISP-{entry['id']:04d}")
        entry["司机id"] = driver_id
        entry["司机编号"] = driver.get("司机编号")
        entry["司机姓名"] = driver.get("姓名")
        entry["线路编号"] = str(values.get("线路编号") or "")
        entry["车辆编号"] = str(values.get("车辆编号") or "")
        entry["排班日期"] = str(values.get("排班日期") or _now()[:10])
        entry["班次"] = str(values.get("班次") or "")
        entry["资格版本"] = version
        entry["审核通过时间"] = review_time
        entry["任务状态"] = "待执行"
        entry["结清状态"] = "未结清"
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)

        # 回写司机：产生在途任务，任务结清证明置为未结清
        driver["任务结清证明"] = "未结清"
        driver["status"] = "出车中"
        driver["pending"] = True
        return entry, f"调度名单已受理：{entry['调度编号']}（资格版本 v{version}）"

    def complete_dispatch(self, entry_id: int) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"调度记录 {entry_id} 不存在"
        if entry.get("任务状态") not in DISPATCH_ACTIVE:
            return None, f"调度记录 {entry.get('调度编号')} 当前状态为「{entry.get('任务状态')}」，无需完成"
        entry["任务状态"] = DISPATCH_DONE
        entry["结清状态"] = "已结清"
        entry["pending"] = False
        driver_id = entry.get("司机id")
        if driver_id is not None:
            driver = store.find("driver", int(driver_id))
            if driver:
                driver["任务结清证明"] = "已结清"
                if driver.get("资格状态") == "可调度":
                    driver["status"] = "在岗"
                    driver["pending"] = True
        return entry, f"调度任务 {entry.get('调度编号')} 已完成，任务已结清"

    def cancel_dispatch(self, entry_id: int) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"调度记录 {entry_id} 不存在"
        if entry.get("任务状态") not in DISPATCH_ACTIVE:
            return None, f"调度记录 {entry.get('调度编号')} 当前状态为「{entry.get('任务状态')}」，无需取消"
        entry["任务状态"] = DISPATCH_CANCELLED
        entry["结清状态"] = "已取消"
        entry["pending"] = False
        driver_id = entry.get("司机id")
        if driver_id is not None:
            driver = store.find("driver", int(driver_id))
            if driver:
                driver["任务结清证明"] = "已结清"
                if driver.get("资格状态") == "可调度":
                    driver["status"] = "在岗"
        return entry, f"调度任务 {entry.get('调度编号')} 已取消"

    def cancel_active_for_driver(self, driver_id: int) -> None:
        """停运时撤回该司机未执行的排班，并回写任务结清证明。"""
        cancelled = False
        for row in store.rows(MODULE):
            if int(row.get("司机id", 0)) == driver_id and row.get("任务状态") in DISPATCH_ACTIVE:
                row["任务状态"] = DISPATCH_CANCELLED
                row["结清状态"] = "已取消"
                row["pending"] = False
                cancelled = True
        if cancelled:
            driver = store.find("driver", driver_id)
            if driver:
                driver["任务结清证明"] = "已结清"

    def sync_version(self, driver_id: int, version: int) -> None:
        """资格版本与司机档案保持一致。"""
        for row in store.rows(MODULE):
            if int(row.get("司机id", 0)) == driver_id:
                row["资格版本"] = version
