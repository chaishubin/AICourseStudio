"""
文档处理器注册中心
"""
from pathlib import Path
from typing import Optional, Type

from .interfaces import DocumentProcessor


class ProcessorRegistry:
    """文档处理器注册中心"""
    
    _processors: dict[str, Type[DocumentProcessor]] = {}
    
    @classmethod
    def register(cls, processor_class: Type[DocumentProcessor]) -> None:
        """注册文档处理器"""
        for ext in processor_class.supported_extensions():
            ext = ext.lower()
            if not ext.startswith('.'):
                ext = f'.{ext}'
            cls._processors[ext] = processor_class
            print(f"  注册处理器: {ext} -> {processor_class.__name__}")
    
    @classmethod
    def get_processor(cls, file_path: Path) -> Optional[Type[DocumentProcessor]]:
        """根据文件扩展名获取对应的处理器"""
        ext = file_path.suffix.lower()
        return cls._processors.get(ext)
    
    @classmethod
    def list_supported_extensions(cls) -> list[str]:
        """列出所有支持的文件扩展名"""
        return list(cls._processors.keys())
    
    @classmethod
    def is_supported(cls, file_path: Path) -> bool:
        """检查文件是否被支持"""
        return file_path.suffix.lower() in cls._processors


def register_processor(processor_class: Type[DocumentProcessor]):
    """装饰器：注册文档处理器"""
    ProcessorRegistry.register(processor_class)
    return processor_class
