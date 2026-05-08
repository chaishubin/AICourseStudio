"""
测试配置文件功能

测试覆盖：
- 配置文件加载（JSON/YAML）
- 配置验证
- 配置转换
- 配置合并
"""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from vidppt.utils.config_loader import ConfigLoader, ConfigValidator, load_config_file
from vidppt.utils.config_converter import ConfigConverter
from vidppt.core.models import ProcessConfig


class TestConfigLoader:
    """测试配置加载器"""

    def test_load_json_config(self, temp_dir):
        """测试加载 JSON 配置文件"""
        # 创建测试配置文件
        config_data = {
            "input": str(temp_dir / "test.pptx"),
            "output": "outputs",
            "tts_engine": "minimax",
        }
        config_file = temp_dir / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        # 加载配置
        loaded = ConfigLoader.load(config_file)

        assert loaded["input"] == str(temp_dir / "test.pptx")
        assert loaded["tts_engine"] == "minimax"

    def test_load_yaml_config(self, temp_dir):
        """测试加载 YAML 配置文件"""
        pytest.importorskip("yaml")

        import yaml

        # 创建测试配置文件
        config_data = {
            "input": str(temp_dir / "test.pptx"),
            "output": "outputs",
            "tts_engine": "edge-tts",
        }
        config_file = temp_dir / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # 加载配置
        loaded = ConfigLoader.load(config_file)

        assert loaded["input"] == str(temp_dir / "test.pptx")
        assert loaded["tts_engine"] == "edge-tts"

    def test_load_nonexistent_file(self, temp_dir):
        """测试加载不存在的文件"""
        config_file = temp_dir / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            ConfigLoader.load(config_file)

    def test_load_unsupported_format(self, temp_dir):
        """测试加载不支持的文件格式"""
        config_file = temp_dir / "config.txt"
        config_file.write_text("test")

        with pytest.raises(ValueError, match="不支持的配置文件格式"):
            ConfigLoader.load(config_file)

    def test_load_invalid_json(self, temp_dir):
        """测试加载无效的 JSON 文件"""
        config_file = temp_dir / "config.json"
        config_file.write_text("{invalid json}")

        with pytest.raises(ValueError):
            ConfigLoader.load(config_file)

    def test_load_json_root_not_dict(self, temp_dir):
        """测试加载根不是字典的 JSON"""
        config_file = temp_dir / "config.json"
        config_file.write_text('["array", "not", "dict"]')

        with pytest.raises(ValueError, match="根必须是对象"):
            ConfigLoader.load(config_file)

    def test_load_empty_yaml(self, temp_dir):
        """测试加载空 YAML 文件"""
        pytest.importorskip("yaml")

        config_file = temp_dir / "config.yaml"
        config_file.write_text("")

        loaded = ConfigLoader.load(config_file)
        assert loaded == {}


class TestConfigValidator:
    """测试配置验证器"""

    def test_validate_schema_valid(self):
        """测试验证有效的配置架构"""
        config = {
            "input": "test.pptx",
            "tts_engine": "minimax",
            "enable_tts": True,
        }
        # 应该不抛出异常
        ConfigValidator.validate_schema(config)

    def test_validate_schema_unsupported_fields(self, caplog):
        """测试检测不支持的字段"""
        config = {
            "input": "test.pptx",
            "unsupported_field": "value",
        }
        ConfigValidator.validate_schema(config)
        # 应该有警告但不抛出异常

    def test_validate_content_empty_input_string(self):
        """测试验证空的输入字符串"""
        config = {
            "input": "",  # 空字符串
        }

        with pytest.raises(ValueError, match="'input' 字段不能为空"):
            ConfigLoader.validate(config)

    def test_validate_content_invalid_tts_engine(self):
        """测试验证无效的 TTS 引擎"""
        config = {
            "input": "test.pptx",
            "tts_engine": "invalid-engine",
        }

        with pytest.raises(ValueError, match="不支持的 TTS 引擎"):
            ConfigLoader.validate(config)

    def test_validate_content_invalid_bool_field(self):
        """测试验证无效的布尔字段"""
        config = {
            "input": "test.pptx",
            "enable_tts": "yes",  # 应该是布尔值
        }

        with pytest.raises(ValueError, match="必须是布尔值"):
            ConfigLoader.validate(config)

    def test_validate_content_invalid_int_field(self):
        """测试验证无效的整数字段"""
        config = {
            "input": "test.pptx",
            "video_fps": "24",  # 应该是整数
        }

        with pytest.raises(ValueError, match="必须是正整数"):
            ConfigLoader.validate(config)

    def test_validate_content_invalid_cache_expiry(self):
        """测试验证无效的缓存过期天数"""
        config = {
            "input": "test.pptx",
            "audio_cache_expiry_days": 0,
        }

        with pytest.raises(ValueError, match="必须大于等于 1"):
            ConfigLoader.validate(config)


