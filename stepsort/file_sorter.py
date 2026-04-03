"""File sorting logic: copies MP3s from a source folder to a target folder
organised as  <Artist>/<Album>/<track_number> - <Title>.mp3
based on metadata from a parsed rhythmdb.xml.
"""

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from stepsort.rhythmdb_parser import Track


@dataclass
class SortPlan:
    """Represents a single planned file operation."""

    source: Path
    destination: Path
    track: Track

    @property
    def destination_relative(self) -> str:
        """Return the destination path as a string (absolute path to target)."""
        return str(self.destination)


def build_sort_plan(
    tracks: List[Track],
    source_folder: str | Path,
    target_folder: str | Path,
) -> List[SortPlan]:
    """Build a list of SortPlan objects mapping source files to destinations.

    Only tracks whose local path exists inside *source_folder* are included.

    Args:
        tracks: List of Track objects from rhythmdb_parser.
        source_folder: Directory containing unsorted MP3 files.
        target_folder: Root directory for sorted output.

    Returns:
        List of SortPlan objects (no files are copied yet).
    """
    source_folder = Path(source_folder).resolve()
    target_folder = Path(target_folder).resolve()

    plan: List[SortPlan] = []
    seen_destinations: set[Path] = set()

    for track in tracks:
        local = track.local_path
        if local is None:
            # Try treating the location as a bare filename inside source_folder
            local = source_folder / track.filename

        # Resolve the candidate source path
        candidate = local if local.is_absolute() else source_folder / local
        # Also try looking up only the filename inside source_folder
        if not candidate.exists():
            candidate = source_folder / local.name
        if not candidate.exists():
            continue

        dest = _build_destination(track, target_folder, seen_destinations)
        seen_destinations.add(dest)
        plan.append(SortPlan(source=candidate, destination=dest, track=track))

    return plan


def execute_sort_plan(
    plan: List[SortPlan],
    progress_callback: Optional[Callable[[int, int, Path], None]] = None,
    copy: bool = True,
) -> List[Tuple[SortPlan, Optional[Exception]]]:
    """Execute a sort plan by copying (or moving) files.

    Args:
        plan: List of SortPlan objects to execute.
        progress_callback: Optional callable(current, total, destination)
            invoked after each file operation.
        copy: If True (default) files are copied; if False they are moved.

    Returns:
        List of (SortPlan, error_or_None) tuples.
    """
    results: List[Tuple[SortPlan, Optional[Exception]]] = []
    total = len(plan)

    for idx, item in enumerate(plan, start=1):
        error: Optional[Exception] = None
        try:
            item.destination.parent.mkdir(parents=True, exist_ok=True)
            if copy:
                shutil.copy2(str(item.source), str(item.destination))
            else:
                shutil.move(str(item.source), str(item.destination))
        except Exception as exc:  # noqa: BLE001
            error = exc

        results.append((item, error))

        if progress_callback:
            progress_callback(idx, total, item.destination)

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize(name: str, replacement: str = "_") -> str:
    """Replace filesystem-unsafe characters in a path component."""
    sanitized = _UNSAFE_CHARS.sub(replacement, name).strip(". ")
    return sanitized or "Unknown"


def _build_destination(
    track: Track, target_folder: Path, seen: set
) -> Path:
    """Construct the destination path for a track inside target_folder."""
    artist = _sanitize(track.album_artist or track.artist or "Unknown Artist")
    album = _sanitize(track.album or "Unknown Album")

    # Build filename: "01 - Title.ext" or just "Title.ext"
    source_suffix = Path(track.filename).suffix.lower() or ".mp3"
    title = _sanitize(track.title or Path(track.filename).stem or "Unknown Title")

    if track.track_number > 0:
        filename = f"{track.track_number:02d} - {title}{source_suffix}"
    else:
        filename = f"{title}{source_suffix}"

    dest = target_folder / artist / album / filename

    # Avoid collisions: append a counter suffix if needed
    if dest in seen:
        stem = dest.stem
        suffix = dest.suffix
        counter = 2
        while dest in seen:
            dest = dest.parent / f"{stem} ({counter}){suffix}"
            counter += 1

    return dest
