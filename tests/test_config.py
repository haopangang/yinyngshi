"""配置加载和校验测试"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config.models import (
    AppConfig,
    DeviceConfig,
    GameConfig,
    LoggingConfig,
    NotifyConfig,
    RecoveryConfig,
    SchedulerConfig,
    StaminaConfig,
    TaskItemConfig,
)
from src.config.loader import load_config, deep_merge


class TestDeepMerge:
    """深度合并测试"""

    def test_simple_merge(self) -> None:
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self) -> None:
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 99, "z": 100}}
        result = deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 99, "z": 100}, "b": 3}

    def test_override_non_dict_with_dict(self) -> None:
        base = {"a": 1}
        override = {"a": {"nested": True}}
        result = deep_merge(base, override)
        assert result == {"a": {"nested": True}}


class TestModels:
    """配置模型校验测试"""

    def test_device_config_defaults(self) -> None:
        cfg = DeviceConfig()
        assert cfg.serial is None
        assert cfg.adb_path == "adb"
        assert cfg.screenshot_method == "screencap"

    def test_game_config_defaults(self) -> None:
        cfg = GameConfig()
        assert cfg.package == "com.netease.onmyoji"
        assert cfg.launch_activity == "com.netease.onmyoji.Client"
        assert cfg.server == "default"

    def test_stamina_config_defaults(self) -> None:
        cfg = StaminaConfig()
        assert cfg.auto_use_sushi is True
        assert cfg.max_daily_sushi == 10
        assert cfg.min_threshold == 100

    def test_task_item_config(self) -> None:
        cfg = TaskItemConfig(type="orochi", count=30, layer=10)
        assert cfg.enabled is True
        assert cfg.priority == 5
        assert cfg.type == "orochi"
        assert cfg.count == 30

    def test_scheduler_config_defaults(self) -> None:
        cfg = SchedulerConfig()
        assert cfg.enabled is False
        assert cfg.start_time == "08:00"
        assert cfg.tasks == []

    def test_notify_config_defaults(self) -> None:
        cfg = NotifyConfig()
        assert cfg.enabled is False
        assert cfg.channels == []
        assert "task_complete" in cfg.events

    def test_recovery_config_defaults(self) -> None:
        cfg = RecoveryConfig()
        assert cfg.auto_restart is True
        assert cfg.max_retry == 5
        assert cfg.network_wait == 30
        assert cfg.battle_timeout == 300

    def test_logging_config_defaults(self) -> None:
        cfg = LoggingConfig()
        assert cfg.level == "INFO"
        assert cfg.file == "logs/yys.log"
        assert cfg.max_size == 10
        assert cfg.backup_count == 7

    def test_app_config_defaults(self) -> None:
        cfg = AppConfig()
        assert isinstance(cfg.device, DeviceConfig)
        assert isinstance(cfg.game, GameConfig)
        assert isinstance(cfg.stamina, StaminaConfig)
        assert isinstance(cfg.scheduler, SchedulerConfig)
        assert isinstance(cfg.notify, NotifyConfig)
        assert isinstance(cfg.recovery, RecoveryConfig)
        assert isinstance(cfg.logging, LoggingConfig)
        assert cfg.tasks == []


class TestLoadConfig:
    """配置加载测试"""

    def test_load_default_config(self) -> None:
        """从项目 config/default.yaml 加载"""
        cfg = load_config()
        assert isinstance(cfg, AppConfig)
        assert cfg.device.adb_path == "adb"
        assert cfg.game.package == "com.netease.onmyoji"

    def test_load_with_user_config_override(self, tmp_path: Path) -> None:
        """用户配置覆盖默认配置"""
        user_yaml = tmp_path / "user_config.yaml"
        user_yaml.write_text(
            "device:\n"
            "  serial: 'test_device_123'\n"
            "stamina:\n"
            "  max_daily_sushi: 20\n",
            encoding="utf-8",
        )
        cfg = load_config(user_config_path=user_yaml)
        assert cfg.device.serial == "test_device_123"
        assert cfg.stamina.max_daily_sushi == 20
        # 未覆盖的字段保持默认值
        assert cfg.device.adb_path == "adb"

    def test_load_nonexistent_user_config(self) -> None:
        """用户配置不存在时不报错"""
        cfg = load_config(user_config_path="/nonexistent/path.yaml")
        assert isinstance(cfg, AppConfig)

    def test_invalid_config_raises_error(self, tmp_path: Path) -> None:
        """无效配置值触发 pydantic 校验错误"""
        user_yaml = tmp_path / "bad.yaml"
        user_yaml.write_text(
            "stamina:\n"
            "  max_daily_sushi: 'not_a_number'\n",
            encoding="utf-8",
        )
        with pytest.raises(Exception):
            load_config(user_config_path=user_yaml)
