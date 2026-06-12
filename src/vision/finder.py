"""
统一查找接口（门面模式）

组合 TemplateMatcher + OCREngine + ColorDetector，
对外提供统一的 find_image / find_text / find_color / click_image / wait_image 等接口。
屏蔽底层细节，方便任务层直接调用。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

import numpy as np
from loguru import logger

from src.vision.color import ColorDetector
from src.vision.matcher import MatchResult, TemplateMatcher
from src.vision.ocr import OCREngine, TextResult

if TYPE_CHECKING:
    pass  # 设备层接口待后续实现


class VisionFinder:
    """统一视觉查找接口（门面模式）

    组合模板匹配、OCR、颜色检测三大引擎，提供简洁的查找/等待/点击 API。
    所有 region 参数为归一化坐标 (x1, y1, x2, y2)，取值 0~1。

    Example:
        >>> finder = VisionFinder()
        >>> result = finder.find_image("common/start_btn.png")
        >>> if result:
        ...     print(f"Found at {result.center()}")
    """

    def __init__(
        self,
        screenshot_func=None,
        click_func=None,
        templates_dir: str = "assets/templates",
    ) -> None:
        """初始化统一查找器

        Args:
            screenshot_func: 截图函数，返回 np.ndarray（BGR 格式）；
                             需要配合设备层注入
            click_func: 点击函数，接收 (x, y) 像素坐标；
                        需要配合设备层注入
            templates_dir: 模板图片根目录
        """
        self._matcher = TemplateMatcher(templates_dir=templates_dir)
        self._ocr = OCREngine()
        self._color = ColorDetector()
        self._screenshot_func = screenshot_func
        self._click_func = click_func

        logger.info("VisionFinder 初始化完成")

    @property
    def matcher(self) -> TemplateMatcher:
        """底层模板匹配引擎"""
        return self._matcher

    @property
    def ocr(self) -> OCREngine:
        """底层 OCR 引擎"""
        return self._ocr

    @property
    def color_detector(self) -> ColorDetector:
        """底层颜色检测器"""
        return self._color

    def _get_screenshot(self) -> np.ndarray | None:
        """获取当前截图

        Returns:
            BGR 格式截图，截图函数未设置或失败返回 None
        """
        if self._screenshot_func is None:
            logger.warning("截图函数未注入，无法获取截图")
            return None
        try:
            return self._screenshot_func()
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return None

    def find_image(
        self,
        template_path: str,
        threshold: float = 0.8,
        region: tuple[float, float, float, float] | None = None,
        screenshot: np.ndarray | None = None,
    ) -> MatchResult | None:
        """在截图中查找指定模板图片

        Args:
            template_path: 模板图片路径（相对于 templates_dir）
            threshold: 匹配阈值 0~1
            region: 归一化区域坐标 (x1, y1, x2, y2)
            screenshot: 可选，直接传入截图；None 则自动截图

        Returns:
            匹配结果，未找到返回 None
        """
        img = screenshot if screenshot is not None else self._get_screenshot()
        if img is None:
            return None

        if region is not None:
            return self._matcher.match_in_region(img, template_path, region, threshold)
        return self._matcher.match(img, template_path, threshold)

    def find_text(
        self,
        text: str,
        region: tuple[float, float, float, float] | None = None,
        screenshot: np.ndarray | None = None,
    ) -> TextResult | None:
        """在截图中查找指定文字

        Args:
            text: 要查找的文字
            region: 归一化区域坐标
            screenshot: 可选，直接传入截图

        Returns:
            文字识别结果，未找到返回 None
        """
        img = screenshot if screenshot is not None else self._get_screenshot()
        if img is None:
            return None

        return self._ocr.find_text(img, text, region)

    def find_color(
        self,
        hsv_lower: tuple[int, int, int],
        hsv_upper: tuple[int, int, int],
        region: tuple[float, float, float, float] | None = None,
        screenshot: np.ndarray | None = None,
    ) -> tuple[int, int] | None:
        """查找指定颜色的位置

        Args:
            hsv_lower: HSV 下界 (H, S, V)
            hsv_upper: HSV 上界 (H, S, V)
            region: 归一化区域坐标
            screenshot: 可选，直接传入截图

        Returns:
            颜色位置 (x, y) 像素坐标，未找到返回 None
        """
        img = screenshot if screenshot is not None else self._get_screenshot()
        if img is None:
            return None

        return self._color.find_color_position(img, hsv_lower, hsv_upper, region)

    def click_image(
        self,
        template_path: str,
        threshold: float = 0.8,
        region: tuple[float, float, float, float] | None = None,
        screenshot: np.ndarray | None = None,
    ) -> bool:
        """查找模板图片并点击其中心位置

        需要设备层的 click_func 已注入。

        Args:
            template_path: 模板图片路径
            threshold: 匹配阈值
            region: 归一化区域坐标
            screenshot: 可选截图

        Returns:
            True 表示找到并点击成功
        """
        result = self.find_image(template_path, threshold, region, screenshot)
        if result is None:
            logger.debug(f"click_image: 未找到 {template_path}")
            return False

        if self._click_func is None:
            logger.warning("click_func 未注入，无法执行点击")
            return False

        try:
            self._click_func(result.center_x, result.center_y)
            logger.info(f"点击: {template_path} -> ({result.center_x}, {result.center_y})")
            return True
        except Exception as e:
            logger.error(f"点击失败: {e}")
            return False

    def wait_image(
        self,
        template_path: str,
        timeout: float = 10.0,
        interval: float = 0.5,
        threshold: float = 0.8,
        region: tuple[float, float, float, float] | None = None,
    ) -> MatchResult | None:
        """等待指定模板图片出现

        Args:
            template_path: 模板图片路径
            timeout: 超时时间（秒）
            interval: 轮询间隔（秒）
            threshold: 匹配阈值
            region: 归一化区域坐标

        Returns:
            匹配结果，超时返回 None
        """
        start = time.time()
        logger.debug(f"等待图片: {template_path} (timeout={timeout}s)")

        while time.time() - start < timeout:
            result = self.find_image(template_path, threshold, region)
            if result is not None:
                elapsed = time.time() - start
                logger.info(f"图片出现: {template_path} ({elapsed:.1f}s)")
                return result
            time.sleep(interval)

        logger.warning(f"等待图片超时: {template_path} ({timeout}s)")
        return None

    def wait_text(
        self,
        text: str,
        timeout: float = 10.0,
        interval: float = 0.5,
        region: tuple[float, float, float, float] | None = None,
    ) -> TextResult | None:
        """等待指定文字出现

        Args:
            text: 要等待的文字
            timeout: 超时时间（秒）
            interval: 轮询间隔（秒）
            region: 归一化区域坐标

        Returns:
            文字识别结果，超时返回 None
        """
        start = time.time()
        logger.debug(f"等待文字: '{text}' (timeout={timeout}s)")

        while time.time() - start < timeout:
            result = self.find_text(text, region)
            if result is not None:
                elapsed = time.time() - start
                logger.info(f"文字出现: '{text}' ({elapsed:.1f}s)")
                return result
            time.sleep(interval)

        logger.warning(f"等待文字超时: '{text}' ({timeout}s)")
        return None

    def exists(
        self,
        template_path: str,
        threshold: float = 0.8,
        region: tuple[float, float, float, float] | None = None,
        screenshot: np.ndarray | None = None,
    ) -> bool:
        """判断指定模板图片是否存在于当前截图中

        Args:
            template_path: 模板图片路径
            threshold: 匹配阈值
            region: 归一化区域坐标
            screenshot: 可选截图

        Returns:
            True 表示图片存在
        """
        return self.find_image(template_path, threshold, region, screenshot) is not None
