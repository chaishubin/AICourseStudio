"""
集成测试：验证 TTS 转换是否真的能工作
"""

import asyncio
import tempfile
from pathlib import Path
import pytest

from vidppt.core.models import ProcessConfig, DocumentContent, PageContent
from vidppt.pipeline import Pipeline
from vidppt.engines.tts.edge_tts_engine import EdgeTTSEngine
from vidppt.utils.progress import ProgressTracker


class TestTTSIntegration:
    """TTS 实际转换的集成测试"""

    def test_edge_tts_engine_direct_call(self):
        """测试直接调用 EdgeTTS 引擎"""
        engine = EdgeTTSEngine()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_audio.mp3"

            # 直接调用 convert_async
            try:
                asyncio.run(
                    engine.convert_async(
                        text="这是一个测试文本",
                        output_path=output_path,
                        voice="zh-CN-XiaoxiaoNeural",
                        rate="+0%",
                    )
                )

                # 验证文件已创建
                assert output_path.exists()
                assert output_path.stat().st_size > 0
                print(
                    f"✓ EdgeTTS 直接调用成功，生成文件大小: {output_path.stat().st_size} 字节"
                )

            except Exception as e:
                print(f"✗ EdgeTTS 直接调用失败: {type(e).__name__}: {e}")
                raise

    def test_edge_tts_batch_convert(self):
        """测试 batch_convert 方法"""
        engine = EdgeTTSEngine()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            audio_files = [
                (1, "第一页的文本", output_dir / "audio_1.mp3"),
                (2, "第二页的文本", output_dir / "audio_2.mp3"),
            ]

            try:
                asyncio.run(
                    engine.batch_convert(
                        texts=audio_files,
                        voice="zh-CN-XiaoxiaoNeural",
                        rate="+0%",
                    )
                )

                # 验证所有文件已创建
                for page_num, text, output_path in audio_files:
                    assert output_path.exists(), f"页面 {page_num} 的音频文件未创建"
                    assert output_path.stat().st_size > 0, (
                        f"页面 {page_num} 的音频文件为空"
                    )
                    print(f"✓ 页面 {page_num}: {output_path.stat().st_size} 字节")

            except Exception as e:
                print(f"✗ batch_convert 失败: {type(e).__name__}: {e}")
                raise

    def test_pipeline_generate_audio_real(self):
        """测试 Pipeline 的音频生成（真实 TTS 调用）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ProcessConfig(
                input_path=Path(tmpdir) / "test.pptx",
                output_dir=Path(tmpdir) / "output",
                enable_audio_cache=False,  # 禁用缓存
                tts_engine="edge-tts",
                tts_voice="zh-CN-XiaoxiaoNeural",
            )

            content = DocumentContent(
                pages=[
                    PageContent(page_number=1, text="这是第一页"),
                    PageContent(page_number=2, text="这是第二页"),
                ]
            )

            pipeline = Pipeline(config)
            progress = ProgressTracker(total_pages=len(content.pages))

            try:
                pipeline._generate_audio(content, progress)

                # 验证音频文件已创建
                for page in content.pages:
                    assert page.audio is not None
                    assert page.audio.exists(), f"页面 {page.page_number} 的音频未创建"
                    assert page.audio.stat().st_size > 0
                    print(
                        f"✓ 页面 {page.page_number} 音频: {page.audio.stat().st_size} 字节"
                    )

            except Exception as e:
                print(f"✗ Pipeline TTS 转换失败: {type(e).__name__}: {e}")
                raise


if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("TTS 集成测试")
    print("=" * 60)

    test = TestTTSIntegration()

    # 运行所有测试
    tests = [
        ("Edge TTS 直接调用", test.test_edge_tts_engine_direct_call),
        ("batch_convert 方法", test.test_edge_tts_batch_convert),
        ("Pipeline TTS 转换", test.test_pipeline_generate_audio_real),
    ]

    failed = []
    for name, test_func in tests:
        print(f"\n测试: {name}")
        try:
            test_func()
            print(f"结果: ✓ 通过")
        except Exception as e:
            print(f"结果: ✗ 失败 - {e}")
            failed.append(name)

    print("\n" + "=" * 60)
    if failed:
        print(f"失败的测试: {len(failed)}")
        for name in failed:
            print(f"  - {name}")
        sys.exit(1)
    else:
        print("所有集成测试通过！✓")
        sys.exit(0)
