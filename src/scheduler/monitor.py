"""运行状态监控

记录和统计任务执行的各项指标：
- 任务执行次数、成功/失败次数
- 单任务和全局耗时统计
- 每日运行报告生成
- 统计数据 JSON 持久化

为通知系统提供数据支撑，支持日报推送和异常告警。
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger


@dataclass
class TaskDetail:
    """单任务执行统计详情

    Attributes:
        task_name: 任务名称
        total_runs: 总执行次数
        success_count: 成功次数
        error_count: 失败次数
        total_time: 累计耗时（秒）
        last_run_time: 最后执行时间
        last_success: 最后是否成功
    """

    task_name: str
    total_runs: int = 0
    success_count: int = 0
    error_count: int = 0
    total_time: float = 0.0
    last_run_time: Optional[str] = None
    last_success: bool = False

    @property
    def success_rate(self) -> float:
        """成功率（0~1）"""
        if self.total_runs == 0:
            return 0.0
        return self.success_count / self.total_runs

    @property
    def avg_time(self) -> float:
        """平均耗时（秒）"""
        if self.total_runs == 0:
            return 0.0
        return self.total_time / self.total_runs


@dataclass
class RuntimeStats:
    """运行统计数据

    Attributes:
        total_runs: 全局总执行次数
        success_count: 全局成功次数
        error_count: 全局失败次数
        total_time: 全局累计耗时（秒）
        task_details: 各任务的详细统计
        report_date: 统计日期
    """

    total_runs: int = 0
    success_count: int = 0
    error_count: int = 0
    total_time: float = 0.0
    task_details: dict[str, TaskDetail] = field(default_factory=dict)
    report_date: str = field(default_factory=lambda: date.today().isoformat())

    @property
    def success_rate(self) -> float:
        """全局成功率（0~1）"""
        if self.total_runs == 0:
            return 0.0
        return self.success_count / self.total_runs

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化的字典

        Returns:
            包含所有统计数据的字典
        """
        return {
            "total_runs": self.total_runs,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "total_time": self.total_time,
            "success_rate": f"{self.success_rate:.1%}",
            "report_date": self.report_date,
            "task_details": {
                name: asdict(detail) for name, detail in self.task_details.items()
            },
        }


