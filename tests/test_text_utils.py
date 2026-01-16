from src.tools.text_utils import split_sentences


def test_split_sentences_abbrev():
    text = "We follow prior work, e.g., Smith et al. 2020. Results are strong."
    sents = [s[0] for s in split_sentences(text)]
    assert len(sents) == 2
    assert sents[0].endswith("2020.")


def test_split_sentences_latex():
    text = "See Fig. 1 for details. We propose \\textbf{method}."
    sents = [s[0] for s in split_sentences(text)]
    assert len(sents) == 2
