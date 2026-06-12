"""
截图管理器

提供 Android 设备屏幕截图的获取、缓存与保存功能：
- 获取当前截图（OpenCV np.ndarray 格式）
- 带缓存的截图（避免短时间内重复截图，降低性能开销）
- 保存截图到本地文件
- 获取设备屏幕尺寸

依赖 ADBClient 获取底层 uiautomator2 Device 实例。
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
from loguru import logger

from src.device.adb_client import ADBClient


class ScreenCapture:
    """
    截图管理器，封装设备截图的获取、缓存与持久化。

    Attributes:
        client: 底层 ADBClient 实例
        max_age_ms: 截图缓存最大有效期（毫秒），默认 500ms
    """

    def __init__(
        self,
        client: ADBClient,
        max_age_ms: int = 500,
    ) -> None:
        """
        初始化 ScreenCapture。

        Args:
            client: ADBClient 实例，需已完成设备连接
            max_age_ms: 截图缓存最大有效期（毫秒），默认 500；
                        在此时间内的重复截图请求直接返回缓存
        """
        self.client: ADBClient = client
        self.max_age_ms: int = max_age_ms

        self._cache: Optional[np.ndarray] = None
        self._cache_ts: float = 0.0  # 缓存时间戳（毫秒）
        self._lock: threading.Lock = threading.Lock()
        self._screen_size: Optional[Tuple[int, int]] = None

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def capture(self) -> np.ndarray:
        """
        获取当前设备屏幕截图。

        每次调用均向设备请求新的截图。

        Returns:
            OpenCV 格式（BGR）的截图，类型为 np.ndarray，
            形状为 (height, width, 3)

        Raises:
            RuntimeError: 截图获取失败时抛出
        """
        try:
            img = self.client.device.screenshot(format="opencv")
            if img is None or not isinstance(img, np.ndarray):
                raise RuntimeError("截图返回数据为空或格式异常")
            logger.debug(f"截图成功: {img.shape}")
            return img
        except Exception as exc:
            raise RuntimeError(f"截图获取失败: {exc}") from exc

    def capture_cached(self, max_age_ms: Optional[int] = None) -> np.ndarray:
        """
        获取截图，带缓存机制以避免频繁截图。

        若缓存中的截图仍在有效期内（默认 500ms），则直接返回缓存；
        否则重新截图并更新缓存。

        Args:
            max_age_ms: 本次调用使用的缓存有效期（毫秒）；
                        为 None 则使用实例默认值 self.max_age_ms

        Returns:
            OpenCV 格式（BGR）的截图，类型为 np.ndarray
        """
        age_limit = max_age_ms if max_age_ms is not None else self.max_age_ms
        now_ms = time.time() * 1000

        with self._lock:
            if (
                self._cache is not None
                and (now_ms - self._cache_ts) < age_limit
            ):
                logger.debug("使用缓存截图")
                return self._cache.copy()

        # 缓存过期或不存在，重新截图
        img = self.capture()
        with self._lock:
            self._cache = img.copy()
            self._cache_ts = now_ms
        return img

    def save_screenshot(self, path: str | Path) -> Path:
        """
        获取当前截图并保存到指定文件路径。

        自动创建父目录（若不存在）。

        Args:
            path: 目标文件路径（支持 str 或 Path），建议使用 .png 后缀

        Returns:
            保存后的文件绝对路径

        Raises:
            RuntimeError: 截图或保存失败时抛出
        """
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        img = self.capture()
        success = cv2.imwrite(str(file_path), img)
        if not success:
            raise RuntimeError(f"截图保存失败: {file_path}")

        logger.info(f"截图已保存: {file_path.resolve()}")
        return file_path.resolve()

    def get_screen_size(self) -> Tuple[int, int]:
        """
        获取设备屏幕尺寸（宽, 高）。

        首次调用时向设备查询，之后返回缓存值。

        Returns:
            (width, height) 元组，单位为像素
        """
        if self._screen_size is None:
            try:
                w, h = self.client.device.window_size()
                self._screen_size = (int(w), int(h))
                logger.debug(f"屏幕尺寸: {self._screen_size}")
            except Exception as exc:
                logger.error(f"获取屏幕尺寸失败: {exc}")
                raise
        return self._screen_size

    def invalidate_cache(self) -> None:
        """
        手动清除截图缓存。

        下次调用 capture_cached() 时将强制重新截图。
        """
        with self._lock:
            self._cache = None
            self._cache_ts = 0.0
            logger.debug("截图缓存已清除")

    def invalidate_screen_size(self) -> None:
        """
        手动清除屏幕尺寸缓存。

        当设备屏幕方向改变或切换分辨率后应调用此方法。
        """
        self._screen_size = None
        logger.debug("屏幕尺寸缓存已清除")
