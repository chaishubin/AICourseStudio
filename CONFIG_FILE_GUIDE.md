# VidPPT Configuration File Guide

## Overview

VidPPT supports configuration files in **YAML** and **JSON** formats. This allows you to:
- Store commonly used configurations
- Avoid typing long command line arguments
- Share configurations with team members
- Version control your settings

## Quick Start

### 1. Create a Configuration File

**YAML format** (`config.yaml`):
```yaml
input: "presentation.pptx"
output: "outputs"
tts_engine: "edge-tts"
tts_voice: "zh-CN-YunyangNeural"
tts_rate: "+0%"
```

**JSON format** (`config.json`):
```json
{
  "input": "presentation.pptx",
  "output": "outputs",
  "tts_engine": "edge-tts",
  "tts_voice": "zh-CN-YunyangNeural",
  "tts_rate": "+0%"
}
```

### 2. Use the Configuration File

```bash
# Using YAML config
vidppt --config config.yaml

# Using JSON config
vidppt --config config.json

# Override settings with command line arguments
vidppt --config config.yaml input2.pptx --voice zh-CN-YunyangNeural
```

## Configuration Fields

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `input` | string | Path to input file | `"presentation.pptx"` |

### Optional Fields

#### Basic Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `output` | string | `"outputs"` | Output directory path |
| `enable_tts` | boolean | `true` | Enable text-to-speech conversion |
| `enable_video` | boolean | `true` | Enable video composition |
| `save_intermediate` | boolean | `true` | Save intermediate files (text, images) |

#### TTS Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tts_engine` | string | `"edge-tts"` | TTS engine: `"edge-tts"` or `"minimax"` |
| `tts_voice` | string | `"zh-CN-XiaoxiaoNeural"` | Voice selection (engine-specific) |
| `tts_rate` | string | `"+0%"` | Speech rate: `"+20%"`, `"-10%"`, `"1.5"`, etc. |
| `tts_options` | object | `{}` | Engine-specific options |

##### Edge-TTS Voices

- `zh-CN-XiaoxiaoNeural` - Female, warm (default)
- `zh-CN-YunyangNeural` - Male, professional
- `zh-CN-YunxiNeural` - Male, lively
- `zh-CN-XiaoyiNeural` - Female, lively

##### MiniMax TTS Options

When using `"tts_engine": "minimax"`, you can set these options:

```yaml
tts_options:
  emotion: "happy"           # Emotion: happy, sad, angry, neutral, peaceful
  sample_rate: 44100         # Sample rate (Hz): 8000-48000
  bitrate: 256000            # Bitrate (bps): 64000-512000
  audio_format: "mp3"        # Format: "mp3" or "wav"
  # api_key is read from MINIMAX_API environment variable
```

#### Cache Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enable_audio_cache` | boolean | `true` | Enable audio caching |
| `audio_cache_dir` | string | `"~/.cache/vidppt/audio"` | Cache directory (supports `~`) |
| `audio_cache_expiry_days` | integer | `30` | Cache expiry in days |

#### Other Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ocr_engine` | string | `"builtin"` | OCR engine: `"builtin"`, `"tesseract"`, `"api"` |
| `image_converter` | string | `"builtin"` | Image converter: `"builtin"`, `"api"` |
| `video_fps` | integer | `24` | Video frames per second |
| `video_codec` | string | `"libx264"` | Video codec |
| `audio_codec` | string | `"aac"` | Audio codec |

## Path Resolution

Paths in configuration files support the following formats:

- `~/cache` - Expands to user's home directory (e.g., `/home/user/cache`)
- `./output` - Relative to current directory
- `/absolute/path` - Absolute paths
- `output` - Relative to current directory

## Priority and Merging

When using both configuration file and command line arguments:

**CLI arguments have higher priority** than configuration file settings.

Example:
```bash
# config.yaml has:
#   tts_voice: "female"
#   tts_rate: "+0%"

# This command:
vidppt --config config.yaml --tts-rate "+20%"

# Results in:
# - tts_voice: "female" (from config file)
# - tts_rate: "+20%" (overridden by CLI)
```

## Complete Examples

### Basic Configuration (Edge-TTS)

```yaml
input: "presentation.pptx"
output: "outputs"
tts_engine: "edge-tts"
tts_voice: "zh-CN-YunyangNeural"
tts_rate: "+0%"
```

### Advanced Configuration (Edge-TTS with Cache)

