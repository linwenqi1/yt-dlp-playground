from __future__ import annotations

from pathlib import Path

from app.storage import files


def test_display_filename_sanitizes_unsafe_characters() -> None:
    assert files.display_filename("A/B:C*D?", ".mp4") == "A_B_C_D_.mp4"
    assert files.display_filename("  hello   world  ", ".webm") == "hello world.webm"


def test_display_filename_fallbacks_and_truncation() -> None:
    assert files.display_filename("", ".mp3") == "video.mp3"
    assert files.display_filename(None, ".mp3") == "video.mp3"
    long_name = files.display_filename("x" * 300, ".mp4")
    assert len(long_name) == 124
    assert long_name.endswith(".mp4")


def test_find_output_ignores_partial_files(tmp_path: Path) -> None:
    (tmp_path / "media.mp4.part").write_bytes(b"x" * 100)
    (tmp_path / "media.mp4.ytdl").write_bytes(b"x")
    assert files.find_output(tmp_path) is None

    small = tmp_path / "media.mp4"
    small.write_bytes(b"a" * 10)
    large = tmp_path / "media.mkv"
    large.write_bytes(b"b" * 50)
    assert files.find_output(tmp_path) == large


def test_content_type_mapping() -> None:
    assert files.content_type_for(Path("x.mp4")) == "video/mp4"
    assert files.content_type_for(Path("x.webm")) == "video/webm"
    assert files.content_type_for(Path("x.mp3")) == "audio/mpeg"
    assert files.content_type_for(Path("x.unknown")) == "application/octet-stream"


def test_cleanup_orphans(tmp_path: Path) -> None:
    jobs_dir = tmp_path / "jobs"
    (jobs_dir / "known").mkdir(parents=True)
    (jobs_dir / "orphan").mkdir()
    (jobs_dir / "loose-file").write_text("x")

    removed = files.cleanup_orphans(jobs_dir, {"known"})
    assert removed == 1
    assert (jobs_dir / "known").exists()
    assert not (jobs_dir / "orphan").exists()
    assert (jobs_dir / "loose-file").exists()


def test_prepare_and_remove_job_dir(tmp_path: Path) -> None:
    directory = tmp_path / "job"
    files.prepare_job_dir(directory)
    assert (directory / ".tmp").is_dir()
    files.remove_job_dir(directory)
    assert not directory.exists()
