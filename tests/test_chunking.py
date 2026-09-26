from backend.app.chunking import chunk_sections, estimate_token_count, recursive_split_text
from backend.app.extraction import ExtractedSection


def test_recursive_split_respects_target_size():
    text = " ".join(f"kata{i}" for i in range(1300))
    chunks = recursive_split_text(text, chunk_size=500, overlap=75)
    assert len(chunks) >= 3
    assert all(estimate_token_count(chunk) <= 500 for chunk in chunks)


def test_ppt_slide_metadata_is_preserved():
    chunks = chunk_sections([ExtractedSection("materi slide", "ppt", slide_number=1)])
    assert chunks[0].source_label == "Slide 1"


def test_visual_chunk_is_marked():
    chunks = chunk_sections([ExtractedSection("diagram alur", "pdf", page_number=2, is_visual=True)])
    assert chunks[0].is_visual
    assert chunks[0].source_label == "Halaman 2 (visual)"
