"""Parser for Rhythmbox rhythmdb.xml metadata files."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote, urlparse


@dataclass
class Track:
    """Represents a single music track from rhythmdb.xml."""

    location: str
    title: str = ""
    artist: str = ""
    album: str = ""
    album_artist: str = ""
    genre: str = ""
    track_number: int = 0
    disc_number: int = 0
    year: int = 0
    duration: int = 0
    media_type: str = ""

    @property
    def local_path(self) -> Optional[Path]:
        """Return the local filesystem path decoded from the file:// URI."""
        if self.location.startswith("file://"):
            return Path(unquote(urlparse(self.location).path))
        return None

    @property
    def filename(self) -> str:
        """Return just the filename portion of the location."""
        path = self.local_path
        if path:
            return path.name
        return Path(self.location).name


def parse_rhythmdb(xml_path: str | Path) -> List[Track]:
    """Parse a rhythmdb.xml file and return a list of Track objects.

    Only entries of type "song" are returned.

    Args:
        xml_path: Path to the rhythmdb.xml file.

    Returns:
        List of Track dataclass instances.

    Raises:
        FileNotFoundError: If the xml_path does not exist.
        ET.ParseError: If the XML is malformed.
    """
    xml_path = Path(xml_path)
    if not xml_path.exists():
        raise FileNotFoundError(f"rhythmdb.xml not found: {xml_path}")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    tracks: List[Track] = []
    for entry in root.findall("entry"):
        if entry.get("type") != "song":
            continue

        location = _text(entry, "location")
        if not location:
            continue

        track = Track(
            location=location,
            title=_text(entry, "title"),
            artist=_text(entry, "artist"),
            album=_text(entry, "album"),
            album_artist=_text(entry, "album-artist"),
            genre=_text(entry, "genre"),
            track_number=_int(entry, "track-number"),
            disc_number=_int(entry, "disc-number"),
            year=_year(entry),
            duration=_int(entry, "duration"),
            media_type=_text(entry, "media-type"),
        )
        tracks.append(track)

    return tracks


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _text(entry: ET.Element, tag: str) -> str:
    el = entry.find(tag)
    return el.text.strip() if el is not None and el.text else ""


def _int(entry: ET.Element, tag: str) -> int:
    el = entry.find(tag)
    if el is not None and el.text:
        try:
            return int(el.text.strip())
        except ValueError:
            pass
    return 0


def _year(entry: ET.Element) -> int:
    """Rhythmbox stores the year as a Julian date in the <date> tag."""
    julian = _int(entry, "date")
    if julian > 0:
        # The Julian Day Number (JDN) epoch is Nov 24, 4714 BC (proleptic
        # Gregorian).  Python's datetime.date.fromordinal uses ordinal 1 =
        # 0001-01-01, which corresponds to JDN 1721425.  Subtracting that
        # offset converts JDN to a Python ordinal for display purposes.
        try:
            import datetime

            # Python's datetime uses "proleptic Gregorian" with Julian Day
            # Number offset 1721425 for the epoch of fromordinal(1) = 0001-01-01
            ordinal = julian - 1721425
            if ordinal > 0:
                return datetime.date.fromordinal(ordinal).year
        except (ValueError, OverflowError):
            pass
    return 0
