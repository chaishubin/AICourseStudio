"""
主处理流程
"""

import asyncio
from pathlib import Path

from loguru import logger

from .core.models import ProcessConfig, DocumentContent
from .core.registry import ProcessorRegistry
from .engines.tts.edge_tts_engine import EdgeTTSEngine
from .utils.video_composer import VideoComposer


class Pipeline:
    """文档到视频转换的主流程"""

    def __init__(self, config: ProcessConfig):
        self.config = config
        self.tts_engine = self._create_tts_engine()

    def _create_tts_engine(self):
        """根据配置创建 TTS 引擎"""
        if self.config.tts_engine == "edge-tts":
            return EdgeTTSEngine()
        elif self.config.tts_engine == "minimax":
            # MiniMax 引擎会自动从环境变量 MINIMAX_API 读取 api_key
            from .engines.tts.api_tts_engine import MiniMaxTTSEngine

            return MiniMaxTTSEngine(
                api_key=self.config.tts_options.get("api_key"),
                api_url=self.config.tts_options.get(
                    "api_url", "https://api.minimaxi.com/v1/t2a_v2"
                ),
                model=self.config.tts_options.get("model", "speech-2.8-hd"),
                sample_rate=self.config.tts_options.get("sample_rate", 32000),
                bitrate=self.config.tts_options.get("bitrate", 128000),
                audio_format=self.config.tts_options.get("audio_format", "mp3"),
                channel=self.config.tts_options.get("channel", 1),
                emotion=self.config.tts_options.get("emotion", "neutral"),
            )
        else:
            raise ValueError(f"不支持的 TTS 引擎: {self.config.tts_engine}")

    def run(self) -> None:
        """执行完整的处理流程"""
        # 1. 检查文件是否存在
        if not self.config.input_path.exists():
            logger.error(f"文件不存在: {self.config.input_path}")
            raise FileNotFoundError(f"输入文件不存在: {self.config.input_path}")

        # 2. 获取对应的处理器
        processor_class = ProcessorRegistry.get_processor(self.config.input_path)
        if not processor_class:
            ext = self.config.input_path.suffix
            supported = ProcessorRegistry.list_supported_extensions()
            logger.error(f"不支持的文件类型: {ext}。支持的类型: {', '.join(supported)}")
            raise ValueError(f"不支持的文件类型: {ext}")

        processor = processor_class()
        logger.info(f"使用处理器: {processor_class.__name__}")
        logger.info(f"输入文件: {self.config.input_path}")
        logger.info(f"输出目录: {self.config.output_dir}")

        # 3. 提取内容和渲染页面
        content = processor.process(self.config)

        # 4. 文字转语音
        if self.config.enable_tts:
            self._generate_audio(content)

        # 5. 合成视频
        if self.config.enable_video:
            self._compose_video(content)

        # 6. 清理临时文件（如果需要）
        if not self.config.save_intermediate:
            self._cleanup_temp_files()

        logger.info(f"完成！输出目录: {self.config.output_dir.resolve()}")

    def _generate_audio(self, content: DocumentContent) -> None:
        """生成语音"""
        logger.info(
            f"开始文字转语音"
            f"（引擎: {self.config.tts_engine}, "
            f"声音: {self.config.tts_voice}, "
            f"语速: {self.config.tts_rate}）"
        )

        try:
            page_texts = []
            for page in content.pages:
                # 跳过没有文本的页面
                if not page.text or not page.text.strip():
                    logger.debug(f"第 {page.page_number} 页 无文本，跳过 TTS 转换")
                    continue

                if self.config.save_intermediate:
                    audio_path = (
                        self.config.output_dir / str(page.page_number) / "audio.mp3"
                    )
                else:
                    audio_path = (
                        self.config.output_dir / f"_temp_audio_{page.page_number}.mp3"
                    )

                audio_path.parent.mkdir(parents=True, exist_ok=True)
                page.audio = audio_path
                page_texts.append((page.page_number, page.text, audio_path))

            # 如果有需要转换的文本，进行异步批量转换
            if page_texts:
                asyncio.run(
                    self.tts_engine.batch_convert(
                        page_texts,
                        voice=self.config.tts_voice,
                        rate=self.config.tts_rate,
                    )
                )

                for page_num, _, audio_path in page_texts:
                    logger.info(f"第 {page_num} 页 音频 -> {audio_path}")
            else:
                logger.info("没有文本需要转换，跳过 TTS 处理")

        except Exception as e:
            logger.warning(f"TTS 转换失败: {e}")
            if "edge-tts" in self.config.tts_engine:
                logger.warning("请检查网络连接，edge-tts 需要访问微软服务器")

    def _compose_video(self, content: DocumentContent) -> None:
        """合成视频"""
        video_name = self.config.input_path.stem
        video_path = self.config.output_dir / f"{video_name}.mp4"

        logger.info("开始合成视频...")
        try:
            VideoComposer.compose(content, self.config, video_path)
        except Exception as e:
            logger.warning(f"视频合成失败: {e}")

    def _cleanup_temp_files(self) -> None:
        """清理临时文件"""
        logger.info("清理临时文件...")
        temp_files = list(self.config.output_dir.glob("_temp_*"))
        for temp_file in temp_files:
            temp_file.unlink()
            logger.debug(f"删除: {temp_file}")