```yaml
input: "presentation.pptx"
output: "outputs"
enable_tts: true
enable_video: true
save_intermediate: true

# TTS settings
tts_engine: "edge-tts"
tts_voice: "zh-CN-YunxiNeural"
tts_rate: "+10%"

# Cache settings
enable_audio_cache: true
audio_cache_dir: "~/.cache/vidppt"
audio_cache_expiry_days: 60

# Video settings
video_fps: 30
```

### MiniMax Configuration

```yaml
input: "presentation.pptx"
output: "outputs"

tts_engine: "minimax"
tts_voice: "male-qn-qingse"
tts_rate: "+10%"

tts_options:
  emotion: "happy"
  sample_rate: 44100
  bitrate: 256000
  audio_format: "mp3"

enable_audio_cache: true
audio_cache_expiry_days: 30
```

### Minimal Configuration

```yaml
input: "presentation.pptx"
# All other settings use defaults
```

## Environment Variables

Some settings are read from environment variables if not specified in the config file:

### MiniMax API Key

The MiniMax API key is always read from the `MINIMAX_API` environment variable:

```bash
export MINIMAX_API='sk-cp-your-api-key'
vidppt --config config.yaml
```

This cannot be set in the configuration file for security reasons.

## Configuration File Examples

VidPPT includes example configuration files:

- `examples/config_example.yaml` - Basic YAML example
- `examples/config_example.json` - Basic JSON example  
- `examples/config_minimax.yaml` - MiniMax example

You can copy and modify these examples:

```bash
cp examples/config_example.yaml my_config.yaml
# Edit my_config.yaml with your settings
vidppt --config my_config.yaml
```

## Troubleshooting

### Configuration File Not Found

```
FileNotFoundError: 配置文件不存在: config.yaml
```

**Solution**: Check the file path and make sure the file exists:
```bash
ls -la config.yaml
```

### Invalid Configuration File Format

```
ValueError: 不支持的配置文件格式: .txt
```

**Solution**: Use `.yaml`, `.yml`, or `.json` extensions.

### Missing YAML Library

```
ImportError: YAML 库未安装。请运行: pip install pyyaml
```

**Solution**: Install PyYAML:
```bash
pip install pyyaml
```

Or use JSON format instead.

### Invalid Configuration Values

```
ValueError: 不支持的 TTS 引擎: minimax-plus
```

**Solution**: Check the supported values:
- `tts_engine`: only `"edge-tts"` or `"minimax"`
- `enable_tts`: only `true` or `false`
- etc.

### Configuration Does Not Apply

```
# Config has tts_voice: "male", but video uses female voice
```

**Reason**: Command line arguments override config file settings.

**Solution**: Check if you passed conflicting arguments on the command line:
```bash
vidppt --config config.yaml --voice female-voice
# This would override config.yaml's tts_voice setting
```

## Best Practices

### 1. Use YAML for Readability

YAML is more readable than JSON for configuration files:

```yaml
# Good - YAML
tts_options:
  emotion: "happy"
  sample_rate: 44100
```

vs.

```json
{
  "tts_options": {
    "emotion": "happy",
    "sample_rate": 44100
  }
}
```

### 2. Use Configuration Files for Defaults

Keep your most common settings in a configuration file:

```yaml
# ~/.vidppt/default.yaml
tts_engine: "minimax"
tts_voice: "male-qn-qingse"
tts_rate: "+10%"
enable_audio_cache: true
```

Then use it as a baseline:
```bash
vidppt --config ~/.vidppt/default.yaml input.pptx
```

### 3. Version Control Your Configs

Save configuration files with your project:

```
my_project/
├── config.yaml
├── presentation1.pptx
├── presentation2.pptx
└── README.md
```

### 4. Use Comments

Add comments to explain your settings (YAML only):

```yaml
# Processing settings
input: "presentation.pptx"
output: "outputs"

# Use male voice for professional tone
tts_voice: "zh-CN-YunyangNeural"

# Cache for faster subsequent runs
enable_audio_cache: true
audio_cache_expiry_days: 30
```

### 5. Separate Sensitive Data

For API keys, use environment variables, not config files:

```bash
# Set API key in environment
export MINIMAX_API='sk-cp-xxx'

# Store config in version control without the key
vidppt --config config.yaml
```

## API Key Security

**Never** put API keys in configuration files that you might commit to version control.

Instead:
1. Set the API key as an environment variable
2. Keep configuration files API-key free
3. Add `.gitignore` rules for sensitive files

```bash
# .gitignore
.env
secrets.yaml
*-local.yaml
```

## See Also

- [CLI Guide](CLI_GUIDE.md) - Command line usage
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Quick reference
- [MINIMAX_GUIDE.md](MINIMAX_GUIDE.md) - MiniMax TTS configuration
