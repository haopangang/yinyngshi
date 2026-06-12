"""程序主入口"""

from __future__ import annotations

from src.config import load_config
from src.logger import setup_logger, logger


def main() -> None:
    """主函数：加载配置、初始化日志"""
    # 加载配置
    config = load_config()

    # 初始化日志
    setup_logger(level=config.logging.level)

    logger.info("阴阳师辅助脚本已启动")
    logger.debug(f"配置加载完成: device={config.device.serial or 'auto'}")


if __name__ == "__main__":
    main()
