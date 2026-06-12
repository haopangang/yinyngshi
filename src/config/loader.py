"""配置加载器 - 加载并合并 YAML 配置文件"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import yaml

from src.config.models import AppConfig


def deep_merge(base: dict, override: dict) -> dict:
    """深度合并两个字典，override 覆盖 base"""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(user_config_path: Optional[Union[str, Path]] = None) -> AppConfig:
    """
    加载配置：先加载默认配置，再用用户配置覆盖。

    合并顺序：user_config → default（用户配置优先级更高）

    Args:
        user_config_path: 用户配置文件路径，为 None 时尝试默认路径

    Returns:
        AppConfig: 校验后的配置对象
    """
    config_dir = Path("config")

    # 加载默认配置
    default_path = config_dir / "default.yaml"
    merged: dict = {}
    if default_path.exists():
        with open(default_path, "r", encoding="utf-8") as f:
            merged = yaml.safe_load(f) or {}

    # 加载用户配置并覆盖
    if user_config_path is None:
        user_config_path = config_dir / "user_config.yaml"
    else:
        user_config_path = Path(user_config_path)

    if user_config_path.exists():
        with open(user_config_path, "r", encoding="utf-8") as f:
            user_data = yaml.safe_load(f) or {}
            merged = deep_merge(merged, user_data)

    return AppConfig(**merged)
