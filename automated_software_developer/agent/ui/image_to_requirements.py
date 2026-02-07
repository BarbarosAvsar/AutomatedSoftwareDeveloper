"""Image-based UI requirements extraction (deterministic placeholder)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ImageRequirementsAddendum:
    """Structured UI hints extracted from an image."""

    summary: str
    screens: tuple[str, ...]
    components: tuple[str, ...]
    questions: tuple[str, ...]


def image_to_requirements(image_path: Path) -> ImageRequirementsAddendum:
    """Extract UI hints from a sketch image in a safe, deterministic way."""
    if not image_path.exists():
        raise ValueError("image_path does not exist.")
    if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("Unsupported image type.")

    name = image_path.stem.lower()
    screens: list[str] = ["Dashboard"]
    components: list[str] = ["Navigation", "Cards", "Buttons"]
    questions: list[str] = [
        "Should the primary CTA be 'Approve & Launch'?",
        "Do you prefer a three-panel layout with live activity on the right?",
    ]
    if "requirements" in name or "spec" in name:
        screens.append("Requirements Studio")
        components.append("Markdown Editor")
    if "metrics" in name or "charts" in name:
        components.append("Charts")
    summary = "UI requirements addendum derived from uploaded sketch."
    return ImageRequirementsAddendum(
        summary=summary,
        screens=tuple(screens),
        components=tuple(components),
        questions=tuple(questions),
    )
