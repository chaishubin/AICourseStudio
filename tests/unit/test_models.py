"""
测试核心数据模型

测试覆盖：
- PageContent 数据类
- DocumentContent 数据类
- ProcessConfig 配置类
"""

import pytest
from pathlib import Path
from vidppt.core.models import PageContent, DocumentContent, ProcessConfig


class TestPageContent:
    """测试 PageContent 数据模型"""

    def test_create_minimal_page(self):
        """测试创建最小化的页面内容"""
        page = PageContent(page_number=1)

        assert page.page_number == 1
        assert page.text == ""
        assert page.images == []
        assert page.slide_image is None
        assert page.audio is None
        assert page.metadata == {}

    def test_create_full_page(self):
        """测试创建完整的页面内容"""
        page = PageContent(
            page_number=2,
            text="这是测试文本",
            images=[Path("img1.png"), Path("img2.png")],
            slide_image=Path("slide.png"),
            audio=Path("audio.mp3"),
            metadata={"title": "测试页", "duration": 10},
        )

        assert page.page_number == 2
        assert page.text == "这是测试文本"
        assert len(page.images) == 2
        assert page.slide_image == Path("slide.png")
        assert page.audio == Path("audio.mp3")
        assert page.metadata["title"] == "测试页"
        assert page.metadata["duration"] == 10

    def test_page_mutability(self):
        """测试页面内容的可变性"""
        page = PageContent(page_number=1)

        # 应该可以修改属性
        page.text = "新文本"
        page.images.append(Path("new_image.png"))
        page.metadata["added"] = True

        assert page.text == "新文本"
        assert Path("new_image.png") in page.images
        assert page.metadata["added"] is True


class TestDocumentContent:
    """测试 DocumentContent 数据模型"""

    def test_create_empty_document(self):
        """测试创建空文档"""
        doc = DocumentContent(pages=[])

        assert doc.pages == []
        assert doc.total_pages == 0
        assert doc.metadata == {}

    def test_create_document_with_pages(self):
        """测试创建包含页面的文档"""
        pages = [
            PageContent(page_number=1, text="第一页"),
            PageContent(page_number=2, text="第二页"),
            PageContent(page_number=3, text="第三页"),
        ]

        doc = DocumentContent(
            pages=pages, metadata={"title": "测试文档", "author": "测试者"}
        )

        assert doc.total_pages == 3
        assert doc.pages[0].text == "第一页"
        assert doc.pages[2].text == "第三页"
        assert doc.metadata["title"] == "测试文档"

    def test_total_pages_property(self):
        """测试 total_pages 属性动态计算"""
        doc = DocumentContent(pages=[])
        assert doc.total_pages == 0

        # 添加页面
        doc.pages.append(PageContent(page_number=1))
        assert doc.total_pages == 1

        doc.pages.append(PageContent(page_number=2))
        assert doc.total_pages == 2

        # 删除页面
        doc.pages.pop()
        assert doc.total_pages == 1


class TestProcessConfig:
    """测试 ProcessConfig 配置模型"""

    def test_create_minimal_config(self):
        """测试创建最小化配置"""
        config = ProcessConfig(input_path=Path("test.pptx"), output_dir=Path("output"))

        assert config.input_path == Path("test.pptx")
        assert config.output_dir == Path("output")

        # 检查默认值
        assert config.enable_tts is True
        assert config.enable_video is True
        assert config.save_intermediate is True
        assert config.tts_engine == "edge-tts"
        assert config.tts_voice == "zh-CN-XiaoxiaoNeural"
        assert config.tts_rate == "+0%"
        assert config.ocr_engine == "builtin"
        assert config.video_fps == 24

    def test_create_custom_config(self):
        """测试创建自定义配置"""
        config = ProcessConfig(
            input_path="input.pptx",
            output_dir="output",
            enable_tts=False,
            enable_video=False,
            save_intermediate=False,
            tts_engine="minimax",
            tts_voice="male-voice",
            tts_rate="+20%",
            ocr_engine="tesseract",
            video_fps=30,
            video_codec="libx265",
        )

        assert config.enable_tts is False
        assert config.enable_video is False
        assert config.save_intermediate is False
        assert config.tts_engine == "minimax"
        assert config.tts_voice == "male-voice"
        assert config.tts_rate == "+20%"
        assert config.ocr_engine == "tesseract"
        assert config.video_fps == 30
        assert config.video_codec == "libx265"

    def test_path_conversion_in_post_init(self):
        """测试 __post_init__ 中的路径转换"""
        # 使用字符串路径
        config = ProcessConfig(input_path="test.pptx", output_dir="output")

        # 应该自动转换为 Path 对象
        assert isinstance(config.input_path, Path)
        assert isinstance(config.output_dir, Path)
        assert config.input_path == Path("test.pptx")
        assert config.output_dir == Path("output")

    def test_config_with_pathlib_paths(self):
        """测试直接使用 Path 对象创建配置"""
        input_path = Path("/tmp/test.pptx")
        output_dir = Path("/tmp/output")

        config = ProcessConfig(input_path=input_path, output_dir=output_dir)

        assert config.input_path == input_path
        assert config.output_dir == output_dir

    def test_config_immutability_concerns(self):
        """测试配置的可修改性（dataclass 默认可修改）"""
        config = ProcessConfig(input_path=Path("test.pptx"), output_dir=Path("output"))

        # dataclass 默认是可修改的
        config.tts_rate = "+50%"
        assert config.tts_rate == "+50%"

        config.video_fps = 60
        assert config.video_fps == 60


class TestModelsIntegration:
    """测试模型之间的集成"""

    def test_full_document_workflow(self):
        """测试完整的文档工作流"""
        # 1. 创建配置
        config = ProcessConfig(
            input_path=Path("test.pptx"),
            output_dir=Path("output"),
            save_intermediate=True,
        )

        # 2. 创建页面
        pages = []
        for i in range(1, 4):
            page = PageContent(
                page_number=i, text=f"第 {i} 页内容", slide_image=Path(f"slide_{i}.png")
            )
            pages.append(page)

        # 3. 创建文档
        doc = DocumentContent(pages=pages, metadata={"source": str(config.input_path)})

        # 4. 验证
        assert doc.total_pages == 3
        assert doc.metadata["source"] == "test.pptx"
        assert all(p.page_number == i for i, p in enumerate(doc.pages, 1))

    def test_page_processing_simulation(self):
        """模拟页面处理过程"""
        page = PageContent(page_number=1, text="测试文本")

        # 模拟添加图片
        page.images.append(Path("extracted_img.png"))

        # 模拟渲染幻灯片
        page.slide_image = Path("rendered_slide.png")

        # 模拟生成音频
        page.audio = Path("generated_audio.mp3")

        # 模拟添加元数据
        page.metadata["processed"] = True
        page.metadata["processing_time"] = 1.5

        # 验证处理结果
        assert len(page.images) == 1
        assert page.slide_image is not None
        assert page.audio is not None
        assert page.metadata["processed"] is True
