"""活动模板引擎 — EventTemplateTask + StepInterpreter

基于 YAML 配置驱动的活动执行引擎：
- EventTemplateTask: 继承 BaseTask，加载 YAML 配置并执行活动流程
- StepInterpreter: 步骤解释器，将 StepConfig 转换为具体的设备/视觉操作

支持的 action 类型：
- click_template: 识别模板图片并点击
- click_position: 点击指定坐标
- wait_template: 等待某个模板出现
- wait_template_disappear: 等待某个模板消失
- wait: 固定等待
- swipe: 滑动操作
- ocr_check: OCR 读取文字并判断
- click_ocr: 识别文字并点击
"""

from __future__ import annotations

import re
import time
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import yaml
from loguru import logger

from src.tasks.base import BaseTask, TaskResult
from src.tasks.event_models import (
    ActionType,
    EventConfig,
    NavigationStep,
    StepConfig,
    StopCondition,
    StopType,
)

if TYPE_CHECKING:
    from src.device.controller import DeviceController
    from src.device.screen import ScreenCapture
    from src.vision.finder import VisionFinder


# ---------------------------------------------------------------------------
# 步骤解释器
# ---------------------------------------------------------------------------

class StepInterpreter:
    """步骤解释器

    将 StepConfig / NavigationStep 中的声明式配置翻译为具体的
    设备操作（DeviceController）和视觉查询（VisionFinder）调用。

    Attributes:
        device: 设备控制器
        vision: 视觉查找器
        screen: 截图管理器
    """

    def __init__(
        self,
        device: DeviceController,
        vision: VisionFinder,
        screen: ScreenCapture,
    ) -> None:
        self.device = device
        self.vision = vision
        self.screen = screen

    # ------------------------------------------------------------------
    # 执行单步
    # ------------------------------------------------------------------

    def execute_step(self, step: StepConfig | NavigationStep) -> bool:
        """执行单个步骤

        根据 step.action 分发到对应的处理方法。

        Args:
            step: 步骤配置对象

        Returns:
            True 表示步骤执行成功，False 表示失败
        """
        action = step.action
        desc = getattr(step, "description", "") or action.value
        logger.info(f"  执行步骤: [{action.value}] {desc}")

        handler = self._ACTION_MAP.get(action)
        if handler is None:
            logger.error(f"  未知的 action 类型: {action}")
            return False

        return handler(self, step)

    # ------------------------------------------------------------------
    # action 处理器
    # ------------------------------------------------------------------

    def _handle_click_template(self, step: StepConfig | NavigationStep) -> bool:
        """识别模板图片并点击"""
        if not step.template:
            logger.error("  click_template 缺少 template 参数")
            return False

        result = self.vision.wait_image(
            step.template,
            timeout=step.timeout if hasattr(step, "timeout") else 10.0,
            threshold=step.threshold,
            region=step.region if hasattr(step, "region") else None,
        )
        if result is None:
            logger.warning(f"  未找到模板: {step.template}")
            return False

        self.device.click(result.center_x, result.center_y)
        time.sleep(step.wait)
        return True

    def _handle_click_position(self, step: StepConfig | NavigationStep) -> bool:
        """点击指定坐标"""
        if step.x is None or step.y is None:
            logger.error("  click_position 缺少 x/y 参数")
            return False

        px, py = int(step.x), int(step.y)

        # 归一化坐标 → 像素坐标
        if getattr(step, "normalized", False):
            w, h = self.screen.get_screen_size()
            px = int(step.x * w)
            py = int(step.y * h)

        self.device.click(px, py)
        time.sleep(step.wait)
        return True

    def _handle_wait_template(self, step: StepConfig | NavigationStep) -> bool:
        """等待模板出现"""
        if not step.template:
            logger.error("  wait_template 缺少 template 参数")
            return False

        result = self.vision.wait_image(
            step.template,
            timeout=step.timeout if hasattr(step, "timeout") else 30.0,
            threshold=step.threshold,
            region=step.region if hasattr(step, "region") else None,
        )
        if result is None:
            return False

        time.sleep(step.wait)
        return True

    def _handle_wait_template_disappear(self, step: StepConfig) -> bool:
        """等待模板消失"""
        if not step.template:
            logger.error("  wait_template_disappear 缺少 template 参数")
            return False

        timeout = step.timeout
        interval = 0.5
        start = time.time()

        while time.time() - start < timeout:
            result = self.vision.find_image(
                step.template,
                threshold=step.threshold,
                region=step.region,
            )
            if result is None:
                logger.info(f"  模板已消失: {step.template}")
                time.sleep(step.wait)
                return True
            time.sleep(interval)

        logger.warning(f"  等待模板消失超时: {step.template} ({timeout}s)")
        return False

    def _handle_wait(self, step: StepConfig) -> bool:
        """固定等待"""
        time.sleep(step.seconds)
        return True

    def _handle_swipe(self, step: StepConfig) -> bool:
        """滑动操作"""
        if any(v is None for v in (step.x1, step.y1, step.x2, step.y2)):
            logger.error("  swipe 缺少 x1/y1/x2/y2 参数")
            return False

        sx1, sy1, sx2, sy2 = int(step.x1), int(step.y1), int(step.x2), int(step.y2)

        # 归一化坐标
        if getattr(step, "normalized", False):
            w, h = self.screen.get_screen_size()
            sx1, sy1 = int(step.x1 * w), int(step.y1 * h)
            sx2, sy2 = int(step.x2 * w), int(step.y2 * h)

        self.device.swipe(sx1, sy1, sx2, sy2, duration=step.duration)
        time.sleep(step.wait)
        return True

    def _handle_ocr_check(self, step: StepConfig) -> bool:
        """OCR 读取文字并判断"""
        if not step.text:
            logger.error("  ocr_check 缺少 text 参数")
            return False

        result = self.vision.find_text(
            step.text,
            region=step.region,
        )
        if result is None:
            logger.warning(f"  OCR 未找到文字: {step.text}")
            return False

        # 如果有 expect 字段，检查识别结果是否匹配
        if step.expect:
            if step.expect not in result.text:
                logger.warning(
                    f"  OCR 文字不匹配: 期望包含 '{step.expect}'，实际 '{result.text}'"
                )
                return False

        logger.info(f"  OCR 检查通过: '{result.text}'")
        return True

    def _handle_click_ocr(self, step: StepConfig) -> bool:
        """识别文字并点击"""
        if not step.text:
            logger.error("  click_ocr 缺少 text 参数")
            return False

        result = self.vision.find_text(
            step.text,
            region=step.region,
        )
        if result is None:
            logger.warning(f"  OCR 未找到文字: {step.text}")
            return False

        self.device.click(result.center_x, result.center_y)
        time.sleep(step.wait)
        return True

    # 分发表
    _ACTION_MAP: dict[ActionType, Any] = {
        ActionType.CLICK_TEMPLATE: _handle_click_template,
        ActionType.CLICK_POSITION: _handle_click_position,
        ActionType.WAIT_TEMPLATE: _handle_wait_template,
        ActionType.WAIT_TEMPLATE_DISAPPEAR: _handle_wait_template_disappear,
        ActionType.WAIT: _handle_wait,
        ActionType.SWIPE: _handle_swipe,
        ActionType.OCR_CHECK: _handle_ocr_check,
        ActionType.CLICK_OCR: _handle_click_ocr,
    }


