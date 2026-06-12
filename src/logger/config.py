"""日志系统配置"""

import sys

from loguru import logger


def setup_logger(level: str = "INFO") -> None:
    """
    配置 loguru 日志系统：
    - 控制台：INFO 级别，彩色格式
    - 文件：DEBUG 级别，按天轮转，保留 7 天
    - 错误文件：ERROR 级别，保留 30 天
    """
    # 移除默认 handler
    logger.remove()

    # 控制台输出 - INFO 级别，彩色
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # 文件输出 - DEBUG 级别，按天轮转，保留 7 天
    logger.add(
        "logs/yys_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="00:00",  # 每天零点轮转
        retention="7 days",
        encoding="utf-8",
    )

    # 错误文件 - ERROR 级别，保留 30 天
    logger.add(
        "logs/error_{time:YYYY-MM-DD}.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="00:00",
        retention="30 days",
        encoding="utf-8",
    )
