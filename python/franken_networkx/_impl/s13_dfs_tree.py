

def dfs_tree(G, source=None, depth_limit=None, *, sort_neighbors=None):
    """Return DFS tree rooted at source.

    Private-root inputs use the Python DFS stream with the raw depth limit;
    native-root inputs retain their binding-specific normalization below.

    br-r37-c1-c4agn: hash-check on source for nx-shaped TypeError
    parity on unhashable inputs.

    br-r37-c1-bfs-depth: nx returns a tree containing just the
    source node when depth_limit is negative (no descent allowed).
    The Rust binding raised OverflowError. Coerce negative
    depth_limit to 0 so the Rust path sees a valid unsigned and
    produces the matching single-node tree.
    """
    if _point_query_uses_private_rows(G):
        T = DiGraph()
        if source is None:
            T.add_nodes_from(G)
        else:
            T.add_node(source)
        T.add_edges_from(_py_dfs_edges(G, source, depth_limit, sort_neighbors))
        return T
    # br-r37-c1-nwkg0: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if source is not None:
        _HASH_PROBE.get(source)
    if depth_limit is not None:
        try:
            if int(depth_limit) < 0:
                depth_limit = 0
        except (TypeError, ValueError):
            pass
    try:
        if sort_neighbors is not None:
            T = DiGraph()
            if source is None:
                T.add_nodes_from(G)
            else:
                T.add_node(source)
            for u, v in _py_dfs_edges(G, source, depth_limit, sort_neighbors):
                T.add_edge(u, v)
            return T
        return _dfs_tree_raw(G, source=source, depth_limit=depth_limit)
    except NodeNotFound as exc:
        raise _traversal_missing_source_error(G, source) from exc


# Algorithm functions — reciprocity (wrapped to match NetworkX API)
def overall_reciprocity(G, *, backend=None, **backend_kwargs):
    """Compute the reciprocity for the whole graph."""
    _validate_backend_dispatch_keywords(
        "overall_reciprocity", backend, backend_kwargs
    )
    if G.is_multigraph() and not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected multigraph type")

    n_all_edge = G.number_of_edges()
    if n_all_edge == 0:
        raise NetworkXError("Not defined for empty graphs")

    # br-r37-c1-5gfx7: directed fast path. The original
    # ``G.to_undirected().number_of_edges()`` clones the whole graph
    # — fnx materializes a fresh undirected graph (O(|V|+|E|) copy)
    # vs nx's thin view. For directed inputs we can _count reciprocal
    # pairs directly: iterate edges once, check if (v, u) is also
    # in the edge set. The math:
    #   n_overlap_edge = 2 * |{(u, v) ∈ E : (v, u) ∈ E, u ≠ v}|
    # which equals (n_all_edge - n_undirected_edges) * 2 since each
    # reciprocal directed pair collapses to one undirected edge.
    if G.is_directed() and not G.is_multigraph():
        edge_set = {(u, v) for u, v in G.edges() if u != v}
        reciprocal_pairs = sum(1 for u, v in edge_set if (v, u) in edge_set)
        # Each reciprocal pair contributes 2 directed edges to the
        # overlap (since the _count is symmetric: (u,v) and (v,u) both
        # match). The sum above counts each pair twice (once as (u,v),
        # once as (v,u)), so reciprocal_pairs IS already n_overlap_edge.
        return reciprocal_pairs / n_all_edge

    n_overlap_edge = (n_all_edge - G.to_undirected().number_of_edges()) * 2
    return n_overlap_edge / n_all_edge


def _reciprocity_value_for_node(G, node):
    # br-r37-c1-o4f52: bypass _private_aware_neighbors wrapper for the
    # common case (plain DiGraph, no private storage). Raw bindings
    # _DIGRAPH_PREDECESSORS / _DIGRAPH_SUCCESSORS were captured at
    # module load before any wrapper attached. Same wrapper-bypass
    # family as find_cliques (lgyq8) and common_neighbors (qkq2h).
    if (
        isinstance(G, DiGraph)
        and not _has_networkx_private_storage(G)
    ):
        pred = set(_DIGRAPH_PREDECESSORS(G, node))
        succ = set(_DIGRAPH_SUCCESSORS(G, node))
    else:
        pred = set(G.predecessors(node))
        succ = set(G.successors(node))
    overlap = pred & succ
    n_total = len(pred) + len(succ)
    if n_total == 0:
        return None
    return 2 * len(overlap) / n_total


def reciprocity(G, nodes=None, *, backend=None, **backend_kwargs):
    """Compute reciprocity for a directed graph.

    If *nodes* is None, return the overall reciprocity of the graph (float).
    If *nodes* is a single node, return the reciprocity for that node (float).
    If *nodes* is an iterable of nodes, return a dict mapping each node to
    its reciprocity.  Matches ``networkx.reciprocity``.
    """
    _validate_backend_dispatch_keywords("reciprocity", backend, backend_kwargs)
    if nodes is None:
        return overall_reciprocity(G)

    if G.is_multigraph() and not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected multigraph type")
    if not G.is_directed():
        raise AttributeError(f"'{type(G).__name__}' object has no attribute 'predecessors'")

    try:
        if nodes in G:
            reciprocity_value = _reciprocity_value_for_node(G, nodes)
            if reciprocity_value is None:
                raise NetworkXError("Not defined for isolated nodes.")
            return reciprocity_value
    except TypeError:
        pass

    try:
        iterator = iter(nodes)
    except TypeError:
        raise NetworkXError(f"Node {nodes} is not in the graph.") from None

    # br-r37-c1-recipbatch: run the integer-CSR kernel over ALL requested nodes
    # in ONE native call instead of a per-node Python loop (each iteration did
    # 2 raw predecessor/successor binding calls + 2 set() builds — ~2x slower
    # than nx on large node sets). The native kernel returns 0.0 for an isolated
    # node, but nx's contract is None; convert 0.0 -> None only for nodes with
    # zero total degree (an O(1) check, indistinguishable from a real 0.0
    # otherwise). Gated to a plain DiGraph with no nx-private storage so the
    # returned dict's node-key objects hash-match the requested nodes; any other
    # shape keeps the proven per-node path.
    if type(G) is DiGraph and not _has_networkx_private_storage(G):
        valid = [node for node in iterator if node in G]
        if not valid:
            return {}
        batch = _fnx.reciprocity(G, valid)
        result = {}
        for node in valid:
            v = batch[node]
            if v == 0.0 and G.in_degree(node) == 0 and G.out_degree(node) == 0:
                result[node] = None
            else:
                result[node] = v
        return result

    result = {}
    for node in iterator:
        if node not in G:
            continue
        result[node] = _reciprocity_value_for_node(G, node)
    return result


_fnx_public_reciprocity = reciprocity


