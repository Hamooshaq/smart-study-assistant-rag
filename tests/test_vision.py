from pathlib import Path

from backend.app.vision import ExtractedImage


def test_extracted_image_shape(tmp_path: Path):
    path = tmp_path / "image.png"
    path.write_bytes(b"fake")
    image = ExtractedImage(path=path, source_type="pdf", page_number=1)
    assert image.path.exists()
    assert image.page_number == 1
