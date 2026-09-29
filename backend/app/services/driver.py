"""司机档案业务规则：资格核验、逐级审核、版本一致、停运后重新审核都收在这里。

资格状态逐级流转：待审核 → 可调度 → 停运。
- 新增司机先建立资格档案（待审核、版本 0）；
- 提交资格审核须先核验驾驶证、从业资格证、任务结清证明，通过后才到可调度，版本 +1；
- 办理停运后再次变更（恢复调度）必须回到待审核重新审核；
- 审核通过后，档案、排班结果、停运记录需反映同一资格版本。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "driver"
REQUIRED_FIELDS = ["司机编号", "姓名", "驾驶证号"]
STATUS_ORDER = ["在岗", "出车中", "休息", "停岗"]
ACTION_RULES = {"安排出车": "出车中", "办理停岗": "停岗", "恢复在岗": "在岗"}
NEGATIVE_ACTIONS = []

# 资格状态：待审核 → 可调度 → 停运
QUALIFICATION_PENDING = "待审核"
QUALIFICATION_READY = "可调度"
QUALIFICATION_SUSPENDED = "停运"
QUALIFICATION_STATUSES = [QUALIFICATION_PENDING, QUALIFICATION_READY, QUALIFICATION_SUSPENDED]

CERT_VERIFIED = "已核验"
CERT_UNVERIFIED = "未核验"
TASK_SETTLED = "已结清"
TASK_UNSETTLED = "未结清"

# 建档时可一并采集的档案/证件字段
PROFILE_FIELDS = ["从业资格证", "健康证有效期", "联系手机", "所属车队", "准驾车型", "驾驶证核验", "从业资格证核验"]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class DriverService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        qualification: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [
                row for row in rows
                if keyword in str(row.get("司机编号", "")) or keyword in str(row.get("姓名", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if qualification:
            rows = [row for row in rows if row.get("资格状态") == qualification]
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
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        for field in PROFILE_FIELDS:
            if field in values and str(values.get(field) or "").strip():
                entry[field] = values.get(field)
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        # 资格档案初始：待审核、版本 0、证件未核验、无在途任务（任务结清证明视为已结清）
        entry["资格状态"] = QUALIFICATION_PENDING
        entry["资格版本"] = 0
        entry.setdefault("驾驶证核验", CERT_UNVERIFIED)
        entry.setdefault("从业资格证核验", CERT_UNVERIFIED)
        entry["任务结清证明"] = TASK_SETTLED
        entry["审核结论"] = "待提交审核"
        entry["最近审核时间"] = ""
        entry["审核通过时间"] = ""
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"驾驶人员 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于司机管理可执行范围"
        # 顺序错误拦截：安排出车前资格状态必须已到可调度
        if action == "安排出车" and entry.get("资格状态") != QUALIFICATION_READY:
            return None, (
                f"顺序错误：司机资格状态为「{entry.get('资格状态')}」，"
                f"须审核通过至「可调度」后才能安排出车"
            )
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"驾驶人员已{action}"

    def submit_review(self, entry_id: int) -> tuple[dict[str, Any] | None, str]:
        """提交资格审核：核验驾驶证、从业资格证、任务结清证明。

        - 停运后须先恢复调度回到待审核，不能直接重新审核；
        - 三项全部核验/结清才通过，资格状态 待审核→可调度，版本 +1，回写审核结论；
        - 任一缺失则驳回，资格状态维持待审核并写明原因。
        """
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"驾驶人员 {entry_id} 不存在或已归档"
        if entry.get("资格状态") == QUALIFICATION_SUSPENDED:
            return None, "停运后再次变更需重新审核：请先办理「恢复调度」回到待审核，再提交资格审核"
        missing: list[str] = []
        if entry.get("驾驶证核验") != CERT_VERIFIED:
            missing.append("驾驶证")
        if entry.get("从业资格证核验") != CERT_VERIFIED:
            missing.append("从业资格证")
        if entry.get("任务结清证明") != TASK_SETTLED:
            missing.append("任务结清证明（存在未结清任务）")
        now = _now()
        entry["最近审核时间"] = now
        if missing:
            entry["资格状态"] = QUALIFICATION_PENDING
            entry["审核结论"] = "审核驳回：" + "、".join(missing) + " 未核验或未结清"
            return entry, entry["审核结论"]
        # 逐级流转：待审核 → 可调度，版本 +1
        entry["资格状态"] = QUALIFICATION_READY
        entry["资格版本"] = int(entry.get("资格版本", 0)) + 1
        entry["审核结论"] = "审核通过：驾驶证、从业资格证、任务结清证明均已核验"
        entry["审核通过时间"] = now
        # 同一资格版本回写到排班结果与停运记录
        self._sync_version(entry["id"], entry["资格版本"])
        return entry, "资格审核已通过，资格状态已流转为可调度"

    def suspend_driver(self, entry_id: int, reason: str) -> tuple[dict[str, Any] | None, str]:
        """办理停运：只有可调度司机可停运；生成停运记录并撤回未执行排班。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"驾驶人员 {entry_id} 不存在或已归档"
        if entry.get("资格状态") != QUALIFICATION_READY:
            return None, f"只有「可调度」司机才能办理停运，当前资格状态为「{entry.get('资格状态')}」"
        entry["资格状态"] = QUALIFICATION_SUSPENDED
        entry["status"] = "停岗"
        entry["pending"] = False
        entry["abnormal"] = True
        entry["审核结论"] = f"已停运：{reason or '未填写原因'}"
        entry["最近审核时间"] = _now()
        # 停运记录与档案保持同一资格版本
        from app.services.suspension import SuspensionService
        SuspensionService().create_suspension(entry, reason)
        # 停运同时撤回未执行的排班，避免同一资格下仍有在途任务
        from app.services.dispatch import DispatchService
        DispatchService().cancel_active_for_driver(entry["id"])
        return entry, "司机已停运，停运记录已生成"

    def reinstate_driver(self, entry_id: int) -> tuple[dict[str, Any] | None, str]:
        """恢复调度：停运后再次变更，资格状态回到待审核，须重新提交审核。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"驾驶人员 {entry_id} 不存在或已归档"
        if entry.get("资格状态") != QUALIFICATION_SUSPENDED:
            return None, f"只有「停运」司机才能恢复调度，当前资格状态为「{entry.get('资格状态')}」"
        entry["资格状态"] = QUALIFICATION_PENDING
        entry["status"] = "休息"
        entry["pending"] = True
        entry["abnormal"] = False
        entry["审核结论"] = "已恢复调度，待重新提交资格审核"
        entry["最近审核时间"] = _now()
        from app.services.suspension import SuspensionService
        SuspensionService().close_active_for_driver(entry["id"])
        return entry, "已恢复调度，请重新提交资格审核"

    def set_cert_verified(self, entry_id: int, field: str, verified: bool) -> tuple[dict[str, Any] | None, str]:
        """登记证件核验结果（驾驶证 / 从业资格证）。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"驾驶人员 {entry_id} 不存在或已归档"
        allowed = {"驾驶证核验", "从业资格证核验"}
        if field not in allowed:
            return None, f"不支持的证件类型「{field}」"
        entry[field] = CERT_VERIFIED if verified else CERT_UNVERIFIED
        return entry, f"{field}已{'核验' if verified else '标记未核验'}"

    def mark_settlement(self, driver_id: int, settled: bool) -> dict[str, Any] | None:
        """由调度流程回写任务结清状态。"""
        entry = store.find(MODULE, driver_id)
        if entry is None:
            return None
        entry["任务结清证明"] = TASK_SETTLED if settled else TASK_UNSETTLED
        return entry

    def _sync_version(self, driver_id: int, version: int) -> None:
        from app.services.dispatch import DispatchService
        from app.services.suspension import SuspensionService
        DispatchService().sync_version(driver_id, version)
        SuspensionService().sync_version(driver_id, version)
