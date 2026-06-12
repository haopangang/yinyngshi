"""阴阳师辅助脚本 CLI 入口 - 基于 Typer"""

from __future__ import annotations

from typing import Optional

import typer

# ─── 根应用 ──────────────────────────────────────────────────────────────────
app = typer.Typer(
    name="yys",
    help="🌙 阴阳师全自动托管辅助脚本",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo("yys-assistant v0.1.0")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="显示版本号并退出",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """🌙 阴阳师全自动托管辅助脚本"""
    pass


# ─── device 子命令组 ─────────────────────────────────────────────────────────
device_app = typer.Typer(help="设备管理命令", no_args_is_help=True)
app.add_typer(device_app, name="device")


@device_app.command("devices")
def device_list() -> None:
    """列出已连接的 ADB 设备"""
    typer.echo("TODO: 列出已连接的 ADB 设备")


@device_app.command("connect")
def device_connect(
    device_id: str = typer.Argument(..., help="设备 ID 或 IP:端口"),
) -> None:
    """连接指定设备（USB 或 WiFi ADB）"""
    typer.echo(f"TODO: 连接设备 {device_id}")


@device_app.command("start")
def device_start(
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="设备 ID"),
) -> None:
    """启动阴阳师游戏"""
    typer.echo(f"TODO: 启动游戏 (device={device_id})")


@device_app.command("stop")
def device_stop(
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="设备 ID"),
) -> None:
    """退出阴阳师游戏"""
    typer.echo(f"TODO: 退出游戏 (device={device_id})")


# ─── run 子命令组 ─────────────────────────────────────────────────────────────
run_app = typer.Typer(help="任务执行命令", no_args_is_help=True)
app.add_typer(run_app, name="run")


@run_app.command("orochi")
def run_orochi(
    layer: int = typer.Option(10, "--layer", "-l", help="副本层数 (1-12)"),
    count: int = typer.Option(30, "--count", "-c", help="挑战次数"),
) -> None:
    """执行御魂副本（八岐大蛇）"""
    typer.echo(f"TODO: 御魂副本 layer={layer} count={count}")


@run_app.command("awake")
def run_awake(
    material: str = typer.Option("fire", "--type", "-t", help="材料类型: fire/wind/thunder/tomb"),
    layer: int = typer.Option(8, "--layer", "-l", help="副本层数"),
    count: int = typer.Option(20, "--count", "-c", help="挑战次数"),
) -> None:
    """执行觉醒副本"""
    typer.echo(f"TODO: 觉醒副本 type={material} layer={layer} count={count}")


@run_app.command("breakthrough")
def run_breakthrough(
    mode: str = typer.Option("personal", "--type", "-t", help="突破类型: personal/guild"),
) -> None:
    """执行结界突破"""
    typer.echo(f"TODO: 结界突破 mode={mode}")


@run_app.command("hyakki")
def run_hyakki(
    count: int = typer.Option(5, "--count", "-c", help="百鬼夜行次数"),
) -> None:
    """执行百鬼夜行"""
    typer.echo(f"TODO: 百鬼夜行 count={count}")


@run_app.command("boss")
def run_boss(
    count: int = typer.Option(3, "--count", "-c", help="挑战次数"),
) -> None:
    """执行地域鬼王"""
    typer.echo(f"TODO: 地域鬼王 count={count}")


@run_app.command("daily")
def run_daily() -> None:
    """执行全部日常任务"""
    typer.echo("TODO: 执行全部日常任务")


@run_app.command("all")
def run_all() -> None:
    """执行全部任务（日常 + 副本）"""
    typer.echo("TODO: 执行全部任务")


# ─── 快捷调试命令 ─────────────────────────────────────────────────────────────
@app.command("click")
def quick_click(
    x: int = typer.Argument(..., help="X 坐标"),
    y: int = typer.Argument(..., help="Y 坐标"),
) -> None:
    """点击指定坐标"""
    typer.echo(f"TODO: 点击 ({x}, {y})")


@app.command("swipe")
def quick_swipe(
    x1: int = typer.Argument(..., help="起始 X"),
    y1: int = typer.Argument(..., help="起始 Y"),
    x2: int = typer.Argument(..., help="结束 X"),
    y2: int = typer.Argument(..., help="结束 Y"),
    duration: int = typer.Option(500, "--duration", "-d", help="滑动时长 (ms)"),
) -> None:
    """执行滑动操作"""
    typer.echo(f"TODO: 滑动 ({x1},{y1}) -> ({x2},{y2}) duration={duration}ms")


@app.command("screenshot")
def quick_screenshot(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="保存路径"),
) -> None:
    """截取当前屏幕"""
    typer.echo(f"TODO: 截图 output={output}")


@app.command("find")
def quick_find(
    template: str = typer.Argument(..., help="模板图片路径"),
) -> None:
    """在屏幕上查找模板图片"""
    typer.echo(f"TODO: 查找模板 {template}")


# ─── 调度与守护命令 ───────────────────────────────────────────────────────────
@app.command("daemon")
def daemon_cmd(
    action: str = typer.Argument("start", help="操作: start/stop/restart"),
) -> None:
    """守护进程管理"""
    typer.echo(f"TODO: 守护进程 {action}")


@app.command("status")
def status_cmd() -> None:
    """查看当前运行状态"""
    typer.echo("TODO: 查看运行状态")


@app.command("report")
def report_cmd(
    date: Optional[str] = typer.Option(None, "--date", "-d", help="日期 (YYYY-MM-DD 或 today)"),
) -> None:
    """查看统计报告"""
    typer.echo(f"TODO: 统计报告 date={date}")


if __name__ == "__main__":
    app()
