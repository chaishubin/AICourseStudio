# VidPPT CLI 使用指南

## 快速开始

### 基础用法

```bash
# 使用 edge-tts 引擎（默认）
python -m vidppt input.pptx

# 或者使用 vidppt 命令（如果已安装）
vidppt input.pptx
```

### 指定输出目录

```bash
python -m vidppt input.pptx -o my_output
# 或
python -m vidppt input.pptx --output my_output
```

## 渲染引擎配置

### 选择渲染引擎

VidPPT 支持两种幻灯片渲染引擎，通过 `--render-engine` 参数选择：

```bash
# 使用 Spire（默认）
python -m vidppt input.pptx --render-engine spire

# 使用 LibreOffice
python -m vidppt input.pptx --render-engine libreoffice
```

**引擎对比**：

| 特性 | Spire | LibreOffice |
|------|-------|-------------|
| 默认引擎 | 是 | 否 |
| 中文排版 | 字形替换风险 | 通过 fontconfig 兼容 |
| 安装要求 | pip 安装即可 | 需安装 LibreOffice + 中文字体 |
| 渲染速度 | 较快 | 首次启动较慢 |
| 渲染质量 | 依赖系统字体 | 对中文更友好 |

### LibreOffice 环境准备

使用 `--render-engine libreoffice` 前需安装系统依赖：

**Arch/Manjaro**：
```bash
sudo pacman -S libreoffice-fresh poppler
# 中文字体（推荐）
sudo pacman -S noto-fonts-cjk adobe-source-han-sans-cn-fonts adobe-source-han-serif-cn-fonts
```

**Ubuntu/Debian**：
```bash
sudo apt install libreoffice-impress poppler-utils
sudo apt install fonts-noto-cjk fonts-wqy-zenhei
```

**macOS**：
```bash
brew install --cask libreoffice
brew install poppler font-noto-sans-cjk-sc
```

安装后验证：
```bash
libreoffice --version
fc-list :lang=zh | head -5  # 检查中文字体
```

### 配置文件中指定渲染引擎

在 YAML/JSON 配置文件中添加 `render_engine` 字段：

```yaml
input: presentation.pptx
output: outputs
render_engine: libreoffice
```

### 仅渲染测试

```bash
# 使用 LibreOffice 渲染，跳过 TTS 和视频合成
python -m vidppt input.pptx --render-engine libreoffice --no-tts --no-video
```

## 功能开关

### 跳过语音合成

```bash
# 仅进行文档处理和图片提取，不生成语音
python -m vidppt input.pptx --no-tts
```

### 跳过视频合成

```bash
# 仅进行文档处理和语音生成，不合成视频
python -m vidppt input.pptx --no-video
```

### 不保存中间文件

```bash
# 仅保留最终视频，删除中间的文本、图片、音频文件
python -m vidppt input.pptx --no-intermediate
```

## EdgeTTS 配置

### 选择不同的语音

```bash
# 使用男声
python -m vidppt input.pptx --voice zh-CN-YunyangNeural

# 使用其他男声
python -m vidppt input.pptx --voice zh-CN-YunxiNeural

# 使用其他女声
python -m vidppt input.pptx --voice zh-CN-XiaoyiNeural
```

**可用语音列表**（edge-tts）：
- `zh-CN-XiaoxiaoNeural` - 女声·温暖（默认）
- `zh-CN-YunyangNeural` - 男声·专业
- `zh-CN-YunxiNeural` - 男声·活泼
- `zh-CN-XiaoyiNeural` - 女声·活泼

### 调整语速

```bash
# 加快 20%
python -m vidppt input.pptx --rate +20%

# 减慢 10%
python -m vidppt input.pptx --rate -10%

# 1.5 倍速
python -m vidppt input.pptx --rate 1.5
```

**语速支持的格式**：
- `+20%` - 增加 20%
- `-10%` - 减少 10%
- `1.5` - 直接指定倍数
- 范围：0.5x ~ 2.0x

## MiniMax TTS 配置

### 基础使用

```bash
# 使用 MiniMax 引擎
python -m vidppt input.pptx --tts-engine minimax

# 必须设置环境变量
export MINIMAX_API='sk-cp-your-api-key'
```

### 情感类型

```bash
# 开心
python -m vidppt input.pptx --tts-engine minimax --minimax-emotion happy

# 悲伤
python -m vidppt input.pptx --tts-engine minimax --minimax-emotion sad

# 愤怒
python -m vidppt input.pptx --tts-engine minimax --minimax-emotion angry

# 中立（默认）
python -m vidppt input.pptx --tts-engine minimax --minimax-emotion neutral

# 平和
python -m vidppt input.pptx --tts-engine minimax --minimax-emotion peaceful
```

### 音频质量配置

```bash
# 标准质量（默认）
python -m vidppt input.pptx --tts-engine minimax

# 高质量配置
python -m vidppt input.pptx --tts-engine minimax \
    --minimax-sample-rate 44100 \
    --minimax-bitrate 256000 \
    --minimax-format wav

# 低质量配置（节省空间）
python -m vidppt input.pptx --tts-engine minimax \
    --minimax-sample-rate 16000 \
    --minimax-bitrate 64000
```

