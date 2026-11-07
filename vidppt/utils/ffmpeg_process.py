"""Cancellable FFmpeg execution with bounded diagnostics and no pipe backpressure."""
import subprocess
import tempfile
import time


def run_ffmpeg(command, cancel_check=None, *, duration=None, progress_callback=None):
    with tempfile.TemporaryFile(mode='w+b') as errors, tempfile.TemporaryDirectory(prefix='ffmpeg_progress_') as folder:
        progress_path = folder + '/progress'
        command = list(command)
        last_fraction = 0.0
        if progress_callback and duration and duration > 0:
            command[1:1] = ['-progress', progress_path, '-nostats']

        def report():
            nonlocal last_fraction
            if not progress_callback or not duration or duration <= 0:
                return
            try:
                with open(progress_path, 'rb') as stream:
                    stream.seek(0, 2)
                    stream.seek(max(0, stream.tell() - 8192))
                    lines = stream.read().decode(errors='replace').split('\n')[:-1]
            except FileNotFoundError:
                return
            for line in reversed(lines):
                if line.startswith('out_time_us='):
                    try:
                        fraction = min(0.99, max(0.0, float(line.split('=', 1)[1]) / 1e6 / duration))
                    except ValueError:
                        return
                    if fraction > last_fraction:
                        last_fraction = fraction
                        progress_callback(fraction)
                    return

        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=errors)
        try:
            while process.poll() is None:
                if cancel_check and cancel_check():
                    raise InterruptedError('用户停止了视频生成')
                report()
                time.sleep(0.1)
            if process.returncode:
                errors.seek(0, 2)
                errors.seek(max(0, errors.tell() - 65536))
                raise subprocess.CalledProcessError(
                    process.returncode, command, stderr=errors.read().decode(errors='replace')
                )
            if progress_callback:
                progress_callback(1.0)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
