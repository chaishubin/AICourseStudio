"""Content-addressed source artifacts shared across task directories.

Only source parsing and rendering belong here; generated scripts never do.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading

from loguru import logger

_LOCK = threading.RLock()


def file_digest(path: Path) -> str:
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class DocumentCache:
    def __init__(self, namespace: str, identity):
        root = Path(os.environ.get('VIDPPT_DOCUMENT_CACHE_DIR',
                                   str(Path.home() / '.cache/vidppt/documents')))
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        self.path = root / namespace / key

    def load(self):
        """Return fresh JSON values and verified asset paths, or a cache miss."""
        try:
            with _LOCK:
                manifest = json.loads((self.path / 'manifest.json').read_text())
                payload_bytes = json.dumps(manifest['payload'], sort_keys=True).encode()
                if hashlib.sha256(payload_bytes).hexdigest() != manifest['payload_hash']:
                    return None
                files = [self.path / str(i) for i in range(len(manifest['assets']))]
                if any(file_digest(p) != digest
                       for p, digest in zip(files, manifest['assets'])):
                    return None
                return manifest['payload'], files
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def store(self, payload, files=()):
        """Publish complete entries atomically; cache failures never fail a task."""
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = Path(tempfile.mkdtemp(prefix='.pending-', dir=self.path.parent))
            hashes = []
            for index, source in enumerate(files):
                target = temporary / str(index)
                shutil.copyfile(source, target)
                hashes.append(file_digest(target))
            (temporary / 'manifest.json').write_text(json.dumps({
                'payload': payload, 'assets': hashes,
                'payload_hash': hashlib.sha256(
                    json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            }, ensure_ascii=False), encoding='utf-8')
            with _LOCK:
                if self.path.exists():
                    if self.load() is not None:
                        return
                    shutil.rmtree(self.path)
                try:
                    temporary.rename(self.path)
                except FileExistsError:
                    pass  # Another worker published the same content.
        except OSError as exc:
            logger.warning(f'无法写入文档缓存，继续使用本次处理结果: {exc}')
        finally:
            if temporary and temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)
