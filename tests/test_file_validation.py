import pytest

from backend.app.file_validation import validate_upload_filename


def test_accept_supported_files():
    assert validate_upload_filename("materi.PDF") == ".pdf"
    assert validate_upload_filename("slide.pptx") == ".pptx"
    assert validate_upload_filename("legacy.ppt") == ".ppt"


def test_reject_unsupported_files():
    with pytest.raises(ValueError):
        validate_upload_filename("catatan.txt")
