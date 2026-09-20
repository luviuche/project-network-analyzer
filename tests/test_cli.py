"""
Tests for cli.py — the parts worth pinning down without running the
whole pipeline.

Where the CLI looks for `data/` and writes `outputs/` is one of them: it
differs between a source checkout and an installed wheel, and getting it
wrong means the installed command looks for the sample network inside
site-packages.
"""

from pathlib import Path

from project_network_analyzer.cli import _project_root

ROOT = Path(__file__).resolve().parents[1]


def test_project_root_is_the_repo_in_a_source_checkout():
    assert _project_root() == ROOT
    assert (_project_root() / "data" / "proyecto_software.json").is_file()


def test_project_root_falls_back_to_the_working_directory(tmp_path, monkeypatch):
    """
    Installed as a wheel, the path two levels up from cli.py lands in
    site-packages and holds no `data/`. The CLI must then work relative
    to wherever it was invoked.
    """
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    workdir = tmp_path / "workdir"
    (workdir / "data").mkdir(parents=True)
    monkeypatch.chdir(workdir)

    assert _project_root(site_packages) == workdir


def test_project_root_prefers_the_candidate_when_it_has_data(tmp_path, monkeypatch):
    checkout = tmp_path / "checkout"
    (checkout / "data").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    assert _project_root(checkout) == checkout
