"""The branching family converts STRUCTURALLY, and only where that is sound.

Since sfq4w.4, ``maximum_branching`` (and through it the rest of the family) runs
networkx's Edmonds natively and matches networkx's result exactly, edge order included
(the tests at the end of this file). What follows describes the networkx delegation it
still falls back to for weights the native plan does not cover.

br-r37-c1-p80x1.14. ``maximum_branching`` delegates to networkx for every class
(br-r37-c1-kb9hm: the native Edmonds kernel does not reproduce nx's incoming-edge
iteration order through tie-rich cycle contractions), and ``minimum_branching`` delegates
for the undirected class. That delegation stays. What was waste is the FAITHFUL conversion
feeding it: networkx's output carries only the ``attr`` weight - node attributes, graph
attributes and other edge attributes are all dropped - so copying them in was overhead the
result discards.

    maximum_branching  DiGraph   432.1M -> 417.3M Ir/call   0.876x -> 0.908x
    maximum_branching  Graph     215.3M -> 194.0M Ir/call   0.766x -> 0.849x
    minimum_branching  Graph     220.0M -> 195.6M Ir/call   0.777x -> 0.874x

ALL THREE ROWS REMAIN LOSSES. The residue is networkx's own implementation plus the
conversion back; closing them needs a native path with a tie-break proof corpus, which is
what br-r37-c1-kb9hm asked for and did not get.

THE SCOPE CLAUSES ARE THE POINT OF THIS FILE. Each was verified against networkx rather
than assumed, and each would silently corrupt results if dropped:

  * ``preserve_attrs=True`` DOES retain extra edge attributes in nx's output, so the
    structural copy must not be used there;
  * a MULTIGRAPH would lose its parallel edges to a simple copy;
  * ``partition`` routes through ``_branching_partition_graph_for_networkx``, a different
    input entirely;
  * ``attr`` must be carried through, not hardcoded to ``"weight"`` - ``attr="cost"`` is
    legal;
  * the ``default`` must NOT be materialised onto the copy. Writing ``d.get(attr, default)``
    makes networkx see explicit weights where it would otherwise apply its own default, and
    that changed the selected branching on attribute-free graphs.

A NOTE FOR ANYONE SWEEPING THIS FAMILY: networkx MUTATES its input here, materialising
``default`` onto the caller's edges as a side effect; fnx does not. A sweep that reuses one
graph across parameter values will therefore compare a mutated nx graph against an
unmutated fnx one and report divergences that are artefacts of the harness. Build a fresh
graph per case.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _outcome(fn):
    try:
        graph = fn()
    except Exception as exc:  # noqa: BLE001 - the exception IS the observation
        return ("raise", type(exc).__name__, tuple(str(a) for a in exc.args))
    return (
        "ok",
        sorted(map(str, graph.nodes())),
        sorted(
            (str(u), str(v), tuple(sorted(d.items()))) for u, v, d in graph.edges(data=True)
        ),
        type(graph).__name__,
    )


def _build(module, cls, seed, attr):
    rng = random.Random(seed)
    n = rng.randint(0, 24)
    labels = list(range(n))
    if seed % 2:
        rng.shuffle(labels)
    graph = getattr(module, cls)()
    graph.add_nodes_from(labels)
    for i in range(n):
        for _ in range(rng.choice([0, 1, 3])):
            j = rng.randrange(n)
            if i != j:
                weight = float(rng.randint(-20, 20)) if seed % 3 else rng.randint(-9, 9)
                graph.add_edge(labels[i], labels[j], **{attr: weight}, color="c")
    return graph


@pytest.mark.parametrize("fn", ["maximum_branching", "minimum_branching"])
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("preserve_attrs", [False, True])
@pytest.mark.parametrize("seed", range(6))
def test_branching_matches_networkx(fn, cls, preserve_attrs, seed):
    attr = "cost" if seed % 5 == 0 else "weight"
    # A FRESH graph per arm: networkx mutates its input (see the module docstring).
    assert _outcome(
        lambda: getattr(fnx, fn)(
            _build(fnx, cls, seed, attr), attr=attr, preserve_attrs=preserve_attrs
        )
    ) == _outcome(
        lambda: getattr(nx, fn)(
            _build(nx, cls, seed, attr), attr=attr, preserve_attrs=preserve_attrs
        )
    )


@pytest.mark.parametrize("fn", ["maximum_branching", "minimum_branching"])
@pytest.mark.parametrize("default", [1, -1, 0])
@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_default_is_not_materialised(fn, default, cls):
    """An attribute-free graph: networkx applies `default` itself, and so must fnx."""

    def build(module):
        rng = random.Random(3)
        graph = getattr(module, cls)()
        for _ in range(8):
            u, v = rng.randrange(6), rng.randrange(6)
            if u != v:
                graph.add_edge(u, v)
        return graph

    assert _outcome(lambda: getattr(fnx, fn)(build(fnx), default=default)) == _outcome(
        lambda: getattr(nx, fn)(build(nx), default=default)
    )


def test_partition_still_takes_the_faithful_route():
    """`partition` routes through a different input graph and must not be short-cut."""
    edges = [(0, 1, 5.0), (1, 2, 3.0), (2, 0, 1.0)]
    fg, ng = fnx.DiGraph(), nx.DiGraph()
    for u, v, w in edges:
        fg.add_edge(u, v, weight=w, partition="")
        ng.add_edge(u, v, weight=w, partition="")
    assert _outcome(
        lambda: fnx.maximum_branching(fg, partition="partition")
    ) == _outcome(lambda: nx.maximum_branching(ng, partition="partition"))


# sfq4w.4: maximum_branching runs networkx's Edmonds natively
# (networkx_maximum_branching_plan) and replays the history of networkx's final
# set of edge keys, so the result's edge ORDER matches too. These compare order,
# attribute order and value types, and the caller's graph after the call (the
# round-trip wrappers rewrite its weights in place, as networkx does).

import sys

BRANCHING_FAMILY = (
    "maximum_branching",
    "minimum_branching",
    "minimal_branching",
    "maximum_spanning_arborescence",
    "minimum_spanning_arborescence",
)


def _exact(graph):
    edges = graph.edges(keys=True, data=True) if graph.is_multigraph() else graph.edges(data=True)
    return (
        type(graph).__name__,
        [repr(n) for n in graph.nodes()],
        [tuple(repr(x) for x in e[:-1]) + (repr(list(e[-1].items())),) for e in edges],
    )


def _exact_outcome(module, fn, build, **kwargs):
    graph = build(module)
    try:
        result = ("ok", _exact(getattr(module, fn)(graph, **kwargs)))
    except Exception as exc:  # noqa: BLE001 - the exception IS the observation
        result = ("raise", type(exc).__name__, tuple(map(str, exc.args)))
    return result, _exact(graph)


def _tie_heavy(cls, seed, attr="weight", partition=None):
    """Small graphs with many equal weights, self-loops and (multigraph) parallel edges."""

    def build(module):
        rng = random.Random(seed)
        n = rng.randint(1, 9)
        labels = [f"n{i}" if seed % 4 == 0 else i for i in range(n)]
        if seed % 2:
            rng.shuffle(labels)
        graph = getattr(module, cls)()
        graph.add_nodes_from(labels)
        for _ in range(rng.randint(0, 3 * n)):
            u, v = rng.choice(labels), rng.choice(labels)
            if u == v and rng.random() < 0.7:
                continue
            data = {}
            if rng.random() < 0.9:
                data[attr] = rng.choice([-1, 0, 1, 1, 2, 2, 3]) if seed % 3 else rng.choice([0.5, 1.0, 1.0, 2.5])
            if partition is not None:
                data[partition] = rng.choice(
                    [nx.EdgePartition.OPEN, nx.EdgePartition.INCLUDED, nx.EdgePartition.EXCLUDED, None, None]
                )
            data["tag"] = rng.randint(0, 3)
            graph.add_edge(u, v, **data)
        return graph

    return build


@pytest.mark.parametrize("fn", BRANCHING_FAMILY)
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph", "Graph", "MultiGraph"])
def test_family_matches_networkx_exactly_on_tie_heavy_graphs(fn, cls):
    for seed in range(120):
        build = _tie_heavy(cls, seed)
        for preserve_attrs in (False, True):
            assert _exact_outcome(fnx, fn, build, preserve_attrs=preserve_attrs) == _exact_outcome(
                nx, fn, build, preserve_attrs=preserve_attrs
            ), (seed, preserve_attrs)


@pytest.mark.parametrize("fn", BRANCHING_FAMILY)
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_family_matches_networkx_exactly_with_partitions(fn, cls):
    for seed in range(120):
        build = _tie_heavy(cls, seed, partition="part")
        for preserve_attrs in (False, True):
            assert _exact_outcome(
                fnx, fn, build, partition="part", preserve_attrs=preserve_attrs
            ) == _exact_outcome(nx, fn, build, partition="part", preserve_attrs=preserve_attrs), (
                seed,
                preserve_attrs,
            )


@pytest.mark.parametrize(
    "weights",
    [
        [2**60, 1, 2],  # an int too large for exact f64 arithmetic
        [1, "2", 3],  # not a number: networkx's own comparison error
        [1, None, 3],
    ],
)
def test_weights_the_plan_does_not_cover_still_match_networkx(weights):
    def build(module):
        graph = module.DiGraph()
        for (u, v), w in zip([(0, 1), (1, 2), (2, 0)], weights):
            graph.add_edge(u, v, weight=w)
        return graph

    assert _exact_outcome(fnx, "maximum_branching", build) == _exact_outcome(
        nx, "maximum_branching", build
    )


def _networkx_frames(call):
    root = nx.__file__.rsplit("/", 1)[0]
    seen = []

    def profile(frame, event, arg):
        if event == "call" and frame.f_code.co_filename.startswith(root):
            seen.append(frame.f_code.co_name)

    sys.setprofile(profile)
    try:
        call()
    finally:
        sys.setprofile(None)
    return seen


@pytest.mark.parametrize("fn", ["maximum_branching", "minimum_branching"])
def test_default_path_runs_no_networkx_code(fn):
    graph = fnx.gnp_random_graph(60, 0.1, seed=4, directed=True)
    rng = random.Random(4)
    for u, v in graph.edges():
        graph[u][v]["weight"] = rng.randint(1, 9)
    frames = _networkx_frames(lambda: getattr(fnx, fn)(graph))
    assert frames == [], frames[:10]
