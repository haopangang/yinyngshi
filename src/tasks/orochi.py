"""御魂八岐大蛇副本任务

实现八岐大蛇（御魂）副本的自动化刷取流程：
导航到御魂 → 选择层数 → 开始挑战 → 等待战斗结束 → 领取奖励 → 循环
"""

from __future__ import annotations

import time
from typing import Any

from loguru import logger

from src.tasks.base import BaseTask, TaskResult
from src.tasks.registry import register_task


@register_task("orochi")
class OrochiTask(BaseTask):
    """八岐大蛇（御魂）副本任务

    支持配置层数和挑战次数，自动循环刷取御魂副本。

    Attributes:
        name: 任务名称
        priority: 优先级
        stamina_cost: 单次体力消耗（御魂消耗 6 体力）
        layer: 副本层数（1-10）
        count: 计划挑战次数

    Example:
        >>> config = {"layer": 10, "count": 30}
        >>> task = OrochiTask(device, vision, screen, config)
        >>> result = task._execute()
    """

    name = "八岐大蛇"
    priority = 3
    stamina_cost = 6

    def __init__(self, device: Any, vision: Any, screen: Any, config: dict[str, Any]) -> None:
        """初始化八岐大蛇任务

        Args:
            device: 设备控制器
            vision: 视觉查找器
            screen: 截图管理器
            config: 任务配置，支持以下字段：
                - layer (int): 副本层数，默认 10
                - count (int): 挑战次数，默认 30
        """
        super().__init__(device, vision, screen, config)
        self.layer: int = config.get("layer", 10)
        self.count: int = config.get("count", 30)
        logger.info(f"八岐大蛇任务配置: layer={self.layer}, count={self.count}")

    def pre_check(self) -> bool:
        """前置条件检查

        检查体力是否足够执行指定次数的挑战。

        Returns:
            True 表示体力充足
        """
        required = self.stamina_cost * self.count
        logger.debug(f"八岐大蛇前置检查: 需要体力 {required}")
        return self.check_stamina(required)

    def navigate(self) -> bool:
        """导航到八岐大蛇副本界面

        流程：主界面 → 探索 → 御魂 → 八岐大蛇

        Returns:
            True 表示导航成功
        """
        logger.info("导航到八岐大蛇副本")
        # 先返回主界面
        if not self.go_to_main():
            return False

        # 点击探索入口
        if not self.click_image("common/explore_entry.png", timeout=5.0):
            logger.warning("未找到探索入口")
            return False

        # TODO: 点击御魂入口
        # TODO: 选择层数
        return True

    def run(self) -> TaskResult:
        """执行八岐大蛇副本主逻辑

        循环执行：开始挑战 → 等待战斗结束 → 领取奖励

        Returns:
            TaskResult 包含执行结果
        """
        logger.info(f"开始执行八岐大蛇: {self.count} 次")
        success_count = 0
        error_count = 0

        for i in range(self.count):
            logger.info(f"八岐大蛇 第 {i + 1}/{self.count} 次")
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
            details={"layer": self.layer, "planned": self.count},
        )

    def on_error(self, error: Exception) -> bool:
        """错误恢复处理

        尝试返回副本选择界面继续执行。

        Args:
            error: 捕获到的异常

        Returns:
            True 表示已恢复可继续
        """
        logger.warning(f"八岐大蛇错误恢复: {error}")
        # 尝试点击确认/关闭弹窗
        self.click_image("common/confirm_btn.png", timeout=2.0)
        return True
