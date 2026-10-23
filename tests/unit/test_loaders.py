from pathlib import Path

SAMPLES = Path("samples")


def test_cv_md_loads():
    from jaa.ingest.loaders import detect_media_type, load_lines

    data = (SAMPLES / "alex-doe-cv.md").read_bytes()
    mt = detect_media_type("alex-doe-cv.md", data[:64])
    lines, warnings = load_lines(data, mt)
    assert len(lines) > 5
