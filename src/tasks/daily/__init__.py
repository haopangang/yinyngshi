"""日常任务（组合任务）

实现日常任务的自动化执行，包括签到、金币妖怪、年兽等。
作为组合任务，按配置的 items 列表依次执行各项日常。
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.tasks.base import BaseTask, TaskResult
from src.tasks.registry import register_task


@register_task("daily")
class DailyTask(BaseTask):
    """日常任务（组合任务）

    按配置列表依次执行各项日常任务，如签到、金币妖怪、年兽等。

    Attributes:
        name: 任务名称
        priority: 优先级（日常任务优先级较高）
        stamina_cost: 单次体力消耗（日常任务不固定）
        items: 日常任务项列表

    Example:
        >>> config = {"items": ["signin", "gold_youkai", "nianshou"]}
        >>> task = DailyTask(device, vision, screen, config)
        >>> result = task._execute()
    """

    name = "日常任务"
    priority = 2
    stamina_cost = 0

    # 支持的日常任务项
    SUPPORTED_ITEMS = {
        "signin": "签到",
        "gold_youkai": "金币妖怪",
        "nianshou": "年兽",
        "tansuo": "探索",
    }

    def __init__(self, device: Any, vision: Any, screen: Any, config: dict[str, Any]) -> None:
        """初始化日常任务

        Args:
            device: 设备控制器
            vision: 视觉查找器
            screen: 截图管理器
            config: 任务配置，支持以下字段：
                - items (list[str]): 日常任务项列表，
                  可选 signin/gold_youkai/nianshou/tansuo
        """
        super().__init__(device, vision, screen, config)
        self.items: list[str] = config.get("items", ["signin", "gold_youkai"])
        logger.info(f"日常任务配置: items={self.items}")

    def pre_check(self) -> bool:
        """前置条件检查

        检查是否有待执行的日常任务项。

        Returns:
            True 表示有待执行项
        """
        valid_items = [item for item in self.items if item in self.SUPPORTED_ITEMS]
        logger.debug(f"日常任务前置检查: 有效项 {valid_items}")
        return len(valid_items) > 0

    def navigate(self) -> bool:
        """导航到日常任务起始界面

        Returns:
            True 表示导航成功
        """
        logger.info("导航到日常任务界面")
        return self.go_to_main()

    def run(self) -> TaskResult:
        """执行日常任务主逻辑

        依次执行配置的各个日常任务项。

        Returns:
            TaskResult 包含执行结果
        """
        logger.info(f"开始执行日常任务: {self.items}")
        success_count = 0
        error_count = 0
        completed_items: list[str] = []

        for item in self.items:
            if item not in self.SUPPORTED_ITEMS:
                logger.warning(f"未知的日常任务项: {item}")
                continue

            logger.info(f"执行日常: {self.SUPPORTED_ITEMS[item]}")
            try:
                # TODO: 根据 item 类型执行对应的日常逻辑
                self._run_count += 1
                success_count += 1
                completed_items.append(item)
            except Exception as e:
                logger.error(f"日常任务 {item} 失败: {e}")
                error_count += 1
                if not self.on_error(e):
                    break

        return TaskResult(
            success=(success_count > 0),
            run_count=success_count,
            error_count=error_count,
            details={"items": self.items, "completed": completed_items},
        )

    def on_error(self, error: Exception) -> bool:
        """错误恢复处理

        日常任务单项失败不影响后续项，返回主界面继续。

        Args:
            error: 捕获到的异常

        Returns:
            True 表示已恢复可继续
        """
        logger.warning(f"日常任务错误恢复: {error}")
        self.go_to_main()
        return True