# Algorithm functions — Wiener index
def wiener_index(G, weight=None, *, backend=None, **backend_kwargs):
    """Returns the Wiener index of the given graph.

    Delegates the simple unweighted case to the Rust implementation
    (``franken_networkx._fnx.wiener_index``). Weighted inputs use the
    NetworkX parity bridge so callable weights, negative-weight errors,
    and multigraph parallel-edge semantics follow NetworkX exactly.
    """
    _validate_backend_dispatch_keywords("wiener_index", backend, backend_kwargs)
    # br-r37-c1-rg8jh: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)

    # br-wienerport: route the unweighted simple-graph case (the most
    # common one) through the native Rust port, which dispatches on
    # directedness.
    # For weighted graphs we stay in Python: ``g[u][v]["weight"] = ...``
    # mutations don't propagate to the Rust adjacency storage, so the
    # Rust dijkstra would silently use the original (often default-1)
    # weight. Multigraphs also stay in Python because the Rust binding
    # sees only the simple-graph collapse and would lose the
    # min-weight-across-parallel-edges semantics nx implements.
    if weight is None and not G.is_multigraph():
        # Empty graphs: nx raises NetworkXPointlessConcept via is_connected.
        # Trigger that contract BEFORE falling into the Rust path so the
        # parity is preserved.
        if G.number_of_nodes() == 0:
            raise NetworkXPointlessConcept(
                "Connectivity is undefined for the null graph."
            )
        value = _fnx.wiener_index(G, weight=None)
        if _math.isinf(value):
            return float("inf")
        # br-r37-c1-t26b4: nx returns int when the graph is directed
        # because nx returns ``total`` un-divided in that branch, and
        # int sums are integral. For undirected graphs nx applies
        # ``total / 2`` which always yields float (Python 3 division),
        # so we keep the Rust f64 result as-is. Coerce the directed
        # case back to int to match (directed_cycle: fnx 9.0 → nx 9).
        if (
            G.is_directed()
            and isinstance(value, float)
            and value.is_integer()
        ):
            return int(value)
        return value

    # Callable weight support evaluates shortest_path_length in-process
    # directly matching NetworkX semantics without cross-package delegation.
    if callable(weight):
        connected = is_strongly_connected(G) if G.is_directed() else is_connected(G)
        if not connected:
            return float("inf")
        spl = shortest_path_length(G, weight=weight)
        total = sum(_itertools.chain.from_iterable(nbrs.values() for node, nbrs in spl))
        return total if G.is_directed() else total / 2

    # Weighted simple graphs and multigraphs stay on the in-process
    # Python BFS/Dijkstra path below (NOT a fallback to nx — the
    # without_fallback parity test asserts this for string weights).
    connected = is_strongly_connected(G) if G.is_directed() else is_connected(G)
    if not connected:
        return float("inf")

    # br-r37-c1-lli0b: the per-source Dijkstra/BFS previously called
    # ``G.neighbors`` + ``G.get_edge_data`` INSIDE the hot loop, paying O(V*E)
    # AdjacencyView wrapper round-trips that made weighted wiener_index ~5.5x
    # SLOWER than nx. Snapshot the (Python-visible, so weight-mutation-fresh)
    # adjacency ONCE into a plain dict, then run the IDENTICAL BFS/Dijkstra over
    # it — same per-source order, same neighbour order, same float-sum order, so
    # the result is byte-exact with both the old path and nx, at O(E) build cost.
    # Multigraph parallel-edge min-weight and the negative-weight ValueError are
    # preserved.
    if weight is None:
        neighbor_keys = {node: list(G.neighbors(node)) for node in G}

        def _single_source_unweighted_lengths(source):
            lengths = {source: 0}
            queue = _deque([source])
            while queue:
                node = queue.popleft()
                next_distance = lengths[node] + 1
                for neighbor in neighbor_keys[node]:
                    if neighbor in lengths:
                        continue
                    lengths[neighbor] = next_distance
                    queue.append(neighbor)
            return lengths

        total = sum(
            sum(_single_source_unweighted_lengths(node).values()) for node in G
        )
    else:
        if G.is_multigraph():
            weighted_adj = {}
            for node in G:
                row = {}
                for neighbor in G.neighbors(node):
                    edge_data = G.get_edge_data(node, neighbor)
                    row[neighbor] = min(
                        attrs.get(weight, 1) for attrs in edge_data.values()
                    )
                weighted_adj[node] = row
        else:
            # br-r37-c1-wieneradjbug (cc): G.adjacency()'s per-edge attrs read the Rust
            # STORE, which is STALE for graphs built via add_edges_from(dict attrs)
            # (weights live only in the mirror until synced) -> weighted wiener silently
            # used default-1 weights (e.g. add_edges_from((u,v,{'weight':w})) then
            # wiener_index gave unit-weight results). edges(data=True) reads the MIRROR
            # (always fresh), so source the WEIGHTS from a bulk edges(data) map while
            # keeping adjacency()'s neighbor STRUCTURE/ORDER (so the per-source Dijkstra
            # discovery order + float-sum order stay byte-identical to nx). All O(E).
            _directed = G.is_directed()
            _edge_w = {}
            for _u, _v, _d in G.edges(data=True):
                _w = _d.get(weight, 1)
                _edge_w[(_u, _v)] = _w
                if not _directed:
                    _edge_w[(_v, _u)] = _w
            weighted_adj = {
                node: {nbr: _edge_w.get((node, nbr), 1) for nbr in nbrs}
                for node, nbrs in G.adjacency()
            }

        counter = _count()

        def _single_source_weighted_lengths(source):
            # An int 0, as networkx's Dijkstra seeds it: int weights then sum to
            # an int, which a directed graph returns un-divided (a 0.0 seed made
            # karate's 6456 come back as 6456.0; br-r37-c1-agwol).
            distances = {source: 0}
            queue = [(0, next(counter), source)]
            while queue:
                distance, _, node = _heappop(queue)
                if distance > distances[node]:
                    continue
                for neighbor, edge_weight in weighted_adj[node].items():
                    if isinstance(edge_weight, (int, float)) and edge_weight < 0:
                        raise ValueError(
                            "wiener_index does not support graphs with negative weights"
                        )
                    candidate = distance + edge_weight
                    if candidate < distances.get(neighbor, float("inf")):
                        distances[neighbor] = candidate
                        _heappush(queue, (candidate, next(counter), neighbor))
            return distances

        total = sum(
            sum(_single_source_weighted_lengths(node).values()) for node in G
        )

    return total if G.is_directed() else total / 2

# Algorithm functions — maximum spanning tree
from franken_networkx._fnx import (
    maximum_spanning_tree as _raw_maximum_spanning_tree,
)
# (maximum_spanning_edges wrapper defined earlier at the tree import site)


def minimum_spanning_tree(G, weight="weight", algorithm="kruskal", ignore_nan=False):
    """Return a minimum spanning tree or forest of an undirected weighted graph.

    Parameters
    ----------
    G : undirected graph
        An undirected graph.
    weight : str, optional (default='weight')
        Edge attribute key to use as weight.
    algorithm : str, optional (default='kruskal')
        Algorithm to use: 'kruskal', 'prim', or 'boruvka'.
    ignore_nan : bool, optional (default=False)
        If True, edges with NaN weights are ignored.

    Returns
    -------
    Graph
        A minimum spanning tree or forest.
    """
    # br-r37-c1-nwkg0: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-ow5fy: nx's @not_implemented_for('directed') raises
    # NetworkXNotImplemented; the Rust binding silently returned a
    # Graph result. MST is undefined on directed graphs (use
    # minimum_spanning_arborescence). Surface the standard error.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    # br-mstcallable: the Rust _raw_minimum_spanning_tree requires
    # ``weight`` to be a str; nx accepts a callable
    # ``weight(u, v, d) -> float``.  Route non-str weight values
    # through nx.  Same for algorithm != kruskal and ignore_nan
    # (Rust impl doesn't model NaN-skipping yet).
    # br-r37-c1-6vq1m: prim/boruvka used to delegate the whole tree to nx
    # (full fnx->nx conversion + nx's algorithm), but fnx's own
    # ``minimum_spanning_edges`` already has byte-exact native Prim / in-process
    # Borůvka kernels. nx's ``minimum_spanning_tree`` is literally "build a graph
    # from ``minimum_spanning_edges``", so assemble the tree from fnx's edge
    # generator instead — same construction, no conversion tax. Simple Graph +
    # str weight + ignore_nan=False only (NaN / callable-weight / multigraph still
    # delegate, exactly as ``minimum_spanning_edges`` itself falls back).
    # br-r37-c1-w0902: networkx builds the tree as ``G.__class__()``, so a Graph
    # subclass takes this construction for every algorithm (the native Kruskal
    # tree is a plain Graph); fnx views report ``__class__`` Graph.
    if (
        (algorithm in ("prim", "boruvka") or G.__class__ is not Graph)
        and isinstance(weight, str)
        and not ignore_nan
        and not G.is_multigraph()
    ):
        return _spanning_tree_from_edges(
            G,
            minimum_spanning_edges(
                G, algorithm=algorithm, weight=weight,
                keys=True, data=True, ignore_nan=ignore_nan,
            ),
        )
    if algorithm != "kruskal" or ignore_nan or not isinstance(weight, str):
        return _minimum_spanning_tree_via_parity(G, weight, algorithm, ignore_nan)
    # br-r37-c1-mstsync: previously we routed ANY graph with a weight
    # attribute through the nx parity path because the Rust kernel
    # read stale weights for post-construction mutations
    # (``g[u][v]['weight'] = w`` after the edge was added unweighted).
    # That detour was a >750× perf hit on weighted MST (e.g. 1300ms
    # vs nx's 1.7ms on a 200-node graph).  The
    # ``_sync_rust_edge_attrs`` helper (br-r37-c1-sjf4t) pushes the
    # Python-visible dict back into Rust storage so the Rust kernel
    # sees fresh weights.  Sync unconditionally — it's ~0.6ms even on
    # a 1k-edge graph, and skipping the conditional has_weight_attr
    # Python scan (~1.5ms) is a net win.
    # br-r37-c1-syncedgeonly: MST reads only edge weights, never node attrs —
    # edge-only sync skips the full sync's unguarded O(N) node-attr rebuild.
    _sync_rust_edge_attrs(G, edge_only=True)
    # Fractions, Decimals and large integers can have distinct values that
    # round to equal f64 weights. Validate the comparison domain as well as
    # finite/numeric values before either simple or multigraph selection.
    if not _spanning_weights_native_safe(G, weight):
        return _minimum_spanning_tree_via_parity(G, weight, algorithm, ignore_nan)
    # br-r37-c1-ij951: MultiGraph must return a keyed MultiGraph, not the
    # simple Graph produced by _raw_minimum_spanning_tree. The native helper
    # runs stable Kruskal directly over MultiGraph storage and returns None for
    # unsupported parity-sensitive shapes (row-display overrides, nonnumeric
    # weights), preserving the previous nx parity fallback.
    if isinstance(G, MultiGraph):
        result = _raw_multigraph_minimum_spanning_tree(G, weight=weight)
        if result is not None:
            return result
        return _minimum_spanning_tree_via_parity(G, weight, algorithm, ignore_nan)
    result = _raw_minimum_spanning_tree(G, weight=weight)
    # br-r37-c1-esr5k: for graphs built via ``add_nodes_from(range(n))`` (lazy
    # int display keys) the _raw_minimum_spanning_tree kernel can emit CANONICAL
    # STRING node keys ('0','1',...) instead of the original ints, changing the
    # node-label TYPE vs nx (edge set + weights are correct). Every sibling
    # native algo (k_truss/condensation/complement/...) and minimum_spanning_edges
    # preserve the real node objects, so rebuild the tree from G's actual nodes
    # and the result's edges re-keyed by str-identity. Guarded so it is a no-op
    # whenever the kernel already returns the correct node objects.
    if any(_n not in G for _n in result):
        _node_by_str = {str(_n): _n for _n in G}
        _fixed = Graph()
        _fixed.add_nodes_from(G.nodes(data=True))
        for _u, _v, _d in result.edges(data=True):
            _fixed.add_edge(
                _node_by_str.get(str(_u), _u), _node_by_str.get(str(_v), _v), **_d
            )
        result = _fixed
    # br-r37-c1-mstminattr: the native binding preserves edge attrs + node
    # identity but NOT graph-level or node attributes; nx's minimum_spanning_tree
    # copies G.graph and every node's data (and the _from_nx_graph parity path it
    # replaces did too). Sibling of the maximum_spanning_tree fix
    # (br-r37-c1-mstmaxnative) — minimum was left dropping them. Restore so the
    # native fast path stays byte-identical to nx.
    if G.graph:
        result.graph.update(dict(G.graph))
    for _node, _attrs in G.nodes(data=True):
        if _attrs:
            result.nodes[_node].update(_attrs)
    return result


