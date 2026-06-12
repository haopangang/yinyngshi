"""御灵副本任务

实现御灵副本的自动化刷取流程：
导航到御灵 → 选择类型 → 挑战 → 结算 → 循环
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.tasks.base import BaseTask, TaskResult
from src.tasks.registry import register_task


@register_task("soul_dungeon")
class SoulDungeonTask(BaseTask):
    """御灵副本任务

    支持配置御灵类型和挑战次数。

    Attributes:
        name: 任务名称
        priority: 优先级
        stamina_cost: 单次体力消耗（御灵消耗 6 体力）
        soul_type: 御灵类型（dragon/white/black/peacock）
        count: 计划挑战次数

    Example:
        >>> config = {"type": "dragon", "count": 10}
        >>> task = SoulDungeonTask(device, vision, screen, config)
        >>> result = task._execute()
    """

    name = "御灵副本"
    priority = 5
    stamina_cost = 6

    # 御灵类型映射
    SOUL_TYPES = {
        "dragon": "神龙",
        "white": "白藏主",
        "black": "黑豹",
        "peacock": "孔雀",
    }

    def __init__(self, device: Any, vision: Any, screen: Any, config: dict[str, Any]) -> None:
        """初始化御灵副本任务

        Args:
            device: 设备控制器
            vision: 视觉查找器
            screen: 截图管理器
            config: 任务配置，支持以下字段：
                - type (str): 御灵类型，可选 dragon/white/black/peacock，默认 dragon
                - count (int): 挑战次数，默认 10
        """
        super().__init__(device, vision, screen, config)
        self.soul_type: str = config.get("type", "dragon")
        self.count: int = config.get("count", 10)
        logger.info(
            f"御灵副本配置: type={self.soul_type}, count={self.count}"
        )

    def pre_check(self) -> bool:
        """前置条件检查

        检查体力是否充足。

        Returns:
            True 表示体力充足
        """
        required = self.stamina_cost * self.count
        logger.debug(f"御灵副本前置检查: 需要体力 {required}")
        return self.check_stamina(required)

    def navigate(self) -> bool:
        """导航到御灵副本界面

        流程：主界面 → 探索 → 御灵 → 选择类型

        Returns:
            True 表示导航成功
        """
        logger.info(f"导航到御灵副本: {self.SOUL_TYPES.get(self.soul_type, self.soul_type)}")
        if not self.go_to_main():
            return False

        # TODO: 点击探索入口
        # TODO: 点击御灵入口
        # TODO: 选择御灵类型
        return True

    def run(self) -> TaskResult:
        """执行御灵副本主逻辑

        循环执行：开始挑战 → 等待战斗结束 → 领取奖励

        Returns:
            TaskResult 包含执行结果
        """
        logger.info(f"开始执行御灵副本: {self.count} 次")
        success_count = 0
        error_count = 0

        for i in range(self.count):
            logger.info(f"御灵副本 第 {i + 1}/{self.count} 次")
            try:
                # TODO: 点击开始挑战
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
            details={
                "type": self.soul_type,
                "planned": self.count,
            },
        )

    def on_error(self, error: Exception) -> bool:
        """错误恢复处理

        Args:
            error: 捕获到的异常

        Returns:
            True 表示已恢复可继续
        """
        logger.warning(f"御灵副本错误恢复: {error}")
        self.click_image("common/confirm_btn.png", timeout=2.0)
        return True
