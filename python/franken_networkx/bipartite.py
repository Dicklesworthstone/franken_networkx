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
from networkx.utils import open_file as _nx_open_file

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

__all__ = list(
    getattr(_nx_bipartite, "__all__", ())
    or [name for name in dir(_nx_bipartite) if not name.startswith("_")]
)


# br-r37-c1-2qsqf: ``from networkx.algorithms.bipartite import *`` above left
# ``is_bipartite`` bound to networkx's implementation, so
# ``fnx.bipartite.is_bipartite`` silently resolved to nx's instead of fnx's
# native version. Route it to the fnx top-level function (the many bipartite
# helpers below are already explicit overrides). Call-time reference keeps it
# import-order robust.
def is_bipartite(G, *, backend=None, **backend_kwargs):
    """Return True if graph G is bipartite (fnx-native).

    See ``networkx.algorithms.bipartite.is_bipartite`` for semantics.
    """
    import franken_networkx as _fnx_top

    return _fnx_top.is_bipartite(G)


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


def min_edge_cover(G, matching_algorithm=None, *, backend=None, **backend_kwargs):
    """Return a bipartite minimum edge cover using fnx-native matching."""
    _fnx._validate_backend_dispatch_keywords(
        "min_edge_cover", backend, backend_kwargs
    )
    if G.is_multigraph():
        raise _fnx.NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for directed type")
    if len(G) == 0:
        return set()
    if any(degree == 0 for _, degree in G.degree()):
        raise _nx.NetworkXException(
            "Graph has a node with no edge incident on it, so no edge cover exists."
        )
    if matching_algorithm is None:
        matching_algorithm = hopcroft_karp_matching
    maximum_matching = matching_algorithm(G)
    try:
        min_cover = set(maximum_matching.items())
        bipartite_cover = True
    except AttributeError:
        min_cover = set(maximum_matching)
        bipartite_cover = False

    covered = {node for edge in min_cover for node in edge}
    for v in set(G) - covered:
        u = next(iter(G[v]))
        min_cover.add((u, v))
        if bipartite_cover:
            min_cover.add((v, u))
    return min_cover


def generate_edgelist(G, delimiter=" ", data=True):
    """Generate bipartite edgelist lines from ``bipartite=0`` nodes."""
    if G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for directed type")
    try:
        part0 = [node for node, attrs in G.nodes.items() if attrs["bipartite"] == 0]
    except BaseException as err:
        raise AttributeError("Missing node attribute `bipartite`") from err

    def _lines():
        if data is True or data is False:
            for node in part0:
                for edge in G.edges(node, data=data):
                    yield delimiter.join(map(str, edge))
        else:
            for node in part0:
                for u, v, attrs in G.edges(node, data=True):
                    edge = [u, v]
                    try:
                        edge.extend(attrs[key] for key in data)
                    except KeyError:
                        pass
                    yield delimiter.join(map(str, edge))

    return _lines()


@_nx_open_file(1, mode="wb")
def write_edgelist(
    G, path, comments="#", delimiter=" ", data=True, encoding="utf-8"
):
    """Write a bipartite edgelist using local ``generate_edgelist``."""
    for line in generate_edgelist(G, delimiter, data):
        line += "\n"
        path.write(line.encode(encoding))


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


