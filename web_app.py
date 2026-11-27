#!/usr/bin/env python3
"""Web UI wrapper for the files and folders organizer CLI tool."""

import io
import json
import os
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Optional

from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "/data/workspace"))
WORKSPACE.mkdir(parents=True, exist_ok=True)
SCRIPT = Path(__file__).resolve().parent / "files and folders organizer.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_unique(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, ext, i = dest.stem, dest.suffix, 2
    while (dest.parent / f"{stem} - {i}{ext}").exists():
        i += 1
    return dest.parent / f"{stem} - {i}{ext}"


def _dest_from_relative(rel: str) -> Optional[Path]:
    """Map an uploaded relative path into the workspace, or None if unsafe."""
    parts = [p for p in rel.replace("\\", "/").split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return None
    return WORKSPACE.joinpath(*parts)


def _make_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Generate a minimal solid-colour PNG using only the stdlib."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes(rgb) * width
    idat = zlib.compress(row * height)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/files")
def list_files():
    files = []
    for p in sorted(WORKSPACE.rglob("*")):
        if p.is_file():
            rel = p.relative_to(WORKSPACE)
            files.append(
                {
                    "name": p.name,
                    "path": str(rel),
                    "size": p.stat().st_size,
                }
            )
    return jsonify(files)


@app.route("/api/upload", methods=["POST"])
def upload():
    uploaded = request.files.getlist("files")
    raw_paths = request.form.get("paths")
    rel_paths = json.loads(raw_paths) if raw_paths else []
    count = 0
    for idx, f in enumerate(uploaded):
        if not f.filename:
            continue
        rel = rel_paths[idx] if idx < len(rel_paths) else f.filename
        dest = _dest_from_relative(rel)
        if dest is None:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        f.save(_ensure_unique(dest))
        count += 1
    return jsonify({"uploaded": count})


@app.route("/api/run", methods=["POST"])
def run():
    opts = request.json or {}
    args = [sys.executable, str(SCRIPT)]

    if opts.get("recursive"):
        args.append("-r")
    if opts.get("dry_run"):
        args.append("--dry-run")
    if opts.get("organize_only"):
        args.append("--organize-only")
    if opts.get("organize"):
        args.append("--organize")
    if opts.get("mnemonically_boosted"):
        args.append("--mnemonically-boosted")
    if opts.get("prune_empty_dirs"):
        args.append("--prune-empty-dirs")
    if opts.get("trace"):
        args.append("--trace")

    model = opts.get("model", "gpt-4.1-mini")
    args.extend(["--model", model])

    env = os.environ.copy()
    env["HOME"] = str(WORKSPACE)

    try:
        proc = subprocess.run(
            args,
            cwd=str(WORKSPACE),
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = proc.stdout
        if proc.stderr:
            output += "\n" + proc.stderr if output else proc.stderr
        return jsonify({"output": output, "exit_code": proc.returncode})
    except subprocess.TimeoutExpired:
        return jsonify({"output": "Process timed out after 300 seconds.", "exit_code": 124})


@app.route("/api/sample", methods=["POST"])
def sample():
    samples = [
        ("IMG_0001.txt", "Photos from our family vacation to Banff National Park last summer. "
                         "Mountains, lakes, and hiking trails. Great trip overall!"),
        ("DSC_0234.txt", "Quarterly business review meeting notes. Discussed Q3 revenue targets, "
                         "marketing strategy, and product roadmap. Action items assigned to team leads."),
        ("a1b2c3d4-e5f6-7890-abcd-ef1234567890.csv",
         "date,amount,description\n2024-01-15,129.99,Internet bill\n2024-02-15,129.99,Internet bill\n"),
        ("PXL_20240315_123456789.png", _make_png(64, 64, (70, 130, 180))),
        ("screenshot 2024-03-20 at 10.30.00.png", _make_png(64, 64, (240, 240, 240))),
    ]
    for name, content in samples:
        dest = _ensure_unique(WORKSPACE / name)
        if isinstance(content, str):
            dest.write_text(content)
        else:
            dest.write_bytes(content)
    return jsonify({"created": len(samples)})


@app.route("/api/clear", methods=["POST"])
def clear():
    count = 0
    for p in WORKSPACE.rglob("*"):
        if p.is_file():
            p.unlink()
            count += 1
    # Remove empty dirs (bottom-up)
    for d in sorted(
        (p for p in WORKSPACE.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        try:
            if not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass
    return jsonify({"cleared": count})


@app.route("/api/key-status")
def key_status():
    return jsonify({"has_key": bool(os.getenv("OPENAI_API_KEY"))})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)
