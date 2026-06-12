# 通知系统 (src/notify/)

多渠道消息推送系统，支持微信、企业微信和通用 Webhook，内置频率限制和消息模板。

## 模块结构

| 文件 | 类 | 说明 |
|------|-----|------|
| `base.py` | `BaseNotifier`, `NotifyEvent` | 通知抽象基类和事件枚举 |
| `wechat.py` | `WxPusherNotifier`, `ServerChanNotifier`, `WecomBotNotifier` | 三种微信推送方式 |
| `webhook.py` | `WebhookNotifier` | 通用 Webhook 推送（支持自定义模板） |
| `manager.py` | `NotifyManager` | 多通道管理器（频率限制 + 重试 + 模板） |

## 支持的通知渠道

| 渠道 | 类型标识 | 必要配置 |
|------|----------|----------|
| WxPusher | `wxpusher` | `token` (app_token) + `uid` |
| Server酱 | `serverchan` | `token` (sendkey) |
| 企业微信机器人 | `wecom` | `url` (webhook_url) |
| 通用 Webhook | `webhook` | `url` |

## 通知事件类型

- `task_complete` — 任务执行完成
- `error` — 错误告警
- `stamina_low` — 体力不足
- `daily_report` — 每日运行报告

## 快速使用

```python
from src.notify import NotifyManager, NotifyEvent

# 初始化
manager = NotifyManager()
manager.init_from_config(notify_config)

# 发送通知
manager.send(NotifyEvent.TASK_COMPLETE, "任务完成", "八岐大蛇 x10")
manager.send_error_alert("游戏崩溃，正在恢复...")
manager.send_daily_report(runtime_stats)
```

## 特性

- **频率限制**: 同类消息 5 分钟内不重复发送
- **失败重试**: 最多重试 2 次
- **消息模板**: 内置任务完成、错误告警、日报格式化模板
- **异步发送**: 使用 httpx AsyncClient，同步上下文通过 asyncio.run() 调用
