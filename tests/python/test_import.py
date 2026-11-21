"""Smoke test: verify the package imports and version is accessible."""

import re


def test_import_version():
    import franken_networkx as fnx

    assert isinstance(fnx.__version__, str)
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[.-][0-9A-Za-z.]+)?", fnx.__version__)


def test_multigraph_classes_import():
    import franken_networkx as fnx

    mg = fnx.MultiGraph()
    mdg = fnx.MultiDiGraph()

    assert mg.is_multigraph()
    assert not mg.is_directed()
    assert mdg.is_multigraph()
    assert mdg.is_directed()
