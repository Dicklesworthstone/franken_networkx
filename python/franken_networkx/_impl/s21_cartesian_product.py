

def cartesian_product(G, H):
    """Return the Cartesian product of *G* and *H*.

    The Cartesian product has node set ``V(G) x V(H)``. Two nodes
    ``(u1, v1)`` and ``(u2, v2)`` are adjacent iff ``u1 == u2`` and
    ``(v1, v2)`` is an edge in *H*, or ``v1 == v2`` and ``(u1, u2)``
    is an edge in *G*.
    """
    _validate_product_graph_types(G, H)
    G, H = _product_factors(G, H)
    # br-r37-c1-prodnative: native fast path for the no-attr, non-multigraph,
    # self-loop-free case (canonicalizes each product tuple once, assembles edges
    # in Rust). Falls back to the Python construction below for any other shape.
    _fast = _native_graph_product(G, H, kind="cartesian")
    if _fast is not None:
        return _fast
    # br-r37-c1-prodedgeattr (cc): EDGE-attributed cartesian products fall through the
    # node-only relaxation above. When both factors are simple Graphs with SCALAR-only
    # edge attrs (pristine edge mirror -> store-complete, e.g. a freshly bulk-built
    # weighted graph), the native kernel clones each source edge's store AttrMap onto
    # the product edges (each cartesian edge inherits exactly one source edge, no
    # pairing) — beating nx instead of the O(E_product) Python batch. Returns None on
    # any other shape (non-pristine mirror / non-scalar attrs / self-loops); node
    # attrs are decorated here afterward.
    if (
        (
            (type(G) is Graph and type(H) is Graph)
            or (type(G) is DiGraph and type(H) is DiGraph)
        )
        and not number_of_selfloops(G)
        and not number_of_selfloops(H)
    ):
        _edge_native = getattr(_fnx, "cartesian_product_edge_attrs_fast", None)
        if _edge_native is not None:
            _r = _edge_native(G, H)
            if _r is not None:
                if _graph_has_any_node_attrs(G) or _graph_has_any_node_attrs(H):
                    _r.add_nodes_from(
                        ((g, h), _product_node_attrs(dict(g_attrs), dict(h_attrs)))
                        for g, g_attrs in G.nodes(data=True)
                        for h, h_attrs in H.nodes(data=True)
                    )
                return _r
    P = _product_graph_class(G, H)()
    _attr_safe = _product_edge_attrs_kwarg_safe(G, H)

    # br-r37-c1-prodbatch (cc): the native path above handles the no-attr case; the
    # ATTRIBUTED simple case bails to here, where the per-node/edge add_node/add_edge
    # loop paid the Python->native dispatch PER product node/edge over the whole
    # O(V_G*V_H) node + O(E_G*V_H + E_H*V_G) edge set. Batch the node build and each
    # simple (non-multigraph factor) edge layer through add_nodes_from/add_edges_from
    # (one native call). Byte-identical to the loop (same tuples, attrs, and insertion
    # order); multigraph factors keep the per-edge keyed path (4-tuple key= collision
    # dodge). ~1.3-2.1x self on attributed products.
    P.add_nodes_from(
        ((g, h), _product_node_attrs(dict(g_attrs), dict(h_attrs)))
        for g, g_attrs in G.nodes(data=True)
        for h, h_attrs in H.nodes(data=True)
    )

    if G.is_multigraph():
        for u, v, key, attrs in G.edges(keys=True, data=True):
            for h in H.nodes():
                # 4-tuple form avoids `key=key, **attrs` collision when attrs
                # contains a 'key' entry (franken_networkx-uphdr).
                _product_add_keyed_edge(P, (u, h), (v, h), key, attrs, _attr_safe)
    else:
        P.add_edges_from(
            ((u, h), (v, h), dict(attrs))
            for u, v, attrs in G.edges(data=True)
            for h in H.nodes()
        )

    if H.is_multigraph():
        for u, v, key, attrs in H.edges(keys=True, data=True):
            for g in G.nodes():
                _product_add_keyed_edge(P, (g, u), (g, v), key, attrs, _attr_safe)
    else:
        P.add_edges_from(
            ((g, u), (g, v), dict(attrs))
            for u, v, attrs in H.edges(data=True)
            for g in G.nodes()
        )

    return P


