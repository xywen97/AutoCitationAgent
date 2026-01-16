from src.tools.latex_utils import append_cite, insert_cite_at_sentence_end


def test_insert_cite_before_punct():
    s = "This is a claim."
    out = insert_cite_at_sentence_end(s, ["Key1"])
    assert out == "This is a claim \\cite{Key1}."


def test_append_existing_cite():
    s = "Prior work \\cite{A,B} shows this."
    out = append_cite(s, ["B", "C"])
    assert "\\cite{A,B,C}" in out
