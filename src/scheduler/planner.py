"""每日任务规划器

根据用户配置自动生成当日任务执行计划，并按优先级顺序执行。
完整执行流程：唤醒设备 → 启动阴阳师 → 等待加载 → 执行任务队列 → 退出游戏。

单个任务失败不影响后续任务的执行，确保计划的健壮性。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

if TYPE_CHECKING:
    from src.device.app_manager import AppManager
    from src.device.controller import DeviceController
    from src.device.screen import ScreenCapture
    from src.tasks.base import TaskResult
    from src.vision.finder import VisionFinder


class PlanStatus(str, Enum):
    """计划任务状态枚举

    Attributes:
        PENDING: 等待执行
        RUNNING: 正在执行
        SUCCESS: 执行成功
        FAILED: 执行失败
        SKIPPED: 已跳过
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlannedTask:
    """计划任务数据类

    描述单个待执行任务的完整信息。

    Attributes:
        task_name: 任务注册名称（对应 registry 中的 key）
        priority: 优先级，数值越小优先级越高（1 最高）
        config: 任务配置字典
        status: 当前执行状态
        result: 执行结果（执行完成后填充）
        error_message: 失败时的错误信息
    """

    task_name: str
    priority: int = 5
    config: dict[str, Any] = field(default_factory=dict)
    status: PlanStatus = PlanStatus.PENDING
    result: Optional[TaskResult] = None
    error_message: str = ""