class RuntimeMonitor:
    """运行状态监控器

    跟踪和记录所有任务的执行情况，生成统计报告和日报。
    支持 JSON 持久化，方便重启后恢复统计。

    Example:
        >>> monitor = RuntimeMonitor()
        >>> monitor.start_task("orochi")
        >>> # ... 执行任务 ...
        >>> monitor.end_task("orochi", result)
        >>> report = monitor.get_daily_report()
        >>> print(report)
    """

    def __init__(self) -> None:
        """初始化运行状态监控器"""
        self._stats = RuntimeStats()
        self._task_start_times: dict[str, float] = {}

        logger.info("RuntimeMonitor 初始化完成")

    def start_task(self, task_name: str) -> None:
        """记录任务开始时间

        Args:
            task_name: 任务名称
        """
        self._task_start_times[task_name] = time.time()
        logger.debug(f"监控: 任务开始 -> {task_name}")

    def end_task(self, task_name: str, result: Any) -> None:
        """记录任务结束并更新统计

        从 TaskResult 中提取成功/失败状态、执行次数、耗时等信息，
        更新全局统计和任务详情。

        Args:
            task_name: 任务名称
            result: TaskResult 实例，包含执行结果数据
        """
        # 计算耗时
        start_time = self._task_start_times.pop(task_name, None)
        elapsed = 0.0
        if start_time is not None:
            elapsed = time.time() - start_time
        elif hasattr(result, "elapsed_time"):
            elapsed = result.elapsed_time

        # 提取结果信息
        success = getattr(result, "success", False)
        run_count = getattr(result, "run_count", 1) or 1
        error_count = getattr(result, "error_count", 0)

        # 更新全局统计
        self._stats.total_runs += run_count
        self._stats.total_time += elapsed
        if success:
            self._stats.success_count += run_count
        else:
            self._stats.error_count += max(error_count, 1)

        # 更新任务详情
        if task_name not in self._stats.task_details:
            self._stats.task_details[task_name] = TaskDetail(task_name=task_name)

        detail = self._stats.task_details[task_name]
        detail.total_runs += run_count
        detail.total_time += elapsed
        detail.last_run_time = datetime.now().strftime("%H:%M:%S")
        detail.last_success = success

        if success:
            detail.success_count += run_count
        else:
            detail.error_count += max(error_count, 1)

        logger.info(
            f"监控: 任务结束 -> {task_name}: "
            f"success={success}, runs={run_count}, time={elapsed:.1f}s"
        )

    def get_stats(self) -> RuntimeStats:
        """获取当前运行统计数据

        Returns:
            RuntimeStats 实例，包含全局统计和各任务详情
        """
        # 确保日期是今天
        self._stats.report_date = date.today().isoformat()
        return self._stats

    def get_daily_report(self) -> str:
        """生成今日运行报告文本

        返回格式化的文本报告，包含全局统计和各任务执行情况。

        Returns:
            格式化的报告文本字符串

        Example:
            >>> report = monitor.get_daily_report()
            >>> print(report)
            📊 阴阳师助手 - 每日运行报告
            ─────────────────────
            📅 日期: 2026-06-12
            ✅ 总执行: 15 次
            ...
        """
        stats = self.get_stats()

        lines = [
            "📊 阴阳师助手 - 每日运行报告",
            "─" * 30,
            f"📅 日期: {stats.report_date}",
            f"🔄 总执行: {stats.total_runs} 次",
            f"✅ 成功: {stats.success_count} 次",
            f"❌ 失败: {stats.error_count} 次",
            f"📈 成功率: {stats.success_rate:.1%}",
            f"⏱️ 总耗时: {self._format_time(stats.total_time)}",
        ]

        if stats.task_details:
            lines.append("")
            lines.append("📋 任务详情:")
            lines.append("─" * 30)

            for name, detail in stats.task_details.items():
                status_icon = "✅" if detail.last_success else "❌"
                lines.append(
                    f"  {status_icon} {name}: "
                    f"{detail.success_count}/{detail.total_runs} "
                    f"({detail.success_rate:.0%}) "
                    f"耗时 {self._format_time(detail.total_time)}"
                )
                if detail.last_run_time:
                    lines.append(f"      最后执行: {detail.last_run_time}")

        lines.append("")
        lines.append("─" * 30)
        lines.append("🤖 由阴阳师助手自动生成")

        return "\n".join(lines)

    def save_stats(self, path: str | Path) -> Path:
        """持久化统计数据到 JSON 文件

        自动创建父目录，以 JSON 格式保存当前统计数据。

        Args:
            path: 目标文件路径

        Returns:
            保存后的文件绝对路径

        Example:
            >>> monitor.save_stats("data/stats.json")
        """
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        data = self._stats.to_dict()
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"统计数据已保存: {file_path.resolve()}")
        return file_path.resolve()

    def load_stats(self, path: str | Path) -> bool:
        """从 JSON 文件加载统计数据

        Args:
            path: JSON 文件路径

        Returns:
            True 表示加载成功，False 表示文件不存在或解析失败
        """
        file_path = Path(path)
        if not file_path.exists():
            logger.warning(f"统计文件不存在: {file_path}")
            return False

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._stats.total_runs = data.get("total_runs", 0)
            self._stats.success_count = data.get("success_count", 0)
            self._stats.error_count = data.get("error_count", 0)
            self._stats.total_time = data.get("total_time", 0.0)

            # 加载任务详情
            for name, detail_data in data.get("task_details", {}).items():
                self._stats.task_details[name] = TaskDetail(
                    task_name=detail_data.get("task_name", name),
                    total_runs=detail_data.get("total_runs", 0),
                    success_count=detail_data.get("success_count", 0),
                    error_count=detail_data.get("error_count", 0),
                    total_time=detail_data.get("total_time", 0.0),
                    last_run_time=detail_data.get("last_run_time"),
                    last_success=detail_data.get("last_success", False),
                )

            logger.info(f"统计数据已加载: {file_path}")
            return True

        except Exception as e:
            logger.error(f"加载统计数据失败: {e}")
            return False

    def reset(self) -> None:
        """重置所有统计数据"""
        self._stats = RuntimeStats()
        self._task_start_times.clear()
        logger.info("统计数据已重置")

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _format_time(seconds: float) -> str:
        """格式化时间为可读字符串

        Args:
            seconds: 秒数

        Returns:
            格式化字符串，如 "1h 23m 45s" 或 "45s"
        """
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            m, s = divmod(int(seconds), 60)
            return f"{m}m {s}s"
        else:
            h, remainder = divmod(int(seconds), 3600)
            m, s = divmod(remainder, 60)
            return f"{h}h {m}m {s}s"
