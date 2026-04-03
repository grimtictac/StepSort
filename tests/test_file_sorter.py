"""Tests for stepsort.file_sorter."""

from pathlib import Path

import pytest

from stepsort.file_sorter import SortPlan, build_sort_plan, execute_sort_plan
from stepsort.rhythmdb_parser import Track


def _make_track(
    filename: str,
    title: str = "Song",
    artist: str = "Artist",
    album: str = "Album",
    track_number: int = 1,
    album_artist: str = "",
) -> Track:
    return Track(
        location=f"file:///source/{filename}",
        title=title,
        artist=artist,
        album=album,
        album_artist=album_artist,
        track_number=track_number,
    )


@pytest.fixture
def source_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "source"
    folder.mkdir()
    return folder


@pytest.fixture
def target_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "target"
    folder.mkdir()
    return folder


def test_build_plan_matches_existing_files(source_folder: Path, target_folder: Path) -> None:
    (source_folder / "song.mp3").write_bytes(b"fake mp3")
    track = _make_track("song.mp3", title="Song", artist="Artist", album="Album", track_number=5)
    plan = build_sort_plan([track], source_folder, target_folder)
    assert len(plan) == 1
    assert plan[0].source == source_folder / "song.mp3"


def test_build_plan_excludes_missing_files(source_folder: Path, target_folder: Path) -> None:
    track = _make_track("missing.mp3")
    plan = build_sort_plan([track], source_folder, target_folder)
    assert len(plan) == 0


def test_destination_structure(source_folder: Path, target_folder: Path) -> None:
    (source_folder / "song.mp3").write_bytes(b"fake mp3")
    track = _make_track("song.mp3", title="My Song", artist="My Artist", album="My Album", track_number=3)
    plan = build_sort_plan([track], source_folder, target_folder)
    dest = plan[0].destination
    assert dest == target_folder / "My Artist" / "My Album" / "03 - My Song.mp3"


def test_destination_uses_album_artist(source_folder: Path, target_folder: Path) -> None:
    (source_folder / "song.mp3").write_bytes(b"fake mp3")
    track = _make_track(
        "song.mp3", artist="Track Artist", album_artist="Album Artist", album="VA Album", track_number=1
    )
    plan = build_sort_plan([track], source_folder, target_folder)
    assert plan[0].destination.parts[-3] == "Album Artist"


def test_destination_no_track_number(source_folder: Path, target_folder: Path) -> None:
    (source_folder / "song.mp3").write_bytes(b"fake mp3")
    track = _make_track("song.mp3", title="Untitled", track_number=0)
    plan = build_sort_plan([track], source_folder, target_folder)
    assert plan[0].destination.name == "Untitled.mp3"


def test_execute_sort_plan_copies_files(source_folder: Path, target_folder: Path) -> None:
    (source_folder / "song.mp3").write_bytes(b"audio data")
    track = _make_track("song.mp3", title="Song", artist="Artist", album="Album", track_number=1)
    plan = build_sort_plan([track], source_folder, target_folder)
    results = execute_sort_plan(plan, copy=True)
    assert len(results) == 1
    item, err = results[0]
    assert err is None
    assert item.destination.exists()
    # Original still exists (copy mode)
    assert (source_folder / "song.mp3").exists()


def test_execute_sort_plan_moves_files(source_folder: Path, target_folder: Path) -> None:
    (source_folder / "song.mp3").write_bytes(b"audio data")
    track = _make_track("song.mp3", title="Song", artist="Artist", album="Album", track_number=1)
    plan = build_sort_plan([track], source_folder, target_folder)
    results = execute_sort_plan(plan, copy=False)
    item, err = results[0]
    assert err is None
    assert item.destination.exists()
    # Original gone (move mode)
    assert not (source_folder / "song.mp3").exists()


def test_collision_avoidance(source_folder: Path, target_folder: Path) -> None:
    (source_folder / "a.mp3").write_bytes(b"a")
    (source_folder / "b.mp3").write_bytes(b"b")
    # Two tracks with identical artist/album/title/track_number -> different destinations
    t1 = Track(location=f"file://{source_folder}/a.mp3", title="Song", artist="A", album="B", track_number=1)
    t2 = Track(location=f"file://{source_folder}/b.mp3", title="Song", artist="A", album="B", track_number=1)
    plan = build_sort_plan([t1, t2], source_folder, target_folder)
    assert len(plan) == 2
    assert plan[0].destination != plan[1].destination


def test_sanitize_unsafe_chars(source_folder: Path, target_folder: Path) -> None:
    (source_folder / "song.mp3").write_bytes(b"data")
    track = _make_track("song.mp3", title='Song: "Title"', artist="Artist/Band", album="Album?")
    plan = build_sort_plan([track], source_folder, target_folder)
    dest = plan[0].destination
    # No unsafe characters in path components
    for part in dest.parts[len(target_folder.parts):]:
        assert "/" not in part
        assert ":" not in part
        assert '"' not in part
        assert "?" not in part


def test_progress_callback(source_folder: Path, target_folder: Path) -> None:
    (source_folder / "song.mp3").write_bytes(b"data")
    track = _make_track("song.mp3", title="Song", artist="Artist", album="Album", track_number=1)
    plan = build_sort_plan([track], source_folder, target_folder)
    calls = []
    execute_sort_plan(plan, progress_callback=lambda cur, tot, dest: calls.append((cur, tot)), copy=True)
    assert calls == [(1, 1)]
