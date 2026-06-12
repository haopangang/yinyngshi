"""配置模型定义 - 基于 Pydantic v2"""

from __future__ import annotations

from typing import Optional, List

from pydantic import BaseModel, Field


class DeviceConfig(BaseModel):
    """设备配置"""
    serial: Optional[str] = None
    adb_path: str = "adb"
    screenshot_method: str = "screencap"


class GameConfig(BaseModel):
    """游戏配置"""
    package: str = "com.netease.onmyoji"
    launch_activity: str = "com.netease.onmyoji.Client"
    server: str = "default"


class StaminaConfig(BaseModel):
    """体力管理配置"""
    auto_use_sushi: bool = True
    max_daily_sushi: int = 10
    min_threshold: int = 100


class TaskItemConfig(BaseModel):
    """单个任务项配置"""
    enabled: bool = True
    priority: int = 5
    max_retry: int = 3
    count: int = 1
    layer: int = 1
    type: str = "daily"


class SchedulerConfig(BaseModel):
    """调度器配置"""
    enabled: bool = False
    start_time: str = "08:00"
    end_time: str = "23:00"
    tasks: List[TaskItemConfig] = Field(default_factory=list)


class NotifyChannelConfig(BaseModel):
    """通知渠道配置"""
    type: str = "wxpusher"
    method: str = "push"
    token: str = ""
    uid: str = ""
    url: str = ""


class NotifyConfig(BaseModel):
    """通知配置"""
    enabled: bool = False
    channels: List[NotifyChannelConfig] = Field(default_factory=list)
    events: List[str] = Field(default_factory=lambda: ["task_complete", "error"])


class RecoveryConfig(BaseModel):
    """异常恢复配置"""
    auto_restart: bool = True
    max_retry: int = 5
    network_wait: int = 30
    battle_timeout: int = 300


class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = "INFO"
    file: str = "logs/yys.log"
    max_size: int = 10  # MB
    backup_count: int = 7


class AppConfig(BaseModel):
    """顶层应用配置，聚合所有子配置"""
    device: DeviceConfig = Field(default_factory=DeviceConfig)
    game: GameConfig = Field(default_factory=GameConfig)
    stamina: StaminaConfig = Field(default_factory=StaminaConfig)
    tasks: List[TaskItemConfig] = Field(default_factory=list)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    notify: NotifyConfig = Field(default_factory=NotifyConfig)
    recovery: RecoveryConfig = Field(default_factory=RecoveryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
