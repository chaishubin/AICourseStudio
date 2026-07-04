"""Word/PDF 教案摄取层。"""

from .models import SourceDocument, SourceSection
from .reader import read_source_document

__all__ = ["SourceDocument", "SourceSection", "read_source_document"]