def biadjacency_matrix(
    B, row_order, column_order=None, dtype=None, weight="weight", format="csr"
):
    """Return the biadjacency matrix (``row_order`` x ``column_order``) of ``B``.

    br-r37-c1-r2h3w: re-exported from networkx as an ``@nx._dispatchable``, so
    calling it on an fnx graph round-trips the WHOLE graph through ``_fnx_to_nx``
    (full O(V+E) conversion) before building the sparse matrix -- ~4x slower than
    nx. Build the COO directly from ``B``'s adjacency (no conversion). The output
    is byte-identical: ``coo_array(...).asformat(...)`` canonicalises so the
    (row, col, data) triple SET fully determines the matrix, and the default
    column ordering ``list(set(B) - set(row_order))`` reproduces nx's
    arbitrary-but-deterministic CPython set order exactly (same node values ->
    same set). Directed graphs use successors only, matching nx's
    ``B.edges(row_order)``.
    """
    import itertools

    import scipy as sp

    nlen = len(row_order)
    if nlen == 0:
        raise _nx.NetworkXError("row_order is empty list")
    if len(row_order) != len(set(row_order)):
        raise _nx.NetworkXError(
            "Ambiguous ordering: `row_order` contained duplicates."
        )
    if column_order is None:
        column_order = list(set(B) - set(row_order))
    mlen = len(column_order)
    if len(column_order) != len(set(column_order)):
        raise _nx.NetworkXError(
            "Ambiguous ordering: `column_order` contained duplicates."
        )

    # br-r37-c1-18cp7: native rectangular-COO kernel — emit (row_pos, col_pos,
    # weight) over the row-node adjacency in Rust, eliminating the per-edge
    # ``B.edges(row_order, data=True)`` PyO3 iteration floor (the residual ~1.2x
    # vs nx after the conversion was already removed). The kernel reports
    # ``all_int`` so we reproduce nx's dtype inference exactly (int64 for an
    # all-integer non-empty matrix, float64 otherwise); coo canonicalisation
    # makes the result order-independent. Directed / multigraph / nx-typed /
    # non-numeric-weight inputs return None -> exact Python loop below.
    native = getattr(_fnx._fnx, "biadjacency_coo", None)
    if (
        native is not None
        and not isinstance(B, _nx.Graph)
        and not B.is_directed()
        and not B.is_multigraph()
    ):
        res = native(B, row_order, column_order, weight)
        if res is not None:
            import numpy as _np

            rows_a, cols_a, data_a, all_int = res
            if dtype is not None:
                arr = _np.array(data_a, dtype=dtype)
            elif all_int and data_a:
                arr = _np.array(data_a, dtype=_np.int64)
            else:
                arr = _np.array(data_a)
            A = sp.sparse.coo_array(
                (arr, (rows_a, cols_a)), shape=(nlen, mlen), dtype=dtype
            )
            try:
                return A.asformat(format)
            except ValueError as err:
                raise _nx.NetworkXError(
                    f"Unknown sparse array format: {format}"
                ) from err

    row_index = dict(zip(row_order, itertools.count()))
    col_index = dict(zip(column_order, itertools.count()))

    row, col, data = [], [], []
    if B.number_of_edges() != 0:
        for u, v, d in B.edges(row_order, data=True):
            ri = row_index.get(u)
            ci = col_index.get(v)
            if ri is not None and ci is not None:
                row.append(ri)
                col.append(ci)
                data.append(d.get(weight, 1))
    A = sp.sparse.coo_array((data, (row, col)), shape=(nlen, mlen), dtype=dtype)
    try:
        return A.asformat(format)
    except ValueError as err:
        raise _nx.NetworkXError(f"Unknown sparse array format: {format}") from err


def robins_alexander_clustering(G):
    """Robins & Alexander bipartite clustering ``4*C_4 / L_3`` of ``G``.

    br-r37-c1-niit0: re-exported from networkx as an ``@nx._dispatchable``, so
    calling it on an fnx graph round-trips the WHOLE graph through ``_fnx_to_nx``
    before nx counts four-cycles / three-paths with Python set operations (~1.1x
    slower than nx). Both counts are integer GRAPH INVARIANTS, so a native
    integer-CSR kernel (`robins_alexander_counts`) computes them with mark-array
    intersections and zero conversion; the float arithmetic
    (`(4.0 * (C_4_numer / 4)) / (L_3_numer / 2)`) is done here EXACTLY as nx, so
    the result is byte-identical. Directed / multigraph / nx-typed inputs delegate.
    """
    native = getattr(_fnx._fnx, "robins_alexander_counts", None)
    if (
        native is not None
        and not isinstance(G, _nx.Graph)
        and not G.is_directed()
        and not G.is_multigraph()
    ):
        counts = native(G)
        if counts is not None:
            # nx returns int 0 for these degenerate cases (checked before any
            # float division), so mirror that exactly.
            if G.order() < 4 or G.size() < 3:
                return 0
            c4_numer, l3_numer = counts
            L_3 = l3_numer / 2
            if L_3 == 0:
                return 0
            C_4 = c4_numer / 4
            return (4.0 * C_4) / L_3
    # nx-typed / directed / multigraph / kernel unavailable: delegate to nx.
    return _nx_bipartite.robins_alexander_clustering(
        G if isinstance(G, _nx.Graph) else _matching_nx_view(G)
    )


