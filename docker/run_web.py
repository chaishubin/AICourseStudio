"""Run the Web service while mirroring container stdout/stderr to a shared log."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


LOG_FILE = Path(os.environ.get(
    "VIDPPT_SERVER_LOG_FILE",
    "/app/web/outputs/_system/server.log",
))
MAX_BYTES = max(1024 * 1024, _env_int("VIDPPT_SERVER_LOG_MAX_BYTES", 50 * 1024 * 1024))
BACKUP_COUNT = max(1, min(10, _env_int("VIDPPT_SERVER_LOG_BACKUPS", 5)))


def _rotate() -> None:
    if not LOG_FILE.exists() or LOG_FILE.stat().st_size < MAX_BYTES:
        return
    oldest = LOG_FILE.with_name(f"{LOG_FILE.name}.{BACKUP_COUNT}")
    oldest.unlink(missing_ok=True)
    for index in range(BACKUP_COUNT - 1, 0, -1):
        source = LOG_FILE.with_name(f"{LOG_FILE.name}.{index}")
        if source.exists():
            source.replace(LOG_FILE.with_name(f"{LOG_FILE.name}.{index + 1}"))
    LOG_FILE.replace(LOG_FILE.with_name(f"{LOG_FILE.name}.1"))


def _write(line: str) -> None:
    sys.stdout.write(line)
    sys.stdout.flush()
    _rotate()
    with LOG_FILE.open("a", encoding="utf-8") as stream:
        stream.write(line)
        stream.flush()


def main() -> int:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-u", "web/app.py", "5000"]
    child = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    def forward_signal(signum, _frame) -> None:
        if child.poll() is None:
            child.send_signal(signum)

    signal.signal(signal.SIGTERM, forward_signal)
    signal.signal(signal.SIGINT, forward_signal)

    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    _write(f"\n===== VidPPT server started at {started_at} pid={child.pid} =====\n")
    assert child.stdout is not None
    for line in child.stdout:
        _write(line)
    return_code = child.wait()
    stopped_at = datetime.now().astimezone().isoformat(timespec="seconds")
    _write(f"===== VidPPT server stopped at {stopped_at} code={return_code} =====\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
