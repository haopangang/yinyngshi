"""通知基类与事件枚举

定义通知系统的抽象接口和事件类型，所有通知渠道实现均需继承 BaseNotifier。

NotifyEvent 枚举定义了系统支持的所有通知事件类型，
用于通知管理器的消息分发和频率控制。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum


class NotifyEvent(str, Enum):
    """通知事件类型枚举

    定义系统支持的所有通知事件类型，用于消息分发和频率控制。

    Attributes:
        TASK_COMPLETE: 任务执行完成通知
        ERROR: 错误告警通知
        STAMINA_LOW: 体力不足通知
        DAILY_REPORT: 每日运行报告
    """

    TASK_COMPLETE = "task_complete"
    ERROR = "error"
    STAMINA_LOW = "stamina_low"
    DAILY_REPORT = "daily_report"


class BaseNotifier(ABC):
    """通知渠道抽象基类

    所有通知实现（微信、Webhook 等）必须继承此类，
    并实现 send() 和 is_configured() 两个抽象方法。

    Example:
        >>> class MyNotifier(BaseNotifier):
        ...     async def send(self, title, content, msg_type="info"):
        ...         # 发送逻辑
        ...         return True
        ...
        ...     def is_configured(self):
        ...         return self._api_key is not None
    """

    @abstractmethod
    async def send(
        self,
        title: str,
        content: str,
        msg_type: str = "info",
    ) -> bool:
        """发送通知消息

        Args:
            title: 通知标题
            content: 通知正文内容
            msg_type: 消息类型，可选 "info" / "warning" / "error"，
                      部分渠道可根据类型调整展示样式

        Returns:
            True 表示发送成功，False 表示发送失败
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """检查通知渠道是否已正确配置

        用于在初始化时验证必要的配置参数是否齐全。

        Returns:
            True 表示配置完整可以使用，False 表示配置不完整
        """
        pass
