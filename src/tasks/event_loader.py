"""活动自动发现与加载器

启动时扫描 config/events/ 下所有 .yaml 文件，
校验配置合法性，并自动注册为可执行任务。

职责：
- 扫描活动配置文件目录
- 加载并校验每个 YAML 配置
- 根据 start_date/end_date 判断活动是否在有效期内
- 通过 @register_task 自动注册到全局任务注册表
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from src.tasks.event_engine import EventTemplateTask
from src.tasks.event_models import EventConfig
from src.tasks.registry import _task_registry

# 活动配置文件默认目录
EVENTS_DIR = Path("config/events")


def _sanitize_task_name(name: str) -> str:
    """将活动名称转换为合法的任务注册名

    替换空格和特殊字符为下划线，转为小写。

    Args:
        name: 原始活动名称

    Returns:
        安全的任务注册名
    """
    safe = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in name)
    return safe.lower().strip("_")


def _is_event_active(cfg: EventConfig, today: date | None = None) -> bool:
    """判断活动是否在有效期内

    Args:
        cfg: 活动配置
        today: 当前日期，None 则使用 date.today()

    Returns:
        True 表示活动有效
    """
    if today is None:
        today = date.today()

    if not cfg.enabled:
        return False

    if cfg.start_date and today < cfg.start_date:
        return False

    if cfg.end_date and today > cfg.end_date:
        return False

    return True


def load_event_config(path: Path) -> EventConfig | None:
    """加载并校验单个活动配置文件

    Args:
        path: YAML 文件路径

    Returns:
        校验后的 EventConfig，加载或校验失败返回 None
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            logger.warning(f"活动配置文件格式错误（非 dict）: {path}")
            return None

        cfg = EventConfig(**raw)
        logger.info(f"活动配置加载成功: {path.name} -> {cfg.name}")
        return cfg

    except FileNotFoundError:
        logger.warning(f"活动配置文件不存在: {path}")
    except yaml.YAMLError as e:
        logger.warning(f"活动配置 YAML 解析失败: {path} — {e}")
    except Exception as e:
        logger.warning(f"活动配置校验失败: {path} — {e}")

    return None


def discover_events(
    events_dir: Path = EVENTS_DIR,
    skip_inactive: bool = True,
) -> list[EventConfig]:
    """扫描目录并加载所有活动配置

    自动跳过以 _ 开头的文件（如 _example.yaml）。

    Args:
        events_dir: 活动配置文件目录
        skip_inactive: 是否跳过不在有效期内的活动

    Returns:
        已加载（且有效）的活动配置列表
    """
    if not events_dir.is_dir():
        logger.warning(f"活动配置目录不存在: {events_dir}")
        return []

    configs: list[EventConfig] = []
    today = date.today()

    for yaml_file in sorted(events_dir.glob("*.yaml")):
        # 跳过以 _ 开头的模板/示例文件
        if yaml_file.stem.startswith("_"):
            logger.debug(f"跳过模板文件: {yaml_file.name}")
            continue

        cfg = load_event_config(yaml_file)
        if cfg is None:
            continue

        if skip_inactive and not _is_event_active(cfg, today):
            reason = "已禁用"
            if cfg.start_date and today < cfg.start_date:
                reason = f"未开始 ({cfg.start_date})"
            elif cfg.end_date and today > cfg.end_date:
                reason = f"已过期 ({cfg.end_date})"
            logger.info(f"跳过非活动期活动: {cfg.name} — {reason}")
            continue

        configs.append(cfg)

    logger.info(
        f"活动发现完成: 扫描 {events_dir}，"
        f"加载 {len(configs)} 个有效活动"
    )
    return configs


def register_event_tasks(
    events_dir: Path = EVENTS_DIR,
    skip_inactive: bool = True,
) -> list[str]:
    """发现活动并自动注册到全局任务注册表

    为每个有效活动动态创建一个 EventTemplateTask 子类并注册。

    Args:
        events_dir: 活动配置文件目录
        skip_inactive: 是否跳过不在有效期内的活动

    Returns:
        已注册的任务名称列表
    """
    configs = discover_events(events_dir=events_dir, skip_inactive=skip_inactive)
    registered: list[str] = []

    for cfg in configs:
        task_name = f"event_{_sanitize_task_name(cfg.name)}"

        # 动态创建子类，绑定配置
        event_cfg = cfg  # 闭包捕获

        class _EventTask(EventTemplateTask):
            """动态生成的活动任务子类"""

            name = event_cfg.name
            priority = 8
            stamina_cost = event_cfg.limits.stamina_cost

            def __init__(self, device, vision, screen, config, **kwargs):
                super().__init__(
                    device=device,
                    vision=vision,
                    screen=screen,
                    config=config,
                    event_config=event_cfg,
                    **kwargs,
                )

        _EventTask.__name__ = f"EventTask_{event_cfg.name}"
        _EventTask.__qualname__ = _EventTask.__name__

        # 注册到全局注册表
        _task_registry[task_name] = _EventTask
        logger.info(f"活动已注册: {task_name} -> {cfg.name}")
        registered.append(task_name)

    logger.info(f"活动注册完成: {len(registered)} 个 — {registered}")
    return registered


def list_event_files(events_dir: Path = EVENTS_DIR) -> list[Path]:
    """列出活动目录下所有 YAML 文件（包括模板文件）

    Args:
        events_dir: 活动配置文件目录

    Returns:
        YAML 文件路径列表
    """
    if not events_dir.is_dir():
        return []
    return sorted(events_dir.glob("*.yaml"))
