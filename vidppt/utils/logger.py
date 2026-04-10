"""
日志配置模块

提供统一的日志管理，支持日志等级控制
"""

import logging
import sys
from typing import Optional


# 日志格式定义
_DEFAULT_FORMAT = "[%(levelname)-8s] %(name)s - %(message)s"
_VERBOSE_FORMAT = (
    "[%(asctime)s] [%(levelname)-8s] %(name)s:%(funcName)s:%(lineno)d - %(message)s"
)


def setup_logger(
    name: str = "vidppt",
    level: int = logging.INFO,
    verbose: bool = False,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """
    配置日志记录器

    参数:
        name: 日志记录器名称（默认: vidppt）
        level: 日志等级（默认: INFO）
        verbose: 是否使用详细格式（默认: False）
        log_file: 日志文件路径，如果为 None 则仅输出到控制台（默认: None）

    返回:
        配置好的 Logger 对象

    示例:
        # 基础使用
        logger = setup_logger()
        logger.info("This is an info message")

        # 详细模式
        logger = setup_logger(verbose=True)

        # 同时输出到文件和控制台
        logger = setup_logger(log_file="output.log")

        # 设置 DEBUG 等级
        logger = setup_logger(level=logging.DEBUG)
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 清除可能存在的旧 handlers
    logger.handlers.clear()

    # 选择日志格式
    fmt = _VERBOSE_FORMAT if verbose else _DEFAULT_FORMAT
    formatter = logging.Formatter(fmt)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（如果指定了日志文件）
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (IOError, OSError) as e:
            logger.warning(f"无法创建日志文件 {log_file}: {e}")

    # 防止日志向上传递
    logger.propagate = False

    return logger


def get_logger(name: str = "vidppt") -> logging.Logger:
    """
    获取日志记录器

    如果记录器不存在，使用默认配置创建一个

    参数:
        name: 日志记录器名称

    返回:
        Logger 对象
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        setup_logger(name)
    return logger


# 为不同模块创建预配置的记录器
def create_module_logger(module_name: str, parent: str = "vidppt") -> logging.Logger:
    """
    为特定模块创建日志记录器

    参数:
        module_name: 模块名称
        parent: 父记录器名称

    返回:
        配置好的 Logger 对象

    示例:
        logger = create_module_logger("pipeline")
        # 日志记录器名称将为 "vidppt.pipeline"
    """
    full_name = f"{parent}.{module_name}"
    return logging.getLogger(full_name)