def tensor_product(G, H):
    """Return the tensor (categorical) product of *G* and *H*.

    Two nodes ``(u1, v1)`` and ``(u2, v2)`` are adjacent iff
    ``(u1, u2)`` is an edge in *G* AND ``(v1, v2)`` is an edge in *H*.
    """
    _validate_product_graph_types(G, H)
    G, H = _product_factors(G, H)
    _fast = _native_graph_product(G, H, kind="tensor")
    if _fast is not None:
        return _fast
    # br-r37-c1-tensorprodattr (bt): native paired-attr attach for the common
    # single-edge-attr-key undirected case — reuses the structure kernel and attaches
    # each edge's paired {k: (g,h)} by index, skipping the set_edge_attributes
    # tuple-node key resolution (~93% of a weighted tensor). Returns None on any
    # other shape (directed / multigraph / self-loops / >1 distinct key / non-pristine
    # mirror), keeping the set_edge_attributes path below. Node attrs decorated after.
    if (
        type(G) in (Graph, DiGraph)
        and type(H) in (Graph, DiGraph)
        and not number_of_selfloops(G)
        and not number_of_selfloops(H)
    ):
        _edge_native = getattr(_fnx, "tensor_product_edge_attrs_fast", None)
        if _edge_native is not None:
            _r = _edge_native(G, H)
            if _r is not None:
                if _graph_has_any_node_attrs(G) or _graph_has_any_node_attrs(H):
                    _r.add_nodes_from(
                        ((g, h), _product_node_attrs(dict(g_attrs), dict(h_attrs)))
                        for g, g_attrs in G.nodes(data=True)
                        for h, h_attrs in H.nodes(data=True)
                    )
                return _r
    # br-cc-prod-edgeattr: `_native_graph_product` bails on EDGE attrs (the kernel
    # can't pair them), dropping the whole product to the O(E_G*E_H)
    # `add_edges_from` of TUPLE-NODE edges — 22.6ms of a 31ms weighted tensor (the
    # tuple-node insertion floor), i.e. 0.24x. But the native kernel builds the
    # STRUCTURE regardless of edge attrs, so build it natively and DECORATE the
    # paired edge attrs with ONE `set_edge_attributes` (a per-edge attr SET on the
    # already-built edges, not a re-insertion). Byte-identical: the native edge set
    # equals the Python build's (product parity canonicalises edge order) and the
    # paired attrs equal `_paired_edge_attrs`; verified across directed/self-loop/
    # node-attr. Gated to simple graphs of matching directedness (the kernel's
    # domain); multigraphs keep the Python path below. ~0.24x -> ~0.59x (2.4x self;
    # the residual is set_edge_attributes' tuple-node key resolution — a full beat
    # needs the kernel to pair attrs in Rust).
    if (
        not G.is_multigraph()
        and not H.is_multigraph()
        and G.is_directed() == H.is_directed()
    ):
        _structure = _fnx.tensor_product_fast(G, H)
        if _structure is not None:
            if _graph_has_any_node_attrs(G) or _graph_has_any_node_attrs(H):
                _structure.add_nodes_from(
                    ((g, h), _product_node_attrs(dict(g_attrs), dict(h_attrs)))
                    for g, g_attrs in G.nodes(data=True)
                    for h, h_attrs in H.nodes(data=True)
                )
            _g_edges = list(G.edges(data=True))
            _h_edges = list(H.edges(data=True))
            _edge_attr_map = {}
            # nx emits the directed-cross pass first, then (undirected only) the
            # undirected-cross pass; a later write wins in the dict exactly as a
            # later nx add_edge would.
            for _gu, _gv, _ga in _g_edges:
                for _hu, _hv, _ha in _h_edges:
                    _edge_attr_map[((_gu, _hu), (_gv, _hv))] = _paired_edge_attrs(
                        _ga, _ha
                    )
            if not G.is_directed():
                for _gu, _gv, _ga in _g_edges:
                    for _hu, _hv, _ha in _h_edges:
                        _edge_attr_map[((_gv, _hu), (_gu, _hv))] = _paired_edge_attrs(
                            _ga, _ha
                        )
            set_edge_attributes(_structure, _edge_attr_map)
            return _structure
    P = _product_graph_class(G, H)()
    _attr_safe = _product_edge_attrs_kwarg_safe(G, H)

    # br-r37-c1-prodbatch (cc): batch the O(V_G*V_H) node build (attributed simple
    # case bails here from the native path; per-node add_node paid dispatch each).
    P.add_nodes_from(
        ((g, h), _product_node_attrs(dict(g_attrs), dict(h_attrs)))
        for g, g_attrs in G.nodes(data=True)
        for h, h_attrs in H.nodes(data=True)
    )

    if G.is_multigraph():
        g_edges = list(G.edges(keys=True, data=True))
    else:
        g_edges = [(u, v, None, attrs) for u, v, attrs in G.edges(data=True)]
    if H.is_multigraph():
        h_edges = list(H.edges(keys=True, data=True))
    else:
        h_edges = [(u, v, None, attrs) for u, v, attrs in H.edges(data=True)]

    # br-r37-c1-prodorder: networkx emits tensor-product edges in TWO passes —
    # all "directed cross" edges (gu,hu)-(gv,hv) first, then (undirected only)
    # all "undirected cross" edges (gv,hu)-(gu,hv) — see
    # networkx.algorithms.operators.product._directed_edges_cross_edges /
    # _undirected_edges_cross_edges. The previous interleaved single loop
    # diverged from nx's edge iteration order.
    # br-r37-c1-prodbatch (cc): branch on P.is_multigraph() ONCE per pass — the
    # simple (non-multigraph) product batches through add_edges_from (one native
    # call) instead of per-edge add_edge dispatch; the multigraph product keeps the
    # per-edge keyed path (4-tuple key= collision dodge). Same edge tuples, paired
    # attrs, and pass order -> byte-identical.
    if P.is_multigraph():
        for gu, gv, gk, g_attrs in g_edges:
            for hu, hv, hk, h_attrs in h_edges:
                edge_attrs = _paired_edge_attrs(dict(g_attrs), dict(h_attrs))
                edge_key = _cross_product_edge_key(G.is_multigraph(), H.is_multigraph(), gk, hk)
                # 4-tuple form avoids `key=edge_key, **edge_attrs`
                # collision when edge_attrs contains a 'key' entry
                # (franken_networkx-uphdr).
                _product_add_keyed_edge(P, (gu, hu), (gv, hv), edge_key, edge_attrs, _attr_safe)
        if not G.is_directed():
            for gu, gv, gk, g_attrs in g_edges:
                for hu, hv, hk, h_attrs in h_edges:
                    edge_attrs = _paired_edge_attrs(dict(g_attrs), dict(h_attrs))
                    edge_key = _cross_product_edge_key(
                        G.is_multigraph(), H.is_multigraph(), gk, hk
                    )
                    _product_add_keyed_edge(P, (gv, hu), (gu, hv), edge_key, edge_attrs, _attr_safe)
    else:
        P.add_edges_from(
            ((gu, hu), (gv, hv), _paired_edge_attrs(dict(g_attrs), dict(h_attrs)))
            for gu, gv, gk, g_attrs in g_edges
            for hu, hv, hk, h_attrs in h_edges
        )
        if not G.is_directed():
            P.add_edges_from(
                ((gv, hu), (gu, hv), _paired_edge_attrs(dict(g_attrs), dict(h_attrs)))
                for gu, gv, gk, g_attrs in g_edges
                for hu, hv, hk, h_attrs in h_edges
            )

    return P


