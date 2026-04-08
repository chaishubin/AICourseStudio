"""
命令行入口
"""
import argparse
import sys
from pathlib import Path

from .core.models import ProcessConfig
from .core.registry import ProcessorRegistry
from .pipeline import Pipeline

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
  %(prog)s input.pptx --voice zh-CN-YunyangNeural  # 使用男声
  %(prog)s input.pptx --rate +20%%              # 加速20%%
  %(prog)s input.pptx --tts-engine minimax      # 使用其他 TTS 引擎

可用的 TTS 声音（edge-tts）:
  zh-CN-XiaoxiaoNeural  女声·温暖（默认）
  zh-CN-YunyangNeural   男声·专业
  zh-CN-YunxiNeural     男声·活泼
  zh-CN-XiaoyiNeural    女声·活泼

支持的文件格式:
  {supported_formats}
        """
    )
    
    # 位置参数
    parser.add_argument(
        "input",
        help="输入文件路径（PPT/PDF/Word）"
    )
    
    # 输出配置
    parser.add_argument(
        "-o", "--output",
        default="outputs",
        help="输出目录（默认: outputs）"
    )
    
    # 功能开关
    parser.add_argument(
        "--no-tts",
        action="store_true",
        help="跳过文字转语音步骤"
    )
    parser.add_argument(
        "--no-video",
        action="store_true",
        help="跳过视频合成步骤"
    )
    parser.add_argument(
        "--no-intermediate",
        action="store_true",
        help="不保存中间文件（文本、图片等），仅保留最终视频"
    )
    
    # TTS 配置
    parser.add_argument(
        "--tts-engine",
        default="edge-tts",
        choices=["edge-tts", "minimax", "api"],
        help="TTS 引擎（默认: edge-tts）"
    )
    parser.add_argument(
        "--voice",
        default="zh-CN-XiaoxiaoNeural",
        help="TTS 声音角色（默认: zh-CN-XiaoxiaoNeural）"
    )
    parser.add_argument(
        "--rate",
        default="+0%",
        help="语速调整，如 +20%% 加快，-10%% 减慢（默认: +0%%）"
    )
    
    # OCR 配置
    parser.add_argument(
        "--ocr-engine",
        default="builtin",
        choices=["builtin", "tesseract", "api"],
        help="OCR 引擎（默认: builtin）"
    )
    
    # 图像转换配置
    parser.add_argument(
        "--image-converter",
        default="builtin",
        choices=["builtin", "api"],
        help="图像转换器（默认: builtin）"
    )
    
    args = parser.parse_args()
    
    # 显示注册的处理器
    print("=" * 60)
    print("文档到视频转换工具")
    print("=" * 60)
    print("\n注册的文档处理器:")
    
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
        ocr_engine=args.ocr_engine,
        image_converter=args.image_converter,
    )
    
    # 创建并运行流程
    pipeline = Pipeline(config)
    pipeline.run()


if __name__ == "__main__":
    main()
