"""
设备操作控制器

封装对 Android 设备的所有交互操作，包括：
- 点击（带随机偏移，模拟人类行为）
- 长按
- 滑动（支持直线和贝塞尔曲线轨迹）
- 文字输入
- 按键操作
- 随机延迟

所有操作均内置随机延迟与随机偏移，降低被反作弊系统识别的风险。
"""

from __future__ import annotations

import random
import time
from typing import Optional, Sequence, Tuple

import numpy as np
from loguru import logger

from src.device.adb_client import ADBClient
from src.utils.constants import (
    MAX_CLICK_DELAY,
    MAX_SWIPE_DURATION,
    MIN_CLICK_DELAY,
    MIN_SWIPE_DURATION,
)

# 点击随机偏移像素范围
_CLICK_OFFSET_MIN = 3
_CLICK_OFFSET_MAX = 5


class DeviceController:
    """
    设备操作控制器，提供对 Android 设备的各种交互操作。

    依赖 ADBClient 获取底层 uiautomator2 Device 实例。所有操作均内置
    随机延迟和随机偏移，模拟人类手指操作行为。

    Attributes:
        client: 底层 ADBClient 实例
        click_delay_range: 点击后随机延迟范围 (min_s, max_s)
    """

    def __init__(
        self,
        client: ADBClient,
        click_delay_range: Tuple[float, float] = (MIN_CLICK_DELAY, MAX_CLICK_DELAY),
    ) -> None:
        """
        初始化 DeviceController。

        Args:
            client: ADBClient 实例，需已完成设备连接
            click_delay_range: 每次操作后的随机延迟范围（秒），
                               默认 (MIN_CLICK_DELAY, MAX_CLICK_DELAY)
        """
        self.client: ADBClient = client
        self.click_delay_range: Tuple[float, float] = click_delay_range

    # ------------------------------------------------------------------
    # 点击操作
    # ------------------------------------------------------------------

    def click(
        self,
        x: int,
        y: int,
        *,
        offset: bool = True,
        delay: bool = True,
    ) -> None:
        """
        在指定坐标执行点击操作。

        默认加入 ±3~5px 的随机偏移以及操作后随机延迟，以模拟人类行为。

        Args:
            x: 目标 X 坐标（像素）
            y: 目标 Y 坐标（像素）
            offset: 是否加入随机坐标偏移，默认 True
            delay: 是否在操作后加入随机延迟，默认 True
        """
        if offset:
            dx = random.randint(-random.randint(_CLICK_OFFSET_MIN, _CLICK_OFFSET_MAX),
                                random.randint(_CLICK_OFFSET_MIN, _CLICK_OFFSET_MAX))
            dy = random.randint(-random.randint(_CLICK_OFFSET_MIN, _CLICK_OFFSET_MAX),
                                random.randint(_CLICK_OFFSET_MIN, _CLICK_OFFSET_MAX))
            x += dx
            y += dy

        logger.debug(f"点击: ({x}, {y})")
        self.client.device.click(x, y)

        if delay:
            self.random_delay()

    def click_center(
        self,
        region: Tuple[int, int, int, int],
        *,
        delay: bool = True,
    ) -> None:
        """
        点击指定区域的中心点。

        Args:
            region: 区域矩形 (x1, y1, x2, y2)，左上角为原点
            delay: 是否在操作后加入随机延迟，默认 True
        """
        x1, y1, x2, y2 = region
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        logger.debug(f"点击区域中心: region={region}, center=({cx}, {cy})")
        self.click(cx, cy, offset=True, delay=delay)

    def long_press(
        self,
        x: int,
        y: int,
        duration: float = 1.0,
        *,
        delay: bool = True,
    ) -> None:
        """
        在指定坐标执行长按操作。

        Args:
            x: 目标 X 坐标（像素）
            y: 目标 Y 坐标（像素）
            duration: 长按持续时间（秒），默认 1.0s
            delay: 是否在操作后加入随机延迟，默认 True
        """
        logger.debug(f"长按: ({x}, {y}), 持续 {duration}s")
        self.client.device.long_click(x, y, duration=duration)
        if delay:
            self.random_delay()

    # ------------------------------------------------------------------
    # 滑动操作
    # ------------------------------------------------------------------

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration: Optional[float] = None,
        *,
        delay: bool = True,
    ) -> None:
        """
        执行直线滑动操作。

        Args:
            x1: 起点 X 坐标
            y1: 起点 Y 坐标
            x2: 终点 X 坐标
            y2: 终点 Y 坐标
            duration: 滑动持续时间（秒）；为 None 则随机生成
            delay: 是否在操作后加入随机延迟，默认 True
        """
        if duration is None:
            duration = random.uniform(MIN_SWIPE_DURATION, MAX_SWIPE_DURATION) / 1000.0

        logger.debug(f"滑动: ({x1},{y1}) -> ({x2},{y2}), {duration:.2f}s")
        self.client.device.swipe(x1, y1, x2, y2, duration=duration)
        if delay:
            self.random_delay()

    def swipe_bezier(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        duration: Optional[float] = None,
        *,
        num_points: int = 40,
        delay: bool = True,
    ) -> None:
        """
        执行贝塞尔曲线滑动，模拟人类手指的真实滑动轨迹。

        在起点和终点之间随机生成 3~5 个控制点，构造贝塞尔曲线，
        然后按曲线轨迹逐步滑动。

        Args:
            start: 起点坐标 (x, y)
            end: 终点坐标 (x, y)
            duration: 滑动持续时间（秒）；为 None 则随机生成
            num_points: 贝塞尔曲线采样点数，默认 40
            delay: 是否在操作后加入随机延迟，默认 True
        """
        if duration is None:
            duration = random.uniform(MIN_SWIPE_DURATION, MAX_SWIPE_DURATION) / 1000.0

        # 生成随机控制点（3~5 个中间点）
        num_ctrl = random.randint(3, 5)
        ctrl_points = [start]
        sx, sy = start
        ex, ey = end
        for i in range(1, num_ctrl + 1):
            ratio = i / (num_ctrl + 1)
            # 控制点在起点到终点的连线上加入随机偏移
            jitter_x = random.randint(-80, 80)
            jitter_y = random.randint(-80, 80)
            cx = int(sx + (ex - sx) * ratio + jitter_x)
            cy = int(sy + (ey - sy) * ratio + jitter_y)
            ctrl_points.append((cx, cy))
        ctrl_points.append(end)

        # 计算贝塞尔曲线上的采样点
        points = self._bezier_points(ctrl_points, num_points)

        logger.debug(
            f"贝塞尔滑动: {start} -> {end}, {len(ctrl_points)} 控制点, "
            f"{num_points} 采样点, {duration:.2f}s"
        )

        # 逐步执行滑动
        step_delay = duration / max(len(points) - 1, 1)
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            self.client.device.swipe(
                int(x1), int(y1), int(x2), int(y2), duration=step_delay
            )

        if delay:
            self.random_delay()

    # ------------------------------------------------------------------
    # 输入与按键
    # ------------------------------------------------------------------

    def input_text(self, text: str, *, delay: bool = True) -> None:
        """
        在当前焦点输入框中输入文字。

        Args:
            text: 要输入的文字内容
            delay: 是否在操作后加入随机延迟，默认 True
        """
        logger.debug(f"输入文字: {text!r}")
        self.client.device.send_keys(text)
        if delay:
            self.random_delay()

    def press_key(self, key: str, *, delay: bool = True) -> None:
        """
        按下系统按键。

        支持的按键名称：
        - "home"：主页键
        - "back"：返回键
        - "recent"：最近任务键
        - "enter"：回车键
        - "delete"：删除键

        Args:
            key: 按键名称（不区分大小写）
            delay: 是否在操作后加入随机延迟，默认 True

        Raises:
            ValueError: 不支持的按键名称
        """
        key_map = {
            "home": "home",
            "back": "back",
            "recent": "recent",
            "enter": "enter",
            "delete": "delete",
        }
        key_lower = key.lower()
        if key_lower not in key_map:
            raise ValueError(
                f"不支持的按键: {key!r}，可选: {list(key_map.keys())}"
            )

        logger.debug(f"按键: {key_lower}")
        self.client.device.press(key_map[key_lower])
        if delay:
            self.random_delay()

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def random_delay(
        self,
        min_s: Optional[float] = None,
        max_s: Optional[float] = None,
    ) -> None:
        """
        随机休眠一段时间，模拟人类操作间隔。

        Args:
            min_s: 最小休眠秒数；为 None 则使用 click_delay_range[0]
            max_s: 最大休眠秒数；为 None 则使用 click_delay_range[1]
        """
        lo = min_s if min_s is not None else self.click_delay_range[0]
        hi = max_s if max_s is not None else self.click_delay_range[1]
        t = random.uniform(lo, hi)
        logger.debug(f"随机延迟: {t:.2f}s")
        time.sleep(t)

    # ------------------------------------------------------------------
    # 贝塞尔曲线计算
    # ------------------------------------------------------------------

    @staticmethod
    def _bezier_points(
        control_points: Sequence[Tuple[int, int]],
        num_points: int,
    ) -> list[Tuple[float, float]]:
        """
        计算贝塞尔曲线上的等间隔采样点。

        使用 de Casteljau 算法递归计算任意阶贝塞尔曲线。

        Args:
            control_points: 控制点序列 [(x, y), ...]
            num_points: 采样点数

        Returns:
            曲线上的采样点列表 [(x, y), ...]
        """
        pts = np.array(control_points, dtype=float)
        n = len(pts) - 1  # 阶数

        result = []
        for step in range(num_points + 1):
            t = step / num_points
            # de Casteljau 算法
            tmp = pts.copy()
            for k in range(1, n + 1):
                tmp[:n - k + 1] = (1 - t) * tmp[:n - k + 1] + t * tmp[1:n - k + 2]
            result.append((tmp[0][0], tmp[0][1]))

        return result
