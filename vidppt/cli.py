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
    parser.add_argument("input", help="输入文件路径（PPT/PDF/Word）")

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
        help="TTS 声音角色（默认: zh-CN-XiaoxiaoNeural）",
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

    # 构建 TTS 选项字典
    tts_options = {}
    if args.tts_engine == "minimax":
        tts_options = {
            "emotion": args.minimax_emotion,
            "sample_rate": args.minimax_sample_rate,
            "bitrate": args.minimax_bitrate,
            "audio_format": args.minimax_format,
            # api_key 将从环境变量 MINIMAX_API 自动读取
        }

    # 显示配置信息
    logger.info("=" * 60)
    logger.info("文档到视频转换工具")
    logger.info("=" * 60)
    logger.info("注册的文档处理器:")

    # 创建配置
    config = ProcessConfig(
        input_path=Path(args.input),
        output_dir=Path(args.output),
        enable_tts=not args.no_tts,
        enable_video=not args.no_video,
        save_intermediate=not args.no_intermediate,
        tts_engine=args.tts_engine,
        tts_voice=args.voice,
        tts_rate=args.rate,
        tts_options=tts_options,
        enable_audio_cache=not args.no_cache,
        audio_cache_dir=Path(args.cache_dir) if args.cache_dir else None,
        audio_cache_expiry_days=args.cache_expiry,
    )

    # 创建并运行流程
    pipeline = Pipeline(config)
    pipeline.run()


if __name__ == "__main__":
    main()
