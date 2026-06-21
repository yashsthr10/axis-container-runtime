from __future__ import annotations

import subprocess

from .errors import CommandError


def run(command: list[str], *, capture: bool = False, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            input=input_bytes,
            text=False if input_bytes is not None else True,
            capture_output=capture,
        )
    except subprocess.CalledProcessError as exc:
        stderr = ""
        if isinstance(exc.stderr, bytes):
            stderr = exc.stderr.decode(errors="replace")
        elif exc.stderr:
            stderr = exc.stderr
        raise CommandError(f"Command failed: {' '.join(command)}\n{stderr}".rstrip()) from exc


def output(command: list[str]) -> str:
    result = run(command, capture=True)
    return result.stdout.strip()