def _spanning_tree_from_edges(G, edges):
    """networkx's spanning-tree construction: ``G.__class__()``, G's graph and
    node data, then the spanning edges in the order given."""
    cls = (
        G.__class__
        if isinstance(G, (Graph, DiGraph, MultiGraph, MultiDiGraph))
        else _concrete_class_for(G)
    )
    T = cls()
    if G.graph:
        T.graph.update(dict(G.graph))
    T.add_nodes_from((n, dict(d)) for n, d in G.nodes(data=True))
    if T.is_multigraph():
        T.add_edges_from((u, v, k, dict(d)) for u, v, k, d in edges)
    else:
        T.add_edges_from((u, v, dict(d)) for u, v, d in edges)
    return T


def _minimum_spanning_tree_via_parity(G, weight, algorithm, ignore_nan):
    """Build the minimum spanning tree in-process from minimum_spanning_edges."""
    edges = list(
        minimum_spanning_edges(
            G,
            algorithm=algorithm,
            weight=weight,
            keys=True,
            data=True,
            ignore_nan=ignore_nan,
        )
    )
    return _spanning_tree_from_edges(G, edges)


def _mst_has_weight_edge_attr(G, weight):
    """Return True if any edge in ``G`` has the named weight attribute.

    br-mstweightwrong: used to detect weighted graphs so the Rust
    Kruskal path (which returns suboptimal MSTs in some cases) is
    bypassed in favour of nx's reference implementation.
    """
    if not isinstance(weight, str):
        return False
    # br-r37-c1-hasattrnative: route through the native-backed helper (the old
    # G.edges(data=True) scan was ~420us per call — a third of multi_source_dijkstra_path).
    return _graph_has_edge_attribute(G, weight)


def maximum_spanning_tree(G, weight="weight", algorithm="kruskal", ignore_nan=False):
    """Return a maximum spanning tree or forest of an undirected weighted graph.

    Parameters
    ----------
    G : undirected graph
        An undirected graph.
    weight : str, optional (default='weight')
        Edge attribute key to use as weight.
    algorithm : str, optional (default='kruskal')
        Algorithm to use: 'kruskal', 'prim', or 'boruvka'.
    ignore_nan : bool, optional (default=False)
        If True, edges with NaN weights are ignored.

    Returns
    -------
    Graph
        A maximum spanning tree or forest.
    """
    # br-r37-c1-nwkg0: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-ow5fy: same directed-rejection guard as
    # minimum_spanning_tree.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    # br-r37-c1-w0902: prim / boruvka (and a Graph subclass, see
    # minimum_spanning_tree) build the tree from maximum_spanning_edges' native
    # Prim / in-process Boruvka as networkx does - they went through a full
    # networkx conversion both ways at 0.26-0.28x.
    if (
        (algorithm in ("prim", "boruvka") or G.__class__ is not Graph)
        and isinstance(weight, str)
        and not ignore_nan
        and not G.is_multigraph()
    ):
        return _spanning_tree_from_edges(
            G,
            maximum_spanning_edges(
                G, algorithm=algorithm, weight=weight,
                keys=True, data=True, ignore_nan=ignore_nan,
            ),
        )
    if algorithm != "kruskal" or ignore_nan or not isinstance(weight, str):
        return _maximum_spanning_tree_via_parity(G, weight, algorithm, ignore_nan)
    # MultiGraph results must keep parallel-edge / keyed-adjacency structure
    # (the Rust kernel collapses to a plain Graph) — route through nx.
    if isinstance(G, MultiGraph):
        return _maximum_spanning_tree_via_parity(G, weight, algorithm, ignore_nan)
    # br-r37-c1-mstmaxnative: the native maximum Kruskal kernel is now optimal
    # AND nx-ordered for weighted inputs (verified on a 60-graph golden incl.
    # tie-heavy integer weights: 0 edge-set / total-weight / node-order
    # mismatches). The old ``_mst_has_weight_edge_attr`` bypass to nx was a stale
    # leftover from br-mstweightwrong — fixed alongside the minimum kernel
    # (c96a96161) but never removed here, leaving weighted maximum_spanning_tree
    # ~3.2x slower than nx (full nx compute + ``_from_nx_graph`` rebuild). Mirror
    # ``minimum_spanning_tree``: sync post-creation weight mutations into Rust,
    # reject NaN/inf weights (nx error contract), then run the native kernel.
    # br-r37-c1-syncedgeonly: edge-only sync (reads edge weights, not node attrs).
    _sync_rust_edge_attrs(G, edge_only=True)
    # Share minimum_spanning_tree's exact comparison-domain admission.
    if not _spanning_weights_native_safe(G, weight):
        return _maximum_spanning_tree_via_parity(G, weight, algorithm, ignore_nan)
    result = _raw_maximum_spanning_tree(G, weight=weight)
    # br-r37-c1-7t11e: sibling of br-r37-c1-esr5k — for range-built graphs (lazy
    # int display keys) the native kernel can emit canonical STRING node keys
    # instead of the original ints. Rebuild from G's actual nodes + re-keyed
    # edges when the result has foreign-typed nodes; no-op otherwise.
    if any(_n not in G for _n in result):
        _node_by_str = {str(_n): _n for _n in G}
        _fixed = Graph()
        _fixed.add_nodes_from(G.nodes(data=True))
        for _u, _v, _d in result.edges(data=True):
            _fixed.add_edge(
                _node_by_str.get(str(_u), _u), _node_by_str.get(str(_v), _v), **_d
            )
        result = _fixed
    # The native binding preserves edge attrs + node identity but not graph-level
    # or node attributes; nx's maximum_spanning_tree copies G.graph and every
    # node's data (and the _from_nx_graph parity path this replaces did too).
    # Restore them so the native fast path stays byte-identical to nx.
    if G.graph:
        result.graph.update(dict(G.graph))
    for _node, _attrs in G.nodes(data=True):
        if _attrs:
            result.nodes[_node].update(_attrs)
    return result