class DailyPlanner:
    """每日任务规划器

    根据用户配置（SchedulerConfig）生成当日任务执行计划，
    并按优先级顺序依次执行，管理完整的游戏生命周期。

    Attributes:
        device: 设备控制器
        vision: 视觉查找器
        screen: 截图管理器
        app_manager: 应用管理器

    Example:
        >>> planner = DailyPlanner(device, vision, screen, app_manager)
        >>> plan = planner.create_plan(config)
        >>> planner.execute_plan(plan)
    """

    def __init__(
        self,
        device: DeviceController,
        vision: VisionFinder,
        screen: ScreenCapture,
        app_manager: AppManager,
    ) -> None:
        """初始化每日任务规划器

        Args:
            device: 设备控制器，提供点击、滑动等操作
            vision: 视觉查找器，提供图像识别、文字识别
            screen: 截图管理器，提供屏幕截图
            app_manager: 应用管理器，提供应用启动/停止
        """
        self.device = device
        self.vision = vision
        self.screen = screen
        self.app_manager = app_manager

    def create_plan(self, config: Any) -> list[PlannedTask]:
        """根据配置生成今日任务计划

        读取 SchedulerConfig 中的任务列表，过滤已禁用的任务，
        并按 priority 升序排序（数值越小优先级越高）。

        Args:
            config: 调度器配置对象（SchedulerConfig），
                    需包含 tasks 字段（TaskItemConfig 列表）

        Returns:
            按优先级排序的 PlannedTask 列表

        Example:
            >>> plan = planner.create_plan(scheduler_config)
            >>> for task in plan:
            ...     print(f"{task.priority}: {task.task_name}")
        """
        planned: list[PlannedTask] = []

        tasks_config = getattr(config, "tasks", [])
        if not tasks_config:
            logger.warning("配置中没有任务列表，生成空计划")
            return planned

        for item in tasks_config:
            # 支持 Pydantic model 和 dict 两种输入
            if hasattr(item, "enabled"):
                enabled = item.enabled
                task_name = getattr(item, "type", "unknown")
                priority = getattr(item, "priority", 5)
                task_config = item.model_dump() if hasattr(item, "model_dump") else {}
            elif isinstance(item, dict):
                enabled = item.get("enabled", True)
                task_name = item.get("type", "unknown")
                priority = item.get("priority", 5)
                task_config = item
            else:
                logger.warning(f"无法解析的任务配置项: {item}")
                continue

            if not enabled:
                logger.debug(f"跳过已禁用任务: {task_name}")
                continue

            planned.append(PlannedTask(
                task_name=task_name,
                priority=priority,
                config=task_config,
            ))

        # 按优先级升序排序（数值越小越先执行）
        planned.sort(key=lambda t: t.priority)

        logger.info(f"生成今日任务计划: {len(planned)} 个任务")
        for i, task in enumerate(planned, 1):
            logger.info(f"  [{i}] {task.task_name} (priority={task.priority})")

        return planned

    def execute_plan(self, plan: list[PlannedTask]) -> list[PlannedTask]:
        """按优先级顺序执行任务计划

        完整执行流程：
        1. 唤醒设备屏幕
        2. 启动阴阳师游戏
        3. 等待游戏加载完成
        4. 按优先级依次执行任务队列
        5. 退出游戏

        单个任务失败不影响后续任务执行。

        Args:
            plan: 待执行的 PlannedTask 列表

        Returns:
            执行完毕后的 PlannedTask 列表（含执行结果）
        """
        if not plan:
            logger.info("任务计划为空，跳过执行")
            return plan

        logger.info(f"开始执行任务计划: {len(plan)} 个任务")

        try:
            # 1. 唤醒设备
            self._wake_device()

            # 2. 启动游戏
            self._start_game()

            # 3. 等待加载
            self._wait_game_loaded()

            # 4. 依次执行任务
            self._execute_tasks(plan)

        except Exception as e:
            logger.error(f"执行计划过程中发生严重错误: {e}")

        finally:
            # 5. 退出游戏
            try:
                self._stop_game()
            except Exception as e:
                logger.error(f"退出游戏失败: {e}")

        # 统计结果
        success = sum(1 for t in plan if t.status == PlanStatus.SUCCESS)
        failed = sum(1 for t in plan if t.status == PlanStatus.FAILED)
        skipped = sum(1 for t in plan if t.status == PlanStatus.SKIPPED)

        logger.info(
            f"任务计划执行完毕: 成功={success}, 失败={failed}, 跳过={skipped}"
        )

        return plan

    # ------------------------------------------------------------------
    # 内部方法：设备与游戏生命周期
    # ------------------------------------------------------------------

    def _wake_device(self) -> None:
        """唤醒设备屏幕并解锁"""
        logger.info("唤醒设备...")
        self.app_manager.wake_screen()
        self.app_manager.unlock_screen()
        time.sleep(1.0)

    def _start_game(self) -> None:
        """启动阴阳师游戏"""
        logger.info("启动阴阳师...")
        if not self.app_manager.is_onmyoji_running():
            self.app_manager.start_onmyoji()
            time.sleep(3.0)
        else:
            logger.info("阴阳师已在运行中")

    def _wait_game_loaded(self, timeout: float = 60.0) -> bool:
        """等待游戏加载完成

        通过查找游戏主界面特征图片判断是否加载完成。

        Args:
            timeout: 最大等待时间（秒）

        Returns:
            True 表示加载成功，False 表示超时
        """
        logger.info(f"等待游戏加载 (timeout={timeout}s)...")
        result = self.vision.wait_image(
            "common/home_btn.png",
            timeout=timeout,
            interval=2.0,
        )
        if result is not None:
            logger.info("游戏加载完成")
            return True

        logger.warning(f"游戏加载超时 ({timeout}s)")
        return False

    def _stop_game(self) -> None:
        """退出阴阳师游戏"""
        logger.info("退出阴阳师...")
        self.app_manager.stop_onmyoji()

    # ------------------------------------------------------------------
    # 内部方法：任务执行
    # ------------------------------------------------------------------

    def _execute_tasks(self, plan: list[PlannedTask]) -> None:
        """按顺序执行任务队列

        单个任务失败不影响后续任务，每个任务执行后记录结果。

        Args:
            plan: PlannedTask 列表
        """
        from src.tasks.registry import create_task

        for i, planned_task in enumerate(plan, 1):
            logger.info(
                f"执行任务 [{i}/{len(plan)}]: {planned_task.task_name} "
                f"(priority={planned_task.priority})"
            )

            planned_task.status = PlanStatus.RUNNING

            try:
                task_instance = create_task(
                    name=planned_task.task_name,
                    device=self.device,
                    vision=self.vision,
                    screen=self.screen,
                    config=planned_task.config,
                )

                result = task_instance._execute()
                planned_task.result = result

                if result.success:
                    planned_task.status = PlanStatus.SUCCESS
                    logger.info(
                        f"任务成功: {planned_task.task_name} "
                        f"(runs={result.run_count}, time={result.elapsed_time:.1f}s)"
                    )
                else:
                    planned_task.status = PlanStatus.FAILED
                    planned_task.error_message = result.details.get("error", "unknown")
                    logger.warning(
                        f"任务失败: {planned_task.task_name} -> {planned_task.error_message}"
                    )

            except KeyError as e:
                planned_task.status = PlanStatus.SKIPPED
                planned_task.error_message = str(e)
                logger.warning(f"任务跳过: {planned_task.task_name} -> {e}")

            except Exception as e:
                planned_task.status = PlanStatus.FAILED
                planned_task.error_message = str(e)
                logger.error(f"任务异常: {planned_task.task_name} -> {e}")

            # 任务间休息，模拟人类行为
            if i < len(plan):
                time.sleep(2.0)
