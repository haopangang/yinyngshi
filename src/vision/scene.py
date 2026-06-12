"""
场景识别状态机

定义阴阳师游戏中的所有场景类型，并基于模板匹配 + 颜色检测 + OCR 组合特征
进行场景识别。支持场景缓存和等待场景切换功能。
"""

from __future__ import annotations

import time
from enum import Enum, auto
from typing import TYPE_CHECKING

import numpy as np
from loguru import logger

if TYPE_CHECKING:
    from src.vision.color import ColorDetector
    from src.vision.matcher import TemplateMatcher
    from src.vision.ocr import OCREngine


class GameScene(Enum):
    """游戏场景枚举

    定义所有可识别的游戏场景状态。
    """

    UNKNOWN = auto()
    """未知场景"""

    LOADING = auto()
    """加载界面"""

    MAIN_SCREEN = auto()
    """主界面（庭院）"""

    EXPLORE = auto()
    """探索界面"""

    OROCHI = auto()
    """八岐大蛇（御魂）"""

    AWAKENING = auto()
    """觉醒副本"""

    BREAKTHROUGH = auto()
    """突破结界"""

    HYAKKI = auto()
    """百鬼夜行"""

    BATTLE = auto()
    """战斗中"""

    BATTLE_RESULT = auto()
    """战斗结算"""

    TEAM_ROOM = auto()
    """组队房间"""

    GUILD = auto()
    """阴阳寮"""

    SETTINGS = auto()
    """设置界面"""

    POPUP_NETWORK = auto()
    """网络异常弹窗"""

    POPUP_UPDATE = auto()
    """更新弹窗"""

    POPUP_GENERIC = auto()
    """通用弹窗"""


# 场景识别特征配置：每个场景对应一组检测规则
# 格式: {场景: {"templates": [...], "ocr_texts": [...], "colors": [...]}}
# 实际模板路径在 assets/templates/scene/ 下
_SCENE_FEATURES: dict[GameScene, dict] = {
    GameScene.LOADING: {
        "templates": ["scene/loading_logo.png"],
        "ocr_texts": [],
        "colors": [],
        "use_loading_detector": True,
    },
    GameScene.MAIN_SCREEN: {
        "templates": ["scene/main_screen_btn.png"],
        "ocr_texts": ["探索", "召唤"],
        "colors": [],
    },
    GameScene.EXPLORE: {
        "templates": ["scene/explore_chapter.png"],
        "ocr_texts": ["章节"],
        "colors": [],
    },
    GameScene.OROCHI: {
        "templates": ["scene/orochi_banner.png"],
        "ocr_texts": ["八岐大蛇", "御魂"],
        "colors": [],
    },
    GameScene.AWAKENING: {
        "templates": ["scene/awakening_banner.png"],
        "ocr_texts": ["觉醒"],
        "colors": [],
    },
    GameScene.BREAKTHROUGH: {
        "templates": ["scene/breakthrough_banner.png"],
        "ocr_texts": ["突破"],
        "colors": [],
    },
    GameScene.BATTLE: {
        "templates": ["scene/battle_auto_btn.png"],
        "ocr_texts": ["自动", "手动"],
        "colors": [],
    },
    GameScene.BATTLE_RESULT: {
        "templates": ["scene/battle_result_victory.png"],
        "ocr_texts": ["胜利", "战斗结算"],
        "colors": [],
        "use_battle_end_detector": True,
    },
    GameScene.TEAM_ROOM: {
        "templates": ["scene/team_room_banner.png"],
        "ocr_texts": ["组队"],
        "colors": [],
    },
    GameScene.GUILD: {
        "templates": ["scene/guild_banner.png"],
        "ocr_texts": ["阴阳寮"],
        "colors": [],
    },
    GameScene.SETTINGS: {
        "templates": ["scene/settings_title.png"],
        "ocr_texts": ["设置"],
        "colors": [],
    },
    GameScene.POPUP_NETWORK: {
        "templates": [],
        "ocr_texts": ["网络", "连接失败", "重试"],
        "colors": [],
    },
    GameScene.POPUP_UPDATE: {
        "templates": [],
        "ocr_texts": ["更新", "下载"],
        "colors": [],
    },
}


