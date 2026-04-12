"""
Loguru 日志配置模块
"""

import sys
from pathlib import Path
from loguru import logger

# 移除默认的处理器
logger.remove()

# 配置格式
LOG_FORMAT = "<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{file}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
LOG_FORMAT_WITH_TIME = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{file}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"


def setup_logger(
    name: str = "vidppt",
    level: str = "INFO",
    verbose: bool = False,
    log_file: str | Path | None = None,
) -> None:
    """
    配置日志系统

    Args:
        name: logger 名称
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        verbose: 是否启用详细模式
        log_file: 日志文件路径 (可选)
    """
    # 确定日志格式
    if verbose:
        log_format = LOG_FORMAT_WITH_TIME
    else:
        log_format = LOG_FORMAT

    # 添加控制台处理器
    logger.add(
        sys.stderr,
        format=log_format,
        level=level,
        colorize=True,
    )

    # 如果指定了日志文件，添加文件处理器
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(log_file),
            format=log_format,
            level=level,
            rotation="10 MB",  # 日志文件达到 10MB 时轮换
            retention="7 days",  # 保留 7 天的日志
        )


def get_logger(name: str = __name__):
    """获取指定名称的 logger"""
    return logger.bind(name=name)
