import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "pipeline_cache_report", Path(__file__).parent.parent / "scripts" / "pipeline_cache_report.py"
)
rep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rep)


def test_detect_hit():
    assert rep.detect_cache_status("Checking cache for pip-1\nSuccessfully extracted cache") == "HIT"


def test_detect_miss():
    assert rep.detect_cache_status("Checking cache for pip-1\nNo URL provided, cache will not be downloaded") == "MISS"
    assert rep.detect_cache_status("Checking cache for pip-1\nFailed to extract cache") == "MISS"


def test_detect_none():
    assert rep.detect_cache_status("nur ein normales Log") == "NONE"


def test_summarize_means_by_status():
    rows = [
        {"job": "test:pytest", "cache": "MISS", "duration": 60},
        {"job": "test:pytest", "cache": "MISS", "duration": 80},
        {"job": "test:pytest", "cache": "HIT", "duration": 20},
        {"job": "test:pytest", "cache": "NONE", "duration": 5},
    ]
    assert rep.summarize(rows) == {"test:pytest": {"MISS": 70.0, "HIT": 20.0}}
