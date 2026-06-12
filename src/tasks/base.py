"""任务结果数据类"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TaskResult:
    """任务执行结果"""

    success: bool
    message: str = ""
    stats: dict = field(default_factory=dict)
