import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"


def tracked_files() -> list[Path]:
    files: list[Path] = []
    for path in SRC_DIR.rglob("*.py"):
        if path.is_file():
            files.append(path)
    env_file = ROOT / ".env"
    if env_file.exists():
        files.append(env_file)
    return sorted(files)


def snapshot(paths: Iterable[Path]) -> dict[str, float]:
    snap: dict[str, float] = {}
    for path in paths:
        try:
            snap[str(path)] = path.stat().st_mtime
        except FileNotFoundError:
            snap[str(path)] = -1.0
    return snap


def changed(prev: dict[str, float], curr: dict[str, float]) -> bool:
    if prev.keys() != curr.keys():
        return True
    for key, old in prev.items():
        if curr.get(key) != old:
            return True
    return False


def stop_process(proc: subprocess.Popen | None) -> None:
    if not proc:
        return
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def start_bots(python_exe: str) -> tuple[subprocess.Popen, subprocess.Popen]:
    highrise = subprocess.Popen([python_exe, "src/bot.py"], cwd=str(ROOT))
    discord = subprocess.Popen([python_exe, "src/discord_bot.py"], cwd=str(ROOT))
    print(f"[supervisor] started highrise pid={highrise.pid}, discord pid={discord.pid}")
    return highrise, discord


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-restart Clerk bots on file changes.")
    parser.add_argument("--interval", type=float, default=1.5, help="Polling interval in seconds.")
    args = parser.parse_args()

    python_exe = sys.executable
    highrise_proc: subprocess.Popen | None = None
    discord_proc: subprocess.Popen | None = None

    files = tracked_files()
    snap = snapshot(files)
    highrise_proc, discord_proc = start_bots(python_exe)

    try:
        while True:
            time.sleep(args.interval)
            files = tracked_files()
            current = snapshot(files)

            if changed(snap, current):
                print("[supervisor] change detected, restarting bots...")
                stop_process(highrise_proc)
                stop_process(discord_proc)
                highrise_proc, discord_proc = start_bots(python_exe)
                snap = current
                continue

            # If either process exited unexpectedly, restart both to keep them in sync.
            if (highrise_proc and highrise_proc.poll() is not None) or (
                discord_proc and discord_proc.poll() is not None
            ):
                print("[supervisor] process exited, restarting both bots...")
                stop_process(highrise_proc)
                stop_process(discord_proc)
                highrise_proc, discord_proc = start_bots(python_exe)
                snap = current
    except KeyboardInterrupt:
        print("[supervisor] stopping...")
    finally:
        stop_process(highrise_proc)
        stop_process(discord_proc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
