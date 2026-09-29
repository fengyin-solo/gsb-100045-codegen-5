"""司机管理业务规则。

在原有驾驶人员档案之上，承载「调度资格」这条主线：

* 入档先核验驾驶证、从业资格证、任务结清证明三项材料；
* 资格状态按 待审核 → 审核中 → 可调度 → 停运 逐级流转，禁止跳级；
* 审核驳回回到待审核，可补料后重新提交；
* 停运后再变更必须走「重新审核」，资格版本号 +1，旧版本下的排班、停运记录不再有效；
* 审核结论（资格状态、版本、结论）实时回写到司机档案，调度工作台和司机详情都读这里。
"""
from __future__ import annotations

import threading
from typing import Any

from app.store import store

MODULE = "driver"
REQUIRED_FIELDS = ["司机编号", "姓名", "驾驶证号"]

# 资格状态机：只允许沿序列逐级流转，驳回是唯一允许的回退（回到起点）
QUAL_PENDING = "待审核"
QUAL_REVIEWING = "审核中"
QUAL_DISPATCHABLE = "可调度"
QUAL_SUSPENDED = "停运"
QUAL_ORDER = [QUAL_PENDING, QUAL_REVIEWING, QUAL_DISPATCHABLE, QUAL_SUSPENDED]

# 三项入档前必须核验的材料
CHECK_ITEMS = ["驾驶证", "从业资格证", "任务结清证明"]

# 动作 -> 目标资格状态（「资料核验」走专门的 verify_docs 入口，逐项勾选三份材料）
ACTION_RULES = {
    "审核通过": QUAL_DISPATCHABLE,
    "审核驳回": QUAL_PENDING,
    "办理停运": QUAL_SUSPENDED,
    "重新审核": QUAL_REVIEWING,
}
# 执行动作前资格状态必须处于的位置
ACTION_PRECONDITIONS = {
    "审核通过": QUAL_REVIEWING,
    "审核驳回": QUAL_REVIEWING,
    "办理停运": QUAL_DISPATCHABLE,
    "重新审核": QUAL_SUSPENDED,
}
# 停运属于负向动作，会在概览看板计入异常
NEGATIVE_ACTIONS = ["办理停运"]

# 所有会改动调度资格的写操作共用这把锁：同一司机被两个调度动作同时选中时，
# 靠它保证只有一个请求完成「先通过审核且任务已结清」的判定与占位。
dispatch_lock = threading.RLock()


def next_id(rows: list[dict[str, Any]]) -> int:
    return max((int(row.get("id", 0)) for row in rows), default=0) + 1


def snapshot_qualification(entry: dict[str, Any]) -> dict[str, Any]:
    """取司机当前资格版本快照，供排班结果、停运记录、调度名单落库时引用。"""
    return {
        "资格版本": entry.get("资格版本"),
        "资格状态": entry.get("status"),
        "审核结论": entry.get("审核结论"),
    }


