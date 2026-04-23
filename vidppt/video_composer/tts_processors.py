"""
TTS 文本预处理策略模块

支持多种文本处理策略：
- 显式停顿：使用 | 分隔符
- 拼音标注：使用 [拼音] 语法
- SSML 标记：直接使用 SSML 标签
- Jieba 分词：智能分词插入停顿
"""

from abc import ABC, abstractmethod
from typing import List
import re


class TextProcessor(ABC):
    """文本预处理策略基类"""

    name: str = "base"
    description: str = "基础处理器"

    @abstractmethod
    def process(self, text: str) -> str:
        """
        处理文本

        Args:
            text: 原始文本

        Returns:
            处理后的文本
        """
        pass


class ExplicitPauseProcessor(TextProcessor):
    """
    显式停顿策略

    将 | 符号转换为 SSML break 标签

    示例：
        输入：武汉市|长江二桥
        输出：武汉市<break time="200ms"/>长江二桥
    """

    name = "explicit_pause"
    description = "显式停顿：使用 | 分隔符插入停顿"

    def __init__(self, pause_duration: str = "200ms"):
        self.pause_duration = pause_duration

    def process(self, text: str) -> str:
        return text.replace("|", f'<break time="{self.pause_duration}"/>')


class PinyinAnnotationProcessor(TextProcessor):
    """
    拼音标注策略

    将 [拼音] 语法转换为 SSML phoneme 标签

    示例：
        输入：市[shi4]
        输出：<phoneme ph="shi4">市</phoneme>
    """

    name = "pinyin_annotation"
    description = "拼音标注：使用 [拼音] 指定读音"

    def process(self, text: str) -> str:
        return re.sub(
            r'(\S+?)\[(\S+?)\]',
            r'<phoneme ph="\2">\1</phoneme>',
            text
        )


class SSMLProcessor(TextProcessor):
    """
    SSML 标记策略

    原样保留 SSML 标签，用于高级控制

    支持的标签：
    - <break time="500ms"/>
    - <phoneme ph="xxx">字</phoneme>
    - <prosody rate="slow">慢速</prosody>
    - <emphasis>强调</emphasis>
    """

    name = "ssml"
    description = "SSML 标记：直接使用 SSML 标签"

    def process(self, text: str) -> str:
        # SSML 标签原样保留
        return text


class JiebaSegmentProcessor(TextProcessor):
    """
    Jieba 智能分词策略

    使用 jieba 分词后在词之间插入停顿

    示例：
        输入：武汉市长江二桥
        输出：武汉市|长江二桥 → 武汉市<break time="200ms"/>长江二桥
    """

    name = "jieba_segment"
    description = "Jieba 分词：智能分词并插入停顿"

    def __init__(self, pause_duration: str = "200ms"):
        self.pause_duration = pause_duration

    def process(self, text: str) -> str:
        try:
            import jieba
            words = jieba.cut(text)
            pause = f'<break time="{self.pause_duration}"/>'
            return pause.join(words)
        except ImportError:
            print("警告: 未安装 jieba，跳过智能分词")
            return text


class CompositeProcessor(TextProcessor):
    """
    组合处理器

    将多个处理器按顺序组合执行
    """

    name = "composite"
    description = "组合处理器：按顺序执行多个策略"

    def __init__(self, processors: List[TextProcessor] = None):
        self.processors = processors or []

    def add_processor(self, processor: TextProcessor) -> "CompositeProcessor":
        """添加处理器"""
        self.processors.append(processor)
        return self

    def process(self, text: str) -> str:
        result = text
        for processor in self.processors:
            result = processor.process(result)
        return result


class ProcessorFactory:
    """
    处理器工厂

    用于创建和获取处理器实例
    """

    _registry: dict = {}

    @classmethod
    def register(cls, processor_class: type) -> None:
        """注册处理器"""
        instance = processor_class()
        cls._registry[instance.name] = processor_class

    @classmethod
    def get(cls, name: str, **kwargs) -> TextProcessor:
        """获取处理器实例"""
        if name not in cls._registry:
            available = list(cls._registry.keys())
            raise KeyError(f"处理器 '{name}' 未注册，可用: {available}")
        return cls._registry[name](**kwargs)

    @classmethod
    def list_all(cls) -> dict:
        """列出所有处理器"""
        return {
            name: cls._registry[name]().description
            for name in cls._registry
        }


# 自动注册内置处理器
ProcessorFactory.register(ExplicitPauseProcessor)
ProcessorFactory.register(PinyinAnnotationProcessor)
ProcessorFactory.register(SSMLProcessor)
ProcessorFactory.register(JiebaSegmentProcessor)
ProcessorFactory.register(CompositeProcessor)
