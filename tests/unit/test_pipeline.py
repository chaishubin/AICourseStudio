"""
测试主流程 Pipeline

测试覆盖：
- Pipeline 初始化
- TTS 引擎创建
- 完整处理流程
- 错误处理
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from vidppt.pipeline import Pipeline
from vidppt.core.models import ProcessConfig, DocumentContent, PageContent


class TestPipelineInit:
    """测试 Pipeline 初始化"""

    def test_pipeline_init(self, temp_dir):
        """测试 Pipeline 初始化"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            tts_engine="edge-tts",
        )

        pipeline = Pipeline(config)

        assert pipeline.config == config
        assert pipeline.tts_engine is not None
        assert pipeline.llm_engine is None  # LLM 默认不启用

    def test_pipeline_init_with_llm(self, temp_dir):
        """测试 Pipeline 初始化时启用 LLM"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            tts_engine="edge-tts",
            llm_enabled=True,
            llm_engine="openai",
            llm_options={"api_key": "test-key"},
        )

        pipeline = Pipeline(config)

        assert pipeline.llm_engine is not None
        from vidppt.engines.llm.openai_llm_engine import OpenAILLMEngine
        assert isinstance(pipeline.llm_engine, OpenAILLMEngine)

    def test_create_edge_tts_engine(self, temp_dir):
        """测试创建 Edge TTS 引擎"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            tts_engine="edge-tts",
        )

        pipeline = Pipeline(config)

        from vidppt.engines.tts.edge_tts_engine import EdgeTTSEngine

        assert isinstance(pipeline.tts_engine, EdgeTTSEngine)

    def test_unsupported_tts_engine(self, temp_dir):
        """测试不支持的 TTS 引擎"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            tts_engine="unsupported-engine",
        )

        with pytest.raises(ValueError) as exc_info:
            Pipeline(config)

        assert "不支持的 TTS 引擎" in str(exc_info.value)

    def test_unsupported_llm_engine(self, temp_dir):
        """测试不支持的 LLM 引擎"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            llm_enabled=True,
            llm_engine="unsupported-llm",
        )

        with pytest.raises(ValueError) as exc_info:
            Pipeline(config)

        assert "不支持的 LLM 引擎" in str(exc_info.value)


