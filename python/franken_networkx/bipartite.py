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


def _native_hopcroft_karp(G, top_nodes):
    """br-r37-c1-bngez: byte-exact native Hopcroft-Karp for an fnx simple Graph.

    nx's algorithm starts from ``bipartite_sets(G, top_nodes)`` whose left/right
    SET iteration order (CPython set order) drives both which augmenting paths
    are found and the result-dict key order — un-reproducible in Rust. When
    ``top_nodes`` is supplied we replicate nx's ``X = set(top_nodes);
    Y = set(G) - X`` directly (cheap, no BFS), then the native kernel does the
    matching over ``neighbors_indices``. Returns ``None`` (caller delegates) for
    any shape the fast path can't own: nx-typed / multigraph / directed inputs,
    or ``top_nodes is None`` (that path needs nx's BFS 2-colouring, whose set
    order we don't reconstruct here).
    """
    if isinstance(G, _nx.Graph) or top_nodes is None:
        return None
    if G.is_multigraph() or G.is_directed():
        return None
    native = getattr(_fnx._fnx, "bipartite_hopcroft_karp_matching", None)
    if native is None:
        return None
    node_list = list(G)
    index = {node: i for i, node in enumerate(node_list)}
    try:
        left_set = set(top_nodes)
        # Mirror nx.bipartite.sets: X = set(top_nodes); Y = set(G) - X. An unknown
        # top node KeyErrors in the index lookup -> fall back to nx (its own error).
        left_idx = [index[x] for x in left_set]
        right_idx = [index[y] for y in (set(G) - left_set)]
    except (KeyError, TypeError):
        return None
    return native(G, left_idx, right_idx)


def hopcroft_karp_matching(G, top_nodes=None):
    """Maximum-cardinality matching of bipartite ``G`` (Hopcroft-Karp).

    br-r37-c1-bngez: native byte-exact kernel for the ``top_nodes``-given simple
    Graph case (no fnx->nx conversion + no nx Python sweeps); other shapes use a
    one-shot nx view. Result is byte-identical to
    ``networkx.bipartite.hopcroft_karp_matching``.
    """
    result = _native_hopcroft_karp(G, top_nodes)
    if result is not None:
        return result
    return _nx_bipartite.hopcroft_karp_matching(_matching_nx_view(G), top_nodes)


def maximum_matching(G, top_nodes=None):
    """Alias of :func:`hopcroft_karp_matching` (matches networkx)."""
    result = _native_hopcroft_karp(G, top_nodes)
    if result is not None:
        return result
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


def degrees(B, nodes, weight=None):
    """Return ``(degX, degY)`` for the two bipartite node sets of ``B``.

    br-r37-c1-bipdeg: re-exported from networkx as an ``@nx._dispatchable``, so
    calling it on an fnx graph round-trips the WHOLE graph through ``_fnx_to_nx``
    (full O(V+E) conversion) just to build two lazy DegreeViews — ~62x slower than
    nx for an O(1) view construction. Run networkx's exact algorithm directly on
    ``B`` so the result is byte-identical (same two DegreeView objects, same node
    sets/order) with no conversion. ``nodes`` is one set (the Y set); the first
    returned view is the OTHER set (X = B - nodes).
    """
    bottom = set(nodes)
    top = set(B) - bottom
    return (B.degree(top, weight=weight), B.degree(bottom, weight=weight))


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


def _weighted_projection_inprocess(B, nodes, weight_fn):
    """br-r37-c1-0y2fn: in-process weighted bipartite projection for a simple
    undirected fnx Graph (else None to fall back). Snapshots B's adjacency ONCE
    via the native key-only binding instead of paying either an nx round-trip +
    ``_from_nx_graph`` (the delegated weighted/overlap/generic wrappers) or
    per-access ``B[u]``/``B[nbr]`` AtlasView lookups (the native-port
    collaboration wrapper). ``weight_fn(unbrs, vnbrs, adj)`` returns each edge
    weight; the adjacency rows are Python sets so ``&``/``|``/``min`` and the
    ``len(adj[k])`` degree lookups are exactly nx's computations.
    """
    nak = getattr(B, "_native_adjacency_keys", None)
    if nak is None or type(B) is not _fnx.Graph or B.is_multigraph() or B.is_directed():
        return None
    adj = {node: set(nbrs) for node, nbrs in nak()}
    G = _fnx.Graph()
    G.graph.update(B.graph)
    G.add_nodes_from((n, B.nodes[n]) for n in nodes)
    edges = []
    for u in nodes:
        unbrs = adj[u]
        nbrs2 = {n for nbr in unbrs for n in adj[nbr] if n != u}
        for v in nbrs2:
            edges.append((u, v, {"weight": weight_fn(unbrs, adj[v], adj)}))
    G.add_edges_from(edges)
    return G


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

    # br-r37-c1-0y2fn: snapshot adjacency once instead of per-access B[u]/pred[v].
    _fast = _weighted_projection_inprocess(
        B,
        nodes,
        lambda un, vn, adj: sum(
            1.0 / (len(adj[n]) - 1) for n in (un & vn) if len(adj[n]) > 1
        ),
    )
    if _fast is not None:
        return _fast

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
    # br-r37-c1-bpproj: de-delegate the common case (simple undirected fnx Graph,
    # no multigraph). The delegated path ran nx's algorithm THROUGH fnx's slow
    # per-access adjacency views AND rebuilt the result via _from_nx_graph (~61%
    # of the time). Instead snapshot B's adjacency once via the native key-only
    # binding and build the fnx projection directly — same edge set (two nodes
    # are joined iff they share a common neighbour; the parity tests compare
    # sorted edges). Directed / multigraph / nx-typed B keep the delegation path.
    nak = getattr(B, "_native_adjacency_keys", None)
    if not multigraph and type(B) is _fnx.Graph and nak is not None:
        adj = {node: nbrs for node, nbrs in nak()}
        G = _fnx.Graph()
        G.graph.update(B.graph)
        G.add_nodes_from((n, B.nodes[n]) for n in nodes)
        for u in nodes:
            nbrs2 = {v for nbr in adj[u] for v in adj[nbr] if v != u}
            G.add_edges_from((u, n) for n in nbrs2)
        return G
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
    # br-r37-c1-0y2fn: de-delegate the simple undirected case. nx guards
    # n_top < 1 (raises) — keep that on the delegation fallback.
    if type(B) is _fnx.Graph and not B.is_multigraph() and not B.is_directed():
        n_top = len(B) - len(nodes)
        if n_top >= 1:
            if ratio:
                wf = lambda un, vn, adj: len(un & vn) / n_top
            else:
                wf = lambda un, vn, adj: len(un & vn)
            _fast = _weighted_projection_inprocess(B, nodes, wf)
            if _fast is not None:
                return _fast
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
    # br-r37-c1-0y2fn: de-delegate only the DEFAULT weight function (number of
    # shared neighbours). A user-supplied weight_function is arbitrary Python and
    # keeps the nx delegation path.
    if weight_function is None:
        _fast = _weighted_projection_inprocess(
            B, nodes, lambda un, vn, adj: len(un & vn)
        )
        if _fast is not None:
            return _fast
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
    # br-r37-c1-0y2fn: de-delegate the simple undirected case.
    if jaccard:
        wf = lambda un, vn, adj: len(un & vn) / len(un | vn)
    else:
        wf = lambda un, vn, adj: len(un & vn) / min(len(un), len(vn))
    _fast = _weighted_projection_inprocess(B, nodes, wf)
    if _fast is not None:
        return _fast
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
