"""结界突破任务

实现结界突破的自动化刷取流程：
导航到结界 → 选择个人/寮 → 选择对手 → 挑战 → 结算 → 循环
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.tasks.base import BaseTask, TaskResult
from src.tasks.registry import register_task


@register_task("breakthrough")
class BreakthroughTask(BaseTask):
    """结界突破任务

    支持配置突破模式（个人/寮）和挑战次数。

    Attributes:
        name: 任务名称
        priority: 优先级
        stamina_cost: 单次体力消耗（突破不消耗体力）
        mode: 突破模式（personal/guild）
        count: 计划挑战次数

    Example:
        >>> config = {"mode": "personal", "count": 9}
        >>> task = BreakthroughTask(device, vision, screen, config)
        >>> result = task._execute()
    """

    name = "结界突破"
    priority = 5
    stamina_cost = 0  # 突破不消耗体力

    # 模式映射
    MODES = {
        "personal": "个人突破",
        "guild": "寮突破",
    }

    def __init__(self, device: Any, vision: Any, screen: Any, config: dict[str, Any]) -> None:
        """初始化结界突破任务

        Args:
            device: 设备控制器
            vision: 视觉查找器
            screen: 截图管理器
            config: 任务配置，支持以下字段：
                - mode (str): 突破模式，可选 personal/guild，默认 personal
                - count (int): 挑战次数，默认 9
        """
        super().__init__(device, vision, screen, config)
        self.mode: str = config.get("mode", "personal")
        self.count: int = config.get("count", 9)
        logger.info(f"结界突破配置: mode={self.mode}, count={self.count}")

    def pre_check(self) -> bool:
        """前置条件检查

        检查是否有突破券。

        Returns:
            True 表示可以执行
        """
        logger.debug("结界突破前置检查")
        # TODO: 检查突破券数量
        return True

    def navigate(self) -> bool:
        """导航到结界突破界面

        流程：主界面 → 结界 → 突破 → 选择模式

        Returns:
            True 表示导航成功
        """
        logger.info(f"导航到结界突破: {self.MODES.get(self.mode, self.mode)}")
        if not self.go_to_main():
            return False

        # TODO: 点击结界入口
        # TODO: 点击突破入口
        # TODO: 选择模式
        return True

    def run(self) -> TaskResult:
        """执行结界突破主逻辑

        循环执行：选择对手 → 挑战 → 结算

        Returns:
            TaskResult 包含执行结果
        """
        logger.info(f"开始执行结界突破: {self.count} 次")
        success_count = 0
        error_count = 0

        for i in range(self.count):
            logger.info(f"结界突破 第 {i + 1}/{self.count} 次")
            try:
                # TODO: 选择对手
                # TODO: 点击挑战
                # TODO: 等待战斗结束
                # TODO: 点击结算
                self._run_count += 1
                success_count += 1
            except Exception as e:
                logger.error(f"第 {i + 1} 次突破失败: {e}")
                error_count += 1
                if not self.on_error(e):
                    break

        return TaskResult(
            success=(success_count > 0),
            run_count=success_count,
            error_count=error_count,
            details={"mode": self.mode, "planned": self.count},
        )

    def on_error(self, error: Exception) -> bool:
        """错误恢复处理

        Args:
            error: 捕获到的异常

        Returns:
            True 表示已恢复可继续
        """
        logger.warning(f"结界突破错误恢复: {error}")
        self.click_image("common/confirm_btn.png", timeout=2.0)
        return True
