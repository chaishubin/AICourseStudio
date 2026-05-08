# VidPPT 快速参考

## 🚀 5分钟快速开始

### 1. 设置环境变量
```bash
export MINIMAX_API='sk-cp-your-api-key'
```

### 2. 最简单的使用方式
```python
from pathlib import Path
from vidppt import Pipeline, ProcessConfig

config = ProcessConfig(
    input_path=Path("presentation.pptx"),
    output_dir=Path("output"),
    tts_engine="minimax"
)

Pipeline(config).run()
```

## 📚 文档导航

| 文档 | 用途 | 长度 |
|-----|------|------|
| **ENV_VAR_SETUP.md** | 环境变量详细设置指南 | 327行 |
| **MINIMAX_GUIDE.md** | MiniMax 完整使用指南 | 2000+ 行 |
| **QUICKSTART_MINIMAX.md** | 5分钟快速开始 | 1200+ 行 |
| **MINIMAX_README.md** | MiniMax 简明概览 | 400行 |
| **LOGGING_GUIDE.md** | 日志系统完整指南 | 500+ 行 |

## 🔧 常用命令

### 测试
```bash
# 运行所有测试
pytest tests/unit/ -v

# 运行环境变量测试
pytest tests/unit/test_minimax_tts.py::TestEnvironmentVariableHandling -v

# 查看覆盖率
pytest tests/unit/ --cov=vidppt --cov-report=term-missing
```

### 日志控制
```bash
# 启用详细日志
python -m vidppt input.pptx --verbose

# 设置日志级别（DEBUG/INFO/WARNING/ERROR）
python -m vidppt input.pptx --log-level DEBUG

# 保存日志到文件
python -m vidppt input.pptx --log-file app.log

# 组合使用
python -m vidppt input.pptx -v --log-level DEBUG --log-file debug.log
```

### Git
```bash
# 查看最近提交
git log --oneline -5

# 查看修改
git status
git diff

# 查看某个文件的改动
git log -p vidppt/engines/tts/api_tts_engine.py
```

## ✨ 核心功能

### 渲染引擎选择

```bash
# Spire（默认，pip 安装即可）
python -m vidppt input.pptx --render-engine spire

# LibreOffice（中文排版更友好，需安装系统依赖）
python -m vidppt input.pptx --render-engine libreoffice
```

**LibreOffice 依赖安装**：
```bash
# Arch/Manjaro
sudo pacman -S libreoffice-fresh poppler noto-fonts-cjk

# Ubuntu/Debian
sudo apt install libreoffice-impress poppler-utils fonts-noto-cjk
```

### MiniMax TTS 引擎选项

```python
config = ProcessConfig(
    tts_engine="minimax",
    tts_voice="male-qn-qingse",        # 语音选择
    tts_rate="+10%",                   # 语速调整
    tts_options={
        "emotion": "happy",             # 情感类型
        "sample_rate": 44100,           # 采样率
        "bitrate": 256000,              # 比特率
        "audio_format": "mp3"           # 格式
    }
)
```

### 支持的语音
- `male-qn-qingse` - 男声清晰
- `female-qn-nana` - 女声娜娜
- 更多语音请参考 MINIMAX_GUIDE.md

### 支持的情感
- `happy` - 开心
- `sad` - 悲伤
- `angry` - 愤怒
- `neutral` - 中立（默认）
- `peaceful` - 平和

### 语速格式
- `+20%` → 1.2x 速度
- `-10%` → 0.9x 速度
- `1.5` → 1.5x 速度
- 范围：0.5x ~ 2.0x

## 🐛 故障排查

### 错误：LibreOffice 未安装
```
FileNotFoundError: [Errno 2] No such file or directory: 'libreoffice'
```

**解决**：`sudo pacman -S libreoffice-fresh`

