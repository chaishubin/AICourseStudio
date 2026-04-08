"""
测试注册系统

测试覆盖：
- ProcessorRegistry 注册中心
- register_processor 装饰器
- 处理器查找和管理
"""

import pytest
from pathlib import Path
from vidppt.core.registry import ProcessorRegistry, register_processor
from vidppt.core.interfaces import DocumentProcessor
from vidppt.core.models import DocumentContent, ProcessConfig


class TestProcessorRegistry:
    """测试 ProcessorRegistry 注册中心"""

    def setup_method(self):
        """每个测试前清空注册表"""
        ProcessorRegistry._processors = {}

    def teardown_method(self):
        """每个测试后清空注册表"""
        ProcessorRegistry._processors = {}

    def test_register_processor_class(self):
        """测试注册处理器类"""

        class TestProcessor(DocumentProcessor):
            @classmethod
            def supported_extensions(cls):
                return [".test"]

            def extract_content(self, config):
                pass

            def render_pages(self, config):
                pass

        # 注册处理器
        ProcessorRegistry.register(TestProcessor)

        # 验证注册成功
        assert ".test" in ProcessorRegistry._processors
        assert ProcessorRegistry._processors[".test"] == TestProcessor

    def test_register_multiple_extensions(self):
        """测试注册支持多个扩展名的处理器"""

        class MultiExtProcessor(DocumentProcessor):
            @classmethod
            def supported_extensions(cls):
                return [".ppt", ".pptx", ".pps"]

            def extract_content(self, config):
                pass

            def render_pages(self, config):
                pass

        ProcessorRegistry.register(MultiExtProcessor)

        # 验证所有扩展名都已注册
        assert ".ppt" in ProcessorRegistry._processors
        assert ".pptx" in ProcessorRegistry._processors
        assert ".pps" in ProcessorRegistry._processors

        # 验证都指向同一个处理器
        assert ProcessorRegistry._processors[".ppt"] == MultiExtProcessor
        assert ProcessorRegistry._processors[".pptx"] == MultiExtProcessor

    def test_register_extension_normalization(self):
        """测试扩展名的规范化（小写、添加点）"""

        class TestProcessor(DocumentProcessor):
            @classmethod
            def supported_extensions(cls):
                # 提供不同格式的扩展名
                return ["txt", ".TXT", "DOC", ".doc"]

            def extract_content(self, config):
                pass

            def render_pages(self, config):
                pass

        ProcessorRegistry.register(TestProcessor)

        # 验证都被规范化为小写并带点
        assert ".txt" in ProcessorRegistry._processors
        assert ".doc" in ProcessorRegistry._processors

        # 不应该有大写或无点版本
        assert "txt" not in ProcessorRegistry._processors
        assert "TXT" not in ProcessorRegistry._processors

    def test_get_processor_by_file_path(self):
        """测试根据文件路径获取处理器"""

        class PDFProcessor(DocumentProcessor):
            @classmethod
            def supported_extensions(cls):
                return [".pdf"]

            def extract_content(self, config):
                pass

            def render_pages(self, config):
                pass

        ProcessorRegistry.register(PDFProcessor)

        # 测试获取处理器
        processor = ProcessorRegistry.get_processor(Path("test.pdf"))
        assert processor == PDFProcessor

        # 测试大小写不敏感
        processor = ProcessorRegistry.get_processor(Path("test.PDF"))
        assert processor == PDFProcessor

    def test_get_processor_returns_none_for_unsupported(self):
        """测试获取不支持的文件类型返回 None"""
        processor = ProcessorRegistry.get_processor(Path("test.xyz"))
        assert processor is None

    def test_list_supported_extensions(self):
        """测试列出所有支持的扩展名"""

        class Processor1(DocumentProcessor):
            @classmethod
            def supported_extensions(cls):
                return [".pdf"]

            def extract_content(self, config):
                pass

            def render_pages(self, config):
                pass

        class Processor2(DocumentProcessor):
            @classmethod
            def supported_extensions(cls):
                return [".pptx", ".docx"]

            def extract_content(self, config):
                pass

            def render_pages(self, config):
                pass

        ProcessorRegistry.register(Processor1)
        ProcessorRegistry.register(Processor2)

        extensions = ProcessorRegistry.list_supported_extensions()

        assert ".pdf" in extensions
        assert ".pptx" in extensions
        assert ".docx" in extensions
        assert len(extensions) == 3

    def test_is_supported(self):
        """测试检查文件是否被支持"""

        class TestProcessor(DocumentProcessor):
            @classmethod
            def supported_extensions(cls):
                return [".test"]

            def extract_content(self, config):
                pass

            def render_pages(self, config):
                pass

        ProcessorRegistry.register(TestProcessor)

        assert ProcessorRegistry.is_supported(Path("file.test")) is True
        assert ProcessorRegistry.is_supported(Path("file.TEST")) is True
        assert ProcessorRegistry.is_supported(Path("file.xyz")) is False

    def test_processor_override(self):
        """测试处理器覆盖（后注册的覆盖先注册的）"""

        class Processor1(DocumentProcessor):
            @classmethod
            def supported_extensions(cls):
                return [".test"]

            def extract_content(self, config):
                pass

            def render_pages(self, config):
                pass

        class Processor2(DocumentProcessor):
            @classmethod
            def supported_extensions(cls):
                return [".test"]

            def extract_content(self, config):
                pass

            def render_pages(self, config):
                pass

        ProcessorRegistry.register(Processor1)
        ProcessorRegistry.register(Processor2)

        # 后注册的应该覆盖先注册的
        processor = ProcessorRegistry.get_processor(Path("test.test"))
        assert processor == Processor2


