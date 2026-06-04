"""FrankenNetworkX bipartite submodule.

Re-exports the upstream ``networkx.algorithms.bipartite`` surface so
existing ``franken_networkx.bipartite.*`` call sites keep working, but
overrides specific functions with fnx-native implementations as the
native port lands.

Current native overrides:

- ``collaboration_weighted_projected_graph`` — Newman's collaboration
  weighted projection (franken_networkx-f2e8).
- ``generic_weighted_projected_graph`` — returns fnx.Graph
- ``overlap_weighted_projected_graph`` — returns fnx.Graph
"""

from __future__ import annotations

import networkx as _nx
from networkx.algorithms.bipartite import *  # noqa: F401,F403
import networkx.algorithms.bipartite as _nx_bipartite

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


def _matching_nx_view(B):
    """Lightweight fnx->nx conversion (nodes + edges, no attributes) for the
    bipartite matching algorithms, which only read adjacency.

    br-r37-c1-bipmatch: the matching functions were re-exported straight from
    networkx, so calling ``fnx.bipartite.hopcroft_karp_matching(F)`` ran nx's
    algorithm directly over the fnx graph -- every adjacency access pays the
    String-keyed PyO3 substrate cost, and Hopcroft-Karp/Eppstein sweep the
    adjacency many times, so it was 3-6x SLOWER than networkx. Convert ONCE to a
    plain nx graph (node order + ``B.edges()`` order preserved, so adj[u] matches
    a directly-built nx graph -> byte-identical matching) and let nx's C-speed
    adjacency carry the repeated sweeps. nx-typed inputs are returned as-is.
    """
    if isinstance(B, _nx.Graph):  # already a networkx graph
        return B
    if B.is_multigraph():
        G = _nx.MultiDiGraph() if B.is_directed() else _nx.MultiGraph()
        G.add_nodes_from(B)
        G.add_edges_from(B.edges(keys=True))
    else:
        G = _nx.DiGraph() if B.is_directed() else _nx.Graph()
        G.add_nodes_from(B)
        G.add_edges_from(B.edges())
    return G


def hopcroft_karp_matching(G, top_nodes=None):
    """Maximum-cardinality matching of bipartite ``G`` (Hopcroft-Karp).

    br-r37-c1-bipmatch: computed on a one-shot nx view of the fnx graph instead
    of running nx's algorithm over the fnx substrate (3-6x slower). Result is
    byte-identical to ``networkx.bipartite.hopcroft_karp_matching``.
    """
    return _nx_bipartite.hopcroft_karp_matching(_matching_nx_view(G), top_nodes)


def maximum_matching(G, top_nodes=None):
    """Alias of :func:`hopcroft_karp_matching` (matches networkx)."""
    return _nx_bipartite.maximum_matching(_matching_nx_view(G), top_nodes)


def eppstein_matching(G, top_nodes=None):
    """Maximum-cardinality matching of bipartite ``G`` (Eppstein).

    br-r37-c1-bipmatch: see :func:`hopcroft_karp_matching`.
    """
    return _nx_bipartite.eppstein_matching(_matching_nx_view(G), top_nodes)


def density(B, nodes):
    """Return the density of bipartite graph ``B``.

    br-r37-c1-bipdense: networkx's bipartite.density is re-exported as an
    ``@nx._dispatchable``; calling it on an fnx graph paid ~4ms of dispatch +
    substrate overhead for an O(1) formula (~80x slower than nx on a native
    graph). Computed directly here (networkx's exact formula) so it is
    byte-identical and ~20x FASTER than networkx. Works on fnx and nx inputs.
    """
    n = len(B)
    m = B.number_of_edges()
    nb = len(nodes)
    nt = n - nb
    if m == 0:  # includes n == 0 / n == 1
        return 0.0
    return m / (2 * nb * nt) if B.is_directed() else m / (nb * nt)