def _maximum_spanning_tree_via_parity(G, weight, algorithm, ignore_nan):
    """Build the maximum spanning tree in-process from maximum_spanning_edges."""
    edges = list(
        maximum_spanning_edges(
            G,
            algorithm=algorithm,
            weight=weight,
            keys=True,
            data=True,
            ignore_nan=ignore_nan,
        )
    )
    return _spanning_tree_from_edges(G, edges)


def _greedy_color_structural_nx(G, strategy, interchange):
    # br-r37-c1-gcstruct / br-r37-c1-hf7zh: structural-only nx delegation
    # lives in this private helper so the public ``greedy_color`` wrapper
    # stays free of direct ``_nx.*`` references (classifier keeps it
    # PY_WRAPPER, not NX_DELEGATED). greedy_color is structure-only, so a
    # cheap structural ``nx.Graph`` (nodes in order + edges) is byte-identical
    # to the faithful conversion for these strategies.
    # br-r37-c1-vevfq (directed): a DIRECTED graph needs a DIRECTED structural copy.
    # The gate below used to exclude directed entirely, on the grounds that "structural
    # would drop parallel edges / direction" - true of an nx.Graph copy, but direction
    # survives an nx.DiGraph one, and greedy_color is still structure-only.
    if G.is_multigraph():
        from franken_networkx.backend import _fnx_to_nx
        _H = _fnx_to_nx(G)
    else:
        _H = _nx.DiGraph() if G.is_directed() else _nx.Graph()
        _H.add_nodes_from(G)
        _H.add_edges_from(G.edges())
    try:
        return _nx.greedy_color(_H, strategy=strategy, interchange=interchange, backend="networkx")
    except Exception as exc:
        _raise_translated_networkx_exception(exc)


def greedy_color(
    G, strategy="largest_first", interchange=False, *, backend=None, **backend_kwargs
):
    """Color a graph using various greedy strategies.

    Parameters
    ----------
    G : graph
        A NetworkX graph.
    strategy : str or function, optional (default='largest_first')
        Greedy strategy to use. Options include 'largest_first',
        'smallest_last', 'independent_set', 'connected_sequential_bfs',
        'connected_sequential_dfs', 'saturation_largest_first', or a function.
    interchange : bool, optional (default=False)
        Use interchange optimization (only valid with 'saturation_largest_first').

    Returns
    -------
    dict
        Dictionary mapping nodes to colors (integers starting at 0).
    """
    _validate_backend_dispatch_keywords("greedy_color", backend, backend_kwargs)
    # br-r37-c1-gr1ct: materialize SubgraphView so the Rust shortcut
    # sees the filtered nodes/edges (view family).
    G = _coerce_arg_to_fnx_graph(G)
    if interchange or callable(strategy):
        return _greedy_color_structural_nx(G, strategy, interchange)
    # br-r37-c1-fki5h: the Rust greedy_color now mirrors nx's
    # ``sorted(G, key=G.degree, reverse=True)`` tie-breaking (stable
    # sort, insertion-order ties) for the default ``"largest_first"``
    # strategy. Verified key-order + color-value parity vs nx on BA
    # fixtures up to 100 nodes. Other strategies (smallest_last,
    # random_sequential, DSATUR, connected_sequential_*) still
    # diverge from nx tie-breaking and stay on the delegation path.
    if strategy == "largest_first" and not G.is_multigraph():
        # br-r37-c1-vevfq: DIRECTED graphs get their own kernel. networkx's directed
        # colouring differs from the undirected one in exactly two places - it orders by
        # `G.degree`, which is IN + OUT on a DiGraph, and reads neighbour colours from
        # `G[u]`, which is SUCCESSORS ONLY - so the undirected kernel cannot serve them
        # and they were paying an fnx->nx conversion instead (0.136x against networkx).
        # Verified 0 divergences over 300 random digraphs, including permuted node
        # insertion order, single-node and edgeless graphs.
        try:
            if G.is_directed():
                return _raw_greedy_color_directed(G)
            return _raw_greedy_color(G, "largest_first")
        except Exception:
            pass
    # br-r37-c1-vevfq: other strategies still delegate (Rust ordering
    # diverges from nx).
    # br-r37-c1-gcstruct: greedy_color is structure-only (no node/edge attrs or
    # weights affect the coloring), so run nx's strategy on a cheap STRUCTURAL
    # nx.Graph (G's nodes in order + edges) instead of the faithful
    # _networkx_graph_for_parity conversion (~half of the call). The node +
    # adjacency iteration order is preserved, so the order-sensitive coloring
    # (these strategies pop nodes from degree buckets in CPython set order) is
    # byte-identical — verified struct==faithful for every str strategy.
    # Multigraph keeps the faithful path (structural would drop parallel edges).
    #
    # br-r37-c1-vevfq (directed): DIRECTED graphs used to be excluded here too and paid
    # the FAITHFUL conversion, measuring 0.136x against networkx - 19,304,753 against
    # 2,624,760 Ir/call on a 250-node DiGraph. Direction survives an nx.DiGraph
    # structural copy, and the result is byte-identical for these strategies: 1280 cases
    # swept over 8 strategies x 40 seeds x permuted node insertion order x attributed
    # graphs, comparing exceptions by type AND args, 0 divergences.
    #
    # This does NOT make the row a win. It is ~2.5x self and still lands near 0.22x,
    # because even the structural copy costs more than networkx's entire call. Closing it
    # needs a native directed kernel, which is what the undirected class has (8.7x).
    if not G.is_multigraph():
        # br-r37-c1-rqsur: the connected_sequential_{bfs,dfs} strategies
        # traverse the graph's adjacency in iteration order, so the cheap
        # structural conversion below (``add_edges_from(G.edges())`` rebuilds
        # adj in node-major *edge* order, not G's per-node *adj-insertion*
        # order) diverges from nx whenever G's node insertion order is a
        # non-identity permutation of its labels. Route those through the
        # faithful ``_fnx_to_nx`` conversion, which emits edges so the
        # converted graph's per-node adj order matches G exactly
        # (br-r37-c1-sgnab). Other str strategies (largest_first handled
        # natively above; smallest_last / saturation / random_sequential /
        # independent_set) depend only on degree/saturation buckets, not adj
        # iteration order, so the structural shortcut stays byte-identical.
        # The native traversal below uses connected_components, which is undirected-only;
        # directed graphs fall through to the structural helper, where networkx raises
        # NetworkXNotImplemented exactly as it does today (covered by the sweep above).
        if not G.is_directed() and strategy in (
            "connected_sequential",
            "connected_sequential_bfs",
            "connected_sequential_dfs",
        ):
            # br-cc-gc-connected: run the connected_sequential coloring NATIVELY
            # instead of the faithful ``_fnx_to_nx`` conversion, which was the
            # WHOLE 0.32x tax (~1.3ms convert + 0.66ms color vs nx's 0.66ms). The
            # BFS/DFS traversal order from fnx's native ``connected_components`` +
            # ``bfs_edges``/``dfs_edges`` matches nx EXACTLY (verified byte-exact
            # across bfs/dfs x single/multi-component), and greedy colour
            # assignment reads neighbour colours as an ORDER-INDEPENDENT set
            # (native ``G.neighbors``), so the {node: colour} result is
            # byte-identical. (interchange=True already delegated above.)
            traversal_dfs = strategy == "connected_sequential_dfs"
            colors = {}
            order = []
            for component in connected_components(G):
                source = next(iter(component))
                order.append(source)
                tree = (
                    dfs_edges(G, source)
                    if traversal_dfs
                    else bfs_edges(G, source)
                )
                for _start, end in tree:
                    order.append(end)
            for u in order:
                neighbor_colors = {
                    colors[v] for v in G.neighbors(u) if v in colors
                }
                for color in _count():
                    if color not in neighbor_colors:
                        break
                colors[u] = color
            return colors
        return _greedy_color_structural_nx(G, strategy, interchange)
    return _greedy_color_structural_nx(G, strategy, interchange)


