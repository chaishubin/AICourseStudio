"""使用用户在 PowerPoint 中确认过的页面 PNG，不重新解释 PPT 版式。"""

import io
import re
from pathlib import Path
from zipfile import ZipFile

from PIL import Image
from pptx import Presentation

MAX_IMAGE_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024


def reference_path(source: Path) -> Path:
    return source.with_suffix('.slides.zip')


def read_original_slides(source: Path, archive: Path) -> list[bytes]:
    """按页码校验整个 ZIP 后返回 PNG 原始字节；不解压不可信路径。"""
    prs = Presentation(str(source))
    count = len(prs.slides)
    aspect = prs.slide_width / prs.slide_height
    pages = {}
    with ZipFile(archive) as bundle:
        total = 0
        for entry in bundle.infolist():
            if entry.is_dir() or entry.filename.startswith('__MACOSX/'):
                continue
            name = Path(entry.filename).name
            if name.startswith('.'):
                continue
            if Path(name).suffix.lower() != '.png':
                raise ValueError('原始页面 ZIP 只能包含 PNG 页面图片')
            match = re.search(r'(\d+)\.png$', name, re.IGNORECASE)
            if not match:
                raise ValueError(f'页面文件名必须以页码结尾：{name}')
            number = int(match[1])
            if number in pages or not 1 <= number <= count:
                raise ValueError(f'页面编号重复或超出 PPT 页数：{number}')
            total += entry.file_size
            if entry.file_size > MAX_IMAGE_BYTES or total > MAX_TOTAL_BYTES:
                raise ValueError('原始页面图片大小超过限制')
            data = bundle.read(entry)
            with Image.open(io.BytesIO(data)) as image:
                if image.format != 'PNG':
                    raise ValueError(f'页面不是有效 PNG：{name}')
                width, height = image.size
                if width * height > 40_000_000:
                    raise ValueError(f'页面像素过大：{name}')
                if abs((width / height) / aspect - 1) > 0.005:
                    raise ValueError(f'第 {number} 页宽高比与原 PPT 不一致')
                image.verify()
            pages[number] = data
    if set(pages) != set(range(1, count + 1)):
        raise ValueError(f'原始页面必须完整包含 PPT 的全部 {count} 页，页码从 1 连续编号')
    return [pages[number] for number in range(1, count + 1)]


def render_original_slides(source: Path, output: Path) -> list[Path]:
    archive = reference_path(source)
    if not archive.is_file():
        raise ValueError(f'缺少 PowerPoint 导出的页面 ZIP：{archive.name}；不会降级到其他排版引擎')
    pages = read_original_slides(source, archive)
    paths = []
    for number, data in enumerate(pages, 1):
        path = output / str(number) / 'slide.png'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        paths.append(path)
    return paths
