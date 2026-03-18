"""Smoke test: verify the package imports and version is accessible."""


def test_import_version():
    import franken_networkx as fnx
    assert fnx.__version__ == "0.1.0"


def test_multigraph_classes_import():
    import franken_networkx as fnx

    mg = fnx.MultiGraph()
    mdg = fnx.MultiDiGraph()

    assert mg.is_multigraph()
    assert not mg.is_directed()
    assert mdg.is_multigraph()
    assert mdg.is_directed()