# Algorithm functions — condensation (wrapped to match NetworkX API)
from franken_networkx._fnx import (
    condensation as _condensation_raw,
    condensation_nx_ordered as _condensation_nx_ordered,
)


def condensation(G, scc=None):
    """Return the condensation of G.

    The condensation of a directed graph contracts each strongly connected
    component into a single node. The resulting graph is a DAG.

    Returns a DiGraph C where each node has a 'members' attribute (the set
    of original nodes in that SCC) and C.graph['mapping'] maps original
    nodes to SCC indices. This matches the NetworkX API.
    """
    if scc is not None:
        cond_dg = DiGraph()
        mapping = {}
        members = {}

        cond_dg.graph["mapping"] = mapping
        if len(G) == 0:
            return cond_dg

        for idx, component in enumerate(scc):
            members[idx] = component
            for node in component:
                mapping[node] = idx

        cond_dg.add_nodes_from(range(idx + 1))

        for u, v in G.edges():
            cu = mapping[u]
            cv = mapping[v]
            if cu != cv:
                cond_dg.add_edge(cu, cv)

        for idx, member_set in members.items():
            cond_dg.nodes[idx]["members"] = member_set
        return cond_dg

    G = _coerce_arg_to_fnx_graph(G)
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    # br-cc-cond-scc: the native `condensation_nx_ordered` kernel computes SCCs
    # fast but then spends ~5x nx's build time MATERIALISING the per-SCC
    # `members` Python sets from Rust (0.59-0.70x for few-but-large SCCs). fnx's
    # native `strongly_connected_components` ALREADY yields Python sets in nx's
    # exact order (verified identical), so run nx's own condensation build over
    # them: the `members` sets come straight from the SCC result (no re-
    # materialisation) and the edge set is one batched `add_edges_from`. Byte-
    # exact node/edge order + mapping + members vs nx; 1.24-2.28x (was 0.59-0.93x).
    scc = strongly_connected_components(G)
    mapping = {}
    members = {}
    C = DiGraph()
    i = -1
    for i, component in enumerate(scc):
        members[i] = component
        mapping.update((n, i) for n in component)
    C.add_nodes_from(range(i + 1))
    C.add_edges_from(
        (mapping[u], mapping[v]) for u, v in G.edges() if mapping[u] != mapping[v]
    )
    C.graph["mapping"] = mapping
    set_node_attributes(C, members, "members")
    return C


# Algorithm functions — all-pairs shortest paths
from franken_networkx._fnx import (
    all_pairs_shortest_path as _raw_all_pairs_shortest_path,
    all_pairs_shortest_path_length as _raw_all_pairs_shortest_path_length,
    shortest_path_length_matrix as _raw_shortest_path_length_matrix,
)


def all_pairs_shortest_path(G, cutoff=None, *, backend=None, **backend_kwargs):
    """Return an iterator of (source, shortest-paths-dict) pairs.

    Compute only the consumed source rows, using the existing single-source
    routes. Graph/view changes between yields are visible, as in NetworkX.
    """
    _validate_backend_dispatch_keywords(
        "all_pairs_shortest_path", backend, backend_kwargs
    )
    # Materializing every source's paths before the first yield can allocate
    # cubic output for a deep path, even when the caller requests just one row.
    # Do not snapshot/coerce the graph here: source iteration and each query
    # must observe the current graph, including live views and private rows.
    for source in G:
        yield source, single_source_shortest_path(G, source, cutoff=cutoff)


def all_pairs_shortest_path_length(G, cutoff=None, *, backend=None, **backend_kwargs):
    """Return an iterator of (source, shortest-path-length-dict) pairs.

    Compute only consumed source rows and observe changes between yields.
    Use shortest_path_length_matrix for explicitly packed bulk output.
    """
    _validate_backend_dispatch_keywords(
        "all_pairs_shortest_path_length", backend, backend_kwargs
    )
    for source in G:
        yield source, single_source_shortest_path_length(G, source, cutoff=cutoff)


def shortest_path_length_matrix(G, sources=None, cutoff=None):
    """Return dense unweighted shortest-path lengths for many sources.

    Rows follow ``sources`` (all graph nodes by default), columns follow
    ``list(G)``, and unreachable pairs contain ``-1``.  The returned
    ``numpy.int32`` array is a read-only view over the native packed result;
    call ``copy()`` only when a writable matrix is required.

    Unlike repeated :func:`single_source_shortest_path_length` calls, this
    builds one cache-friendly CSR adjacency and fills independent source rows
    in parallel without constructing a Python dict or integer object per pair.
    Assigned private storage and views over it use the authoritative Python
    rows instead of a native CSR snapshot.

    Refused dense-output or packed-bytes allocations raise ``MemoryError``.
    This does not impose a general budget on graph ingestion or BFS scratch.
    """
    private_rows = _point_query_uses_private_rows(G)
    if not private_rows:
        G = _coerce_arg_to_fnx_graph(G)
    nodelist = list(G)
    source_nodes = nodelist if sources is None else list(sources)
    for source in source_nodes:
        if source not in G:
            raise NodeNotFound(f"Source {source} is not in G")
    if cutoff is not None:
        try:
            if int(cutoff) < 0:
                cutoff = 0
        except (TypeError, ValueError):
            pass

    import numpy as _np

    if private_rows:
        # The native storage can deliberately disagree with assigned _adj /
        # _succ rows. Reuse the parity-exact source BFS without coercing them
        # away. Keep immutable packed backing just like the native result.
        matrix = _np.full((len(source_nodes), len(nodelist)), -1, dtype=_np.int32)
        positions = {node: column for column, node in enumerate(nodelist)}
        for row, source in enumerate(source_nodes):
            for target, distance in single_source_shortest_path_length(
                G, source, cutoff=cutoff
            ).items():
                matrix[row, positions[target]] = distance
        packed = matrix.tobytes()
    else:
        packed = _raw_shortest_path_length_matrix(G, source_nodes, cutoff)
    return _np.frombuffer(packed, dtype=_np.int32).reshape(
        (len(source_nodes), len(nodelist))
    )

# Algorithm functions — graph predicates & utilities
from franken_networkx._fnx import (
    is_empty,
    non_neighbors,
    all_triangles as _rust_all_triangles,
    enumerate_all_cliques as _raw_enumerate_all_cliques,
    find_cliques_recursive as _raw_find_cliques_recursive,
    chordal_graph_cliques as _raw_chordal_graph_cliques,
    chordal_graph_treewidth as _rust_chordal_graph_treewidth,
    make_max_clique_graph as _rust_make_max_clique_graph,
    ring_of_cliques,
)


def chordal_graph_cliques(G):
    """br-isokw: ``G`` matches nx; Rust binding used ``g``.

    br-chordalcliquetypes: nx.chordal_graph_cliques yields a generator
    of frozensets (one per maximal clique of the chordal graph). The
    Rust binding returned a list of lists, breaking both the iterator
    contract (``iter(r) is r`` etc.) and the set-operation contract
    (users could not intersect / union the cliques directly). Convert
    each inner list to frozenset and yield via a generator.

    br-r37-c1-xd6xi: nx accepts MultiGraph inputs and returns the
    maximal cliques of the underlying simple graph (parallel edges
    collapsed). The previous fnx implementation incorrectly rejected
    MultiGraph with NetworkXNotImplemented, even though nx has no
    @not_implemented_for guard on this function. Project the
    MultiGraph to a simple Graph before delegating to the Rust core
    so the algorithm matches nx's behavior on multigraph inputs.
    """
    # br-r37-c1-0555d: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        return _chordal_graph_cliques_inprocess(G)
    # br-r37-c1-9vzvv: nx's chordal_graph_cliques does NOT raise on every
    # non-chordal graph — it runs MCS per connected component and yields the
    # maximal cliques it finds (e.g. C4 -> [{0,1},{1,2},{0,2,3}]), raising
    # NetworkXError only when the MCS clique-completeness check fails mid-walk.
    # The native _raw_chordal_graph_cliques returns EMPTY for non-chordal, and
    # the previous fix delegated to nx (which the no-fallback conformance test
    # forbids). For non-chordal input, run nx's exact MCS algorithm in-process
    # on the fnx graph (no nx call) so the output and partial-yield-then-raise
    # behaviour match byte-for-byte. Chordal input keeps the fast native path.
    if not is_chordal(G):
        return _chordal_graph_cliques_inprocess(G)
    cliques = _raw_chordal_graph_cliques(G)
    def _gen():
        for c in cliques:
            yield frozenset(c)
    return _gen()