# ---------------------------------------------------------------------------
# 活动模板任务
# ---------------------------------------------------------------------------

class EventTemplateTask(BaseTask):
    """活动模板任务

    基于 YAML 配置驱动的活动执行任务。加载 YAML 配置后，通过
    StepInterpreter 逐步解释并执行配置中定义的操作。

    生命周期：
    - pre_check: 校验配置合法性 + 检查前置条件（体力、有效期等）
    - navigate: 执行 navigation 步骤列表
    - run: 循环执行 steps 步骤列表，并在每轮开始前检测停止条件
    - cleanup: 返回主界面

    Attributes:
        event_config: 解析后的 EventConfig 配置对象
        interpreter: 步骤解释器实例
    """

    name = "活动模板"
    priority = 8
    stamina_cost = 0

    def __init__(
        self,
        device: DeviceController,
        vision: VisionFinder,
        screen: ScreenCapture,
        config: dict[str, Any],
        event_config: EventConfig | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        """初始化活动模板任务

        Args:
            device: 设备控制器
            vision: 视觉查找器
            screen: 截图管理器
            config: 任务配置字典（兼容 BaseTask 接口）
            event_config: 已解析的活动配置对象（优先使用）
            config_path: YAML 配置文件路径（event_config 为 None 时加载）
        """
        # 解析活动配置
        if event_config is not None:
            self.event_config = event_config
        elif config_path is not None:
            self.event_config = self._load_yaml(config_path)
        else:
            raise ValueError("必须提供 event_config 或 config_path 之一")

        # 从活动配置中同步属性到 BaseTask
        self.name = self.event_config.name
        self.stamina_cost = self.event_config.limits.stamina_cost

        super().__init__(device=device, vision=vision, screen=screen, config=config)

        # 步骤解释器
        self.interpreter = StepInterpreter(device, vision, screen)

        # 内部状态
        self._loop_count = 0
        self._run_start_time: float = 0.0
        self._timeout_minutes: int = self._resolve_timeout()

        logger.info(
            f"活动模板任务初始化: {self.event_config.name} "
            f"(steps={len(self.event_config.steps)}, "
            f"stops={len(self.event_config.stop_conditions)})"
        )

    # ------------------------------------------------------------------
    # 配置加载
    # ------------------------------------------------------------------

    @staticmethod
    def _load_yaml(path: str | Path) -> EventConfig:
        """从 YAML 文件加载并校验活动配置

        Args:
            path: YAML 文件路径

        Returns:
            校验后的 EventConfig 对象

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 配置校验失败
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"活动配置文件不存在: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            raise ValueError(f"活动配置文件格式错误: {path}")

        return EventConfig(**raw)

    # ------------------------------------------------------------------
    # 生命周期方法
    # ------------------------------------------------------------------

    def pre_check(self) -> bool:
        """前置条件检查

        校验项：
        1. 活动是否启用
        2. 活动是否在有效期内
        3. 体力是否充足（如果配置了 stamina_cost）
        """
        cfg = self.event_config

        # 检查启用状态
        if not cfg.enabled:
            logger.info(f"活动 {cfg.name} 已禁用，跳过")
            return False

        # 检查有效期
        today = date.today()
        if cfg.start_date and today < cfg.start_date:
            logger.info(f"活动 {cfg.name} 尚未开始 ({cfg.start_date})")
            return False
        if cfg.end_date and today > cfg.end_date:
            logger.info(f"活动 {cfg.name} 已过期 ({cfg.end_date})")
            return False

        # 检查体力
        if cfg.limits.stamina_cost > 0:
            if not self.check_stamina(cfg.limits.stamina_cost):
                logger.warning(f"活动 {cfg.name} 体力不足")
                return False

        logger.info(f"活动 {cfg.name} 前置检查通过")
        return True

    def navigate(self) -> bool:
        """执行导航步骤列表

        按照 navigation 配置逐步导航到活动入口界面。

        Returns:
            True 表示导航成功
        """
        if not self.event_config.navigation:
            logger.info(f"活动 {self.event_config.name} 无导航步骤")
            return True

        logger.info(f"开始导航: {self.event_config.name} ({len(self.event_config.navigation)} 步)")

        for i, nav_step in enumerate(self.event_config.navigation):
            desc = f"[{i + 1}/{len(self.event_config.navigation)}] {nav_step.action.value}"
            logger.debug(f"  导航步骤 {desc}")

            if not self.interpreter.execute_step(nav_step):
                logger.error(f"  导航步骤失败: {desc}")
                return False

        logger.info(f"导航完成: {self.event_config.name}")
        return True

    def run(self) -> TaskResult:
        """执行活动主循环

        循环执行 steps 步骤列表，每轮开始前检测停止条件。

        Returns:
            TaskResult 包含执行结果
        """
        cfg = self.event_config
        self._run_start_time = time.time()
        self._loop_count = 0

        logger.info(f"开始执行活动: {cfg.name} (最大次数={cfg.limits.daily_count})")

        while True:
            # 检查停止条件
            stop_reason = self._check_stop_conditions()
            if stop_reason:
                logger.info(f"活动停止: {cfg.name} — 原因: {stop_reason}")
                break

            # 检查最大执行次数
            if self._loop_count >= cfg.limits.daily_count:
                logger.info(f"活动达到最大次数限制: {cfg.name} ({cfg.limits.daily_count})")
                break

            # 执行一轮步骤
            logger.info(f"--- 第 {self._loop_count + 1}/{cfg.limits.daily_count} 轮 ---")
            success = self._execute_steps(cfg.steps)
            self._loop_count += 1

            if not success:
                logger.warning(f"活动步骤执行失败: {cfg.name} (第 {self._loop_count} 轮)")
                self._error_count += 1
                # 尝试恢复
                if not self._try_recover():
                    break

        elapsed = time.time() - self._run_start_time
        return TaskResult(
            success=True,
            run_count=self._loop_count,
            error_count=self._error_count,
            elapsed_time=elapsed,
            details={"event": cfg.name},
        )

    def on_error(self, error: Exception) -> bool:
        """异常处理"""
        logger.error(f"活动 {self.event_config.name} 发生错误: {error}")
        return False

    def cleanup(self) -> None:
        """清理：返回主界面"""
        logger.debug(f"活动 {self.event_config.name} 清理")
        self.go_to_main()

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _execute_steps(self, steps: list[StepConfig]) -> bool:
        """执行一轮步骤列表

        Args:
            steps: 步骤配置列表

        Returns:
            True 表示全部步骤成功
        """
        for i, step in enumerate(steps):
            desc = f"[{i + 1}/{len(steps)}] {step.action.value}"
            if step.description:
                desc += f" — {step.description}"

            if not self.interpreter.execute_step(step):
                logger.warning(f"  步骤失败: {desc}")
                return False

        return True

    def _check_stop_conditions(self) -> str | None:
        """检测所有停止条件

        在每轮循环开始前调用，任一条件满足即返回停止原因。

        Returns:
            停止原因字符串，None 表示不应停止
        """
        cfg = self.event_config

        for cond in cfg.stop_conditions:
            reason = self._evaluate_stop_condition(cond)
            if reason:
                return reason

        return None

    def _evaluate_stop_condition(self, cond: StopCondition) -> str | None:
        """评估单个停止条件

        Args:
            cond: 停止条件配置

        Returns:
            停止原因字符串，None 表示条件不满足
        """
        if cond.type == StopType.COUNT_ZERO:
            return self._check_count_zero()

        if cond.type == StopType.TEMPLATE_MATCH:
            return self._check_template_match(cond)

        if cond.type == StopType.BUTTON_DISABLED:
            return self._check_button_disabled(cond)

        if cond.type == StopType.TIMEOUT:
            return self._check_timeout(cond)

        return None

    def _check_count_zero(self) -> str | None:
        """检查 OCR 剩余次数是否为 0"""
        rc = self.event_config.remaining_count
        if rc is None or not rc.enabled:
            return None

        screenshot = self.screen.capture_cached()
        if screenshot is None:
            return None

        results = self.vision.ocr.recognize(screenshot, region=rc.roi)
        for text_result in results:
            match = re.search(rc.pattern, text_result.text)
            if match:
                try:
                    remaining = int(match.group(1))
                    if remaining <= 0:
                        return f"剩余次数为 0 (OCR: '{text_result.text}')"
                    logger.debug(f"  剩余次数: {remaining}")
                    return None
                except (ValueError, IndexError):
                    continue

        return None

    def _check_template_match(self, cond: StopCondition) -> str | None:
        """检查是否匹配到停止模板（如"次数用完"弹窗）"""
        if not cond.template:
            return None

        if self.vision.exists(cond.template, threshold=cond.threshold):
            return f"检测到停止模板: {cond.template}"
        return None

    def _check_button_disabled(self, cond: StopCondition) -> str | None:
        """检查按钮是否变灰"""
        if not cond.template:
            return None

        if self.vision.exists(cond.template, threshold=cond.threshold):
            return f"检测到按钮变灰: {cond.template}"
        return None

    def _check_timeout(self, cond: StopCondition) -> str | None:
        """检查超时保护"""
        elapsed_minutes = (time.time() - self._run_start_time) / 60.0
        if elapsed_minutes >= cond.minutes:
            return f"超时保护: {elapsed_minutes:.1f}min >= {cond.minutes}min"
        return None

    def _resolve_timeout(self) -> int:
        """从停止条件中提取超时分钟数"""
        for cond in self.event_config.stop_conditions:
            if cond.type == StopType.TIMEOUT:
                return cond.minutes
        return 60  # 默认 60 分钟

    def _try_recover(self) -> bool:
        """尝试从步骤执行失败中恢复

        策略：点击屏幕中心 + 短等待，看是否能恢复正常界面。

        Returns:
            True 表示恢复成功可继续
        """
        logger.info("尝试恢复...")
        w, h = self.screen.get_screen_size()
        self.device.click(w // 2, h // 2, offset=False, delay=False)
        time.sleep(1.5)
        return True
