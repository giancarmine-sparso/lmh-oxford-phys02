from pathlib import Path

import matplotlib.pyplot as plt

from atlas_analysis.plot_style import paper_style, save_figure_variants


def test_paper_style_uses_stix_two_fallback_and_restores_rcparams() -> None:
    original_family = plt.rcParams["font.family"].copy()
    original_usetex = plt.rcParams["text.usetex"]

    with paper_style(use_tex=False):
        assert plt.rcParams["font.family"] == ["serif"]
        assert plt.rcParams["font.serif"][0] == "STIX Two Text"
        assert plt.rcParams["mathtext.fontset"] == "custom"
        assert plt.rcParams["mathtext.rm"] == "STIX Two Text"
        assert plt.rcParams["mathtext.cal"] == "STIX Two Math"
        assert plt.rcParams["text.usetex"] is False
        assert plt.rcParams["savefig.dpi"] == 600

    assert plt.rcParams["font.family"] == original_family
    assert plt.rcParams["text.usetex"] is original_usetex


def test_save_figure_variants_writes_png_and_pdf(tmp_path: Path) -> None:
    output = tmp_path / "paper_plot.png"

    with paper_style(use_tex=False):
        figure, axis = plt.subplots(figsize=(2.0, 1.5))
        axis.plot([0.0, 1.0], [0.0, 1.0])
        png_output, pdf_output = save_figure_variants(figure, output)
        plt.close(figure)

    assert png_output == output
    assert pdf_output == output.with_suffix(".pdf")
    assert png_output.stat().st_size > 0
    assert pdf_output.stat().st_size > 0
