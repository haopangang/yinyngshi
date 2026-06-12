"""寮任务

实现阴阳寮相关日常任务的自动化：
喂猫、结界卡放置等
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.tasks.base import BaseTask, TaskResult
from src.tasks.registry import register_task


@register_task("guild")
class GuildTask(BaseTask):
    """寮任务

    执行阴阳寮内的日常操作，如喂猫、放置结界卡等。

    Attributes:
        name: 任务名称
        priority: 优先级
        stamina_cost: 单次体力消耗（寮任务不消耗体力）

    Example:
        >>> config = {}
        >>> task = GuildTask(device, vision, screen, config)
        >>> result = task._execute()
    """

    name = "寮任务"
    priority = 6
    stamina_cost = 0

    def __init__(self, device: Any, vision: Any, screen: Any, config: dict[str, Any]) -> None:
        """初始化寮任务

        Args:
            device: 设备控制器
            vision: 视觉查找器
            screen: 截图管理器
            config: 任务配置，支持以下字段：
                - feed_cat (bool): 是否喂猫，默认 True
                - place_card (bool): 是否放置结界卡，默认 True
        """
        super().__init__(device, vision, screen, config)
        self.feed_cat: bool = config.get("feed_cat", True)
        self.place_card: bool = config.get("place_card", True)
        logger.info(f"寮任务配置: feed_cat={self.feed_cat}, place_card={self.place_card}")

    def pre_check(self) -> bool:
        """前置条件检查

        检查是否有待执行的寮任务。

        Returns:
            True 表示有待执行项
        """
        logger.debug("寮任务前置检查")
        return self.feed_cat or self.place_card

    def navigate(self) -> bool:
        """导航到阴阳寮界面

        流程：主界面 → 阴阳寮

        Returns:
            True 表示导航成功
        """
        logger.info("导航到阴阳寮")
        if not self.go_to_main():
            return False

        # TODO: 点击阴阳寮入口
        return True

    def run(self) -> TaskResult:
        """执行寮任务主逻辑

        按配置执行喂猫、放置结界卡等操作。

        Returns:
            TaskResult 包含执行结果
        """
        logger.info("开始执行寮任务")
        success_count = 0
        error_count = 0
        completed: list[str] = []

        if self.feed_cat:
            try:
                logger.info("执行: 喂猫")
                # TODO: 点击喂猫入口
                # TODO: 执行喂猫操作
                success_count += 1
                completed.append("feed_cat")
            except Exception as e:
                logger.error(f"喂猫失败: {e}")
                error_count += 1

        if self.place_card:
            try:
                logger.info("执行: 放置结界卡")
                # TODO: 进入结界
                # TODO: 放置结界卡
                success_count += 1
                completed.append("place_card")
            except Exception as e:
                logger.error(f"放置结界卡失败: {e}")
                error_count += 1

        self._run_count = success_count
        self._error_count = error_count

        return TaskResult(
            success=(success_count > 0),
            run_count=success_count,
            error_count=error_count,
            details={"completed": completed},
        )

    def on_error(self, error: Exception) -> bool:
        """错误恢复处理

        Args:
            error: 捕获到的异常

        Returns:
            True 表示已恢复可继续
        """
        logger.warning(f"寮任务错误恢复: {error}")
        self.go_to_main()
        return True
