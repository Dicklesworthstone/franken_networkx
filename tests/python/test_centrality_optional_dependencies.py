"""Optional matrix accelerators must not become centrality requirements."""

import builtins

import networkx as nx
import pytest

import franken_networkx as fnx


CASES = [
    ("eigenvector_centrality", {"weight": "weight"}),
    ("eigenvector_centrality", {"nstart": {0: 1, 1: 2, 2: 1}}),
    ("eigenvector_centrality", {"weight": "weight", "tol": 1e-9}),
    ("katz_centrality", {"weight": "weight", "alpha": 0.05}),
    ("katz_centrality", {"beta": {0: 1, 1: 2, 2: 1}}),
    ("katz_centrality", {"nstart": {0: 1, 1: 2, 2: 1}, "normalized": False}),
]


def _graph_pair(graph_type):
    reference = getattr(nx, graph_type)()
    actual = getattr(fnx, graph_type)()
    for graph in (reference, actual):
        graph.add_weighted_edges_from([(0, 1, 2), (1, 2, 3), (2, 0, 1)])
    return reference, actual


def _block_import(monkeypatch, missing):
    original_import = builtins.__import__
    attempts = []

    def import_without_optional_module(name, *args, **kwargs):
        if name == missing or name.startswith(missing + "."):
            attempts.append(name)
            raise ModuleNotFoundError(
                f"No module named '{missing}'", name=missing
            )
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_optional_module)
    return attempts


@pytest.mark.parametrize("missing", ["numpy", "scipy"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize(("algorithm", "kwargs"), CASES)
def test_nondefault_centrality_works_without_optional_accelerator(
    monkeypatch, missing, graph_type, algorithm, kwargs
):
    reference, actual = _graph_pair(graph_type)
    expected = getattr(nx, algorithm)(reference, **kwargs)
    attempts = _block_import(monkeypatch, missing)
    result = getattr(fnx, algorithm)(actual, **kwargs)
    assert result == pytest.approx(expected, rel=1e-12, abs=1e-12)
    assert attempts


@pytest.mark.parametrize("missing", ["numpy", "scipy"])
@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
def test_fallback_preserves_convergence_failure(monkeypatch, missing, algorithm):
    reference, actual = _graph_pair("DiGraph")
    kwargs = {"weight": "weight", "max_iter": 1, "tol": 1e-30}
    with pytest.raises(nx.PowerIterationFailedConvergence):
        getattr(nx, algorithm)(reference, **kwargs)
    _block_import(monkeypatch, missing)
    with pytest.raises(fnx.PowerIterationFailedConvergence):
        getattr(fnx, algorithm)(actual, **kwargs)


@pytest.mark.parametrize("missing", ["numpy", "scipy"])
def test_fallback_preserves_invalid_start_error(monkeypatch, missing):
    _, actual = _graph_pair("Graph")
    _block_import(monkeypatch, missing)
    with pytest.raises(fnx.NetworkXError, match="all zero"):
        fnx.eigenvector_centrality(actual, nstart={0: 0, 1: 0, 2: 0})


@pytest.mark.parametrize("missing", ["numpy", "scipy"])
def test_fallback_preserves_incomplete_beta_error(monkeypatch, missing):
    _, actual = _graph_pair("Graph")
    _block_import(monkeypatch, missing)
    with pytest.raises(fnx.NetworkXError, match="beta"):
        fnx.katz_centrality(actual, beta={0: 1})


def test_default_native_centrality_does_not_need_matrix_imports(monkeypatch):
    reference, actual = _graph_pair("Graph")
    expected_eigenvector = nx.eigenvector_centrality(reference)
    expected_katz = nx.katz_centrality(reference)
    attempts = _block_import(monkeypatch, "numpy")
    assert fnx.eigenvector_centrality(actual) == pytest.approx(expected_eigenvector)
    assert fnx.katz_centrality(actual) == pytest.approx(expected_katz)
    assert attempts == []
