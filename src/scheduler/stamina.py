"""体力管理器

管理阴阳师游戏中的体力资源，包括：
- 通过 OCR 识别当前体力值
- 判断体力是否满足任务需求
- 使用体力道具（寿司/体力药水）
- 记录每日体力消耗与预算控制

确保在体力预算范围内合理使用体力道具，避免浪费或超限。
"""

from __future__ import annotations

import time
from datetime import date
from typing import TYPE_CHECKING, Optional

import numpy as np
from loguru import logger

if TYPE_CHECKING:
    from src.config.models import StaminaConfig
    from src.device.controller import DeviceController
    from src.device.screen import ScreenCapture
    from src.vision.finder import VisionFinder


# 体力显示区域的归一化坐标 (x1, y1, x2, y2)
_STAMINA_REGION = (0.0, 0.0, 0.3, 0.1)


class StaminaManager:
    """体力管理器

    封装体力值的 OCR 识别、消耗记录和道具使用逻辑，
    配合 StaminaConfig 配置控制每日体力预算。

    Attributes:
        device: 设备控制器
        vision: 视觉查找器
        screen: 截图管理器
        config: 体力配置

    Example:
        >>> stamina = StaminaManager(device, vision, screen, config)
        >>> current = stamina.check_stamina(screenshot)
        >>> if stamina.has_enough(30):
        ...     # 执行消耗 30 体力的任务
        ...     stamina.record_consumption(30)
    """

    def __init__(
        self,
        device: DeviceController,
        vision: VisionFinder,
        screen: ScreenCapture,
        config: StaminaConfig,
    ) -> None:
        """初始化体力管理器

        Args:
            device: 设备控制器
            vision: 视觉查找器
            screen: 截图管理器
            config: 体力配置（StaminaConfig）
        """
        self.device = device
        self.vision = vision
        self.screen = screen
        self.config = config

        # 内部状态
        self._current_stamina: Optional[int] = None
        self._daily_consumed: int = 0
        self._items_used_today: int = 0
        self._last_check_date: Optional[date] = None
        self._last_check_time: float = 0.0

        logger.info(
            f"StaminaManager 初始化: auto_sushi={config.auto_use_sushi}, "
            f"max_daily_sushi={config.max_daily_sushi}, "
            f"min_threshold={config.min_threshold}"
        )

    def check_stamina(self, screenshot: np.ndarray) -> int:
        """通过 OCR 识别当前体力值

        在截图的体力区域识别数字，更新缓存的当前体力值。

        Args:
            screenshot: BGR 格式的屏幕截图（np.ndarray）

        Returns:
            当前体力值（整数），识别失败返回 0

        Example:
            >>> screenshot = screen.capture()
            >>> stamina_value = stamina_mgr.check_stamina(screenshot)
            >>> print(f"当前体力: {stamina_value}")
        """
        value = self.vision.ocr.read_number(screenshot, _STAMINA_REGION)

        if value is not None:
            self._current_stamina = value
            self._last_check_time = time.time()
            self._last_check_date = date.today()
            logger.info(f"当前体力: {value}")
        else:
            logger.warning("OCR 识别体力失败，使用缓存值")
            if self._current_stamina is None:
                self._current_stamina = 0

        return self._current_stamina

    def has_enough(self, required: int) -> bool:
        """判断当前体力是否足够执行任务

        Args:
            required: 任务所需体力值

        Returns:
            True 表示体力充足，False 表示不足

        Example:
            >>> if stamina_mgr.has_enough(30):
            ...     print("体力充足")
        """
        if self._current_stamina is None:
            logger.warning("体力值未检测，请先调用 check_stamina()")
            return False

        enough = self._current_stamina >= required
        logger.debug(f"体力检查: 当前={self._current_stamina}, 需要={required}, 足够={enough}")
        return enough

    def use_stamina_item(self) -> bool:
        """使用体力道具（寿司/体力药水）

        自动检测今日是否还能使用道具，并执行使用操作。
        使用后会更新今日已使用道具计数。

        Returns:
            True 表示使用成功，False 表示无法使用（超限或操作失败）

        Example:
            >>> if stamina_mgr.can_use_item():
            ...     success = stamina_mgr.use_stamina_item()
        """
        if not self.can_use_item():
            logger.warning("今日体力道具使用已达上限，无法继续使用")
            return False

        logger.info("尝试使用体力道具...")

        try:
            # 点击体力区域打开道具面板
            self.device.click(100, 50, offset=True)
            time.sleep(1.0)

            # 查找并点击寿司图标
            result = self.vision.find_image("common/sushi_item.png")
            if result is not None:
                self.device.click(result.center_x, result.center_y)
                time.sleep(0.5)

                # 确认使用
                confirm = self.vision.find_image("common/confirm_btn.png")
                if confirm is not None:
                    self.device.click(confirm.center_x, confirm.center_y)
                    time.sleep(0.5)

                    self._items_used_today += 1
                    logger.info(
                        f"体力道具使用成功 (今日已用: {self._items_used_today})"
                    )
                    return True

            logger.warning("未找到体力道具或确认按钮")
            return False

        except Exception as e:
            logger.error(f"使用体力道具失败: {e}")
            return False

    def get_daily_budget(self) -> int:
        """获取今日体力预算

        根据配置计算今日可用体力预算上限：
        - 基础自然恢复体力（每日约 288 点 = 每 5 分钟 1 点 × 24 小时）
        - 加上可使用的体力道具数量 × 单道具恢复量（默认 100）

        Returns:
            今日体力预算总量（整数）
        """
        natural_stamina = 288  # 自然恢复：每 5 分钟 1 点 × 1440 分钟
        item_stamina = self.config.max_daily_sushi * 100  # 假设每个寿司恢复 100 体力
        budget = natural_stamina + item_stamina

        logger.debug(f"今日体力预算: 自然={natural_stamina}, 道具={item_stamina}, 总计={budget}")
        return budget

    def record_consumption(self, amount: int) -> None:
        """记录体力消耗

        更新今日累计消耗量和当前体力缓存值。

        Args:
            amount: 本次消耗的体力值（正整数）

        Example:
            >>> stamina_mgr.record_consumption(30)
        """
        if amount < 0:
            logger.warning(f"体力消耗量不能为负数: {amount}")
            return

        self._daily_consumed += amount

        if self._current_stamina is not None:
            self._current_stamina = max(0, self._current_stamina - amount)

        logger.info(
            f"体力消耗记录: 本次={amount}, 今日累计={self._daily_consumed}, "
            f"剩余≈{self._current_stamina}"
        )

    def can_use_item(self) -> bool:
        """检查今日是否还能使用体力道具

        根据配置的每日最大使用道具数量判断。

        Returns:
            True 表示还能使用，False 表示已达上限

        Example:
            >>> if stamina_mgr.can_use_item():
            ...     stamina_mgr.use_stamina_item()
        """
        # 检查是否跨天重置
        today = date.today()
        if self._last_check_date != today:
            self._items_used_today = 0
            self._daily_consumed = 0
            self._last_check_date = today
            logger.info("跨天重置：体力道具使用计数已清零")

        can_use = (
            self.config.auto_use_sushi
            and self._items_used_today < self.config.max_daily_sushi
        )

        logger.debug(
            f"道具使用检查: 已用={self._items_used_today}, "
            f"上限={self.config.max_daily_sushi}, 可用={can_use}"
        )
        return can_use

    @property
    def current_stamina(self) -> Optional[int]:
        """当前体力值（缓存值，可能不是最新）"""
        return self._current_stamina

    @property
    def daily_consumed(self) -> int:
        """今日累计体力消耗"""
        return self._daily_consumed

    @property
    def items_used_today(self) -> int:
        """今日已使用体力道具数量"""
        return self._items_used_today