**音频参数说明**：
- `--minimax-sample-rate` - 采样率，默认 32000
- `--minimax-bitrate` - 比特率，默认 128000
- `--minimax-format` - 格式，支持 mp3 和 wav

## 完整使用示例

### 示例 1：使用 EdgeTTS 加快语速

```bash
python -m vidppt presentation.pptx -o outputs --rate +15%
```

### 示例 2：使用 MiniMax 开心情感

```bash
export MINIMAX_API='sk-cp-your-api-key'
python -m vidppt presentation.pptx \
    --tts-engine minimax \
    --minimax-emotion happy \
    --rate +10%
```

### 示例 3：只生成音频，不合成视频

```bash
python -m vidppt presentation.pptx \
    --no-video \
    --save-intermediate
```

### 示例 4：高质量 MiniMax 输出

```bash
export MINIMAX_API='sk-cp-your-api-key'
python -m vidppt presentation.pptx \
    --tts-engine minimax \
    --minimax-emotion peaceful \
    --minimax-sample-rate 44100 \
    --minimax-bitrate 256000 \
    --minimax-format wav
```

### 示例 5：组合多个选项

```bash
export MINIMAX_API='sk-cp-your-api-key'
python -m vidppt input.pptx \
    -o high_quality_output \
    --tts-engine minimax \
    --minimax-emotion happy \
    --rate +20% \
    --minimax-sample-rate 44100 \
    --minimax-bitrate 256000
```

## 环境变量设置

### Linux/Mac

```bash
# 临时设置（仅当前会话）
export MINIMAX_API='sk-cp-your-api-key'

# 永久设置（添加到 ~/.bashrc 或 ~/.zshrc）
echo "export MINIMAX_API='sk-cp-your-api-key'" >> ~/.bashrc
source ~/.bashrc
```

### Windows CMD

```cmd
setx MINIMAX_API "sk-cp-your-api-key"
```

### Windows PowerShell

```powershell
[Environment]::SetEnvironmentVariable("MINIMAX_API", "sk-cp-your-api-key", "User")
```

## 获取帮助

### 查看所有可用选项

```bash
python -m vidppt --help
# 或
vidppt --help
```

### 查看版本

```bash
# 查看 pyproject.toml 中定义的版本
cat pyproject.toml | grep version
```

## 常见错误

### 错误：LibreOffice 未安装

```
FileNotFoundError: [Errno 2] No such file or directory: 'libreoffice'
```

**解决**：安装 LibreOffice（参见上方"LibreOffice 环境准备"）

### 错误：中文字体缺失导致字形替换

**现象**：使用 Spire 渲染时，某些中文字符显示为形近错字（如"径"显示为其他字）

**解决**：
```bash
# 方案 1：切换到 LibreOffice 引擎
python -m vidppt input.pptx --render-engine libreoffice

# 方案 2：安装缺失字体后继续使用 Spire
sudo pacman -S noto-fonts-cjk
fc-cache -fv
```

### 错误：输入文件不存在

```
Error: [Errno 2] No such file or directory: 'input.pptx'
```

**解决**：确保输入文件路径正确
```bash
# 检查文件是否存在
ls -la input.pptx

# 使用绝对路径
python -m vidppt /path/to/input.pptx
```

### 错误：不支持的文件格式

```
ValueError: Unsupported file type
```

**解决**：确保使用支持的格式（PPT/PPTX/PDF）
```bash
# 检查文件类型
file input.pptx
```

### 错误：MiniMax API key 未设置

```
AssertionError: MiniMax API key 未设置。请设置环境变量 MINIMAX_API
```

**解决**：设置 MINIMAX_API 环境变量
```bash
export MINIMAX_API='sk-cp-your-api-key'
python -m vidppt input.pptx --tts-engine minimax
```

## 调用方式

VidPPT 支持两种调用方式：

### 方式 1：使用 `python -m` 模块方式（推荐）

```bash
python -m vidppt input.pptx [options]
```

优点：
- 不需要安装，直接使用源代码
- 跨平台兼容

### 方式 2：安装后直接使用命令

```bash
# 安装
pip install -e .

# 使用
vidppt input.pptx [options]
```

优点：
- 更方便，无需 `python -m` 前缀
- 直接集成到系统命令

## 性能建议

### 快速处理（默认）
```bash
python -m vidppt input.pptx --tts-engine edge-tts
```

### 高质量处理（MiniMax）
```bash
export MINIMAX_API='sk-cp-your-api-key'
python -m vidppt input.pptx \
    --tts-engine minimax \
    --minimax-sample-rate 44100 \
    --minimax-bitrate 256000 \
    --minimax-format wav
```

### 最小化输出
```bash
python -m vidppt input.pptx \
    --no-intermediate \
    --minimax-bitrate 64000
```

## 更多信息

- 详见 `ENV_VAR_SETUP.md` - 环境变量详细配置
- 详见 `MINIMAX_GUIDE.md` - MiniMax 完整使用指南
- 详见 `QUICK_REFERENCE.md` - 快速参考卡片

---

**最后更新**: 2026-05-08
**版本**: v0.2.0