class TestPipelineRun:
    """测试 Pipeline 执行流程"""

    def test_run_file_not_exists(self, temp_dir):
        """测试文件不存在时的错误处理"""
        config = ProcessConfig(
            input_path=temp_dir / "nonexistent.pptx", output_dir=temp_dir / "output"
        )

        pipeline = Pipeline(config)

        # 应该抛出 FileNotFoundError
        with pytest.raises(FileNotFoundError) as exc_info:
            pipeline.run()

        assert "输入文件不存在" in str(exc_info.value)

    def test_run_unsupported_file_type(self, temp_dir):
        """测试不支持的文件类型"""
        # 创建一个不支持的文件
        unsupported_file = temp_dir / "test.xyz"
        unsupported_file.write_text("test")

        config = ProcessConfig(
            input_path=unsupported_file, output_dir=temp_dir / "output"
        )

        pipeline = Pipeline(config)

        # 应该抛出 ValueError
        with pytest.raises(ValueError) as exc_info:
            pipeline.run()

        assert "不支持的文件类型" in str(exc_info.value)

    def test_run_full_workflow(self, temp_dir):
        """测试完整工作流"""
        # 创建测试文件
        test_file = temp_dir / "test.pptx"
        test_file.write_text("test")

        config = ProcessConfig(
            input_path=test_file,
            output_dir=temp_dir / "output",
            enable_tts=True,
            enable_video=True,
        )

        # Mock 处理器
        mock_processor = Mock()
        mock_content = DocumentContent(
            pages=[
                PageContent(
                    page_number=1, text="测试文本", slide_image=Path("slide1.png")
                )
            ]
        )
        mock_processor.process.return_value = mock_content

        mock_processor_class = Mock(return_value=mock_processor)
        mock_processor_class.__name__ = "MockProcessor"

        pipeline = Pipeline(config)

        with patch(
            "vidppt.pipeline.ProcessorRegistry.get_processor"
        ) as mock_get_processor:
            mock_get_processor.return_value = mock_processor_class

            with patch.object(pipeline, "_generate_audio") as mock_generate_audio:
                with patch.object(pipeline, "_compose_video") as mock_compose_video:
                    with patch.object(pipeline, "_cleanup_temp_files") as mock_cleanup:
                        pipeline.run()

                        # 验证调用
                        mock_processor.process.assert_called_once_with(config)
                        mock_generate_audio.assert_called_once()
                        mock_compose_video.assert_called_once()

    def test_run_without_tts(self, temp_dir):
        """测试禁用 TTS 的流程"""
        test_file = temp_dir / "test.pptx"
        test_file.write_text("test")

        config = ProcessConfig(
            input_path=test_file,
            output_dir=temp_dir / "output",
            enable_tts=False,
            enable_video=True,
        )

        mock_processor = Mock()
        mock_content = DocumentContent(pages=[])
        mock_processor.process.return_value = mock_content

        mock_processor_class = Mock(return_value=mock_processor)
        mock_processor_class.__name__ = "MockProcessor"

        pipeline = Pipeline(config)

        with patch(
            "vidppt.pipeline.ProcessorRegistry.get_processor"
        ) as mock_get_processor:
            mock_get_processor.return_value = mock_processor_class

            with patch.object(pipeline, "_generate_audio") as mock_generate_audio:
                with patch.object(pipeline, "_compose_video") as mock_compose_video:
                    pipeline.run()

                    # TTS 不应该被调用
                    mock_generate_audio.assert_not_called()
                    # 视频应该被调用
                    mock_compose_video.assert_called_once()

    def test_run_without_video(self, temp_dir):
        """测试禁用视频合成的流程"""
        test_file = temp_dir / "test.pptx"
        test_file.write_text("test")

        config = ProcessConfig(
            input_path=test_file,
            output_dir=temp_dir / "output",
            enable_tts=True,
            enable_video=False,
        )

        mock_processor = Mock()
        mock_content = DocumentContent(pages=[])
        mock_processor.process.return_value = mock_content

        mock_processor_class = Mock(return_value=mock_processor)
        mock_processor_class.__name__ = "MockProcessor"

        pipeline = Pipeline(config)

        with patch(
            "vidppt.pipeline.ProcessorRegistry.get_processor"
        ) as mock_get_processor:
            mock_get_processor.return_value = mock_processor_class

            with patch.object(pipeline, "_generate_audio") as mock_generate_audio:
                with patch.object(pipeline, "_compose_video") as mock_compose_video:
                    pipeline.run()

                    # TTS 应该被调用
                    mock_generate_audio.assert_called_once()
                    # 视频不应该被调用
                    mock_compose_video.assert_not_called()


