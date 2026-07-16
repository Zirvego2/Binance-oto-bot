"""Servis basina tek process kilidi (SQLite cakismasini onler)."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def _repo_root() -> Path:
    start = Path(__file__).resolve()
    for parent in start.parents:
        if (parent / "packages" / "shared" / "shared").is_dir():
            return parent
    return Path.cwd()


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        out = result.stdout or ""
        return str(pid) in out and "No tasks are running" not in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def acquire_service_lock(service_name: str) -> Path:
    """Kilit al; baska instance calisiyorsa process'i sonlandir."""
    lock_dir = _repo_root() / ".run"
    lock_dir.mkdir(exist_ok=True)
    lock_file = lock_dir / f"{service_name}.pid"

    if lock_file.exists():
        try:
            old_pid = int(lock_file.read_text(encoding="utf-8").strip())
        except ValueError:
            old_pid = 0
        if _pid_alive(old_pid) and old_pid != os.getpid():
            raise RuntimeError(
                f"{service_name} zaten calisiyor (PID {old_pid}). "
                f"Once scripts/stop_bot.ps1 calistirin."
            )
        lock_file.unlink(missing_ok=True)

    for _ in range(20):
        try:
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("utf-8"))
            os.close(fd)
            return lock_file
        except FileExistsError:
            if lock_file.exists():
                try:
                    old_pid = int(lock_file.read_text(encoding="utf-8").strip())
                except ValueError:
                    old_pid = 0
                if _pid_alive(old_pid) and old_pid != os.getpid():
                    raise RuntimeError(
                        f"{service_name} zaten calisiyor (PID {old_pid}). "
                        f"Once scripts/stop_bot.ps1 calistirin."
                    )
                lock_file.unlink(missing_ok=True)
            time.sleep(0.1)

    raise RuntimeError(f"{service_name} process kilidi alinamadi")


def release_service_lock(lock_file: Path | None) -> None:
    if lock_file is None or not lock_file.exists():
        return
    try:
        if int(lock_file.read_text(encoding="utf-8").strip()) == os.getpid():
            lock_file.unlink(missing_ok=True)
    except (ValueError, OSError):
        pass


def ensure_single_instance(service_name: str) -> Path:
    try:
        return acquire_service_lock(service_name)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
