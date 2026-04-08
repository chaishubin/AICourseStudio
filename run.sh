#!/usr/bin/env bash
# 一键安装依赖并运行文档到视频转换工具（重构版本）
#
# 用法:
#   ./run.sh <文件> [输出目录] [其他参数]
#
# 示例:
#   ./run.sh datas/example.pptx                          # 完整流程，输出到 outputs/
#   ./run.sh datas/example.pptx my_output                # 指定输出目录
#   ./run.sh datas/example.pptx outputs --no-tts         # 跳过语音
#   ./run.sh datas/example.pptx outputs --no-video       # 跳过视频合成
#   ./run.sh datas/example.pptx outputs --no-intermediate  # 不保存中间文件
#   ./run.sh datas/example.pptx outputs --voice zh-CN-YunyangNeural  # 男声
#   ./run.sh datas/example.pptx outputs --rate +20%      # 加速20%
#
# 可选 TTS 声音角色（edge-tts）:
#   zh-CN-XiaoxiaoNeural  女声·温暖（默认）
#   zh-CN-YunyangNeural   男声·专业
#   zh-CN-YunxiNeural     男声·活泼
#   zh-CN-XiaoyiNeural    女声·活泼
#
# 输出结构（--save-intermediate 时）:
#   outputs/
#   ├── <文件同名>.mp4        ← 最终合成视频
#   ├── 1/
#   │   ├── text.txt         ← 页面文字
#   │   ├── slide.png        ← 整页截图
#   │   ├── audio.mp3        ← 页面语音
#   │   └── image_*.png/jpg  ← 内嵌图片（如果有）
#   └── 2/ ...

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

INPUT_FILE="${1:-}"
OUTPUT_DIR="${2:-outputs}"

if [ -z "$INPUT_FILE" ]; then
	echo "用法: $0 <文件路径> [输出目录] [选项]"
	echo ""
	echo "支持的文件格式: .ppt, .pptx, .pdf (需要额外依赖)"
	echo ""
	echo "常用选项:"
	echo "  --no-tts            跳过语音合成"
	echo "  --no-video          跳过视频合成"
	echo "  --no-intermediate   不保存中间文件"
	echo "  --voice <角色>       指定TTS声音"
	echo "  --rate <语速>        调整语速（如 +20% 或 -10%）"
	echo ""
	echo "示例:"
	echo "  $0 datas/example.pptx"
	echo "  $0 datas/example.pptx outputs --no-intermediate"
	exit 1
fi

echo ">>> 安装依赖..."
uv sync

echo ">>> 开始处理: $INPUT_FILE"
# 使用新的 CLI 入口
uv run vidppt "$INPUT_FILE" -o "$OUTPUT_DIR" "${@:3}"

