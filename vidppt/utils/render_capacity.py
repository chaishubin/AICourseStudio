"""One CPU-heavy render at a time, while network tasks continue independently."""
import threading
from contextlib import contextmanager, nullcontext
from functools import wraps
from .performance import timed_step

_render_lock = threading.RLock()


@contextmanager
def render_capacity(cancel_check=None, output_dir=None):
    with timed_step(output_dir, 'render_wait') if output_dir else nullcontext():
        while not _render_lock.acquire(timeout=0.2):
            if cancel_check and cancel_check():
                raise InterruptedError('用户停止了生成')
    try:
        if cancel_check and cancel_check():
            raise InterruptedError('用户停止了生成')
        yield
    finally:
        _render_lock.release()


def serialized_render(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with render_capacity(kwargs.get('cancel_check')):
            return function(*args, **kwargs)
    return wrapped
