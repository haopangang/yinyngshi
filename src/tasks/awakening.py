"""觉醒副本任务

实现觉醒材料副本的自动化刷取流程：
导航到觉醒 → 选择材料类型 → 选择层数 → 挑战 → 结算 → 循环
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.tasks.base import BaseTask, TaskResult
from src.tasks.registry import register_task


@register_task("awakening")
class AwakeningTask(BaseTask):
    """觉醒副本任务

    支持配置材料类型、层数和挑战次数，自动循环刷取觉醒材料。

    Attributes:
        name: 任务名称
        priority: 优先级
        stamina_cost: 单次体力消耗（觉醒消耗 6 体力）
        material_type: 材料类型（fire/wind/water/thunder）
        layer: 副本层数（1-10）
        count: 计划挑战次数

    Example:
        >>> config = {"type": "fire", "layer": 10, "count": 20}
        >>> task = AwakeningTask(device, vision, screen, config)
        >>> result = task._execute()
    """

    name = "觉醒副本"
    priority = 4
    stamina_cost = 6

    # 材料类型映射
    MATERIAL_TYPES = {
        "fire": "火灵",
        "wind": "风转",
        "water": "水灵",
        "thunder": "雷灵",
    }

    def __init__(self, device: Any, vision: Any, screen: Any, config: dict[str, Any]) -> None:
        """初始化觉醒副本任务

        Args:
            device: 设备控制器
            vision: 视觉查找器
            screen: 截图管理器
            config: 任务配置，支持以下字段：
                - type (str): 材料类型，可选 fire/wind/water/thunder，默认 fire
                - layer (int): 副本层数，默认 10
                - count (int): 挑战次数，默认 20
        """
        super().__init__(device, vision, screen, config)
        self.material_type: str = config.get("type", "fire")
        self.layer: int = config.get("layer", 10)
        self.count: int = config.get("count", 20)
        logger.info(
            f"觉醒副本配置: type={self.material_type}, "
            f"layer={self.layer}, count={self.count}"
        )

    def pre_check(self) -> bool:
        """前置条件检查

        检查体力是否足够执行指定次数的挑战。

        Returns:
            True 表示体力充足
        """
        required = self.stamina_cost * self.count
        logger.debug(f"觉醒副本前置检查: 需要体力 {required}")
        return self.check_stamina(required)

    def navigate(self) -> bool:
        """导航到觉醒副本界面

        流程：主界面 → 探索 → 觉醒 → 选择材料类型 → 选择层数

        Returns:
            True 表示导航成功
        """
        logger.info(f"导航到觉醒副本: {self.MATERIAL_TYPES.get(self.material_type, self.material_type)}")
        if not self.go_to_main():
            return False

        # TODO: 点击探索入口
        # TODO: 点击觉醒入口
        # TODO: 选择材料类型
        # TODO: 选择层数
        return True

    def run(self) -> TaskResult:
        """执行觉醒副本主逻辑

        循环执行：开始挑战 → 等待战斗结束 → 领取奖励

        Returns:
            TaskResult 包含执行结果
        """
        logger.info(f"开始执行觉醒副本: {self.count} 次")
        success_count = 0
        error_count = 0

        for i in range(self.count):
            logger.info(f"觉醒副本 第 {i + 1}/{self.count} 次")
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
                "type": self.material_type,
                "layer": self.layer,
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
        logger.warning(f"觉醒副本错误恢复: {error}")
        self.click_image("common/confirm_btn.png", timeout=2.0)
        return True
