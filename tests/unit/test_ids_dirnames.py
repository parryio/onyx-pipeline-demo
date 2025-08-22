from onyx_pipeline.ids import doc_dirname_from_path


def test_doc_dirname_from_path_basic():
    assert doc_dirname_from_path("file.pdf") == "file"
    assert doc_dirname_from_path("weird name!!.txt").startswith("weird_name")


def test_doc_dirname_empty():
    # path like '.hidden'
    dn = doc_dirname_from_path(".hidden")
    assert dn  # non-empty
