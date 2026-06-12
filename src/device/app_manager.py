"""
应用管理器

负责 Android 设备上应用的启动、停止、状态检测等操作，并提供
阴阳师游戏的专用快捷方法。

依赖 ADBClient 获取底层 uiautomator2 Device 实例。
"""

from __future__ import annotations

import time

from loguru import logger

from src.device.adb_client import ADBClient
from src.utils.constants import GAME_ACTIVITY, GAME_PACKAGE


class AppManager:
    """
    应用生命周期管理器。

    提供通用的应用启动/停止/状态检测能力，以及阴阳师游戏的专用
    快捷方法。同时支持屏幕唤醒和简单滑动解锁。

    Attributes:
        client: 底层 ADBClient 实例
        game_package: 阴阳师包名，默认从常量读取
        game_activity: 阴阳师启动 Activity，默认从常量读取
    """

    def __init__(
        self,
        client: ADBClient,
        game_package: str = GAME_PACKAGE,
        game_activity: str = GAME_ACTIVITY,
    ) -> None:
        """
        初始化 AppManager。

        Args:
            client: ADBClient 实例，需已完成设备连接
            game_package: 游戏包名，默认 "com.netease.onmyoji"
            game_activity: 游戏启动 Activity，默认 "com.netease.onmyoji.Client"
        """
        self.client: ADBClient = client
        self.game_package: str = game_package
        self.game_activity: str = game_activity

    # ------------------------------------------------------------------
    # 通用应用管理
    # ------------------------------------------------------------------

    def start_app(self, package: str, activity: str) -> None:
        """
        启动指定应用。

        通过 uiautomator2 的 app_start 方法启动应用。若应用已在运行，
        则会将其切换到前台。

        Args:
            package: 应用包名
            activity: 启动 Activity 名称
        """
        logger.info(f"启动应用: {package}/{activity}")
        self.client.device.app_start(package, activity)
        time.sleep(1.0)

    def stop_app(self, package: str) -> None:
        """
        强制停止指定应用。

        Args:
            package: 应用包名
        """
        logger.info(f"强制停止应用: {package}")
        self.client.device.app_stop(package)
        time.sleep(0.5)

    def restart_app(self, package: str, activity: str) -> None:
        """
        重启指定应用（先停止再启动）。

        Args:
            package: 应用包名
            activity: 启动 Activity 名称
        """
        logger.info(f"重启应用: {package}/{activity}")
        self.stop_app(package)
        time.sleep(1.0)
        self.start_app(package, activity)

    def is_app_running(self, package: str) -> bool:
        """
        检查指定应用是否正在运行。

        通过对比当前前台应用包名进行判断。

        Args:
            package: 应用包名

        Returns:
            True 表示应用正在前台运行
        """
        current = self.get_current_app()
        running = current == package
        logger.debug(f"应用 {package} 运行状态: {running} (前台: {current})")
        return running

    def get_current_app(self) -> str:
        """
        获取当前前台应用的包名。

        Returns:
            当前前台应用的包名字符串；获取失败时返回空字符串
        """
        try:
            info = self.client.device.app_current()
            # uiautomator2 app_current() 返回 dict: {"package": ..., "activity": ...}
            pkg = info.get("package", "") if isinstance(info, dict) else str(info)
            logger.debug(f"当前前台应用: {pkg}")
            return pkg
        except Exception as exc:
            logger.error(f"获取当前应用失败: {exc}")
            return ""

    # ------------------------------------------------------------------
    # 阴阳师专用快捷方法
    # ------------------------------------------------------------------

    def start_onmyoji(self) -> None:
        """
        启动阴阳师游戏。

        等价于 start_app(game_package, game_activity)。
        """
        logger.info("启动阴阳师")
        self.start_app(self.game_package, self.game_activity)

    def stop_onmyoji(self) -> None:
        """
        退出阴阳师游戏。

        等价于 stop_app(game_package)。
        """
        logger.info("退出阴阳师")
        self.stop_app(self.game_package)

    def is_onmyoji_running(self) -> bool:
        """
        检查阴阳师是否正在前台运行。

        Returns:
            True 表示阴阳师正在运行
        """
        return self.is_app_running(self.game_package)

    # ------------------------------------------------------------------
    # 屏幕控制
    # ------------------------------------------------------------------

    def wake_screen(self) -> None:
        """
        唤醒设备屏幕。

        若屏幕已亮则不做操作；若息屏则按电源键唤醒。
        """
        try:
            if not self.client.device.info.get("screenOn", True):
                logger.info("唤醒屏幕")
                self.client.device.press("power")
                time.sleep(0.5)
            else:
                logger.debug("屏幕已处于亮屏状态")
        except Exception as exc:
            logger.warning(f"唤醒屏幕时出现异常: {exc}")
            # 兜底：直接发送 power 键
            try:
                self.client.device.press("power")
                time.sleep(0.5)
            except Exception:
                pass

    def unlock_screen(self) -> None:
        """
        解锁设备屏幕（简单滑动解锁）。

        先唤醒屏幕，然后执行从下向上的滑动操作模拟简单解锁。
        注意：此方法仅适用于无密码/图案锁的设备。
        """
        logger.info("尝试滑动解锁屏幕")
        self.wake_screen()
        time.sleep(0.3)

        # 获取屏幕尺寸，执行从底部 80% 到顶部 20% 的上滑
        w, h = self.client.device.window_size()
        start_x = w // 2
        start_y = int(h * 0.8)
        end_x = w // 2
        end_y = int(h * 0.2)

        self.client.device.swipe(start_x, start_y, end_x, end_y, duration=0.4)
        time.sleep(0.5)
        logger.info("屏幕解锁完成")
