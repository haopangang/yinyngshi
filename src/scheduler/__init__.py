"""智能调度系统模块

提供阴阳师辅助脚本的完整调度能力，包括：
- TaskScheduler: APScheduler 定时任务管理（每日/间隔/暂停/恢复）
- DailyPlanner: 每日任务规划（生成计划 → 按优先级执行）
- StaminaManager: 体力管理（OCR 识别 → 预算控制 → 道具使用）
- RecoveryManager: 异常恢复（弹窗 → 网络 → 崩溃 → 断连，指数退避）
- RuntimeMonitor: 运行监控（统计记录 → 日报生成 → JSON 持久化）
"""

from src.scheduler.monitor import RuntimeMonitor, RuntimeStats, TaskDetail
from src.scheduler.planner import DailyPlanner, PlannedTask, PlanStatus
from src.scheduler.recovery import RecoveryManager
from src.scheduler.scheduler import TaskScheduler
from src.scheduler.stamina import StaminaManager

__all__ = [
    "TaskScheduler",
    "DailyPlanner",
    "PlannedTask",
    "PlanStatus",
    "StaminaManager",
    "RecoveryManager",
    "RuntimeMonitor",
    "RuntimeStats",
    "TaskDetail",
]
