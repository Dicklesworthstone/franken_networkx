"""The documented drop-in backend mode must not dispatch into itself.

``nx.config.backend_priority = ["franken_networkx"]`` is the headline usage in
the README, and it turns every registered entry of
``backend._SUPPORTED_ALGORITHMS`` into a dispatch target. Two ways that becomes
an infinite loop, both of which shipped (br-r37-c1-egjfn):

* a registered fnx function whose networkx fallback is called WITHOUT
  ``backend="networkx"`` — nx routes the fallback straight back into fnx
  (``louvain_communities``);
* a registration whose "implementation" IS networkx's ``@_dispatchable`` of the
  same name, so the cycle contains no fnx frame at all
  (``max_clique``, ``maximum_independent_set``, ``clique_removal``).

The second kind cannot be repaired by pinning at the call site: nx's own
``max_clique`` body calls ``clique_removal()`` unpinned, so the cycle re-forms
one frame deeper. Those names must simply not be registered.
"""

from __future__ import annotations

import types

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx.backend import _SUPPORTED_ALGORITHMS

# The four names that recursed before br-r37-c1-egjfn. Kept explicit so a
# regression names its victim instead of failing somewhere in the sweep.
_PREVIOUSLY_RECURSING = [
    "louvain_communities",
    "max_clique",
    "maximum_independent_set",
    "clique_removal",
]

_NX_NAMESPACES = [
    nx,
    nx.algorithms.approximation,
    nx.algorithms.community,
]


def _set_backend_priority(names):
    """Set nx's algo dispatch order.

    ``nx.config.backend_priority`` accepts a plain list on assignment (the
    spelling the README documents) but reads back as a ``BackendPriorities``
    struct, so round-tripping it through ``list()`` yields its field names and
    fails on the way back in. ``.algos`` is the field the assignment writes.
    """
    nx.config.backend_priority.algos = list(names)


@pytest.fixture
def backend_priority():
    """Run the body with fnx installed as nx's preferred backend."""
    previous = list(nx.config.backend_priority.algos)
    _set_backend_priority(["franken_networkx"])
    try:
        yield
    finally:
        _set_backend_priority(previous)


def _networkx_twin(name):
    """Return networkx's own object of this name, if it has one."""
    for namespace in _NX_NAMESPACES:
        candidate = getattr(namespace, name, None)
        if candidate is not None:
            return candidate
    return None


def test_no_registration_is_the_networkx_dispatchable_itself():
    """A registration may not name nx's own dispatchable of the same algorithm.

    That is not an implementation, it is a cycle: nx dispatches the name to this
    backend, this backend calls nx's dispatchable, and nx dispatches it again.
    """
    cycles = []
    for name, implementation in sorted(_SUPPORTED_ALGORITHMS.items()):
        twin = _networkx_twin(name)
        if twin is not None and implementation is twin:
            cycles.append(name)
    assert cycles == [], (
        "these registrations dispatch to themselves via networkx and will "
        f"recurse under backend_priority: {cycles}"
    )


@pytest.mark.parametrize("name", _PREVIOUSLY_RECURSING)
def test_previously_recursing_algorithms_terminate(name, backend_priority):
    """Each of the four historical offenders returns instead of recursing."""
    graph = nx.path_graph(7)
    if name == "louvain_communities":
        result = fnx.community.louvain_communities(graph, seed=7)
    else:
        result = getattr(nx.algorithms.approximation, name)(graph)
    assert result is not None


@pytest.mark.parametrize("name", _PREVIOUSLY_RECURSING)
def test_previously_recursing_algorithms_match_networkx(name, backend_priority):
    """...and returns exactly what networkx alone returns, on both graph types."""
    nx_graph = nx.path_graph(7)
    fnx_graph = fnx.path_graph(7)

    previous = list(nx.config.backend_priority.algos)
    _set_backend_priority([])
    try:
        if name == "louvain_communities":
            expected = nx.community.louvain_communities(nx_graph, seed=7)
        else:
            expected = getattr(nx.algorithms.approximation, name)(nx_graph)
    finally:
        _set_backend_priority(previous)

    if name == "louvain_communities":
        assert fnx.community.louvain_communities(nx_graph, seed=7) == expected
        assert fnx.community.louvain_communities(fnx_graph, seed=7) == expected
    else:
        function = getattr(nx.algorithms.approximation, name)
        assert function(nx_graph) == expected
        assert function(fnx_graph) == expected


