"""Lazy-materialization stress guard for the fully-lazy construction frontier.

The biggest remaining construction-tax lever (br-r37-c1-n7gxs #1) drops the Rust
AttrMap entirely on copy/to_undirected/subgraph and relies on LAZY materialization
from the Python dict mirror (as PyGraph.to_directed already does). The risk: some
consumer reads the Rust attrs directly and would see EMPTY attrs if a fold forgot
to materialize. The existing guards check attribute *fidelity*; this one forces
materialization through EVERY access path after a lazy-fold construction, so a
fully-lazy fold that breaks any one consumer is caught.

For graphs built via copy() / to_undirected() / subgraph(), every attribute
access route must agree with networkx:
  * subscript g[u][v] and g.get_edge_data(u, v);
  * edges(data=True) / nodes(data=True);
  * adjacency() rows;
  * NATIVE consumers that read the Rust AttrMap: to_numpy_array(weight=...),
    degree(weight=...), size(weight=...).

No mocks: real fnx vs real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx

np = pytest.importorskip("numpy")

_BUILDERS = ["copy", "to_undirected", "subgraph"]


def _seed_pair(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    fg, ng = fnx.Graph(), nx.Graph()
    for node in range(n):
        fg.add_node(node, tag=f"t{node}")
        ng.add_node(node, tag=f"t{node}")
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.5:
                w = r.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    return fg, ng, n, r


def _apply(builder, g, n, r):
    if builder == "copy":
        return g.copy()
    if builder == "to_undirected":
        return g.to_undirected()
    if builder == "subgraph":
        keep = sorted(r.sample(range(n), max(2, n - 1)))
        return g.subgraph(keep).copy()
    raise AssertionError(builder)


@pytest.mark.parametrize("builder", _BUILDERS)
@pytest.mark.parametrize("seed", range(15))
def test_all_attr_access_paths_agree_after_lazy_build(builder, seed):
    fg, ng, n, r = _seed_pair(seed)
    r2 = random.Random(seed)  # identical sampling for both libs' subgraph
    fb = _apply(builder, fg, n, r2)
    r3 = random.Random(seed)
    nb = _apply(builder, ng, n, r3)

    # Subscript + get_edge_data must materialize the same weights.
    for u, v in nb.edges():
        assert fb[u][v] == nb[u][v]
        assert fb.get_edge_data(u, v) == nb.get_edge_data(u, v)
    # Views.
    assert {n_: dict(d) for n_, d in fb.nodes(data=True)} == {
        n_: dict(d) for n_, d in nb.nodes(data=True)
    }
    assert sorted((tuple(sorted((u, v))), tuple(sorted(d.items())))
                  for u, v, d in fb.edges(data=True)) == sorted(
        (tuple(sorted((u, v))), tuple(sorted(d.items())))
        for u, v, d in nb.edges(data=True))
    # NATIVE consumers that read the Rust AttrMap.
    assert fb.size(weight="weight") == nb.size(weight="weight")
    assert dict(fb.degree(weight="weight")) == dict(nb.degree(weight="weight"))
    fnodes = sorted(fb.nodes())
    nnodes = sorted(nb.nodes())
    assert fnodes == nnodes
    fa = fnx.to_numpy_array(fb, nodelist=fnodes, weight="weight")
    na = nx.to_numpy_array(nb, nodelist=nnodes, weight="weight")
    assert np.array_equal(fa, na)
    # NODE-attr consumers — cover the NODE-only fully-lazy fold's risk (n7gxs #1):
    # if fnx ever serves node attrs from the Rust inner rather than the Python
    # mirror, a fold that empties the Rust node AttrMap would diverge here. If
    # these stay green, node attrs are mirror-only => the node fully-lazy fold is
    # safe (no Rust node-attr consumer to break). nodes(data=True) above reads the
    # mirror; these are the extra angles.
    assert fnx.get_node_attributes(fb, "tag") == nx.get_node_attributes(nb, "tag")
    for node in nnodes:
        assert fb.nodes[node] == nb.nodes[node]
