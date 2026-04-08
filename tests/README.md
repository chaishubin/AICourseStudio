# VidPPT 测试指南

本项目包含全面的单元测试套件，用于测试 VidPPT 的各个模块。

## 测试结构

```
tests/
├── __init__.py
├── conftest.py              # 共享的 fixtures 和配置
├── unit/                    # 单元测试
│   ├── test_models.py       # 核心数据模型测试
│   ├── test_registry.py     # 注册系统测试
│   ├── test_tts_engines.py  # TTS 引擎测试
│   ├── test_processors.py   # 文档处理器测试
│   └── test_pipeline.py     # Pipeline 流程测试
└── integration/             # 集成测试
    └── __init__.py
```

## 安装测试依赖

```bash
# 使用 uv（推荐）
uv pip install -e ".[dev]"

# 或使用 pip
pip install -e ".[dev]"
```

这将安装：
- pytest >= 7.0.0
- pytest-asyncio >= 0.21.0  
- pytest-cov >= 4.0.0
- black >= 23.0.0

## 运行测试

### 运行所有测试

```bash
pytest
```

### 运行特定测试文件

```bash
pytest tests/unit/test_models.py
```

### 运行特定测试类

```bash
pytest tests/unit/test_models.py::TestPageContent
```

### 运行特定测试函数

```bash
pytest tests/unit/test_models.py::TestPageContent::test_create_minimal_page
```

### 查看详细输出

```bash
pytest -v
```

### 运行并生成覆盖率报告

```bash
# 生成终端报告
pytest --cov=vidppt --cov-report=term

# 生成 HTML 报告
pytest --cov=vidppt --cov-report=html

# 查看 HTML 报告
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### 运行特定类型的测试

```bash
# 只运行单元测试
pytest tests/unit/

# 只运行集成测试
pytest tests/integration/
```

### 运行失败测试的调试

```bash
# 在第一个失败时停止
pytest -x

# 显示本地变量
pytest -l

# 进入 pdb 调试器
pytest --pdb
```

## 测试覆盖范围

### 1. 核心模型测试 (test_models.py)

测试 `vidppt/core/models.py` 中的数据模型：

- **PageContent**: 单页内容的创建、修改和访问
- **DocumentContent**: 文档内容和 total_pages 属性
- **ProcessConfig**: 配置的创建、默认值和路径转换

**关键测试**:
- 最小化对象创建
- 完整对象创建
- 属性可变性
- 路径自动转换
- 默认值验证

### 2. 注册系统测试 (test_registry.py)

测试 `vidppt/core/registry.py` 中的处理器注册：

- **ProcessorRegistry**: 注册、查找、列表功能
- **register_processor**: 装饰器功能
- 扩展名规范化
- 处理器覆盖

**关键测试**:
- 单个和多个扩展名注册
- 文件类型查找（大小写不敏感）
- 不支持类型的处理
- 装饰器自动注册

### 3. TTS 引擎测试 (test_tts_engines.py)

测试 `vidppt/engines/tts/` 中的 TTS 引擎：

- **EdgeTTSEngine**: 异步转换、空文本处理
- **TTSEngine 接口**: 批量转换、分批处理
- 不同语音和语速设置
- 错误处理

**关键测试**:
- 异步文本转音频
- 空白文本的默认处理
- 批量转换和并发控制
- 异常处理

### 4. 文档处理器测试 (test_processors.py)

测试 `vidppt/processors/` 中的文档处理器：

- **DocumentProcessor 接口**: 抽象方法、模板方法
- **PPTProcessor**: 文本提取、图片提取
- 文本层级保留
- 组合形状处理

**关键测试**:
- 支持的扩展名
- 幻灯片文本提取（含缩进）
- 图片提取（含组合）
- 中间文件保存

### 5. Pipeline 测试 (test_pipeline.py)

测试 `vidppt/pipeline.py` 中的主流程：

- **Pipeline 初始化**: TTS 引擎创建
- **完整流程**: 文件检查、处理、TTS、视频
- **功能开关**: enable_tts、enable_video
- **错误处理**: 文件不存在、不支持的类型
- **临时文件清理**

**关键测试**:
- 文件存在性检查
- 处理器选择
- TTS 生成（含/不含中间文件）
- 视频合成
- 异常捕获和处理

## 测试 Fixtures

在 `conftest.py` 中定义的共享 fixtures：

- `temp_dir`: 临时目录（自动清理）
- `sample_text`: 示例文本
- `sample_config`: 示例配置
- `mock_page_content`: 模拟页面内容
- `mock_document_content`: 模拟文档内容

使用示例：

```python
def test_something(temp_dir, sample_config):
    # temp_dir 是一个 Path 对象
    # sample_config 是一个 ProcessConfig 对象
    pass
```

## 编写新测试

### 测试类组织

```python
class TestYourFeature:
    """测试 YourFeature 功能"""
    
    def test_basic_functionality(self):
        """测试基本功能"""
        # Arrange
        # Act
        # Assert
        pass
    
    def test_edge_case(self):
        """测试边界情况"""
        pass
    
    def test_error_handling(self):
        """测试错误处理"""
        with pytest.raises(Exception):
            # 触发错误的代码
            pass
```

### 使用 Mock

```python
from unittest.mock import Mock, patch

def test_with_mock():
    """使用 mock 对象测试"""
    mock_obj = Mock()
    mock_obj.method.return_value = "result"
    
    result = mock_obj.method()
    assert result == "result"
    mock_obj.method.assert_called_once()

def test_with_patch():
    """使用 patch 测试"""
    with patch('module.ClassName') as mock_class:
        mock_instance = Mock()
        mock_class.return_value = mock_instance
        
        # 测试代码
        pass
```

### 异步测试

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """测试异步函数"""
    result = await some_async_function()
    assert result == expected_value
```

## 持续集成

测试可以集成到 CI/CD 流程中：

```yaml
# .github/workflows/test.yml 示例
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - run: pip install -e ".[dev]"
      - run: pytest --cov=vidppt --cov-report=xml
      - uses: codecov/codecov-action@v2
```

## 最佳实践

1. **测试命名**: 使用描述性的测试名称
   - ✅ `test_extract_text_preserves_hierarchy`
   - ❌ `test_1`

2. **测试隔离**: 每个测试应该独立运行
   - 使用 `setup_method` 和 `teardown_method`
   - 清理测试数据

3. **测试覆盖**: 覆盖正常路径和异常路径
   - 正常情况
   - 边界情况
   - 错误情况

4. **Mock 使用**: 隔离外部依赖
   - 文件系统操作
   - 网络请求
   - 第三方库

5. **断言明确**: 使用具体的断言
   - ✅ `assert result == expected_value`
   - ❌ `assert result`

## 故障排查

### 测试失败

1. 查看详细输出: `pytest -v`
2. 查看本地变量: `pytest -l`
3. 进入调试器: `pytest --pdb`

### Import 错误

确保已安装项目：
```bash
pip install -e .
```

### Fixture 未找到

检查 `conftest.py` 是否在正确位置。

## 贡献指南

添加新功能时：

1. 先编写测试（TDD）
2. 确保所有测试通过
3. 保持测试覆盖率 > 80%
4. 更新此文档

## 测试统计

运行以下命令查看测试统计：

```bash
pytest --collect-only  # 查看测试数量
pytest --cov=vidppt --cov-report=term-missing  # 查看覆盖率
```

当前测试数量：40+ 个测试用例，覆盖核心功能的各个方面。