def latapy_clustering(G, nodes=None, mode="dot"):
    """Bipartite clustering coefficient (br-r37-c1-bipclust, cc).

    nx re-materialises ``set(G[u])`` for every (v, second-order-neighbour u) pair, i.e.
    O(V * |N(N(v))|) adjacency-view materialisations — the dominant cost on an fnx graph
    (the re-export ran nx's loop over the slow fnx views -> 0.84x). Snapshot each node's
    neighbour set ONCE (O(V)) and reuse it. Neighbour lists keep G's adjacency order, so
    ``nbrs2`` (a set comprehension) and the float-accumulation order are byte-identical to
    nx.
    """

    def cc_dot(nu, nv):
        return len(nu & nv) / len(nu | nv)

    def cc_min(nu, nv):
        return len(nu & nv) / min(len(nu), len(nv))

    def cc_max(nu, nv):
        return len(nu & nv) / max(len(nu), len(nv))

    modes = {"dot": cc_dot, "min": cc_min, "max": cc_max}
    try:
        cc_func = modes[mode]
    except KeyError as err:
        raise _nx.NetworkXError(
            "Mode for bipartite clustering must be: dot, min or max"
        ) from err

    adj = {n: list(nbrs) for n, nbrs in G.adjacency()}
    adj_set = {n: set(lst) for n, lst in adj.items()}
    if nodes is None:
        nodes = G
    ccs = {}
    for v in nodes:
        cc = 0.0
        nbrs2 = {u for nbr in adj[v] for u in adj[nbr]} - {v}
        for u in nbrs2:
            cc += cc_func(adj_set[u], adj_set[v])
        if cc > 0.0:  # len(nbrs2)>0
            cc /= len(nbrs2)
        ccs[v] = cc
    return ccs


clustering = latapy_clustering


def average_clustering(G, nodes=None, mode="dot"):
    """Average bipartite clustering coefficient (br-r37-c1-bipclust, cc).

    Re-exported from nx it ran nx's slow latapy_clustering (0.86x); routing through the
    concrete fast ``latapy_clustering`` above makes it a win. Byte-identical: same per-node
    ccs, same ``sum(...)/len(nodes)`` reduction.
    """
    if nodes is None:
        nodes = G
    ccs = latapy_clustering(G, nodes=nodes, mode=mode)
    return sum(ccs[v] for v in nodes) / len(nodes)


def degree_centrality(G, nodes):
    """Bipartite degree centrality (br-r37-c1-bipdc, cc).

    nx calls ``G.degree(top)`` then ``G.degree(bottom)`` — two per-nbunch DegreeView
    walks (~30us each on fnx) — re-export ran that at 0.41x. One batch ``dict(G.degree())``
    is native (~12us); filter it in G-node order, which is exactly the order nx's
    ``G.degree(nbunch)`` (nbunch_iter) yields, so the result dict is byte-identical.
    """
    top = set(nodes)
    bottom = set(G) - top
    all_deg = dict(G.degree())
    s = 1.0 / len(bottom)
    # nx yields G.degree(top) in nbunch_iter order = set(top) iteration order (filtered to
    # G), then G.degree(bottom); mirror that exactly so the result dict is byte-identical.
    centrality = {n: all_deg[n] * s for n in top if n in all_deg}
    s = 1.0 / len(top)
    centrality.update({n: all_deg[n] * s for n in bottom if n in all_deg})
    return centrality


