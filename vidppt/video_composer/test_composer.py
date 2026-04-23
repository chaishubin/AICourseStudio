"""
视频合成工具单元测试

测试内容：
1. TTS 生成
2. 背景视频生成（静态图片片段）
3. 融合视频生成（合成背景+人脸视频）
"""

import pytest
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image

from composer import (
    TTSGenerator,
    create_image_clip,
    create_circular_video_clip,
    VideoConfig,
)
from tts_processors import ProcessorFactory, CompositeProcessor


class TestTTSGenerator:
    """TTS 生成测试"""

    @pytest.fixture
    def tts(self):
        """创建 TTS 实例"""
        return TTSGenerator(voice="zh-CN-XiaoxiaoNeural")

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_simple_generation(self, tts, temp_dir):
        """测试简单文本生成"""
        output = temp_dir / "test_simple.mp3"
        result = tts.generate("你好中国", output)

        assert result.exists()
        assert result.stat().st_size > 0

    def test_explicit_pause_processor(self, tts, temp_dir):
        """测试显式停顿处理"""
        output = temp_dir / "test_pause.mp3"

        # 使用显式停顿策略
        tts = TTSGenerator(processor_name="explicit_pause")
        result = tts.generate("你好|中国", output)

        assert result.exists()

    def test_pinyin_annotation(self, tts, temp_dir):
        """测试拼音标注处理"""
        output = temp_dir / "test_pinyin.mp3"

        tts = TTSGenerator(processor_name="pinyin_annotation")
        result = tts.generate("好[hao3]", output)

        assert result.exists()

    def test_composite_processor(self, temp_dir):
        """测试组合策略"""
        output = temp_dir / "test_composite.mp3"

        processor = CompositeProcessor()
        processor.add_processor(ProcessorFactory.get("explicit_pause"))
        processor.add_processor(ProcessorFactory.get("pinyin_annotation"))

        tts = TTSGenerator(processor=processor)
        result = tts.generate("你好|中[zhong1]国", output)

        assert result.exists()

    def test_factory_list(self):
        """测试策略工厂"""
        strategies = ProcessorFactory.list_all()

        assert "explicit_pause" in strategies
        assert "pinyin_annotation" in strategies
        assert "ssml" in strategies
        assert "jieba_segment" in strategies


class TestImageClip:
    """背景视频生成测试"""

    @pytest.fixture
    def gray_image(self, temp_dir):
        """创建灰色测试图像"""
        img_path = temp_dir / "gray_bg.png"

        # 创建 1920x1080 灰色图像
        img_array = np.full((1080, 1920, 3), 128, dtype=np.uint8)
        img = Image.fromarray(img_array, mode="RGB")
        img.save(img_path)

        return img_path

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_create_image_clip(self, gray_image, temp_dir):
        """测试创建静态图片片段"""
        config = VideoConfig()
        clip = create_image_clip(
            gray_image,
            duration=3.0,
            fps=config.fps,
            size=(config.width, config.height)
        )

        # 验证片段属性
        assert clip.duration == 3.0
        assert clip.fps == config.fps
        assert clip.size == (config.width, config.height)

        # 写入文件验证
        output = temp_dir / "bg_clip.mp4"
        clip.write_videofile(str(output), fps=config.fps, codec='libx264')

        assert output.exists()
        assert output.stat().st_size > 0

    def test_different_durations(self, gray_image):
        """测试不同时长"""
        for duration in [1.0, 5.0, 10.0]:
            clip = create_image_clip(gray_image, duration=duration)
            assert clip.duration == duration


