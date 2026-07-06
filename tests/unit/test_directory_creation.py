"""
测试文件写入时自动创建目录的功能
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from PIL import Image

from vidppt.core.models import PageContent, DocumentContent, ProcessConfig
from vidppt.processors.ppt_processor import PPTProcessor
from vidppt.utils.video_composer import VideoComposer


class TestDirectoryCreation:
    """测试文件写入时的目录创建"""

    def test_extract_images_creates_directory_if_not_exists(self, temp_dir):
        """测试图像提取时如果目录不存在则创建"""
        processor = PPTProcessor()

        # 创建不存在的嵌套目录路径
        nested_dir = temp_dir / "nested" / "path" / "for" / "images"
        assert not nested_dir.exists()

        # Mock slide
        mock_slide = MagicMock()
        mock_shape = MagicMock()
        mock_shape.shape_type = 13  # MSO_SHAPE_TYPE.PICTURE
        mock_image = MagicMock()
        mock_image.ext = "png"
        mock_image.blob = b"fake_image_data"
        mock_shape.image = mock_image
        mock_slide.shapes = [mock_shape]

        # 调用方法
        result = processor._extract_images_from_slide(mock_slide, nested_dir)

        # 验证目录被创建了
        assert nested_dir.exists(), "目录应该被自动创建"
        assert len(result) == 1
        assert result[0] == nested_dir / "image_1.png"

    def test_render_pages_creates_temp_directory(self, temp_dir):
        """测试 render_pages 在保存临时文件时创建目录"""
        processor = PPTProcessor()

        # 创建测试图像
        test_image = Image.new("RGB", (100, 100), color="blue")

        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "nested" / "output",
            save_intermediate=False,  # 使用临时文件模式
        )

        # 确保输出目录不存在
        assert not config.output_dir.exists()

        # Mock Spire Presentation
        mock_prs = MagicMock()
        mock_slide = MagicMock()
        mock_img_stream = MagicMock()

        # 配置 mock
        mock_prs.Slides.Count = 1
        mock_prs.Slides.__getitem__ = MagicMock(return_value=mock_slide)
        mock_slide.SaveAsImage.return_value = mock_img_stream
        mock_img_stream.ToArray.return_value = [0, 0]  # 空的字节数组

        # 使用 patch 替换 Presentation 和 Image 操作
        with patch("spire.presentation.Presentation", return_value=mock_prs):
            with patch("vidppt.processors.ppt_processor.Image.open") as mock_image_open:
                # 配置 Image mock
                mock_image_open.return_value = test_image

                # 调用方法
                result = processor.render_pages(config)

                # 验证目录被创建了
                assert config.output_dir.exists(), "输出目录应该被自动创建"

    def test_video_composer_creates_output_directory(self, temp_dir):
        """测试视频合成器创建输出目录"""
        # 创建测试图像
        test_img = Image.new("RGB", (100, 100), color="red")
        img_path = temp_dir / "test.png"
        test_img.save(img_path)

        # 创建页面内容（无音频的空白页）
        pages = [
            PageContent(page_number=1, text="", slide_image=img_path, audio=None),
        ]
        content = DocumentContent(pages=pages)

        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "nested" / "video" / "output",
        )

        video_path = config.output_dir / "output.mp4"

        # 确保输出目录不存在
        assert not config.output_dir.exists()

        # Mock concatenate_videoclips
        with patch("vidppt.utils.video_composer.concatenate_videoclips") as mock_concat:
            mock_final = MagicMock()
            mock_final.write_videofile.side_effect = (
                lambda filename, **kwargs: Path(filename).touch()
            )
            mock_concat.return_value = mock_final

            VideoComposer.compose(content, config, video_path)

            # 验证目录和高校网课输出参数
            assert config.output_dir.exists(), "输出目录应该被自动创建"
            kwargs = mock_final.write_videofile.call_args.kwargs
            assert kwargs["fps"] == 24
            assert kwargs["codec"] == "libx264"
            assert kwargs["preset"] == "veryfast"
            assert kwargs["pixel_format"] == "yuv420p"
            assert kwargs["audio_fps"] == 48000
            assert kwargs["audio_bitrate"] == "128k"
            assert kwargs["ffmpeg_params"] == [
                "-profile:v",
                "high",
                "-crf",
                "21",
                "-g",
                "48",
                "-movflags",
                "+faststart",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "48000",
                "-ac",
                "1",
                "-af",
                "loudnorm=I=-16.0:TP=-1.5:LRA=11",
            ]

    def test_ppt_processor_creates_page_directory(self, temp_dir):
        """测试 PPT 处理器在提取内容时创建页面目录"""
        processor = PPTProcessor()

        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "nested" / "output",
            save_intermediate=True,
        )

        # 确保输出目录不存在
        assert not config.output_dir.exists()

        # Mock Presentation
        mock_prs = MagicMock()
        mock_slide = MagicMock()

        # 配置 mock
        mock_prs.slides = [mock_slide]
        mock_slide.shapes = []

        # 创建测试文本
        mock_prs.slides[0].shapes = []

        # Mock 方法
        with patch(
            "vidppt.processors.ppt_processor.Presentation", return_value=mock_prs
        ):
            with patch.object(
                processor, "_extract_text_from_slide", return_value="测试文本"
            ):
                with patch.object(
                    processor, "_extract_images_from_slide", return_value=[]
                ):
                    # 调用方法
                    content = processor.extract_content(config)

                    # 验证文本文件被创建了
                    text_file = config.output_dir / "1" / "text.txt"
                    assert text_file.exists(), "文本文件应该被创建"
                    assert text_file.read_text() == "测试文本"


class TestDirectoryCreationIntegration:
    """集成测试：确保所有文件操作都会创建目录"""

    def test_nested_directory_creation_for_images(self, temp_dir):
        """测试深层嵌套目录的创建"""
        processor = PPTProcessor()

        # 创建非常深层的路径
        deep_dir = temp_dir / "a" / "b" / "c" / "d" / "e" / "f"
        assert not deep_dir.exists()

        # Mock slide
        mock_slide = MagicMock()
        mock_shape = MagicMock()
        mock_shape.shape_type = 13  # PICTURE
        mock_image = MagicMock()
        mock_image.ext = "jpg"
        mock_image.blob = b"image_data"
        mock_shape.image = mock_image
        mock_slide.shapes = [mock_shape]

        # 调用方法
        result = processor._extract_images_from_slide(mock_slide, deep_dir)

        # 验证深层目录被创建了
        assert deep_dir.exists(), "深层嵌套目录应该被创建"
        assert len(result) == 1

    def test_concurrent_directory_creation(self, temp_dir):
        """测试并发创建目录（多次调用）"""
        processor = PPTProcessor()

        base_dir = temp_dir / "images"

        # Mock slide 和 shape
        def create_mock_slide():
            mock_slide = MagicMock()
            mock_shape = MagicMock()
            mock_shape.shape_type = 13
            mock_image = MagicMock()
            mock_image.ext = "png"
            mock_image.blob = b"data"
            mock_shape.image = mock_image
            mock_slide.shapes = [mock_shape]
            return mock_slide

        # 多次调用
        for i in range(3):
            slide = create_mock_slide()
            result = processor._extract_images_from_slide(slide, base_dir)
            assert base_dir.exists()
            assert len(result) == 1

    def test_directory_already_exists_no_error(self, temp_dir):
        """测试目录已存在时不会出错"""
        processor = PPTProcessor()

        # 预先创建目录
        test_dir = temp_dir / "existing" / "dir"
        test_dir.mkdir(parents=True, exist_ok=True)
        assert test_dir.exists()

        # Mock slide
        mock_slide = MagicMock()
        mock_shape = MagicMock()
        mock_shape.shape_type = 13
        mock_image = MagicMock()
        mock_image.ext = "png"
        mock_image.blob = b"data"
        mock_shape.image = mock_image
        mock_slide.shapes = [mock_shape]

        # 调用方法（目录已存在，应该不出错）
        result = processor._extract_images_from_slide(mock_slide, test_dir)

        # 验证成功
        assert test_dir.exists()
        assert len(result) == 1
