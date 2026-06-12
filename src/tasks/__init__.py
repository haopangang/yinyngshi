"""任务模块

提供阴阳师辅助脚本的所有任务实现和注册表管理功能。

任务生命周期：
    __init__ -> pre_check -> navigate -> run -> cleanup

使用方式：
    >>> from src.tasks import create_task, get_all_tasks
    >>> tasks = get_all_tasks()  # 获取所有已注册任务
    >>> task = create_task("orochi", device, vision, screen, config)
    >>> result = task._execute()
"""

# 基础类
from src.tasks.base import BaseTask, TaskResult

# 注册表
from src.tasks.registry import create_task, get_all_tasks, get_task, register_task

# 导入所有任务模块以触发自动注册（顺序重要）
from src.tasks.awakening import AwakeningTask
from src.tasks.breakthrough import BreakthroughTask
from src.tasks.daily import DailyTask
from src.tasks.guild import GuildTask
from src.tasks.hyakki import HyakkiTask
from src.tasks.orochi import OrochiTask
from src.tasks.region_king import RegionKingTask
from src.tasks.reward_seal import RewardSealTask
from src.tasks.soul_dungeon import SoulDungeonTask

__all__ = [
    # 基础类
    "BaseTask",
    "TaskResult",
    # 注册表函数
    "register_task",
    "get_task",
    "get_all_tasks",
    "create_task",
    # 任务类
    "OrochiTask",
    "AwakeningTask",
    "BreakthroughTask",
    "HyakkiTask",
    "RegionKingTask",
    "DailyTask",
    "RewardSealTask",
    "GuildTask",
    "SoulDungeonTask",
]