def test_louvain_networkx_fallback_pins_the_backend():
    """The fallback in ``community.louvain_communities`` must stay pinned.

    The native gate declines for a graph carrying the weight attribute, so this
    call reaches the networkx fallback; unpinned it would re-enter fnx.
    """
    weighted = fnx.Graph()
    weighted.add_edge("a", "b", weight=1.0)
    weighted.add_edge("b", "c", weight=2.0)
    weighted.add_edge("c", "a", weight=1.5)

    previous = list(nx.config.backend_priority.algos)
    _set_backend_priority(["franken_networkx"])
    try:
        communities = fnx.community.louvain_communities(weighted, seed=7)
    finally:
        _set_backend_priority(previous)

    assert {frozenset(community) for community in communities} == {
        frozenset({"a", "b", "c"})
    }


def _multi_argument_probes():
    """Concrete calls for registered algorithms the one-argument sweep skips.

    The sweep calls every entry with a single graph, so 271 of the 313
    registrations raise on arity and are skipped — a blind spot exactly where a
    louvain-shaped unpinned fallback could hide. These are the registered names
    that delegate into networkx WITHOUT ``backend="networkx"`` (found by walking
    the package AST), each given real arguments. All of them are expected to
    terminate: being unpinned is necessary for the louvain cycle but not
    sufficient, and nothing here should be "fixed" by adding pins on spec.
    """
    path = fnx.path_graph(6)
    dag = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
    dense = fnx.complete_graph(6)
    return [
        ("bfs_tree", lambda: fnx.traversal.bfs_tree(path, 0)),
        ("dfs_tree", lambda: fnx.traversal.dfs_tree(path, 0)),
        ("transitive_closure", lambda: fnx.dag.transitive_closure(dag)),
        ("transitive_reduction", lambda: fnx.dag.transitive_reduction(dag)),
        ("contracted_nodes", lambda: fnx.minors.contracted_nodes(path, 0, 1)),
        ("contracted_edge", lambda: fnx.minors.contracted_edge(path, (0, 1))),
        ("identified_nodes", lambda: fnx.minors.identified_nodes(path, 0, 1)),
        ("greedy_color", lambda: fnx.greedy_color(path)),
        ("intersection", lambda: fnx.intersection(path, fnx.path_graph(6))),
        ("union", lambda: fnx.union(fnx.Graph([(0, 1)]), fnx.Graph([(2, 3)]))),
        ("shortest_path", lambda: fnx.shortest_path(path, 0, 5)),
        ("maximum_spanning_tree", lambda: fnx.maximum_spanning_tree(path)),
        ("minimum_spanning_edges", lambda: list(fnx.minimum_spanning_edges(path))),
        ("chordal_graph_cliques", lambda: list(fnx.chordal_graph_cliques(dense))),
        (
            "complete_bipartite_graph",
            lambda: fnx.bipartite.complete_bipartite_graph(2, 3),
        ),
    ]


@pytest.mark.parametrize("name", [probe[0] for probe in _multi_argument_probes()])
def test_multi_argument_delegations_terminate(name, backend_priority):
    """The arity-skipped half of the table terminates too."""
    call = dict(_multi_argument_probes())[name]
    assert call() is not None


@pytest.mark.slow
def test_no_dispatchable_algorithm_recurses(backend_priority):
    """Sweep every registered algorithm; none may exhaust the stack.

    Arity and semantics vary wildly across the table, so a call that raises for
    any other reason is not evidence of anything and is skipped. What is being
    asserted is narrow and exact: no registered name blows the stack.
    """
    probes = (nx.path_graph(5), nx.DiGraph([(0, 1), (1, 2)]))
    recursed = []
    exercised = 0

    for name, function in sorted(_SUPPORTED_ALGORITHMS.items()):
        for graph in probes:
            try:
                result = function(graph)
                if isinstance(result, types.GeneratorType):
                    list(result)
            except RecursionError:
                recursed.append(name)
                break
            except Exception:  # noqa: BLE001 - wrong arity/semantics, not a cycle
                continue
            else:
                exercised += 1
                break

    assert recursed == [], f"dispatch cycles under backend_priority: {recursed}"
    # Guard the guard: if the table stopped being callable this way the sweep
    # would pass while proving nothing.
    assert exercised >= 150, f"only {exercised} algorithms actually ran"
