# 🚀 VidPPT v0.2.0 - 从这里开始

欢迎使用 VidPPT！这是一个将文档（PPT/PDF/Word）转换为配音视频的可扩展工具。

## 📚 文档导航

### 快速上手
1. **[README_NEW.md](README_NEW.md)** - 开始使用（必读）
   - 安装步骤
   - 基本使用
   - 功能特性

### 深入了解
2. **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - 项目总览
   - 项目目标
   - 核心特性
   - 使用示例

3. **[ARCHITECTURE.md](ARCHITECTURE.md)** - 架构设计
   - 设计模式
   - 扩展指南
   - 最佳实践

4. **[EXAMPLES.md](EXAMPLES.md)** - 代码示例
   - 基本用法
   - 高级用法
   - 扩展开发

### 迁移和参考
5. **[MIGRATION.md](MIGRATION.md)** - 迁移指南
   - 版本对比
   - 迁移步骤
   - 常见问题

6. **[TEST_REPORT.md](TEST_REPORT.md)** - 测试报告
   - 测试结果
   - 性能数据
   - Bug 修复

7. **[REFACTOR_SUMMARY.md](REFACTOR_SUMMARY.md)** - 重构总结
   - 技术细节
   - 设计决策
   - 未来计划

8. **[FILES_CREATED.md](FILES_CREATED.md)** - 文件清单
   - 目录结构
   - 代码统计
   - 文件说明

## ⚡ 快速开始（5分钟）

### 1. 安装依赖
```bash
uv sync
```

### 2. 查看帮助
```bash
uv run vidppt --help
```

### 3. 转换第一个文件
```bash
# 基本使用（保存所有中间文件）
uv run vidppt your_file.pptx

# 仅生成最终视频
uv run vidppt your_file.pptx --no-intermediate
```

### 4. 高级选项
```bash
# 使用男声，加速20%
uv run vidppt your_file.pptx \
  --voice zh-CN-YunyangNeural \
  --rate +20%

# 跳过视频合成（仅提取和生成音频）
uv run vidppt your_file.pptx --no-video
```

## 🎯 主要特性

### ✅ 已实现
- 多文档格式支持（PPT 完整实现）
- 插件式处理器架构
- 多种 TTS 引擎支持
- 灵活的配置系统
- 中间文件开关
- 完整的类型提示

### 🚧 框架已搭建（待实现）
- PDF 处理器
- Word 处理器
- 更多 TTS 引擎
- OCR 引擎
- API 集成

## 📖 推荐阅读顺序

### 新用户（只想使用）
1. README_NEW.md - 快速开始
2. 直接运行命令开始使用

### 开发者（想要扩展）
1. README_NEW.md - 了解基本用法
2. ARCHITECTURE.md - 理解架构设计
3. EXAMPLES.md - 学习如何扩展
4. 开始编写自己的处理器

### 贡献者（想要改进）
1. PROJECT_SUMMARY.md - 了解项目全貌
2. ARCHITECTURE.md - 理解设计决策
3. TEST_REPORT.md - 了解测试覆盖
4. REFACTOR_SUMMARY.md - 了解技术细节

## 🔧 常用命令

```bash
# 查看帮助
vidppt --help

# 完整流程
vidppt input.pptx

# 指定输出目录
vidppt input.pptx -o my_output

# 不保存中间文件
vidppt input.pptx --no-intermediate

# 跳过某些步骤
vidppt input.pptx --no-tts      # 跳过语音
vidppt input.pptx --no-video    # 跳过视频

# 调整语音
vidppt input.pptx --voice zh-CN-YunyangNeural  # 男声
vidppt input.pptx --rate +20%                   # 加速
```

## 🆘 获取帮助

1. **命令行帮助**: `vidppt --help`
2. **查看文档**: 浏览上面的文档链接
3. **提交 Issue**: 遇到问题时提交 Issue
4. **查看示例**: EXAMPLES.md 中有丰富的示例

## 💡 快速示例

### Python API 使用
```python
from vidppt import Pipeline, ProcessConfig
from pathlib import Path

config = ProcessConfig(
    input_path=Path("input.pptx"),
    output_dir=Path("outputs"),
    save_intermediate=False,  # 不保存中间文件
)

pipeline = Pipeline(config)
pipeline.run()
```

### 添加新处理器
```python
from vidppt import DocumentProcessor, register_processor

@register_processor
class MyProcessor(DocumentProcessor):
    @classmethod
    def supported_extensions(cls):
        return ['.ext']
    
    def extract_content(self, config):
        # 你的实现
        pass
    
    def render_pages(self, config):
        # 你的实现
        pass
```

## 🎉 现在开始

选择一个入口：

1. **我只想用** → 直接运行 `vidppt your_file.pptx`
2. **我想了解** → 阅读 [README_NEW.md](README_NEW.md)
3. **我想扩展** → 阅读 [ARCHITECTURE.md](ARCHITECTURE.md) + [EXAMPLES.md](EXAMPLES.md)
4. **我想贡献** → 阅读所有文档，了解项目全貌

祝你使用愉快！🚀

---

**项目版本**: v0.2.0  
**最后更新**: 2026-04-08  
**状态**: ✅ 生产就绪
