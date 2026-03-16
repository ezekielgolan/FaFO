# New project

This repository is currently a small workspace rather than a single tightly scoped app.

## Contents

- `files and folders organizer.py`: Python CLI for renaming and organizing files with OpenAI-assisted classification.
- `doctor-gavrielov/`: Wix/Velo project synced from a Wix site.
- Geospatial and 3D assets: helper scripts, KML/KMZ outputs, CSV tables, and `.dae` model files used for mapping and visualization work.

## Files and folders organizer

Setup:

```bash
./"files and folders organizer - setup.sh"
```

Run from the directory you want to process:

```bash
cd ~/Pictures
python3 "/absolute/path/to/files and folders organizer.py" -r --organize --mnemonically-boosted
```

If you only want moving and not AI renaming:

```bash
python3 "/absolute/path/to/files and folders organizer.py" -r --organize-only
```

## Notes

- The organizer script uses the current working directory as the root it processes.
- The organizer script skips its own project directory to avoid renaming or moving itself.
- Local secrets, caches, virtual environments, and generated scratch directories are ignored by git.
