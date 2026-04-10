# VidPPT 日志系统使用指南

## 📋 目录

1. [概述](#概述)
2. [日志级别](#日志级别)
3. [CLI 使用](#cli-使用)
4. [代码中使用](#代码中使用)
5. [日志配置](#日志配置)
6. [常见用例](#常见用例)

---

## 概述

VidPPT 集成了完整的 Python `logging` 模块，用于替代 `print()` 语句。所有日志输出都已标准化，支持：

- ✅ 多个日志级别（DEBUG、INFO、WARNING、ERROR、CRITICAL）
- ✅ 控制台彩色输出
- ✅ 日志文件输出
- ✅ 模块化日志记录
- ✅ 灵活的日志配置

---

## 日志级别

日志系统使用以下5个级别，从低到高排序：

| 级别 | 值 | 用途 | 示例 |
|------|-----|------|------|
| **DEBUG** | 10 | 详细诊断信息 | `正在处理第 1 页`、`缓存命中` |
| **INFO** | 20 | 一般信息，重要进度 | `开始文字转语音`、`处理完成` |
| **WARNING** | 30 | 警告信息，可能问题 | `页面缺少图像`、`音频转换可能失败` |
| **ERROR** | 40 | 错误信息，功能失效 | `文件不存在`、`API 请求失败` |
| **CRITICAL** | 50 | 严重错误，程序可能崩溃 | `内存不足`、`磁盘满` |

---

## CLI 使用

### 基本命令

```bash
# 默认使用 INFO 级别
python -m vidppt input.pptx

# 启用详细模式（输出所有日志）
python -m vidppt input.pptx --verbose
python -m vidppt input.pptx -v
```

### 日志级别控制

```bash
# 设置日志级别为 DEBUG（最详细）
python -m vidppt input.pptx --log-level DEBUG

# 设置日志级别为 INFO（默认）
python -m vidppt input.pptx --log-level INFO

# 设置日志级别为 WARNING（仅警告和错误）
python -m vidppt input.pptx --log-level WARNING

# 设置日志级别为 ERROR（仅错误）
python -m vidppt input.pptx --log-level ERROR

# 设置日志级别为 CRITICAL（仅严重错误）
python -m vidppt input.pptx --log-level CRITICAL
```

### 日志文件输出

```bash
# 将日志输出到文件
python -m vidppt input.pptx --log-file output.log

# 同时输出到控制台和文件
python -m vidppt input.pptx --log-file app.log -v
```

### 组合使用

```bash
# 最完整的配置
python -m vidppt input.pptx \
  --tts-engine minimax \
  --log-level DEBUG \
  --log-file debug.log \
  -v

# 简化版
python -m vidppt input.pptx -v --log-file app.log
```

---

## 代码中使用

### 基本使用

在任何模块中导入 logger：

```python
import logging

logger = logging.getLogger(__name__)

# 输出日志
logger.debug("这是调试信息")
logger.info("这是一般信息")
logger.warning("这是警告信息")
logger.error("这是错误信息")
logger.critical("这是严重错误信息")
```

### 模块化日志

为每个模块创建独立的 logger：

```python
# vidppt/pipeline.py
import logging

logger = logging.getLogger(__name__)  # 会得到名称 'vidppt.pipeline'

class Pipeline:
    def run(self):
        logger.info(f"开始处理: {self.config.input_path}")
        # ... 处理逻辑
```

### 日志消息格式

```python
# ✅ 推荐格式
logger.info(f"处理文件: {file_path}")
logger.debug(f"第 {page_num} 页的处理结果: {result}")
logger.error(f"API 返回错误: {response.status_code}")

# ❌ 避免的格式
logger.info(f"第 {page_num} 页\n处理完成")  # 不要用 \n
logger.info("[处理] 开始...")  # 不要用 [前缀]，日志系统已处理格式
```

### 异常日志

```python
import logging

logger = logging.getLogger(__name__)

try:
    # 处理逻辑
    result = process_file(file_path)
except FileNotFoundError as e:
    # 方式 1: 记录异常和消息
    logger.error(f"文件不存在: {file_path}", exc_info=True)
    
    # 方式 2: 仅记录消息（不显示堆栈）
    logger.error(f"文件不存在: {file_path}")
    
    # 方式 3: 使用异常日志方法
    logger.exception(f"处理文件时出错: {file_path}")
```

---

## 日志配置

### 日志配置模块

日志系统通过 `vidppt/utils/logger.py` 进行配置：

```python
from vidppt.utils.logger import setup_logger, get_logger

# 方式 1: 使用 setup_logger 初始化
setup_logger(
    name="vidppt",
    level=logging.INFO,
    verbose=False,
    log_file=None
)

# 方式 2: 在已初始化后获取 logger
logger = get_logger("vidppt.pipeline")
```

### logger.py 源码

```python
# vidppt/utils/logger.py

def setup_logger(name, level, verbose=False, log_file=None):
    """
    设置日志系统
    
    参数:
        name: logger 名称
        level: 日志级别 (logging.DEBUG 等)
        verbose: 是否启用详细模式
        log_file: 日志文件路径 (可选)
    """
    # 实现细节...
```

### 环境变量配置

```bash
# 通过环境变量设置日志级别
export VIDPPT_LOG_LEVEL=DEBUG

# 通过环境变量设置日志文件
export VIDPPT_LOG_FILE=/tmp/vidppt.log
```

---

## 常见用例

### 用例 1: 开发阶段调试

```bash
# 启用最详细的日志，用于调试
python -m vidppt input.pptx --log-level DEBUG --log-file debug.log -v

# 查看日志
tail -f debug.log
```

### 用例 2: 生产环境运行

```bash
# 仅记录重要信息和错误
python -m vidppt input.pptx --log-level WARNING --log-file app.log

# 定期检查日志
cat app.log | grep ERROR
```

### 用例 3: 特定功能调试

```bash
# 记录所有日志到文件，便于事后分析
python -m vidppt input.pptx --log-level DEBUG --log-file full_trace.log

# 筛选特定模块的日志
grep "pipeline" full_trace.log
grep "tts" full_trace.log
```

### 用例 4: Python 脚本中使用

```python
from pathlib import Path
from vidppt import Pipeline, ProcessConfig
from vidppt.utils.logger import setup_logger
import logging

# 初始化日志
setup_logger(
    name="vidppt",
    level=logging.DEBUG,
    verbose=True,
    log_file="my_app.log"
)

# 创建和运行 pipeline
config = ProcessConfig(
    input_path=Path("presentation.pptx"),
    output_dir=Path("output"),
    tts_engine="minimax"
)

Pipeline(config).run()
```

### 用例 5: 自定义日志处理器

```python
import logging
from vidppt.utils.logger import get_logger

# 获取 logger
logger = get_logger("vidppt")

# 添加自定义处理器
file_handler = logging.FileHandler("custom.log")
file_handler.setLevel(logging.WARNING)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
```

---

## 日志输出示例

### DEBUG 模式输出

```
[DEBUG   ] vidppt.pipeline - 初始化 Pipeline
[DEBUG   ] vidppt.pipeline - 使用处理器: PPTProcessor
[DEBUG   ] vidppt.processors.ppt_processor - 处理第 1 页
[DEBUG   ] vidppt.processors.ppt_processor - 提取文本: "标题文本"
[INFO    ] vidppt.pipeline - 开始文字转语音
[DEBUG   ] vidppt.engines.tts - 调用 MiniMax API...
[INFO    ] vidppt.pipeline - 音频生成完成
[DEBUG   ] vidppt.utils.video_composer - 第 1 页 片段时长: 5.2s
[INFO    ] vidppt.utils.video_composer - 合并 1 个片段，输出 -> output/video.mp4
[INFO    ] vidppt.utils.video_composer - 视频生成完成：output/video.mp4  (25.3 MB)
```

### 错误处理输出

```
[ERROR   ] vidppt.pipeline - 文件不存在: /path/to/file.pptx
[ERROR   ] vidppt.pipeline - 不支持的文件类型: .xyz。支持的类型: .ppt, .pptx, .pdf
[WARNING ] vidppt.utils.video_composer - 跳过第 2 页：缺少页面图像
[ERROR   ] vidppt.engines.tts - MiniMax API 请求失败: Connection timeout
```

---

## 最佳实践

### ✅ 应该做

1. **使用适当的日志级别**
   - DEBUG: 详细的诊断信息
   - INFO: 重要的进度信息
   - WARNING: 可能的问题
   - ERROR: 实际的错误

2. **包含有用的上下文**
   ```python
   # ✅ 好的例子
   logger.info(f"处理文件: {file_path}, 大小: {file_size}MB")
   
   # ❌ 差的例子
   logger.info("处理文件")
   ```

3. **在适当的地方记录**
   ```python
   # ✅ 在操作开始前记录
   logger.info("开始转换文件...")
   result = convert_file()
   logger.info("文件转换完成")
   ```

### ❌ 不应该做

1. **不要滥用 print()**
   ```python
   # ❌ 避免
   print("Processing file")
   
   # ✅ 使用
   logger.info("处理文件")
   ```

2. **不要记录敏感信息**
   ```python
   # ❌ 避免记录 API 密钥
   logger.info(f"API Key: {api_key}")
   
   # ✅ 只记录必要信息
   logger.info("API 认证成功")
   ```

3. **不要过度记录**
   ```python
   # ❌ 避免在循环中记录每一项
   for item in items:
       logger.info(f"处理 {item}")  # 过多的日志
   
   # ✅ 记录摘要信息
   logger.info(f"处理 {len(items)} 个项目")
   ```

---

## 故障排除

### 问题: 看不到日志输出

**原因**: 日志级别设置太高

**解决方案**:
```bash
# 降低日志级别
python -m vidppt input.pptx --log-level DEBUG
```

### 问题: 日志输出太多

**原因**: 日志级别设置太低

**解决方案**:
```bash
# 提高日志级别
python -m vidppt input.pptx --log-level WARNING

# 或只查看特定类型的日志
grep ERROR app.log
```

### 问题: 日志没有保存到文件

**原因**: 目录不存在或没有写权限

**解决方案**:
```bash
# 确保目录存在
mkdir -p logs

# 使用绝对路径
python -m vidppt input.pptx --log-file /tmp/vidppt.log

# 检查权限
ls -la logs/
```

---

## 相关文件

- **日志配置**: `vidppt/utils/logger.py` (110 行)
- **CLI 配置**: `vidppt/cli.py` (使用日志参数)
- **使用示例**: 所有 `vidppt/*.py` 文件

---

## 总结

| 任务 | 命令 |
|------|------|
| 启用详细日志 | `python -m vidppt input.pptx -v` |
| 设置日志级别 | `python -m vidppt input.pptx --log-level DEBUG` |
| 保存到文件 | `python -m vidppt input.pptx --log-file app.log` |
| 完整配置 | `python -m vidppt input.pptx -v --log-level DEBUG --log-file app.log` |

---

**最后更新**: 2026-04-10  
**版本**: VidPPT v0.3.0  
**测试**: 107 个单元测试全部通过 ✅
