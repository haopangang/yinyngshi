"""任务注册表

提供装饰器自动注册任务类到全局注册表，支持按名称查找和实例化任务。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from src.device.controller import DeviceController
    from src.device.screen import ScreenCapture
    from src.tasks.base import BaseTask
    from src.vision.finder import VisionFinder

# 全局任务注册表：name -> task_class
_task_registry: dict[str, type[BaseTask]] = {}


def register_task(name: str):
    """装饰器：将任务类注册到全局注册表

    使用此装饰器标记的任务类可通过名称查找和实例化。

    Args:
        name: 任务注册名称，必须唯一；重复注册会覆盖并警告

    Returns:
        装饰器函数

    Example:
        >>> @register_task("orochi")
        ... class OrochiTask(BaseTask):
        ...     name = "八岐大蛇"
    """
    def decorator(cls: type[BaseTask]) -> type[BaseTask]:
        """实际装饰器实现

        Args:
            cls: 被装饰的任务类

        Returns:
            原任务类（不做修改）
        """
        if name in _task_registry:
            logger.warning(f"任务名称重复注册: {name}，将覆盖已有实现")
        _task_registry[name] = cls
        logger.info(f"任务已注册: {name} -> {cls.__name__}")
        return cls
    return decorator


def get_task(name: str) -> type[BaseTask] | None:
    """获取已注册的任务类

    Args:
        name: 任务注册名称

    Returns:
        对应的任务类，未找到返回 None
    """
    return _task_registry.get(name)


def get_all_tasks() -> dict[str, type[BaseTask]]:
    """获取所有已注册的任务类

    Returns:
        任务名称到任务类的映射字典（副本）
    """
    return dict(_task_registry)


def create_task(
    name: str,
    device: DeviceController,
    vision: VisionFinder,
    screen: ScreenCapture,
    config: dict[str, Any],
) -> BaseTask:
    """根据名称创建任务实例

    从注册表中查找任务类并实例化，传入标准依赖。

    Args:
        name: 任务注册名称
        device: 设备控制器实例
        vision: 视觉查找器实例
        screen: 截图管理器实例
        config: 任务配置字典

    Returns:
        任务实例

    Raises:
        KeyError: 任务名称未注册
    """
    task_cls = _task_registry.get(name)
    if task_cls is None:
        available = list(_task_registry.keys())
        raise KeyError(f"未注册的任务: {name!r}，可用任务: {available}")

    logger.info(f"创建任务实例: {name} -> {task_cls.__name__}")
    return task_cls(device=device, vision=vision, screen=screen, config=config)