class TestVideoComposition:
    """视频合成测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def gray_background(self, temp_dir):
        """创建灰色背景图像"""
        img_path = temp_dir / "background.png"

        # 创建蓝色背景（更明显）
        img_array = np.full((1080, 1920, 3), [100, 100, 200], dtype=np.uint8)
        img = Image.fromarray(img_array, mode="RGB")
        img.save(img_path)

        return img_path

    @pytest.fixture
    def mock_face_video(self, temp_dir):
        """创建模拟人脸视频（纯色圆形）"""
        from moviepy.editor import VideoClip, ColorClip

        video_path = temp_dir / "face_mock.mp4"

        # 创建一个纯红色视频作为"人脸"
        def make_frame(t):
            frame = np.zeros((300, 300, 3), dtype=np.uint8)
            # 画一个红色圆形
            y, x = np.ogrid[:300, :300]
            mask = (x - 150) ** 2 + (y - 150) ** 2 <= 140 ** 2
            frame[mask] = [255, 100, 100]
            return frame

        clip = VideoClip(make_frame, duration=3.0)
        clip = clip.set_fps(30)
        clip.write_videofile(str(video_path), fps=30, codec='libx264')

        return video_path

    def test_circular_mask(self, mock_face_video, temp_dir):
        """测试圆形遮罩生成"""
        from moviepy.editor import VideoFileClip

        # 应用圆形遮罩
        face_clip = create_circular_video_clip(mock_face_video, target_size=300)

        # 应该是 RGBA 格式（带 alpha 通道）
        first_frame = face_clip.get_frame(0)
        assert first_frame.shape[2] == 4  # RGBA

    def test_composite_video(self, gray_background, mock_face_video, temp_dir):
        """测试视频合成"""
        from moviepy.editor import CompositeVideoClip

        config = VideoConfig()
        output_path = temp_dir / "composed.mp4"

        # 创建背景片段
        bg_clip = create_image_clip(
            gray_background,
            duration=3.0,
            fps=config.fps,
            size=(config.width, config.height)
        )

        # 创建圆形人脸片段
        face_clip = create_circular_video_clip(mock_face_video, config.face_size)

        # 计算位置
        face_w, face_h = face_clip.size
        position = config.get_face_position(face_w, face_h)
        face_clip = face_clip.set_position(position)

        # 合成
        final = CompositeVideoClip(
            [bg_clip, face_clip],
            size=(config.width, config.height)
        )

        # 输出
        final.write_videofile(
            str(output_path),
            fps=config.fps,
            codec='libx264'
        )

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_different_positions(self, gray_background, mock_face_video):
        """测试不同位置"""
        from moviepy.editor import CompositeVideoClip

        config = VideoConfig()
        positions = ["top-left", "top-right", "bottom-left", "bottom-right"]

        for pos in positions:
            config.face_position = pos
            face_clip = create_circular_video_clip(mock_face_video, config.face_size)
            face_w, face_h = face_clip.size
            position = config.get_face_position(face_w, face_h)

            # 验证位置在有效范围内
            x, y = position
            assert 0 <= x < config.width
            assert 0 <= y < config.height


class TestProcessorStrategies:
    """文本处理策略测试"""

    def test_explicit_pause(self):
        """测试显式停顿策略"""
        processor = ProcessorFactory.get("explicit_pause")
        result = processor.process("你好|中国")

        assert '<break time="200ms"/>' in result
        assert "|" not in result

    def test_explicit_pause_custom_duration(self):
        """测试自定义停顿时长"""
        processor = ProcessorFactory.get("explicit_pause", pause_duration="500ms")
        result = processor.process("你好|中国")

        assert '<break time="500ms"/>' in result

    def test_pinyin_annotation(self):
        """测试拼音标注"""
        processor = ProcessorFactory.get("pinyin_annotation")
        result = processor.process("好[hao3]")

        assert '<phoneme ph="hao3">好</phoneme>' in result

    def test_ssml_passthrough(self):
        """测试 SSML 原样传递"""
        processor = ProcessorFactory.get("ssml")
        result = processor.process('<break time="500ms"/>')

        assert result == '<break time="500ms"/>'

    def test_composite(self):
        """测试组合处理器"""
        processor = CompositeProcessor()
        processor.add_processor(ProcessorFactory.get("explicit_pause"))
        processor.add_processor(ProcessorFactory.get("pinyin_annotation"))

        result = processor.process("你好|中[zhong1]国")

        assert '<break time="200ms"/>' in result
        assert '<phoneme ph="zhong1">中</phoneme>' in result


# 运行测试的入口
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