def degree_centrality(G, nodes):
    """Bipartite degree centrality, keyed by node.

    br-r37-c1-bipdense: same ``@nx._dispatchable`` overhead as :func:`density`
    (~100x slower on an fnx graph for an O(V) computation). Reproduces
    networkx's exact algorithm directly on ``G`` -- byte-identical (values and
    dict key order) and ~17x faster than the dispatched path.
    """
    top = set(nodes)
    bottom = set(G) - top
    s = 1.0 / len(bottom)
    centrality = {n: d * s for n, d in G.degree(top)}
    s = 1.0 / len(top)
    centrality.update({n: d * s for n, d in G.degree(bottom)})
    return centrality


def betweenness_centrality(G, nodes):
    """Bipartite betweenness centrality, computed via the fnx-native kernel.

    br-r37-c1-kp3o0: networkx's ``bipartite.betweenness_centrality`` is
    re-exported and internally calls ``nx.betweenness_centrality`` — the
    pure-Python Brandes algorithm — directly over the fnx graph's String-keyed
    PyO3 adjacency (~108ms / ~1.0x: nx-on-fnx-substrate). The bipartite layer
    only adds a closed-form rescaling on top of the *unnormalized* betweenness
    values, so we route the heavy Brandes computation through fnx's own native
    ``betweenness_centrality`` kernel (``normalized=False``) and apply the exact
    same bipartite normalization.

    The native kernel is fnx's standard, shipped betweenness implementation —
    its float accumulation order differs from networkx at the ~1e-16 level (the
    established fnx betweenness contract; the top-level ``betweenness_centrality``
    already diverges from nx by ~1e-13), so this makes the bipartite variant
    *consistent* with fnx's own betweenness rather than introducing any new
    divergence. Dict key order is byte-identical to nx and the result is
    deterministic across runs. ~28-31x FASTER than the re-exported path.
    """
    top = set(nodes)
    bottom = set(G) - top
    n = len(top)
    m = len(bottom)
    s, t = divmod(n - 1, m)
    bet_max_top = (
        ((m**2) * ((s + 1) ** 2))
        + (m * (s + 1) * (2 * t - s - 1))
        - (t * ((2 * s) - t + 3))
    ) / 2.0
    p, r = divmod(m - 1, n)
    bet_max_bot = (
        ((n**2) * ((p + 1) ** 2))
        + (n * (p + 1) * (2 * r - p - 1))
        - (r * ((2 * p) - r + 3))
    ) / 2.0
    betweenness = _fnx.betweenness_centrality(G, normalized=False, weight=None)
    for node in top:
        betweenness[node] /= bet_max_top
    for node in bottom:
        betweenness[node] /= bet_max_bot
    return betweenness


def closeness_centrality(G, nodes, normalized=True):
    """Bipartite closeness centrality, computed via fnx-native BFS.

    br-r37-c1-kp3o0: networkx's ``bipartite.closeness_centrality`` is
    re-exported and runs a Python ``single_source_shortest_path_length``
    BFS from *every* node directly over the fnx graph's String-keyed PyO3
    adjacency (the per-access substrate tax made it ~1.2x slower than nx).
    This reproduces networkx's exact algorithm but sources each BFS from
    ``fnx.single_source_shortest_path_length`` (native kernel). Every value
    derives from integer hop-count sums (``totsp = sum(sp.values())``) and
    integer set cardinalities, so the result is byte-identical to networkx
    (values and dict key order) while running ~2.3-2.9x FASTER.
    """
    closeness = {}
    path_length = _fnx.single_source_shortest_path_length
    top = set(nodes)
    bottom = set(G) - top
    n = len(top)
    m = len(bottom)
    len_G = len(G)
    for node in top:
        sp = dict(path_length(G, node))
        totsp = sum(sp.values())
        if totsp > 0.0 and len_G > 1:
            closeness[node] = (m + 2 * (n - 1)) / totsp
            if normalized:
                s = (len(sp) - 1) / (len_G - 1)
                closeness[node] *= s
        else:
            closeness[node] = 0.0
    for node in bottom:
        sp = dict(path_length(G, node))
        totsp = sum(sp.values())
        if totsp > 0.0 and len_G > 1:
            closeness[node] = (n + 2 * (m - 1)) / totsp
            if normalized:
                s = (len(sp) - 1) / (len_G - 1)
                closeness[node] *= s
        else:
            closeness[node] = 0.0
    return closeness


