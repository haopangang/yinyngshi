"""
OpenCV 模板匹配引擎

提供单目标/多目标/区域/多尺度模板匹配功能。
使用 cv2.matchTemplate + TM_CCOEFF_NORMED 算法，支持 0.8x~1.2x 缩放适配不同分辨率。
模板图片加载后缓存在内存中，避免重复 IO。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from loguru import logger


@dataclass
class MatchResult:
    """模板匹配结果

    Attributes:
        x: 匹配区域左上角 x 坐标（像素）
        y: 匹配区域左上角 y 坐标（像素）
        width: 匹配区域宽度（像素）
        height: 匹配区域高度（像素）
        confidence: 匹配置信度 0~1
        center_x: 匹配区域中心 x 坐标（像素）
        center_y: 匹配区域中心 y 坐标（像素）
    """

    x: int
    y: int
    width: int
    height: int
    confidence: float

    @property
    def center_x(self) -> int:
        """匹配区域中心 x 坐标"""
        return self.x + self.width // 2

    @property
    def center_y(self) -> int:
        """匹配区域中心 y 坐标"""
        return self.y + self.height // 2

    def center(self) -> tuple[int, int]:
        """返回中心坐标 (x, y)"""
        return self.center_x, self.center_y

    def __repr__(self) -> str:
        return (
            f"MatchResult(x={self.x}, y={self.y}, "
            f"size={self.width}x{self.height}, "
            f"confidence={self.confidence:.3f}, "
            f"center=({self.center_x}, {self.center_y}))"
        )


class TemplateMatcher:
    """OpenCV 模板匹配引擎

    支持多尺度匹配（0.8x ~ 1.2x），模板缓存，ROI 区域匹配。

    Example:
        >>> matcher = TemplateMatcher()
        >>> result = matcher.match(screenshot, "assets/templates/common/start_btn.png")
        >>> if result:
        ...     print(f"Found at ({result.center_x}, {result.center_y})")
    """

    # 多尺度缩放因子
    SCALES = [0.8, 0.9, 1.0, 1.1, 1.2]

    def __init__(self, templates_dir: str | Path = "assets/templates") -> None:
        """初始化模板匹配引擎

        Args:
            templates_dir: 模板图片根目录路径
        """
        self._templates_dir = Path(templates_dir)
        self._cache: dict[str, np.ndarray] = {}
        logger.info(f"TemplateMatcher 初始化，模板目录: {self._templates_dir}")

    def _load_template(self, template_path: str) -> np.ndarray | None:
        """加载模板图片（带内存缓存）

        Args:
            template_path: 模板图片路径，相对于 templates_dir 或绝对路径

        Returns:
            BGR 格式的模板图像，加载失败返回 None
        """
        if template_path in self._cache:
            return self._cache[template_path]

        path = Path(template_path)
        if not path.is_absolute():
            path = self._templates_dir / path

        if not path.exists():
            logger.warning(f"模板文件不存在: {path}")
            return None

        template = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if template is None:
            logger.error(f"模板文件读取失败: {path}")
            return None

        self._cache[template_path] = template
        logger.debug(f"模板已加载并缓存: {template_path} ({template.shape[1]}x{template.shape[0]})")
        return template

    def clear_cache(self) -> None:
        """清除模板缓存"""
        self._cache.clear()
        logger.debug("模板缓存已清除")

    def _match_single_scale(
        self,
        screenshot: np.ndarray,
        template: np.ndarray,
        threshold: float,
        scale: float,
    ) -> MatchResult | None:
        """在指定缩放下执行单次模板匹配，返回最佳匹配

        Args:
            screenshot: 截图 BGR 图像
            template: 模板 BGR 图像
            threshold: 匹配阈值
            scale: 缩放因子

        Returns:
            最佳匹配结果，未找到返回 None
        """
        if scale != 1.0:
            h, w = template.shape[:2]
            new_w = int(w * scale)
            new_h = int(h * scale)
            scaled_template = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        else:
            scaled_template = template

        th, tw = scaled_template.shape[:2]
        sh, sw = screenshot.shape[:2]

        if th > sh or tw > sw:
            return None

        result = cv2.matchTemplate(screenshot, scaled_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            return MatchResult(
                x=int(max_loc[0]),
                y=int(max_loc[1]),
                width=tw,
                height=th,
                confidence=float(max_val),
            )
        return None

    def match(
        self,
        screenshot: np.ndarray,
        template_path: str,
        threshold: float = 0.8,
    ) -> MatchResult | None:
        """在截图中查找指定模板图片（多尺度，取最佳）

        Args:
            screenshot: BGR 格式截图
            template_path: 模板图片路径
            threshold: 匹配阈值 0~1，默认 0.8

        Returns:
            最佳匹配结果，未找到返回 None
        """
        template = self._load_template(template_path)
        if template is None:
            return None

        best: MatchResult | None = None
        for scale in self.SCALES:
            result = self._match_single_scale(screenshot, template, threshold, scale)
            if result is not None:
                if best is None or result.confidence > best.confidence:
                    best = result

        if best:
            logger.debug(f"模板匹配成功: {template_path} -> {best}")
        else:
            logger.debug(f"模板匹配失败: {template_path} (threshold={threshold})")
        return best

    def match_multi(
        self,
        screenshot: np.ndarray,
        template_path: str,
        threshold: float = 0.8,
        max_count: int = 10,
    ) -> list[MatchResult]:
        """在截图中查找多个匹配目标

        使用非极大值抑制（NMS）去除重叠框。

        Args:
            screenshot: BGR 格式截图
            template_path: 模板图片路径
            threshold: 匹配阈值
            max_count: 最大返回数量

        Returns:
            匹配结果列表，按置信度降序排列
        """
        template = self._load_template(template_path)
        if template is None:
            return []

        all_results: list[MatchResult] = []

        for scale in self.SCALES:
            if scale != 1.0:
                h, w = template.shape[:2]
                scaled_template = cv2.resize(
                    template,
                    (int(w * scale), int(h * scale)),
                    interpolation=cv2.INTER_LINEAR,
                )
            else:
                scaled_template = template

            th, tw = scaled_template.shape[:2]
            sh, sw = screenshot.shape[:2]
            if th > sh or tw > sw:
                continue

            result_map = cv2.matchTemplate(screenshot, scaled_template, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result_map >= threshold)

            for pt_y, pt_x in zip(*locations):
                all_results.append(
                    MatchResult(
                        x=int(pt_x),
                        y=int(pt_y),
                        width=tw,
                        height=th,
                        confidence=float(result_map[pt_y, pt_x]),
                    )
                )

        # 非极大值抑制（简单版：按置信度排序后去除重叠框）
        results = self._nms(all_results, overlap_thresh=0.5)
        results.sort(key=lambda r: r.confidence, reverse=True)
        results = results[:max_count]

        logger.debug(f"多目标匹配: {template_path} -> 找到 {len(results)} 个")
        return results

    @staticmethod
    def _nms(results: list[MatchResult], overlap_thresh: float = 0.5) -> list[MatchResult]:
        """简单非极大值抑制，去除重叠匹配框

        Args:
            results: 候选匹配结果列表
            overlap_thresh: IoU 重叠阈值

        Returns:
            抑制后的匹配结果列表
        """
        if not results:
            return []

        boxes = np.array([[r.x, r.y, r.x + r.width, r.y + r.height] for r in results], dtype=np.float32)
        scores = np.array([r.confidence for r in results], dtype=np.float32)

        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]

        keep: list[int] = []
        while order.size > 0:
            i = order[0]
            keep.append(i)

            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h
            iou = inter / (areas[i] + areas[order[1:]] - inter)

            inds = np.where(iou <= overlap_thresh)[0]
            order = order[inds + 1]

        return [results[i] for i in keep]

    def match_in_region(
        self,
        screenshot: np.ndarray,
        template_path: str,
        region: tuple[float, float, float, float],
        threshold: float = 0.8,
    ) -> MatchResult | None:
        """在指定 ROI 区域内查找模板

        Args:
            screenshot: BGR 格式截图
            template_path: 模板图片路径
            region: 归一化区域坐标 (x1, y1, x2, y2)，取值 0~1
            threshold: 匹配阈值

        Returns:
            匹配结果（坐标已换算回全图坐标），未找到返回 None
        """
        h, w = screenshot.shape[:2]
        rx1 = int(region[0] * w)
        ry1 = int(region[1] * h)
        rx2 = int(region[2] * w)
        ry2 = int(region[3] * h)

        # 边界保护
        rx1 = max(0, min(rx1, w))
        ry1 = max(0, min(ry1, h))
        rx2 = max(0, min(rx2, w))
        ry2 = max(0, min(ry2, h))

        if rx2 <= rx1 or ry2 <= ry1:
            logger.warning(f"无效 ROI 区域: {region}")
            return None

        roi = screenshot[ry1:ry2, rx1:rx2]
        result = self.match(roi, template_path, threshold)

        if result is not None:
            # 换算回全图坐标
            result.x += rx1
            result.y += ry1
            logger.debug(f"区域匹配成功: {template_path} in region {region} -> {result}")

        return result

    def match_best(
        self,
        screenshot: np.ndarray,
        template_paths: list[str],
        threshold: float = 0.8,
    ) -> tuple[str, MatchResult] | None:
        """多模板匹配，返回置信度最高的模板及其匹配结果

        Args:
            screenshot: BGR 格式截图
            template_paths: 模板图片路径列表
            threshold: 匹配阈值

        Returns:
            (模板路径, 匹配结果) 元组，无匹配返回 None
        """
        best_path: str | None = None
        best_result: MatchResult | None = None

        for path in template_paths:
            result = self.match(screenshot, path, threshold)
            if result is not None:
                if best_result is None or result.confidence > best_result.confidence:
                    best_path = path
                    best_result = result

        if best_path and best_result:
            logger.debug(f"多模板最佳匹配: {best_path} -> {best_result}")
            return best_path, best_result

        logger.debug("多模板匹配: 未找到任何匹配")
        return None
