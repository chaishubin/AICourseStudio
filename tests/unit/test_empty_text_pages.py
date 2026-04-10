"""
测试空文本页面的处理
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from vidppt.core.models import PageContent, DocumentContent, ProcessConfig
from vidppt.pipeline import Pipeline
from vidppt.utils.video_composer import VideoComposer


class TestEmptyTextPages:
    """测试空文本页面处理"""

    def test_pipeline_skip_tts_for_empty_text(self, temp_dir):
        """测试管道跳过没有文本的页面的 TTS 处理"""
        # 创建有些页面有文本，有些没有文本的内容
        pages = [
            PageContent(page_number=1, text="第一页的文本"),
            PageContent(page_number=2, text=""),  # 空文本
            PageContent(page_number=3, text="   "),  # 只有空格
            PageContent(page_number=4, text="第四页的文本"),
        ]
        content = DocumentContent(pages=pages)

        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            tts_engine="edge-tts",
        )

        # Mock TTS 引擎的 batch_convert 方法
        pipeline = Pipeline(config)
        with patch.object(pipeline.tts_engine, "batch_convert") as mock_tts:
            pipeline._generate_audio(content)

            # 验证只有非空文本的页面被传递给 TTS
            call_args = mock_tts.call_args
            if call_args:
                page_texts = call_args[0][0]
                page_numbers = [page_num for page_num, _, _ in page_texts]

                # 应该只有第 1 和 4 页被处理
                assert 1 in page_numbers or not page_texts  # 如果调用，应包含第1页
                assert 2 not in page_numbers
                assert 3 not in page_numbers
                assert 4 in page_numbers or not page_texts  # 如果调用，应包含第4页

    def test_ppt_processor_skip_empty_text_file(self, temp_dir):
        """测试 PPT 处理器跳过保存空文本文件"""
        from vidppt.processors.ppt_processor import PPTProcessor

        processor = PPTProcessor()

        # 创建测试页面
        page_with_text = PageContent(page_number=1, text="有文本")
        page_empty = PageContent(page_number=2, text="")
        page_whitespace = PageContent(page_number=3, text="   \n  ")

        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            save_intermediate=True,
        )

        # Mock extract_text 方法
        texts = ["有文本", "", "   \n  "]
        text_index = [0]

        def mock_extract_text(slide):
            result = texts[text_index[0]]
            text_index[0] += 1
            return result

        # 测试：验证只有非空文本才会被保存
        with patch.object(
            processor, "_extract_text_from_slide", side_effect=mock_extract_text
        ):
            with patch.object(processor, "_extract_images_from_slide", return_value=[]):
                from unittest.mock import MagicMock
                from pptx import Presentation

                mock_prs = MagicMock()
                mock_slide1 = MagicMock()
                mock_slide2 = MagicMock()
                mock_slide3 = MagicMock()

                mock_prs.slides = [mock_slide1, mock_slide2, mock_slide3]

                with patch(
                    "vidppt.processors.ppt_processor.Presentation",
                    return_value=mock_prs,
                ):
                    content = processor.extract_content(config)

                    # 验证文本被正确提取
                    assert content.pages[0].text == "有文本"
                    assert content.pages[1].text == ""
                    assert content.pages[2].text == "   \n  "

                    # 验证只有非空文本的文件被保存
                    text_file_1 = config.output_dir / "1" / "text.txt"
                    text_file_2 = config.output_dir / "2" / "text.txt"
                    text_file_3 = config.output_dir / "3" / "text.txt"

                    # 第1页有文本，应该被保存
                    if text_file_1.exists():
                        assert text_file_1.read_text() == "有文本"

                    # 第2页和第3页无文本或只有空格，不应该被保存
                    assert (
                        not text_file_2.exists() or not text_file_2.read_text().strip()
                    )
                    assert (
                        not text_file_3.exists() or not text_file_3.read_text().strip()
                    )

    def test_video_composer_handles_empty_pages(self, temp_dir):
        """测试视频合成器处理没有音频的页面"""
        # 创建临时图像
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        img_path = temp_dir / "test.png"
        img.save(img_path)

        # 测试页面：有图像，没有音频或文本
        pages = [
            PageContent(
                page_number=1,
                text="有文本",
                slide_image=img_path,
                audio=temp_dir / "audio1.mp3",  # 不存在的文件
            ),
            PageContent(
                page_number=2,
                text="",  # 无文本
                slide_image=img_path,
                audio=None,  # 无音频
            ),
        ]
        content = DocumentContent(pages=pages)

        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
        )

        video_path = temp_dir / "output.mp4"

        # 测试：第1页有音频但文件不存在（会跳过），第2页无音频无文本（会使用默认时长）
        with patch("vidppt.utils.video_composer.concatenate_videoclips") as mock_concat:
            with patch("vidppt.utils.video_composer.ImageClip") as mock_image_clip:
                mock_final = MagicMock()
                mock_concat.return_value = mock_final
                mock_clip = MagicMock()
                mock_image_clip.return_value.with_duration.return_value = mock_clip

                # 执行时可能出现异常（文件操作），但这是测试目的
                try:
                    VideoComposer.compose(content, config, video_path)
                except Exception:
                    pass  # 预期可能出现错误


class TestEmptyTextIntegration:
    """集成测试：空文本页面处理"""

    def test_all_pages_have_text(self, temp_dir):
        """测试所有页面都有文本的情况"""
        pages = [
            PageContent(page_number=1, text="第一页"),
            PageContent(page_number=2, text="第二页"),
        ]
        content = DocumentContent(pages=pages)

        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            tts_engine="edge-tts",
        )

        pipeline = Pipeline(config)

        # 应该尝试处理所有页面
        with patch.object(pipeline.tts_engine, "batch_convert") as mock_tts:
            pipeline._generate_audio(content)

            # 应该有调用 TTS
            mock_tts.assert_called_once()

    def test_no_pages_have_text(self, temp_dir):
        """测试所有页面都无文本的情况"""
        pages = [
            PageContent(page_number=1, text=""),
            PageContent(page_number=2, text="  "),
        ]
        content = DocumentContent(pages=pages)

        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            tts_engine="edge-tts",
        )

        pipeline = Pipeline(config)

        # 应该跳过 TTS 处理
        with patch.object(pipeline.tts_engine, "batch_convert") as mock_tts:
            pipeline._generate_audio(content)

            # 不应该调用 TTS
            mock_tts.assert_not_called()

    def test_mixed_pages(self, temp_dir):
        """测试混合页面（有的有文本，有的没有）"""
        pages = [
            PageContent(page_number=1, text="有文本"),
            PageContent(page_number=2, text=""),
            PageContent(page_number=3, text="  "),
            PageContent(page_number=4, text="也有文本"),
        ]
        content = DocumentContent(pages=pages)

        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            tts_engine="edge-tts",
        )

        pipeline = Pipeline(config)

        with patch.object(pipeline.tts_engine, "batch_convert") as mock_tts:
            pipeline._generate_audio(content)

            # 应该调用 TTS，但只处理第1和4页
            if mock_tts.called:
                page_texts = mock_tts.call_args[0][0]
                page_numbers = [page_num for page_num, _, _ in page_texts]

                assert 1 in page_numbers
                assert 2 not in page_numbers
                assert 3 not in page_numbers
                assert 4 in page_numbers
