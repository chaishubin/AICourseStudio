"""
配置文件加载器

支持 YAML 和 JSON 格式的配置文件，支持与命令行参数的合并。
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger


class ConfigLoader:
    """配置文件加载器"""

    # 支持的配置文件扩展名
    SUPPORTED_EXTENSIONS = {".yaml", ".yml", ".json"}

    @staticmethod
    def load(config_path: Path) -> Dict[str, Any]:
        """
        加载配置文件

        参数:
            config_path: 配置文件路径

        返回:
            配置字典

        抛出异常:
            FileNotFoundError: 配置文件不存在
            ValueError: 不支持的文件格式或文件内容无效
        """
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        # 检查文件扩展名
        suffix = config_path.suffix.lower()
        if suffix not in ConfigLoader.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"不支持的配置文件格式: {suffix}。"
                f"支持的格式: {', '.join(ConfigLoader.SUPPORTED_EXTENSIONS)}"
            )

        try:
            if suffix == ".json":
                return ConfigLoader._load_json(config_path)
            else:  # .yaml 或 .yml
                return ConfigLoader._load_yaml(config_path)
        except Exception as e:
            raise ValueError(f"加载配置文件失败: {e}")

    @staticmethod
    def _load_json(config_path: Path) -> Dict[str, Any]:
        """加载 JSON 配置文件"""
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        if not isinstance(config, dict):
            raise ValueError("配置文件的根必须是对象/字典")

        return config

    @staticmethod
    def _load_yaml(config_path: Path) -> Dict[str, Any]:
        """加载 YAML 配置文件"""
        try:
            import yaml
        except ImportError:
            raise ImportError(
                "YAML 库未安装。请运行: pip install pyyaml\n或使用 JSON 格式的配置文件"
            )

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if config is None:
            return {}

        if not isinstance(config, dict):
            raise ValueError("配置文件的根必须是对象/字典")

        return config

    @staticmethod
    def validate(config: Dict[str, Any]) -> None:
        """
        验证配置内容

        参数:
            config: 配置字典

        抛出异常:
            ValueError: 配置不有效
        """
        # 验证必填字段
        if "input" in config and not config["input"]:
            raise ValueError("配置中的 'input' 字段不能为空")

        # 验证 TTS 引擎
        if "tts_engine" in config:
            tts_engine = config["tts_engine"]
            if tts_engine not in ["edge-tts", "minimax", "volcengine"]:
                raise ValueError(
                    f"不支持的 TTS 引擎: {tts_engine}。"
                    f"支持的引擎: edge-tts, minimax, volcengine"
                )

        # 验证布尔值
        bool_fields = [
            "enable_tts",
            "enable_video",
            "save_intermediate",
            "enable_audio_cache",
            "llm_enabled",
        ]
        for field in bool_fields:
            if field in config:
                if not isinstance(config[field], bool):
                    raise ValueError(f"'{field}' 必须是布尔值（true/false）")

        # 验证整数值
        int_fields = [
            "video_width",
            "video_height",
            "video_fps",
            "video_crf",
            "video_gop_seconds",
            "audio_sample_rate",
            "audio_channels",
        ]
        for field in int_fields:
            if field in config:
                if not isinstance(config[field], int) or config[field] <= 0:
                    raise ValueError(f"'{field}' 必须是正整数")

        # 验证缓存过期天数（需要单独处理因为有额外的约束）
        if "audio_cache_expiry_days" in config:
            if not isinstance(config["audio_cache_expiry_days"], int):
                raise ValueError("'audio_cache_expiry_days' 必须是整数")
            if config["audio_cache_expiry_days"] < 1:
                raise ValueError("'audio_cache_expiry_days' 必须大于等于 1")

        # 验证 LLM 引擎
        if "llm_engine" in config:
            llm_engine = config["llm_engine"]
            if llm_engine not in ["qwen", "minimax"]:
                raise ValueError(
                    f"不支持的 LLM 引擎: {llm_engine}。"
                    f"支持的引擎: qwen, minimax"
                )

        # 验证 LLM 模式
        if "llm_mode" in config:
            llm_mode = config["llm_mode"]
            if llm_mode not in ["per-page", "whole-document"]:
                raise ValueError(
                    f"不支持的 LLM 模式: {llm_mode}。"
                    f"支持的模式: per-page, whole-document"
                )

        # 验证 llm_options 类型
        if "llm_options" in config:
            if not isinstance(config["llm_options"], dict):
                raise ValueError("'llm_options' 必须是对象/字典")

        logger.debug("配置验证通过")

    @staticmethod
    def merge_with_cli_args(
        config: Dict[str, Any], cli_args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        将配置文件与命令行参数合并

        命令行参数优先级更高。

        参数:
            config: 配置文件中的配置
            cli_args: 命令行参数

        返回:
            合并后的配置
        """
        merged = config.copy()

        # 合并 CLI 参数（跳过 None 值）
        for key, value in cli_args.items():
            if value is not None:
                merged[key] = value

        return merged


class ConfigValidator:
    """配置验证器"""

    # 支持的顶级字段
    SUPPORTED_FIELDS = {
        # 输入输出
        "input",
        "output",
        # 功能开关
        "enable_tts",
        "enable_video",
        "save_intermediate",
        # TTS 配置
        "tts_engine",
        "tts_voice",
        "tts_rate",
        "tts_options",
        # 缓存配置
        "enable_audio_cache",
        "audio_cache_dir",
        "audio_cache_expiry_days",
        # OCR 配置
        "ocr_engine",
        # LLM 配置
        "llm_enabled",
        "llm_engine",
        "llm_mode",
        "llm_options",
        # 图像转换配置
        "image_converter",
        # 视频配置
        "video_width",
        "video_height",
        "video_fps",
        "video_codec",
        "video_preset",
        "video_crf",
        "video_pixel_format",
        "video_gop_seconds",
        "video_profile",
        "audio_codec",
        "audio_bitrate",
        "audio_sample_rate",
        "audio_channels",
        "audio_loudness_lufs",
    }

    @staticmethod
    def validate_schema(config: Dict[str, Any]) -> None:
        """
        验证配置的架构

        参数:
            config: 配置字典

        抛出异常:
            ValueError: 配置架构不有效
        """
        # 检查是否有不支持的字段
        unsupported_fields = set(config.keys()) - ConfigValidator.SUPPORTED_FIELDS
        if unsupported_fields:
            logger.warning(
                f"配置文件中存在不支持的字段: {', '.join(sorted(unsupported_fields))}"
            )

        # 验证嵌套对象
        if "tts_options" in config:
            if not isinstance(config["tts_options"], dict):
                raise ValueError("'tts_options' 必须是对象/字典")


def load_config_file(config_path: str) -> Dict[str, Any]:
    """
    加载并验证配置文件的便捷函数

    参数:
        config_path: 配置文件路径

    返回:
        经过验证的配置字典

    抛出异常:
        FileNotFoundError: 配置文件不存在
        ValueError: 配置无效
    """
    logger.debug(f"加载配置文件: {config_path}")

    # 加载配置
    config = ConfigLoader.load(Path(config_path))

    # 验证架构
    ConfigValidator.validate_schema(config)

    # 验证内容
    ConfigLoader.validate(config)

    logger.debug(f"配置文件加载成功，包含 {len(config)} 个字段")

    return config
