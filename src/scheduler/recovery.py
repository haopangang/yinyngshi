"""异常恢复系统

采用责任链模式依次检测和处理各类异常情况：
- 弹窗干扰（广告、活动公告、系统提示等）
- 网络断开（重连或等待恢复）
- 游戏崩溃（检测进程状态并重启）
- 战斗超时（强制退出并重新进入）
- 设备断连（尝试重新连接 ADB）

所有恢复操作均内置指数退避重试策略（1s → 2s → 4s → 8s，最多 3 次），
确保异常情况下脚本能够自动恢复到正常执行状态。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

import numpy as np
from loguru import logger

if TYPE_CHECKING:
    from src.config.models import RecoveryConfig
    from src.device.app_manager import AppManager
    from src.device.controller import DeviceController
    from src.device.screen import ScreenCapture
    from src.vision.finder import VisionFinder


# 默认指数退避参数
_DEFAULT_MAX_RETRY = 3
_DEFAULT_BASE_DELAY = 1.0  # 秒


def _exponential_backoff(attempt: int, base_delay: float = _DEFAULT_BASE_DELAY) -> float:
    """计算指数退避延迟时间

    Args:
        attempt: 当前重试次数（从 0 开始）
        base_delay: 基础延迟秒数

    Returns:
        延迟秒数（base_delay * 2^attempt）
    """
    return base_delay * (2 ** attempt)


class RecoveryManager:
    """异常恢复管理器（责任链模式）

    依次检查并处理各类游戏异常，包括弹窗、网络错误、崩溃、超时等。
    每种异常类型均有独立的处理方法，支持指数退避重试。

    Attributes:
        device: 设备控制器
        vision: 视觉查找器
        screen: 截图管理器
        app_manager: 应用管理器
        config: 恢复配置

    Example:
        >>> recovery = RecoveryManager(device, vision, screen, app_manager, config)
        >>> screenshot = screen.capture()
        >>> recovered = recovery.check_and_recover(screenshot)
    """

    # 常见弹窗模板列表（按优先级排列）
    _POPUP_TEMPLATES = [
        "common/popup_close.png",       # 通用关闭按钮
        "common/popup_confirm.png",     # 确认弹窗
        "common/ad_close.png",          # 广告关闭
        "common/event_close.png",       # 活动弹窗关闭
        "common/update_skip.png",       # 更新跳过
        "common/notice_close.png",      # 公告关闭
    ]

    def __init__(
        self,
        device: DeviceController,
        vision: VisionFinder,
        screen: ScreenCapture,
        app_manager: AppManager,
        config: RecoveryConfig,
    ) -> None:
        """初始化异常恢复管理器

        Args:
            device: 设备控制器
            vision: 视觉查找器
            screen: 截图管理器
            app_manager: 应用管理器
            config: 恢复配置（RecoveryConfig）
        """
        self.device = device
        self.vision = vision
        self.screen = screen
        self.app_manager = app_manager
        self.config = config

        # 重试计数
        self._consecutive_failures: int = 0
        self._last_recovery_time: float = 0.0

        logger.info(
            f"RecoveryManager 初始化: auto_restart={config.auto_restart}, "
            f"max_retry={config.max_retry}, "
            f"network_wait={config.network_wait}s, "
            f"battle_timeout={config.battle_timeout}s"
        )

    def check_and_recover(self, screenshot: np.ndarray) -> bool:
        """检查截图并处理异常（责任链入口）

        依次尝试以下恢复策略：
        1. 处理弹窗干扰
        2. 检测网络错误
        3. 检测游戏崩溃
        4. 检测设备断连

        Args:
            screenshot: BGR 格式的屏幕截图

        Returns:
            True 表示检测到异常并成功恢复，
            False 表示未检测到异常或恢复失败
        """
        # 1. 弹窗处理
        if self.handle_popup(screenshot):
            logger.info("恢复: 弹窗已处理")
            self._consecutive_failures = 0
            return True

        # 2. 网络错误检测
        if self._is_network_error(screenshot):
            if self.handle_network_error():
                logger.info("恢复: 网络错误已处理")
                self._consecutive_failures = 0
                return True

        # 3. 游戏崩溃检测
        if self._is_game_crashed():
            if self.handle_crash():
                logger.info("恢复: 游戏崩溃已处理")
                self._consecutive_failures = 0
                return True

        # 4. 设备断连检测
        if self._is_device_disconnected():
            if self.handle_device_disconnect():
                logger.info("恢复: 设备断连已处理")
                self._consecutive_failures = 0
                return True

        # 未检测到异常
        return False

    # ------------------------------------------------------------------
    # 弹窗处理
    # ------------------------------------------------------------------

    def handle_popup(self, screenshot: np.ndarray) -> bool:
        """处理各种弹窗干扰

        依次查找预定义的弹窗关闭按钮模板，找到后点击关闭。

        Args:
            screenshot: BGR 格式的屏幕截图

        Returns:
            True 表示检测到弹窗并成功关闭
        """
        for template in self._POPUP_TEMPLATES:
            result = self.vision.find_image(template, screenshot=screenshot)
            if result is not None:
                logger.info(f"检测到弹窗: {template}")
                try:
                    self.device.click(result.center_x, result.center_y)
                    time.sleep(0.5)
                    return True
                except Exception as e:
                    logger.warning(f"关闭弹窗失败: {template} -> {e}")

        return False

    # ------------------------------------------------------------------
    # 网络错误恢复
    # ------------------------------------------------------------------

    def handle_network_error(self) -> bool:
        """网络断开恢复

        采用指数退避策略等待网络恢复，最多重试 config.max_retry 次。
        每次重试间隔：1s → 2s → 4s → 8s...

        Returns:
            True 表示网络恢复成功，False 表示恢复失败
        """
        logger.warning("检测到网络错误，尝试恢复...")

        max_retry = min(self.config.max_retry, _DEFAULT_MAX_RETRY)
        wait_time = self.config.network_wait

        for attempt in range(max_retry):
            delay = _exponential_backoff(attempt)
            logger.info(f"网络恢复尝试 [{attempt + 1}/{max_retry}]，等待 {delay:.1f}s")
            time.sleep(delay)

            # 尝试重新连接或检查网络弹窗
            screenshot = self._safe_screenshot()
            if screenshot is not None:
                # 查找"重新连接"按钮
                reconnect = self.vision.find_image("common/reconnect_btn.png", screenshot=screenshot)
                if reconnect is not None:
                    self.device.click(reconnect.center_x, reconnect.center_y)
                    time.sleep(2.0)

                # 检查是否恢复正常（主界面出现）
                home = self.vision.find_image("common/home_btn.png", screenshot=screenshot)
                if home is not None:
                    logger.info("网络恢复成功")
                    return True

            # 等待较长时间让网络恢复
            if attempt < max_retry - 1:
                logger.info(f"等待网络恢复 {wait_time}s...")
                time.sleep(wait_time)

        logger.error("网络恢复失败")
        self._consecutive_failures += 1
        return False

    # ------------------------------------------------------------------
    # 游戏崩溃恢复
    # ------------------------------------------------------------------

    def handle_crash(self) -> bool:
        """游戏崩溃恢复（检测进程 → 重启）

        检查游戏进程是否存在，若不存在或无响应则重启游戏。
        重启后等待加载完成。

        Returns:
            True 表示重启成功，False 表示重启失败
        """
        logger.warning("检测到游戏崩溃，尝试重启...")

        if not self.config.auto_restart:
            logger.error("配置禁止自动重启，无法恢复崩溃")
            return False

        max_retry = min(self.config.max_retry, _DEFAULT_MAX_RETRY)

        for attempt in range(max_retry):
            delay = _exponential_backoff(attempt)
            logger.info(f"崩溃恢复尝试 [{attempt + 1}/{max_retry}]，等待 {delay:.1f}s")
            time.sleep(delay)

            try:
                # 强制停止游戏
                self.app_manager.stop_onmyoji()
                time.sleep(2.0)

                # 重新启动
                self.app_manager.start_onmyoji()
                time.sleep(5.0)

                # 等待加载
                result = self.vision.wait_image(
                    "common/home_btn.png",
                    timeout=60.0,
                    interval=3.0,
                )

                if result is not None:
                    logger.info("游戏崩溃恢复成功")
                    return True

                logger.warning("游戏启动后未检测到主界面")

            except Exception as e:
                logger.error(f"崩溃恢复异常: {e}")

        logger.error("游戏崩溃恢复失败")
        self._consecutive_failures += 1
        return False

    # ------------------------------------------------------------------
    # 战斗超时处理
    # ------------------------------------------------------------------

    def handle_battle_timeout(self, timeout_s: int = 300) -> bool:
        """战斗超时处理

        当战斗持续时间超过指定阈值时，尝试强制退出战斗并返回主界面。

        Args:
            timeout_s: 战斗超时阈值（秒），默认使用配置值

        Returns:
            True 表示成功处理超时，False 表示处理失败
        """
        if timeout_s <= 0:
            timeout_s = self.config.battle_timeout

        logger.warning(f"战斗超时 ({timeout_s}s)，尝试强制退出...")

        max_retry = _DEFAULT_MAX_RETRY

        for attempt in range(max_retry):
            delay = _exponential_backoff(attempt)
            logger.info(f"超时恢复尝试 [{attempt + 1}/{max_retry}]，等待 {delay:.1f}s")
            time.sleep(delay)

            try:
                # 尝试按返回键退出战斗
                self.device.press_key("back")
                time.sleep(1.0)

                # 查找确认退出按钮
                screenshot = self._safe_screenshot()
                if screenshot is not None:
                    confirm = self.vision.find_image(
                        "common/confirm_exit_btn.png",
                        screenshot=screenshot,
                    )
                    if confirm is not None:
                        self.device.click(confirm.center_x, confirm.center_y)
                        time.sleep(1.0)

                    # 检查是否回到主界面
                    home = self.vision.find_image("common/home_btn.png")
                    if home is not None:
                        logger.info("战斗超时恢复成功")
                        return True

            except Exception as e:
                logger.error(f"超时恢复异常: {e}")

        logger.error("战斗超时恢复失败")
        self._consecutive_failures += 1
        return False

    # ------------------------------------------------------------------
    # 设备断连恢复
    # ------------------------------------------------------------------

    def handle_device_disconnect(self) -> bool:
        """设备断连恢复

        尝试重新建立 ADB 连接，恢复设备通信。

        Returns:
            True 表示重连成功，False 表示重连失败
        """
        logger.warning("检测到设备断连，尝试重新连接...")

        max_retry = min(self.config.max_retry, _DEFAULT_MAX_RETRY)

        for attempt in range(max_retry):
            delay = _exponential_backoff(attempt, base_delay=2.0)
            logger.info(f"设备重连尝试 [{attempt + 1}/{max_retry}]，等待 {delay:.1f}s")
            time.sleep(delay)

            try:
                # 尝试重新连接 ADB
                self.device.client.connect()
                time.sleep(1.0)

                # 验证连接
                screenshot = self._safe_screenshot()
                if screenshot is not None:
                    logger.info("设备重连成功")
                    return True

            except Exception as e:
                logger.error(f"设备重连异常: {e}")

        logger.error("设备重连失败")
        self._consecutive_failures += 1
        return False

    # ------------------------------------------------------------------
    # 内部检测方法
    # ------------------------------------------------------------------

    def _is_network_error(self, screenshot: np.ndarray) -> bool:
        """检测是否存在网络错误提示

        Args:
            screenshot: BGR 格式截图

        Returns:
            True 表示检测到网络错误
        """
        # 查找网络错误相关文字
        result = self.vision.find_text("网络", screenshot=screenshot)
        if result is not None:
            return True

        # 查找网络错误图片
        result = self.vision.find_image("common/network_error.png", screenshot=screenshot)
        return result is not None

    def _is_game_crashed(self) -> bool:
        """检测游戏是否崩溃（进程不在运行）

        Returns:
            True 表示游戏进程不存在
        """
        return not self.app_manager.is_onmyoji_running()

    def _is_device_disconnected(self) -> bool:
        """检测设备是否断连

        Returns:
            True 表示设备无法通信
        """
        try:
            screenshot = self._safe_screenshot()
            return screenshot is None
        except Exception:
            return True

    def _safe_screenshot(self) -> Optional[np.ndarray]:
        """安全获取截图（不抛异常）

        Returns:
            BGR 格式截图，获取失败返回 None
        """
        try:
            return self.screen.capture()
        except Exception as e:
            logger.debug(f"截图失败: {e}")
            return None

    @property
    def consecutive_failures(self) -> int:
        """连续恢复失败次数"""
        return self._consecutive_failures
