"""
命令行入口
"""

import argparse
import sys
from pathlib import Path

from loguru import logger

from .core.models import ProcessConfig
from .core.registry import ProcessorRegistry
from .pipeline import Pipeline
from .course_pipeline import CoursePipeline
from .utils.logger import setup_logger
from .utils.config_loader import load_config_file, ConfigLoader
from .utils.config_converter import ConfigConverter

# 导入所有处理器以触发注册
from .processors.ppt_processor import PPTProcessor
from .processors.pdf_processor import PDFProcessor


def main():
    """主入口函数"""
    supported_formats = ", ".join(
        sorted(set(ProcessorRegistry.list_supported_extensions()) | {".docx"})
    )

    parser = argparse.ArgumentParser(
        description="AI Course Studio - AI 课程生产平台\n从教案（Word/PDF）或演示文稿（PPT）经 AI 理解与知识建模，生成课程视频、幻灯片、HTML 三路输出。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
示例:
  %(prog)s input.pptx                           # 路线 B：PPT → 视频（保留原样式）
  %(prog)s input.docx -o outputs                # 路线 A：教案 → 课程产出（规划中）
  %(prog)s input.pptx --no-tts                  # 跳过语音合成
  %(prog)s input.pptx --no-video                # 跳过视频合成
  %(prog)s input.pptx --voice zh-CN-YunyangNeural  # 使用男声 (edge-tts)
  %(prog)s input.pptx --rate +20%%              # 加速20%%
  %(prog)s input.pptx --face face.jpg           # 启用数字人叠加（默认 sadtalker）

配置文件示例:
  %(prog)s --config config.yaml                 # 使用 YAML 配置文件
  %(prog)s --config config.json                 # 使用 JSON 配置文件
  %(prog)s --config config.yaml input.pptx      # 配置文件 + 命令行覆盖
  
MiniMax TTS 示例:
   %(prog)s input.pptx --tts-engine minimax      # 使用 MiniMax 引擎
   %(prog)s input.pptx --tts-engine minimax --minimax-emotion happy  # 开心情感
   %(prog)s input.pptx --tts-engine minimax --rate -10%%  # 减速10%%
   %(prog)s input.pptx --tts-engine minimax \\
                     --minimax-emotion peaceful \\
                     --minimax-sample-rate 44100 \\
                     --minimax-bitrate 256000    # 高质量配置

缓存选项:
   %(prog)s input.pptx --no-cache               # 禁用音频缓存
   %(prog)s input.pptx --cache-dir /tmp/cache   # 自定义缓存目录
   %(prog)s input.pptx --cache-expiry 7         # 7天后缓存过期

LLM 文本摘要示例:
   %(prog)s input.pptx --llm                    # 启用逐页摘要
   %(prog)s input.pptx --llm --llm-mode whole-document  # 整文档摘要
   %(prog)s input.pptx --llm --llm-engine openai --llm-model gpt-4o-mini  # 使用 ChatGPT
   %(prog)s input.pptx --llm --llm-temperature 0.5       # 降低随机性

千问 + 火山引擎示例:
   %(prog)s lesson.docx --llm --llm-engine qwen \\
                     --tts-engine volcengine \\
                     --voice zh_female_cancan_mars_bigtts

可用的 TTS 声音（edge-tts）:
  zh-CN-XiaoxiaoNeural  女声·温暖（默认）
  zh-CN-YunyangNeural   男声·专业
  zh-CN-YunxiNeural     男声·活泼
  zh-CN-XiaoyiNeural    女声·活泼

支持的文件格式:
  {supported_formats}
        """,
    )

    # 位置参数
    parser.add_argument(
        "input", nargs="?", default=None, help="输入文件路径（PPT/PDF/Word）"
    )

    # 配置文件
    parser.add_argument(
        "--config", default=None, help="配置文件路径（支持 YAML/JSON 格式）"
    )

    # 输出配置
    parser.add_argument(
        "-o", "--output", default="outputs", help="输出目录（默认: outputs）"
    )

    # 功能开关
    parser.add_argument("--no-tts", action="store_true", help="跳过文字转语音步骤")
    parser.add_argument("--no-video", action="store_true", help="跳过视频合成步骤")
    parser.add_argument(
        "--no-intermediate",
        action="store_true",
        help="不保存中间文件（文本、图片等），仅保留最终视频",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="强制重新处理所有页面，即使输出文件已存在",
    )

    # TTS 配置
    parser.add_argument(
        "--tts-engine",
        default="edge-tts",
        choices=["edge-tts", "minimax", "volcengine"],
        help="TTS 引擎（默认: edge-tts）",
    )
    parser.add_argument(
        "--voice",
        default="zh-CN-XiaoxiaoNeural",
        help="声音 ID；火山引擎请填写 voice_type",
    )
    parser.add_argument(
        "--rate",
        default="+0%",
        help="语速调整，如 +20%% 加快，-10%% 减慢（默认: +0%%）",
    )

    # MiniMax 特定选项
    parser.add_argument(
        "--minimax-emotion",
        default="neutral",
        choices=["happy", "sad", "angry", "neutral", "peaceful"],
        help="MiniMax TTS 情感类型（默认: neutral）",
    )
    parser.add_argument(
        "--minimax-sample-rate",
        type=int,
        default=32000,
        help="MiniMax 采样率（默认: 32000）",
    )
    parser.add_argument(
        "--minimax-bitrate",
        type=int,
        default=128000,
        help="MiniMax 比特率（默认: 128000）",
    )
    parser.add_argument(
        "--minimax-format",
        default="mp3",
        choices=["mp3", "wav"],
        help="MiniMax 音频格式（默认: mp3）",
    )
    parser.add_argument(
        "--volc-appid",
        default=None,
        help="火山引擎 AppID（默认读取 VOLCENGINE_TTS_APPID）",
    )
    parser.add_argument(
        "--volc-access-token",
        default=None,
        help="火山引擎 Access Token（默认读取 VOLCENGINE_TTS_ACCESS_TOKEN）",
    )
    parser.add_argument(
        "--volc-cluster",
        default="volcano_tts",
        help="火山 TTS 业务集群（默认: volcano_tts）",
    )

    # 缓存配置
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="禁用音频缓存，每次都重新转换",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="自定义音频缓存目录（默认: ~/.cache/vidppt/audio）",
    )
    parser.add_argument(
        "--cache-expiry",
        type=int,
        default=30,
        help="音频缓存过期天数（默认: 30）",
    )

    # 渲染配置
    parser.add_argument(
        "--render-engine",
        default="spire",
        choices=["spire", "libreoffice"],
        help="幻灯片渲染引擎（默认: spire）",
    )

    # 数字人配置
    parser.add_argument(
        "--face",
        default=None,
        help="人脸图片路径；提供此参数后自动启用数字人叠加模式",
    )
    parser.add_argument(
        "--provider",
        default="sadtalker",
        choices=["sadtalker", "heygen"],
        help="数字人后端（默认: sadtalker）",
    )
    parser.add_argument(
        "--provider-config",
        default=None,
        help='数字人 Provider 专属配置（JSON 格式，如 \'{"api_key":"xxx"}\'）',
    )
    parser.add_argument(
        "--face-position",
        default="bottom-right",
        choices=["top-left", "top-right", "bottom-left", "bottom-right"],
        help="数字人位置（默认: bottom-right）",
    )
    parser.add_argument(
        "--face-size",
        type=int,
        default=300,
        help="数字人圆形直径，单位像素（默认: 300）",
    )
    parser.add_argument(
        "--face-margin",
        type=int,
        default=50,
        help="数字人距视频边缘的边距，单位像素（默认: 50）",
    )
    parser.add_argument(
        "--transition",
        type=float,
        default=1.0,
        help="转场淡入淡出时长，单位秒（默认: 1.0）",
    )

    # LLM 配置
    parser.add_argument(
        "--llm",
        action="store_true",
        help="启用 LLM 文本摘要/改写",
    )
    parser.add_argument(
        "--llm-engine",
        default="qwen",
        choices=["qwen", "openai"],
        help="LLM 引擎（默认: qwen）",
    )
    parser.add_argument(
        "--llm-mode",
        default="per-page",
        choices=["per-page", "whole-document"],
        help="LLM 摘要模式（默认: per-page）",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="LLM 模型名称（默认: 引擎默认模型）",
    )
    parser.add_argument(
        "--llm-system-prompt",
        default=None,
        help="自定义 LLM 系统提示词",
    )
    parser.add_argument(
        "--llm-temperature",
        type=float,
        default=None,
        help="LLM 生成温度（默认: 0.7）",
    )
    parser.add_argument(
        "--llm-max-tokens",
        type=int,
        default=None,
        help="LLM 最大 token 数（默认: 4096）",
    )

    # 日志配置
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="启用详细日志输出（包括时间戳和函数名）",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="日志等级（默认: INFO）",
    )
    parser.add_argument(
        "--log-file", default=None, help="日志文件路径（默认: 仅输出到控制台）"
    )

    args = parser.parse_args()

    # 初始化日志系统
    setup_logger(
        name="vidppt",
        level=args.log_level.upper(),
        verbose=args.verbose,
        log_file=args.log_file,
    )

    logger.info(f"AI Course Studio 启动 (日志等级: {args.log_level})")
    if args.log_file:
        logger.info(f"日志文件: {args.log_file}")

    # 加载配置文件（如果提供了）
    config_dict = {}
    if args.config:
        logger.info(f"加载配置文件: {args.config}")
        try:
            config_dict = load_config_file(args.config)
            logger.debug(f"配置文件加载成功，包含 {len(config_dict)} 个字段")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            sys.exit(1)

    # 将命令行参数转换为配置字典
    cli_config = {}

    # 如果提供了输入文件作为位置参数，覆盖配置文件中的 input
    if args.input:
        cli_config["input"] = args.input
    if args.output != "outputs":  # 非默认值
        cli_config["output"] = args.output
    if args.no_tts:
        cli_config["enable_tts"] = False
    if args.no_video:
        cli_config["enable_video"] = False
    if args.no_intermediate:
        cli_config["save_intermediate"] = False
    if args.no_skip_existing:
        cli_config["skip_existing"] = False
    if args.tts_engine != "edge-tts":
        cli_config["tts_engine"] = args.tts_engine
    # --voice 的含义取决于引擎：
    # edge-tts -> tts_voice（如 zh-CN-XiaoxiaoNeural）
    # minimax -> voice_id；volcengine -> voice_type
    if args.tts_engine == "minimax":
        # minimax 的 voice 通过 tts_options.voice_id 传递，tts_voice 对其无意义
        if args.voice != "zh-CN-XiaoxiaoNeural":
            # 用户明确指定了 voice，写入 tts_options
            tts_options_cli = cli_config.get("tts_options", {})
            tts_options_cli["voice_id"] = args.voice
            cli_config["tts_options"] = tts_options_cli
    elif args.tts_engine == "volcengine":
        tts_options_cli = cli_config.get("tts_options", {})
        if args.voice != "zh-CN-XiaoxiaoNeural":
            tts_options_cli["voice_type"] = args.voice
        if args.volc_appid:
            tts_options_cli["appid"] = args.volc_appid
        if args.volc_access_token:
            tts_options_cli["access_token"] = args.volc_access_token
        if args.volc_cluster != "volcano_tts":
            tts_options_cli["cluster"] = args.volc_cluster
        cli_config["tts_options"] = tts_options_cli
    else:
        if args.voice != "zh-CN-XiaoxiaoNeural":
            cli_config["tts_voice"] = args.voice
    if args.rate != "+0%":
        cli_config["tts_rate"] = args.rate
    if args.no_cache:
        cli_config["enable_audio_cache"] = False
    if args.cache_dir:
        cli_config["audio_cache_dir"] = args.cache_dir
    if args.cache_expiry != 30:
        cli_config["audio_cache_expiry_days"] = args.cache_expiry
    if args.render_engine != "spire":
        cli_config["render_engine"] = args.render_engine

    # 数字人参数
    if args.face:
        import json as _json

        cli_config["enable_avatar"] = True
        cli_config["avatar_face_image"] = args.face
        cli_config["avatar_provider"] = args.provider
        if args.provider_config:
            try:
                cli_config["avatar_provider_config"] = _json.loads(args.provider_config)
            except Exception:
                logger.warning(
                    f"--provider-config 解析失败，忽略: {args.provider_config}"
                )
        cli_config["avatar_face_position"] = args.face_position
        cli_config["avatar_face_size"] = args.face_size
        cli_config["avatar_face_margin"] = args.face_margin
        cli_config["avatar_transition_duration"] = args.transition

    # LLM 参数
    if args.llm:
        cli_config["llm_enabled"] = True
        cli_config["llm_engine"] = args.llm_engine
        cli_config["llm_mode"] = args.llm_mode
        llm_options_cli = cli_config.get("llm_options", {})
        if args.llm_model:
            llm_options_cli["model"] = args.llm_model
        if args.llm_system_prompt:
            llm_options_cli["system_prompt"] = args.llm_system_prompt
        if args.llm_temperature is not None:
            llm_options_cli["temperature"] = args.llm_temperature
        if args.llm_max_tokens is not None:
            llm_options_cli["max_tokens"] = args.llm_max_tokens
        if llm_options_cli:
            cli_config["llm_options"] = llm_options_cli

    # 合并配置
    if args.config and not config_dict.get("input") and not args.input:
        logger.error(
            "错误: 必须指定输入文件，要么通过 --config 文件中的 'input' 字段，要么通过命令行位置参数"
        )
        sys.exit(1)

    # 合并配置文件和 CLI 参数（CLI 参数优先）
    merged_config = {**config_dict, **cli_config}

    # MiniMax 选项（如果指定了 MiniMax）
    if merged_config.get("tts_engine") == "minimax" and not args.config:
        tts_options = merged_config.get("tts_options", {})
        # 始终设置所有 MiniMax 选项（包括默认值）
        # voice_id：如果用户通过 --voice 明确指定则已写入，否则用默认值
        if "voice_id" not in tts_options:
            tts_options["voice_id"] = "male-qn-qingse"
        tts_options["emotion"] = args.minimax_emotion
        tts_options["sample_rate"] = args.minimax_sample_rate
        tts_options["bitrate"] = args.minimax_bitrate
        tts_options["audio_format"] = args.minimax_format
        merged_config["tts_options"] = tts_options

    # 转换为 ProcessConfig
    try:
        config = ConfigConverter.to_process_config(merged_config)
    except Exception as e:
        logger.error(f"配置转换失败: {e}")
        sys.exit(1)

    # 路线 A：教案先生成 Course JSON 和可编辑 PPTX，再复用媒体组件。
    if config.input_path.suffix.lower() in {".docx", ".pdf"}:
        llm_engine = None
        if config.llm_enabled:
            if config.llm_engine == "qwen":
                from .engines.llm.qwen_llm_engine import QwenLLMEngine

                llm_engine = QwenLLMEngine(**config.llm_options)
            elif config.llm_engine == "openai":
                from .engines.llm.openai_llm_engine import OpenAILLMEngine

                llm_engine = OpenAILLMEngine(**config.llm_options)
            else:
                logger.error(f"不支持的课程生成 LLM: {config.llm_engine}")
                sys.exit(1)

        result = CoursePipeline(llm_engine).run(
            config.input_path,
            config.output_dir,
            media_config=config,
        )
        logger.info(f"课程模型: {result.course_json}")
        logger.info(f"可编辑 PPT: {result.presentation}")
        if result.subtitles:
            logger.info(f"字幕文件: {result.subtitles}")
        if result.video:
            logger.info(f"课程视频: {result.video}")
        return

    # 路线 B：保留原 PPT 视觉样式并生成视频。
    pipeline = Pipeline(config)
    pipeline.run()


if __name__ == "__main__":
    main()