def strong_product(G, H):
    """Return the strong product of *G* and *H*.

    Union of Cartesian and tensor products.
    """
    _validate_product_graph_types(G, H)
    G, H = _product_factors(G, H)
    # br-r37-c1-prodstronglex: native fast path (simple, no-attr, self-loop-free)
    # assembles the cartesian ∪ tensor edge set in Rust, canonicalising each
    # product tuple once instead of per-edge — same edge set as the Python build
    # (product parity tests compare canonicalised edges), 3.3x slower -> faster.
    _fast = _native_graph_product(G, H, kind="strong")
    if _fast is not None:
        return _fast
    # br-r37-c1-strongprodattr (bt): native paired/scalar-attr attach for the common
    # single-edge-attr-key undirected case — reuses the (cartesian ∪ tensor) structure
    # and attaches all four edge passes by index, skipping the set_edge_attributes
    # tuple-node key resolution. Returns None on any other shape (directed / multigraph
    # / self-loops / >1 distinct key / non-pristine mirror). Node attrs decorated after.
    if (
        type(G) in (Graph, DiGraph)
        and type(H) in (Graph, DiGraph)
        and not number_of_selfloops(G)
        and not number_of_selfloops(H)
    ):
        _edge_native = getattr(_fnx, "strong_product_edge_attrs_fast", None)
        if _edge_native is not None:
            _r = _edge_native(G, H)
            if _r is not None:
                if _graph_has_any_node_attrs(G) or _graph_has_any_node_attrs(H):
                    _r.add_nodes_from(
                        ((g, h), _product_node_attrs(dict(g_attrs), dict(h_attrs)))
                        for g, g_attrs in G.nodes(data=True)
                        for h, h_attrs in H.nodes(data=True)
                    )
                return _r
    # br-cc-prod-edgeattr: edge-attr sibling of the tensor_product fast path — the
    # native `strong_product_fast` kernel builds the (cartesian ∪ tensor) STRUCTURE
    # regardless of edge attrs, so build it natively and DECORATE the four edge
    # passes with ONE `set_edge_attributes` (per-edge attr SET, not the O(E_product)
    # tuple-node `add_edges_from` re-insertion). ~0.29x -> ~0.51x (2x self), byte-
    # exact vs nx (verified directed/self-loop/node-attr/multi-attr). Simple graphs
    # of matching directedness only; multigraphs keep the Python path below.
    if (
        not G.is_multigraph()
        and not H.is_multigraph()
        and G.is_directed() == H.is_directed()
    ):
        _structure = _fnx.strong_product_fast(G, H)
        if _structure is not None:
            if _graph_has_any_node_attrs(G) or _graph_has_any_node_attrs(H):
                _structure.add_nodes_from(
                    ((g, h), _product_node_attrs(dict(g_attrs), dict(h_attrs)))
                    for g, g_attrs in G.nodes(data=True)
                    for h, h_attrs in H.nodes(data=True)
                )
            _g_edges = list(G.edges(data=True))
            _h_edges = list(H.edges(data=True))
            _Gn = list(G.nodes())
            _Hn = list(H.nodes())
            _em = {}
            # nx's exact pass order (later write wins, as a later add_edge would):
            # 1 nodes-cross-H-edges (H attrs), 2 G-edges-cross-nodes (G attrs),
            # 3 tensor directed cross (paired), 4 undirected-only tensor cross.
            for _g in _Gn:
                for _hu, _hv, _ha in _h_edges:
                    _em[((_g, _hu), (_g, _hv))] = dict(_ha)
            for _gu, _gv, _ga in _g_edges:
                for _h in _Hn:
                    _em[((_gu, _h), (_gv, _h))] = dict(_ga)
            for _gu, _gv, _ga in _g_edges:
                for _hu, _hv, _ha in _h_edges:
                    _em[((_gu, _hu), (_gv, _hv))] = _paired_edge_attrs(_ga, _ha)
            if not G.is_directed():
                for _gu, _gv, _ga in _g_edges:
                    for _hu, _hv, _ha in _h_edges:
                        _em[((_gv, _hu), (_gu, _hv))] = _paired_edge_attrs(_ga, _ha)
            set_edge_attributes(_structure, _em)
            return _structure
    # br-r37-c1-prodorder: nx.strong_product orders the two Cartesian passes
    # OPPOSITE to nx.cartesian_product (it does _nodes_cross_edges THEN
    # _edges_cross_nodes), so we cannot reuse cartesian_product(). Mirror
    # networkx's exact edge-pass order: (1) nodes x H-edges, (2) G-edges x nodes,
    # (3) tensor directed cross (gu,hu)-(gv,hv), (4) undirected-only tensor cross
    # (gv,hu)-(gu,hv). The previous build-on-cartesian-then-interleave diverged.
    P = _product_graph_class(G, H)()
    _attr_safe = _product_edge_attrs_kwarg_safe(G, H)

    # br-r37-c1-prodbatch (cc): batch the O(V_G*V_H) node build (attributed simple
    # case bails here from the native path).
    P.add_nodes_from(
        ((g, h), _product_node_attrs(dict(g_attrs), dict(h_attrs)))
        for g, g_attrs in G.nodes(data=True)
        for h, h_attrs in H.nodes(data=True)
    )

    if G.is_multigraph():
        g_edges = list(G.edges(keys=True, data=True))
    else:
        g_edges = [(u, v, None, attrs) for u, v, attrs in G.edges(data=True)]
    if H.is_multigraph():
        h_edges = list(H.edges(keys=True, data=True))
    else:
        h_edges = [(u, v, None, attrs) for u, v, attrs in H.edges(data=True)]

    # br-r37-c1-prodbatch (cc): branch on P.is_multigraph() ONCE — the simple
    # (non-multigraph) product batches each of nx's four edge passes through
    # add_edges_from (one native call/pass), the multigraph product keeps the
    # per-edge keyed path. Same tuples, paired attrs, and pass order (1 nodes-cross-
    # H-edges, 2 G-edges-cross-nodes, 3 tensor directed cross, 4 undirected-only
    # tensor cross) -> byte-identical to the per-edge build.
    if P.is_multigraph():
        # 1. _nodes_cross_edges: u == v and (x, y) an edge of H (H's edge attrs).
        for g in G.nodes():
            for hu, hv, hk, h_attrs in h_edges:
                _product_add_keyed_edge(P, (g, hu), (g, hv), hk, h_attrs, _attr_safe)
        # 2. _edges_cross_nodes: x == y and (u, v) an edge of G (G's edge attrs).
        for gu, gv, gk, g_attrs in g_edges:
            for h in H.nodes():
                _product_add_keyed_edge(P, (gu, h), (gv, h), gk, g_attrs, _attr_safe)
        # 3. tensor directed cross.
        for gu, gv, gk, g_attrs in g_edges:
            for hu, hv, hk, h_attrs in h_edges:
                edge_attrs = _paired_edge_attrs(dict(g_attrs), dict(h_attrs))
                edge_key = _cross_product_edge_key(G.is_multigraph(), H.is_multigraph(), gk, hk)
                _product_add_keyed_edge(P, (gu, hu), (gv, hv), edge_key, edge_attrs, _attr_safe)
        # 4. tensor undirected cross (undirected only).
        if not G.is_directed():
            for gu, gv, gk, g_attrs in g_edges:
                for hu, hv, hk, h_attrs in h_edges:
                    edge_attrs = _paired_edge_attrs(dict(g_attrs), dict(h_attrs))
                    edge_key = _cross_product_edge_key(
                        G.is_multigraph(), H.is_multigraph(), gk, hk
                    )
                    _product_add_keyed_edge(P, (gv, hu), (gu, hv), edge_key, edge_attrs, _attr_safe)
    else:
        # 1. _nodes_cross_edges.
        P.add_edges_from(
            ((g, hu), (g, hv), dict(h_attrs))
            for g in G.nodes()
            for hu, hv, hk, h_attrs in h_edges
        )
        # 2. _edges_cross_nodes.
        P.add_edges_from(
            ((gu, h), (gv, h), dict(g_attrs))
            for gu, gv, gk, g_attrs in g_edges
            for h in H.nodes()
        )
        # 3. tensor directed cross.
        P.add_edges_from(
            ((gu, hu), (gv, hv), _paired_edge_attrs(dict(g_attrs), dict(h_attrs)))
            for gu, gv, gk, g_attrs in g_edges
            for hu, hv, hk, h_attrs in h_edges
        )
        # 4. tensor undirected cross (undirected only).
        if not G.is_directed():
            P.add_edges_from(
                ((gv, hu), (gu, hv), _paired_edge_attrs(dict(g_attrs), dict(h_attrs)))
                for gu, gv, gk, g_attrs in g_edges
                for hu, hv, hk, h_attrs in h_edges
            )

    return P


# ---------------------------------------------------------------------------
# Additional high-value utilities
# ---------------------------------------------------------------------------


def adjacency_matrix(G, nodelist=None, dtype=None, weight="weight"):
    """Return the adjacency matrix of *G* as a SciPy sparse array.

    This is an alias for ``to_scipy_sparse_array``.
    """
    return to_scipy_sparse_array(G, nodelist=nodelist, dtype=dtype, weight=weight)


def has_bridges(G, root=None, *, backend=None, **backend_kwargs):
    """Return True if graph *G* has at least one bridge.

    Parameters
    ----------
    G : graph
        An undirected graph.
    root : node, optional
        A node in the graph. If specified, only check the connected
        component containing root.

    Returns
    -------
    bool
        True if G has at least one bridge.
    """
    _validate_backend_dispatch_keywords("has_bridges", backend, backend_kwargs)
    for _ in bridges(G, root=root):
        return True
    return False


