from onyx_pipeline.ids import doc_id_from_hash, hash_bytes_tagged
import pytest


def test_doc_id_from_hash_valid():
    h = hash_bytes_tagged(b"abc")
    doc_id = doc_id_from_hash(h)
    assert len(doc_id) == 64
    assert doc_id in h


def test_doc_id_from_hash_invalid():
    with pytest.raises(ValueError):
        doc_id_from_hash("not-a-hash")
