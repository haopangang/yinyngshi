"""
OCR 文字识别引擎封装

基于 rapidocr-onnxruntime 实现轻量级 OCR，无需 PaddlePaddle。
使用单例模式确保 OCR 模型只加载一次，节省内存和初始化时间。
支持全图识别、区域识别、指定文字查找、数字识别等常用接口。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
from loguru import logger


@dataclass
class TextResult:
    """OCR 文字识别结果

    Attributes:
        text: 识别出的文本
        confidence: 识别置信度 0~1
        box: 文字边界框 (x1, y1, x2, y2)，像素坐标
        center_x: 文字区域中心 x 坐标（像素）
        center_y: 文字区域中心 y 坐标（像素）
    """

    text: str
    confidence: float
    box: tuple[int, int, int, int]

    @property
    def center_x(self) -> int:
        """文字区域中心 x 坐标"""
        return (self.box[0] + self.box[2]) // 2

    @property
    def center_y(self) -> int:
        """文字区域中心 y 坐标"""
        return (self.box[1] + self.box[3]) // 2

    def center(self) -> tuple[int, int]:
        """返回中心坐标 (x, y)"""
        return self.center_x, self.center_y

    def __repr__(self) -> str:
        return (
            f"TextResult(text='{self.text}', "
            f"confidence={self.confidence:.3f}, "
            f"box={self.box}, "
            f"center=({self.center_x}, {self.center_y}))"
        )


class OCREngine:
    """OCR 文字识别引擎（单例模式）

    封装 rapidocr-onnxruntime，提供全图识别、区域识别、文字查找、数字识别等接口。

    Example:
        >>> ocr = OCREngine()
        >>> results = ocr.recognize(screenshot)
        >>> for r in results:
        ...     print(f"{r.text} ({r.confidence:.2f})")
    """

    _instance: OCREngine | None = None
    _ocr: object | None = None

    def __new__(cls) -> OCREngine:
        """单例模式：确保全局只有一个 OCREngine 实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """初始化 OCR 引擎（延迟加载模型）"""
        if self._ocr is not None:
            return
        self._ensure_loaded()

    def _ensure_loaded(self) -> None:
        """延迟加载 OCR 模型（仅首次调用时加载）"""
        if self._ocr is not None:
            return
        try:
            from rapidocr_onnxruntime import RapidOCR

            OCREngine._ocr = RapidOCR()
            logger.info("OCR 引擎加载成功 (rapidocr-onnxruntime)")
        except ImportError as e:
            logger.error(f"rapidocr-onnxruntime 未安装或加载失败: {e}")
            raise

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例实例（测试用途）"""
        cls._instance = None
        cls._ocr = None
        logger.debug("OCR 引擎单例已重置")

    def _run_ocr(self, image: np.ndarray) -> list[tuple[str, float, tuple[int, int, int, int]]]:
        """执行底层 OCR 识别

        Args:
            image: BGR 格式图像

        Returns:
            识别结果列表，每项为 (text, confidence, (x1, y1, x2, y2))
        """
        self._ensure_loaded()
        try:
            result, _ = self._ocr(image)  # type: ignore[misc]
        except Exception as e:
            logger.error(f"OCR 识别异常: {e}")
            return []

        if not result:
            return []

        parsed: list[tuple[str, float, tuple[int, int, int, int]]] = []
        for item in result:
            box_points, text, confidence = item
            # box_points 为 [[x1,y1],[x2,y1],[x2,y2],[x1,y2]] 四点坐标
            xs = [p[0] for p in box_points]
            ys = [p[1] for p in box_points]
            x1, x2 = int(min(xs)), int(max(xs))
            y1, y2 = int(min(ys)), int(max(ys))
            parsed.append((text, float(confidence), (x1, y1, x2, y2)))

        return parsed

    def recognize(
        self,
        screenshot: np.ndarray,
        region: tuple[float, float, float, float] | None = None,
    ) -> list[TextResult]:
        """全图或指定区域 OCR 文字识别

        Args:
            screenshot: BGR 格式截图
            region: 归一化区域坐标 (x1, y1, x2, y2)，取值 0~1；None 表示全图

        Returns:
            识别结果列表
        """
        if region is not None:
            h, w = screenshot.shape[:2]
            ox = max(0, int(region[0] * w))
            oy = max(0, int(region[1] * h))
            screenshot = self._crop_region(screenshot, region)
            if screenshot is None:
                return []
        else:
            ox, oy = 0, 0

        raw_results = self._run_ocr(screenshot)
        results = [
            TextResult(
                text=text,
                confidence=conf,
                box=(box[0] + ox, box[1] + oy, box[2] + ox, box[3] + oy),
            )
            for text, conf, box in raw_results
        ]

        logger.debug(f"OCR 识别: 找到 {len(results)} 个文字区域")
        return results

    def find_text(
        self,
        screenshot: np.ndarray,
        text: str,
        region: tuple[float, float, float, float] | None = None,
    ) -> TextResult | None:
        """在截图中查找指定文字

        支持精确匹配和包含匹配，优先返回精确匹配结果。

        Args:
            screenshot: BGR 格式截图
            text: 要查找的文字
            region: 归一化区域坐标，None 表示全图

        Returns:
            匹配的文字结果，未找到返回 None
        """
        results = self.recognize(screenshot, region)

        # 优先精确匹配
        for r in results:
            if r.text.strip() == text.strip():
                logger.debug(f"文字精确匹配: '{text}' -> {r}")
                return r

        # 包含匹配
        for r in results:
            if text.strip() in r.text.strip():
                logger.debug(f"文字包含匹配: '{text}' in '{r.text}' -> {r}")
                return r

        logger.debug(f"文字未找到: '{text}'")
        return None

    def read_number(
        self,
        screenshot: np.ndarray,
        region: tuple[float, float, float, float],
    ) -> int | None:
        """识别指定区域内的数字（如体力值、金币等）

        Args:
            screenshot: BGR 格式截图
            region: 归一化区域坐标 (x1, y1, x2, y2)

        Returns:
            识别出的整数，无法识别返回 None
        """
        results = self.recognize(screenshot, region)
        for r in results:
            # 提取数字部分
            digits = re.sub(r"\D", "", r.text)
            if digits:
                try:
                    value = int(digits)
                    logger.debug(f"数字识别: region={region} -> {value} (raw='{r.text}')")
                    return value
                except ValueError:
                    continue

        logger.debug(f"数字识别失败: region={region}")
        return None

    @staticmethod
    def _crop_region(
        screenshot: np.ndarray,
        region: tuple[float, float, float, float],
    ) -> np.ndarray | None:
        """裁剪归一化区域

        Args:
            screenshot: BGR 截图
            region: 归一化坐标 (x1, y1, x2, y2)

        Returns:
            裁剪后的图像，区域无效返回 None
        """
        h, w = screenshot.shape[:2]
        rx1 = max(0, int(region[0] * w))
        ry1 = max(0, int(region[1] * h))
        rx2 = min(w, int(region[2] * w))
        ry2 = min(h, int(region[3] * h))

        if rx2 <= rx1 or ry2 <= ry1:
            logger.warning(f"无效 OCR 区域: {region}")
            return None

        return screenshot[ry1:ry2, rx1:rx2].copy()
