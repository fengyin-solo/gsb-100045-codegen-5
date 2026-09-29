"""调度工作台业务规则。

围绕「调度名单 → 排班选中 → 停运 / 释放」维护三类记录，所有记录都快照司机
当前的资格版本与审核结论，保证司机档案、排班结果、停运记录说的是同一版资格：

* dispatch   调度名单：资格审核通过的司机才能入名单；
* schedule   排班结果：同一司机同一时刻只能被一个调度动作选中（进程锁 + 结清校验）；
* suspension 停运记录：资格进入停运时落痕，绑定停运时的资格版本。
"""
from __future__ import annotations

from typing import Any

from app.services.driver import (
    QUAL_DISPATCHABLE,
    QUAL_SUSPENDED,
    dispatch_lock,
    next_id,
    snapshot_qualification,
)
from app.store import store

DISPATCH_MODULE = "dispatch"
SCHEDULE_MODULE = "schedule"
SUSPENSION_MODULE = "suspension"

# 名单状态
ROSTER_WAITING = "待排班"
ROSTER_SCHEDULED = "已排班"
ROSTER_SUSPENDED = "随资格停运"
# 排班状态
SCHEDULE_LOCKED = "已锁定"
SCHEDULE_RELEASED = "已释放"
SCHEDULE_SUSPENDED = "随资格停运"


