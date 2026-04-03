#!/usr/bin/env bash
# 一键安装依赖并运行 PPT 提取 + 视频合成工具
#
# 用法:
#   ./run.sh <ppt文件> [输出目录] [其他参数]
#
# 示例:
#   ./run.sh datas/example.pptx                          # 完整流程，输出到 outputs/
#   ./run.sh datas/example.pptx my_output                # 指定输出目录
#   ./run.sh datas/example.pptx outputs --no-tts         # 跳过语音（也不会生成视频）
#   ./run.sh datas/example.pptx outputs --no-video       # 跳过视频合成
#   ./run.sh datas/example.pptx outputs --voice zh-CN-YunyangNeural  # 男声
#   ./run.sh datas/example.pptx outputs --rate +20%      # 加速20%
#
# 可选 TTS 声音角色:
#   zh-CN-XiaoxiaoNeural  女声·温暖（默认）
#   zh-CN-YunyangNeural   男声·专业
#   zh-CN-YunxiNeural     男声·活泼
#   zh-CN-XiaoyiNeural    女声·活泼
#
# 输出结构:
#   outputs/
#   ├── <ppt同名>.mp4        ← 最终合成视频
#   ├── 1/
#   │   ├── text.txt         ← 页面文字
#   │   ├── slide.png        ← 整页截图
#   │   ├── audio.mp3        ← 页面语音
#   │   └── image_*.png/jpg  ← 内嵌图片
#   └── 2/ ...

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PPT_FILE="${1:-}"
OUTPUT_DIR="${2:-outputs}"

if [ -z "$PPT_FILE" ]; then
	echo "用法: $0 <ppt文件路径> [输出目录] [--no-tts] [--no-video] [--voice <角色>] [--rate <语速>]"
	echo "示例: $0 datas/example.pptx outputs"
	exit 1
fi

echo ">>> 安装依赖..."
uv sync

echo ">>> 开始处理: $PPT_FILE"
uv run python extract_ppt.py "$PPT_FILE" -o "$OUTPUT_DIR" "${@:3}"