class TestPipelineGenerateAudio:
    """测试音频生成"""

    def test_generate_audio_with_intermediate_files(self, temp_dir):
        """测试保存中间文件时的音频生成"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            save_intermediate=True,
            tts_voice="zh-CN-XiaoxiaoNeural",
            tts_rate="+0%",
        )

        pipeline = Pipeline(config)

        content = DocumentContent(
            pages=[
                PageContent(page_number=1, text="第一页"),
                PageContent(page_number=2, text="第二页"),
            ]
        )

        # Mock TTS engine with proper async mock
        mock_tts = Mock()

        # Create an async function that does nothing
        async def mock_batch_convert(*args, **kwargs):
            pass

        mock_tts.batch_convert = AsyncMock(side_effect=mock_batch_convert)
        pipeline.tts_engine = mock_tts

        # 创建进度跟踪器
        from vidppt.utils.progress import ProgressTracker

        progress = ProgressTracker(total_pages=len(content.pages))

        pipeline._generate_audio(content, progress)

        # 验证调用
        mock_tts.batch_convert.assert_called_once()

        # 验证音频路径已设置
        assert content.pages[0].audio == temp_dir / "output" / "1" / "audio.mp3"
        assert content.pages[1].audio == temp_dir / "output" / "2" / "audio.mp3"

    def test_generate_audio_without_intermediate_files(self, temp_dir):
        """测试不保存中间文件时的音频生成"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            save_intermediate=False,
        )

        pipeline = Pipeline(config)

        content = DocumentContent(pages=[PageContent(page_number=1, text="测试")])

        # Mock TTS engine with proper async mock
        mock_tts = Mock()

        async def mock_batch_convert(*args, **kwargs):
            pass

        mock_tts.batch_convert = AsyncMock(side_effect=mock_batch_convert)
        pipeline.tts_engine = mock_tts

        # 创建进度跟踪器
        from vidppt.utils.progress import ProgressTracker

        progress = ProgressTracker(total_pages=len(content.pages))

        pipeline._generate_audio(content, progress)

        # 验证使用临时路径
        assert "_temp_audio_" in str(content.pages[0].audio)

    def test_generate_audio_error_handling(self, temp_dir):
        """测试音频生成错误处理"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx", output_dir=temp_dir / "output"
        )

        pipeline = Pipeline(config)

        content = DocumentContent(pages=[PageContent(page_number=1, text="测试")])

        # Mock TTS 引擎抛出异常
        mock_tts = Mock()
        mock_tts.batch_convert.side_effect = Exception("网络错误")

        # 创建进度跟踪器
        from vidppt.utils.progress import ProgressTracker

        progress = ProgressTracker(total_pages=len(content.pages))

        with patch("asyncio.run") as mock_asyncio_run:
            mock_asyncio_run.side_effect = Exception("网络错误")
            pipeline.tts_engine = mock_tts

            # 应该捕获异常，不会崩溃
            pipeline._generate_audio(content, progress)


class TestPipelineComposeVideo:
    """测试视频合成"""

    def test_compose_video(self, temp_dir):
        """测试视频合成"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx", output_dir=temp_dir / "output"
        )

        pipeline = Pipeline(config)

        content = DocumentContent(
            pages=[
                PageContent(
                    page_number=1,
                    text="测试",
                    slide_image=Path("slide1.png"),
                    audio=Path("audio1.mp3"),
                )
            ]
        )

        with patch("vidppt.pipeline.VideoComposer.compose") as mock_compose:
            # 创建进度跟踪器
            from vidppt.utils.progress import ProgressTracker

            progress = ProgressTracker(total_pages=len(content.pages))

            pipeline._compose_video(content, progress)

            # 验证调用
            mock_compose.assert_called_once()
            call_args = mock_compose.call_args[0]
            assert call_args[0] == content
            assert call_args[1] == config

    def test_compose_video_error_handling(self, temp_dir):
        """测试视频合成错误处理"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx", output_dir=temp_dir / "output"
        )

        pipeline = Pipeline(config)
        content = DocumentContent(pages=[])

        with patch("vidppt.pipeline.VideoComposer.compose") as mock_compose:
            mock_compose.side_effect = Exception("合成错误")

            # 创建进度跟踪器
            from vidppt.utils.progress import ProgressTracker

            progress = ProgressTracker(total_pages=len(content.pages))

            # 应该捕获异常
            pipeline._compose_video(content, progress)


class TestPipelineCleanup:
    """测试临时文件清理"""

    def test_cleanup_temp_files(self, temp_dir):
        """测试清理临时文件"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx", output_dir=temp_dir / "output"
        )

        # 创建临时文件
        config.output_dir.mkdir(parents=True, exist_ok=True)
        (config.output_dir / "_temp_audio_1.mp3").write_text("temp")
        (config.output_dir / "_temp_slide_1.png").write_text("temp")
        (config.output_dir / "normal_file.txt").write_text("keep")

        pipeline = Pipeline(config)

        # 创建进度跟踪器
        from vidppt.utils.progress import ProgressTracker

        progress = ProgressTracker(total_pages=1)

        pipeline._cleanup_temp_files(progress)

        # 临时文件应该被删除
        assert not (config.output_dir / "_temp_audio_1.mp3").exists()
        assert not (config.output_dir / "_temp_slide_1.png").exists()

        # 正常文件应该保留
        assert (config.output_dir / "normal_file.txt").exists()