def _is_complete_simple_graph(G):
    """True iff G is complete; raises if self-loop present (nx _is_complete_graph)."""
    if number_of_selfloops(G) > 0:
        raise NetworkXError("Self loop found in _is_complete_graph()")
    n = G.number_of_nodes()
    if n < 2:
        return True
    return G.number_of_edges() == n * (n - 1) / 2


def _max_cardinality_node_local(G, choices, wanna_connect):
    """Port of nx ``_max_cardinality_node``: most connections into
    ``wanna_connect``, ties broken by ``choices`` iteration order."""
    max_number = -1
    max_cardinality_node = None
    for x in choices:
        number = len([y for y in G[x] if y in wanna_connect])
        if number > max_number:
            max_number = number
            max_cardinality_node = x
    return max_cardinality_node


def _chordal_graph_cliques_inprocess(G):
    """In-process port of nx ``chordal_graph_cliques`` (br-r37-c1-9vzvv).

    Runs maximum-cardinality search per connected component on the fnx graph,
    yielding maximal cliques as frozensets and raising NetworkXError if the
    graph is found non-chordal during the walk — identical to nx, but without
    calling ``nx.chordal_graph_cliques`` (so the no-fallback contract holds).
    """
    for component in connected_components(G):
        C = G.subgraph(component).copy()
        if C.number_of_nodes() == 1:
            if number_of_selfloops(C) > 0:
                raise NetworkXError("Input graph is not chordal.")
            yield frozenset(C.nodes())
            continue
        unnumbered = set(C.nodes())
        v = next(iter(C))
        unnumbered.remove(v)
        numbered = {v}
        clique_wanna_be = {v}
        while unnumbered:
            v = _max_cardinality_node_local(C, unnumbered, numbered)
            unnumbered.remove(v)
            numbered.add(v)
            new_clique_wanna_be = set(C.neighbors(v)) & numbered
            sg = C.subgraph(clique_wanna_be)
            if _is_complete_simple_graph(sg):
                new_clique_wanna_be.add(v)
                if not new_clique_wanna_be >= clique_wanna_be:
                    yield frozenset(clique_wanna_be)
                clique_wanna_be = new_clique_wanna_be
            else:
                raise NetworkXError("Input graph is not chordal.")
        yield frozenset(clique_wanna_be)


# br-ringlabels: the Rust ring_of_cliques used string labels like
# "0_0", "0_1", ... which broke drop-in parity — nx uses integer
# labels 0..n*k-1 with clique-bridge edges specifically at
# (i*k + 1, (i+1)*k % (n*k)). Shadow the Rust binding with a Python
# wrapper that mirrors nx's labelling + validation messages.
# br-r37-c1-c8xop: previously kept _rust_ring_of_cliques as a fallback
# reference "in case anything internal needs it" but nothing did. Removed.


def ring_of_cliques(num_cliques, clique_size):
    """Defines a ring of cliques graph.

    br-ringlabels / br-ringvalid: match nx exactly — integer node
    labels 0..num_cliques*clique_size-1 and nx's validation messages.
    The Rust binding emitted string labels "i_j" and error messages
    using ``num_cliques`` / ``clique_size`` parameter names that
    diverged from nx's human-friendly wording.
    """
    import itertools as _itertools
    if num_cliques < 2:
        raise NetworkXError("A ring of cliques must have at least two cliques")
    if clique_size < 2:
        raise NetworkXError("The cliques must have at least two nodes")
    # br-r37-c1-ringbatch: collect every clique's edges + the ring-link edge into
    # ONE list and commit through a single add_edges_from, instead of 2*num_cliques
    # separate add_edges_from/add_edge PyO3 calls. The edge order is identical to
    # nx's per-clique sequence (each clique's combinations followed by its ring
    # link), so node/adj insertion order — and thus the graph — is byte-identical.
    G = Graph()
    n_total = num_cliques * clique_size
    all_edges = []
    for i in range(num_cliques):
        all_edges.extend(
            _itertools.combinations(
                range(i * clique_size, i * clique_size + clique_size), 2
            )
        )
        all_edges.append((i * clique_size + 1, (i + 1) * clique_size % n_total))
    G.add_edges_from(all_edges)
    return G


def all_triangles(G, nbunch=None):
    """Yield unique triangles in an undirected graph.

    br-r37-c1-ulojb: previously routed nbunch=None to the Rust
    binding which produced triangles with unsorted vertex tuples
    (e.g. ``(0, 12, 3)``) and a non-nx iteration order. nx's
    contract yields ``(u, v, w)`` with insertion-id order
    ``id(u) < id(v) < id(w)``. Use the Python reference impl for
    both branches so the output matches nx exactly.
    """
    # br-r37-c1-scceager: all_triangles' body uses ``yield`` (generator), so
    # the directed-only check must run in this non-generator wrapper to raise
    # EAGERLY on the call (nx contract). Generator body in _all_triangles_impl.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    return _all_triangles_impl(G, nbunch)


def _all_triangles_impl(G, nbunch=None):
    # br-r37-c1-tri3snap: snapshot adjacency once into a plain dict
    # (``{u: nbrs}`` from G.adjacency(), no per-key copy) instead of
    # re-materialising the ``G.adj[u]`` view on every inner-loop access.
    # ``adj[u].keys()`` are still real dict_keys in G.adj order, so the
    # ``keys & keys`` set-intersection iteration order (and thus the yielded
    # triangle order) stays byte-identical to nx — only the repeated fnx
    # adjacency-view construction is eliminated (~6x self-speedup, 7.9x->1.65x).
    #
    # br-r37-c1-iowms: for an exact simple FNX ``Graph``, build the snapshot
    # from key-only rows (``_native_adjacency_keys`` -> ``{node: [nbr, ...]}``)
    # instead of ``G.adjacency()`` (which materialises an attr-bearing
    # ``{nbr: attrs}`` dict per node). ``dict.fromkeys(nbrs).keys()`` is a real
    # dict_keys whose hash-table layout depends only on the neighbour KEY
    # objects and their insertion order — identical to the attr-bearing dict's
    # keys — so the ``keys & keys`` set-intersection iteration order (and thus
    # the yielded triangle stream + tuple orientation) is byte-identical to nx.
    # Multigraph / filtered views (where the native key snapshot can diverge
    # from the live adjacency) fall back to the attr-bearing ``G.adjacency()``.
    _nak = getattr(G, "_native_adjacency_keys", None) if type(G) is Graph else None
    if _nak is not None:
        adj = {node: dict.fromkeys(nbrs) for node, nbrs in _nak()}
    else:
        adj = {node: nbrs for node, nbrs in G.adjacency()}
    if nbunch is None:
        nbunch_lookup = dict.fromkeys(G)
        relevant_nodes = nbunch_lookup
    else:
        nbunch_nodes = _global_nbunch_nodes(G, nbunch)
        nbunch_lookup = dict.fromkeys(nbunch_nodes)
        relevant_nodes = _itertools.chain(
            nbunch_lookup,
            (
                neighbor
                for node in nbunch_lookup
                for neighbor in G.neighbors(node)
                if neighbor not in nbunch_lookup
            ),
        )
    node_to_id = {node: index for index, node in enumerate(relevant_nodes)}

    for u in nbunch_lookup:
        u_id = node_to_id[u]
        # br-r37-c1-ulojb: use dict_keys directly (matching nx's
        # ``G._adj[u].keys()`` access) so the ``keys & keys`` set
        # intersection produces the same iteration order as nx.
        # Wrapping in ``set(...)`` first changes the resulting set's
        # internal layout, causing the inner ``for w in ...`` loop
        # to yield in a different order.
        u_neighbors = adj[u].keys()
        for v in u_neighbors:
            v_id = node_to_id.get(v, -1)
            if v_id <= u_id:
                continue
            v_neighbors = adj[v].keys()
            for w in v_neighbors & u_neighbors:
                if node_to_id.get(w, -1) > v_id:
                    yield (u, v, w)


