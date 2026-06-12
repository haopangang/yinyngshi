"""微信通知渠道实现

提供三种微信推送方式：
1. WxPusher — 通过 WxPusher 平台推送到微信（需要 app_token + uid）
2. Server酱 — 通过 Server酱 推送到微信（需要 sendkey）
3. 企业微信机器人 — 通过企业微信 Webhook 推送（需要 webhook_url）

所有实现均使用 httpx 异步发送，支持超时和错误处理。
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from src.notify.base import BaseNotifier


class WxPusherNotifier(BaseNotifier):
    """WxPusher 微信推送通知

    通过 WxPusher API 向指定用户推送消息。

    API 文档: https://wxpusher.zjiecode.com/docs/

    Attributes:
        app_token: WxPusher 应用的 app_token
        uid: 接收消息的用户 UID

    Example:
        >>> notifier = WxPusherNotifier(app_token="xxx", uid="yyy")
        >>> if notifier.is_configured():
        ...     await notifier.send("任务完成", "八岐大蛇 x10 已完成")
    """

    _API_URL = "https://wxpusher.zjiecode.com/api/send/message"

    def __init__(self, app_token: str = "", uid: str = "") -> None:
        """初始化 WxPusher 通知器

        Args:
            app_token: WxPusher 应用的 app_token
            uid: 接收消息的用户 UID
        """
        self._app_token = app_token
        self._uid = uid

    async def send(
        self,
        title: str,
        content: str,
        msg_type: str = "info",
    ) -> bool:
        """通过 WxPusher 发送通知

        Args:
            title: 通知标题
            content: 通知正文（支持 HTML 格式）
            msg_type: 消息类型（"info" / "warning" / "error"）

        Returns:
            True 表示发送成功
        """
        import httpx

        # 根据消息类型选择内容类型
        content_type = 1  # 1=文本, 2=HTML, 3=Markdown
        full_content = f"**{title}**\n\n{content}"

        payload = {
            "appToken": self._app_token,
            "content": full_content,
            "summary": title,
            "contentType": content_type,
            "uids": [self._uid],
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self._API_URL, json=payload)
                response.raise_for_status()

                data = response.json()
                if data.get("code") == 1000:
                    logger.info(f"WxPusher 发送成功: {title}")
                    return True
                else:
                    logger.warning(f"WxPusher 发送失败: {data}")
                    return False

        except httpx.HTTPStatusError as e:
            logger.error(f"WxPusher HTTP 错误: {e.response.status_code}")
            return False
        except Exception as e:
            logger.error(f"WxPusher 发送异常: {e}")
            return False

    def is_configured(self) -> bool:
        """检查 WxPusher 配置是否完整

        Returns:
            True 表示 app_token 和 uid 均已配置
        """
        return bool(self._app_token and self._uid)


class ServerChanNotifier(BaseNotifier):
    """Server酱 微信推送通知

    通过 Server酱（方糖）API 推送消息到微信。

    API 文档: https://sct.ftqq.com/

    Attributes:
        sendkey: Server酱的 SendKey

    Example:
        >>> notifier = ServerChanNotifier(sendkey="SCTxxx")
        >>> await notifier.send("日报", "今日完成 15 个任务")
    """

    _API_TEMPLATE = "https://sctapi.ftqq.com/{sendkey}.send"

    def __init__(self, sendkey: str = "") -> None:
        """初始化 Server酱通知器

        Args:
            sendkey: Server酱 SendKey
        """
        self._sendkey = sendkey

    async def send(
        self,
        title: str,
        content: str,
        msg_type: str = "info",
    ) -> bool:
        """通过 Server酱发送通知

        Args:
            title: 通知标题（最长 100 字符）
            content: 通知正文（支持 Markdown）
            msg_type: 消息类型

        Returns:
            True 表示发送成功
        """
        import httpx

        url = self._API_TEMPLATE.format(sendkey=self._sendkey)

        payload = {
            "title": title[:100],  # Server酱限制标题长度
            "desp": content,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, data=payload)
                response.raise_for_status()

                data = response.json()
                if data.get("code") == 0:
                    logger.info(f"Server酱发送成功: {title}")
                    return True
                else:
                    logger.warning(f"Server酱发送失败: {data}")
                    return False

        except httpx.HTTPStatusError as e:
            logger.error(f"Server酱 HTTP 错误: {e.response.status_code}")
            return False
        except Exception as e:
            logger.error(f"Server酱发送异常: {e}")
            return False

    def is_configured(self) -> bool:
        """检查 Server酱配置是否完整

        Returns:
            True 表示 sendkey 已配置
        """
        return bool(self._sendkey)


class WecomBotNotifier(BaseNotifier):
    """企业微信机器人通知

    通过企业微信群机器人 Webhook 推送消息（Markdown 格式）。

    Attributes:
        webhook_url: 企业微信机器人 Webhook 地址

    Example:
        >>> notifier = WecomBotNotifier(webhook_url="https://qyapi.weixin.qq.com/...")
        >>> await notifier.send("告警", "游戏崩溃，正在恢复...")
    """

    def __init__(self, webhook_url: str = "") -> None:
        """初始化企业微信机器人通知器

        Args:
            webhook_url: 企业微信机器人 Webhook 地址
        """
        self._webhook_url = webhook_url

    async def send(
        self,
        title: str,
        content: str,
        msg_type: str = "info",
    ) -> bool:
        """通过企业微信机器人发送通知

        使用 Markdown 格式发送消息。

        Args:
            title: 通知标题
            content: 通知正文（支持 Markdown）
            msg_type: 消息类型，"error" 时使用红色提醒

        Returns:
            True 表示发送成功
        """
        import httpx

        # 构建 Markdown 内容
        if msg_type == "error":
            color = "warning"
            prefix = "🚨"
        elif msg_type == "warning":
            color = "warning"
            prefix = "⚠️"
        else:
            color = "info"
            prefix = "ℹ️"

        markdown_content = (
            f"## {prefix} {title}\n\n"
            f"{content}\n\n"
            f"<font color=\"comment\">来自阴阳师助手</font>"
        )

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": markdown_content,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self._webhook_url, json=payload)
                response.raise_for_status()

                data = response.json()
                if data.get("errcode") == 0:
                    logger.info(f"企业微信机器人发送成功: {title}")
                    return True
                else:
                    logger.warning(f"企业微信机器人发送失败: {data}")
                    return False

        except httpx.HTTPStatusError as e:
            logger.error(f"企业微信机器人 HTTP 错误: {e.response.status_code}")
            return False
        except Exception as e:
            logger.error(f"企业微信机器人发送异常: {e}")
            return False

    def is_configured(self) -> bool:
        """检查企业微信机器人配置是否完整

        Returns:
            True 表示 webhook_url 已配置
        """
        return bool(self._webhook_url)
