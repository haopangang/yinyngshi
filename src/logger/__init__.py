"""日志模块 - 导出 setup_logger 和 logger 实例"""

from loguru import logger

from src.logger.config import setup_logger

__all__ = ["setup_logger", "logger"]
