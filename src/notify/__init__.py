"""通知系统模块

提供多渠道消息推送能力，支持：
- BaseNotifier: 通知渠道抽象基类
- NotifyEvent: 通知事件类型枚举
- WxPusherNotifier: WxPusher 微信推送
- ServerChanNotifier: Server酱微信推送
- WecomBotNotifier: 企业微信机器人推送
- WebhookNotifier: 通用 Webhook 推送
- NotifyManager: 多通道通知管理器（频率限制 + 重试 + 模板）
"""

from src.notify.base import BaseNotifier, NotifyEvent
from src.notify.manager import NotifyManager
from src.notify.webhook import WebhookNotifier
from src.notify.wechat import ServerChanNotifier, WecomBotNotifier, WxPusherNotifier

__all__ = [
    "BaseNotifier",
    "NotifyEvent",
    "NotifyManager",
    "WxPusherNotifier",
    "ServerChanNotifier",
    "WecomBotNotifier",
    "WebhookNotifier",
]