class TestRegisterProcessorDecorator:
    """测试 register_processor 装饰器"""

    def setup_method(self):
        """每个测试前清空注册表"""
        ProcessorRegistry._processors = {}

    def teardown_method(self):
        """每个测试后清空注册表"""
        ProcessorRegistry._processors = {}

    def test_decorator_registers_processor(self):
        """测试装饰器自动注册处理器"""

        @register_processor
        class DecoratedProcessor(DocumentProcessor):
            @classmethod
            def supported_extensions(cls):
                return [".decorated"]

            def extract_content(self, config):
                pass

            def render_pages(self, config):
                pass

        # 验证自动注册
        assert ".decorated" in ProcessorRegistry._processors
        assert ProcessorRegistry._processors[".decorated"] == DecoratedProcessor

    def test_decorator_returns_class(self):
        """测试装饰器返回原始类"""

        @register_processor
        class TestProcessor(DocumentProcessor):
            @classmethod
            def supported_extensions(cls):
                return [".test"]

            def extract_content(self, config):
                return "test"

            def render_pages(self, config):
                pass

        # 装饰器应该返回原始类，可以正常实例化
        instance = TestProcessor()
        assert isinstance(instance, DocumentProcessor)

    def test_multiple_decorated_processors(self):
        """测试多个装饰的处理器"""

        @register_processor
        class Processor1(DocumentProcessor):
            @classmethod
            def supported_extensions(cls):
                return [".p1"]

            def extract_content(self, config):
                pass

            def render_pages(self, config):
                pass

        @register_processor
        class Processor2(DocumentProcessor):
            @classmethod
            def supported_extensions(cls):
                return [".p2"]

            def extract_content(self, config):
                pass

            def render_pages(self, config):
                pass

        # 验证都已注册
        assert ".p1" in ProcessorRegistry._processors
        assert ".p2" in ProcessorRegistry._processors
        assert ProcessorRegistry._processors[".p1"] == Processor1
        assert ProcessorRegistry._processors[".p2"] == Processor2


class TestRegistryIntegration:
    """测试注册系统的集成场景"""

    def setup_method(self):
        """每个测试前清空注册表"""
        ProcessorRegistry._processors = {}

    def teardown_method(self):
        """每个测试后清空注册表"""
        ProcessorRegistry._processors = {}

    def test_full_registration_workflow(self):
        """测试完整的注册工作流"""

        # 1. 使用装饰器注册处理器
        @register_processor
        class PPTProcessor(DocumentProcessor):
            @classmethod
            def supported_extensions(cls):
                return [".ppt", ".pptx"]

            def extract_content(self, config):
                return DocumentContent(pages=[])

            def render_pages(self, config):
                return []

        # 2. 检查支持的文件
        test_files = [
            Path("presentation.pptx"),
            Path("slide.ppt"),
            Path("document.docx"),
        ]

        for file_path in test_files:
            if ProcessorRegistry.is_supported(file_path):
                processor_class = ProcessorRegistry.get_processor(file_path)
                assert processor_class == PPTProcessor
            else:
                assert file_path.suffix == ".docx"

    def test_processor_selection_logic(self):
        """测试处理器选择逻辑"""

        @register_processor
        class PPTProcessor(DocumentProcessor):
            @classmethod
            def supported_extensions(cls):
                return [".pptx"]

            def extract_content(self, config):
                pass

            def render_pages(self, config):
                pass

        @register_processor
        class PDFProcessor(DocumentProcessor):
            @classmethod
            def supported_extensions(cls):
                return [".pdf"]

            def extract_content(self, config):
                pass

            def render_pages(self, config):
                pass

        # 验证正确选择处理器
        ppt_file = Path("test.pptx")
        pdf_file = Path("test.pdf")
        unknown_file = Path("test.xyz")

        assert ProcessorRegistry.get_processor(ppt_file) == PPTProcessor
        assert ProcessorRegistry.get_processor(pdf_file) == PDFProcessor
        assert ProcessorRegistry.get_processor(unknown_file) is None
