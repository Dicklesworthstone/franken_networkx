"""Parity for algebraic_connectivity on directed graphs.

Bead br-r37-c1-d8qdy. ``fnx.algebraic_connectivity`` silently
computed a Fiedler value on directed graphs; nx is
``@not_implemented_for('directed')`` and raises
NetworkXNotImplemented.

Repro:
    >>> g = fnx.DiGraph([(1, 2), (2, 1)])
    >>> fnx.algebraic_connectivity(g)
    2.0
    >>> nx.algebraic_connectivity(nx.DiGraph([(1, 2), (2, 1)]))
    NetworkXNotImplemented: not implemented for directed type

Sister functions ``fiedler_vector`` (already raised on directed)
and ``spectral_ordering`` (correctly accepts both per nx's contract)
were already correct — only ``algebraic_connectivity`` was the
remaining outlier.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_algebraic_connectivity_rejects_directed(cls_name):
    G = getattr(fnx, cls_name)([(1, 2), (2, 1)])
    GX = getattr(nx, cls_name)([(1, 2), (2, 1)])
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"not implemented for directed type",
    ):
        fnx.algebraic_connectivity(G)
    with pytest.raises(
        nx.NetworkXNotImplemented,
        match=r"not implemented for directed type",
    ):
        nx.algebraic_connectivity(GX)


@needs_nx
def test_algebraic_connectivity_directed_caught_by_nx_class():
    """Drop-in: fnx-raised NetworkXNotImplemented must be catchable
    via ``except nx.NetworkXNotImplemented``."""
    G = fnx.DiGraph([(1, 2)])
    try:
        fnx.algebraic_connectivity(G)
    except nx.NetworkXNotImplemented:
        return
    pytest.fail(
        "fnx.algebraic_connectivity should raise NetworkXNotImplemented on directed input"
    )


@needs_nx
def test_algebraic_connectivity_undirected_unchanged():
    """Regression guard — undirected inputs must continue to compute
    the algebraic connectivity (Fiedler value)."""
    G = fnx.path_graph(4)
    GX = nx.path_graph(4)
    assert abs(fnx.algebraic_connectivity(G) - nx.algebraic_connectivity(GX)) < 1e-9


@needs_nx
def test_algebraic_connectivity_empty_still_raises_less_than_two_nodes():
    """Pre-existing parity (br-r37-c1-pb97z) preserved: empty/null
    graph raises NetworkXError. The new directed guard fires before
    the size check, but ``fnx.Graph()`` is undirected so the size
    check still applies."""
    with pytest.raises(fnx.NetworkXError, match=r"less than two nodes"):
        fnx.algebraic_connectivity(fnx.Graph())
    with pytest.raises(nx.NetworkXError, match=r"less than two nodes"):
        nx.algebraic_connectivity(nx.Graph())


@needs_nx
def test_algebraic_connectivity_normalized_directed_also_rejects():
    """The normalized=True path must also raise on directed input;
    the type check fires before the dispatch into the normalized
    Laplacian solver."""
    G = fnx.DiGraph([(1, 2), (2, 1)])
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"not implemented for directed type",
    ):
        fnx.algebraic_connectivity(G, normalized=True)


def _spectral_outcome(lib, name, directed, seed):
    graph =(lib.DiGraph if directed else lib.Graph)([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])
    try:
        result = getattr(lib, name)(graph, seed=seed)
    except Exception as exc:  # noqa: BLE001 - the exception is the outcome
        return ("raise", type(exc).__name__, str(exc).replace(hex(id(seed)), "ID"))
    return ("ok", type(result).__name__, type(result[0]).__name__ if isinstance(result, tuple) else None)


# br-r37-c1-cdf1v: networkx's @np_random_state(5) rejects a seed numpy cannot
# take - a random.Random, a float, a str, an int outside [0, 2**32) - and its
# flattened argmap resolves the seed BEFORE @not_implemented_for("directed").
# fnx's dense solver draws nothing and dropped the seed unchecked, so every one
# of these answered. spectral_bisection also returned frozensets for
# networkx's two sets.
@needs_nx
@pytest.mark.parametrize("directed", [False, True], ids=["undirected", "directed"])
@pytest.mark.parametrize(
    "seed",
    ["random.Random", 1.5, "x", -1, 2**40, 7, None],
    ids=["random.Random", "float", "str", "negative", "2**40", "int", "None"],
)
@pytest.mark.parametrize("name", ["algebraic_connectivity", "fiedler_vector", "spectral_bisection"])
def test_spectral_seed_is_checked_first_as_networkx_does(name, seed, directed):
    import random

    fnx_seed = random.Random(3) if seed == "random.Random" else seed
    nx_seed = random.Random(3) if seed == "random.Random" else seed
    # the message embeds the random.Random's repr - its address becomes "ID"
    assert _spectral_outcome(fnx, name, directed, fnx_seed) == _spectral_outcome(
        nx, name, directed, nx_seed
    )
