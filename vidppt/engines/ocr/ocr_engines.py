"""
OCR 引擎实现
"""
from pathlib import Path

from ...core.interfaces import OCREngine


class TesseractOCREngine(OCREngine):
    """
    基于 Tesseract 的 OCR 引擎
    
    安装：
        # macOS
        brew install tesseract tesseract-lang
        
        # Ubuntu
        sudo apt install tesseract-ocr tesseract-ocr-chi-sim
        
        # Python
        pip install pytesseract
    """
    
    def __init__(self, lang: str = "chi_sim+eng"):
        self.lang = lang
    
    def extract_text(self, image_path: Path) -> str:
        """从图像中提取文字"""
        try:
            import pytesseract
            from PIL import Image
            
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img, lang=self.lang)
            return text.strip()
        except ImportError:
            raise ImportError(
                "需要安装 pytesseract:\n"
                "  pip install pytesseract\n"
                "并确保系统已安装 Tesseract OCR"
            )
    
    def extract_text_batch(self, image_paths: list[Path]) -> list[str]:
        """批量从图像中提取文字"""
        return [self.extract_text(path) for path in image_paths]


class APIOCREngine(OCREngine):
    """
    基于 API 的 OCR 引擎（示例）
    可以对接各种云服务商的 OCR API
    """
    
    def __init__(self, api_key: str, api_url: str, **kwargs):
        self.api_key = api_key
        self.api_url = api_url
        self.options = kwargs
    
    def extract_text(self, image_path: Path) -> str:
        """从图像中提取文字"""
        # TODO: 实现具体的 API 调用逻辑
        raise NotImplementedError(
            "API OCR Engine 需要根据具体的 API 服务商实现"
        )
    
    def extract_text_batch(self, image_paths: list[Path]) -> list[str]:
        """批量从图像中提取文字"""
        # TODO: 可以实现批量调用优化
        return [self.extract_text(path) for path in image_paths]