def local_bridges(G, with_span=True, weight=None, *, backend=None, **backend_kwargs):
    """Yield local bridges in *G*.

    A local bridge is an edge (u, v) where u and v have no common neighbors.
    If ``with_span`` is True, yields ``(u, v, span)`` where span is the
    distance between u and v after virtually removing the edge.

    Matches the upstream ``@not_implemented_for("directed", "multigraph")``
    decorator (br-zzcm8) — directed and multigraph inputs raise
    NetworkXNotImplemented instead of silently projecting to simple
    graphs.  br-r37-c1-mnziq: nx applies the decorators with
    ``directed`` inner, so on a MultiDiGraph the 'directed' message
    fires first.
    """
    _validate_backend_dispatch_keywords("local_bridges", backend, backend_kwargs)
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    # br-r37-c1-tqcpg: the Rust fast-path (and the old discard-based
    # intersection below) mishandle self-loops. nx tests
    # ``set(G[u]) & set(G[v])`` WITHOUT removing the endpoints, so a
    # self-loop on an endpoint makes it a shared neighbour and the edge is
    # NOT a local bridge. For loop-free graphs the discard is a no-op, so
    # both behaviours agree there; route self-loop graphs through the Python
    # generator with the nx-exact intersection.
    if not with_span and weight is None and number_of_selfloops(G) == 0:
        from franken_networkx._fnx import local_bridges_rust

        return iter(local_bridges_rust(G))

    def _generate():
        for u, v in G.edges():
            # Match nx exactly: intersect full neighbour sets (no endpoint
            # discard) so a self-loop on u or v counts as a shared neighbour.
            if set(G.neighbors(u)) & set(G.neighbors(v)):
                continue  # common neighbor exists — not a local bridge
            if with_span:
                # Compute shortest path from u to v not using edge (u,v).
                # BFS/Dijkstra from u, but skip the direct u->v hop.
                from collections import deque as _deque

                if weight is None:
                    # Unweighted BFS avoiding direct (u,v) edge.
                    dist = {u: 0}
                    queue = _deque([u])
                    found = False
                    while queue and not found:
                        curr = queue.popleft()
                        for nbr in G.neighbors(curr):
                            # Skip the direct u<->v edge.
                            if curr == u and nbr == v:
                                continue
                            if curr == v and nbr == u:
                                continue
                            if nbr not in dist:
                                dist[nbr] = dist[curr] + 1
                                if nbr == v:
                                    found = True
                                    break
                                queue.append(nbr)
                    span = dist.get(v, float("inf"))
                else:
                    # Weighted: Dijkstra avoiding direct (u,v) edge.
                    import heapq
                    from itertools import count as _count

                    # br-r37-c1-64xcg: networkx's Dijkstra breaks distance
                    # ties with a counter; (distance, node) compared the
                    # nodes and raised TypeError on mixed int / str labels.
                    push_order = _count()
                    dist = {u: 0}
                    heap = [(0, next(push_order), u)]
                    while heap:
                        d, _, curr = heapq.heappop(heap)
                        if d > dist.get(curr, float("inf")):
                            continue
                        if curr == v:
                            break
                        for nbr in G.neighbors(curr):
                            if curr == u and nbr == v:
                                continue
                            if curr == v and nbr == u:
                                continue
                            if callable(weight):
                                w = weight(curr, nbr, G[curr][nbr])
                            else:
                                w = G[curr][nbr].get(weight, 1)
                            if w is None:
                                continue
                            if w < 0:
                                raise ValueError("Contradictory paths found, negative weights?")
                            nd = d + w
                            if nd < dist.get(nbr, float("inf")):
                                dist[nbr] = nd
                                heapq.heappush(heap, (nd, next(push_order), nbr))
                    span = dist.get(v, float("inf"))
                yield (u, v, span)
            else:
                yield (u, v)

    return _generate()


def _minimum_edge_cut_inproc(G, s=None, t=None, flow_func=None):
    from franken_networkx.backend import _fnx_to_nx
    H = _fnx_to_nx(G)
    try:
        return _nx.algorithms.connectivity.cuts.minimum_edge_cut(
            H, s=s, t=t, flow_func=flow_func, backend="networkx"
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)


def minimum_edge_cut(G, s=None, t=None, flow_func=None, *, backend=None, **backend_kwargs):
    """Return a minimum edge cut of *G*."""
    _validate_backend_dispatch_keywords("minimum_edge_cut", backend, backend_kwargs)
    G = _coerce_arg_to_fnx_graph(G)
    if len(G) == 0:
        raise NetworkXPointlessConcept("Connectivity is undefined for the null graph.")
    if (s is not None and t is None) or (s is None and t is not None):
        raise NetworkXError("Both source and target must be specified.")

    if flow_func is not None:
        return _minimum_edge_cut_inproc(
            G, s=s, t=t, flow_func=flow_func,
        )

    H = _build_auxiliary_edge_connectivity_fast(G)

    def _min_st_cut(H, s, t):
        _, (reachable, non_reachable) = _minimum_cut_raw(
            H, s, t, capacity="capacity", edmonds_karp=True
        )
        reachable = set(reachable)
        non_reachable = set(non_reachable)
        cutset = set()
        for u in reachable:
            for v in H[u]:
                if v in non_reachable:
                    cutset.add((u, v))
        return cutset

    if s is not None and t is not None:
        if s not in G:
            raise NetworkXError(f"node {s} not in graph")
        if t not in G:
            raise NetworkXError(f"node {t} not in graph")
        if s == t:
            raise NetworkXError("source and sink are the same node")
        return _min_st_cut(H, s, t)

    if G.is_directed():
        if len(G) == 1:
            raise NetworkXError("source and sink are the same node")
        if not is_weakly_connected(G):
            raise NetworkXError("Input graph is not connected")

        node = min(G, key=G.degree)
        min_cut = set(G.edges(node))
        nodes = list(G)
        n = len(nodes)
        for i in range(n):
            try:
                this_cut = _min_st_cut(H, nodes[i], nodes[i + 1])
                if len(this_cut) <= len(min_cut):
                    min_cut = this_cut
            except IndexError:
                this_cut = _min_st_cut(H, nodes[i], nodes[0])
                if len(this_cut) <= len(min_cut):
                    min_cut = this_cut
        return min_cut
    else:
        if len(G) == 1:
            return set()
        if not is_connected(G):
            raise NetworkXError("Input graph is not connected")

        node = min(G, key=G.degree)
        min_cut = set(G.edges(node))
        for nd in G:
            D = dominating_set(G, start_with=nd)
            v = D.pop()
            if D:
                break
        else:
            return min_cut
        for w in D:
            this_cut = _min_st_cut(H, v, w)
            if len(this_cut) <= len(min_cut):
                min_cut = this_cut
        return min_cut


def stochastic_graph(G, copy=True, weight="weight"):
    """Return the stochastic graph of *G* (row-normalized adjacency)."""
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")

    # br-r37-c1-stochcopy: the copy dominated — _copy_graph_shallow rebuilds via a
    # per-edge add_edge loop (~35ms @3200e, 0.34x nx). For an exact DiGraph use the
    # native integer-CSR ``G.copy()`` (independent attr dicts, so the in-place
    # weight normalisation below stays isolated from G); and materialise the edge
    # view ONCE (live attr-dict refs) rather than crossing ``edges(data=True)``
    # twice. 0.34x -> ~parity, ~3x self-speedup. Multigraph keeps
    # _copy_graph_shallow (its native G.copy() is the slow String-keyed path), and
    # subclasses keep it (SubgraphView can't be empty-constructed).
    if copy:
        if type(G) is MultiDiGraph and isinstance(weight, str):
            _sync_rust_edge_attrs(G, edge_only=True)
            graph = _fnx.stochastic_graph_copy_multidigraph(G, weight)
            if graph is not None:
                return graph
        graph = G.copy() if type(G) is DiGraph else _copy_graph_shallow(G)
    else:
        graph = G
    if (
        type(graph) is DiGraph
        and isinstance(weight, str)
        and _fnx.stochastic_graph_normalize_digraph_inplace(graph, weight)
    ):
        return graph
    if (
        type(graph) is MultiDiGraph
        and isinstance(weight, str)
        and _fnx.stochastic_graph_normalize_multidigraph_inplace(graph, weight)
    ):
        return graph
    degree = {node: 0 for node in graph.nodes()}
    if graph.is_multigraph():
        edges = list(graph.edges(keys=True, data=True))
        for u, _, _, attrs in edges:
            degree[u] += attrs.get(weight, 1)
        for u, _, _, attrs in edges:
            attrs[weight] = 0 if degree[u] == 0 else attrs.get(weight, 1) / degree[u]
    else:
        edges = list(graph.edges(data=True))
        for u, _, attrs in edges:
            degree[u] += attrs.get(weight, 1)
        for u, _, attrs in edges:
            attrs[weight] = 0 if degree[u] == 0 else attrs.get(weight, 1) / degree[u]
    return graph


def _normalize_pagerank_vector(vector, nodes, *, zero_sum="raise"):
    # br-r37-c1-prnk-perso: nx filters personalization /
    # nstart / dangling vectors to graph-intersection keys
    # before normalizing, so:
    #   * a vector with NO graph-key entries (e.g. {99: 1.0}
    #     on a 3-node graph) raises ZeroDivisionError on the
    #     ``/ total`` step
    #   * a partially-bad vector (e.g. {0: 0.5, 99: 0.5})
    #     normalizes the in-graph weight to sum 1 — node 0
    #     gets 1.0, not 0.5
    # fnx previously summed over ALL keys (including
    # bad ones), silently distributing implicit weight to
    # dropped keys.  Filter first to match nx semantics.
    nodeset = set(nodes)
    filtered = {key: value for key, value in vector.items() if key in nodeset}
    total = _math.fsum(filtered.values())
    if total == 0 and zero_sum == "nan":
        nan = float("nan")
        return dict.fromkeys(nodes, nan)
    return {node: filtered.get(node, 0) / total for node in nodes}


