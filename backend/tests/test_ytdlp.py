from app.downloader.ytdlp import _expected_bytes


def test_expected_bytes_sums_requested_formats():
    raw = {
        "requested_formats": [
            {"filesize": 1000, "filesize_approx": None},
            {"filesize": None, "filesize_approx": 500},
        ]
    }
    assert _expected_bytes(raw) == 1500


def test_expected_bytes_falls_back_to_requested_downloads():
    raw = {"requested_downloads": [{"filesize": None, "filesize_approx": 2048}]}
    assert _expected_bytes(raw) == 2048


def test_expected_bytes_falls_back_to_top_level():
    assert _expected_bytes({"filesize_approx": 42}) == 42


def test_expected_bytes_unknown_or_partial():
    assert _expected_bytes({}) is None
    assert _expected_bytes(None) is None
    assert _expected_bytes({"requested_formats": [{"filesize": 1000}, {}]}) is None