def chordal_graph_treewidth(G):
    """Return the treewidth of a chordal graph."""
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.number_of_nodes() == 0:
        return -2
    return _rust_chordal_graph_treewidth(G)


def find_cliques(G, nodes=None):
    """Yield all maximal cliques in an undirected graph.

    _Generator function so the returned object is a true generator
    matching nx's contract (br-r37-c1-682kr).

    br-r37-c1-tvf43: run the nx-order iterative Bron-Kerbosch path
    locally for ``nodes=None`` instead of delegating to NetworkX or
    using the Rust binding's canonical clique ordering.
    """
    # br-r37-c1-scceager: find_cliques' body uses ``yield``, making this a
    # generator function — so the directed-only check must run in this
    # non-generator wrapper to raise EAGERLY on the call (nx contract), not
    # lazily on first iteration. The generator body lives in _find_cliques_impl.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    return _find_cliques_impl(G, nodes)


def _find_cliques_impl(G, nodes=None):
    # Conversion can snapshot private storage or a foreign graph. Like nx's
    # adjacency snapshot, it must observe edits made before the first next().
    G = _coerce_arg_to_fnx_graph(G)
    if nodes is None:
        nodes = []

    if len(G) == 0:
        return

    # br-r37-c1-tvf43: build adjacency via the raw Rust ``neighbors``
    # binding (``_GRAPH_NEIGHBORS`` captured before any Python wrappers
    # were applied) instead of ``G[u]`` (AtlasView with per-edge PyO3
    # attribute fetch). The set-comprehension preserves nx's exact
    # iteration order because elements are inserted in the same sequence
    # as nx's ``{v for v in G[u] if v != u}`` (the raw Rust call and
    # ``G[u]`` iterate in the same order — verified directly).
    #
    # /profiling-software-performance follow-up: bypass the per-call
    # ``_private_aware_neighbors`` + ``_neighbors_with_networkx_missing
    # _node_error`` wrappers when the graph has no nx-compatibility
    # private storage. cProfile on BA500 showed those wrappers were
    # ~30% of the total find_cliques time even though the slow path
    # never executes for normal graphs. Single ``_has_networkx_private
    # _storage`` check at function entry replaces |V| per-call checks.
    _raw = _raw_neighbors_dispatch(G)
    if _raw is not None and _raw_find_cliques_adjacency_sets is not None:
        adjacency = _raw_find_cliques_adjacency_sets(G)
    elif _raw is not None:
        adjacency = {u: {v for v in _raw(G, u) if v != u} for u in G}
    else:
        adjacency = {u: {v for v in G.neighbors(u) if v != u} for u in G}
    current_clique = nodes[:]
    candidates = set(G)

    for node in current_clique:
        if node not in candidates:
            raise ValueError(f"The given `nodes` {nodes} do not form a clique")
        candidates &= adjacency[node]

    if not candidates:
        yield current_clique[:]
        return

    subgraph = candidates.copy()
    stack = []
    current_clique.append(None)

    pivot = max(subgraph, key=lambda node: len(candidates & adjacency[node]))
    extension = candidates - adjacency[pivot]

    try:
        while True:
            if extension:
                selected = extension.pop()
                candidates.remove(selected)
                current_clique[-1] = selected
                selected_neighbors = adjacency[selected]
                subgraph_selected = subgraph & selected_neighbors
                if not subgraph_selected:
                    yield current_clique[:]
                else:
                    candidates_selected = candidates & selected_neighbors
                    if candidates_selected:
                        stack.append((subgraph, candidates, extension))
                        current_clique.append(None)
                        subgraph = subgraph_selected
                        candidates = candidates_selected
                        pivot = max(
                            subgraph, key=lambda node: len(candidates & adjacency[node])
                        )
                        extension = candidates - adjacency[pivot]
            else:
                current_clique.pop()
                subgraph, candidates, extension = stack.pop()
    except IndexError:
        pass


def enumerate_all_cliques(G):
    """Yield all cliques (not just maximal) in an undirected graph.

    _Generator function so the returned object is a true generator
    matching nx's contract (br-r37-c1-682kr).
    """
    # br-r37-c1-scceager: nx is @not_implemented_for('directed') — eager raise.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    def _gen():
        graph = _coerce_arg_to_fnx_graph(G)
        # Keep ordinary generator send() semantics while consuming native rows.
        for clique in _raw_enumerate_all_cliques(graph):
            yield clique

    return _gen()


def find_cliques_recursive(G, nodes=None):
    """Yield all maximal cliques in an undirected graph (recursive).

    Returns a true iterator matching nx's contract (br-r37-c1-682kr).

    br-r37-c1-fcrnative: port nx's exact recursive Bron-Kerbosch in PYTHON
    in-process instead of delegating (br-r37-c1-g71v3) or borrowing the iterative
    find_cliques order (br-r37-c1-scceager). Building ``adj`` from ``G[u]`` the
    same way nx does makes the CPython set-iteration tie-breaks (the pivot
    ``max(subg, ...)`` and ``cand - adj[u]``) identical to nx, so the clique
    SEQUENCE byte-matches. This also restores nx's EAGER ``ValueError`` for a
    ``nodes`` argument that is not a clique (the old generator-wrapped version
    raised lazily / not at all), and drops the per-call fnx->nx conversion.
    """
    # br-r37-c1-scceager: nx is @not_implemented_for('directed') — eager raise.
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    # --- eager part (runs on call, exactly like nx's function body) ---
    if len(G) == 0:
        return iter([])

    adj = {u: {v for v in G[u] if v != u} for u in G}

    Q = nodes[:] if nodes is not None else []
    cand_init = set(G)
    for node in Q:
        if node not in cand_init:
            raise ValueError(f"The given `nodes` {nodes} do not form a clique")
        cand_init &= adj[node]

    if not cand_init:
        return iter([Q])

    subg_init = cand_init.copy()

    def expand(subg, cand):
        u = max(subg, key=lambda u: len(cand & adj[u]))
        for q in cand - adj[u]:
            cand.remove(q)
            Q.append(q)
            adj_q = adj[q]
            subg_q = subg & adj_q
            if not subg_q:
                yield Q[:]
            else:
                cand_q = cand & adj_q
                if cand_q:
                    yield from expand(subg_q, cand_q)
            Q.pop()

    return expand(subg_init, cand_init)


def number_of_cliques(G, nodes=None, cliques=None):
    """Return the number of maximal cliques each node is part of."""
    if cliques is None:
        if G.is_directed():
            raise NetworkXNotImplemented("not implemented for directed type")
        # br-r37-c1-ncliqueego (cc): a single node's maximal cliques are exactly the
        # maximal cliques of its ego graph (v universal -> every ego clique contains v, and
        # such a clique can't extend outside the ego graph since outside nodes aren't v-
        # adjacent). Count them on the small ego graph instead of every whole-graph clique.
        if nodes is not None and not isinstance(nodes, list):
            try:
                single = nodes in G
            except TypeError:
                single = False
            if single:
                return sum(1 for _ in find_cliques(ego_graph(G, nodes)))
        # br-r37-c1-ncliquelistego (cc): a LIST of nodes gets the same per-node ego
        # count (a node's maximal cliques in G are exactly the maximal cliques of its
        # ego graph — ego bijection). Missing nodes -> 0 (matching nx's
        # Counter[missing]==0) and unhashable -> TypeError (via ``node in G``), both
        # byte-exact vs nx (0/25 trials incl injected-missing). ~1.9x (beats nx) vs the
        # whole-graph find_cliques + Counter for small lists. The whole-graph Counter
        # path stays for nodes=None and precomputed ``cliques``.
        if isinstance(nodes, list):
            return {
                node: (
                    sum(1 for _ in find_cliques(ego_graph(G, node)))
                    if node in G
                    else 0
                )
                for node in nodes
            }
        cliques = find_cliques(G)

    if nodes is None:
        nodes = list(G.nodes())

    if not isinstance(nodes, list):
        return sum(1 for clique in cliques if nodes in clique)

    clique_counts = _Counter()
    for clique in cliques:
        clique_counts.update(clique)
    return {node: clique_counts[node] for node in nodes}


