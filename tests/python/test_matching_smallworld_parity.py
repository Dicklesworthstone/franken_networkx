"""Phase B certification: matching predicates (is_matching /
is_maximal_matching / is_perfect_matching), max/min weight matching,
seeded small-world metrics (sigma/omega), k-edge-connectivity. Zero
divergences.
"""
import importlib
import random

import networkx as nx

import franken_networkx as fnx


def test_smallworld_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.smallworld")
    expected = importlib.import_module("networkx.algorithms.smallworld")

    assert set(module.__all__) == set(expected.__all__)


def test_smallworld_module_routes_through_top_level_fnx(monkeypatch):
    module = importlib.import_module("franken_networkx.smallworld")
    algorithms_module = importlib.import_module("franken_networkx.algorithms.smallworld")
    calls = []
    outputs = {
        name: object()
        for name in ("random_reference", "lattice_reference", "sigma", "omega")
    }

    def sentinel(name):
        def routed(*args, **kwargs):
            calls.append((name, args, kwargs))
            return outputs[name]

        return routed

    for name in ("random_reference", "lattice_reference", "sigma", "omega"):
        monkeypatch.setattr(fnx, name, sentinel(name))

    assert (
        module.random_reference("graph", niter=2, connectivity=False, seed=3)
        is outputs["random_reference"]
    )
    assert (
        algorithms_module.random_reference("graph", niter=2, connectivity=False, seed=3)
        is outputs["random_reference"]
    )
    assert (
        module.lattice_reference("graph", niter=3, D="dist", connectivity=False, seed=4)
        is outputs["lattice_reference"]
    )
    assert (
        algorithms_module.lattice_reference(
            "graph",
            niter=3,
            D="dist",
            connectivity=False,
            seed=4,
        )
        is outputs["lattice_reference"]
    )
    assert module.sigma("graph", niter=4, nrand=2, seed=5) is outputs["sigma"]
    assert (
        algorithms_module.sigma("graph", niter=4, nrand=2, seed=5)
        is outputs["sigma"]
    )
    assert module.omega("graph", niter=5, nrand=3, seed=6) is outputs["omega"]
    assert (
        algorithms_module.omega("graph", niter=5, nrand=3, seed=6)
        is outputs["omega"]
    )

    assert [name for name, _args, _kwargs in calls] == [
        "random_reference",
        "random_reference",
        "lattice_reference",
        "lattice_reference",
        "sigma",
        "sigma",
        "omega",
        "omega",
    ]


def test_smallworld_module_functions_are_not_networkx_versions():
    module = importlib.import_module("franken_networkx.smallworld")
    expected = importlib.import_module("networkx.algorithms.smallworld")

    for name in ("random_reference", "lattice_reference", "sigma", "omega"):
        assert getattr(module, name) is not getattr(expected, name)


def test_smallworld_module_seeded_values_match_networkx():
    module = importlib.import_module("franken_networkx.smallworld")
    algorithms_module = importlib.import_module("franken_networkx.algorithms.smallworld")

    fg = fnx.cycle_graph(10)
    ng = nx.cycle_graph(10)

    fr = module.random_reference(fg, niter=2, seed=7)
    nr = nx.random_reference(ng, niter=2, seed=7)
    assert sorted(fr.edges()) == sorted(nr.edges())

    fl = algorithms_module.lattice_reference(fnx.cycle_graph(10), niter=2, seed=5)
    nl = nx.lattice_reference(nx.cycle_graph(10), niter=2, seed=5)
    assert sorted(fl.edges()) == sorted(nl.edges())

    wf = fnx.connected_watts_strogatz_graph(20, 4, 0.3, seed=1)
    wn = nx.connected_watts_strogatz_graph(20, 4, 0.3, seed=1)
    assert round(module.sigma(wf, niter=2, nrand=2, seed=1), 4) == round(
        nx.sigma(wn, niter=2, nrand=2, seed=1),
        4,
    )
    assert round(algorithms_module.omega(wf, niter=2, nrand=2, seed=1), 4) == round(
        nx.omega(wn, niter=2, nrand=2, seed=1),
        4,
    )


def _mk():
    R = random.Random(97)
    ue = [(u, v) for u, v in ((R.randrange(14), R.randrange(14)) for _ in range(40)) if u != v]
    return fnx.Graph(ue), nx.Graph(ue)


def test_matching_predicates():
    gf, gn = _mk()
    mf, mn = nx.max_weight_matching(gf), nx.max_weight_matching(gn)
    assert {tuple(sorted((repr(a), repr(b)))) for a, b in mf} == {
        tuple(sorted((repr(a), repr(b)))) for a, b in mn
    }
    assert nx.is_matching(gf, mf) == nx.is_matching(gn, mn) is True
    assert nx.is_maximal_matching(gf, mf) == nx.is_maximal_matching(gn, mn)
    assert nx.is_perfect_matching(gf, mf) == nx.is_perfect_matching(gn, mn)
    assert len(nx.maximal_matching(gf)) == len(nx.maximal_matching(gn))


def test_weighted_matching():
    R = random.Random(97)
    ue = [(u, v) for u, v in ((R.randrange(14), R.randrange(14)) for _ in range(40)) if u != v]
    wf, wn = fnx.Graph(), nx.Graph()
    for i, (u, v) in enumerate(ue):
        wf.add_edge(u, v, weight=1 + (i % 9))
        wn.add_edge(u, v, weight=1 + (i % 9))
    assert {tuple(sorted((repr(a), repr(b)))) for a, b in nx.max_weight_matching(wf)} == {
        tuple(sorted((repr(a), repr(b)))) for a, b in nx.max_weight_matching(wn)
    }
    assert len(nx.min_weight_matching(wf)) == len(nx.min_weight_matching(wn))


def test_smallworld_seeded():
    wf = fnx.connected_watts_strogatz_graph(20, 4, 0.3, seed=1)
    wn = nx.connected_watts_strogatz_graph(20, 4, 0.3, seed=1)
    assert round(nx.sigma(wf, niter=2, nrand=2, seed=1), 4) == round(
        nx.sigma(wn, niter=2, nrand=2, seed=1), 4
    )
    assert round(nx.omega(wf, niter=2, nrand=2, seed=1), 4) == round(
        nx.omega(wn, niter=2, nrand=2, seed=1), 4
    )


def test_k_edge_connectivity():
    gf, gn = _mk()
    assert nx.is_k_edge_connected(gf, 2) == nx.is_k_edge_connected(gn, 2)
    assert nx.is_connected(gf) == nx.is_connected(gn)
