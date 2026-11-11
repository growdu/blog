"""Render mermaid diagrams to PNG.

WeChat cannot run JavaScript, so a ``<div class="mermaid">`` copied from
the site would arrive as an empty div and the diagram would vanish
silently.  This module renders each diagram to a PNG with mermaid-cli.

A diagram that fails to render must not disappear: the caller receives
an asset with ``png=None`` and an error message, and the renderer falls
back to showing the diagram source.

Roughly 8% of the diagrams in this repository fail to parse (see
``tools/mermaid-audit.md``), so the failure path is a normal path, not an
edge case.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

__all__ = ["MermaidAsset", "mermaid_key", "render_mermaid", "default_runner"]

# Pinned to the 10.9 line so the rendered diagram matches what the site
# shows with mermaid 10.9.8.
MERMAID_CLI_VERSION = "10.9.1"
DEFAULT_WIDTH = 1080
DEFAULT_BACKGROUND = "white"
# Render at 2x so the diagram stays sharp on a retina phone.  WeChat
# scales images down to the body width, so the extra pixels survive.
DEFAULT_SCALE = 2
RENDER_TIMEOUT = 180

_CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
)


@dataclass(frozen=True)
class MermaidAsset:
    """One mermaid diagram and its rendered PNG (if rendering worked)."""

    key: str
    source: str
    png: Path | None = None
    error: str | None = None


def mermaid_key(source: str) -> str:
    """Stable key for a diagram, independent of its position in the post."""
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]


def _find_chrome() -> str | None:
    for candidate in _CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def _summarize_error(stderr: str, stdout: str) -> str:
    """Extract the meaningful message from mermaid-cli's output.

    mermaid-cli prints a JavaScript stack trace after the real error, and
    the trace is longer than the message, so the head of the output is
    kept rather than the tail.
    """
    for stream in (stderr, stdout):
        for line in stream.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("Error") or "Parse error" in line:
                return line[:400]
    for stream in (stderr, stdout):
        for line in stream.split("\n"):
            if line.strip():
                return line.strip()[:400]
    return "mermaid-cli failed"


def default_runner(source: str, out_file: Path):
    """Render a diagram with mermaid-cli.

    Returns ``(ok, error_message)``.  The system Chrome is used when one
    is installed, so puppeteer does not download its own Chromium.
    """
    out_file.parent.mkdir(parents=True, exist_ok=True)
    source_file = out_file.with_suffix(".mmd")
    source_file.write_text(source, encoding="utf-8")

    env = dict(os.environ)
    chrome = _find_chrome()
    if chrome:
        env["PUPPETEER_EXECUTABLE_PATH"] = chrome

    command = [
        "npx", "-y", "@mermaid-js/mermaid-cli@{}".format(MERMAID_CLI_VERSION),
        "-i", str(source_file),
        "-o", str(out_file),
        "-w", str(DEFAULT_WIDTH),
        "-b", DEFAULT_BACKGROUND,
        "-s", str(DEFAULT_SCALE),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, env=env, timeout=RENDER_TIMEOUT)
    except FileNotFoundError:
        return False, "npx not found: install Node.js to render mermaid diagrams"
    except subprocess.TimeoutExpired:
        return False, "mermaid-cli timed out after {}s".format(RENDER_TIMEOUT)

    if result.returncode != 0 or not out_file.exists():
        return False, _summarize_error(result.stderr or "", result.stdout or "")
    return True, ""


def render_mermaid(blocks: list, out_dir: Path, *, runner=None) -> dict:
    """Render every mermaid block in ``blocks`` to a PNG.

    Returns a mapping from diagram key to :class:`MermaidAsset`.  Results
    are cached on disk by source hash, so re-running a conversion does not
    re-render diagrams that have not changed.
    """
    run = runner or default_runner
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    assets = {}
    for block in blocks:
        if getattr(block, "lang", "").lower() != "mermaid":
            continue
        source = block.code
        key = mermaid_key(source)
        if key in assets:
            continue

        png = out_dir / "{}.png".format(key)
        if png.exists() and png.stat().st_size > 0:
            assets[key] = MermaidAsset(key=key, source=source, png=png)
            continue

        ok, error = run(source, png)
        if ok and png.exists():
            assets[key] = MermaidAsset(key=key, source=source, png=png)
        else:
            if png.exists():
                png.unlink()
            assets[key] = MermaidAsset(key=key, source=source, png=None, error=error)

    return assets
