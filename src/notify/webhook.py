"""通用 Webhook 通知渠道

支持自定义 URL、请求头和请求体模板的通用 Webhook 推送，
适用于任意支持 HTTP POST 的外部服务集成（如飞书、钉钉、IFTTT 等）。

使用 httpx 异步发送 JSON 格式请求。
"""

from __future__ import annotations

from typing import Any, Optional

from loguru import logger

from src.notify.base import BaseNotifier


class WebhookNotifier(BaseNotifier):
    """通用 Webhook 通知器

    支持完全自定义的 HTTP POST Webhook 推送，
    可配置 URL、请求头和请求体模板。

    请求体默认 JSON 格式，支持 {title}、{content}、{msg_type} 占位符替换。

    Attributes:
        _url: Webhook 目标 URL
        _headers: 自定义请求头
        _body_template: 请求体模板字典

    Example:
        >>> notifier = WebhookNotifier(
        ...     url="https://hooks.example.com/notify",
        ...     headers={"Authorization": "Bearer xxx"},
        ...     body_template={"text": "{title}\\n{content}"}
        ... )
        >>> await notifier.send("任务完成", "八岐大蛇 x10")
    """

    def __init__(
        self,
        url: str = "",
        headers: Optional[dict[str, str]] = None,
        body_template: Optional[dict[str, Any]] = None,
    ) -> None:
        """初始化通用 Webhook 通知器

        Args:
            url: Webhook 目标 URL
            headers: 自定义 HTTP 请求头字典（如认证 Token）
            body_template: 请求体模板字典，支持 {title}、{content}、{msg_type} 占位符；
                           为 None 时使用默认模板 {"title": ..., "content": ..., "type": ...}
        """
        self._url = url
        self._headers = headers or {}
        self._body_template = body_template

        # 确保 Content-Type 为 JSON
        if "Content-Type" not in self._headers and "content-type" not in self._headers:
            self._headers["Content-Type"] = "application/json"

    async def send(
        self,
        title: str,
        content: str,
        msg_type: str = "info",
    ) -> bool:
        """通过 Webhook 发送通知

        将 title、content、msg_type 填充到请求体模板中，
        以 JSON 格式 POST 到目标 URL。

        Args:
            title: 通知标题
            content: 通知正文
            msg_type: 消息类型（"info" / "warning" / "error"）

        Returns:
            True 表示发送成功（HTTP 2xx），False 表示发送失败
        """
        import httpx

        if not self._url:
            logger.warning("Webhook URL 未配置")
            return False

        # 构建请求体
        if self._body_template:
            payload = self._render_template(
                self._body_template,
                title=title,
                content=content,
                msg_type=msg_type,
            )
        else:
            payload = {
                "title": title,
                "content": content,
                "type": msg_type,
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self._url,
                    json=payload,
                    headers=self._headers,
                )
                response.raise_for_status()

                logger.info(f"Webhook 发送成功: {title} -> {self._url}")
                return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Webhook HTTP 错误: {e.response.status_code} "
                f"-> {e.response.text[:200]}"
            )
            return False
        except Exception as e:
            logger.error(f"Webhook 发送异常: {e}")
            return False

    def is_configured(self) -> bool:
        """检查 Webhook 是否已配置

        Returns:
            True 表示 URL 已配置
        """
        return bool(self._url)

    @staticmethod
    def _render_template(
        template: dict[str, Any],
        title: str,
        content: str,
        msg_type: str,
    ) -> dict[str, Any]:
        """渲染请求体模板

        递归替换模板中的 {title}、{content}、{msg_type} 占位符。

        Args:
            template: 模板字典
            title: 标题值
            content: 内容值
            msg_type: 消息类型值

        Returns:
            替换占位符后的字典
        """
        rendered: dict[str, Any] = {}
        replacements = {
            "{title}": title,
            "{content}": content,
            "{msg_type}": msg_type,
        }

        for key, value in template.items():
            if isinstance(value, str):
                rendered[key] = value
                for placeholder, replacement in replacements.items():
                    rendered[key] = rendered[key].replace(placeholder, replacement)
            elif isinstance(value, dict):
                rendered[key] = WebhookNotifier._render_template(
                    value, title, content, msg_type
                )
            else:
                rendered[key] = value

        return rendered
