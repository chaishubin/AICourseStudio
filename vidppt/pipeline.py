"""
主处理流程
"""

import asyncio
from pathlib import Path

from loguru import logger

from .core.models import ProcessConfig, DocumentContent
from .core.registry import ProcessorRegistry
from .engines.tts.edge_tts_engine import EdgeTTSEngine
from .engines.llm.minimax_llm_engine import MiniMaxLLMEngine
from .utils.video_composer import VideoComposer
from .utils.audio_cache import AudioCacheManager
from .utils.progress import ProgressTracker, ProcessStage


def _run_async(coro):
    """
    安全地运行异步协程，兼容嵌套事件循环场景（如 Jupyter、某些框架）。

    优先尝试在已有事件循环中运行（使用 nest_asyncio），
    若不可用则回退到 asyncio.run()。
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # 已有运行中的事件循环（如 Jupyter），尝试使用 nest_asyncio
        try:
            import nest_asyncio

            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        except ImportError:
            raise RuntimeError(
                "检测到已有运行中的事件循环，但 nest_asyncio 未安装。\n"
                "请运行: pip install nest_asyncio"
            )
    else:
        return asyncio.run(coro)


class Pipeline:
    """文档到视频转换的主流程"""

    def __init__(self, config: ProcessConfig):
        self.config = config
        self.tts_engine = self._create_tts_engine()
        self.llm_engine = self._create_llm_engine() if config.llm_enabled else None
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
                timeout=self.config.tts_options.get("timeout", 60.0),
                max_retries=self.config.tts_options.get("max_retries", 3),
            )
        else:
            raise ValueError(f"不支持的 TTS 引擎: {self.config.tts_engine}")

    def _create_llm_engine(self):
        """根据配置创建 LLM 引擎"""
        if self.config.llm_engine == "minimax":
            llm_opts = self.config.llm_options
            return MiniMaxLLMEngine(
                api_key=llm_opts.get("api_key"),
                api_url=llm_opts.get("api_url", MiniMaxLLMEngine.DEFAULT_API_URL),
                model=llm_opts.get("model", MiniMaxLLMEngine.DEFAULT_MODEL),
                system_prompt=llm_opts.get(
                    "system_prompt", MiniMaxLLMEngine.DEFAULT_SYSTEM_PROMPT
                ),
                temperature=llm_opts.get("temperature", MiniMaxLLMEngine.DEFAULT_TEMPERATURE),
                max_tokens=llm_opts.get("max_tokens", MiniMaxLLMEngine.DEFAULT_MAX_TOKENS),
                timeout=llm_opts.get("timeout", MiniMaxLLMEngine.DEFAULT_TIMEOUT),
                max_retries=llm_opts.get("max_retries", MiniMaxLLMEngine.DEFAULT_MAX_RETRIES),
            )
        else:
            raise ValueError(f"不支持的 LLM 引擎: {self.config.llm_engine}")

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

            # 4. LLM 文本摘要
            if self.config.llm_enabled and self.llm_engine:
                self._summarize_content(content, progress)

            # 5. 文字转语音
            if self.config.enable_tts:
                self._generate_audio(content, progress)

            # 6. 合成视频
            if self.config.enable_video:
                self._compose_video(content, progress)

            # 7. 清理临时文件（如果需要）
            if not self.config.save_intermediate:
                self._cleanup_temp_files(progress)

            logger.info(f"完成！输出目录: {self.config.output_dir.resolve()}")
            progress.print_summary()

        except Exception as e:
            logger.error(f"处理失败: {e}")
            progress.print_summary()
            raise

    def _summarize_content(
        self, content: DocumentContent, progress: ProgressTracker
    ) -> None:
        """使用 LLM 引擎对文本进行摘要/改写"""
        logger.info(
            f"开始文本摘要（引擎: {self.config.llm_engine}, "
            f"模式: {self.config.llm_mode}）"
        )

        try:
            progress.start_stage(ProcessStage.LLM)
            progress.stages[ProcessStage.LLM].total = content.total_pages

            # 保存原文到 metadata
            for page in content.pages:
                page.metadata["original_text"] = page.text

            # 构建逐页调用时的额外参数
            llm_kwargs = {}
            for key in ("system_prompt", "temperature", "max_tokens"):
                if key in self.config.llm_options:
                    llm_kwargs[key] = self.config.llm_options[key]

            if self.config.llm_mode == "per-page":
                # 逐页摘要
                for i, page in enumerate(content.pages, 1):
                    if not page.text or not page.text.strip():
                        logger.debug(f"第 {page.page_number} 页 无文本，跳过 LLM 摘要")
                        progress.update_stage(ProcessStage.LLM, i)
                        continue
                    logger.debug(f"LLM 摘要: 第 {page.page_number} 页")
                    page.text = self.llm_engine.summarize(page.text, **llm_kwargs)
                    progress.update_stage_incremental(
                        ProcessStage.LLM, i,
                        force_display=(i == 1 or i == content.total_pages)
                    )

            elif self.config.llm_mode == "whole-document":
                # 整文档摘要
                pages_text = [page.text for page in content.pages]
                summary = self.llm_engine.summarize_document(pages_text, **llm_kwargs)
                # 摘要放第一页，其余页 text 置空
                content.pages[0].text = summary
                for page in content.pages[1:]:
                    page.text = ""
                progress.update_stage(ProcessStage.LLM, content.total_pages)

            progress.complete_stage(ProcessStage.LLM)

        except Exception as e:
            logger.error(f"LLM 摘要失败: {e}")
            progress.fail_stage(ProcessStage.LLM, str(e))
            raise

    def _generate_audio(
        self, content: DocumentContent, progress: ProgressTracker
    ) -> None:
        """生成语音"""
        logger.info(
            f"开始文字转语音"
            f"（引擎: {self.config.tts_engine}, "
            f"声音: {self.config.tts_voice if self.config.tts_engine == 'edge-tts' else self.config.tts_options.get('voice_id', 'male-qn-qingse')}, "
            f"语速: {self.config.tts_rate}）"
        )

        try:
            progress.start_stage(ProcessStage.TTS)
            progress.stages[ProcessStage.TTS].total = content.total_pages

            page_texts = []
            cached_pages = []
            skipped_pages = []

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

                # 检查音频文件是否已存在（跳过已有文件）
                if self.config.save_intermediate and self.config.skip_existing and audio_path.exists():
                    page.audio = audio_path
                    skipped_pages.append(page.page_number)
                    logger.debug(f"第 {page.page_number} 页 音频已存在，跳过TTS")
                    progress.update_stage(ProcessStage.TTS, page.page_number)
                    continue

                # 尝试从缓存获取
                if self.config.tts_engine == "edge-tts":
                    cached_audio = self.cache_manager.get(
                        text=page.text,
                        tts_engine=self.config.tts_engine,
                        voice=self.config.tts_voice,
                        rate=self.config.tts_rate,
                        input_path=str(self.config.input_path),
                    )
                else:
                    # minimax：voice 来自 tts_options，其余 tts_options 也作为 cache key
                    cached_audio = self.cache_manager.get(
                        text=page.text,
                        tts_engine=self.config.tts_engine,
                        voice=self.config.tts_options.get("voice_id", "male-qn-qingse"),
                        rate=self.config.tts_rate,
                        input_path=str(self.config.input_path),
                        **{
                            k: v
                            for k, v in self.config.tts_options.items()
                            if k != "api_key"
                        },
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
                # 创建进度回调函数
                def tts_progress_callback(current: int, total: int, info: str):
                    """TTS 转换进度回调"""
                    # 计算总进度：缓存页数 + 当前转换数
                    total_processed = len(cached_pages) + current
                    # 使用增量更新，避免频繁输出
                    progress.update_stage_incremental(
                        ProcessStage.TTS,
                        total_processed,
                        force_display=(current == 1 or current == total)
                    )

                if self.config.tts_engine == "edge-tts":
                    # edge-tts 只需要 voice 和 rate，不接受其他参数
                    errors = _run_async(
                        self.tts_engine.batch_convert(
                            page_texts,
                            voice=self.config.tts_voice,
                            rate=self.config.tts_rate,
                            progress_callback=tts_progress_callback,
                        )
                    )
                elif self.config.tts_engine == "minimax":
                    # MiniMax 引擎：voice_id 来自 tts_options，
                    # 额外参数（emotion、pronunciation_dict）也来自 tts_options
                    # 引擎级参数（model、sample_rate 等）已在初始化时传入，不重复传递
                    minimax_voice = self.config.tts_options.get(
                        "voice_id", "male-qn-qingse"
                    )
                    minimax_extra = {
                        k: v
                        for k, v in self.config.tts_options.items()
                        if k
                        not in (
                            "api_key",
                            "api_url",
                            "model",
                            "sample_rate",
                            "bitrate",
                            "audio_format",
                            "channel",
                            "voice_id",
                            "timeout",
                            "max_retries",
                        )
                    }
                    errors = _run_async(
                        self.tts_engine.batch_convert(
                            page_texts,
                            voice=minimax_voice,
                            rate=self.config.tts_rate,
                            progress_callback=tts_progress_callback,
                            **minimax_extra,
                        )
                    )
                else:
                    errors = []

                # 处理失败的页面：移除其 audio 路径
                failed_pages = {page_num for page_num, _ in errors}
                if failed_pages:
                    for page in content.pages:
                        if page.page_number in failed_pages:
                            page.audio = None
                    logger.warning(
                        f"TTS 转换失败 {len(failed_pages)} 页: {sorted(failed_pages)}"
                    )

                # 转换后保存到缓存（仅保存成功的）
                for page_num, text, audio_path in page_texts:
                    if page_num in failed_pages:
                        continue
                    if self.config.tts_engine == "edge-tts":
                        self.cache_manager.put(
                            audio_path=audio_path,
                            text=text,
                            tts_engine=self.config.tts_engine,
                            voice=self.config.tts_voice,
                            rate=self.config.tts_rate,
                            input_path=str(self.config.input_path),
                        )
                    else:
                        self.cache_manager.put(
                            audio_path=audio_path,
                            text=text,
                            tts_engine=self.config.tts_engine,
                            voice=self.config.tts_options.get(
                                "voice_id", "male-qn-qingse"
                            ),
                            rate=self.config.tts_rate,
                            input_path=str(self.config.input_path),
                            **{
                                k: v
                                for k, v in self.config.tts_options.items()
                                if k != "api_key"
                            },
                        )
                    logger.info(f"第 {page_num} 页 音频 -> {audio_path}")

            if page_texts or cached_pages or skipped_pages:
                success_count = len(page_texts) - len(failed_pages) if 'failed_pages' in dir() else len(page_texts)
                parts = []
                if skipped_pages:
                    parts.append(f"跳过已有: {len(skipped_pages)}")
                if self.config.enable_audio_cache:
                    parts.append(f"缓存命中: {len(cached_pages)}")
                    parts.append(f"新转换: {success_count}")
                    if 'failed_pages' in dir() and failed_pages:
                        parts.append(f"失败: {len(failed_pages)}")
                else:
                    parts.append(f"成功: {success_count}")
                    if 'failed_pages' in dir() and failed_pages:
                        parts.append(f"失败: {len(failed_pages)}")
                cache_info = f"（{', '.join(parts)}）"
                logger.info(f"文字转语音完成 {cache_info}")
            else:
                logger.info("没有文本需要转换，跳过 TTS 处理")

            progress.complete_stage(ProcessStage.TTS)

        except Exception as e:
            logger.error(f"TTS 转换失败: {e}")
            progress.fail_stage(ProcessStage.TTS, str(e))
            if "edge-tts" in self.config.tts_engine:
                logger.warning("请检查网络连接，edge-tts 需要访问微软服务器")
                logger.info("提示: 可以使用 --tts-engine minimax 并设置 MINIMAX_API 环境变量")

    def _compose_video(
        self, content: DocumentContent, progress: ProgressTracker
    ) -> None:
        """合成视频：若启用数字人则叠加人脸，否则使用普通合成"""
        video_name = self.config.input_path.stem
        video_path = self.config.output_dir / f"{video_name}.mp4"

        logger.info("开始合成视频...")
        try:
            progress.start_stage(ProcessStage.VIDEO)
            progress.stages[ProcessStage.VIDEO].total = content.total_pages

            if self.config.enable_avatar and self.config.avatar_face_image:
                self._compose_video_with_avatar(content, video_path, progress)
            else:
                VideoComposer.compose(content, self.config, video_path)

            progress.complete_stage(ProcessStage.VIDEO)
        except Exception as e:
            logger.warning(f"视频合成失败: {e}")
            progress.fail_stage(ProcessStage.VIDEO, str(e))

    def _compose_video_with_avatar(
        self,
        content: DocumentContent,
        video_path: Path,
        progress: ProgressTracker,
    ) -> None:
        """使用数字人叠加合成视频"""
        import tempfile
        import shutil

        from .video_composer.composer import (
            FaceVideoGenerator,
            VideoConfig,
            create_image_clip,
            create_circular_video_clip,
            add_transition,
        )
        from moviepy import CompositeVideoClip, AudioFileClip, VideoFileClip

        cfg = self.config
        video_config = VideoConfig(
            width=cfg.avatar_video_width,
            height=cfg.avatar_video_height,
            fps=cfg.video_fps,
            face_position=cfg.avatar_face_position,
            face_margin=cfg.avatar_face_margin,
            face_size=cfg.avatar_face_size,
            transition_duration=cfg.avatar_transition_duration,
        )

        face_generator = FaceVideoGenerator(
            provider_name=cfg.avatar_provider,
            face_image_path=cfg.avatar_face_image,
            provider_config=cfg.avatar_provider_config,
        )

        temp_dir = Path(tempfile.mkdtemp(prefix="vidppt_avatar_"))
        logger.info(f"数字人临时目录: {temp_dir}")

        all_clips = []

        try:
            for page in content.pages:
                if not page.slide_image:
                    logger.warning(f"第 {page.page_number} 页 缺少幻灯片图片，跳过")
                    progress.update_stage(ProcessStage.VIDEO, page.page_number)
                    continue

                logger.info(f"第 {page.page_number} 页 合成数字人视频...")

                if not page.audio:
                    # 无音频：生成无人脸的静态背景片段
                    logger.debug(f"第 {page.page_number} 页 无音频，使用静态背景")
                    clip = create_image_clip(
                        page.slide_image,
                        duration=5.0,
                        fps=video_config.fps,
                        size=(video_config.width, video_config.height),
                    )
                    all_clips.append(clip)
                    progress.update_stage(ProcessStage.VIDEO, page.page_number)
                    continue

                # 获取音频时长
                audio_clip = AudioFileClip(str(page.audio))
                audio_duration = audio_clip.duration
                audio_clip.close()

                # 生成人脸视频（将已有音频传入 provider）
                face_video_path = temp_dir / f"face_{page.page_number}.mp4"
                face_generator.generate(
                    audio_path=page.audio,
                    output_path=face_video_path,
                    text=page.text or "",
                )

                # 背景图片片段
                bg_clip = create_image_clip(
                    page.slide_image,
                    duration=audio_duration,
                    fps=video_config.fps,
                    size=(video_config.width, video_config.height),
                )

                # 圆形人脸片段
                face_clip = create_circular_video_clip(
                    face_video_path, video_config.face_size
                )
                face_w, face_h = face_clip.size
                pos = video_config.get_face_position(face_w, face_h)
                face_clip = face_clip.set_position(pos)

                # 合成背景 + 人脸
                composite = CompositeVideoClip(
                    [bg_clip, face_clip],
                    size=(video_config.width, video_config.height),
                )

                # 使用人脸视频自带的音频（已同步）
                face_with_audio = VideoFileClip(str(face_video_path))
                if face_with_audio.audio:
                    composite = composite.set_audio(face_with_audio.audio)
                else:
                    composite = composite.set_audio(AudioFileClip(str(page.audio)))

                all_clips.append(composite)
                logger.info(f"第 {page.page_number} 页 数字人合成完成")
                progress.update_stage(ProcessStage.VIDEO, page.page_number)

            if not all_clips:
                logger.warning("没有可用的视频片段，跳过输出")
                return

            # 转场 + 拼接
            logger.info("添加转场效果并拼接...")
            final_video = add_transition(all_clips, video_config.transition_duration)

            video_path.parent.mkdir(parents=True, exist_ok=True)
            final_video.write_videofile(
                str(video_path),
                fps=video_config.fps,
                codec=cfg.video_codec,
                audio_codec=cfg.audio_codec,
                logger=None,
            )
            logger.info(f"数字人视频输出: {video_path}")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.debug("数字人临时目录已清理")

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