class SceneRecognizer:
    """游戏场景识别器

    组合模板匹配、OCR、颜色检测进行场景判断，支持结果缓存和等待切换。

    Example:
        >>> recognizer = SceneRecognizer(matcher, ocr, color_detector)
        >>> scene = recognizer.recognize(screenshot)
        >>> print(f"当前场景: {scene.name}")
    """

    def __init__(
        self,
        matcher: TemplateMatcher,
        ocr: OCREngine,
        color_detector: ColorDetector,
        cache_ttl: float = 1.0,
    ) -> None:
        """初始化场景识别器

        Args:
            matcher: 模板匹配引擎实例
            ocr: OCR 引擎实例
            color_detector: 颜色检测器实例
            cache_ttl: 场景缓存有效期（秒），避免短时间内重复识别
        """
        self._matcher = matcher
        self._ocr = ocr
        self._color = color_detector
        self._cache_ttl = cache_ttl

        self._cached_scene: GameScene = GameScene.UNKNOWN
        self._cache_time: float = 0.0

        logger.info("SceneRecognizer 初始化完成")

    def recognize(self, screenshot: np.ndarray) -> GameScene:
        """识别当前游戏场景

        优先使用缓存，缓存过期后依次检测各场景特征。
        检测优先级：颜色（快速）→ 模板 → OCR（较慢）

        Args:
            screenshot: BGR 格式截图

        Returns:
            识别到的游戏场景
        """
        now = time.time()
        if now - self._cache_time < self._cache_ttl and self._cached_scene != GameScene.UNKNOWN:
            logger.debug(f"场景识别（缓存）: {self._cached_scene.name}")
            return self._cached_scene

        scene = self._do_recognize(screenshot)
        self._cached_scene = scene
        self._cache_time = now

        logger.info(f"场景识别: {scene.name}")
        return scene

    def is_scene(self, screenshot: np.ndarray, scene: GameScene) -> bool:
        """判断当前截图是否为指定场景

        Args:
            screenshot: BGR 格式截图
            scene: 目标场景

        Returns:
            True 表示当前为指定场景
        """
        return self.recognize(screenshot) == scene

    def wait_scene(
        self,
        target_scene: GameScene,
        timeout: float = 30.0,
        interval: float = 0.5,
        screenshot_func=None,
    ) -> bool:
        """等待进入指定场景

        轮询截图并识别场景，直到匹配目标场景或超时。

        Args:
            target_scene: 目标场景
            timeout: 超时时间（秒）
            interval: 轮询间隔（秒）
            screenshot_func: 截图函数，返回 np.ndarray；
                             为 None 时使用外部传入（需要调用方提供）

        Returns:
            True 表示在超时内进入目标场景
        """
        start = time.time()
        logger.info(f"等待场景: {target_scene.name} (timeout={timeout}s)")

        while time.time() - start < timeout:
            if screenshot_func is None:
                logger.warning("wait_scene 未提供截图函数，无法执行")
                return False

            screenshot = screenshot_func()
            if screenshot is not None:
                current = self.recognize(screenshot)
                if current == target_scene:
                    elapsed = time.time() - start
                    logger.info(f"已进入目标场景: {target_scene.name} ({elapsed:.1f}s)")
                    return True

            time.sleep(interval)

        logger.warning(f"等待场景超时: {target_scene.name} ({timeout}s)")
        return False

    def invalidate_cache(self) -> None:
        """清除场景缓存，强制下次重新识别"""
        self._cached_scene = GameScene.UNKNOWN
        self._cache_time = 0.0
        logger.debug("场景缓存已清除")

    def _do_recognize(self, screenshot: np.ndarray) -> GameScene:
        """执行实际的场景识别逻辑

        对每个已知场景按特征权重打分，返回得分最高的场景。

        Args:
            screenshot: BGR 格式截图

        Returns:
            识别到的场景，无法识别返回 UNKNOWN
        """
        best_scene = GameScene.UNKNOWN
        best_score = 0.0

        for scene, features in _SCENE_FEATURES.items():
            score = self._score_scene(screenshot, features)
            if score > best_score:
                best_score = score
                best_scene = scene

        if best_score > 0:
            logger.debug(f"场景识别最佳: {best_scene.name} (score={best_score:.2f})")
        return best_scene

    def _score_scene(self, screenshot: np.ndarray, features: dict) -> float:
        """计算当前截图与指定场景特征的匹配得分

        Args:
            screenshot: BGR 截图
            features: 场景特征配置字典

        Returns:
            匹配得分 0~N，0 表示不匹配
        """
        score = 0.0

        # 颜色检测器（快速）
        if features.get("use_loading_detector"):
            if self._color.is_loading(screenshot):
                score += 3.0

        if features.get("use_battle_end_detector"):
            if self._color.is_battle_end(screenshot):
                score += 3.0

        # 模板匹配
        templates = features.get("templates", [])
        for tpl in templates:
            result = self._matcher.match(screenshot, tpl, threshold=0.7)
            if result is not None:
                score += 2.0 + result.confidence

        # OCR 文字匹配
        ocr_texts = features.get("ocr_texts", [])
        if ocr_texts:
            try:
                ocr_results = self._ocr.recognize(screenshot)
                ocr_text_all = " ".join(r.text for r in ocr_results)
                for target_text in ocr_texts:
                    if target_text in ocr_text_all:
                        score += 1.5
            except Exception as e:
                logger.warning(f"场景识别 OCR 异常: {e}")

        return score
