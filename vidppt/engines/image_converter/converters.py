"""
图像转换器实现
"""
from pathlib import Path
from typing import Optional

from ...core.interfaces import ImageConverter


class SpireImageConverter(ImageConverter):
    """
    基于 Spire 的图像转换器
    支持 PPT, Word, Excel 等格式
    """
    
    def convert_to_image(
        self,
        source_path: Path,
        output_path: Path,
        page_number: Optional[int] = None,
    ) -> Path:
        """将源文件（或指定页）转换为图像"""
        # 根据文件类型选择对应的 Spire 库
        suffix = source_path.suffix.lower()
        
        if suffix in ['.ppt', '.pptx']:
            return self._convert_ppt_page(source_path, output_path, page_number)
        elif suffix in ['.doc', '.docx']:
            return self._convert_word_page(source_path, output_path, page_number)
        else:
            raise ValueError(f"不支持的文件类型: {suffix}")
    
    def convert_all_pages(
        self,
        source_path: Path,
        output_dir: Path,
    ) -> list[Path]:
        """将所有页转换为图像"""
        suffix = source_path.suffix.lower()
        
        if suffix in ['.ppt', '.pptx']:
            return self._convert_ppt_all_pages(source_path, output_dir)
        elif suffix in ['.doc', '.docx']:
            return self._convert_word_all_pages(source_path, output_dir)
        else:
            raise ValueError(f"不支持的文件类型: {suffix}")
    
    def _convert_ppt_page(
        self,
        source_path: Path,
        output_path: Path,
        page_number: Optional[int],
    ) -> Path:
        """转换 PPT 单页"""
        from spire.presentation import Presentation
        import io
        from PIL import Image
        
        prs = Presentation()
        prs.LoadFromFile(str(source_path))
        
        page_idx = (page_number or 1) - 1
        slide = prs.Slides[page_idx]
        img_stream = slide.SaveAsImage()
        img_bytes = bytes(img_stream.ToArray())
        img = Image.open(io.BytesIO(img_bytes))
        
        img.save(output_path, "PNG")
        img_stream.Dispose()
        prs.Dispose()
        
        return output_path
    
    def _convert_ppt_all_pages(
        self,
        source_path: Path,
        output_dir: Path,
    ) -> list[Path]:
        """转换 PPT 所有页"""
        from spire.presentation import Presentation
        import io
        from PIL import Image
        
        prs = Presentation()
        prs.LoadFromFile(str(source_path))
        
        output_dir.mkdir(parents=True, exist_ok=True)
        slide_images = []
        
        for i in range(prs.Slides.Count):
            slide = prs.Slides[i]
            img_stream = slide.SaveAsImage()
            img_bytes = bytes(img_stream.ToArray())
            img = Image.open(io.BytesIO(img_bytes))
            
            out_path = output_dir / f"page_{i + 1}.png"
            img.save(out_path, "PNG")
            slide_images.append(out_path)
            
            img_stream.Dispose()
        
        prs.Dispose()
        return slide_images
    
    def _convert_word_page(
        self,
        source_path: Path,
        output_path: Path,
        page_number: Optional[int],
    ) -> Path:
        """转换 Word 单页"""
        # TODO: 使用 spire.doc
        raise NotImplementedError("Word 转换需要实现")
    
    def _convert_word_all_pages(
        self,
        source_path: Path,
        output_dir: Path,
    ) -> list[Path]:
        """转换 Word 所有页"""
        # TODO: 使用 spire.doc
        raise NotImplementedError("Word 转换需要实现")


class APIImageConverter(ImageConverter):
    """
    基于 API 的图像转换器（示例）
    可以通过 API 进行文件转换
    """
    
    def __init__(self, api_key: str, api_url: str, **kwargs):
        self.api_key = api_key
        self.api_url = api_url
        self.options = kwargs
    
    def convert_to_image(
        self,
        source_path: Path,
        output_path: Path,
        page_number: Optional[int] = None,
    ) -> Path:
        """将源文件（或指定页）转换为图像"""
        # TODO: 实现 API 调用
        raise NotImplementedError("API 图像转换需要实现")
    
    def convert_all_pages(
        self,
        source_path: Path,
        output_dir: Path,
    ) -> list[Path]:
        """将所有页转换为图像"""
        # TODO: 实现 API 调用
        raise NotImplementedError("API 图像转换需要实现")