def _pagerank_outgoing_weights(succ_row, weight, is_multigraph):
    # br-prcallable: takes a pre-fetched successor row (from a single adjacency
    # snapshot) instead of indexing ``G.succ[node]`` per call. The old form was
    # invoked once per node in the pagerank weight loop, and each ``G.succ[node]``
    # rebuilt the FULL native adjacency dict (``_native_adjacency_dict``) just to
    # read one row — O(N) per node, O(N^2) overall (callable-weight pagerank was
    # ~497ms / 0.00x vs nx at N=600). The caller now snapshots the adjacency ONCE.
    if is_multigraph:
        neighbor_weights = {}
        for nbr, keyed_attrs in succ_row.items():
            neighbor_weights[nbr] = _math.fsum(
                1.0 if weight is None else attrs.get(weight, 1)
                for attrs in keyed_attrs.values()
            )
        return neighbor_weights

    return {
        nbr: 1.0 if weight is None else attrs.get(weight, 1)
        # br-prcallable fix (cc): use the pre-fetched succ_row (the function's
        # contract — see the is_multigraph branch above). The pre-snapshot refactor
        # left a stale ``G.succ[node]`` here, but neither ``G`` nor ``node`` is in
        # scope, so the non-string-weight-key pagerank path raised NameError.
        for nbr, attrs in succ_row.items()
    }


