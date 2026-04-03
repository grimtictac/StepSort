"""Tests for stepsort.rhythmdb_parser."""

import textwrap
from pathlib import Path

import pytest

from stepsort.rhythmdb_parser import Track, parse_rhythmdb


SAMPLE_XML = textwrap.dedent("""\
    <?xml version="1.0" standalone="yes"?>
    <rhythmdb version="2.0">
      <entry type="song">
        <title>Test Song</title>
        <artist>Test Artist</artist>
        <album>Test Album</album>
        <album-artist>Test Album Artist</album-artist>
        <genre>Rock</genre>
        <track-number>3</track-number>
        <disc-number>1</disc-number>
        <duration>210</duration>
        <location>file:///music/test_song.mp3</location>
        <media-type>audio/mpeg</media-type>
        <date>736695</date>
      </entry>
      <entry type="song">
        <title>Another Track</title>
        <artist>Another Artist</artist>
        <album>Another Album</album>
        <track-number>1</track-number>
        <duration>180</duration>
        <location>file:///music/another_track.mp3</location>
        <media-type>audio/mpeg</media-type>
      </entry>
      <entry type="radio">
        <title>Radio Station</title>
        <location>http://example.com/stream</location>
      </entry>
    </rhythmdb>
""")


@pytest.fixture
def xml_file(tmp_path: Path) -> Path:
    f = tmp_path / "rhythmdb.xml"
    f.write_text(SAMPLE_XML)
    return f


def test_parse_returns_only_songs(xml_file: Path) -> None:
    tracks = parse_rhythmdb(xml_file)
    assert len(tracks) == 2  # radio entry excluded


def test_parse_track_fields(xml_file: Path) -> None:
    tracks = parse_rhythmdb(xml_file)
    t = tracks[0]
    assert t.title == "Test Song"
    assert t.artist == "Test Artist"
    assert t.album == "Test Album"
    assert t.album_artist == "Test Album Artist"
    assert t.genre == "Rock"
    assert t.track_number == 3
    assert t.disc_number == 1
    assert t.duration == 210
    assert t.media_type == "audio/mpeg"
    assert t.location == "file:///music/test_song.mp3"


def test_parse_track_local_path(xml_file: Path) -> None:
    tracks = parse_rhythmdb(xml_file)
    assert tracks[0].local_path == Path("/music/test_song.mp3")


def test_parse_track_filename(xml_file: Path) -> None:
    tracks = parse_rhythmdb(xml_file)
    assert tracks[0].filename == "test_song.mp3"


def test_parse_missing_optional_fields(xml_file: Path) -> None:
    tracks = parse_rhythmdb(xml_file)
    t = tracks[1]
    assert t.album_artist == ""
    assert t.genre == ""
    assert t.year == 0


def test_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        parse_rhythmdb("/nonexistent/rhythmdb.xml")


def test_malformed_xml(tmp_path: Path) -> None:
    import xml.etree.ElementTree as ET
    bad = tmp_path / "bad.xml"
    bad.write_text("<not closed")
    with pytest.raises(ET.ParseError):
        parse_rhythmdb(bad)
