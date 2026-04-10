"""
MiniMax TTS 真实集成测试

这个测试文件用于真实验证 MiniMax TTS API 的集成。
仅当设置了 MINIMAX_API 环境变量时才会运行。

注意：这会真实调用 MiniMax API，可能产生费用。
"""

import os
import pytest
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from vidppt.engines.tts.api_tts_engine import MiniMaxTTSEngine


# 检查是否有API key - 如果没有则跳过这个test模块
pytestmark = pytest.mark.skipif(
    not os.getenv("MINIMAX_API"),
    reason="需要设置 MINIMAX_API 环境变量才能运行真实集成测试",
)


class TestMiniMaxRealAPIIntegration:
    """MiniMax TTS 真实 API 集成测试"""

    @pytest.mark.asyncio
    async def test_convert_async_real_api(self):
        """测试真实的 convert_async API 调用"""
        engine = MiniMaxTTSEngine()

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test.mp3"

            # 调用真实的 convert_async
            await engine.convert_async(
                text="你好，这是一个测试。",
                output_path=output_path,
                voice="male-qn-qingse",
                rate="+0%",
            )

            # 验证文件被创建
            assert output_path.exists()
            # 验证文件不为空
            assert output_path.stat().st_size > 0
            print(f"✓ 音频文件大小: {output_path.stat().st_size} 字节")

    @pytest.mark.asyncio
    async def test_convert_async_with_emotion(self):
        """测试带情感的 convert_async"""
        engine = MiniMaxTTSEngine()

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_emotion.mp3"

            # 调用带情感的 convert_async
            await engine.convert_async(
                text="你好，这是一个开心的测试。",
                output_path=output_path,
                voice="female-qn-nana",
                rate="+10%",
                emotion="happy",
            )

            # 验证文件被创建
            assert output_path.exists()
            assert output_path.stat().st_size > 0
            print(f"✓ 情感音频文件大小: {output_path.stat().st_size} 字节")

    @pytest.mark.asyncio
    async def test_batch_convert_real_api(self):
        """测试真实的批量转换"""
        engine = MiniMaxTTSEngine()

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            texts = [
                (1, "第一页的文本", temp_path / "page1.mp3"),
                (2, "第二页的文本", temp_path / "page2.mp3"),
                (3, "第三页的文本", temp_path / "page3.mp3"),
            ]

            # 调用真实的 batch_convert
            await engine.batch_convert(
                texts=texts, voice="male-qn-qingse", rate="+0%", batch_size=2
            )

            # 验证所有文件都被创建
            for page_num, text, path in texts:
                assert path.exists(), f"页面 {page_num} 的音频文件不存在"
                assert path.stat().st_size > 0, f"页面 {page_num} 的音频文件为空"
                print(f"✓ 页面 {page_num}: {path.stat().st_size} 字节")

    @pytest.mark.asyncio
    async def test_empty_text_handling(self):
        """测试空文本处理"""
        engine = MiniMaxTTSEngine()

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "empty.mp3"

            # 空文本应该被转换为默认文本
            await engine.convert_async(
                text="", output_path=output_path, voice="male-qn-qingse", rate="+0%"
            )

            # 即使是空文本也应该生成音频
            assert output_path.exists()
            assert output_path.stat().st_size > 0
            print(f"✓ 空文本处理: {output_path.stat().st_size} 字节")

    @pytest.mark.asyncio
    async def test_different_voices_produce_different_audio(self):
        """测试不同的声音产生不同的音频"""
        engine = MiniMaxTTSEngine()
        text = "这是一个测试文本"

        with TemporaryDirectory() as temp_dir:
            # 男声
            male_path = Path(temp_dir) / "male.mp3"
            await engine.convert_async(
                text=text, output_path=male_path, voice="male-qn-qingse", rate="+0%"
            )

            # 女声
            female_path = Path(temp_dir) / "female.mp3"
            await engine.convert_async(
                text=text, output_path=female_path, voice="female-qn-nana", rate="+0%"
            )

            # 两个文件都应该存在
            assert male_path.exists()
            assert female_path.exists()

            # 文件大小应该不同（因为不同的声音）
            male_size = male_path.stat().st_size
            female_size = female_path.stat().st_size
            print(f"✓ 男声: {male_size} 字节, 女声: {female_size} 字节")

    @pytest.mark.asyncio
    async def test_batch_convert_with_emotions(self):
        """测试批量转换不同情感"""
        engine = MiniMaxTTSEngine()

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # 测试不同情感
            texts = [
                (1, "开心的文本", temp_path / "happy.mp3", "happy"),
                (2, "伤心的文本", temp_path / "sad.mp3", "sad"),
                (3, "中立的文本", temp_path / "neutral.mp3", "neutral"),
            ]

            # 调用 batch_convert_with_emotions
            await engine.batch_convert_with_emotions(
                texts=texts, voice="female-qn-nana", rate="+0%", batch_size=2
            )

            # 验证所有文件都被创建
            for page_num, text, path, emotion in texts:
                assert path.exists(), f"情感 {emotion} 的音频文件不存在"
                assert path.stat().st_size > 0
                print(f"✓ 情感 {emotion}: {path.stat().st_size} 字节")


class TestMiniMaxErrorHandling:
    """MiniMax 错误处理测试"""

    @pytest.mark.asyncio
    async def test_invalid_api_key(self):
        """测试无效的 API key"""
        engine = MiniMaxTTSEngine(api_key="invalid-key-xxx")

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test.mp3"

            # 应该抛出 HTTP 错误
            with pytest.raises(Exception):  # httpx.HTTPStatusError 或类似
                await engine.convert_async(
                    text="测试",
                    output_path=output_path,
                    voice="male-qn-qingse",
                    rate="+0%",
                )


class TestMiniMaxPerformance:
    """MiniMax 性能测试"""

    @pytest.mark.asyncio
    async def test_batch_convert_performance(self):
        """测试批量转换性能"""
        import time

        engine = MiniMaxTTSEngine()

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # 创建10页的文本
            texts = [
                (i, f"第{i}页的文本内容", temp_path / f"page{i}.mp3")
                for i in range(1, 11)
            ]

            start_time = time.time()

            # 批量转换
            await engine.batch_convert(
                texts=texts, voice="male-qn-qingse", rate="+0%", batch_size=5
            )

            elapsed_time = time.time() - start_time

            # 验证
            for i in range(1, 11):
                path = temp_path / f"page{i}.mp3"
                assert path.exists()

            print(f"✓ 10页批量转换耗时: {elapsed_time:.2f} 秒")
            print(f"  平均每页: {elapsed_time / 10:.2f} 秒")