def node_redundancy(G, nodes=None):
    """Node redundancy coefficients ``{node: rc(v)}`` for bipartite ``G``.

    br-r37-c1-g6wla: re-exported from networkx as an ``@nx._dispatchable``, so
    calling it on an fnx graph round-trips the WHOLE graph through ``_fnx_to_nx``
    before nx counts, per node, the neighbour pairs sharing another common
    neighbour using Python set intersections (~1.16x slower than nx). ``rc(v) =
    2*overlap / (deg*(deg-1))`` where ``overlap`` is an integer GRAPH INVARIANT,
    so a native integer-CSR kernel (`node_redundancy_overlaps`) counts it with
    mark-array intersections + early exit and zero conversion; the float division
    is done here EXACTLY as nx so the result is byte-identical. The default
    ``nodes=None`` (all nodes) case takes the native path; an explicit ``nodes``
    subset, nx-typed / directed / multigraph inputs delegate to nx.
    """
    native = getattr(_fnx._fnx, "node_redundancy_overlaps", None)
    if (
        native is not None
        and nodes is None
        and not isinstance(G, _nx.Graph)
        and not G.is_directed()
        and not G.is_multigraph()
    ):
        counts = native(G)
        if counts is not None:
            # nx checks all requested nodes have >=2 neighbours BEFORE computing
            # anything and raises a single NetworkXError otherwise; mirror that.
            if any(deg < 2 for (_overlap, deg) in counts):
                raise _nx.NetworkXError(
                    "Cannot compute redundancy coefficient for a node"
                    " that has fewer than two neighbors."
                )
            # `counts` is in node order (== list(G)); dict key order matches nx.
            return {
                node: (2 * overlap) / (deg * (deg - 1))
                for node, (overlap, deg) in zip(G, counts)
            }
    # nx-typed / directed / multigraph / explicit nodes / unavailable: delegate.
    return _nx_bipartite.node_redundancy(
        G if isinstance(G, _nx.Graph) else _matching_nx_view(G), nodes
    )


def minimum_weight_full_matching(G, top_nodes=None, weight="weight"):
    """Minimum-weight full matching of bipartite ``G`` (rectangular LAP).

    br-r37-c1-n4dwd: re-exported from networkx as an ``@nx._dispatchable``, so
    calling it on an fnx graph round-trips the WHOLE graph through ``_fnx_to_nx``
    before nx builds the biadjacency matrix and defers to
    ``scipy.optimize.linear_sum_assignment`` (~4x slower than nx). Run nx's EXACT
    algorithm IN-PROCESS on the fnx graph using the already-native
    :func:`sets` and :func:`biadjacency_matrix` (both byte-exact) plus the same
    deterministic SciPy LAP solver — no conversion. Byte-identical: the bipartite
    set split, the row/column ordering (``list(left)`` / ``list(right)``), the
    inf-padded weight matrix, and the SciPy assignment all match nx exactly
    (verified across heavy integer-weight tie cases). nx-typed inputs delegate.
    """
    if isinstance(G, _nx.Graph):
        return _nx_bipartite.minimum_weight_full_matching(G, top_nodes, weight)
    import numpy as _np
    import scipy as _sp

    left, right = sets(G, top_nodes)
    U = list(left)
    V = list(right)
    # Inf where edges are missing (not zero), exactly as nx.
    weights_sparse = biadjacency_matrix(
        G, row_order=U, column_order=V, weight=weight, format="coo"
    )
    weights = _np.full(weights_sparse.shape, _np.inf)
    weights[weights_sparse.row, weights_sparse.col] = weights_sparse.data
    left_matches = _sp.optimize.linear_sum_assignment(weights)
    d = {U[u]: V[v] for u, v in zip(*left_matches)}
    d.update({v: u for u, v in d.items()})
    return d


def _spectral_bipartivity_nx_copy(B):
    """Weight-preserving fnx->nx copy for the spectral_bipartivity delegate path
    (directed / multigraph), which needs edge weights and the matching graph
    type."""
    if B.is_multigraph():
        H = _nx.MultiDiGraph() if B.is_directed() else _nx.MultiGraph()
        H.add_nodes_from(B)
        H.add_edges_from(B.edges(keys=True, data=True))
    else:
        H = _nx.DiGraph() if B.is_directed() else _nx.Graph()
        H.add_nodes_from(B)
        H.add_edges_from(B.edges(data=True))
    return H


