# MiniMax API 环境变量设置指南

## 快速开始

### 第一步：设置环境变量

```bash
export MINIMAX_API='sk-cp-your-api-key-here'
```

### 第二步：使用 MiniMax 引擎

```python
from pathlib import Path
from vidppt import Pipeline, ProcessConfig

# 环境变量会自动读取，无需显式传入 api_key
config = ProcessConfig(
    input_path=Path("presentation.pptx"),
    output_dir=Path("output"),
    tts_engine="minimax"
)

pipeline = Pipeline(config)
pipeline.run()
```

## 详细说明

### 环境变量处理流程

```
MiniMaxTTSEngine(api_key=?)
    ├─ 如果 api_key 明确传入 (非 None)
    │  ├─ 如果为空字符串 "" ❌ → AssertionError
    │  └─ 否则使用该值 ✓
    │
    └─ 如果 api_key=None
       ├─ 从 MINIMAX_API 环境变量读取
       ├─ 如果环境变量存在且非空 ✓ → 使用
       └─ 否则 ❌ → AssertionError
```

### 错误情况及解决方案

#### 情况 1：未设置环境变量

```
AssertionError: MiniMax API key 未设置。请设置环境变量 MINIMAX_API。
示例: export MINIMAX_API='sk-cp-xxxxxxxxxxxxxx'
```

**解决方案：**
```bash
export MINIMAX_API='sk-cp-your-real-api-key'
```

#### 情况 2：环境变量为空

```bash
export MINIMAX_API=''  # ❌ 错误
```

**解决方案：**
```bash
export MINIMAX_API='sk-cp-your-real-api-key'  # ✓ 正确
```

#### 情况 3：显式传入空字符串

```python
# ❌ 错误
engine = MiniMaxTTSEngine(api_key="")
# AssertionError: MiniMax API key 不能为空字符串
```

**解决方案：**
```python
# ✓ 正确 - 使用环境变量
engine = MiniMaxTTSEngine()

# ✓ 也正确 - 显式传入有效的 key
engine = MiniMaxTTSEngine(api_key="sk-cp-your-real-api-key")
```

## 使用场景

### 场景 1：开发环境（推荐）

设置环境变量一次，所有脚本都可以使用：

```bash
# ~/.bashrc 或 ~/.zshrc
export MINIMAX_API='sk-cp-your-api-key'
```

```python
# 代码中无需关心 api_key
config = ProcessConfig(
    input_path=Path("presentation.pptx"),
    output_dir=Path("output"),
    tts_engine="minimax"
)
```

### 场景 2：配置文件方式

通过配置文件传入其他参数，api_key 仍从环境变量读取：

```python
config = ProcessConfig(
    input_path=Path("presentation.pptx"),
    output_dir=Path("output"),
    tts_engine="minimax",
    tts_voice="male-qn-qingse",
    tts_rate="+10%",
    tts_options={
        "emotion": "happy",
        "sample_rate": 44100,
        # api_key 不需要在这里，会自动从 MINIMAX_API 读取
    }
)
```

### 场景 3：单元测试

测试中可以显式传入 api_key（优先级更高）：

```python
# 测试中可以直接传入，不依赖环境变量
engine = MiniMaxTTSEngine(api_key="test-key-123")
```

## 安全建议

### ✓ 推荐做法

1. **使用环境变量存储 API key**
   ```bash
   export MINIMAX_API='sk-cp-xxxxx'
   ```

2. **在 .gitignore 中排除包含 key 的文件**
   ```
   # .gitignore
   .env
   config.local.json
   ```

3. **在 CI/CD 中使用 Secret**
   ```yaml
   # GitHub Actions
   env:
     MINIMAX_API: ${{ secrets.MINIMAX_API }}
   ```

### ✗ 避免做法

1. **不要在代码中硬编码 API key**
   ```python
   # ❌ 错误
   engine = MiniMaxTTSEngine(api_key="sk-cp-xxxxx")
   ```

2. **不要提交包含 API key 的文件**
   ```bash
   # ❌ 错误
   git add config.json  # 如果包含 api_key
   ```

3. **不要在日志中打印 API key**
   ```python
   # ❌ 错误
   print(f"Using API key: {api_key}")
   ```

## Docker 环境

### Dockerfile

```dockerfile
FROM python:3.12

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

# 从构建参数或环境变量读取
ARG MINIMAX_API
ENV MINIMAX_API=${MINIMAX_API}

ENTRYPOINT ["python", "-m", "vidppt"]
```

### docker-compose.yml

```yaml
services:
  vidppt:
    build: .
    environment:
      - MINIMAX_API=${MINIMAX_API}
    volumes:
      - ./input:/app/input
      - ./output:/app/output
```

### 运行

```bash
# 方式 1：通过 .env 文件
docker-compose --env-file .env up

# 方式 2：直接传递
docker run -e MINIMAX_API='sk-cp-xxxxx' vidppt:latest
```

## 常见问题

### Q: 如何检查环境变量是否正确设置？

```bash
echo $MINIMAX_API
```

输出应该是你的 API key：
```
sk-cp-xxxxxxxxxxxxx
```

### Q: 支持多个 API key 吗？

不支持。当前只支持单个 MINIMAX_API 环境变量。

如果需要支持多个 key，可以：
1. 通过不同的脚本/容器使用不同的 MINIMAX_API
2. 在配置文件中显式指定（未来功能）

### Q: 可以动态修改 API key 吗？

可以，在创建 Pipeline 之前修改：

```python
import os

os.environ['MINIMAX_API'] = 'new-key'

config = ProcessConfig(...)
pipeline = Pipeline(config)
```

### Q: 显式传入的 api_key 会覆盖环境变量吗？

是的。优先级顺序：
1. 显式传入的 api_key（最高）
2. MINIMAX_API 环境变量
3. 未设置（报错）

## 环境变量持久化

### Linux/Mac (.bashrc 或 .zshrc)

```bash
# 添加到文件末尾
echo "export MINIMAX_API='sk-cp-xxxxx'" >> ~/.bashrc
source ~/.bashrc  # 重新加载
```

### Windows (CMD)

```cmd
setx MINIMAX_API "sk-cp-xxxxx"
```

然后重启 CMD 或 IDE。

### Windows (PowerShell)

```powershell
[Environment]::SetEnvironmentVariable("MINIMAX_API", "sk-cp-xxxxx", "User")
```

### .env 文件方式（Python-dotenv）

```python
# 需要安装: pip install python-dotenv

from dotenv import load_dotenv
import os

load_dotenv()  # 从 .env 文件加载
api_key = os.getenv('MINIMAX_API')
```

创建 `.env` 文件：
```
MINIMAX_API=sk-cp-xxxxx
```

## 测试环境变量功能

```python
import os
from vidppt.engines.tts.api_tts_engine import MiniMaxTTSEngine

# 测试 1：从环境变量读取
os.environ['MINIMAX_API'] = 'test-key-123'
engine = MiniMaxTTSEngine()
print(engine.api_key)  # 输出: test-key-123

# 测试 2：显式传入覆盖环境变量
engine = MiniMaxTTSEngine(api_key='explicit-key')
print(engine.api_key)  # 输出: explicit-key

# 测试 3：缺少环境变量会报错
del os.environ['MINIMAX_API']
try:
    engine = MiniMaxTTSEngine()  # ❌ AssertionError
except AssertionError as e:
    print(f"错误: {e}")
```

## 更多信息

- 参考：`MINIMAX_GUIDE.md` - 完整 MiniMax 使用指南
- 参考：`QUICKSTART_MINIMAX.md` - 快速开始示例
