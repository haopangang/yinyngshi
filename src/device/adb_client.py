"""
ADB 连接管理器

提供 Android 设备的 ADB 连接管理功能，支持：
- USB 和 WiFi 两种连接方式
- 自动列出已连接设备
- 心跳检测（后台线程定期检查连接状态）
- 自动重连机制

底层使用 uiautomator2 库实现设备通信。
"""

from __future__ import annotations

import subprocess
import threading
import time
from typing import List, Optional

import uiautomator2 as u2
from loguru import logger


class ADBClient:
    """
    ADB 设备连接管理器

    负责维护与 Android 设备的 ADB 连接，提供连接、断开、重连及
    心跳检测等能力。所有设备操作类（DeviceController、AppManager、
    ScreenCapture）均依赖此实例获取 uiautomator2 设备对象。

    Attributes:
        serial: 当前连接设备的序列号（USB 为设备 ID，WiFi 为 ip:port）
        adb_path: ADB 可执行文件路径，默认使用系统 PATH 中的 adb
        heartbeat_interval: 心跳检测间隔（秒），默认 30s
    """

    def __init__(
        self,
        serial: Optional[str] = None,
        adb_path: str = "adb",
        heartbeat_interval: int = 30,
    ) -> None:
        """
        初始化 ADBClient。

        Args:
            serial: 设备序列号；为 None 时不自动连接，需后续调用 connect()
            adb_path: ADB 可执行文件路径，默认 "adb"
            heartbeat_interval: 心跳检测间隔秒数，默认 30s；设为 0 则禁用心跳
        """
        self.serial: Optional[str] = serial
        self.adb_path: str = adb_path
        self.heartbeat_interval: int = heartbeat_interval

        self._device: Optional[u2.Device] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_stop: threading.Event = threading.Event()
        self._lock: threading.Lock = threading.Lock()

        if serial:
            self.connect(serial)

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def list_devices(self) -> List[str]:
        """
        列出当前 ADB 已连接的所有设备序列号。

        Returns:
            包含各设备序列号的列表，如 ["emulator-5554", "192.168.1.2:5555"]
        """
        try:
            result = subprocess.run(
                [self.adb_path, "devices"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            lines = result.stdout.strip().splitlines()[1:]  # 跳过表头
            devices = [
                line.split()[0]
                for line in lines
                if line.strip() and "device" in line
            ]
            logger.debug(f"已发现设备: {devices}")
            return devices
        except Exception as exc:
            logger.error(f"获取设备列表失败: {exc}")
            return []

    def connect(self, serial: str) -> "ADBClient":
        """
        连接指定设备（USB 或 WiFi）。

        若当前已有活跃连接，会先断开旧连接再建立新连接。

        Args:
            serial: 设备序列号，如 "emulator-5554" 或 "192.168.1.2:5555"

        Returns:
            self，支持链式调用

        Raises:
            ConnectionError: 连接失败时抛出
        """
        with self._lock:
            if self._device is not None:
                logger.info(f"断开旧连接: {self.serial}")
                self._cleanup()

            logger.info(f"正在连接设备: {serial}")
            try:
                self._device = u2.connect(serial)
                # 触发一次 info 访问以验证连接真实可用
                _ = self._device.info
                self.serial = serial
                logger.success(f"设备连接成功: {serial}")
                self._start_heartbeat()
            except Exception as exc:
                self._device = None
                self.serial = None
                raise ConnectionError(f"无法连接设备 {serial}: {exc}") from exc

            return self

    def connect_wifi(self, ip: str, port: int = 5555) -> "ADBClient":
        """
        通过 WiFi 连接设备。

        先通过 adb connect 命令建立 TCP/IP 连接，再用 uiautomator2 接管。

        Args:
            ip: 设备 IP 地址
            port: ADB TCP 端口，默认 5555

        Returns:
            self，支持链式调用

        Raises:
            ConnectionError: 连接失败时抛出
        """
        addr = f"{ip}:{port}"
        logger.info(f"正在通过 WiFi 连接: {addr}")
        try:
            result = subprocess.run(
                [self.adb_path, "connect", addr],
                capture_output=True,
                text=True,
                timeout=15,
            )
            output = result.stdout.strip()
            if "connected" not in output.lower():
                raise ConnectionError(f"adb connect 返回异常: {output}")
        except subprocess.TimeoutExpired as exc:
            raise ConnectionError(f"WiFi 连接超时: {addr}") from exc

        return self.connect(addr)

    def disconnect(self) -> None:
        """
        断开当前设备连接，停止心跳线程。

        调用后实例仍可复用，再次调用 connect() 即可重新连接。
        """
        logger.info(f"正在断开连接: {self.serial}")
        self._stop_heartbeat()
        with self._lock:
            self._cleanup()
            self.serial = None

    def is_connected(self) -> bool:
        """
        检查当前设备是否处于连接状态。

        通过尝试访问 uiautomator2 device.info 来判断连接是否存活。

        Returns:
            True 表示连接正常，False 表示未连接或连接已断开
        """
        with self._lock:
            if self._device is None:
                return False
            try:
                _ = self._device.info
                return True
            except Exception:
                return False

    def reconnect(self) -> "ADBClient":
        """
        重新连接当前设备。

        先断开旧连接，再使用上次的 serial 重新建立连接。

        Returns:
            self，支持链式调用

        Raises:
            ConnectionError: 没有可重连的设备或重连失败
        """
        if not self.serial:
            raise ConnectionError("无可重连设备：serial 为空")
        serial = self.serial
        logger.info(f"正在重连设备: {serial}")
        self._stop_heartbeat()
        with self._lock:
            self._cleanup()
        return self.connect(serial)

    @property
    def device(self) -> u2.Device:
        """
        获取底层 uiautomator2 Device 实例。

        Returns:
            uiautomator2.Device 对象

        Raises:
            RuntimeError: 当前无活跃连接
        """
        if self._device is None:
            raise RuntimeError(
                "设备未连接，请先调用 connect() 或 connect_wifi()"
            )
        return self._device

    # ------------------------------------------------------------------
    # 心跳检测
    # ------------------------------------------------------------------

    def _start_heartbeat(self) -> None:
        """启动心跳检测后台线程（若尚未运行）。"""
        if self.heartbeat_interval <= 0:
            return
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return

        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="adb-heartbeat",
        )
        self._heartbeat_thread.start()
        logger.debug(f"心跳检测已启动，间隔 {self.heartbeat_interval}s")

    def _stop_heartbeat(self) -> None:
        """停止心跳检测后台线程。"""
        self._heartbeat_stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=5)
            self._heartbeat_thread = None

    def _heartbeat_loop(self) -> None:
        """心跳主循环：定期检查设备连接状态，断线时尝试重连。"""
        while not self._heartbeat_stop.is_set():
            self._heartbeat_stop.wait(timeout=self.heartbeat_interval)
            if self._heartbeat_stop.is_set():
                break

            if not self.is_connected():
                logger.warning(f"心跳检测到连接断开: {self.serial}")
                try:
                    self.reconnect()
                    logger.success(f"心跳重连成功: {self.serial}")
                except Exception as exc:
                    logger.error(f"心跳重连失败: {exc}")

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _cleanup(self) -> None:
        """清理底层 uiautomator2 资源（内部使用，需在锁内调用）。"""
        if self._device is not None:
            try:
                # uiautomator2 Device 没有显式 close，置 None 即可
                self._device = None
            except Exception:
                self._device = None
