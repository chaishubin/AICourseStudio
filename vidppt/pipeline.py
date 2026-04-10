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
from .utils.audio_cache import AudioCacheManager
from .utils.progress import ProgressTracker, ProcessStage


class Pipeline:
    """文档到视频转换的主流程"""

    def __init__(self, config: ProcessConfig):
        self.config = config
        self.tts_engine = self._create_tts_engine()
        self.cache_manager = AudioCacheManager(
            cache_dir=config.audio_cache_dir,
            enable_cache=config.enable_audio_cache,
            expiry_days=config.audio_cache_expiry_days,
        )

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

        # 初始化进度跟踪器（将在提取内容后更新总页数）
        progress = ProgressTracker(
            total_pages=0,  # 暂时为 0，提取内容后更新
            enable_progress=True,
        )

        try:
            # 3. 提取内容和渲染页面
            stage = progress.start_stage(ProcessStage.EXTRACT)
            content = processor.process(self.config)
            progress.stages[ProcessStage.EXTRACT].total = content.total_pages
            progress.complete_stage(ProcessStage.EXTRACT)

            # 4. 文字转语音
            if self.config.enable_tts:
                self._generate_audio(content, progress)

            # 5. 合成视频
            if self.config.enable_video:
                self._compose_video(content, progress)

            # 6. 清理临时文件（如果需要）
            if not self.config.save_intermediate:
                self._cleanup_temp_files(progress)

            logger.info(f"完成！输出目录: {self.config.output_dir.resolve()}")
            progress.print_summary()

        except Exception as e:
            logger.error(f"处理失败: {e}")
            progress.print_summary()
            raise

    def _generate_audio(
        self, content: DocumentContent, progress: ProgressTracker
    ) -> None:
        """生成语音"""
        logger.info(
            f"开始文字转语音"
            f"（引擎: {self.config.tts_engine}, "
            f"声音: {self.config.tts_voice}, "
            f"语速: {self.config.tts_rate}）"
        )

        try:
            progress.start_stage(ProcessStage.TTS)
            progress.stages[ProcessStage.TTS].total = content.total_pages

            page_texts = []
            cached_pages = []

            for page in content.pages:
                # 跳过没有文本的页面
                if not page.text or not page.text.strip():
                    logger.debug(f"第 {page.page_number} 页 无文本，跳过 TTS 转换")
                    progress.update_stage(ProcessStage.TTS, page.page_number)
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

                # 尝试从缓存获取
                cached_audio = self.cache_manager.get(
                    text=page.text,
                    tts_engine=self.config.tts_engine,
                    voice=self.config.tts_voice,
                    rate=self.config.tts_rate,
                    **self.config.tts_options,
                )

                if cached_audio:
                    # 从缓存复制文件
                    import shutil

                    shutil.copy2(cached_audio, audio_path)
                    page.audio = audio_path
                    cached_pages.append((page.page_number, cached_audio))
                    logger.info(
                        f"第 {page.page_number} 页 音频（从缓存）-> {audio_path}"
                    )
                else:
                    page.audio = audio_path
                    page_texts.append((page.page_number, page.text, audio_path))

                progress.update_stage(ProcessStage.TTS, page.page_number)

            # 如果有需要转换的文本，进行异步批量转换
            if page_texts:
                asyncio.run(
                    self.tts_engine.batch_convert(
                        page_texts,
                        voice=self.config.tts_voice,
                        rate=self.config.tts_rate,
                    )
                )

                # 转换后保存到缓存
                for page_num, text, audio_path in page_texts:
                    self.cache_manager.put(
                        audio_path=audio_path,
                        text=text,
                        tts_engine=self.config.tts_engine,
                        voice=self.config.tts_voice,
                        rate=self.config.tts_rate,
                        **self.config.tts_options,
                    )
                    logger.info(f"第 {page_num} 页 音频 -> {audio_path}")

            if page_texts or cached_pages:
                cache_info = (
                    f"（缓存命中: {len(cached_pages)}, 新转换: {len(page_texts)}）"
                    if self.config.enable_audio_cache
                    else ""
                )
                logger.info(f"文字转语音完成 {cache_info}")
            else:
                logger.info("没有文本需要转换，跳过 TTS 处理")

            progress.complete_stage(ProcessStage.TTS)

        except Exception as e:
            logger.warning(f"TTS 转换失败: {e}")
            progress.fail_stage(ProcessStage.TTS, str(e))
            if "edge-tts" in self.config.tts_engine:
                logger.warning("请检查网络连接，edge-tts 需要访问微软服务器")

    def _compose_video(
        self, content: DocumentContent, progress: ProgressTracker
    ) -> None:
        """合成视频"""
        video_name = self.config.input_path.stem
        video_path = self.config.output_dir / f"{video_name}.mp4"

        logger.info("开始合成视频...")
        try:
            progress.start_stage(ProcessStage.VIDEO)
            progress.stages[ProcessStage.VIDEO].total = content.total_pages

            VideoComposer.compose(content, self.config, video_path)

            progress.complete_stage(ProcessStage.VIDEO)
        except Exception as e:
            logger.warning(f"视频合成失败: {e}")
            progress.fail_stage(ProcessStage.VIDEO, str(e))

    def _cleanup_temp_files(self, progress: ProgressTracker) -> None:
        """清理临时文件"""
        logger.info("清理临时文件...")
        try:
            progress.start_stage(ProcessStage.CLEANUP)
            temp_files = list(self.config.output_dir.glob("_temp_*"))
            for temp_file in temp_files:
                temp_file.unlink()
                logger.debug(f"删除: {temp_file}")
            progress.complete_stage(ProcessStage.CLEANUP)
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")
            progress.fail_stage(ProcessStage.CLEANUP, str(e))