def spectral_bipartivity(G, nodes=None, weight="weight"):
    """Spectral bipartivity measure of bipartite ``G``.

    br-r37-c1-1h238: re-exported from networkx as an ``@nx._dispatchable``, so on
    an fnx graph it converts the WHOLE graph then forms TWO dense matrix
    exponentials (`expm(A)` and `expm(-A)`, each O(n^3) Pade) — ~430ms at n=270.
    But the measure is `trace(cosh A) / trace(exp A)` for the whole-graph case
    (`nodes=None`) and a ratio of `expm` DIAGONALS per node otherwise — both
    expressible from the symmetric spectrum alone. Compute one eigendecomposition
    of the (symmetric, undirected) adjacency: `nodes=None` uses
    `eigvalsh` -> `sum(cosh λ)/sum(exp λ)`; per-node uses `eigh` -> diagonals
    `Σ_k V_ik² e^{λ_k}` / `Σ_k V_ik² cosh(λ_k)`. ~90x faster, agreeing with nx's
    expm result to far beyond the module's round-6 conformance bar. Directed /
    multigraph / nx-typed inputs delegate to nx (non-symmetric / general expm).
    """
    if isinstance(G, _nx.Graph):
        return _nx_bipartite.spectral_bipartivity(G, nodes, weight)
    if G.is_directed() or G.is_multigraph():
        return _nx_bipartite.spectral_bipartivity(
            _spectral_bipartivity_nx_copy(G), nodes, weight
        )
    if len(G) > 0:
        try:
            color(G)
        except _nx.NetworkXError:
            pass
        else:
            if nodes is None:
                return 1.0
            present = set(G)
            result = {}
            for node in nodes:
                if node not in present:
                    raise KeyError(node)
                result[node] = 1.0
            return result
    import numpy as _np

    nodelist = list(G)
    A = _fnx.to_numpy_array(G, nodelist, weight=weight)
    if nodes is None:
        lam = _np.linalg.eigvalsh(A)
        return float(_np.cosh(lam).sum() / _np.exp(lam).sum())
    lam, V = _np.linalg.eigh(A)
    v2 = V * V
    exp_diag = v2 @ _np.exp(lam)
    cosh_diag = v2 @ _np.cosh(lam)
    index = {n: i for i, n in enumerate(nodelist)}
    return {n: cosh_diag[index[n]] / exp_diag[index[n]] for n in nodes}


def color(G):
    """Return a two-coloring ``{node: 0|1}`` of bipartite graph ``G``.

    br-r37-c1-r175x: re-exported nx ``@nx._dispatchable`` -> ~8.6x slower on an
    fnx graph (whole-graph _fnx_to_nx conversion). networkx's exact BFS coloring
    run in-process (using fnx-native ``isolates``) -- byte-identical (values and
    BFS-order dict keys). Raises NetworkXError on a non-bipartite graph exactly
    as nx does.
    """
    if G.is_directed():
        import itertools

        def neighbors(v):
            return itertools.chain.from_iterable(
                [G.predecessors(v), G.successors(v)]
            )

    else:
        neighbors = G.neighbors

    color = {}
    for n in G:  # handle disconnected graphs
        if n in color or len(G[n]) == 0:  # skip isolates
            continue
        queue = [n]
        color[n] = 1
        while queue:
            v = queue.pop()
            c = 1 - color[v]
            for w in neighbors(v):
                if w in color:
                    if color[w] == color[v]:
                        raise _nx.NetworkXError("Graph is not bipartite.")
                else:
                    color[w] = c
                    queue.append(w)
    color.update(dict.fromkeys(_fnx.isolates(G), 0))
    return color


