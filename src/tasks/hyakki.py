"""百鬼夜行任务

实现百鬼夜行的自动化刷取流程：
进入百鬼夜行 → 等待式神出现 → 点击撒豆 → 结算
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.tasks.base import BaseTask, TaskResult
from src.tasks.registry import register_task


@register_task("hyakki")
class HyakkiTask(BaseTask):
    """百鬼夜行任务

    支持配置挑战次数和是否消耗百鬼夜行券。

    Attributes:
        name: 任务名称
        priority: 优先级
        stamina_cost: 单次体力消耗（百鬼夜行不消耗体力）
        count: 计划执行次数
        use_ticket: 是否消耗百鬼夜行券

    Example:
        >>> config = {"count": 5, "use_ticket": True}
        >>> task = HyakkiTask(device, vision, screen, config)
        >>> result = task._execute()
    """

    name = "百鬼夜行"
    priority = 6
    stamina_cost = 0  # 百鬼夜行不消耗体力

    def __init__(self, device: Any, vision: Any, screen: Any, config: dict[str, Any]) -> None:
        """初始化百鬼夜行任务

        Args:
            device: 设备控制器
            vision: 视觉查找器
            screen: 截图管理器
            config: 任务配置，支持以下字段：
                - count (int): 执行次数，默认 5
                - use_ticket (bool): 是否消耗券，默认 True
        """
        super().__init__(device, vision, screen, config)
        self.count: int = config.get("count", 5)
        self.use_ticket: bool = config.get("use_ticket", True)
        logger.info(f"百鬼夜行配置: count={self.count}, use_ticket={self.use_ticket}")

    def pre_check(self) -> bool:
        """前置条件检查

        检查是否有百鬼夜行券或体力。

        Returns:
            True 表示可以执行
        """
        logger.debug("百鬼夜行前置检查")
        # TODO: 检查百鬼夜行券数量
        return True

    def navigate(self) -> bool:
        """导航到百鬼夜行界面

        流程：主界面 → 町中 → 百鬼夜行

        Returns:
            True 表示导航成功
        """
        logger.info("导航到百鬼夜行")
        if not self.go_to_main():
            return False

        # TODO: 点击町中入口
        # TODO: 点击百鬼夜行入口
        return True

    def run(self) -> TaskResult:
        """执行百鬼夜行主逻辑

        循环执行：进入 → 等待式神 → 撒豆 → 结算

        Returns:
            TaskResult 包含执行结果
        """
        logger.info(f"开始执行百鬼夜行: {self.count} 次")
        success_count = 0
        error_count = 0

        for i in range(self.count):
            logger.info(f"百鬼夜行 第 {i + 1}/{self.count} 次")
            try:
                # TODO: 点击开始
                # TODO: 等待式神出现
                # TODO: 点击撒豆
                # TODO: 等待结算
                self._run_count += 1
                success_count += 1
            except Exception as e:
                logger.error(f"第 {i + 1} 次百鬼夜行失败: {e}")
                error_count += 1
                if not self.on_error(e):
                    break

        return TaskResult(
            success=(success_count > 0),
            run_count=success_count,
            error_count=error_count,
            details={"use_ticket": self.use_ticket, "planned": self.count},
        )

    def on_error(self, error: Exception) -> bool:
        """错误恢复处理

        Args:
            error: 捕获到的异常

        Returns:
            True 表示已恢复可继续
        """
        logger.warning(f"百鬼夜行错误恢复: {error}")
        self.click_image("common/confirm_btn.png", timeout=2.0)
        return True
