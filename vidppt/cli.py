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
from .utils.logger import setup_logger
from .utils.config_loader import load_config_file, ConfigLoader
from .utils.config_converter import ConfigConverter

# 导入所有处理器以触发注册
from .processors.ppt_processor import PPTProcessor
from .processors.pdf_processor import PDFProcessor


def main():
    """主入口函数"""
    supported_formats = ", ".join(ProcessorRegistry.list_supported_extensions())

    parser = argparse.ArgumentParser(
        description="将文档（PPT/PDF/Word）转换为配音视频",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
示例:
  %(prog)s input.pptx                           # 完整流程
  %(prog)s input.pptx -o outputs                # 指定输出目录
  %(prog)s input.pptx --no-tts                  # 跳过语音合成
  %(prog)s input.pptx --no-video                # 跳过视频合成
  %(prog)s input.pptx --no-intermediate         # 不保存中间文件
  %(prog)s input.pptx --voice zh-CN-YunyangNeural  # 使用男声 (edge-tts)
  %(prog)s input.pptx --rate +20%%              # 加速20%%
  
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

    # TTS 配置
    parser.add_argument(
        "--tts-engine",
        default="edge-tts",
        choices=["edge-tts", "minimax"],
        help="TTS 引擎（默认: edge-tts）",
    )
    parser.add_argument(
        "--voice",
        default="zh-CN-XiaoxiaoNeural",
        help="TTS 声音角色（edge-tts 默认: zh-CN-XiaoxiaoNeural；minimax 请填写 voice_id，如 male-qn-qingse）",
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

    # 日志配置
    parser.add_argument(
        "-v",
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

    logger.info(f"VidPPT 启动 (日志等级: {args.log_level})")
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
    if args.tts_engine != "edge-tts":
        cli_config["tts_engine"] = args.tts_engine
    # --voice 的含义取决于引擎：
    # edge-tts -> tts_voice（如 zh-CN-XiaoxiaoNeural）
    # minimax  -> tts_options.voice_id（如 male-qn-qingse）
    if args.tts_engine == "minimax":
        # minimax 的 voice 通过 tts_options.voice_id 传递，tts_voice 对其无意义
        if args.voice != "zh-CN-XiaoxiaoNeural":
            # 用户明确指定了 voice，写入 tts_options
            tts_options_cli = cli_config.get("tts_options", {})
            tts_options_cli["voice_id"] = args.voice
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

    # 创建并运行流程
    pipeline = Pipeline(config)
    pipeline.run()


if __name__ == "__main__":
    main()