def sets(G, top_nodes=None):
    """Return the two bipartite node sets ``(X, Y)`` of ``G``.

    br-r37-c1-r175x: re-exported nx ``@nx._dispatchable`` -> ~142x slower on an
    fnx graph (the whole-graph conversion dwarfs the O(V) set split). networkx's
    exact algorithm in-process (fnx-native connectivity check + :func:`color`).
    Same AmbiguousSolution (disconnected, no top_nodes) / NetworkXError contracts.
    """
    is_connected = _fnx.is_weakly_connected if G.is_directed() else _fnx.is_connected
    if top_nodes is not None:
        X = set(top_nodes)
        Y = set(G) - X
    else:
        if not is_connected(G):
            raise _nx.AmbiguousSolution(
                "Disconnected graph: Ambiguous solution for bipartite sets."
            )
        c = color(G)
        X = {n for n, is_top in c.items() if is_top}
        Y = {n for n, is_top in c.items() if not is_top}
    return (X, Y)


def is_bipartite_node_set(G, nodes):
    """Return True iff ``nodes`` and ``G - nodes`` are a bipartition of ``G``.

    br-r37-c1-r175x: re-exported nx ``@nx._dispatchable`` -> whole-graph
    conversion per call. networkx's exact algorithm in-process (fnx-native
    ``connected_components`` + the local :func:`sets`). Same AmbiguousSolution
    on duplicate input nodes.
    """
    S = set(nodes)
    if len(S) < len(nodes):
        raise _nx.AmbiguousSolution(
            "The input node set contains duplicates.\n"
            "This may lead to incorrect results when using it in bipartite algorithms.\n"
            "Consider using set(nodes) as the input"
        )
    for cc in _fnx.connected_components(G):
        component = G.subgraph(cc).copy()
        X, Y = sets(component)
        if not (
            (X.issubset(S) and Y.isdisjoint(S))
            or (Y.issubset(S) and X.isdisjoint(S))
        ):
            return False
    return True


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

    # br-r37-c1-collabbatch: the undirected case takes the snapshot fast path
    # above; this fallback (directed B, since _weighted_projection_inprocess bails
    # on type(B) is not Graph) still paid a per-node ``add_node`` + per-edge
    # ``add_edge`` PyO3 round-trip (the construction tax). Collect the (node, attrs)
    # and (u, v, weight-dict) tuples and commit them via add_nodes_from /
    # add_edges_from in one bulk pass each — identical node/edge order and weights,
    # only the construction is batched. Code-only; bench deferred (disk-low).
    G.graph.update(B.graph)
    G.add_nodes_from((node, dict(B.nodes[node])) for node in nodes)

    edges = []
    for u in nodes:
        unbrs = set(B[u])
        nbrs2 = {n for nbr in unbrs for n in B[nbr] if n != u}
        for v in nbrs2:
            vnbrs = set(pred[v])
            common_degree = (len(B[n]) for n in unbrs & vnbrs)
            weight = sum(1.0 / (deg - 1) for deg in common_degree if deg > 1)
            edges.append((u, v, {"weight": weight}))
    G.add_edges_from(edges)
    return G


def projected_graph(B, nodes, multigraph=False, *, backend=None, **backend_kwargs):
    """Return the projection of B onto one of its node sets.

    Wraps ``networkx.algorithms.bipartite.projected_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "projected_graph", backend, backend_kwargs
    )
    # br-r37-c1-bpproj: de-delegate the common case (simple fnx Graph/DiGraph, no
    # multigraph). The delegated path ran nx's algorithm THROUGH fnx's slow
    # per-access adjacency views AND rebuilt the result via _from_nx_graph (~61%
    # of the time). Instead snapshot B's adjacency once via the native key-only
    # binding and build the fnx projection directly — same edge set (two nodes are
    # joined iff they share a common neighbour; for directed B the result is a
    # DiGraph and ``_native_adjacency_keys`` yields successors, exactly nx's
    # ``B[u]``). Projection is UNWEIGHTED so there is no float-summation order to
    # diverge — byte-exact. Multigraph / nx-typed B keep the delegation path.
    nak = getattr(B, "_native_adjacency_keys", None)
    if not multigraph and nak is not None and type(B) in (_fnx.Graph, _fnx.DiGraph):
        adj = {node: nbrs for node, nbrs in nak()}
        G = _fnx.DiGraph() if type(B) is _fnx.DiGraph else _fnx.Graph()
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
