"""
视觉识别引擎模块

提供阴阳师游戏辅助脚本的核心视觉识别能力：
- TemplateMatcher: OpenCV 多尺度模板匹配
- OCREngine: 基于 rapidocr-onnxruntime 的文字识别
- ColorDetector: HSV 颜色检测
- SceneRecognizer: 游戏场景识别状态机
- VisionFinder: 统一查找接口（门面模式）

Example:
    >>> from src.vision import VisionFinder, GameScene, SceneRecognizer
    >>> finder = VisionFinder(screenshot_func=device.screenshot, click_func=device.click)
    >>> result = finder.find_image("common/start_btn.png")
"""

from src.vision.color import ColorDetector
from src.vision.finder import VisionFinder
from src.vision.matcher import MatchResult, TemplateMatcher
from src.vision.ocr import OCREngine, TextResult
from src.vision.scene import GameScene, SceneRecognizer

__all__ = [
    # 核心类
    "TemplateMatcher",
    "OCREngine",
    "ColorDetector",
    "SceneRecognizer",
    "VisionFinder",
    # 数据类
    "MatchResult",
    "TextResult",
    # 枚举
    "GameScene",
]