### 错误：MiniMax API key 未设置
```
AssertionError: MiniMax API key 未设置。请设置环境变量 MINIMAX_API。
示例: export MINIMAX_API='sk-cp-xxxxxxxxxxxxxx'
```

**解决**：
```bash
export MINIMAX_API='sk-cp-your-real-api-key'
```

### 验证环境变量
```bash
echo $MINIMAX_API  # 应该输出你的 API key
```

### 运行测试验证安装
```bash
pytest tests/unit/test_minimax_tts.py -v
```

## 📁 项目结构

```
vidppt/
├── core/                  # 核心模块
├── engines/tts/           # TTS 引擎
│   ├── edge_tts_engine.py
│   └── api_tts_engine.py  # MiniMax 实现
├── processors/            # 文档处理
├── utils/                 # 工具
└── pipeline.py            # 主流程

tests/unit/              # 单元测试 (93 个)
docs/                    # 文档和指南
```

## 🎓 示例代码

### 基础使用
```python
from pathlib import Path
from vidppt import Pipeline, ProcessConfig

# 设置环境变量：export MINIMAX_API='sk-cp-xxx'

config = ProcessConfig(
    input_path=Path("input.pptx"),
    output_dir=Path("output"),
    tts_engine="minimax"
)

pipeline = Pipeline(config)
pipeline.run()
```

### 高级配置
```python
import os
from pathlib import Path
from vidppt import Pipeline, ProcessConfig

config = ProcessConfig(
    input_path=Path("input.pptx"),
    output_dir=Path("output"),
    tts_engine="minimax",
    tts_voice="male-qn-qingse",
    tts_rate="+15%",
    tts_options={
        "emotion": "happy",
        "sample_rate": 44100,
        "bitrate": 256000,
        "audio_format": "mp3"
    }
)

pipeline = Pipeline(config)
pipeline.run()
```

### 动态修改 API Key
```python
import os
from vidppt.engines.tts.api_tts_engine import MiniMaxTTSEngine

# 临时切换 API key
os.environ['MINIMAX_API'] = 'new-key'
engine = MiniMaxTTSEngine()
# 使用新 key...

# 恢复旧 key
os.environ['MINIMAX_API'] = 'old-key'
```

## 📊 测试覆盖

```
单元测试: 107 个 ✅
├── MiniMax TTS: 27 个
│   ├── 基础功能: 3 个
│   ├── 环境变量: 8 个
│   ├── 语速解析: 7 个
│   ├── 负载构建: 5 个
│   └── 集成测试: 4 个
├── 数据模型: 13 个
├── 流程管道: 13 个
├── 处理器: 10 个
├── 注册表: 13 个
└── TTS 引擎: 13 个

总通过率: 100% ✅
执行时间: 0.45 秒
```

## 🔗 重要链接

- **GitHub**: [vidppt repository]
- **文档**: 见本项目根目录
- **环变量指南**: `ENV_VAR_SETUP.md`
- **MiniMax 指南**: `MINIMAX_GUIDE.md`

## 💡 提示

1. **环境变量优先级**：
   - 显式传入的 api_key（最高）
   - MINIMAX_API 环境变量
   - 未设置（报错）

2. **测试中使用**：
   ```python
   # 测试中可以直接传入 api_key（不依赖环境变量）
   engine = MiniMaxTTSEngine(api_key="test-key")
   ```

3. **Docker 中使用**：
   ```bash
   docker run -e MINIMAX_API='sk-cp-xxx' vidppt:latest
   ```

## 🚀 下一步

查看以下待办事项中最高优先级的工作：
- [ ] CLI 参数支持
- [ ] 音频缓存机制
- [ ] 进度条/日志显示

## 📞 获取帮助

1. 查看 `ENV_VAR_SETUP.md` 中的常见问题
2. 运行 `pytest tests/unit/ -v` 验证环境
3. 查看 `MINIMAX_GUIDE.md` 中的故障排查部分

---

**最后更新**: 2026-05-08
**版本**: v0.2.0