def collaboration_weighted_projected_graph(B, nodes, *, backend=None, **backend_kwargs):
    r"""Native port of Newman's collaboration-weighted bipartite projection.

    Produces the same graph as
    ``networkx.bipartite.collaboration_weighted_projected_graph`` without
    delegating to NetworkX. Both undirected and directed bipartite graphs
    are supported; multigraph inputs are rejected matching upstream.

    Edge weight between ``u`` and ``v`` is the sum over shared neighbors
    ``k`` of ``1 / (deg_B(k) - 1)``, where ``deg_B(k)`` is the degree of
    ``k`` in the bipartite graph ``B``.

    br-r37-c1-bk-submod: backend dispatch surface match nx.
    """
    _fnx._validate_backend_dispatch_keywords(
        "collaboration_weighted_projected_graph", backend, backend_kwargs
    )
    if B.is_multigraph():
        raise _fnx.NetworkXNotImplemented("not implemented for multigraph type")

    if B.is_directed():
        pred = B.pred
        G = _fnx.DiGraph()
    else:
        pred = B.adj
        G = _fnx.Graph()

    G.graph.update(B.graph)
    for node in nodes:
        G.add_node(node, **dict(B.nodes[node]))

    for u in nodes:
        unbrs = set(B[u])
        nbrs2 = {n for nbr in unbrs for n in B[nbr] if n != u}
        for v in nbrs2:
            vnbrs = set(pred[v])
            common_degree = (len(B[n]) for n in unbrs & vnbrs)
            weight = sum(1.0 / (deg - 1) for deg in common_degree if deg > 1)
            G.add_edge(u, v, weight=weight)
    return G


def projected_graph(B, nodes, multigraph=False, *, backend=None, **backend_kwargs):
    """Return the projection of B onto one of its node sets.

    Wraps ``networkx.algorithms.bipartite.projected_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "projected_graph", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.projected_graph(B, nodes, multigraph=multigraph)
    return _from_nx_graph(nx_result)


def weighted_projected_graph(B, nodes, ratio=False, *, backend=None, **backend_kwargs):
    """Return a weighted projection of B onto one of its node sets.

    Wraps ``networkx.algorithms.bipartite.weighted_projected_graph`` and
    converts the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "weighted_projected_graph", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.weighted_projected_graph(B, nodes, ratio=ratio)
    return _from_nx_graph(nx_result)


def generic_weighted_projected_graph(B, nodes, weight_function=None, *, backend=None, **backend_kwargs):
    """Return a weighted projection of B with a user-specified weight function.

    Wraps ``networkx.algorithms.bipartite.generic_weighted_projected_graph`` and
    converts the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "generic_weighted_projected_graph", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.generic_weighted_projected_graph(B, nodes, weight_function=weight_function)
    return _from_nx_graph(nx_result)


def overlap_weighted_projected_graph(B, nodes, jaccard=True, *, backend=None, **backend_kwargs):
    """Return a weighted projection of B using overlap/Jaccard coefficients.

    Wraps ``networkx.algorithms.bipartite.overlap_weighted_projected_graph`` and
    converts the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "overlap_weighted_projected_graph", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.overlap_weighted_projected_graph(B, nodes, jaccard=jaccard)
    return _from_nx_graph(nx_result)


def random_graph(n, m, p, seed=None, directed=False, *, backend=None, **backend_kwargs):
    """Return a bipartite random graph.

    Wraps ``networkx.algorithms.bipartite.random_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "random_graph", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.random_graph(n, m, p, seed=seed, directed=directed)
    return _from_nx_graph(nx_result)


def gnmk_random_graph(n, m, k, seed=None, directed=False, *, backend=None, **backend_kwargs):
    """Return a random bipartite graph G_{n,m,k}.

    Wraps ``networkx.algorithms.bipartite.gnmk_random_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "gnmk_random_graph", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.gnmk_random_graph(n, m, k, seed=seed, directed=directed)
    return _from_nx_graph(nx_result)