class TestConfigConverter:
    """测试配置转换器"""

    def test_convert_minimal_config(self, temp_dir):
        """测试转换最小化配置"""
        # 创建测试输入文件
        input_file = temp_dir / "test.pptx"
        input_file.write_text("test")

        config_dict = {"input": str(input_file)}

        config = ConfigConverter.to_process_config(config_dict)

        assert config.input_path == input_file
        assert config.output_dir == Path("outputs")
        assert config.enable_tts is True
        assert config.tts_engine == "edge-tts"

    def test_convert_full_config(self, temp_dir):
        """测试转换完整配置"""
        input_file = temp_dir / "test.pptx"
        input_file.write_text("test")

        config_dict = {
            "input": str(input_file),
            "output": "custom_output",
            "enable_tts": False,
            "enable_video": False,
            "save_intermediate": False,
            "tts_engine": "minimax",
            "tts_rate": "+20%",
            "tts_options": {"voice_id": "male-qn-qingse", "emotion": "happy"},
            "enable_audio_cache": False,
            "audio_cache_expiry_days": 7,
            "video_fps": 30,
        }

        config = ConfigConverter.to_process_config(config_dict)

        assert config.input_path == input_file
        assert config.output_dir == Path("custom_output")
        assert config.enable_tts is False
        assert config.enable_video is False
        assert config.save_intermediate is False
        assert config.tts_engine == "minimax"
        assert config.tts_voice is None  # minimax 不使用 tts_voice
        assert config.tts_options["voice_id"] == "male-qn-qingse"
        assert config.tts_rate == "+20%"
        assert config.tts_options["emotion"] == "happy"
        assert config.enable_audio_cache is False
        assert config.audio_cache_expiry_days == 7
        assert config.video_fps == 30

    def test_convert_missing_input_file(self, temp_dir):
        """测试转换时输入文件不存在"""
        config_dict = {"input": str(temp_dir / "nonexistent.pptx")}

        with pytest.raises(ValueError, match="输入文件不存在"):
            ConfigConverter.to_process_config(config_dict)

    def test_convert_missing_input_field(self):
        """测试转换时缺少输入字段"""
        config_dict = {"output": "outputs"}

        with pytest.raises(ValueError, match="缺少必填字段 'input'"):
            ConfigConverter.to_process_config(config_dict)

    def test_resolve_path_home_directory(self):
        """测试解析包含 ~ 的路径"""
        path = ConfigConverter._resolve_path("~/cache/vidppt")
        assert "cache/vidppt" in str(path)
        assert "~" not in str(path)

    def test_resolve_path_none(self):
        """测试解析 None 路径"""
        path = ConfigConverter._resolve_path(None)
        assert path is None

    def test_resolve_path_relative(self):
        """测试解析相对路径"""
        path = ConfigConverter._resolve_path("./outputs")
        assert path == Path("./outputs").expanduser()

    def test_render_engine_from_config_dict(self, temp_dir):
        """验证 ConfigConverter 正确传递 render_engine"""
        input_file = temp_dir / "test.pptx"
        input_file.write_text("test")

        config_dict = {"input": str(input_file), "render_engine": "libreoffice"}
        config = ConfigConverter.to_process_config(config_dict)

        assert config.render_engine == "libreoffice"

    def test_render_engine_default_value(self, temp_dir):
        """验证 ConfigConverter 默认 render_engine 为 spire"""
        input_file = temp_dir / "test.pptx"
        input_file.write_text("test")

        config_dict = {"input": str(input_file)}
        config = ConfigConverter.to_process_config(config_dict)

        assert config.render_engine == "spire"


class TestLoadConfigFile:
    """测试便捷函数"""

    def test_load_config_file_json(self, temp_dir):
        """测试通过便捷函数加载 JSON"""
        # 创建输入文件
        input_file = temp_dir / "test.pptx"
        input_file.write_text("test")

        # 创建配置文件
        config_data = {
            "input": str(input_file),
            "tts_engine": "minimax",
        }
        config_file = temp_dir / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        # 加载配置
        config = load_config_file(str(config_file))

        assert config["input"] == str(input_file)
        assert config["tts_engine"] == "minimax"

    def test_load_config_file_invalid(self, temp_dir):
        """测试加载无效的配置文件"""
        config_file = temp_dir / "config.json"
        config_file.write_text("{invalid}")

        with pytest.raises(ValueError):
            load_config_file(str(config_file))


class TestConfigMerge:
    """测试配置合并"""

    def test_merge_config_cli_priority(self, temp_dir):
        """测试 CLI 参数优先于配置文件"""
        input_file = temp_dir / "test.pptx"
        input_file.write_text("test")

        file_config = {
            "input": str(input_file),
            "tts_engine": "edge-tts",
            "tts_voice": "male",
        }

        cli_args = {
            "tts_voice": "female",
            "tts_rate": "+20%",
        }

        merged = ConfigLoader.merge_with_cli_args(file_config, cli_args)

        assert merged["input"] == str(input_file)
        assert merged["tts_engine"] == "edge-tts"
        assert merged["tts_voice"] == "female"  # CLI 覆盖了
        assert merged["tts_rate"] == "+20%"

    def test_merge_config_none_values_ignored(self, temp_dir):
        """测试 None 值不覆盖文件配置"""
        input_file = temp_dir / "test.pptx"
        input_file.write_text("test")

        file_config = {
            "input": str(input_file),
            "tts_engine": "minimax",
        }

        cli_args = {
            "tts_voice": None,  # None 值应该被忽略
        }

        merged = ConfigLoader.merge_with_cli_args(file_config, cli_args)

        assert "tts_voice" not in merged  # None 值被忽略
        assert merged["tts_engine"] == "minimax"
