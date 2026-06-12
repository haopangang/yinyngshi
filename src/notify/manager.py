"""通知管理器

统一管理多个通知渠道，提供消息分发、频率限制、失败重试和内置消息模板。

核心功能：
- 根据 NotifyConfig 自动初始化通知渠道
- 多通道并行分发通知
- 同类消息 5 分钟内不重复发送（频率限制）
- 发送失败最多重试 2 次
- 内置任务完成、错误告警、日报格式化模板
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from loguru import logger

from src.notify.base import BaseNotifier, NotifyEvent

if TYPE_CHECKING:
    from src.config.models import NotifyChannelConfig, NotifyConfig
    from src.scheduler.monitor import RuntimeStats


# 频率限制：同类消息最小发送间隔（秒）
_RATE_LIMIT_SECONDS = 300  # 5 分钟

# 发送失败重试次数
_MAX_RETRY = 2


class NotifyManager:
    """通知管理器

    管理多个通知渠道的生命周期，统一分发消息，
    内置频率限制和重试机制。

    Attributes:
        _notifiers: 已配置的通知渠道列表
        _enabled_events: 已启用的事件类型集合
        _last_send_times: 频率限制记录（event -> 上次发送时间戳）

    Example:
        >>> manager = NotifyManager()
        >>> manager.init_from_config(notify_config)
        >>> manager.send(NotifyEvent.TASK_COMPLETE, "任务完成", "八岐大蛇 x10")
        >>> manager.send_daily_report(stats)
    """

    def __init__(self) -> None:
        """初始化通知管理器"""
        self._notifiers: list[BaseNotifier] = []
        self._enabled_events: set[str] = set()
        self._last_send_times: dict[str, float] = {}
        self._enabled: bool = False

        logger.info("NotifyManager 初始化完成")

    def init_from_config(self, config: NotifyConfig) -> None:
        """根据配置初始化通知渠道

        读取 NotifyConfig 中的 channels 列表，依次创建对应的通知器实例，
        并过滤掉未正确配置的渠道。

        Args:
            config: 通知配置（NotifyConfig），包含 channels 和 events 字段

        Example:
            >>> manager.init_from_config(app_config.notify)
        """
        self._enabled = config.enabled

        if not config.enabled:
            logger.info("通知系统未启用")
            return

        # 记录已启用的事件类型
        self._enabled_events = set(config.events)
        logger.info(f"已启用事件类型: {self._enabled_events}")

        # 初始化各通知渠道
        for channel_config in config.channels:
            notifier = self._create_notifier(channel_config)
            if notifier is not None and notifier.is_configured():
                self._notifiers.append(notifier)
                logger.info(f"通知渠道已就绪: {type(notifier).__name__}")
            else:
                logger.warning(
                    f"通知渠道配置不完整，跳过: {getattr(channel_config, 'type', 'unknown')}"
                )

        logger.info(f"通知管理器初始化完毕: {len(self._notifiers)} 个渠道就绪")

    # ------------------------------------------------------------------
    # 消息发送
    # ------------------------------------------------------------------

    def send(
        self,
        event: NotifyEvent,
        title: str,
        content: str,
    ) -> bool:
        """发送通知（分发到所有已配置渠道）

        内置频率限制：同类事件 5 分钟内不重复发送。
        同步接口，内部通过 asyncio.run() 调用异步发送。

        Args:
            event: 通知事件类型
            title: 通知标题
            content: 通知正文

        Returns:
            True 表示至少一个渠道发送成功

        Example:
            >>> manager.send(NotifyEvent.ERROR, "错误", "游戏崩溃")
        """
        if not self._enabled:
            logger.debug("通知系统未启用，跳过发送")
            return False

        if not self._notifiers:
            logger.warning("无可用通知渠道")
            return False

        # 检查事件类型是否启用
        if event.value not in self._enabled_events and self._enabled_events:
            logger.debug(f"事件类型 {event.value} 未启用，跳过")
            return False

        # 频率限制检查
        if self._is_rate_limited(event):
            logger.debug(f"频率限制: {event.value} 在 {_RATE_LIMIT_SECONDS}s 内已发送")
            return False

        # 确定消息类型
        msg_type = "error" if event == NotifyEvent.ERROR else "info"

        # 异步发送到所有渠道
        success = self._send_to_all(title, content, msg_type)

        # 更新发送时间
        if success:
            self._last_send_times[event.value] = time.time()

        return success

    def send_daily_report(self, stats: RuntimeStats) -> bool:
        """发送每日运行报告

        使用内置日报模板格式化统计数据并发送。

        Args:
            stats: RuntimeStats 运行统计数据实例

        Returns:
            True 表示发送成功
        """
        title = f"📊 每日运行报告 - {datetime.now().strftime('%Y-%m-%d')}"
        content = self._format_daily_report(stats)

        return self.send(NotifyEvent.DAILY_REPORT, title, content)

    def send_error_alert(self, error: str) -> bool:
        """发送错误告警通知

        使用内置错误模板格式化告警信息并发送。

        Args:
            error: 错误描述信息

        Returns:
            True 表示发送成功
        """
        title = "🚨 阴阳师助手 - 错误告警"
        content = self._format_error_alert(error)

        return self.send(NotifyEvent.ERROR, title, content)

    def send_task_complete(
        self,
        task_name: str,
        run_count: int,
        success: bool,
        elapsed_time: float,
    ) -> bool:
        """发送任务完成通知

        Args:
            task_name: 任务名称
            run_count: 执行次数
            success: 是否成功
            elapsed_time: 耗时（秒）

        Returns:
            True 表示发送成功
        """
        status = "✅ 成功" if success else "❌ 失败"
        title = f"任务完成: {task_name}"
        content = self._format_task_complete(task_name, status, run_count, elapsed_time)

        return self.send(NotifyEvent.TASK_COMPLETE, title, content)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _create_notifier(
        self, channel_config: NotifyChannelConfig
    ) -> Optional[BaseNotifier]:
        """根据渠道配置创建通知器实例

        Args:
            channel_config: 渠道配置

        Returns:
            通知器实例，创建失败返回 None
        """
        channel_type = getattr(channel_config, "type", "")

        if channel_type == "wxpusher":
            from src.notify.wechat import WxPusherNotifier

            return WxPusherNotifier(
                app_token=getattr(channel_config, "token", ""),
                uid=getattr(channel_config, "uid", ""),
            )

        elif channel_type == "serverchan":
            from src.notify.wechat import ServerChanNotifier

            return ServerChanNotifier(
                sendkey=getattr(channel_config, "token", ""),
            )

        elif channel_type == "wecom":
            from src.notify.wechat import WecomBotNotifier

            return WecomBotNotifier(
                webhook_url=getattr(channel_config, "url", ""),
            )

        elif channel_type == "webhook":
            from src.notify.webhook import WebhookNotifier

            return WebhookNotifier(
                url=getattr(channel_config, "url", ""),
            )

        else:
            logger.warning(f"未知的通知渠道类型: {channel_type}")
            return None

    def _is_rate_limited(self, event: NotifyEvent) -> bool:
        """检查是否触发频率限制

        Args:
            event: 通知事件类型

        Returns:
            True 表示被限流应跳过发送
        """
        last_time = self._last_send_times.get(event.value, 0)
        return (time.time() - last_time) < _RATE_LIMIT_SECONDS

    def _send_to_all(
        self,
        title: str,
        content: str,
        msg_type: str,
    ) -> bool:
        """异步发送通知到所有渠道（带重试）

        Args:
            title: 通知标题
            content: 通知内容
            msg_type: 消息类型

        Returns:
            True 表示至少一个渠道发送成功
        """
        any_success = False

        for notifier in self._notifiers:
            for attempt in range(_MAX_RETRY + 1):
                try:
                    success = asyncio.run(
                        notifier.send(title, content, msg_type)
                    )
                    if success:
                        any_success = True
                        break  # 成功则不再重试
                    else:
                        if attempt < _MAX_RETRY:
                            logger.warning(
                                f"发送失败，重试 [{attempt + 1}/{_MAX_RETRY}]: "
                                f"{type(notifier).__name__}"
                            )
                            time.sleep(1.0)
                except RuntimeError:
                    # 已有事件循环在运行，尝试 get_event_loop
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # 在已有循环中创建任务
                            import concurrent.futures

                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(
                                    asyncio.run,
                                    notifier.send(title, content, msg_type),
                                )
                                success = future.result(timeout=30.0)
                                if success:
                                    any_success = True
                                    break
                        else:
                            success = loop.run_until_complete(
                                notifier.send(title, content, msg_type)
                            )
                            if success:
                                any_success = True
                                break
                    except Exception as e:
                        logger.error(f"通知发送异常: {type(notifier).__name__} -> {e}")
                        break
                except Exception as e:
                    logger.error(f"通知发送异常: {type(notifier).__name__} -> {e}")
                    break

        return any_success

    # ------------------------------------------------------------------
    # 消息模板
    # ------------------------------------------------------------------

    @staticmethod
    def _format_daily_report(stats: RuntimeStats) -> str:
        """格式化每日报告

        Args:
            stats: 运行统计数据

        Returns:
            格式化的报告文本
        """
        lines = [
            f"📅 日期: {stats.report_date}",
            f"🔄 总执行: {stats.total_runs} 次",
            f"✅ 成功: {stats.success_count} 次",
            f"❌ 失败: {stats.error_count} 次",
            f"📈 成功率: {stats.success_rate:.1%}",
            "",
        ]

        if stats.task_details:
            lines.append("📋 任务详情:")
            for name, detail in stats.task_details.items():
                icon = "✅" if detail.last_success else "❌"
                lines.append(
                    f"  {icon} {name}: "
                    f"{detail.success_count}/{detail.total_runs} "
                    f"({detail.success_rate:.0%})"
                )

        return "\n".join(lines)

    @staticmethod
    def _format_error_alert(error: str) -> str:
        """格式化错误告警

        Args:
            error: 错误描述

        Returns:
            格式化的告警文本
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return (
            f"⏰ 时间: {now}\n"
            f"❌ 错误: {error}\n\n"
            f"请尽快检查设备状态和日志。"
        )

    @staticmethod
    def _format_task_complete(
        task_name: str,
        status: str,
        run_count: int,
        elapsed_time: float,
    ) -> str:
        """格式化任务完成通知

        Args:
            task_name: 任务名称
            status: 状态文本
            run_count: 执行次数
            elapsed_time: 耗时

        Returns:
            格式化的通知文本
        """
        return (
            f"📋 任务: {task_name}\n"
            f"📊 状态: {status}\n"
            f"🔄 次数: {run_count}\n"
            f"⏱️ 耗时: {elapsed_time:.1f}s"
        )

    @property
    def notifier_count(self) -> int:
        """已配置的通知渠道数量"""
        return len(self._notifiers)

    @property
    def is_enabled(self) -> bool:
        """通知系统是否启用"""
        return self._enabled