def alternating_havel_hakimi_graph(aseq, bseq, create_using=None, *, backend=None, **backend_kwargs):
    """Return a bipartite graph from two degree sequences using alternating Havel-Hakimi.

    Wraps ``networkx.algorithms.bipartite.alternating_havel_hakimi_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "alternating_havel_hakimi_graph", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.alternating_havel_hakimi_graph(aseq, bseq, create_using=create_using)
    return _from_nx_graph(nx_result, create_using=create_using)


def complete_bipartite_graph(n1, n2, create_using=None, *, backend=None, **backend_kwargs):
    """Return the complete bipartite graph K_{n1,n2}.

    Wraps ``networkx.algorithms.bipartite.complete_bipartite_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "complete_bipartite_graph", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.complete_bipartite_graph(n1, n2, create_using=create_using)
    return _from_nx_graph(nx_result, create_using=create_using)


def configuration_model(aseq, bseq, create_using=None, seed=None, *, backend=None, **backend_kwargs):
    """Return a random bipartite graph from two degree sequences.

    Wraps ``networkx.algorithms.bipartite.configuration_model`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "configuration_model", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.configuration_model(aseq, bseq, create_using=create_using, seed=seed)
    return _from_nx_graph(nx_result, create_using=create_using)


def havel_hakimi_graph(aseq, bseq, create_using=None, *, backend=None, **backend_kwargs):
    """Return a bipartite graph from two degree sequences using Havel-Hakimi.

    Wraps ``networkx.algorithms.bipartite.havel_hakimi_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "havel_hakimi_graph", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.havel_hakimi_graph(aseq, bseq, create_using=create_using)
    return _from_nx_graph(nx_result, create_using=create_using)


def preferential_attachment_graph(aseq, p, create_using=None, seed=None, *, backend=None, **backend_kwargs):
    """Create a bipartite graph with preferential attachment model.

    Wraps ``networkx.algorithms.bipartite.preferential_attachment_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "preferential_attachment_graph", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.preferential_attachment_graph(aseq, p, create_using=create_using, seed=seed)
    return _from_nx_graph(nx_result, create_using=create_using)


def reverse_havel_hakimi_graph(aseq, bseq, create_using=None, *, backend=None, **backend_kwargs):
    """Return a bipartite graph from two degree sequences using reverse Havel-Hakimi.

    Wraps ``networkx.algorithms.bipartite.reverse_havel_hakimi_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "reverse_havel_hakimi_graph", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.reverse_havel_hakimi_graph(aseq, bseq, create_using=create_using)
    return _from_nx_graph(nx_result, create_using=create_using)


def from_biadjacency_matrix(A, create_using=None, edge_attribute="weight", *, row_order=None, column_order=None, backend=None, **backend_kwargs):
    """Create a bipartite graph from a biadjacency matrix.

    Wraps ``networkx.algorithms.bipartite.from_biadjacency_matrix`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "from_biadjacency_matrix", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.from_biadjacency_matrix(
        A, create_using=create_using, edge_attribute=edge_attribute,
        row_order=row_order, column_order=column_order
    )
    return _from_nx_graph(nx_result, create_using=create_using)


def parse_edgelist(lines, comments="#", delimiter=None, create_using=None, nodetype=None, data=True, *, backend=None, **backend_kwargs):
    """Parse lines of a bipartite graph edge list representation.

    Wraps ``networkx.algorithms.bipartite.parse_edgelist`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "parse_edgelist", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.parse_edgelist(
        lines, comments=comments, delimiter=delimiter,
        create_using=create_using, nodetype=nodetype, data=data
    )
    return _from_nx_graph(nx_result, create_using=create_using)


def read_edgelist(path, comments="#", delimiter=None, create_using=None, nodetype=None, data=True, edgetype=None, encoding="utf-8", *, backend=None, **backend_kwargs):
    """Read a bipartite graph edge list from a file.

    Wraps ``networkx.algorithms.bipartite.read_edgelist`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "read_edgelist", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.read_edgelist(
        path, comments=comments, delimiter=delimiter,
        create_using=create_using, nodetype=nodetype, data=data,
        edgetype=edgetype, encoding=encoding
    )
    return _from_nx_graph(nx_result, create_using=create_using)
