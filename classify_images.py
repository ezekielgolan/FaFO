#!/usr/bin/env python3
"""
Classify images into bins and suggest descriptive filenames.

Bins:
  - software_screenshot
  - document
  - realistic (photo or photorealistic rendering)
  - cartoon_diagram
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional

from PIL import Image


IMAGE_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}
DOC_EXTS = {".pdf"}


@dataclass
class Suggestion:
    path: str
    bin: str
    top_label: str
    top_score: float
    caption: str
    ocr_snippet: str
    suggested_name: str


def slugify(text: str, max_len: int = 120) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    text = re.sub(r"-{2,}", "-", text)
    if len(text) > max_len:
        text = text[:max_len].rstrip("-")
    return text or "untitled"


def iter_files(root: Path, recursive: bool) -> Iterable[Path]:
    if recursive:
        yield from (p for p in root.rglob("*") if p.is_file())
    else:
        yield from (p for p in root.iterdir() if p.is_file())


def load_image(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def load_pdf_first_page(path: Path) -> Image.Image:
    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "PyMuPDF is required for PDFs. Install with `pip install pymupdf`."
        ) from exc

    doc = fitz.open(str(path))
    if len(doc) == 0:
        raise RuntimeError("Empty PDF")
    page = doc.load_page(0)
    pix = page.get_pixmap(dpi=200)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img


def build_models(device: int):
    from transformers import pipeline

    classifier = pipeline(
        "zero-shot-image-classification",
        model="openai/clip-vit-large-patch14",
        device=device,
    )
    captioner = pipeline(
        "image-to-text",
        model="Salesforce/blip-image-captioning-large",
        device=device,
    )
    return classifier, captioner


def get_ocr_snippet(img: Image.Image, max_words: int = 12) -> str:
    try:
        import easyocr  # type: ignore
    except Exception:
        return ""

    reader = easyocr.Reader(["en"], gpu=False)
    results = reader.readtext(
        image=np_image(img),
        detail=0,
        paragraph=False,
    )
    words = [w.strip() for w in results if w.strip()]
    return " ".join(words[:max_words])


def np_image(img: Image.Image):
    try:
        import numpy as np
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError("numpy is required. Install with `pip install numpy`.") from exc
    return np.array(img)


def classify_image(
    img: Image.Image,
    classifier,
    captioner,
    ocr_snippet: str,
) -> tuple[str, str, float, str]:
    candidate_labels = [
        "software screenshot",
        "scanned document",
        "document",
        "photo of a real scene",
        "photorealistic rendering",
        "cartoon illustration",
        "diagram",
        "schematic",
        "infographic",
    ]
    results = classifier(img, candidate_labels=candidate_labels)
    top = results[0]
    top_label = top["label"]
    top_score = float(top["score"])

    label_to_bin = {
        "software screenshot": "software_screenshot",
        "scanned document": "document",
        "document": "document",
        "photo of a real scene": "realistic",
        "photorealistic rendering": "realistic",
        "cartoon illustration": "cartoon_diagram",
        "diagram": "cartoon_diagram",
        "schematic": "cartoon_diagram",
        "infographic": "cartoon_diagram",
    }
    bin_name = label_to_bin.get(top_label, "realistic")

    caption = captioner(img)[0]["generated_text"].strip()

    # If OCR suggests lots of text, bias towards document/screenshot.
    if ocr_snippet and bin_name == "realistic":
        if len(ocr_snippet.split()) >= 6:
            bin_name = "document"

    return bin_name, top_label, top_score, caption


def build_suggestion(
    path: Path,
    bin_name: str,
    caption: str,
    ocr_snippet: str,
) -> str:
    if bin_name == "software_screenshot":
        detail = "software screenshot"
        if ocr_snippet:
            detail += f" showing {ocr_snippet}"
    elif bin_name == "document":
        detail = "document"
        if path.suffix.lower() == ".pdf":
            detail += " pdf"
        if ocr_snippet:
            detail += f" {ocr_snippet}"
    elif bin_name == "cartoon_diagram":
        detail = f"diagram {caption}"
    else:
        detail = f"photo {caption}"

    detail = re.sub(r"\s+", " ", detail).strip()
    return f"{slugify(detail)}{path.suffix.lower()}"


def write_output(
    suggestions: list[Suggestion],
    output_path: Path,
    fmt: str,
):
    if fmt == "jsonl":
        with output_path.open("w", encoding="utf-8") as f:
            for s in suggestions:
                f.write(json.dumps(asdict(s), ensure_ascii=True) + "\n")
    else:
        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "path",
                    "bin",
                    "top_label",
                    "top_score",
                    "caption",
                    "ocr_snippet",
                    "suggested_name",
                ],
            )
            writer.writeheader()
            for s in suggestions:
                writer.writerow(asdict(s))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classify images into bins and suggest descriptive filenames."
    )
    parser.add_argument("directory", type=Path, help="Directory to scan")
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Scan nested folders",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("suggestions.jsonl"),
        help="Output file (jsonl or csv)",
    )
    parser.add_argument(
        "--format",
        choices=["jsonl", "csv"],
        default="jsonl",
        help="Output format",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=-1,
        help="Device for inference (-1=CPU, 0=GPU)",
    )
    args = parser.parse_args()

    if not args.directory.exists():
        print(f"Directory not found: {args.directory}", file=sys.stderr)
        return 2

    classifier, captioner = build_models(args.device)

    suggestions: list[Suggestion] = []
    for path in iter_files(args.directory, args.recursive):
        ext = path.suffix.lower()
        if ext not in IMAGE_EXTS and ext not in DOC_EXTS:
            continue

        try:
            if ext in DOC_EXTS:
                img = load_pdf_first_page(path)
            else:
                img = load_image(path)
        except Exception as exc:
            print(f"Skipping {path}: {exc}", file=sys.stderr)
            continue

        ocr_snippet = ""
        try:
            ocr_snippet = get_ocr_snippet(img)
        except Exception:
            ocr_snippet = ""

        bin_name, top_label, top_score, caption = classify_image(
            img,
            classifier,
            captioner,
            ocr_snippet,
        )
        suggested_name = build_suggestion(path, bin_name, caption, ocr_snippet)

        suggestions.append(
            Suggestion(
                path=str(path),
                bin=bin_name,
                top_label=top_label,
                top_score=top_score,
                caption=caption,
                ocr_snippet=ocr_snippet,
                suggested_name=suggested_name,
            )
        )

    write_output(suggestions, args.output, args.format)
    print(f"Wrote {len(suggestions)} suggestions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