try:
    from franken_networkx._fnx import (
        graph_has_nonfinite_edge_weight as _native_has_nonfinite_edge_weight,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_has_nonfinite_edge_weight = None

try:
    # br-gauntlet-perf1: native O(E) non-numeric-weight scan. Unlike the
    # ``as_f64``-based ``graph_has_nonfinite_edge_weight`` (which parses
    # ``"5"`` → 5.0 and would wrongly call a string weight numeric), this
    # helper checks the ``CgseValue`` *variant* via ``is_strictly_numeric()``
    # (true only for Bool/Int/Float), so it is a SOUND replacement for the
    # slow Python EdgeView scan in ``_has_nonnumeric_edge_weight``.
    from franken_networkx._fnx import (
        graph_has_nonnumeric_edge_weight as _native_has_nonnumeric_edge_weight,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_has_nonnumeric_edge_weight = None

try:
    # br-gauntlet-perf1: native O(E) all-integer-weights scan (Int CgseValue
    # variant; missing keys default to int 1). Replaces the Python EdgeView
    # scan in ``_sp_edge_weights_all_int`` (the shortest-path int/float
    # distance-coercion parity gate).
    from franken_networkx._fnx import (
        graph_edge_weights_all_int as _native_edge_weights_all_int,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_edge_weights_all_int = None

try:
    from franken_networkx._fnx import (
        adjacency_arrays as _native_adjacency_arrays,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_adjacency_arrays = None

try:
    from franken_networkx._fnx import (
        adjacency_index_arrays as _native_adjacency_index_arrays,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_adjacency_index_arrays = None

try:
    from franken_networkx._fnx import (
        adjacency_arrays_multigraph as _native_adjacency_arrays_multigraph,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_adjacency_arrays_multigraph = None

try:
    # br-r37-c1-iyu0a: single-pass COO + finiteness guard (folds the separate
    # graph_has_nonfinite_edge_weight_multigraph scan into the COO build).
    from franken_networkx._fnx import (
        adjacency_arrays_multigraph_finite_checked as _native_adjacency_arrays_multigraph_checked,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_adjacency_arrays_multigraph_checked = None

try:
    from franken_networkx._fnx import (
        adjacency_arrays_multigraph_live_finite_checked as _native_adjacency_arrays_multigraph_live_checked,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_adjacency_arrays_multigraph_live_checked = None

try:
    from franken_networkx._fnx import (
        adjacency_arrays_multigraph_default_order_live_finite_checked as _native_adjacency_arrays_multigraph_default_order_live_checked,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_adjacency_arrays_multigraph_default_order_live_checked = None

try:
    from franken_networkx._fnx import (
        adjacency_csr_multidigraph_default_order_live_finite_checked as _native_adjacency_csr_multidigraph_default_order_live_checked,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_adjacency_csr_multidigraph_default_order_live_checked = None

try:
    from franken_networkx._fnx import (
        adjacency_csr_bytes_default_order_unweighted as _native_adjacency_csr_bytes_default_order_unweighted,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_adjacency_csr_bytes_default_order_unweighted = None

try:
    from franken_networkx._fnx import (
        adjacency_csr_bytes_multidigraph_default_order_live_finite_checked as _native_adjacency_csr_bytes_multidigraph_default_order_live_checked,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_adjacency_csr_bytes_multidigraph_default_order_live_checked = None

try:
    from franken_networkx._fnx import (
        adjacency_csr_bytes_multigraph_default_order_live_finite_checked as _native_adjacency_csr_bytes_multigraph_default_order_live_checked,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_adjacency_csr_bytes_multigraph_default_order_live_checked = None

try:
    from franken_networkx._fnx import (
        graph_has_nonfinite_edge_weight_multigraph as _native_has_nonfinite_edge_weight_multigraph,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_has_nonfinite_edge_weight_multigraph = None

try:
    from franken_networkx._fnx import (
        adjacency_default_order_index_arrays as _native_adjacency_default_order_index_arrays,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_adjacency_default_order_index_arrays = None

try:
    from franken_networkx._fnx import (
        adjacency_default_order_arrays as _native_adjacency_default_order_arrays,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_adjacency_default_order_arrays = None

try:
    from franken_networkx._fnx import (
        adjacency_default_order_typed_arrays as _native_adjacency_default_order_typed_arrays,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_adjacency_default_order_typed_arrays = None

try:
    from franken_networkx._fnx import (
        adjacency_nodelist_typed_arrays as _native_adjacency_nodelist_typed_arrays,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_adjacency_nodelist_typed_arrays = None

try:
    from franken_networkx._fnx import (
        graph_has_edge_attr as _native_has_edge_attr,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_has_edge_attr = None

try:
    from franken_networkx._fnx import (
        graph_has_none_edge_attr_key as _native_has_none_edge_attr_key,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_has_none_edge_attr_key = None


# br-r37-c1-dijknone: an attribute name no edge can carry, used to express
# "every weight is 1" to a kernel whose binding requires a `str` weight.
_UNWEIGHTED_WEIGHT_SENTINEL = "\x00__fnx_unweighted__"


def _dijkstra_weight_for_none(G, weight):
    """Rewrite ``weight=None`` to an absent attribute name when that is exact.

    nx resolves each edge weight as ``data.get(weight, 1)``, so ``weight=None``
    is the unweighted case — every edge weighs 1 — UNLESS some edge really
    carries the literal ``None`` as an attribute key (``G.edges[u, v][None] = 5``
    is legal and nx honours it). Naming an attribute that no edge carries makes
    the native kernel compute exactly that, instead of delegating: the
    delegation path converts the whole graph to nx and then runs nx, which
    measured 0.088x — an order of magnitude SLOWER than simply calling nx.

    Returns the original ``weight`` (keeping today's delegation) whenever the
    rewrite cannot be proven safe.
    """
    if weight is not None or _native_has_none_edge_attr_key is None:
        return weight
    if G.is_multigraph():
        return weight
    try:
        has_none_key = _native_has_none_edge_attr_key(G)
    except Exception:
        return weight
    if has_none_key is not False:
        return weight
    # Paranoia: the sentinel must itself be absent, or it would be read as a
    # real weight.
    if _graph_has_edge_attribute(G, _UNWEIGHTED_WEIGHT_SENTINEL):
        return weight
    return _UNWEIGHTED_WEIGHT_SENTINEL

try:
    from franken_networkx._fnx import (
        graph_has_any_attrs as _native_graph_has_any_attrs,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_graph_has_any_attrs = None


def _pagerank_needs_networkx_weight_parity(G, weight):
    if weight is None:
        return False

    # br-r37-c1-s0tno: route the scan through a native O(|E|) Rust
    # helper for simple Graph/DiGraph. The previous Python iteration
    # over G.edges() cost ~40 ms on BA5000 — it was the entire fnx
    # vs nx pagerank-wrapper gap (the Rust algorithm is already at
    # parity with nx). Native helper returns None for multigraphs;
    # fall back to the Python scan there so per-key parallel-edge
    # attrs are inspected correctly.
    if _native_has_nonfinite_edge_weight is not None and not G.is_multigraph():
        try:
            native = _native_has_nonfinite_edge_weight(G, weight)
        except Exception:
            native = None
        if native is not None:
            return bool(native)

    # br-r37-c1-fb9td: native O(|E|) scan for multigraph too — avoids
    # materializing the whole G.edges(keys=True, data=True) view (per-edge
    # tuples + attr-dict clones) just to check for a non-finite weight value.
    # Same semantics as the simple kernel (absent key skipped; present key is
    # non-finite when not a finite float).
    if _native_has_nonfinite_edge_weight_multigraph is not None and G.is_multigraph():
        try:
            native = _native_has_nonfinite_edge_weight_multigraph(G, weight)
        except Exception:
            native = None
        if native is not None:
            return bool(native)

    edges = G.edges(keys=True, data=True) if G.is_multigraph() else G.edges(data=True)
    for edge in edges:
        attrs = edge[-1]
        if weight not in attrs:
            continue
        try:
            value = float(attrs[weight])
        except (TypeError, ValueError, OverflowError):
            return True
        if not _math.isfinite(value):
            return True
    return False


def _pagerank_scipy_matrix(G, weight):
    """Build or reuse the transition matrix shared by PageRank vector variants."""
    import numpy as np
    import scipy.sparse as sp

    N = len(G)
    cache_key = None
    cached = None
    if (
        type(G) in (Graph, DiGraph)
        and _native_dijkstra_weight_cache_token is not None
        and (weight is None or isinstance(weight, str))
    ):
        try:
            token = _native_dijkstra_weight_cache_token(G)
        except Exception:
            token = None
        if token is not None:
            nodes_seq, edges_seq, edge_attrs_dirty, attr_rewrites = token
            if not edge_attrs_dirty:
                cache_key = (type(G), weight, nodes_seq, edges_seq, attr_rewrites)
                cached = vars(G).get("_fnx_pagerank_scipy_matrix_cache")
                if cached is not None and cached[0] != cache_key:
                    cached = None

    if cached is not None:
        nodelist, A, is_dangling = cached[1]
    else:
        nodelist = list(G)
        # br-r37-c1-raqel: build COO directly for pagerank to skip dtype
        # checks in to_scipy_sparse_array. Native path returns (rows, cols, data).
        if (
            _native_adjacency_arrays is not None
            and not G.is_multigraph()
            and (weight is None or isinstance(weight, str))
        ):
            native_weight = weight if isinstance(weight, str) else None
            native_result = None
            native_index_used = False
            native_csr_normalized = False
            if native_weight is None and (
                _native_adjacency_csr_bytes_default_order_unweighted is not None
                or _native_adjacency_index_arrays is not None
            ):
                # br-r37-c1-g3z4d: keep simple unweighted adjacency in CSR from
                # Rust storage through SciPy. The former COO handoff allocated
                # two Python integers per edge, copied both lists into NumPy,
                # converted COO->CSR, then multiplied by a diagonal sparse
                # matrix. Native byte buffers make the NumPy views O(1), while
                # direct row normalization deletes both sparse conversions.
                native_csr_result = None
                if _native_adjacency_csr_bytes_default_order_unweighted is not None:
                    native_csr_result = (
                        _native_adjacency_csr_bytes_default_order_unweighted(G, None)
                    )
                if native_csr_result is not None:
                    indptr_buffer, indices_buffer = native_csr_result
                    indptr = np.frombuffer(indptr_buffer, dtype=np.intp)
                    indices = np.frombuffer(indices_buffer, dtype=np.intp)
                    degrees = np.diff(indptr)
                    inverse_degree = np.zeros(N, dtype=float)
                    np.divide(
                        1.0,
                        degrees,
                        out=inverse_degree,
                        where=degrees != 0,
                    )
                    data = np.repeat(inverse_degree, degrees)
                    A = sp.csr_array(
                        (data, indices, indptr), shape=(N, N), dtype=float
                    )
                    is_dangling = np.flatnonzero(degrees == 0)
                    native_index_used = True
                    native_csr_normalized = True

                # br-r37-c1-prdir: prefer the default-order index COO (directed +
                # undirected) — it skips the Python nodelist canonicalisation; nodelist
                # == list(G) so the index-ordered (rows, cols) align. Fall back to the
                # nodelist builder if unavailable.
                native_index_result = None
                if (
                    not native_index_used
                    and _native_adjacency_default_order_index_arrays is not None
                ):
                    native_index_result = _native_adjacency_default_order_index_arrays(G, None)
                if (
                    not native_index_used
                    and native_index_result is None
                    and _native_adjacency_index_arrays is not None
                ):
                    native_index_result = _native_adjacency_index_arrays(G, nodelist, None)
                if native_index_result is not None:
                    rows, cols = native_index_result
                    rows = np.asarray(rows, dtype=np.intp)
                    cols = np.asarray(cols, dtype=np.intp)
                    data = np.ones(len(rows), dtype=float)
                    A = sp.coo_array(
                        (data, (rows, cols)), shape=(N, N), dtype=float
                    ).tocsr()
                    native_index_used = True
                elif not native_index_used:
                    native_result = _native_adjacency_arrays(
                        G, nodelist, native_weight, 1.0
                    )
            else:
                # br-r37-c1-coowt/prdir: default-order integer-CSR weighted COO for
                # BOTH undirected and directed graphs (the builder now emits the
                # row-major out-adjacency for a DiGraph). Reads weights by index pair,
                # skipping the Python nodelist canonicalisation + per-edge node
                # string->index lookups of adjacency_arrays. nodelist == list(G) here
                # so the index-ordered COO matches; matrix assembly is order-
                # independent regardless.
                if _native_adjacency_default_order_arrays is not None:
                    native_result = _native_adjacency_default_order_arrays(
                        G, native_weight, 1.0
                    )
                if native_result is None:
                    native_result = _native_adjacency_arrays(
                        G, nodelist, native_weight, 1.0
                    )
            if native_result is not None:
                rows, cols, data = native_result
                A = sp.coo_array(
                    (data, (rows, cols)), shape=(N, N), dtype=float
                ).tocsr()
            elif not native_index_used:
                A = to_scipy_sparse_array(G, nodelist=nodelist, weight=weight, dtype=float)
        elif (
            type(G) in (MultiGraph, MultiDiGraph)
            and not _has_networkx_private_storage(G)
            and isinstance(weight, str)
            and _native_adjacency_arrays_multigraph_live_checked is not None
        ):
            # Read escaped edge dictionaries on every call. The store-only
            # sparse exporter can outlive a second write to a held MultiGraph
            # dictionary, even after the wrapper's attribute sync.
            native_csr_normalized = False
            live_arrays = _native_adjacency_arrays_multigraph_live_checked(
                G, nodelist, weight, 1.0
            )
            if live_arrays is not None:
                rows, cols, data = live_arrays
                if not G.is_directed():
                    # NetworkX constructs all forward entries, then their
                    # mirrors, then negative diagonal entries. A self-loop
                    # emitted only once is mathematically equivalent but not
                    # float-bit equivalent after SciPy sums COO duplicates.
                    rows = np.asarray(rows, dtype=np.intp)
                    cols = np.asarray(cols, dtype=np.intp)
                    data = np.asarray(data, dtype=float)
                    forward = rows <= cols
                    rows, cols, data = rows[forward], cols[forward], data[forward]
                    loops = rows == cols
                    rows, cols, data = (
                        np.concatenate((rows, cols, rows[loops])),
                        np.concatenate((cols, rows, cols[loops])),
                        np.concatenate((data, data, -data[loops])),
                    )
                A = sp.coo_array(
                    (data, (rows, cols)), shape=(N, N), dtype=float
                ).tocsr()
            else:
                # A present nonnumeric/nonfinite value must retain SciPy's
                # exact conversion/error behavior, never become unit weight.
                from franken_networkx.backend import _fnx_to_nx

                A = _nx.to_scipy_sparse_array(
                    _fnx_to_nx(G), nodelist=nodelist, weight=weight,
                    dtype=float, backend="networkx",
                )
        else:
            native_csr_normalized = False
            A = to_scipy_sparse_array(G, nodelist=nodelist, weight=weight, dtype=float)
        if not native_csr_normalized:
            S = np.asarray(A.sum(axis=1)).flatten()
            S[S != 0] = 1.0 / S[S != 0]
            Q = sp.dia_array((S, 0), shape=A.shape).tocsr()
            A = Q @ A
            is_dangling = np.where(S == 0)[0]
        if cache_key is not None:
            vars(G)["_fnx_pagerank_scipy_matrix_cache"] = (
                cache_key,
                (nodelist, A, is_dangling),
            )

    return nodelist, A, is_dangling


def _pagerank_scipy(G, alpha, max_iter, tol, weight):
    """scipy.sparse-backed PageRank power iteration.

    br-r37-c1-y5y7i: matches nx's _pagerank_scipy for the simple case
    (no personalization/nstart/dangling). Uses BLAS-backed matvec
    instead of pure-Rust scalar iteration — 2-3× faster on dense graphs.
    """
    import numpy as np

    N = len(G)
    if N == 0:
        return {}
    nodelist, A, is_dangling = _pagerank_scipy_matrix(G, weight)
    x = np.full(N, 1.0 / N)
    p = np.full(N, 1.0 / N)

    for _ in range(max_iter):
        xlast = x
        x = alpha * (x @ A + x[is_dangling].sum() * p) + (1 - alpha) * p
        err = np.abs(x - xlast).sum()
        if err < N * tol:
            return dict(zip(nodelist, map(float, x)))
    raise PowerIterationFailedConvergence(max_iter)


def _pagerank_scipy_personalized(
    G, alpha, personalization, max_iter, tol, nstart, weight, dangling
):
    """scipy.sparse PageRank mirroring ``networkx._pagerank_scipy`` for the
    personalization / nstart / dangling cases (br-r37-c1-prscipy, cc).

    The personalized path previously ran a pure-Python power iteration over
    ``G.to_directed()`` (~5x slower than nx, which uses scipy for every case).
    Share the default path's native matrix builder and mutation-aware cache;
    the vectors and their iteration arithmetic remain separate, including
    NetworkX's Python ``sum`` association for dangling ranks.
    """
    import numpy as _np

    N = len(G)
    if N == 0:
        return {}
    nodelist, A, is_dangling = _pagerank_scipy_matrix(G, weight)

    if nstart is None:
        x = _np.repeat(1.0 / N, N)
    else:
        x = _np.array([nstart.get(n, 0) for n in nodelist], dtype=float)
        x = x / x.sum()
    if personalization is None:
        p = _np.repeat(1.0 / N, N)
    else:
        p = _np.array([personalization.get(n, 0) for n in nodelist], dtype=float)
        p_sum = p.sum()
        if p_sum == 0:
            raise ZeroDivisionError
        p = p / p_sum
    if dangling is None:
        dangling_weights = p
    else:
        dangling_weights = _np.array([dangling.get(n, 0) for n in nodelist], dtype=float)
        dangling_weights = dangling_weights / dangling_weights.sum()
    for _ in range(max_iter):
        xlast = x
        x = alpha * (x @ A + sum(x[is_dangling]) * dangling_weights) + (1 - alpha) * p
        err = _np.absolute(x - xlast).sum()
        if err < N * tol:
            return dict(zip(nodelist, map(float, x)))
    raise PowerIterationFailedConvergence(max_iter)


def pagerank_many(
    G,
    personalizations,
    alpha=0.85,
    max_iter=100,
    tol=1.0e-6,
    weight="weight",
    *,
    workers=None,
):
    """Compute many personalized PageRank vectors over one shared CSR matrix.

    This is the batched equivalent of::

        [pagerank(G, personalization=p, ...) for p in personalizations]

    The graph-to-CSR conversion and row normalization happen once.  Independent
    power iterations then run on a persistent worker pool; each worker owns one
    rank vector and therefore preserves NetworkX's exact floating-point
    association order.  Results are returned in personalization input order.

    ``workers=None`` uses two workers when the batch has at least two queries;
    sparse matvec is memory-bandwidth-bound, so this measured default avoids
    oversubscribing the shared matrix.  Pass an explicit worker count to tune a
    dedicated host, or ``workers=1`` for deterministic single-worker scheduling.
    """
    import concurrent.futures as _concurrent_futures

    import numpy as _np
    import scipy.sparse as _sp

    G = _coerce_arg_to_fnx_graph(G)
    max_iter = _coerce_index_arg(max_iter, "max_iter")
    queries = list(personalizations)
    if not queries:
        return []

    N = len(G)
    if N == 0:
        return [{} for _ in queries]

    if isinstance(weight, str):
        _sync_rust_edge_attrs(G, edge_only=True)

    nodelist = list(G)
    A = to_scipy_sparse_array(G, nodelist=nodelist, weight=weight, dtype=float)
    S = _np.asarray(A.sum(axis=1)).ravel()
    S[S != 0] = 1.0 / S[S != 0]
    Q = _sp.csr_array(_sp.spdiags(S.T, 0, *A.shape))
    A = Q @ A
    is_dangling = _np.where(S == 0)[0]

    def _solve(personalization):
        x = _np.repeat(1.0 / N, N)
        if personalization is None:
            p = _np.repeat(1.0 / N, N)
        else:
            p = _np.array(
                [personalization.get(node, 0) for node in nodelist],
                dtype=float,
            )
            if p.sum() == 0:
                raise ZeroDivisionError
            p /= p.sum()

        for _ in range(max_iter):
            xlast = x
            x = alpha * (x @ A + sum(x[is_dangling]) * p) + (1 - alpha) * p
            err = _np.absolute(x - xlast).sum()
            if err < N * tol:
                return dict(zip(nodelist, map(float, x)))
        raise PowerIterationFailedConvergence(max_iter)

    if workers is None:
        # All workers stream the same CSR arrays.  Two saturate this host's
        # useful memory-level parallelism; fanning to every visible core slows
        # the whole job by competing for bandwidth.  Keep the explicit knob for
        # hosts with a different memory topology.
        worker_count = min(2, len(queries))
    else:
        worker_count = _coerce_index_arg(workers, "workers")
        if worker_count < 1:
            raise ValueError("workers must be greater than 0")
    worker_count = min(worker_count, len(queries))

    if worker_count == 1:
        return [_solve(personalization) for personalization in queries]
    with _concurrent_futures.ThreadPoolExecutor(
        max_workers=worker_count,
        thread_name_prefix="fnx-pagerank",
    ) as executor:
        return list(executor.map(_solve, queries))


def _pagerank_inproc(
    G,
    alpha=0.85,
    personalization=None,
    max_iter=100,
    tol=1.0e-6,
    nstart=None,
    weight="weight",
    dangling=None,
):
    from franken_networkx.backend import _fnx_to_nx
    H = _fnx_to_nx(G)
    try:
        return _nx.algorithms.link_analysis.pagerank_alg.pagerank(
            H,
            alpha=alpha,
            personalization=personalization,
            max_iter=max_iter,
            tol=tol,
            nstart=nstart,
            weight=weight,
            dangling=dangling,
            backend="networkx",
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)


def pagerank(
    G,
    alpha=0.85,
    personalization=None,
    max_iter=100,
    tol=1.0e-6,
    nstart=None,
    weight="weight",
    dangling=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Return the PageRank of the nodes in graph ``G``."""
    _validate_backend_dispatch_keywords("pagerank", backend, backend_kwargs)
    # br-r37-c1-y77dc: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)

    # br-r37-c1-pyo3prefix: the Rust binding declares ``max_iter`` as
    # an unsigned int and rejects floats with ``TypeError: argument
    # 'max_iter': 'float' object cannot be interpreted as an
    # integer``.  nx raises the same TypeError via ``range(max_iter)``
    # but *without* the ``argument 'max_iter':`` prefix.  Pre-validate
    # in Python so drop-in callers regex-matching nx's wording match.
    max_iter = _coerce_index_arg(max_iter, "max_iter")

    # The Rust pagerank honours the ``weight`` attribute and matches nx
    # within 1e-16 on non-negative weights. Try the fast-path whenever
    # the unsupported kwargs (personalization / nstart / dangling) are
    # absent; the Rust impl raises NetworkXNotImplemented if it detects
    # negative edge weights (numerically unstable for power iteration),
    # and we fall through to the pure-Python path in that case. Non-string
    # hashable weight keys also stay on the Python path because the PyO3
    # binding accepts only str/None.
    pagerank_weight = weight
    if (
        isinstance(weight, str)
        and not G.is_multigraph()
        and isinstance(G, (Graph, DiGraph))
    ):
        # br-r37-c1-pagerankhaswt: the per-edge ``any(weight in attrs for ... in
        # G.edges(data=True))`` walk was O(E) Python on EVERY call — and for the
        # common UNWEIGHTED graph (no edge carries ``weight``) it scanned every edge
        # to conclude "no weights". Use the native inner-aware presence check
        # (graph_has_edge_attr) instead: same decision, no Python edge walk.
        if not _graph_has_edge_attribute(G, weight):
            pagerank_weight = None

    # br-gauntlet-pagerank-sync: pagerank reads edge weights from the Rust
    # ``inner`` adjacency via native helpers (``_native_has_nonfinite_edge_weight``
    # in the parity scan and ``_native_adjacency_arrays`` in ``_pagerank_scipy``).
    # A post-construction mutation such as ``G.edges[u, v]["weight"] = w`` only
    # updates the Python-side attribute dict, leaving ``inner`` stale, so the
    # native scan/matvec silently ignore the new weights (observable bug: fnx
    # returned the *unweighted* PageRank while nx returned the weighted one).
    # Push Python attrs down only when a real string weight attr can be read.
    if isinstance(pagerank_weight, str):
        _sync_rust_edge_attrs(G, edge_only=True)

    if (
        personalization is None
        and nstart is None
        and dangling is None
        and (pagerank_weight is None or isinstance(pagerank_weight, str))
    ):
        if _pagerank_needs_networkx_weight_parity(G, pagerank_weight):
            return _pagerank_inproc(
                G,
                alpha=alpha,
                personalization=None,
                max_iter=max_iter,
                tol=tol,
                nstart=None,
                weight=pagerank_weight,
                dangling=None,
            )
        # br-r37-c1-y5y7i: use scipy.sparse matvec for 2-3× speedup
        # over pure-Rust scalar iteration on dense graphs.
        return _pagerank_scipy(G, alpha, max_iter, tol, pagerank_weight)

    # br-r37-c1-prscipy (cc): personalization / nstart / dangling case — use the scipy
    # matvec (mirroring nx) instead of the ~5x-slower pure-Python power iteration below.
    # Gated to simple Graph/DiGraph and canonical native multigraphs with
    # str/None weight and dict (or None) vectors. Multigraph sparse conversion
    # already sums parallel edges; keep its uncached matrix so held edge-dict
    # writes remain visible. Multigraph private rows and subclasses retain
    # their own route.
    # Keep scipy's errors: retrying zero-sum personalization or invalid weights
    # in the Python loop changes NetworkX's exception type/message.
    if (
        len(G) > 0
        and (
            (not G.is_multigraph() and isinstance(G, (Graph, DiGraph)))
            or (
                type(G) in (MultiGraph, MultiDiGraph)
                and not _has_networkx_private_storage(G)
            )
        )
        and (pagerank_weight is None or isinstance(pagerank_weight, str))
        and (personalization is None or isinstance(personalization, dict))
        and (nstart is None or isinstance(nstart, dict))
        and (dangling is None or isinstance(dangling, dict))
    ):
        return _pagerank_scipy_personalized(
            G, alpha, personalization, max_iter, tol, nstart, pagerank_weight, dangling
        )

    if len(G) == 0:
        return {}

    directed_graph = G.to_directed()
    nodes = list(directed_graph)
    node_count = len(nodes)

    if nstart is None:
        current = dict.fromkeys(nodes, 1.0 / node_count)
    else:
        current = _normalize_pagerank_vector(nstart, nodes, zero_sum="nan")

    if personalization is None:
        personalization_vector = dict.fromkeys(nodes, 1.0 / node_count)
    else:
        personalization_vector = _normalize_pagerank_vector(personalization, nodes)

    if dangling is None:
        dangling_weights = personalization_vector
    else:
        dangling_weights = _normalize_pagerank_vector(dangling, nodes, zero_sum="nan")

    transition_weights = {}
    dangling_nodes = []
    # br-prcallable: snapshot the out-adjacency ONCE (single native bulk build)
    # instead of indexing ``directed_graph.succ[node]`` per node — the latter
    # rebuilt the whole adjacency dict on every access (O(N^2)).
    _succ_snapshot = dict(directed_graph.adjacency())
    _is_multi = directed_graph.is_multigraph()
    for node in nodes:
        neighbor_weights = _pagerank_outgoing_weights(
            _succ_snapshot[node], weight, _is_multi
        )
        total_weight = _math.fsum(neighbor_weights.values())
        if total_weight == 0:
            transition_weights[node] = None
            dangling_nodes.append(node)
            continue
        transition_weights[node] = {
            nbr: neighbor_weight / total_weight
            for nbr, neighbor_weight in neighbor_weights.items()
        }

    for _ in range(max_iter):
        previous = current
        current = dict.fromkeys(nodes, 0.0)
        dangling_sum = alpha * _math.fsum(previous[node] for node in dangling_nodes)

        for node in nodes:
            neighbor_weights = transition_weights[node]
            if not neighbor_weights:
                continue
            scaled_rank = alpha * previous[node]
            for nbr, neighbor_weight in neighbor_weights.items():
                current[nbr] += scaled_rank * neighbor_weight

        for node in nodes:
            current[node] += (
                dangling_sum * dangling_weights.get(node, 0)
                + (1.0 - alpha) * personalization_vector.get(node, 0)
            )

        error = _math.fsum(abs(current[node] - previous[node]) for node in nodes)
        if error < node_count * tol:
            return current

    raise PowerIterationFailedConvergence(max_iter)
