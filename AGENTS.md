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

The compose service has a healthcheck against `/api/files`; `docker compose ps` should show `(healthy)`.

## How the organizer is invoked

The web UI runs `"files and folders organizer.py"` as a **subprocess** with:
- `cwd` = the workspace directory (so `Path.cwd()` in the script resolves there)
- `HOME` = the workspace directory (so `--organize` moves files into subfolders of the workspace, not the container's real home)

## Dependencies

- Python 3.12 (`python:3.12-slim`)
- `flask`, `openai`, `pymupdf` from `web_requirements.txt`
- `ffmpeg` (needed for video frame extraction)

Both are installed at image build time by `Dockerfile.base44`; the repo is bind-mounted, so no
source is baked into the image. After changing `web_requirements.txt` rebuild:
`docker compose -f docker-compose.base44.yml up -d --build`.

## Why the CLI alone would not start

`files and folders organizer.py` is a CLI: with no server, nothing listens on port 3000, and on a
bare host it exits immediately with `ModuleNotFoundError: No module named 'openai'` because
dependencies are not installed. `web_app.py` + `docker-compose.base44.yml` are what make the
project startable/previewable here.

## Runtime failure that is NOT a bug

`fitz` prints a `FutureWarning` ("The `fitz` API is deprecated…") on every run — it comes from
PyMuPDF and is harmless; the app still runs.

## Secrets

- `OPENAI_API_KEY` — required for AI renaming; not needed for `--organize-only` mode. Delivered via `/run/base44/app.env`.

## Verifying it works

```bash
curl -sf http://localhost:3000/  # should return the HTML page
curl -sf http://localhost:3000/api/files  # should return JSON file list
```

In the preview: load sample files, check "Dry Run", click "Run Organizer" — you'll see proposed renames in the terminal output.
