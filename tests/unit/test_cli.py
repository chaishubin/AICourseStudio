"""
测试 CLI 命令行接口

测试覆盖:
- 参数解析
- MiniMax 选项处理
- EdgeTTS 选项处理
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from vidppt.cli import main


class TestCLIArgumentParsing:
    """测试命令行参数解析"""

    def test_basic_arguments(self):
        """测试基础参数"""
        with patch("sys.argv", ["vidppt", "test.pptx"]):
            with patch("vidppt.cli.Pipeline") as mock_pipeline:
                with patch("pathlib.Path.exists", return_value=True):
                    try:
                        main()
                    except SystemExit:
                        pass

                    # 验证 Pipeline 被调用
                    assert mock_pipeline.called

    def test_output_directory_argument(self):
        """测试输出目录参数"""
        with patch("sys.argv", ["vidppt", "test.pptx", "-o", "my_output"]):
            with patch("vidppt.cli.Pipeline") as mock_pipeline:
                with patch("pathlib.Path.exists", return_value=True):
                    try:
                        main()
                    except SystemExit:
                        pass

                    # 获取调用时的参数
                    call_args = mock_pipeline.call_args
                    config = call_args[0][0]
                    assert str(config.output_dir) == "my_output"

    def test_no_tts_flag(self):
        """测试跳过 TTS 标志"""
        with patch("sys.argv", ["vidppt", "test.pptx", "--no-tts"]):
            with patch("vidppt.cli.Pipeline"):
                with patch("pathlib.Path.exists", return_value=True):
                    try:
                        main()
                    except SystemExit:
                        pass

    def test_tts_engine_choice(self):
        """测试 TTS 引擎选择"""
        with patch("sys.argv", ["vidppt", "test.pptx", "--tts-engine", "minimax"]):
            with patch("vidppt.cli.Pipeline") as mock_pipeline:
                with patch("pathlib.Path.exists", return_value=True):
                    try:
                        main()
                    except SystemExit:
                        pass

                    call_args = mock_pipeline.call_args
                    config = call_args[0][0]
                    assert config.tts_engine == "minimax"


class TestMiniMaxCLIOptions:
    """测试 MiniMax 命令行选项"""

    def test_minimax_emotion_option(self):
        """测试 MiniMax 情感选项"""
        with patch(
            "sys.argv",
            [
                "vidppt",
                "test.pptx",
                "--tts-engine",
                "minimax",
                "--minimax-emotion",
                "happy",
            ],
        ):
            with patch("vidppt.cli.Pipeline") as mock_pipeline:
                with patch("pathlib.Path.exists", return_value=True):
                    try:
                        main()
                    except SystemExit:
                        pass

                    call_args = mock_pipeline.call_args
                    config = call_args[0][0]
                    assert config.tts_options["emotion"] == "happy"

    def test_minimax_sample_rate_option(self):
        """测试 MiniMax 采样率选项"""
        with patch(
            "sys.argv",
            [
                "vidppt",
                "test.pptx",
                "--tts-engine",
                "minimax",
                "--minimax-sample-rate",
                "44100",
            ],
        ):
            with patch("vidppt.cli.Pipeline") as mock_pipeline:
                with patch("pathlib.Path.exists", return_value=True):
                    try:
                        main()
                    except SystemExit:
                        pass

                    call_args = mock_pipeline.call_args
                    config = call_args[0][0]
                    assert config.tts_options["sample_rate"] == 44100

    def test_minimax_bitrate_option(self):
        """测试 MiniMax 比特率选项"""
        with patch(
            "sys.argv",
            [
                "vidppt",
                "test.pptx",
                "--tts-engine",
                "minimax",
                "--minimax-bitrate",
                "256000",
            ],
        ):
            with patch("vidppt.cli.Pipeline") as mock_pipeline:
                with patch("pathlib.Path.exists", return_value=True):
                    try:
                        main()
                    except SystemExit:
                        pass

                    call_args = mock_pipeline.call_args
                    config = call_args[0][0]
                    assert config.tts_options["bitrate"] == 256000

    def test_minimax_format_option(self):
        """测试 MiniMax 格式选项"""
        with patch(
            "sys.argv",
            [
                "vidppt",
                "test.pptx",
                "--tts-engine",
                "minimax",
                "--minimax-format",
                "wav",
            ],
        ):
            with patch("vidppt.cli.Pipeline") as mock_pipeline:
                with patch("pathlib.Path.exists", return_value=True):
                    try:
                        main()
                    except SystemExit:
                        pass

                    call_args = mock_pipeline.call_args
                    config = call_args[0][0]
                    assert config.tts_options["audio_format"] == "wav"

    def test_minimax_all_options_combined(self):
        """测试 MiniMax 所有选项组合"""
        with patch(
            "sys.argv",
            [
                "vidppt",
                "test.pptx",
                "--tts-engine",
                "minimax",
                "--minimax-emotion",
                "peaceful",
                "--minimax-sample-rate",
                "44100",
                "--minimax-bitrate",
                "256000",
                "--minimax-format",
                "wav",
            ],
        ):
            with patch("vidppt.cli.Pipeline") as mock_pipeline:
                with patch("pathlib.Path.exists", return_value=True):
                    try:
                        main()
                    except SystemExit:
                        pass

                    call_args = mock_pipeline.call_args
                    config = call_args[0][0]
                    assert config.tts_options["emotion"] == "peaceful"
                    assert config.tts_options["sample_rate"] == 44100
                    assert config.tts_options["bitrate"] == 256000
                    assert config.tts_options["audio_format"] == "wav"


class TestEdgeTTSCLIOptions:
    """测试 EdgeTTS 命令行选项"""

    def test_voice_option(self):
        """测试声音选项"""
        with patch(
            "sys.argv", ["vidppt", "test.pptx", "--voice", "zh-CN-YunyangNeural"]
        ):
            with patch("vidppt.cli.Pipeline") as mock_pipeline:
                with patch("pathlib.Path.exists", return_value=True):
                    try:
                        main()
                    except SystemExit:
                        pass

                    call_args = mock_pipeline.call_args
                    config = call_args[0][0]
                    assert config.tts_voice == "zh-CN-YunyangNeural"

    def test_rate_option(self):
        """测试语速选项"""
        with patch("sys.argv", ["vidppt", "test.pptx", "--rate", "+20%"]):
            with patch("vidppt.cli.Pipeline") as mock_pipeline:
                with patch("pathlib.Path.exists", return_value=True):
                    try:
                        main()
                    except SystemExit:
                        pass

                    call_args = mock_pipeline.call_args
                    config = call_args[0][0]
                    assert config.tts_rate == "+20%"


class TestCLIEdgeCases:
    """测试 CLI 边界情况"""

    def test_render_engine_default(self):
        """测试默认 render_engine 为 spire"""
        with patch("sys.argv", ["vidppt", "test.pptx"]):
            with patch("vidppt.cli.Pipeline") as mock_pipeline:
                with patch("pathlib.Path.exists", return_value=True):
                    try:
                        main()
                    except SystemExit:
                        pass

                    call_args = mock_pipeline.call_args
                    config = call_args[0][0]
                    assert config.render_engine == "spire"

    def test_render_engine_libreoffice(self):
        """测试 --render-engine libreoffice 时 config.render_engine == libreoffice"""
        with patch("sys.argv", ["vidppt", "test.pptx", "--render-engine", "libreoffice"]):
            with patch("vidppt.cli.Pipeline") as mock_pipeline:
                with patch("pathlib.Path.exists", return_value=True):
                    try:
                        main()
                    except SystemExit:
                        pass

                    call_args = mock_pipeline.call_args
                    config = call_args[0][0]
                    assert config.render_engine == "libreoffice"

    def test_no_tts_options_for_edgetts(self):
        """测试 EdgeTTS 不需要 tts_options"""
        with patch("sys.argv", ["vidppt", "test.pptx", "--tts-engine", "edge-tts"]):
            with patch("vidppt.cli.Pipeline") as mock_pipeline:
                with patch("pathlib.Path.exists", return_value=True):
                    try:
                        main()
                    except SystemExit:
                        pass

                    call_args = mock_pipeline.call_args
                    config = call_args[0][0]
                    assert config.tts_options == {}

    def test_default_minimax_options(self):
        """测试 MiniMax 默认选项"""
        with patch("sys.argv", ["vidppt", "test.pptx", "--tts-engine", "minimax"]):
            with patch("vidppt.cli.Pipeline") as mock_pipeline:
                with patch("pathlib.Path.exists", return_value=True):
                    try:
                        main()
                    except SystemExit:
                        pass

                    call_args = mock_pipeline.call_args
                    config = call_args[0][0]
                    # 检查默认值
                    assert config.tts_options["emotion"] == "neutral"
                    assert config.tts_options["sample_rate"] == 32000
                    assert config.tts_options["bitrate"] == 128000
                    assert config.tts_options["audio_format"] == "mp3"

    def test_feature_flags_combination(self):
        """测试功能标志组合"""
        with patch(
            "sys.argv",
            ["vidppt", "test.pptx", "--no-tts", "--no-video", "--no-intermediate"],
        ):
            with patch("vidppt.cli.Pipeline") as mock_pipeline:
                with patch("pathlib.Path.exists", return_value=True):
                    try:
                        main()
                    except SystemExit:
                        pass

                    call_args = mock_pipeline.call_args
                    config = call_args[0][0]
                    assert config.enable_tts is False
                    assert config.enable_video is False
                    assert config.save_intermediate is False
