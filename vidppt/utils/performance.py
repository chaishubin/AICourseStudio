"""Persist small, thread-safe timing aggregates without recording content or credentials."""
import json
import threading
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter

from loguru import logger

_timing_lock = threading.Lock()


@contextmanager
def timed_step(output_dir, name):
    started = perf_counter()
    failed = False
    try:
        yield
    except BaseException:
        failed = True
        raise
    finally:
        duration = perf_counter() - started
        path = Path(output_dir) / 'performance.json'
        try:
            with _timing_lock:
                try:
                    data = json.loads(path.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    data = {}
                if not isinstance(data, dict) or not isinstance(data.get('steps', {}), dict):
                    data = {}
                steps = data.setdefault('steps', {})
                previous = steps.get(name, {})
                steps[name] = {
                    'calls': previous.get('calls', 0) + 1,
                    'failures': previous.get('failures', 0) + int(failed),
                    'total_seconds': round(previous.get('total_seconds', 0) + duration, 4),
                    'last_seconds': round(duration, 4),
                }
                data['version'] = 1
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix('.json.tmp')
                temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
                temporary.replace(path)
        except (OSError, ValueError, TypeError):
            logger.warning('无法保存性能计时：{}', path)
        logger.info('performance step={} seconds={:.3f} failed={}', name, duration, failed)

