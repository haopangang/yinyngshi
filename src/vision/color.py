"""
颜色检测模块

基于 HSV 颜色空间进行颜色检测，支持：
- 指定颜色范围检测（是否存在）
- 颜色位置查找
- 像素颜色读取
- 游戏状态颜色判断（战斗结束、加载中）
"""

from __future__ import annotations

import cv2
import numpy as np
from loguru import logger


class ColorDetector:
    """HSV 颜色检测器

    所有 region 参数格式为归一化坐标 (x1, y1, x2, y2)，取值 0~1。

    Example:
        >>> detector = ColorDetector()
        >>> # 检测红色区域
        >>> is_red = detector.detect_color(
        ...     screenshot,
        ...     hsv_lower=(0, 100, 100),
        ...     hsv_upper=(10, 255, 255),
        ... )
    """

    # 战斗结束时屏幕主色调 HSV 范围（偏暗灰/蓝灰）
    BATTLE_END_HSV_LOWER = np.array([90, 10, 40])
    BATTLE_END_HSV_UPPER = np.array([130, 80, 120])

    # 加载界面的特征颜色范围（偏白/浅灰）
    LOADING_HSV_LOWER = np.array([0, 0, 200])
    LOADING_HSV_UPPER = np.array([180, 30, 255])

    # 颜色检测最小像素数阈值
    MIN_PIXEL_THRESHOLD = 100

    def detect_color(
        self,
        screenshot: np.ndarray,
        hsv_lower: tuple[int, int, int],
        hsv_upper: tuple[int, int, int],
        region: tuple[float, float, float, float] | None = None,
    ) -> bool:
        """检测截图中指定颜色是否存在

        通过 HSV 颜色范围进行掩码提取，判断符合条件的像素数是否超过阈值。

        Args:
            screenshot: BGR 格式截图
            hsv_lower: HSV 下界 (H, S, V)
            hsv_upper: HSV 上界 (H, S, V)
            region: 归一化区域坐标 (x1, y1, x2, y2)，None 表示全图

        Returns:
            True 表示检测到指定颜色
        """
        mask = self._create_mask(screenshot, hsv_lower, hsv_upper, region)
        pixel_count = cv2.countNonZero(mask)
        detected = pixel_count >= self.MIN_PIXEL_THRESHOLD

        logger.debug(
            f"颜色检测: hsv=[{hsv_lower}~{hsv_upper}] "
            f"pixels={pixel_count} detected={detected}"
        )
        return detected

    def find_color_position(
        self,
        screenshot: np.ndarray,
        hsv_lower: tuple[int, int, int],
        hsv_upper: tuple[int, int, int],
        region: tuple[float, float, float, float] | None = None,
    ) -> tuple[int, int] | None:
        """找到指定颜色的中心位置

        对掩码区域进行轮廓分析，返回最大轮廓的中心坐标（全图像素坐标）。

        Args:
            screenshot: BGR 格式截图
            hsv_lower: HSV 下界 (H, S, V)
            hsv_upper: HSV 上界 (H, S, V)
            region: 归一化区域坐标，None 表示全图

        Returns:
            颜色区域中心 (x, y) 像素坐标，未找到返回 None
        """
        mask = self._create_mask(screenshot, hsv_lower, hsv_upper, region)
        pixel_count = cv2.countNonZero(mask)

        if pixel_count < self.MIN_PIXEL_THRESHOLD:
            logger.debug(f"颜色位置查找: 像素不足 ({pixel_count})")
            return None

        # 计算偏移量
        ox, oy = self._get_region_offset(screenshot.shape, region)

        # 查找轮廓，取最大轮廓的中心
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        largest = max(contours, key=cv2.contourArea)
        M = cv2.moments(largest)
        if M["m00"] == 0:
            return None

        cx = int(M["m10"] / M["m00"]) + ox
        cy = int(M["m01"] / M["m00"]) + oy

        logger.debug(f"颜色位置: hsv=[{hsv_lower}~{hsv_upper}] -> ({cx}, {cy})")
        return cx, cy

    def get_pixel_color(
        self,
        screenshot: np.ndarray,
        x: int,
        y: int,
    ) -> tuple[int, int, int]:
        """获取指定像素的 HSV 颜色值

        Args:
            screenshot: BGR 格式截图
            x: 像素 x 坐标
            y: 像素 y 坐标

        Returns:
            HSV 颜色值 (H, S, V)
        """
        h, w = screenshot.shape[:2]
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))

        pixel_bgr = screenshot[y, x]
        pixel_img = np.uint8([[pixel_bgr]])
        pixel_hsv = cv2.cvtColor(pixel_img, cv2.COLOR_BGR2HSV)[0][0]

        return int(pixel_hsv[0]), int(pixel_hsv[1]), int(pixel_hsv[2])

    def is_battle_end(self, screenshot: np.ndarray) -> bool:
        """通过颜色特征检测战斗是否结束

        战斗结束时屏幕会出现结算画面，主色调变为偏暗灰/蓝灰色。
        检测画面中央区域的颜色变化来判断。

        Args:
            screenshot: BGR 格式截图

        Returns:
            True 表示战斗已结束
        """
        # 检测画面中央区域（40%~60% 范围）
        center_region = (0.3, 0.3, 0.7, 0.7)
        detected = self.detect_color(
            screenshot,
            hsv_lower=tuple(self.BATTLE_END_HSV_LOWER.tolist()),
            hsv_upper=tuple(self.BATTLE_END_HSV_UPPER.tolist()),
            region=center_region,
        )
        logger.debug(f"战斗结束检测: {detected}")
        return detected

    def is_loading(self, screenshot: np.ndarray) -> bool:
        """检测是否处于加载界面

        加载界面通常以白色/浅灰色为主。

        Args:
            screenshot: BGR 格式截图

        Returns:
            True 表示正在加载
        """
        # 全图检测浅色区域
        detected = self.detect_color(
            screenshot,
            hsv_lower=tuple(self.LOADING_HSV_LOWER.tolist()),
            hsv_upper=tuple(self.LOADING_HSV_UPPER.tolist()),
        )

        # 加载界面通常浅色像素占比很高
        if detected:
            mask = self._create_mask(
                screenshot,
                tuple(self.LOADING_HSV_LOWER.tolist()),
                tuple(self.LOADING_HSV_UPPER.tolist()),
            )
            total_pixels = screenshot.shape[0] * screenshot.shape[1]
            ratio = cv2.countNonZero(mask) / total_pixels
            is_loading = ratio > 0.5
            logger.debug(f"加载检测: 浅色占比={ratio:.2%} -> {is_loading}")
            return is_loading

        return False

    def _create_mask(
        self,
        screenshot: np.ndarray,
        hsv_lower: tuple[int, int, int],
        hsv_upper: tuple[int, int, int],
        region: tuple[float, float, float, float] | None = None,
    ) -> np.ndarray:
        """创建 HSV 颜色掩码

        Args:
            screenshot: BGR 截图
            hsv_lower: HSV 下界
            hsv_upper: HSV 上界
            region: 归一化区域，None 为全图

        Returns:
            二值掩码图像
        """
        image = screenshot
        if region is not None:
            image = self._crop_region(screenshot, region)

        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower = np.array(hsv_lower)
        upper = np.array(hsv_upper)
        mask = cv2.inRange(hsv_image, lower, upper)

        # 形态学操作去除噪声
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        return mask

    @staticmethod
    def _crop_region(
        screenshot: np.ndarray,
        region: tuple[float, float, float, float],
    ) -> np.ndarray:
        """裁剪归一化区域

        Args:
            screenshot: BGR 截图
            region: 归一化坐标 (x1, y1, x2, y2)

        Returns:
            裁剪后的图像
        """
        h, w = screenshot.shape[:2]
        rx1 = max(0, int(region[0] * w))
        ry1 = max(0, int(region[1] * h))
        rx2 = min(w, int(region[2] * w))
        ry2 = min(h, int(region[3] * h))
        rx2 = max(rx2, rx1 + 1)
        ry2 = max(ry2, ry1 + 1)
        return screenshot[ry1:ry2, rx1:rx2]

    @staticmethod
    def _get_region_offset(
        shape: tuple,
        region: tuple[float, float, float, float] | None,
    ) -> tuple[int, int]:
        """计算区域裁剪后的坐标偏移量

        Args:
            shape: 原始图像 shape (h, w, ...)
            region: 归一化区域坐标

        Returns:
            (ox, oy) 像素偏移量
        """
        if region is None:
            return 0, 0
        h, w = shape[:2]
        ox = max(0, int(region[0] * w))
        oy = max(0, int(region[1] * h))
        return ox, oy
