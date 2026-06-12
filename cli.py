"""阴阳师辅助脚本 CLI 入口 - 基于 Typer

命令结构：
    yys devices               — 列出已连接的 ADB 设备
    yys connect [serial]       — 连接设备
    yys start                  — 启动阴阳师
    yys stop                   — 退出阴阳师
    yys click <x> <y>          — 点击指定坐标
    yys swipe <x1> <y1> <x2> <y2> — 滑动
    yys screenshot [output]    — 截图保存
    yys run <task> [--count N] — 运行指定任务
    yys run-all                — 运行全部日常任务
    yys tasks                  — 列出已注册任务
    yys daemon                 — 启动调度守护进程
    yys status                 — 查看运行状态
    yys report                 — 生成日报
    yys config show            — 显示当前配置
    yys config edit            — 编辑配置文件
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ─── Rich Console ─────────────────────────────────────────────────────────────
console = Console()
err_console = Console(stderr=True)

# ─── 根应用 ──────────────────────────────────────────────────────────────────
app = typer.Typer(
    name="yys",
    help="🌙 阴阳师全自动托管辅助脚本",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


# ─── 全局 verbose 回调 ───────────────────────────────────────────────────────
def _setup_logging(verbose: bool) -> None:
    """根据 --verbose 参数配置日志级别"""
    from loguru import logger

    level = "DEBUG" if verbose else "INFO"
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    )


def version_callback(value: bool) -> None:
    if value:
        console.print("[bold cyan]yys-assistant[/] v0.1.0")
        raise typer.Exit()


def verbose_callback(ctx: typer.Context, value: bool) -> None:
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = value
    _setup_logging(value)


@app.callback()
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="显示版本号并退出",
        callback=version_callback,
        is_eager=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="启用 DEBUG 级别日志输出",
        callback=verbose_callback,
        is_eager=True,
    ),
) -> None:
    """🌙 阴阳师全自动托管辅助脚本"""
    ctx.ensure_object(dict)


# ─── 内部辅助 ─────────────────────────────────────────────────────────────────

def _load_config():
    """加载配置，失败时给出友好提示"""
    try:
        from src.config import load_config
        return load_config()
    except Exception as exc:
        err_console.print(f"[red]配置加载失败:[/red] {exc}")
        raise typer.Exit(code=1)


def _get_adb_client():
    """创建并返回未连接的 ADBClient 实例"""
    try:
        from src.device.adb_client import ADBClient
        config = _load_config()
        return ADBClient(adb_path=config.device.adb_path, heartbeat_interval=0), config
    except Exception as exc:
        err_console.print(f"[red]初始化失败:[/red] {exc}")
        raise typer.Exit(code=1)


def _get_connected_device(serial: Optional[str] = None):
    """连接设备并返回 ADBClient 实例"""
    client, config = _get_adb_client()
    target_serial = serial or config.device.serial

    if not target_serial:
        # 尝试自动检测
        devices = client.list_devices()
        if not devices:
            err_console.print("[red]未检测到任何已连接的设备[/red]")
            err_console.print("请先使用 [cyan]yys connect <设备ID>[/cyan] 连接设备")
            raise typer.Exit(code=1)
        target_serial = devices[0]

    try:
        client.connect(target_serial)
        return client, config
    except ConnectionError as exc:
        err_console.print(f"[red]设备连接失败:[/red] {exc}")
        raise typer.Exit(code=1)


def _build_device_stack(serial: Optional[str] = None):
    """构建设备操作栈：ADBClient + DeviceController + AppManager + ScreenCapture"""
    client, config = _get_connected_device(serial)
    from src.device.app_manager import AppManager
    from src.device.controller import DeviceController
    from src.device.screen import ScreenCapture

    controller = DeviceController(client)
    app_mgr = AppManager(client)
    screen = ScreenCapture(client)
    return client, controller, app_mgr, screen, config


# ─── 设备管理命令 ─────────────────────────────────────────────────────────────

@app.command("devices")
def cmd_devices() -> None:
    """列出已连接的 ADB 设备"""
    client, _ = _get_adb_client()
    devices = client.list_devices()

    if not devices:
        console.print("[yellow]未发现任何已连接的 ADB 设备[/yellow]")
        console.print("提示: 请确认设备已开启 USB 调试，或使用 [cyan]yys connect <IP:端口>[/cyan] 连接")
        return

    table = Table(title="已连接的 ADB 设备", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("设备序列号", style="cyan")
    table.add_column("连接类型", style="green")

    for i, serial in enumerate(devices, 1):
        conn_type = "WiFi" if ":" in serial else "USB"
        table.add_row(str(i), serial, conn_type)

    console.print(table)


@app.command("connect")
def cmd_connect(
    serial: str = typer.Argument(..., help="设备序列号、USB ID 或 WiFi 地址（IP:端口）"),
) -> None:
    """连接指定设备（支持 USB / WiFi ADB）"""
    client, _ = _get_adb_client()

    with console.status(f"正在连接 [cyan]{serial}[/cyan] ..."):
        try:
            if ":" in serial and not serial.startswith("emulator"):
                # WiFi 连接
                parts = serial.rsplit(":", 1)
                ip = parts[0]
                port = int(parts[1]) if len(parts) > 1 else 5555
                client.connect_wifi(ip, port)
            else:
                client.connect(serial)
            console.print(f"[green]✓ 设备连接成功:[/green] {serial}")
        except ConnectionError as exc:
            err_console.print(f"[red]✗ 连接失败:[/red] {exc}")
            raise typer.Exit(code=1)


# ─── 游戏控制命令 ─────────────────────────────────────────────────────────────

@app.command("start")
def cmd_start(
    device: Optional[str] = typer.Option(None, "--device", "-d", help="设备序列号"),
) -> None:
    """启动阴阳师游戏"""
    with console.status("正在启动阴阳师..."):
        try:
            _, _, app_mgr, _, _ = _build_device_stack(device)
            app_mgr.wake_screen()
            app_mgr.start_onmyoji()
            console.print("[green]✓ 阴阳师已启动[/green]")
        except typer.Exit:
            raise
        except Exception as exc:
            err_console.print(f"[red]启动失败:[/red] {exc}")
            raise typer.Exit(code=1)


@app.command("stop")
def cmd_stop(
    device: Optional[str] = typer.Option(None, "--device", "-d", help="设备序列号"),
) -> None:
    """退出阴阳师游戏"""
    try:
        _, _, app_mgr, _, _ = _build_device_stack(device)
        app_mgr.stop_onmyoji()
        console.print("[green]✓ 阴阳师已退出[/green]")
    except typer.Exit:
        raise
    except Exception as exc:
        err_console.print(f"[red]退出失败:[/red] {exc}")
        raise typer.Exit(code=1)


# ─── 快捷操作命令 ─────────────────────────────────────────────────────────────

@app.command("click")
def cmd_click(
    x: int = typer.Argument(..., help="X 坐标（像素）"),
    y: int = typer.Argument(..., help="Y 坐标（像素）"),
    device: Optional[str] = typer.Option(None, "--device", "-d", help="设备序列号"),
) -> None:
    """点击指定屏幕坐标"""
    try:
        _, controller, _, _, _ = _build_device_stack(device)
        controller.click(x, y, offset=False, delay=False)
        console.print(f"[green]✓ 已点击[/green] ({x}, {y})")
    except typer.Exit:
        raise
    except Exception as exc:
        err_console.print(f"[red]点击失败:[/red] {exc}")
        raise typer.Exit(code=1)


@app.command("swipe")
def cmd_swipe(
    x1: int = typer.Argument(..., help="起始 X 坐标"),
    y1: int = typer.Argument(..., help="起始 Y 坐标"),
    x2: int = typer.Argument(..., help="结束 X 坐标"),
    y2: int = typer.Argument(..., help="结束 Y 坐标"),
    duration: int = typer.Option(500, "--duration", "-t", help="滑动时长（毫秒）"),
    device: Optional[str] = typer.Option(None, "--device", "-d", help="设备序列号"),
) -> None:
    """在屏幕上执行滑动操作"""
    try:
        _, controller, _, _, _ = _build_device_stack(device)
        controller.swipe(x1, y1, x2, y2, duration=duration / 1000.0, delay=False)
        console.print(f"[green]✓ 已滑动[/green] ({x1},{y1}) → ({x2},{y2})  {duration}ms")
    except typer.Exit:
        raise
    except Exception as exc:
        err_console.print(f"[red]滑动失败:[/red] {exc}")
        raise typer.Exit(code=1)


@app.command("screenshot")
def cmd_screenshot(
    output: Optional[str] = typer.Argument(None, help="保存路径（默认: screenshot.png）"),
    device: Optional[str] = typer.Option(None, "--device", "-d", help="设备序列号"),
) -> None:
    """截取当前屏幕并保存为图片"""
    output_path = output or "screenshot.png"
    try:
        _, _, _, screen, _ = _build_device_stack(device)
        saved = screen.save_screenshot(output_path)
        console.print(f"[green]✓ 截图已保存:[/green] {saved}")
    except typer.Exit:
        raise
    except Exception as exc:
        err_console.print(f"[red]截图失败:[/red] {exc}")
        raise typer.Exit(code=1)


# ─── 任务执行命令 ─────────────────────────────────────────────────────────────

@app.command("run")
def cmd_run(
    task_name: str = typer.Argument(..., help="任务名称（如 orochi、awakening、hyakki 等）"),
    count: int = typer.Option(1, "--count", "-c", help="执行次数"),
    device: Optional[str] = typer.Option(None, "--device", "-d", help="设备序列号"),
) -> None:
    """运行指定游戏任务"""
    from src.tasks.registry import get_all_tasks, get_task

    # 检查任务是否存在
    task_cls = get_task(task_name)
    if task_cls is None:
        available = list(get_all_tasks().keys())
        err_console.print(f"[red]任务不存在:[/red] {task_name}")
        if available:
            err_console.print(f"可用任务: [cyan]{', '.join(available)}[/cyan]")
        else:
            err_console.print("[yellow]当前没有已注册的任务[/yellow]")
        raise typer.Exit(code=1)

    try:
        _, controller, app_mgr, screen, config = _build_device_stack(device)

        # 构建视觉查找器
        from src.vision.finder import VisionFinder
        vision = VisionFinder(
            screenshot_func=screen.capture_cached,
            click_func=controller.click,
        )

        from src.tasks.registry import create_task
        task_config = {"enabled": True, "count": count, "type": task_name}

        console.print(f"正在执行任务 [cyan]{task_name}[/cyan] × {count} 次...")

        task_instance = create_task(
            name=task_name,
            device=controller,
            vision=vision,
            screen=screen,
            config=task_config,
        )

        result = task_instance._execute()

        if result.success:
            console.print(
                f"[green]✓ 任务完成:[/green] {task_name}  "
                f"执行 {result.run_count} 次  耗时 {result.elapsed_time:.1f}s"
            )
        else:
            reason = result.details.get("error") or result.details.get("reason", "未知原因")
            err_console.print(f"[yellow]⚠ 任务未完全完成:[/yellow] {task_name} → {reason}")

    except typer.Exit:
        raise
    except Exception as exc:
        err_console.print(f"[red]任务执行失败:[/red] {exc}")
        raise typer.Exit(code=1)


@app.command("run-all")
def cmd_run_all(
    device: Optional[str] = typer.Option(None, "--device", "-d", help="设备序列号"),
) -> None:
    """运行全部日常任务（按 planner 规划顺序执行）"""
    try:
        _, controller, app_mgr, screen, config = _build_device_stack(device)

        from src.scheduler.planner import DailyPlanner, PlanStatus
        from src.vision.finder import VisionFinder

        vision = VisionFinder(
            screenshot_func=screen.capture_cached,
            click_func=controller.click,
        )

        planner = DailyPlanner(controller, vision, screen, app_mgr)
        plan = planner.create_plan(config)

        if not plan:
            console.print("[yellow]配置中没有启用的任务[/yellow]")
            return

        console.print(f"今日任务计划: [cyan]{len(plan)}[/cyan] 个任务")
        for i, t in enumerate(plan, 1):
            console.print(f"  [{i}] {t.task_name}  (优先级 {t.priority})")
        console.print()

        results = planner.execute_plan(plan)

        # 汇总结果
        success = sum(1 for t in results if t.status == PlanStatus.SUCCESS)
        failed = sum(1 for t in results if t.status == PlanStatus.FAILED)
        skipped = sum(1 for t in results if t.status == PlanStatus.SKIPPED)

        console.print()
        table = Table(title="执行结果汇总", show_lines=False)
        table.add_column("任务", style="cyan")
        table.add_column("状态", width=8)
        table.add_column("耗时", style="dim")

        for t in results:
            if t.status == PlanStatus.SUCCESS:
                status_str = "[green]✓ 成功[/green]"
            elif t.status == PlanStatus.FAILED:
                status_str = "[red]✗ 失败[/red]"
            else:
                status_str = "[yellow]⊘ 跳过[/yellow]"

            elapsed = f"{t.result.elapsed_time:.1f}s" if t.result else "-"
            table.add_row(t.task_name, status_str, elapsed)

        console.print(table)
        console.print(
            f"\n[green]成功 {success}[/green]  "
            f"[red]失败 {failed}[/red]  "
            f"[yellow]跳过 {skipped}[/yellow]"
        )

    except typer.Exit:
        raise
    except Exception as exc:
        err_console.print(f"[red]执行失败:[/red] {exc}")
        raise typer.Exit(code=1)


@app.command("tasks")
def cmd_tasks() -> None:
    """列出所有已注册的游戏任务"""
    # 确保所有任务模块被导入以触发 @register_task 装饰器
    _import_all_tasks()

    from src.tasks.registry import get_all_tasks

    all_tasks = get_all_tasks()

    if not all_tasks:
        console.print("[yellow]当前没有已注册的任务[/yellow]")
        console.print("提示: 请确认 [cyan]src/tasks/[/cyan] 下有任务实现文件")
        return

    table = Table(title="已注册任务列表", show_lines=False)
    table.add_column("任务标识", style="cyan")
    table.add_column("任务名称", style="green")
    table.add_column("优先级", justify="center", style="dim")
    table.add_column("体力消耗", justify="center", style="yellow")

    for name, cls in sorted(all_tasks.items(), key=lambda x: getattr(x[1], "priority", 99)):
        display_name = getattr(cls, "name", cls.__name__)
        priority = str(getattr(cls, "priority", "-"))
        stamina = str(getattr(cls, "stamina_cost", 0))
        table.add_row(name, display_name, priority, stamina)

    console.print(table)


# ─── 调度管理命令 ─────────────────────────────────────────────────────────────

@app.command("daemon")
def cmd_daemon(
    action: str = typer.Argument("start", help="操作: start / stop"),
    device: Optional[str] = typer.Option(None, "--device", "-d", help="设备序列号"),
) -> None:
    """启动或停止调度守护进程（APScheduler 后台运行）"""
    if action not in ("start", "stop"):
        err_console.print(f"[red]不支持的操作:[/red] {action}，可选: start, stop")
        raise typer.Exit(code=1)

    if action == "stop":
        console.print("[yellow]守护进程停止需要手动终止进程（Ctrl+C）[/yellow]")
        return

    console.print("[cyan]正在启动调度守护进程...[/cyan]")

    try:
        config = _load_config()

        if not config.scheduler.enabled:
            err_console.print("[yellow]调度器未启用[/yellow]")
            err_console.print("请在配置文件中设置 [cyan]scheduler.enabled: true[/cyan]")
            raise typer.Exit(code=1)

        from src.scheduler.scheduler import TaskScheduler

        scheduler = TaskScheduler()
        scheduler.start()

        console.print("[green]✓ 调度守护进程已启动[/green]")
        console.print(f"  调度时间: {config.scheduler.start_time} ~ {config.scheduler.end_time}")
        console.print("按 [bold]Ctrl+C[/bold] 停止守护进程")

        # 阻塞主线程
        import time
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            scheduler.stop()
            console.print("\n[yellow]守护进程已停止[/yellow]")

    except typer.Exit:
        raise
    except Exception as exc:
        err_console.print(f"[red]守护进程启动失败:[/red] {exc}")
        raise typer.Exit(code=1)


@app.command("status")
def cmd_status(
    device: Optional[str] = typer.Option(None, "--device", "-d", help="设备序列号"),
) -> None:
    """查看当前运行状态和今日统计"""
    # 设备状态
    device_status = "[dim]未检测[/dim]"
    game_status = "[dim]未检测[/dim]"
    serial_info = "-"

    try:
        client, config = _get_adb_client()
        devices = client.list_devices()
        if devices:
            target = config.device.serial or devices[0]
            try:
                client.connect(target)
                serial_info = target
                device_status = "[green]已连接[/green]"

                from src.device.app_manager import AppManager
                app_mgr = AppManager(client)
                if app_mgr.is_onmyoji_running():
                    game_status = "[green]运行中[/green]"
                else:
                    game_status = "[dim]未运行[/dim]"
            except Exception:
                device_status = "[red]连接失败[/red]"
        else:
            device_status = "[yellow]无设备[/yellow]"
    except Exception:
        pass

    # 今日统计
    from src.scheduler.monitor import RuntimeMonitor
    monitor = RuntimeMonitor()
    stats_file = Path("data/stats.json")
    if stats_file.exists():
        monitor.load_stats(stats_file)
    stats = monitor.get_stats()

    # 渲染面板
    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column(style="dim", width=12)
    info_table.add_column()
    info_table.add_row("设备", serial_info)
    info_table.add_row("设备状态", device_status)
    info_table.add_row("游戏状态", game_status)

    stats_table = Table(show_header=False, box=None, padding=(0, 2))
    stats_table.add_column(style="dim", width=12)
    stats_table.add_column()
    stats_table.add_row("今日执行", f"{stats.total_runs} 次")
    stats_table.add_row("成功", f"[green]{stats.success_count}[/green] 次")
    stats_table.add_row("失败", f"[red]{stats.error_count}[/red] 次")
    stats_table.add_row("成功率", f"{stats.success_rate:.1%}")

    console.print(Panel(info_table, title="📱 设备信息", border_style="blue"))
    console.print(Panel(stats_table, title="📊 今日统计", border_style="green"))


@app.command("report")
def cmd_report(
    date: Optional[str] = typer.Option(None, "--date", "-d", help="日期（YYYY-MM-DD，默认今天）"),
) -> None:
    """生成并显示每日运行报告"""
    from src.scheduler.monitor import RuntimeMonitor

    monitor = RuntimeMonitor()

    # 尝试加载持久化统计
    stats_file = Path("data/stats.json")
    if stats_file.exists():
        monitor.load_stats(stats_file)

    stats = monitor.get_stats()

    if stats.total_runs == 0:
        console.print("[yellow]今日暂无运行数据[/yellow]")
        console.print("提示: 运行任务后数据会自动记录")
        return

    report = monitor.get_daily_report()
    console.print(Panel(report, title="📊 运行报告", border_style="cyan"))


# ─── 配置子命令组 ─────────────────────────────────────────────────────────────

config_app = typer.Typer(help="配置管理命令", no_args_is_help=True)
app.add_typer(config_app, name="config")


@config_app.command("show")
def cmd_config_show() -> None:
    """显示当前生效的完整配置"""
    config = _load_config()

    # 将配置转为 YAML 格式展示
    import yaml

    config_dict = config.model_dump()
    yaml_str = yaml.dump(config_dict, allow_unicode=True, default_flow_style=False, sort_keys=False)

    console.print(Panel(yaml_str.strip(), title="⚙️  当前配置", border_style="blue"))

    # 显示配置文件路径
    default_path = Path("config/default.yaml")
    user_path = Path("config/user_config.yaml")
    console.print(f"\n[dim]默认配置: {default_path.resolve()}[/dim]")
    if user_path.exists():
        console.print(f"[dim]用户配置: {user_path.resolve()}[/dim]")
    else:
        console.print(f"[dim]用户配置: 未创建（可复制 user_config.yaml.example）[/dim]")


@config_app.command("edit")
def cmd_config_edit() -> None:
    """打开用户配置文件进行编辑"""
    user_path = Path("config/user_config.yaml")
    example_path = Path("config/user_config.yaml.example")

    # 如果用户配置不存在，从示例复制
    if not user_path.exists():
        if example_path.exists():
            import shutil
            shutil.copy(example_path, user_path)
            console.print(f"[green]✓ 已从示例创建用户配置文件[/green]")
        else:
            err_console.print("[red]示例配置文件不存在:[/red] config/user_config.yaml.example")
            raise typer.Exit(code=1)

    # 获取编辑器
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vi"))
    console.print(f"使用编辑器 [cyan]{editor}[/cyan] 打开配置文件...")

    try:
        subprocess.run([editor, str(user_path)], check=True)
        console.print("[green]✓ 配置文件已保存[/green]")

        # 验证配置是否有效
        try:
            _load_config()
            console.print("[green]✓ 配置格式验证通过[/green]")
        except Exception as exc:
            err_console.print(f"[red]⚠ 配置格式有误:[/red] {exc}")
    except subprocess.CalledProcessError:
        err_console.print("[yellow]编辑器异常退出，配置可能未保存[/yellow]")
    except FileNotFoundError:
        err_console.print(f"[red]找不到编辑器:[/red] {editor}")
        err_console.print("请设置环境变量 EDITOR 或 VISUAL 指定编辑器")
        raise typer.Exit(code=1)


# ─── 辅助函数 ─────────────────────────────────────────────────────────────────

def _import_all_tasks() -> None:
    """导入所有任务模块以触发 @register_task 装饰器注册"""
    import importlib

    task_modules = [
        "src.tasks.orochi",
        "src.tasks.awakening",
        "src.tasks.breakthrough",
        "src.tasks.guild",
        "src.tasks.hyakki",
        "src.tasks.region_king",
        "src.tasks.reward_seal",
        "src.tasks.soul_dungeon",
        "src.tasks.daily",
    ]
    for mod_name in task_modules:
        try:
            importlib.import_module(mod_name)
        except ImportError:
            pass  # 模块不存在则跳过
        except Exception:
            pass  # 导入错误不阻塞 CLI


if __name__ == "__main__":
    app()