class DriverService:
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
                row
                for row in rows
                if keyword in str(row.get("司机编号", ""))
                or keyword in str(row.get("姓名", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": next_id(rows)}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        # 从业资格证、健康证、联系方式等补充信息一并留档
        for field in ["从业资格证", "健康证有效期", "联系手机", "所属车队"]:
            if values.get(field) is not None:
                entry[field] = values.get(field)
        # 资格初始状态：待审核、第 1 版，三项材料均未核验，任务默认未结清
        entry["status"] = QUAL_PENDING
        entry["pending"] = True
        entry["abnormal"] = False
        entry["资格版本"] = "v1"
        entry["资格版本号"] = 1
        entry["审核结论"] = "待核验驾驶证、从业资格证、任务结清证明"
        entry["材料核验"] = {item: False for item in CHECK_ITEMS}
        entry["任务结清"] = False
        entry["选中锁定"] = None
        rows.append(entry)
        return entry, []

    def verify_docs(self, entry_id: int, checks: dict[str, bool]) -> tuple[dict[str, Any] | None, str]:
        """逐项核验三项材料；全部通过后自动进入审核中（逐级流转的第一步）。"""
        with dispatch_lock:
            entry = store.find(MODULE, entry_id)
            if entry is None:
                return None, f"驾驶人员 {entry_id} 不存在或已归档"
            if entry.get("status") != QUAL_PENDING:
                return None, "只有待审核档案可以核验材料"
            verified = dict(entry.get("材料核验") or {})
            for item in CHECK_ITEMS:
                if item in checks:
                    verified[item] = bool(checks[item])
            entry["材料核验"] = verified
            passed = [item for item in CHECK_ITEMS if verified.get(item)]
            if len(passed) < len(CHECK_ITEMS):
                pending_items = [item for item in CHECK_ITEMS if not verified.get(item)]
                entry["任务结清"] = bool(verified.get("任务结清证明"))
                entry["审核结论"] = f"材料待核验：{'、'.join(pending_items)}"
                return entry, f"{'、'.join(pending_items)}尚未核验通过，暂不能提交审核"
            # 任务结清证明通过即视为历史任务已结清
            entry["任务结清"] = True
            entry["status"] = QUAL_REVIEWING
            entry["pending"] = True
            entry["审核结论"] = "三项材料核验通过，等待审核结论"
            return entry, "驾驶证、从业资格证、任务结清证明均核验通过，已进入审核中"

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        with dispatch_lock:
            entry = store.find(MODULE, entry_id)
            if entry is None:
                return None, f"驾驶人员 {entry_id} 不存在或已归档"
            if action not in ACTION_RULES:
                return None, f"动作「{action}」不属于司机管理可执行范围"

            target = ACTION_RULES[action]
            current = str(entry.get("status"))
            required_current = ACTION_PRECONDITIONS[action]

            if current != required_current:
                return None, (
                    f"顺序错误：动作「{action}」要求资格状态为{required_current}，"
                    f"当前为{current}，请按 {' → '.join(QUAL_ORDER)} 逐级流转"
                )

            if action == "办理停运" and entry.get("选中锁定"):
                return None, f"该司机已被调度动作「{entry['选中锁定']}」选中，需先释放排班才能停运"

            if action == "重新审核":
                # 停运后再次变更必须重新审核：资格版本升级，旧版本结论全部作废
                version_no = int(entry.get("资格版本号", 1)) + 1
                entry["资格版本号"] = version_no
                entry["资格版本"] = f"v{version_no}"
                entry["材料核验"] = {item: False for item in CHECK_ITEMS}
                entry["任务结清"] = False
                entry["审核结论"] = f"停运后第 {version_no} 版资格重新提交，等待材料核验"
            elif action == "审核通过":
                entry["审核结论"] = "审核通过，可参与调度"
            elif action == "审核驳回":
                entry["审核结论"] = "审核驳回，请补齐材料后重新核验"
            elif action == "办理停运":
                entry["审核结论"] = "已停运，再次变更需重新审核"

            entry["status"] = target
            entry["pending"] = target != QUAL_SUSPENDED
            entry["abnormal"] = action in NEGATIVE_ACTIONS

            # 停运 / 重新审核会使旧版本下的排班与名单失效，结论同步回写调度侧
            from app.services.dispatch import DispatchService  # 局部导入避免循环依赖

            DispatchService()._sync_qualification(entry)
            return entry, f"驾驶人员已{action}（资格版本 {entry['资格版本']}）"

    def detail(self, entry_id: int) -> dict[str, Any] | None:
        """司机详情：档案 + 同一资格版本下的排班结果、停运记录、名单记录。"""
        with dispatch_lock:
            entry = store.find(MODULE, entry_id)
            if entry is None:
                return None
            from app.services.dispatch import DispatchService

            dispatch = DispatchService()
            roster = [r for r in store.rows("dispatch") if int(r.get("司机ID", 0)) == entry_id]
            schedules = [r for r in store.rows("schedule") if int(r.get("司机ID", 0)) == entry_id]
            suspensions = [r for r in store.rows("suspension") if int(r.get("司机ID", 0)) == entry_id]

            def consistency(rows: list[dict[str, Any]]) -> dict[str, int]:
                same = sum(1 for row in rows if row.get("资格版本") == entry.get("资格版本"))
                return {"同版本": same, "跨版本": len(rows) - same}

            return {
                "driver": entry,
                "名单记录": roster,
                "排班结果": schedules,
                "停运记录": suspensions,
                "版本一致性": {
                    "名单": consistency(roster),
                    "排班": consistency(schedules),
                    "停运": consistency(suspensions),
                },
                "当前锁定动作": dispatch.active_lock(entry_id),
            }
