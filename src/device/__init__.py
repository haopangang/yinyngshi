"""
设备控制层（Device Layer）

阴阳师辅助脚本的最底层模块，负责与 Android 设备的直接交互。
提供 ADB 连接管理、操作控制、应用管理和截图功能。

主要导出类：
- ADBClient: ADB 连接管理器，支持 USB/WiFi 连接与心跳检测
- DeviceController: 设备操作控制器，封装点击、滑动、输入等交互操作
- AppManager: 应用管理器，管理应用生命周期与阴阳师快捷操作
- ScreenCapture: 截图管理器，提供截图获取、缓存与保存

注意：设备层为最底层模块，不可依赖上层（engine、tasks、scene 等）。
"""

from src.device.adb_client import ADBClient
from src.device.app_manager import AppManager
from src.device.controller import DeviceController
from src.device.screen import ScreenCapture

__all__ = [
    "ADBClient",
    "AppManager",
    "DeviceController",
    "ScreenCapture",
]