class TestPipelineSummarizeContent:
    """测试 LLM 文本摘要"""

    def test_summarize_content_per_page(self, temp_dir):
        """测试逐页摘要模式"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            llm_enabled=True,
            llm_engine="openai",
            llm_mode="per-page",
            llm_options={"api_key": "test-key"},
        )

        pipeline = Pipeline(config)

        # Mock LLM 引擎
        mock_llm = Mock()
        mock_llm.summarize.side_effect = lambda text, **kw: f"改写: {text}"
        pipeline.llm_engine = mock_llm

        content = DocumentContent(
            pages=[
                PageContent(page_number=1, text="第一页"),
                PageContent(page_number=2, text="第二页"),
                PageContent(page_number=3, text=""),  # 空页
            ]
        )

        from vidppt.utils.progress import ProgressTracker

        progress = ProgressTracker(total_pages=3, enable_progress=False)

        pipeline._summarize_content(content, progress)

        # 验证原文保存到 metadata
        assert content.pages[0].metadata["original_text"] == "第一页"
        assert content.pages[1].metadata["original_text"] == "第二页"
        assert content.pages[2].metadata["original_text"] == ""

        # 验证文本被改写
        assert content.pages[0].text == "改写: 第一页"
        assert content.pages[1].text == "改写: 第二页"
        # 空页不调用 summarize
        assert content.pages[2].text == ""

        # summarize 只对有文本的页调用
        assert mock_llm.summarize.call_count == 2

    def test_summarize_content_whole_document(self, temp_dir):
        """测试整文档摘要模式"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            llm_enabled=True,
            llm_engine="openai",
            llm_mode="whole-document",
            llm_options={"api_key": "test-key"},
        )

        pipeline = Pipeline(config)

        # Mock LLM 引擎
        mock_llm = Mock()
        mock_llm.summarize_document.return_value = "整文档摘要文本"
        pipeline.llm_engine = mock_llm

        content = DocumentContent(
            pages=[
                PageContent(page_number=1, text="第一页"),
                PageContent(page_number=2, text="第二页"),
                PageContent(page_number=3, text="第三页"),
            ]
        )

        from vidppt.utils.progress import ProgressTracker

        progress = ProgressTracker(total_pages=3, enable_progress=False)

        pipeline._summarize_content(content, progress)

        # 摘要放第一页，其余页 text 置空
        assert content.pages[0].text == "整文档摘要文本"
        assert content.pages[1].text == ""
        assert content.pages[2].text == ""

        # 原文保存到 metadata
        assert content.pages[0].metadata["original_text"] == "第一页"
        assert content.pages[1].metadata["original_text"] == "第二页"

        mock_llm.summarize_document.assert_called_once()

    def test_summarize_content_error_raises(self, temp_dir):
        """测试 LLM 摘要失败时抛出异常"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            llm_enabled=True,
            llm_engine="openai",
            llm_mode="per-page",
            llm_options={"api_key": "test-key"},
        )

        pipeline = Pipeline(config)

        mock_llm = Mock()
        mock_llm.summarize.side_effect = RuntimeError("API 调用失败")
        pipeline.llm_engine = mock_llm

        content = DocumentContent(
            pages=[PageContent(page_number=1, text="测试")]
        )

        from vidppt.utils.progress import ProgressTracker

        progress = ProgressTracker(total_pages=1, enable_progress=False)

        with pytest.raises(RuntimeError, match="API 调用失败"):
            pipeline._summarize_content(content, progress)

    def test_run_with_llm_enabled(self, temp_dir):
        """测试启用 LLM 的完整流程"""
        test_file = temp_dir / "test.pptx"
        test_file.write_text("test")

        config = ProcessConfig(
            input_path=test_file,
            output_dir=temp_dir / "output",
            llm_enabled=True,
            llm_engine="openai",
            llm_mode="per-page",
            llm_options={"api_key": "test-key"},
            enable_tts=True,
            enable_video=True,
        )

        mock_processor = Mock()
        mock_content = DocumentContent(
            pages=[PageContent(page_number=1, text="测试文本")]
        )
        mock_processor.process.return_value = mock_content
        mock_processor_class = Mock(return_value=mock_processor)
        mock_processor_class.__name__ = "MockProcessor"

        pipeline = Pipeline(config)

        with patch("vidppt.pipeline.ProcessorRegistry.get_processor") as mock_get:
            mock_get.return_value = mock_processor_class
            with patch.object(pipeline, "_summarize_content") as mock_summarize:
                with patch.object(pipeline, "_generate_audio"):
                    with patch.object(pipeline, "_compose_video"):
                        with patch.object(pipeline, "_cleanup_temp_files"):
                            pipeline.run()
                            mock_summarize.assert_called_once()

    def test_run_without_llm_does_not_call_summarize(self, temp_dir):
        """测试禁用 LLM 时不调用摘要"""
        test_file = temp_dir / "test.pptx"
        test_file.write_text("test")

        config = ProcessConfig(
            input_path=test_file,
            output_dir=temp_dir / "output",
            llm_enabled=False,
        )

        mock_processor = Mock()
        mock_content = DocumentContent(pages=[])
        mock_processor.process.return_value = mock_content
        mock_processor_class = Mock(return_value=mock_processor)
        mock_processor_class.__name__ = "MockProcessor"

        pipeline = Pipeline(config)

        with patch("vidppt.pipeline.ProcessorRegistry.get_processor") as mock_get:
            mock_get.return_value = mock_processor_class
            with patch.object(pipeline, "_summarize_content") as mock_summarize:
                with patch.object(pipeline, "_generate_audio"):
                    with patch.object(pipeline, "_compose_video"):
                        with patch.object(pipeline, "_cleanup_temp_files"):
                            pipeline.run()
                            mock_summarize.assert_not_called()
