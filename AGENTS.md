# Base44 Dev Environment

## What this is

A Python CLI tool ("files and folders organizer") that renames and organizes files using OpenAI classification. The repo also contains geospatial helper scripts and a Wix/Velo project (`doctor-gavrielov/`, gitignored).

## Web UI

`web_app.py` is a Flask wrapper around the CLI tool, served on port 3000. It provides:
- File upload to a Docker-volume workspace (`/data/workspace`)
- Sample file generation for quick demos
- Options panel matching the CLI flags (dry-run, recursive, organize-only, etc.)
- Terminal-style output display

The Flask app runs with `debug=True` for live reload of Python changes. Template/static file changes are picked up automatically.

## How the organizer is invoked

The web UI runs `"files and folders organizer.py"` as a **subprocess** with:
- `cwd` = the workspace directory (so `Path.cwd()` in the script resolves there)
- `HOME` = the workspace directory (so `--organize` moves files into subfolders of the workspace, not the container's real home)

## Dependencies

- Python 3.12 (from `python:3.12-slim` base image)
- `flask`, `openai`, `pymupdf` (installed via `web_requirements.txt` at container start)
- `ffmpeg` (installed via apt at container start, needed for video frame extraction)

## Secrets

- `OPENAI_API_KEY` — required for AI renaming; not needed for `--organize-only` mode. Delivered via `/run/base44/app.env`.

## Verifying it works

```bash
curl -sf http://localhost:3000/  # should return the HTML page
curl -sf http://localhost:3000/api/files  # should return JSON file list
```

In the preview: load sample files, check "Dry Run", click "Run Organizer" — you'll see proposed renames in the terminal output.
