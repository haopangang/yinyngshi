"""地域鬼王任务

实现地域鬼王的自动化刷取流程：
导航到地域鬼王 → 选择鬼王 → 挑战 → 结算 → 循环
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.tasks.base import BaseTask, TaskResult
from src.tasks.registry import register_task


@register_task("region_king")
class RegionKingTask(BaseTask):
    """地域鬼王任务

    支持配置挑战次数，默认每天 3 次。

    Attributes:
        name: 任务名称
        priority: 优先级
        stamina_cost: 单次体力消耗（地域鬼王消耗 6 体力）
        count: 计划挑战次数

    Example:
        >>> config = {"count": 3}
        >>> task = RegionKingTask(device, vision, screen, config)
        >>> result = task._execute()
    """

    name = "地域鬼王"
    priority = 5
    stamina_cost = 6

    def __init__(self, device: Any, vision: Any, screen: Any, config: dict[str, Any]) -> None:
        """初始化地域鬼王任务

        Args:
            device: 设备控制器
            vision: 视觉查找器
            screen: 截图管理器
            config: 任务配置，支持以下字段：
                - count (int): 挑战次数，默认 3
        """
        super().__init__(device, vision, screen, config)
        self.count: int = config.get("count", 3)
        logger.info(f"地域鬼王配置: count={self.count}")

    def pre_check(self) -> bool:
        """前置条件检查

        检查体力是否充足。

        Returns:
            True 表示体力充足
        """
        required = self.stamina_cost * self.count
        logger.debug(f"地域鬼王前置检查: 需要体力 {required}")
        return self.check_stamina(required)

    def navigate(self) -> bool:
        """导航到地域鬼王界面

        流程：主界面 → 探索 → 地域鬼王

        Returns:
            True 表示导航成功
        """
        logger.info("导航到地域鬼王")
        if not self.go_to_main():
            return False

        # TODO: 点击探索入口
        # TODO: 点击地域鬼王入口
        return True

    def run(self) -> TaskResult:
        """执行地域鬼王主逻辑

        循环执行：选择鬼王 → 挑战 → 结算

        Returns:
            TaskResult 包含执行结果
        """
        logger.info(f"开始执行地域鬼王: {self.count} 次")
        success_count = 0
        error_count = 0

        for i in range(self.count):
            logger.info(f"地域鬼王 第 {i + 1}/{self.count} 次")
            try:
                # TODO: 选择鬼王
                # TODO: 点击挑战
                # TODO: 等待战斗结束
                # TODO: 点击结算
                self._run_count += 1
                success_count += 1
            except Exception as e:
                logger.error(f"第 {i + 1} 次挑战失败: {e}")
                error_count += 1
                if not self.on_error(e):
                    break

        return TaskResult(
            success=(success_count > 0),
            run_count=success_count,
            error_count=error_count,
            details={"planned": self.count},
        )

    def on_error(self, error: Exception) -> bool:
        """错误恢复处理

        Args:
            error: 捕获到的异常

        Returns:
            True 表示已恢复可继续
        """
        logger.warning(f"地域鬼王错误恢复: {error}")
        self.click_image("common/confirm_btn.png", timeout=2.0)
        return True