class DispatchService:
    # ---------- 调度名单 ----------
    def list_roster(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(DISPATCH_MODULE)
        if keyword:
            rows = [
                row
                for row in rows
                if keyword in str(row.get("司机编号", ""))
                or keyword in str(row.get("姓名", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("名单状态") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def add_to_roster(self, driver_id: int) -> tuple[dict[str, Any] | None, str]:
        """新增司机调度名单：先看资格是否到可调度、任务是否结清、版本是否最新。"""
        with dispatch_lock:
            driver = store.find("driver", driver_id)
            if driver is None:
                return None, f"顺序错误：驾驶人员 {driver_id} 不存在，无法加入调度名单"
            if driver.get("status") != QUAL_DISPATCHABLE:
                return None, (
                    f"顺序错误：{driver.get('姓名')} 当前资格为「{driver.get('status')}」，"
                    "须先通过资格审核（待审核 → 审核中 → 可调度）才能加入调度名单"
                )
            if not driver.get("任务结清"):
                return None, f"{driver.get('姓名')} 尚有未结清任务，暂不能加入调度名单"

            rows = store.rows(DISPATCH_MODULE)
            active = [
                row
                for row in rows
                if int(row.get("司机ID", 0)) == driver_id
                and row.get("名单状态") in (ROSTER_WAITING, ROSTER_SCHEDULED)
            ]
            if active:
                return None, f"{driver.get('姓名')} 已在当前版本（{driver.get('资格版本')}）调度名单中"

            entry = {
                "id": next_id(rows),
                "名单编号": f"ROST-{len(rows) + 1:04d}",
                "司机ID": driver_id,
                "司机编号": driver.get("司机编号"),
                "姓名": driver.get("姓名"),
                "名单状态": ROSTER_WAITING,
                "选中动作": None,
                "任务结清": True,
                "pending": True,
                "abnormal": False,
            }
            entry.update(snapshot_qualification(driver))
            rows.append(entry)
            return entry, f"{driver.get('姓名')} 已凭 {driver.get('资格版本')} 资格加入调度名单"

    # ---------- 排班选中 ----------
    def list_schedules(
        self,
        *,
        only_active: bool = False,
    ) -> list[dict[str, Any]]:
        rows = store.rows(SCHEDULE_MODULE)
        if only_active:
            rows = [row for row in rows if row.get("排班状态") == SCHEDULE_LOCKED]
        return rows

    def active_lock(self, driver_id: int) -> str | None:
        for row in self.list_schedules(only_active=True):
            if int(row.get("司机ID", 0)) == driver_id:
                return str(row.get("调度动作"))
        return None

    def select_schedule(
        self,
        driver_id: int,
        action_name: str,
        *,
        roster_id: int | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        """把一个调度动作排到司机头上。

        顺序错误（未审核 / 未结清 / 版本过期）或同一司机已被别的动作选中时一律拒绝，
        保证并发的两个动作里只有「先通过审核且任务已结清」的那一项落库。
        """
        action_name = action_name.strip()
        if not action_name:
            return None, "调度动作名称不能为空"
        with dispatch_lock:
            driver = store.find("driver", driver_id)
            if driver is None:
                return None, f"顺序错误：驾驶人员 {driver_id} 不存在"
            if driver.get("status") != QUAL_DISPATCHABLE:
                return None, (
                    f"顺序错误：{driver.get('姓名')} 资格为「{driver.get('status')}」，"
                    "调度只接受已通过审核的司机"
                )

            roster = self._find_active_roster(driver_id)
            if roster is None:
                return None, f"顺序错误：{driver.get('姓名')} 不在当前调度名单中，请先新增名单"
            if roster_id is not None and int(roster.get("id", 0)) != roster_id:
                return None, "名单与司机不匹配，排班未受理"
            if roster.get("资格版本") != driver.get("资格版本"):
                return None, (
                    f"顺序错误：名单引用的是 {roster.get('资格版本')} 资格，"
                    f"档案已更新到 {driver.get('资格版本')}，请按新版本重新加入名单"
                )
            if not driver.get("任务结清"):
                return None, (
                    f"{driver.get('姓名')} 任务未结清，调度只接受任务已结清的一项；"
                    f"动作「{action_name}」未受理"
                )
            locked = self.active_lock(driver_id)
            if locked is not None:
                return None, (
                    f"{driver.get('姓名')} 已被调度动作「{locked}」先选中，"
                    f"动作「{action_name}」不再受理"
                )

            rows = store.rows(SCHEDULE_MODULE)
            entry = {
                "id": next_id(rows),
                "排班编号": f"PLAN-{len(rows) + 1:04d}",
                "司机ID": driver_id,
                "司机编号": driver.get("司机编号"),
                "姓名": driver.get("姓名"),
                "调度动作": action_name,
                "排班状态": SCHEDULE_LOCKED,
                "pending": True,
                "abnormal": False,
            }
            entry.update(snapshot_qualification(driver))
            rows.append(entry)

            # 占位：同一司机的后续调度动作会被 active_lock 拦下。
            # 任务结清是资格版本内的核验结论，不因本次派单改写（由停运/重新审核重置）。
            driver["选中锁定"] = action_name
            roster["名单状态"] = ROSTER_SCHEDULED
            roster["选中动作"] = action_name
            roster["pending"] = False
            return entry, f"动作「{action_name}」已排到 {driver.get('姓名')}（{entry['资格版本']}）"

    def batch_select(
        self, items: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """批量排班：顺序处理，同一司机重复出现时只有第一项可能被接受。"""
        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for item in items:
            try:
                driver_id = int(item.get("司机ID"))
            except (TypeError, ValueError):
                rejected.append({"raw": item, "原因": "司机ID无效"})
                continue
            action_name = str(item.get("任务名称") or item.get("调度动作") or "")
            entry, message = self.select_schedule(driver_id, action_name)
            if entry is None:
                rejected.append({"司机ID": driver_id, "任务名称": action_name, "原因": message})
            else:
                accepted.append({"entry": entry, "结果": message})
        return {"accepted": accepted, "rejected": rejected}

    def release_schedule(self, schedule_id: int) -> tuple[dict[str, Any] | None, str]:
        """任务完成并结清后释放排班，司机重新可被调度。"""
        with dispatch_lock:
            row = store.find(SCHEDULE_MODULE, schedule_id)
            if row is None:
                return None, f"排班结果 {schedule_id} 不存在"
            if row.get("排班状态") != SCHEDULE_LOCKED:
                return None, f"排班 {row.get('排班编号')} 当前为「{row.get('排班状态')}」，无需释放"
            row["排班状态"] = SCHEDULE_RELEASED
            row["pending"] = False
            driver = store.find("driver", int(row.get("司机ID", 0)))
            if driver is not None and driver.get("选中锁定") == row.get("调度动作"):
                driver["选中锁定"] = None
                driver["任务结清"] = True
            roster = self._find_active_roster(int(row.get("司机ID", 0)))
            if roster is not None:
                roster["名单状态"] = ROSTER_WAITING
                roster["选中动作"] = None
                roster["pending"] = True
            return row, f"排班 {row.get('排班编号')} 已释放，任务已结清"

    # ---------- 停运记录 ----------
    def list_suspensions(self) -> list[dict[str, Any]]:
        return store.rows(SUSPENSION_MODULE)

    def log_suspension(self, driver: dict[str, Any], reason: str | None = None) -> dict[str, Any]:
        """停运落痕：绑定停运发生时的资格版本，后续版本变更不会改写这条记录。"""
        rows = store.rows(SUSPENSION_MODULE)
        entry = {
            "id": next_id(rows),
            "停运编号": f"STOP-{len(rows) + 1:04d}",
            "司机ID": int(driver.get("id", 0)),
            "司机编号": driver.get("司机编号"),
            "姓名": driver.get("姓名"),
            "停运原因": reason or "资格办理停运",
            "pending": False,
            "abnormal": True,
        }
        entry.update(snapshot_qualification(driver))
        rows.append(entry)
        return entry

    # ---------- 资格结论回写 ----------
    def _sync_qualification(self, driver: dict[str, Any]) -> None:
        """审核结论回写调度工作台：同版本名单 / 排班同步状态，跨版本记录保持冻结。"""
        driver_id = int(driver.get("id", 0))
        version = driver.get("资格版本")
        status = driver.get("status")
        conclusion = driver.get("审核结论")

        for row in store.rows(DISPATCH_MODULE):
            if int(row.get("司机ID", 0)) != driver_id:
                continue
            if row.get("资格版本") != version:
                continue  # 旧版本名单不回写，保留当时结论用于追溯
            row["审核结论"] = conclusion
            if status == QUAL_SUSPENDED and row.get("名单状态") in (
                ROSTER_WAITING,
                ROSTER_SCHEDULED,
            ):
                row["名单状态"] = ROSTER_SUSPENDED
                row["选中动作"] = None
                row["pending"] = False

        for row in store.rows(SCHEDULE_MODULE):
            if int(row.get("司机ID", 0)) != driver_id:
                continue
            if row.get("资格版本") != version:
                continue
            row["审核结论"] = conclusion
            if status == QUAL_SUSPENDED and row.get("排班状态") == SCHEDULE_LOCKED:
                row["排班状态"] = SCHEDULE_SUSPENDED
                row["pending"] = False

        if status == QUAL_SUSPENDED:
            # 停运即解除排班占位；重新审核通过前不可再被选中
            driver["选中锁定"] = None
            self.log_suspension(driver)

    # ---------- 内部工具 ----------
    def _find_active_roster(self, driver_id: int) -> dict[str, Any] | None:
        for row in store.rows(DISPATCH_MODULE):
            if int(row.get("司机ID", 0)) == driver_id and row.get("名单状态") in (
                ROSTER_WAITING,
                ROSTER_SCHEDULED,
            ):
                return row
        return None
