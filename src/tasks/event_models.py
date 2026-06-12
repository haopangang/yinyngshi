"""活动模板 Pydantic 配置模型

定义活动 YAML 配置的校验模型，包括：
- EventConfig: 活动配置主模型
- StepConfig: 步骤配置
- StopCondition: 停止条件
- RemainingCount: 剩余次数配置
- EventLimits: 限制配置

所有活动 YAML 文件加载后必须通过此模型校验，确保配置合法。
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# 枚举定义
# ---------------------------------------------------------------------------

class ActionType(str, Enum):
    """步骤动作类型"""

    CLICK_TEMPLATE = "click_template"
    CLICK_POSITION = "click_position"
    WAIT_TEMPLATE = "wait_template"
    WAIT_TEMPLATE_DISAPPEAR = "wait_template_disappear"
    WAIT = "wait"
    SWIPE = "swipe"
    OCR_CHECK = "ocr_check"
    CLICK_OCR = "click_ocr"


class StopType(str, Enum):
    """停止条件类型"""

    COUNT_ZERO = "count_zero"
    TEMPLATE_MATCH = "template_match"
    BUTTON_DISABLED = "button_disabled"
    TIMEOUT = "timeout"


# ---------------------------------------------------------------------------
# 子模型
# ---------------------------------------------------------------------------

class EventLimits(BaseModel):
    """活动限制配置"""

    daily_count: int = Field(default=30, ge=0, description="每日最大执行次数")
    stamina_cost: int = Field(default=0, ge=0, description="每次执行消耗的体力值，0 表示不消耗")


class RemainingCount(BaseModel):
    """剩余次数识别配置（OCR 读取）"""

    enabled: bool = Field(default=True, description="是否启用剩余次数识别")
    roi: tuple[float, float, float, float] = Field(
        description="归一化坐标区域 (x1, y1, x2, y2)",
    )
    pattern: str = Field(
        description="正则表达式，用于从 OCR 文本中提取当前剩余次数",
    )


class StepConfig(BaseModel):
    """单步操作配置

    描述活动执行流程中的一个步骤，包括动作类型及相关参数。
    """

    action: ActionType = Field(description="动作类型")
    description: str = Field(default="", description="步骤描述（用于日志）")

    # click_template / wait_template / wait_template_disappear
    template: Optional[str] = Field(default=None, description="模板图片路径（相对于 assets/templates/）")
    threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="模板匹配阈值")
    region: Optional[tuple[float, float, float, float]] = Field(
        default=None, description="归一化区域坐标 (x1, y1, x2, y2)",
    )

    # click_template / wait_template
    wait: float = Field(default=1.0, ge=0.0, description="操作后等待秒数")
    timeout: float = Field(default=30.0, ge=0.0, description="等待模板出现/消失的超时秒数")

    # click_position
    x: Optional[float] = Field(default=None, description="点击 X 坐标（像素或归一化）")
    y: Optional[float] = Field(default=None, description="点击 Y 坐标（像素或归一化）")
    normalized: bool = Field(default=False, description="x/y 是否为归一化坐标 (0~1)")

    # swipe
    x1: Optional[float] = Field(default=None, description="滑动起点 X")
    y1: Optional[float] = Field(default=None, description="滑动起点 Y")
    x2: Optional[float] = Field(default=None, description="滑动终点 X")
    y2: Optional[float] = Field(default=None, description="滑动终点 Y")
    duration: float = Field(default=0.5, ge=0.0, description="滑动持续时间（秒）")

    # wait
    seconds: float = Field(default=1.0, ge=0.0, description="固定等待秒数")

    # ocr_check / click_ocr
    text: Optional[str] = Field(default=None, description="OCR 查找的目标文字")
    expect: Optional[str] = Field(default=None, description="OCR 期望匹配的值（用于 ocr_check 判断）")

    @field_validator("action", mode="before")
    @classmethod
    def _coerce_action(cls, v: str) -> str:
        """兼容 YAML 中大小写不一致的 action 名称"""
        return v.lower().replace("-", "_") if isinstance(v, str) else v


class StopCondition(BaseModel):
    """停止条件配置

    满足任一停止条件即终止活动循环。
    """

    type: StopType = Field(description="停止条件类型")
    template: Optional[str] = Field(default=None, description="模板图片路径")
    threshold: float = Field(default=0.85, ge=0.0, le=1.0, description="模板匹配阈值")
    minutes: int = Field(default=60, ge=1, description="超时保护（分钟）")

    @field_validator("type", mode="before")
    @classmethod
    def _coerce_type(cls, v: str) -> str:
        return v.lower().replace("-", "_") if isinstance(v, str) else v


class NavigationStep(BaseModel):
    """导航步骤配置"""

    action: ActionType = Field(description="动作类型")
    template: Optional[str] = Field(default=None, description="模板图片路径")
    threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="匹配阈值")
    wait: float = Field(default=1.0, ge=0.0, description="操作后等待秒数")
    x: Optional[float] = Field(default=None)
    y: Optional[float] = Field(default=None)
    normalized: bool = Field(default=False)

    @field_validator("action", mode="before")
    @classmethod
    def _coerce_action(cls, v: str) -> str:
        return v.lower().replace("-", "_") if isinstance(v, str) else v


# ---------------------------------------------------------------------------
# 主模型
# ---------------------------------------------------------------------------

class EventConfig(BaseModel):
    """活动配置主模型

    对应 config/events/ 下的 YAML 文件结构，加载后通过 pydantic 校验合法性。
    """

    name: str = Field(description="活动名称")
    description: str = Field(default="", description="活动描述")
    enabled: bool = Field(default=True, description="是否启用")

    start_date: Optional[date] = Field(default=None, description="活动开始日期")
    end_date: Optional[date] = Field(default=None, description="活动结束日期")

    limits: EventLimits = Field(default_factory=EventLimits, description="任务限制")
    remaining_count: Optional[RemainingCount] = Field(
        default=None, description="剩余次数识别配置",
    )
    stop_conditions: list[StopCondition] = Field(
        default_factory=list, description="停止条件列表（满足任一即停止）",
    )
    navigation: list[NavigationStep] = Field(
        default_factory=list, description="导航步骤列表",
    )
    steps: list[StepConfig] = Field(description="执行步骤列表")

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _parse_date(cls, v):
        """支持字符串日期解析"""
        if isinstance(v, str):
            return date.fromisoformat(v)
        return v