def node_clique_number(G, nodes=None, cliques=None, separate_nodes=False):
    """Return the size of the largest maximal clique containing each node."""
    if cliques is None:
        if G.is_directed():
            raise NetworkXNotImplemented("not implemented for directed type")
        # br-r37-c1-ncliqueego (cc): for a single node, the maximal cliques containing it
        # all live in its ego graph (v + neighbours, where v is universal so every maximal
        # clique contains it). Enumerate cliques of that small graph instead of EVERY
        # maximal clique of the whole graph (was 0.15x). max-size is order-invariant.
        if nodes is not None:
            try:
                single = nodes in G
            except TypeError:
                single = False
            if single:
                return max(len(c) for c in find_cliques(ego_graph(G, nodes)))
            # br-r37-c1-ncliquelistego (cc): a LIST of nodes gets the SAME per-node
            # ego treatment (nx's exact algorithm) instead of one find_cliques over
            # the WHOLE graph + a per-node membership scan. Each node is universal in
            # its ego graph, so every maximal clique there contains it; max-size is
            # order-invariant -> byte-exact vs nx (0/30 random-list trials) including
            # the NodeNotFound("Source .. is not in G") contract (ego_graph raises it)
            # and the {node:0} fallback for an unhashable-in-list node. ~2.6x on small
            # lists (beats nx); the whole-graph find_cliques path is now nodes=None only.
            try:
                return {
                    node: max(len(c) for c in find_cliques(ego_graph(G, node)))
                    for node in nodes
                }
            except TypeError:
                return {node: 0 for node in nodes}
        cliques = list(find_cliques(G))

    if nodes in G:
        return max(len(clique) for clique in cliques if nodes in clique)

    size_for_node = _defaultdict(int)
    for clique in cliques:
        clique_size = len(clique)
        for node in clique:
            if size_for_node[node] < clique_size:
                size_for_node[node] = clique_size
    if nodes is None:
        return size_for_node
    return {node: size_for_node[node] for node in nodes}

# Classic graph generators
from franken_networkx._fnx import (
    balanced_tree as _rust_balanced_tree,
    barbell_graph as _rust_barbell_graph,
    bull_graph as _rust_bull_graph,
    chvatal_graph as _rust_chvatal_graph,
    cubical_graph as _rust_cubical_graph,
    desargues_graph as _rust_desargues_graph,
    diamond_graph as _rust_diamond_graph,
    dodecahedral_graph as _rust_dodecahedral_graph,
    frucht_graph as _rust_frucht_graph,
    heawood_graph as _rust_heawood_graph,
    house_graph as _rust_house_graph,
    house_x_graph as _rust_house_x_graph,
    icosahedral_graph as _rust_icosahedral_graph,
    krackhardt_kite_graph as _rust_krackhardt_kite_graph,
    moebius_kantor_graph as _rust_moebius_kantor_graph,
    octahedral_graph as _rust_octahedral_graph,
    pappus_graph as _rust_pappus_graph,
    petersen_graph as _rust_petersen_graph,
    sedgewick_maze_graph as _rust_sedgewick_maze_graph,
    tetrahedral_graph as _rust_tetrahedral_graph,
    truncated_cube_graph as _rust_truncated_cube_graph,
    truncated_tetrahedron_graph as _rust_truncated_tetrahedron_graph,
    tutte_graph as _rust_tutte_graph,
    hoffman_singleton_graph as _rust_hoffman_singleton_graph,
    generalized_petersen_graph as _rust_generalized_petersen_graph,
    wheel_graph as _rust_wheel_graph,
    ladder_graph as _rust_ladder_graph,
    circular_ladder_graph as _rust_circular_ladder_graph,
    lollipop_graph as _rust_lollipop_graph,
    tadpole_graph as _rust_tadpole_graph,
    turan_graph as _rust_turan_graph,
    windmill_graph as _rust_windmill_graph,
    hypercube_graph as _rust_hypercube_graph,
    complete_bipartite_graph as _rust_complete_bipartite_graph,
    complete_multipartite_graph as _rust_complete_multipartite_graph,
    grid_2d_graph as _rust_grid_2d_graph,
    grid_graph as _rust_grid_graph,
    caveman_graph_native as _rust_caveman_graph,
    circular_ladder_graph_native as _rust_circular_ladder_graph_native,
    dorogovtsev_goltsev_mendes_graph as _rust_dorogovtsev_goltsev_mendes_graph,
    null_graph as _rust_null_graph,
    trivial_graph as _rust_trivial_graph,
    binomial_tree as _rust_binomial_tree,
    full_rary_tree as _rust_full_rary_tree,
    full_rary_tree_native as _rust_full_rary_tree_native,
    circulant_graph as _rust_circulant_graph,
    kneser_graph as _rust_kneser_graph,
    paley_graph as _rust_paley_graph,
    chordal_cycle_graph as _rust_chordal_cycle_graph,
    sudoku_graph as _rust_sudoku_graph,
)

# Algorithm functions — single-source shortest paths
from franken_networkx._fnx import (
    single_source_shortest_path as _raw_single_source_shortest_path,
    single_source_shortest_path_length as _raw_single_source_shortest_path_length,
)


def _bfs_visit_order(G, source):
    """Yield nodes in BFS-from-source order, visiting each layer's
    neighbours in G.adj[u] iteration order. Matches nx's
    ``single_source_shortest_path`` iteration contract
    (br-r37-c1-tlrdu)."""
    seen = {source}
    yield source
    frontier = [source]
    while frontier:
        next_frontier = []
        for u in frontier:
            try:
                neighbours = G.adj[u]
            except KeyError:
                continue
            for v in neighbours:
                if v not in seen:
                    seen.add(v)
                    yield v
                    next_frontier.append(v)
        frontier = next_frontier


def single_source_shortest_path(G, source, cutoff=None):
    """Return a dict of shortest paths from ``source`` to every reachable
    node. Matches NetworkX: raises NodeNotFound('Source {src} not in G')
    when the source isn't in the graph, instead of returning ``{}``.

    br-r37-c1-bfs-depth: nx returns ``{source: [source]}`` when
    cutoff is negative (no edges traversed but the source is always
    reachable from itself at distance 0). The Rust binding declared
    cutoff as unsigned int and raised OverflowError on negatives.
    Coerce negative cutoff to 0 to match nx exactly.

    br-r37-c1-ssspview: materialize native-root SubgraphView inputs before
    crossing the Rust boundary (see single_source_shortest_path_length).
    Private-root views instead walk their current Python rows directly.
    Exact reverse views instead read the root's native predecessor BFS
    directly, retaining its discovery objects and avoiding a reverse copy.
    """
    root = _reverse_view_root(G)
    if root is None and not _point_query_uses_private_rows(G):
        G = _coerce_arg_to_fnx_graph(G)
    if source not in G:
        raise NodeNotFound(f"Source {source} not in G")
    if root is None and _has_networkx_private_storage(G):
        # Assigned adjacency can differ from native topology. Walk the current
        # rows, preserving discovery objects and the oracle's len(adj) exit.
        adj = G._adj
        count = len(adj)
        paths = {source: [source]}
        frontier = [source]
        level = 0
        limit = float("inf") if cutoff is None else cutoff
        while frontier and limit > level:
            current, frontier = frontier, []
            for node in current:
                for neighbor in adj[node]:
                    if neighbor not in paths:
                        paths[neighbor] = paths[node] + [neighbor]
                        frontier.append(neighbor)
                if len(paths) == count:
                    return paths
            level += 1
        return paths
    if cutoff is not None:
        try:
            if int(cutoff) < 0:
                cutoff = 0
        except (TypeError, ValueError):
            pass
    if root is not None and (
        cutoff is None or isinstance(cutoff, int) and 0 <= cutoff <= _sys.maxsize
    ):
        # The view's successors are the root's predecessors. BFS emits the
        # actual discovery objects, unlike the target-path canonical emitter.
        paths = {source: [source]}
        for parent, node in _bfs_edges_raw(root, source, reverse=True, depth_limit=cutoff):
            paths[node] = paths[parent] + [node]
        return paths
    if root is not None:
        G = _coerce_arg_to_fnx_graph(G)
    # Rust returns results in BFS discovery order (br-r37-c1-bapbi), so no reordering needed.
    return _raw_single_source_shortest_path(G, source, cutoff)
