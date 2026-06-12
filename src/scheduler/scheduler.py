"""APScheduler 定时任务管理器

基于 APScheduler BackgroundScheduler 实现定时任务调度，
支持 SQLite 持久化（通过 SQLAlchemyJobStore），确保重启后任务不丢失。

提供每日定时、间隔执行、暂停/恢复/移除等完整调度能力。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger


class TaskScheduler:
    """APScheduler 定时任务管理器

    封装 BackgroundScheduler，提供简洁的中文 API，支持：
    - 每日定时任务（指定 HH:MM 时间）
    - 间隔任务（指定分钟数）
    - 任务暂停 / 恢复 / 移除
    - SQLite 持久化（jobs.sqlite）

    Attributes:
        _scheduler: APScheduler BackgroundScheduler 实例
        _running: 调度器是否正在运行

    Example:
        >>> scheduler = TaskScheduler()
        >>> scheduler.start()
        >>> scheduler.add_daily_job("08:00", my_func, "morning_task")
        >>> scheduler.add_interval_job(30, check_func, "check_job")
    """

    def __init__(
        self,
        db_path: str = "jobs.sqlite",
        timezone: str = "Asia/Shanghai",
    ) -> None:
        """初始化任务调度器

        Args:
            db_path: SQLite 持久化数据库文件路径，默认 "jobs.sqlite"
            timezone: 调度器时区，默认 "Asia/Shanghai"
        """
        self._db_path = db_path
        self._timezone = timezone
        self._scheduler: Any = None
        self._running: bool = False

        self._init_scheduler()

    def _init_scheduler(self) -> None:
        """初始化 APScheduler BackgroundScheduler 及 SQLAlchemyJobStore

        使用 SQLite 作为持久化存储，确保调度器重启后任务仍然保留。
        """
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
            from apscheduler.executors.pool import ThreadPoolExecutor

            # 确保数据库目录存在
            db_file = Path(self._db_path)
            db_file.parent.mkdir(parents=True, exist_ok=True)

            jobstores = {
                "default": SQLAlchemyJobStore(url=f"sqlite:///{self._db_path}"),
            }
            executors = {
                "default": ThreadPoolExecutor(max_workers=5),
            }
            job_defaults = {
                "coalesce": True,          # 错过的任务合并为一次
                "max_instances": 1,        # 同一任务同时只运行一个实例
                "misfire_grace_time": 600,  # 错过 10 分钟内仍执行
            }

            self._scheduler = BackgroundScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone=self._timezone,
            )

            logger.info(
                f"TaskScheduler 初始化完成 (db={self._db_path}, tz={self._timezone})"
            )

        except ImportError as e:
            logger.error(f"APScheduler 依赖缺失: {e}")
            raise

    # ------------------------------------------------------------------
    # 调度器生命周期
    # ------------------------------------------------------------------

    def start(self) -> None:
        """启动调度器

        开始执行所有已注册的计划任务。若调度器已在运行则跳过。
        """
        if self._running:
            logger.warning("调度器已在运行中，跳过重复启动")
            return

        self._scheduler.start()
        self._running = True
        logger.info("调度器已启动")

    def stop(self) -> None:
        """停止调度器

        等待当前正在执行的任务完成后停止调度器。
        """
        if not self._running:
            logger.warning("调度器未运行，无需停止")
            return

        self._scheduler.shutdown(wait=True)
        self._running = False
        logger.info("调度器已停止")

    @property
    def is_running(self) -> bool:
        """调度器是否正在运行"""
        return self._running

    # ------------------------------------------------------------------
    # 任务管理
    # ------------------------------------------------------------------

    def add_daily_job(
        self,
        time_str: str,
        func: Callable,
        job_id: str,
        args: list | None = None,
        kwargs: dict | None = None,
    ) -> str:
        """添加每日定时任务

        在每天指定时间执行一次任务。若已存在相同 job_id 的任务则替换。

        Args:
            time_str: 执行时间，格式 "HH:MM"，例如 "08:00"
            func: 要执行的函数
            job_id: 任务唯一标识
            args: 传递给函数的位置参数列表
            kwargs: 传递给函数的关键字参数字典

        Returns:
            任务 ID 字符串

        Example:
            >>> scheduler.add_daily_job("08:00", morning_func, "morning_task")
        """
        from apscheduler.triggers.cron import CronTrigger

        hour, minute = map(int, time_str.split(":"))

        trigger = CronTrigger(hour=hour, minute=minute)

        job = self._scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name=job_id,
            args=args or [],
            kwargs=kwargs or {},
            replace_existing=True,
        )

        logger.info(f"添加每日任务: {job_id} @ {time_str} (next_run={job.next_run_time})")
        return job_id

    def add_interval_job(
        self,
        minutes: int,
        func: Callable,
        job_id: str,
        args: list | None = None,
        kwargs: dict | None = None,
    ) -> str:
        """添加间隔执行任务

        每隔指定分钟数执行一次任务。若已存在相同 job_id 的任务则替换。

        Args:
            minutes: 间隔分钟数
            func: 要执行的函数
            job_id: 任务唯一标识
            args: 传递给函数的位置参数列表
            kwargs: 传递给函数的关键字参数字典

        Returns:
            任务 ID 字符串

        Example:
            >>> scheduler.add_interval_job(30, check_func, "check_job")
        """
        from apscheduler.triggers.interval import IntervalTrigger

        trigger = IntervalTrigger(minutes=minutes)

        job = self._scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name=job_id,
            args=args or [],
            kwargs=kwargs or {},
            replace_existing=True,
        )

        logger.info(
            f"添加间隔任务: {job_id} 每 {minutes} 分钟 (next_run={job.next_run_time})"
        )
        return job_id

    def remove_job(self, job_id: str) -> bool:
        """移除指定任务

        Args:
            job_id: 任务唯一标识

        Returns:
            True 表示移除成功，False 表示任务不存在
        """
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"移除任务: {job_id}")
            return True
        except Exception as e:
            logger.warning(f"移除任务失败: {job_id} -> {e}")
            return False

    def pause_job(self, job_id: str) -> bool:
        """暂停指定任务

        暂停后任务不会被触发，直到调用 resume_job() 恢复。

        Args:
            job_id: 任务唯一标识

        Returns:
            True 表示暂停成功
        """
        try:
            self._scheduler.pause_job(job_id)
            logger.info(f"暂停任务: {job_id}")
            return True
        except Exception as e:
            logger.warning(f"暂停任务失败: {job_id} -> {e}")
            return False

    def resume_job(self, job_id: str) -> bool:
        """恢复指定任务

        恢复之前被暂停的任务，使其重新按计划触发。

        Args:
            job_id: 任务唯一标识

        Returns:
            True 表示恢复成功
        """
        try:
            self._scheduler.resume_job(job_id)
            logger.info(f"恢复任务: {job_id}")
            return True
        except Exception as e:
            logger.warning(f"恢复任务失败: {job_id} -> {e}")
            return False

    def get_jobs(self) -> list[dict[str, Any]]:
        """获取所有计划任务信息

        Returns:
            任务信息列表，每项包含 id, name, next_run_time, trigger 等字段

        Example:
            >>> for job in scheduler.get_jobs():
            ...     print(f"{job['id']}: next_run={job['next_run_time']}")
        """
        jobs = self._scheduler.get_jobs()
        result = []
        for job in jobs:
            result.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        logger.debug(f"当前计划任务数: {len(result)}")
        return result
