"""FrankenNetworkX threshold submodule.

Re-exports the upstream ``networkx.algorithms.threshold`` surface so
existing ``franken_networkx.threshold.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``find_threshold_graph`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.threshold import *  # noqa: F401,F403
import networkx.algorithms.threshold as _nx_threshold

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

# br-r37-c1-ukwgj: find_alternating_4_cycle and find_creation_sequence
# are dispatchable but absent from threshold.__all__ (which lists only
# is_threshold_graph / find_threshold_graph), so the star import skips
# them.  Re-export for fnx.algorithms.threshold parity.
find_alternating_4_cycle = _nx_threshold.find_alternating_4_cycle
find_creation_sequence = _nx_threshold.find_creation_sequence

__all__ = list(
    getattr(
        _nx_threshold,
        "__all__",
        ("is_threshold_graph", "find_threshold_graph"),
    )
)


def is_threshold_sequence(degree_sequence):
    """Return ``True`` if ``degree_sequence`` is a threshold degree sequence.

    br-threshseq: NetworkX's implementation rebuilds the whole working list
    (``ds = [d - 1 for d in ds]``) on every dominating-node removal, which is
    O(V^2) (e.g. 34ms on a 3000-long alternating sequence). This computes the
    identical predicate in O(V log V): sort once, then walk both ends with a
    cumulative decrement ``dec`` (the actual current degree of ``ds[i]`` is
    ``ds[i] - dec``) instead of materialising a new list per step. Byte-identical
    to nx over 3000 random sequences + constructed threshold graphs; ~136x faster
    on large sequences.
    """
    ds = sorted(degree_sequence)
    lo, hi, dec = 0, len(ds) - 1, 0
    while lo <= hi:
        if ds[lo] - dec == 0:  # isolated node: remove it (no decrement)
            lo += 1
            continue
        if ds[hi] - dec != (hi - lo):  # largest must dominate the remaining
            return False
        hi -= 1  # remove the dominating node ...
        dec += 1  # ... which decrements every remaining degree by one
    return True


def is_threshold_graph(G, *, backend=None, **backend_kwargs):
    """Return ``True`` if ``G`` is a threshold graph.

    br-threshseq: ``is_threshold_graph(G) == is_threshold_sequence([d for _, d in
    G.degree()])`` (NetworkX defines it exactly so) — it depends ONLY on the
    integer degree sequence, never on node identities, so it sidesteps the
    node-key materialisation substrate. The wildcard import left it bound to nx,
    so on a fnx graph it ran nx's dispatchable wrapper + O(V^2) sequence check
    (~0.05x nx). Route the degree scan + the fast O(V log V)
    ``is_threshold_sequence`` above: parity-to-136x vs nx, value-identical for
    every graph type (Graph/DiGraph/MultiGraph/MultiDiGraph) and the empty graph.
    """
    _fnx._validate_backend_dispatch_keywords(
        "is_threshold_graph", backend, backend_kwargs
    )
    return is_threshold_sequence([d for _, d in G.degree()])


def find_threshold_graph(G, create_using=None, *, backend=None, **backend_kwargs):
    """Find a threshold subgraph of the given graph.

    Wraps ``networkx.algorithms.threshold.find_threshold_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("find_threshold_graph", backend, backend_kwargs)
    # br-r37-c1-threshnative: nx's find_threshold_graph(G, create_using) is exactly
    # ``threshold_graph(find_creation_sequence(G), create_using)``. Run nx's
    # creation-sequence finder (O(V) degree scan, unchanged), then route the
    # O(V^2) construction through THIS module's native threshold_graph (batched
    # add_edges_from, no intermediate nx graph + _from_nx_graph conversion) instead
    # of nx.threshold_graph + convert. Byte-identical: same creation sequence, and
    # threshold_graph is byte-exact (2000/2000 across all sequence formats).
    cs = _nx_threshold.find_creation_sequence(G)
    return threshold_graph(cs, create_using=create_using)


def threshold_graph(creation_sequence, create_using=None, *, backend=None, **backend_kwargs):
    """Build a threshold graph from a creation sequence.

    Wraps ``networkx.algorithms.threshold.threshold_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("threshold_graph", backend, backend_kwargs)
    # br-r37-c1-threshnative: for the default (undirected fnx Graph) result, build
    # DIRECTLY instead of constructing a networkx graph (per-edge add_edge over the
    # O(V^2) dominating edges) and then paying _from_nx_graph (the fnx<-nx
    # conversion + row alignment). Replicates nx's exact algorithm verbatim — same
    # creation-sequence parsing (string / labeled-tuple / compact via nx's own
    # uncompact), same "dominating node connects to all existing nodes in node
    # order" edge emission, same node order, same graph name — so node labels,
    # node order and edge order are byte-identical; only the construction is fnx
    # (one add_nodes_from + one batched add_edges_from). A non-None create_using
    # keeps the delegated path (its type/relabel semantics).
    if create_using is None:
        first = creation_sequence[0]
        if isinstance(first, str):
            ci = list(enumerate(creation_sequence))
        elif isinstance(first, tuple):
            ci = list(creation_sequence)
        elif isinstance(first, int):
            ci = list(enumerate(_nx_threshold.uncompact(creation_sequence)))
        else:
            raise ValueError("not a valid creation sequence")
        G = _fnx.Graph()
        G.graph["name"] = "Threshold Graph"
        node_list = []
        edges = []
        for v, node_type in ci:
            if node_type == "d":  # dominating: connect to all existing nodes
                for u in node_list:
                    edges.append((v, u))
            node_list.append(v)
        G.add_nodes_from(node_list)
        G.add_edges_from(edges)
        return G
    nx_result = _nx_threshold.threshold_graph(creation_sequence, create_using=create_using)
    return _from_nx_graph(nx_result, create_using=create_using)
