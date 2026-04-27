"""
核心抽象接口定义
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Callable

from .models import DocumentContent, PageContent, ProcessConfig


# 进度回调函数类型: (当前页码, 总页数, 页信息) -> None
ProgressCallback = Callable[[int, int, str], None]


class DocumentProcessor(ABC):
    """文档处理器抽象基类"""

    @classmethod
    @abstractmethod
    def supported_extensions(cls) -> list[str]:
        """返回支持的文件扩展名列表"""
        pass

    @abstractmethod
    def extract_content(self, config: ProcessConfig) -> DocumentContent:
        """提取文档内容（文字、图片等）"""
        pass

    @abstractmethod
    def render_pages(self, config: ProcessConfig) -> list[Path]:
        """渲染页面为图像"""
        pass

    def process(self, config: ProcessConfig) -> DocumentContent:
        """
        完整处理流程（模板方法）
        子类可以重写以定制流程
        """
        # 1. 提取内容
        content = self.extract_content(config)

        # 2. 渲染页面
        slide_images = self.render_pages(config)
        for i, page in enumerate(content.pages):
            if i < len(slide_images):
                page.slide_image = slide_images[i]

        return content


class TTSEngine(ABC):
    """文字转语音引擎抽象基类"""

    @abstractmethod
    async def convert_async(
        self,
        text: str,
        output_path: Path,
        voice: str,
        rate: str,
    ) -> None:
        """异步转换单个文本为音频"""
        pass

    async def batch_convert(
        self,
        texts: list[tuple[int, str, Path]],
        voice: str,
        rate: str,
        batch_size: int = 5,
        progress_callback: Optional[ProgressCallback] = None,
        continue_on_error: bool = True,
        **kwargs,
    ) -> list[tuple[int, str]]:
        """批量转换文本为音频

        参数:
            texts: [(页码, 文本, 输出路径), ...]
            voice: 语音 ID
            rate: 语速
            batch_size: 批处理大小（默认 5）
            progress_callback: 进度回调函数 (当前索引, 总数, 页信息)
            continue_on_error: 单个失败时是否继续处理其他页面（默认 True）
            **kwargs: 透传给 convert_async 的额外参数（如 emotion、pronunciation_dict 等）

        返回:
            失败列表: [(页码, 错误信息), ...]
        """
        import asyncio
        from loguru import logger

        total = len(texts)
        errors: list[tuple[int, str]] = []

        async def convert_with_progress(item: tuple[int, str, Path], index: int):
            """转换单个并更新进度"""
            page_num, text, path = item
            try:
                await self.convert_async(text, path, voice, rate, **kwargs)
            except Exception as e:
                error_msg = str(e)
                errors.append((page_num, error_msg))
                if continue_on_error:
                    logger.warning(f"第 {page_num} 页 TTS 转换失败: {error_msg}")
                else:
                    raise
            if progress_callback:
                progress_callback(index + 1, total, f"第 {page_num} 页")

        tasks = [
            convert_with_progress(item, i)
            for i, item in enumerate(texts)
        ]

        # 分批处理避免并发过多
        for i in range(0, len(tasks), batch_size):
            await asyncio.gather(*tasks[i : i + batch_size])

        return errors


class OCREngine(ABC):
    """OCR 引擎抽象基类"""

    @abstractmethod
    def extract_text(self, image_path: Path) -> str:
        """从图像中提取文字"""
        pass

    @abstractmethod
    def extract_text_batch(self, image_paths: list[Path]) -> list[str]:
        """批量从图像中提取文字"""
        pass


class ImageConverter(ABC):
    """图像转换器抽象基类"""

    @abstractmethod
    def convert_to_image(
        self,
        source_path: Path,
        output_path: Path,
        page_number: Optional[int] = None,
    ) -> Path:
        """将源文件（或指定页）转换为图像"""
        pass

    @abstractmethod
    def convert_all_pages(
        self,
        source_path: Path,
        output_dir: Path,
    ) -> list[Path]:
        """将所有页转换为图像"""
        pass
