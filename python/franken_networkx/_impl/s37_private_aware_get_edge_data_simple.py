

# Keep the legacy alias so any internal call sites still resolve.


def _private_aware_get_edge_data_simple(raw_get_edge_data):
    """get_edge_data wrapper for non-multigraph types — nx signature is
    (u, v, default=None) (br-r37-c1-gyn8z).

    br-r37-c1-vbe1o: DEAD, exactly as the has_edge factory above — the live path
    is `_assigned_private_get_edge_data_simple`.
    """
    def get_edge_data(self, u, v, default=None):
        # br-r37-c1-ged-hash: nx propagates ``TypeError: unhashable
        # type: 'X'`` from the underlying ``self._adj[u]`` lookup;
        # fnx's Rust binding silently returned ``default`` on
        # unhashable u/v, masking caller bugs (sister of the
        # has_edge fix br-r37-c1-cvtv6).  Hash-check eagerly.
        _HASH_PROBE.get(u)
        _HASH_PROBE.get(v)
        if not _has_networkx_private_storage(self):
            return raw_get_edge_data(self, u, v, default)
        if not self.has_edge(u, v):
            return default
        return self.adj[u][v]

    return get_edge_data


def _private_aware_get_edge_data_multi(raw_get_edge_data):
    """get_edge_data wrapper for multigraph types — nx signature is
    (u, v, key=None, default=None) (br-r37-c1-gyn8z)."""
    def get_edge_data(self, u, v, key=None, default=None):
        # br-r37-c1-ged-hash: see simple variant above.
        _HASH_PROBE.get(u)
        _HASH_PROBE.get(v)
        # br-r37-c1-mged-keyhash: extend the hash-check to the
        # multigraph ``key`` arg.  nx propagates ``TypeError:
        # unhashable type: '<X>'`` from the inner ``key in
        # neighbors[v]`` dict lookup; fnx's Rust binding caught
        # the error and silently returned ``default`` (or None),
        # masking caller bugs.  Sister of br-r37-c1-exavo
        # (has_edge key fix in cycle 111) and br-r37-c1-cl78j
        # (add_edge mutation fix in cycle 110).
        if key is not None:
            _HASH_PROBE.get(key)
        if not _has_networkx_private_storage(self):
            if key is None:
                return raw_get_edge_data(self, u, v, default=default)
            return raw_get_edge_data(self, u, v, key, default)
        if not self.has_edge(u, v, key):
            return default
        edge_data = self.adj[u][v]
        if key is not None:
            return edge_data[key]
        return edge_data

    return get_edge_data


# Legacy alias retained for callers in the Rust binding tables.


def _private_aware_number_of_nodes(raw_number_of_nodes):
    def number_of_nodes(self):
        storage = self.__dict__
        if _PRIVATE_NODE_OVERRIDE in storage or _SHARED_STORAGE_SOURCE in storage:
            return len(self)
        return raw_number_of_nodes(self)

    return number_of_nodes


# br-r37-c1-s8dj1: the classes whose native `number_of_edges_between` is the
# whole of `number_of_edges(u, v)` -- no edge filtering, no subclass override.
_NATIVE_EDGE_COUNT_CLASSES = (Graph, DiGraph, MultiGraph, MultiDiGraph)
# br-r37-c1-s8dj1: the directed classes whose `has_successor`/`has_predecessor`
# are exactly `has_edge`. Defined here, after the classes exist, and read at CALL
# time by the shims near the top of this module.
_NATIVE_DIRECTED_EDGE_CLASSES = (DiGraph, MultiDiGraph)


def _private_aware_number_of_edges(raw_number_of_edges):
    def number_of_edges(self, u=None, v=None):
        owner = _shared_unsplit_owner(self)
        if owner is not None:
            if (
                u is not None
                and v is not None
                and type(owner) in _NATIVE_EDGE_COUNT_CLASSES
            ):
                return owner.number_of_edges_between(u, v)
            return raw_number_of_edges(owner, u, v)
        # br-r37-c1-s8dj1: the both-endpoints case goes STRAIGHT to the native
        # counter. `raw_number_of_edges` is a Python body, and on MultiDiGraph
        # the native it eventually reaches now answers from node positions
        # (254.7 ns at 2000-character keys) while the Python route around it
        # cost 685.6 ns for the same answer -- the shim, not the lookup, was
        # most of the row.
        #
        # EXACT BASE CLASSES ONLY. A view has its own `number_of_edges` that
        # applies `_edge_visible` filtering, and a subclass may override the
        # count; both must keep the Python body. A graph carrying assigned
        # private storage is excluded by the check below, which still runs
        # first for every other shape.
        if (
            u is not None
            and v is not None
            and type(self) in _NATIVE_EDGE_COUNT_CLASSES
            and not _has_networkx_private_storage(self)
        ):
            return self.number_of_edges_between(u, v)
        if not _has_networkx_private_storage(self):
            return raw_number_of_edges(self, u, v)
        if u is None and v is None:
            # br-r37-c1-vbe1o: nx does not COUNT here, it DERIVES.
            # `number_of_edges()` is `int(self.size())` and `size()` is
            # `sum(d for _, d in self.degree()) // 2`, so the answer comes from
            # the DEGREE view — which already reads assigned storage.
            #
            # Counting `len(self.edges)` instead disagreed on the directed
            # classes, where nx RAISES: total degree needs both `_succ[n]` and
            # `_pred[n]`, so a node carried only by an assigned `_succ`/`_adj`
            # has no `_pred` row and networkx propagates the KeyError. fnx
            # returned a plausible number instead. That single spot accounted
            # for 15 sweep cases, because `size()` and `nx.density` both derive
            # from it.
            #
            # Undirected classes already agreed; the degree formula keeps them
            # agreeing, since multi-degree counts parallel edges with the
            # multiplicity that makes the halving exact.
            return int(sum(d for _, d in self.degree()) // 2)
        if v is None:
            raise TypeError("number_of_edges() missing 1 required positional argument: 'u'")
        if not self.has_edge(u, v):
            return 0
        if self.is_multigraph():
            return len(self.adj[u][v])
        return 1

    return number_of_edges


def _private_aware_neighbors(raw_neighbors, *, attr_name="adj"):
    def neighbors(self, n):
        # Parameter named ``n`` to match networkx (br-r37-c1-classmethsig).
        # br-r37-c1-spg9n: lean warm fast-path. ONE ``vars(self)`` snapshot fused
        # with the private-storage membership checks (instead of a separate
        # ``_has_networkx_private_storage`` call + the per-call guard machinery in
        # ``_cached_adj_row_key_iter`` + a fresh lambda). When the graph has no
        # private storage and a token-valid per-row cache already holds this row,
        # return ``iter(cached_keydict)`` — pure Python, no PyO3 round-trip, like
        # nx's ``iter(self._adj[n])`` (5x slower -> ~2.4x). ``cache.get((attr_name,
        # n))`` hashes ``n``, so unhashable nodes raise ``TypeError`` here exactly
        # as nx does. Cold/miss falls through to the full cached builder.
        ov = vars(self)
        if (
            _PRIVATE_NODE_OVERRIDE not in ov
            and _PRIVATE_ADJ_OVERRIDE not in ov
            and _PRIVATE_SUCC_OVERRIDE not in ov
            and _PRIVATE_PRED_OVERRIDE not in ov
            and _SHARED_STORAGE_SOURCE not in ov
        ):
            cache = ov.get("_fnx_adj_row_keydict_cache")
            if cache is not None and ov.get(
                "_fnx_adj_row_keydict_cache_state"
            ) == (self.nodes_seq, self.edges_seq):
                keydict = cache.get((attr_name, n))
                if keydict is not None:
                    return iter(keydict)
            cached = _cached_adj_row_key_iter(
                self,
                attr_name,
                n,
                lambda: raw_neighbors(self, n),
            )
            if cached is not None:
                return cached
            return raw_neighbors(self, n)
        adjacency = getattr(self, attr_name)
        if n not in self:
            raise NetworkXError(f"The node {n} is not in the graph.")
        return iter(adjacency[n])

    return neighbors


def _private_aware_digraph_successors():
    def successors(self, n):
        ov = vars(self)
        if (
            _PRIVATE_NODE_OVERRIDE not in ov
            and _PRIVATE_ADJ_OVERRIDE not in ov
            and _PRIVATE_SUCC_OVERRIDE not in ov
            and _PRIVATE_PRED_OVERRIDE not in ov
            and _SHARED_STORAGE_SOURCE not in ov
        ):
            state = (self.nodes_seq, self.edges_seq)
            if ov.get("_fnx_succ_row_keydict_cache_state") != state:
                ov["_fnx_succ_row_keydict_cache_state"] = state
                ov["_fnx_succ_row_keydict_cache"] = {}
            cache = ov["_fnx_succ_row_keydict_cache"]
            keydict = cache.get(n)
            if keydict is None:
                _HASH_PROBE.get(n)
                try:
                    keydict = self._native_successor_row_dict(n)
                except KeyError as exc:
                    raise NetworkXError(f"The node {n} is not in the digraph.") from exc
                cache[n] = keydict
            return iter(keydict)
        adjacency = self.succ
        if n not in self:
            raise NetworkXError(f"The node {n} is not in the graph.")
        return iter(adjacency[n])

    return successors


def _private_aware_digraph_predecessors():
    def predecessors(self, n):
        ov = vars(self)
        if (
            _PRIVATE_NODE_OVERRIDE not in ov
            and _PRIVATE_ADJ_OVERRIDE not in ov
            and _PRIVATE_SUCC_OVERRIDE not in ov
            and _PRIVATE_PRED_OVERRIDE not in ov
            and _SHARED_STORAGE_SOURCE not in ov
        ):
            state = (self.nodes_seq, self.edges_seq)
            if ov.get("_fnx_pred_row_keydict_cache_state") != state:
                ov["_fnx_pred_row_keydict_cache_state"] = state
                ov["_fnx_pred_row_keydict_cache"] = {}
            cache = ov["_fnx_pred_row_keydict_cache"]
            keydict = cache.get(n)
            if keydict is None:
                _HASH_PROBE.get(n)
                try:
                    keydict = self._native_predecessor_row_dict(n)
                except KeyError as exc:
                    raise NetworkXError(f"The node {n} is not in the digraph.") from exc
                cache[n] = keydict
            return iter(keydict)
        # br-r37-c1-ppiei: the ASSIGNED mapping is the authority, not the node
        # view. nx is `iter(self._pred[n])` with the KeyError reshaped, so a
        # node reachable only through assigned private storage is answered and
        # a node the mapping lacks is refused -- and `n not in self` got both
        # backwards. It rejected a node present only in an assigned `_pred`
        # (nx returns its predecessors), and it ADMITTED a node present only in
        # an assigned `_node`, letting the raw KeyError out of `adjacency[n]`
        # past every caller catching NetworkXError.
        #
        # `adjacency[n]` hashes `n` exactly as nx's subscript does, so an
        # unhashable node still raises TypeError rather than reporting absence
        # (br-r37-c1-lvlu7).
        adjacency = self.pred
        try:
            row = adjacency[n]
        except KeyError as exc:
            raise NetworkXError(f"The node {n} is not in the digraph.") from exc
        return iter(row)

    return predecessors


# br-r37-c1-l7ww9: `__iter__` is NOT rebound either — see `__len__` above.
# br-r37-c1-l7ww9: `__len__` is NOT rebound — the native slot is private-storage
# aware, so `len(G)` reaches it with no Python frame at all.

Graph.nodes = _private_aware_nodes(_GRAPH_PRIVATE_AWARE_NODES)
DiGraph.nodes = _private_aware_nodes(_DIGRAPH_PRIVATE_AWARE_NODES)
MultiGraph.nodes = _private_aware_nodes(_MULTIGRAPH_PRIVATE_AWARE_NODES)
MultiDiGraph.nodes = _private_aware_nodes(_MULTIDIGRAPH_PRIVATE_AWARE_NODES)
Graph.edges = _private_aware_edges(_GRAPH_PRIVATE_AWARE_EDGES)
DiGraph.edges = _private_aware_edges(_DIGRAPH_PRIVATE_AWARE_EDGES)
MultiGraph.edges = _private_aware_edges(_MULTIGRAPH_PRIVATE_AWARE_EDGES)
MultiDiGraph.edges = _private_aware_edges(_MULTIDIGRAPH_PRIVATE_AWARE_EDGES)
Graph.degree = _private_aware_degree(_GRAPH_PRIVATE_AWARE_DEGREE)
DiGraph.degree = _private_aware_degree(_DIGRAPH_PRIVATE_AWARE_DEGREE)
MultiGraph.degree = _private_aware_degree(_MULTIGRAPH_PRIVATE_AWARE_DEGREE)
MultiDiGraph.degree = _private_aware_degree(_MULTIDIGRAPH_PRIVATE_AWARE_DEGREE)

# br-r37-c1-hwu8a (cc): the DIRECTED siblings of the accessors converted above.
# `in_degree`/`out_degree`/`in_edges`/`out_edges` were still plain `property`
# objects, so — exactly like `nodes`/`edges`/`degree` before br-r37-c1-wbwkb —
# their Python body re-ran on every access while nx serves all four from
# `@cached_property`. Measured per-access before this change: `in_degree` 0.365x,
# `out_degree` 0.371x, `in_edges` 0.290x, `out_edges` 0.293x of nx (DiGraph;
# MultiDiGraph 0.244-0.394x), against 0.90-1.05x for the already-converted
# accessors on the same graphs.
#
# The build closures are reused verbatim (`fget` of the property being replaced),
# so the view each accessor returns is unchanged. For `in_degree`/`out_degree`
# that view was already memoised in `_fnx_view_{in,out}_degree`, so identity is
# unchanged; for `in_edges`/`out_edges` the getter built a FRESH
# `_DiEdgeMethodView` per access, which made `G.out_edges is G.out_edges` False
# where nx's cached_property makes it True — memoising fixes that divergence.
# Sharing one instance is safe: `_DiEdgeMethodView` is `__slots__ =
# ("_graph", "_method")` with no mutable per-instance state; every method reads
# through to the graph.
#
# Only setter-less accessors may be converted (a setter means the attribute
# installs networkx private storage and must stay a DATA descriptor), so the
# guard below skips anything carrying one rather than silently dropping it.
for _cls, _accessor in (
    (DiGraph, "in_degree"),
    (DiGraph, "out_degree"),
    (MultiDiGraph, "in_degree"),
    (MultiDiGraph, "out_degree"),
    (DiGraph, "in_edges"),
    (DiGraph, "out_edges"),
    (MultiDiGraph, "in_edges"),
    (MultiDiGraph, "out_edges"),
):
    _installed = _cls.__dict__.get(_accessor)
    if isinstance(_installed, property) and _installed.fset is None:
        setattr(_cls, _accessor, _CachedViewDescriptor(_installed.fget, _accessor))
del _cls, _accessor, _installed

# br-r37-c1-qmi5w / br-r37-c1-6q4wl: install raw primitive descriptors for
# ordinary graphs. ``_set_private_override`` restores mapping-aware behavior
# per instance if a NetworkX utility assigns one of its private stores.
def _has_node_through_the_membership_slot(self, n):
    """``G.has_node(n)`` answered by ``n in G``.

    br-r37-c1-hasnode-slot: the native ``has_node`` method and the native
    ``__contains__`` slot are the SAME question with the same body - both take
    the identity-int fast path, then the exact-``str`` present-set memo, then the
    borrowed canonical probe - and one of them is twice the price of the other.
    Measured on this interpreter, 2000-node str-keyed graphs, min of 11 blocks of
    512 calls, all four classes, against live networkx in the same process:

        class          has_node    n in G   ratio      networkx
        Graph            768.9      447.2   1.72x          68.4
        DiGraph          716.5      446.4   1.61x          70.2
        MultiGraph       749.5      445.3   1.68x          71.3
        MultiDiGraph     775.6      570.1   1.36x          70.3

    THE DIFFERENCE IS THE CALLING CONVENTION, not the work, and that was
    established by controls rather than inferred. A trivial native SLOT on the
    same object (``len(G)``) costs 265ns and a trivial native METHOD
    (``G.number_of_nodes()``) costs 303ns, so a no-argument method pays only
    ~38ns over a slot; the same comparison with ONE argument is ~370ns. PyO3's
    method trampoline accepts keywords - ``G.has_node(n='a')`` works, and must
    keep working, because networkx's plain ``def`` accepts it too - so every call
    carries argument-binding machinery the slot wrapper does not have.

    REFUTED on the way, so nobody re-runs it: GC traversal is NOT the mechanism.
    ``PyGraph.__traverse__`` visits every node key, adjacency key and attr dict,
    which made a gen-0 collection look like a plausible per-call tax; with
    ``gc.disable()`` the numbers do not move (len 265->286, has_node 744->741).
    Nor is it data-dependent: ``len(G)`` is 267ns at 100 nodes and 283ns at
    40000, so the floor is per-call, not per-graph.

    A Python frame is added here and it is still 1.7x cheaper - the frame costs
    ~20ns against the ~320ns the trampoline costs. The slot is also the more
    faithful path: ``__contains__`` consults assigned NetworkX private storage
    (``private_node_contains``) where the native ``has_node`` does not read it at
    all, and the two answer identically on every key type tested - present,
    missing, int, bool, float, tuple, None, an unhashable ``str`` subclass, and a
    graph carrying an assigned ``_node`` mapping.
    """
    return n in self


Graph.has_node = _has_node_through_the_membership_slot
DiGraph.has_node = _has_node_through_the_membership_slot
MultiGraph.has_node = _has_node_through_the_membership_slot
MultiDiGraph.has_node = _has_node_through_the_membership_slot
# br-r37-c1-hasnode-slot: the slot-routed `has_node` is a RAW implementation
# too, and `_RAW_HAS_NODE_METHODS` is how a graph that later receives assigned
# private storage decides whether its class attribute is one it must shadow.
# Leaving it out silently stopped installing the `_assigned_private_has_node`
# shadow - test_private_shadow_state_guard caught that within a minute, because
# the widened state no longer contained `has_node`. Extended HERE rather than at
# the tuple's definition because the function has to exist first.
_RAW_HAS_NODE_METHODS = _RAW_HAS_NODE_METHODS + (
    _has_node_through_the_membership_slot,
)
Graph.has_edge = _GRAPH_PRIVATE_AWARE_HAS_EDGE
DiGraph.has_edge = _DIGRAPH_PRIVATE_AWARE_HAS_EDGE
MultiGraph.has_edge = _MULTIGRAPH_PRIVATE_AWARE_HAS_EDGE
MultiDiGraph.has_edge = _MULTIDIGRAPH_PRIVATE_AWARE_HAS_EDGE
Graph.get_edge_data = _GRAPH_PRIVATE_AWARE_GET_EDGE_DATA
DiGraph.get_edge_data = _DIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA
MultiGraph.get_edge_data = _MULTIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA
MultiDiGraph.get_edge_data = _MULTIDIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA


# br-r37-c1-nv-hash: the directed and multigraph NodeView bindings still
# silently return False on unhashable items, whereas nx propagates
# ``TypeError: unhashable type: 'X'`` from its dict lookup. Keep their Python
# hash guards until their native slots grow the same check. The ordinary Graph
# sibling moved that guard into Rust in br-r37-c1-m7xek, so wrapping it here
# would reintroduce the hot Python frame that native slot removes.
# br-r37-c1-uk664: the Python `hash(item)` wrapper that used to be installed on
# DiNodeView / MultiGraphNodeView / MultiDiGraphNodeView is GONE. It existed only
# to enforce networkx's unhashable-key TypeError, and all three native slots now
# do that themselves (br-r37-c1-alll4 for the multigraphs, br-r37-c1-uk664 for
# the directed one) — exactly as the simple NodeView always has. Keeping it cost
# a Python frame on every membership probe.
Graph.number_of_nodes = _GRAPH_PRIVATE_AWARE_NUMBER_OF_NODES
DiGraph.number_of_nodes = _DIGRAPH_PRIVATE_AWARE_NUMBER_OF_NODES
MultiGraph.number_of_nodes = _MULTIGRAPH_PRIVATE_AWARE_NUMBER_OF_NODES
MultiDiGraph.number_of_nodes = _MULTIDIGRAPH_PRIVATE_AWARE_NUMBER_OF_NODES
Graph.order = _GRAPH_PRIVATE_AWARE_NUMBER_OF_NODES
DiGraph.order = _DIGRAPH_PRIVATE_AWARE_NUMBER_OF_NODES
MultiGraph.order = _MULTIGRAPH_PRIVATE_AWARE_NUMBER_OF_NODES
MultiDiGraph.order = _MULTIDIGRAPH_PRIVATE_AWARE_NUMBER_OF_NODES
Graph.number_of_edges = _private_aware_number_of_edges(_GRAPH_PRIVATE_AWARE_NUMBER_OF_EDGES)
DiGraph.number_of_edges = _private_aware_number_of_edges(_DIGRAPH_PRIVATE_AWARE_NUMBER_OF_EDGES)
MultiGraph.number_of_edges = _private_aware_number_of_edges(_MULTIGRAPH_PRIVATE_AWARE_NUMBER_OF_EDGES)
MultiDiGraph.number_of_edges = _private_aware_number_of_edges(_MULTIDIGRAPH_PRIVATE_AWARE_NUMBER_OF_EDGES)
# br-r37-c1-heyxu: ordinary DiGraphs call the native live-row iterator
# descriptors directly. Private NetworkX storage restores mapping-aware
# versions through `_install_private_method_shadows`.
# br-r37-c1-6mxtl: `Graph.neighbors` is the native slot, not the Python function
# above. That function read `vars(self)`, tested four private-override keys,
# built a `(nodes_seq, edges_seq)` tuple, compared it to a cache-generation
# marker and probed a per-instance dict before calling
# `_native_adjacency_row_dict` — which already caches its row. A cache in front
# of a cache, worth 1.21x on `list(G.neighbors(n))`. The slot answers the
# private-storage case itself, so no Python frame is left to inspect its result.
#
# Its factory is deleted rather than left unused: `Graph` was its only caller.
# The DiGraph and multigraph bindings below use `_private_aware_neighbors` and
# the raw native descriptors, which are untouched — only the undirected Graph
# has a slot to bind here.
Graph.neighbors = _fnx.Graph._native_neighbors_iter
DiGraph.neighbors = _DIGRAPH_NEIGHBORS
DiGraph.successors = _DIGRAPH_SUCCESSORS
DiGraph.predecessors = _private_aware_digraph_predecessors()
# br-r37-c1-bvwam: the multigraph classes join Graph on a native slot. The
# `_private_aware_neighbors` wrapper they used to carry rebuilt the
# `(nodes_seq, edges_seq)` token from two PyO3 property reads, allocated a tuple
# to compare it and a second tuple to key the per-row cache, all to reach an
# `iter()` that networkx reaches with one cached-hash dict probe — measured
# 0.2515x (MultiGraph) and 0.2331x (MultiDiGraph) on iterator CREATION. The
# native slots answer the private-storage case themselves, so no Python frame is
# left behind to inspect the result. The wrapper stays in the module: the
# `_ASSIGNED_*` private-storage view classes still bind it.
MultiGraph.neighbors = _fnx.MultiGraph._native_neighbors_iter
MultiDiGraph.neighbors = _fnx.MultiDiGraph._native_neighbors_iter
MultiDiGraph.successors = _fnx.MultiDiGraph._native_neighbors_iter
# br-r37-c1-predrow-8vytj: the DiGraph twin, bound the same way and for the same
# reason. The Python body it replaces kept its own keydict cache in the instance
# dict; the native iterator probes the node-index twin of `pred_row_py` instead,
# which is what keeps it flat in node key length.
DiGraph.predecessors = _fnx.DiGraph._native_predecessors_iter
MultiDiGraph.predecessors = _fnx.MultiDiGraph._native_predecessors_iter

Graph.adj = property(
    lambda self: _read_only_private_mapping(
        self,
        _private_adj_mapping(self, _graph_adj_view)
    ),
    lambda self, value: _set_private_override(self, _PRIVATE_ADJ_OVERRIDE, value),
)
Graph._adj = property(
    lambda self: _private_adj_mapping(self, _graph_private_adj_view),
    lambda self, value: _set_private_override(self, _PRIVATE_ADJ_OVERRIDE, value),
)
Graph._node = property(
    _private_node_mapping,
    lambda self, value: _set_private_override(self, _PRIVATE_NODE_OVERRIDE, value),
)
DiGraph.adj = property(
    lambda self: _read_only_private_mapping(
        self,
        _private_directed_adj_mapping(self, _digraph_adj_view)
    ),
    lambda self, value: _set_private_override(self, _PRIVATE_ADJ_OVERRIDE, value),
)
DiGraph._adj = property(
    lambda self: _private_directed_adj_mapping(self, _digraph_private_adj_view),
    lambda self, value: _set_private_override(self, _PRIVATE_ADJ_OVERRIDE, value),
)
DiGraph.succ = property(
    lambda self: _read_only_private_mapping(
        self,
        _private_succ_mapping(self, _digraph_succ_view)
    ),
    lambda self, value: _set_private_override(self, _PRIVATE_SUCC_OVERRIDE, value),
)
DiGraph._succ = property(
    lambda self: _private_succ_mapping(self, _digraph_private_succ_view),
    lambda self, value: _set_private_override(self, _PRIVATE_SUCC_OVERRIDE, value),
)
DiGraph.pred = property(
    lambda self: _read_only_private_mapping(
        self,
        _private_pred_mapping(self, _digraph_pred_view)
    ),
    lambda self, value: _set_private_override(self, _PRIVATE_PRED_OVERRIDE, value),
)
DiGraph._pred = property(
    lambda self: _private_pred_mapping(self, _digraph_private_pred_view),
    lambda self, value: _set_private_override(self, _PRIVATE_PRED_OVERRIDE, value),
)
DiGraph._node = property(
    _private_node_mapping,
    lambda self, value: _set_private_override(self, _PRIVATE_NODE_OVERRIDE, value),
)
MultiGraph.adj = property(
    lambda self: _read_only_private_mapping(
        self,
        _private_adj_mapping(self, _multigraph_adj_view)
    ),
    lambda self, value: _set_private_override(self, _PRIVATE_ADJ_OVERRIDE, value),
)
MultiGraph._adj = property(
    lambda self: _private_adj_mapping(self, _multigraph_private_adj_view),
    lambda self, value: _set_private_override(self, _PRIVATE_ADJ_OVERRIDE, value),
)
MultiGraph._node = property(
    _private_node_mapping,
    lambda self, value: _set_private_override(self, _PRIVATE_NODE_OVERRIDE, value),
)
MultiDiGraph.adj = property(
    lambda self: _read_only_private_mapping(
        self,
        _private_directed_adj_mapping(self, _multidigraph_adj_view)
    ),
    lambda self, value: _set_private_override(self, _PRIVATE_ADJ_OVERRIDE, value),
)
MultiDiGraph._adj = property(
    lambda self: _private_directed_adj_mapping(self, _multidigraph_private_adj_view),
    lambda self, value: _set_private_override(self, _PRIVATE_ADJ_OVERRIDE, value),
)
MultiDiGraph.succ = property(
    lambda self: _read_only_private_mapping(
        self,
        _private_succ_mapping(self, _multidigraph_succ_view)
    ),
    lambda self, value: _set_private_override(self, _PRIVATE_SUCC_OVERRIDE, value),
)
MultiDiGraph._succ = property(
    lambda self: _private_succ_mapping(self, _multidigraph_private_succ_view),
    lambda self, value: _set_private_override(self, _PRIVATE_SUCC_OVERRIDE, value),
)
MultiDiGraph.pred = property(
    lambda self: _read_only_private_mapping(
        self,
        _private_pred_mapping(self, _multidigraph_pred_view)
    ),
    lambda self, value: _set_private_override(self, _PRIVATE_PRED_OVERRIDE, value),
)
MultiDiGraph._pred = property(
    lambda self: _private_pred_mapping(self, _multidigraph_private_pred_view),
    lambda self, value: _set_private_override(self, _PRIVATE_PRED_OVERRIDE, value),
)
MultiDiGraph._node = property(
    _private_node_mapping,
    lambda self, value: _set_private_override(self, _PRIVATE_NODE_OVERRIDE, value),
)

# br-r37-c1-pc4hk: ``Graph.adj`` was the last high-frequency accessor still
# installed as a data-descriptor property. Its getter therefore ran two Python
# frames on every read merely to recover the already-cached AdjacencyView.
# NetworkX exposes the public name as an assignable cached property and keeps
# the load-bearing storage setter on ``_adj``. Mirror that split: ``adj`` is a
# non-data descriptor (then an instance-dict hit), while ``_adj`` above remains
# the private-override data descriptor and invalidates this cache through
# ``_set_private_override``.
_GRAPH_PUBLIC_ADJ_PROPERTY = Graph.__dict__["adj"]
_GRAPH_SETATTR_BEFORE_PUBLIC_ADJ_CACHE = Graph.__setattr__


def _discard_cached_descriptor_marker(self, name):
    """Turn an assignment over a memoized descriptor into user-owned state."""
    cached = vars(self).get(_DESCRIPTOR_CACHED_VIEWS)
    if cached is not None:
        cached.discard(name)
        if not cached:
            vars(self).pop(_DESCRIPTOR_CACHED_VIEWS, None)


def _graph_setattr_with_cached_public_adj(self, name, value):
    # Filtered views deliberately have an empty Rust base and route graph
    # algorithms through a Python adjacency override. Their constructor's
    # ``self.adj = ...`` must therefore keep using the old property's setter;
    # a plain instance attribute would make degree/traversal consult the empty
    # base instead. Ordinary Graph instances still get nx-style public
    # assignment below.
    if name == "adj" and isinstance(self, _FilteredGraphView):
        return _GRAPH_PUBLIC_ADJ_PROPERTY.__set__(self, value)

    # A user assignment after a plain access replaces the memoised view. Remove
    # only its internal-cache marker so deepcopy/pickle preserve the user value,
    # just as they do for any other genuine instance attribute.
    if name == "adj" or name in _COMMON_CACHED_PUBLIC_NAMES:
        _discard_cached_descriptor_marker(self, name)
    result = _GRAPH_SETATTR_BEFORE_PUBLIC_ADJ_CACHE(self, name, value)
    self._fnx_register_gc_dict(vars(self))
    return result


Graph.__setattr__ = _graph_setattr_with_cached_public_adj
Graph.adj = _CachedViewDescriptor(_GRAPH_PUBLIC_ADJ_PROPERTY.fget, "adj")


# MultiGraph is an independent PyO3 class rather than a Graph subclass, so it
# does not inherit Graph's cached public-adjacency descriptor.  Preserve the
# load-bearing ``_adj`` property above, but make ordinary warm ``adj`` reads
# instance-dict hits exactly like the other three graph classes.
_MULTIGRAPH_PUBLIC_ADJ_PROPERTY = MultiGraph.__dict__["adj"]
_MULTIGRAPH_SETATTR_BEFORE_PUBLIC_ADJ_CACHE = MultiGraph.__setattr__


def _multigraph_setattr_with_cached_public_adj(self, name, value):
    if name == "adj" and isinstance(self, _FilteredGraphView):
        return _MULTIGRAPH_PUBLIC_ADJ_PROPERTY.__set__(self, value)

    if name == "adj" or name in _COMMON_CACHED_PUBLIC_NAMES:
        _discard_cached_descriptor_marker(self, name)
    result = _MULTIGRAPH_SETATTR_BEFORE_PUBLIC_ADJ_CACHE(self, name, value)
    self._fnx_register_gc_dict(vars(self))
    return result


MultiGraph.__setattr__ = _multigraph_setattr_with_cached_public_adj
MultiGraph.adj = _CachedViewDescriptor(_MULTIGRAPH_PUBLIC_ADJ_PROPERTY.fget, "adj")


# br-r37-c1-dyuzb: the directed public siblings had the same repeated data-
# descriptor tax as Graph.adj. Keep the load-bearing `_adj` / `_succ` / `_pred`
# properties above, but make the public names assignable cached descriptors.
# Ordinary warm reads then become instance-dict hits. Filtered and reverse
# synthetics deliberately own an empty Rust base and install their live Python
# mappings through public assignments, so their constructor writes must still
# delegate to the captured property setters.
_DIGRAPH_PUBLIC_ADJ_PROPERTIES = {
    "adj": DiGraph.__dict__["adj"],
    "succ": DiGraph.__dict__["succ"],
    "pred": DiGraph.__dict__["pred"],
}
_DIGRAPH_SETATTR_BEFORE_PUBLIC_ADJ_CACHE = DiGraph.__setattr__


def _digraph_setattr_with_cached_public_adjacency(self, name, value):
    if name in _DIGRAPH_PUBLIC_ADJ_PROPERTIES and isinstance(
        self, (_FilteredGraphView, _ReverseDirectedViewBase)
    ):
        return _DIGRAPH_PUBLIC_ADJ_PROPERTIES[name].__set__(self, value)

    if name in _DIGRAPH_PUBLIC_ADJ_PROPERTIES or name in _DIRECTED_CACHED_PUBLIC_NAMES:
        _discard_cached_descriptor_marker(self, name)
    result = _DIGRAPH_SETATTR_BEFORE_PUBLIC_ADJ_CACHE(self, name, value)
    self._fnx_register_gc_dict(vars(self))
    return result


DiGraph.__setattr__ = _digraph_setattr_with_cached_public_adjacency
for _name, _property in _DIGRAPH_PUBLIC_ADJ_PROPERTIES.items():
    setattr(DiGraph, _name, _CachedViewDescriptor(_property.fget, _name))
del _name, _property


# br-r37-c1-a5xrj: MultiDiGraph's public adjacency siblings paid the same
# repeated data-descriptor tax as DiGraph's. Preserve the load-bearing private
# properties above and the synthetic-view assignment path, but let ordinary
# warm public reads resolve from the instance dict.
_MULTIDIGRAPH_PUBLIC_ADJ_PROPERTIES = {
    "adj": MultiDiGraph.__dict__["adj"],
    "succ": MultiDiGraph.__dict__["succ"],
    "pred": MultiDiGraph.__dict__["pred"],
}
_MULTIDIGRAPH_SETATTR_BEFORE_PUBLIC_ADJ_CACHE = MultiDiGraph.__setattr__


def _multidigraph_setattr_with_cached_public_adjacency(self, name, value):
    if name in _MULTIDIGRAPH_PUBLIC_ADJ_PROPERTIES and isinstance(
        self, (_FilteredGraphView, _ReverseDirectedViewBase)
    ):
        return _MULTIDIGRAPH_PUBLIC_ADJ_PROPERTIES[name].__set__(self, value)

    if (
        name in _MULTIDIGRAPH_PUBLIC_ADJ_PROPERTIES
        or name in _DIRECTED_CACHED_PUBLIC_NAMES
    ):
        _discard_cached_descriptor_marker(self, name)
    result = _MULTIDIGRAPH_SETATTR_BEFORE_PUBLIC_ADJ_CACHE(self, name, value)
    self._fnx_register_gc_dict(vars(self))
    return result


MultiDiGraph.__setattr__ = _multidigraph_setattr_with_cached_public_adjacency
for _name, _property in _MULTIDIGRAPH_PUBLIC_ADJ_PROPERTIES.items():
    setattr(MultiDiGraph, _name, _CachedViewDescriptor(_property.fget, _name))
del _name, _property


# br-r37-c1-o1i86: capture the raw Rust __copy__ impls BEFORE the Python
# override below replaces them. The Rust versions clone the inner graph
# wholesale (node order, edge order, adjacency ROW content order all
# byte-identical to the source — what nx's shared-_adj copy.copy shows)
# and clone_ref the per-node/per-edge attr dicts so they stay SHARED.
_RAW_GRAPH_SHALLOWCOPY = {
    Graph: Graph.__copy__,
    DiGraph: DiGraph.__copy__,
    MultiGraph: MultiGraph.__copy__,
    MultiDiGraph: MultiDiGraph.__copy__,
}


def _graph_shallowcopy(self):
    # br-r37-c1-epic-storage-architecture-yr2oc.3: copy.copy(G) is O(1) and shares
    # underlying storage with G, matching NetworkX's copy.copy(G) semantics.
    if isinstance(
        self, (_FilteredGraphView, _ConversionGraphViewBase, _ReverseDirectedViewBase)
    ):
        result = self.copy()
        vars(result)[_GRAPH_ATTR_OVERRIDE] = self.graph
        result._fnx_register_gc_dict(vars(result))
        _reapply_private_overrides(result, _captured_private_overrides(self))
        if getattr(self, "frozen", False):
            freeze(result)
        return result

    cls = type(self)
    result = cls.__new__(cls)
    src_storage = self.__dict__
    dst_storage = result.__dict__
    root = src_storage.get(_SHARED_STORAGE_SOURCE, self)
    dst_storage[_SHARED_STORAGE_SOURCE] = root
    dst_storage[_GRAPH_ATTR_OVERRIDE] = self.graph
    descriptor_cached = src_storage.get(_DESCRIPTOR_CACHED_VIEWS) or ()
    private_method_shadows = src_storage.get(_PRIVATE_NODE_METHOD_SHADOWS) or {}
    for key, val in src_storage.items():
        if key in dst_storage:
            continue
        if key.startswith("_fnx_") or key in descriptor_cached:
            continue
        if key in private_method_shadows and val is private_method_shadows[key]:
            continue
        if key == "frozen":
            continue
        dst_storage[key] = val
    result._fnx_register_gc_dict(dst_storage)
    result._fnx_set_shared_storage(
        root,
        root._node,
        root._adj,
        self.is_directed(),
    )
    overrides = _captured_private_overrides(self)
    if overrides:
        _reapply_private_overrides(result, overrides)
    else:
        _install_private_method_shadows(result, dst_storage)
    if getattr(self, "frozen", False):
        freeze(result)
    return result


Graph.__copy__ = _graph_shallowcopy
DiGraph.__copy__ = _graph_shallowcopy
MultiGraph.__copy__ = _graph_shallowcopy
MultiDiGraph.__copy__ = _graph_shallowcopy


# br-r37-c1-ish29: preserve the frozen flag across pickle. The Rust
# __reduce_ex__ returns (constructor, args, state) with state =
# {'mode', 'runtime_policy', 'nodes', 'edges', 'graph'} — none of
# which carry frozen. Wrap the reduce result to re-apply freeze on
# load when the source was frozen.
def _reconstruct_graph_preserving_frozen(reduce_payload, was_frozen, extra_attrs=None):
    """Module-level pickle reconstructor: rebuild via the inner
    reduce payload, restore custom Python-side instance attrs,
    then re-apply freeze if the source was frozen."""
    cls, args = reduce_payload[0], reduce_payload[1]
    state = reduce_payload[2] if len(reduce_payload) > 2 else None
    obj = cls(*args)
    if state is not None:
        if hasattr(obj, "__setstate__"):
            obj.__setstate__(state)
        else:
            obj.__dict__.update(state)
    # br-r37-c1-8nz0x: re-apply custom instance attrs before freezing
    # so user-set Python-side attributes survive the round trip.
    if extra_attrs:
        for key, val in extra_attrs.items():
            try:
                setattr(obj, key, val)
            except Exception:
                obj.__dict__[key] = val
    if was_frozen:
        freeze(obj)
    return obj


import copyreg

# Capture the Rust __reduce_ex__ before installing our wrapper so we
# can call into it without recursing.
_GRAPH_RAW_REDUCE_EX = Graph.__reduce_ex__
_DIGRAPH_RAW_REDUCE_EX = DiGraph.__reduce_ex__
_MULTIGRAPH_RAW_REDUCE_EX = MultiGraph.__reduce_ex__
_MULTIDIGRAPH_RAW_REDUCE_EX = MultiDiGraph.__reduce_ex__


def _make_reduce_ex_preserving_frozen(raw_reduce_ex):
    def _reduce_ex(self, protocol=2):
        # br-r37-c1-ish29 follow-up: _FilteredGraphView has its own
        # __reduce__ that snapshots to a real Graph copy. Delegate so
        # the SG view's custom path runs instead of our generic one.
        # br-r37-c1-fabqo: a conversion view has one too, and now carries its
        # adjacency as a private override, which the generic path below would
        # re-apply onto the unpickled copy as its `_adj`.
        # br-r37-c1-ndro1: and a reverse view (the generic path rebuilt its
        # empty base).
        if isinstance(
            self, (_FilteredGraphView, _ConversionGraphViewBase, _ReverseDirectedViewBase)
        ):
            return self.__reduce__()
        target = vars(self).get(_SHARED_STORAGE_SOURCE, self)
        inner = raw_reduce_ex(target, protocol)
        if isinstance(inner, tuple) and len(inner) >= 2:
            reconstructor = inner[0]
            if reconstructor is copyreg.__newobj__:
                cls = inner[1][0]
                rest_args = inner[1][1:]
                normalized = (cls, rest_args) + inner[2:]
            else:
                normalized = inner
        else:
            normalized = inner
        was_frozen = bool(getattr(self, "frozen", False))
        # br-r37-c1-8nz0x: capture custom Python-side __dict__ attrs
        # the user set on the graph (e.g. ``g.custom_attr = 'x'``) so
        # they survive pickle, matching nx's __dict__ preservation.
        extra = {}
        # br-r37-c1-wbwkb: skip views memoised under their public name by
        # ``_CachedViewDescriptor`` — see the matching note in _graph_deepcopy.
        descriptor_cached = vars(self).get(_DESCRIPTOR_CACHED_VIEWS) or ()
        private_method_shadows = (
            vars(self).get(_PRIVATE_NODE_METHOD_SHADOWS) or {}
        )
        for key, val in vars(self).items():
            if key.startswith("_fnx_") or key in descriptor_cached:
                continue
            if key in private_method_shadows and val is private_method_shadows[key]:
                continue
            if key == "frozen":
                # Handled separately so the freeze() re-application
                # also restores the mutator overrides.
                continue
            extra[key] = val
        # br-r37-c1-s8obc: carry assigned private stores under their PUBLIC
        # names. The reconstructor applies ``extra`` with setattr, so the
        # interception that stashed them in the first place runs again on the
        # unpickled graph and rebuilds its method shadows.
        extra.update(_captured_private_overrides(self))
        return (
            _reconstruct_graph_preserving_frozen,
            (normalized, was_frozen, extra or None),
        )
    return _reduce_ex


Graph.__reduce_ex__ = _make_reduce_ex_preserving_frozen(_GRAPH_RAW_REDUCE_EX)
DiGraph.__reduce_ex__ = _make_reduce_ex_preserving_frozen(_DIGRAPH_RAW_REDUCE_EX)
MultiGraph.__reduce_ex__ = _make_reduce_ex_preserving_frozen(_MULTIGRAPH_RAW_REDUCE_EX)
MultiDiGraph.__reduce_ex__ = _make_reduce_ex_preserving_frozen(_MULTIDIGRAPH_RAW_REDUCE_EX)


def _reconstruct_filtered_view_as_copy(graph_copy):
    """Module-level pickle reconstructor for _FilteredGraphView.

    `__reduce__` snapshots the filtered view as a real Graph/DiGraph/
    MultiGraph/MultiDiGraph copy at pickle time; this reconstructor
    just returns that copy (re-frozen — SG views are always frozen,
    so the snapshot must inherit that contract to match nx).
    """
    if not getattr(graph_copy, "frozen", False):
        freeze(graph_copy)
    return graph_copy


_FILTERED_GRAPH_VIEW_TYPES = {
    (False, False): type(
        "Graph",
        (_FilteredGraphView, Graph),
        {
            "adjlist_inner_dict_factory": dict,
            "adjlist_outer_dict_factory": dict,
            "edge_attr_dict_factory": dict,
            "graph_attr_dict_factory": dict,
            "node_attr_dict_factory": dict,
            "node_dict_factory": dict,
            "to_directed_class": _to_directed_class,
            "to_undirected_class": _to_undirected_class,
        },
    ),
    (True, False): type(
        "DiGraph",
        (_FilteredGraphView, DiGraph),
        {
            "adjlist_inner_dict_factory": dict,
            "adjlist_outer_dict_factory": dict,
            "edge_attr_dict_factory": dict,
            "graph_attr_dict_factory": dict,
            "node_attr_dict_factory": dict,
            "node_dict_factory": dict,
            "to_directed_class": _to_directed_class,
            "to_undirected_class": _to_undirected_class,
        },
    ),
    (False, True): type(
        "MultiGraph",
        (_FilteredGraphView, MultiGraph),
        {
            "adjlist_inner_dict_factory": dict,
            "adjlist_outer_dict_factory": dict,
            "edge_attr_dict_factory": dict,
            "graph_attr_dict_factory": dict,
            "node_attr_dict_factory": dict,
            "node_dict_factory": dict,
            "edge_key_dict_factory": dict,
            "new_edge_key": _multigraph_new_edge_key,
            "to_directed_class": _to_directed_class,
            "to_undirected_class": _to_undirected_class,
        },
    ),
    (True, True): type(
        "MultiDiGraph",
        (_FilteredGraphView, MultiDiGraph),
        {
            "adjlist_inner_dict_factory": dict,
            "adjlist_outer_dict_factory": dict,
            "edge_attr_dict_factory": dict,
            "graph_attr_dict_factory": dict,
            "node_attr_dict_factory": dict,
            "node_dict_factory": dict,
            "edge_key_dict_factory": dict,
            "new_edge_key": _multigraph_new_edge_key,
            "to_directed_class": _to_directed_class,
            "to_undirected_class": _to_undirected_class,
        },
    ),
}


_FILTERED_SUBCLASS_VIEW_CACHE: dict = {}

# _Set of canonical graph types — instances of these go through the
# precomputed fast path; subclasses go through the subclass-preserving
# dynamic-class path (br-r37-c1-subgraphsub).
_FILTERED_GRAPH_VIEW_TYPES_SOURCE_TYPES = frozenset((
    Graph, DiGraph, MultiGraph, MultiDiGraph,
))


def _generic_filtered_graph_view(graph, *, filter_node=None, filter_edge=None):
    # br-r37-c1-subgraphsub: nx's ``G.subgraph(...)`` /
    # ``G.edge_subgraph(...)`` / ``nx.subgraph_view(G, ...)`` preserves
    # the source graph's subclass — e.g. ``MyG(nx.Graph).subgraph([1])``
    # returns a ``MyG`` instance.  fnx hardcoded the view type via
    # ``_FILTERED_GRAPH_VIEW_TYPES`` keyed only on (directed, multi),
    # so user subclasses got cast to the canonical Graph/DiGraph etc.
    # — drop-in code that uses subclassing for behavior augmentation
    # silently lost the subclass.
    #
    # Fast path: the four canonical types use the precomputed view
    # types (cycle 188 et al rely on these for class-name parity).
    # Subclass path: dynamically build a filtered view class that
    # combines _FilteredGraphView with the user subclass; cache the
    # resulting class by the user type to avoid re-creating each call.
    g_type = type(graph)
    # If g_type is itself a synthetic subclass-preserving filtered view
    # (from a previous subgraph call on a user subclass), reuse it
    # directly so nested subgraphs preserve the user's subclass through
    # MyG.subgraph().subgraph() etc.
    if getattr(g_type, "_fnx_subclass_filtered_view", False):
        view_type = g_type
    elif g_type in _FILTERED_GRAPH_VIEW_TYPES_SOURCE_TYPES or issubclass(
        g_type, _FilteredGraphView
    ):
        # Fast path: canonical graph types or already-filtered canonical
        # views (no user subclass) use the precomputed view type.
        view_type = _FILTERED_GRAPH_VIEW_TYPES[
            (graph.is_directed(), graph.is_multigraph())
        ]
    else:
        view_type = _FILTERED_SUBCLASS_VIEW_CACHE.get(g_type)
        if view_type is None:
            view_type = type(
                g_type.__name__,
                (_FilteredGraphView, g_type),
                {
                    "adjlist_inner_dict_factory": dict,
                    "adjlist_outer_dict_factory": dict,
                    "edge_attr_dict_factory": dict,
                    "graph_attr_dict_factory": dict,
                    "node_attr_dict_factory": dict,
                    "node_dict_factory": dict,
                    "to_directed_class": _to_directed_class,
                    "to_undirected_class": _to_undirected_class,
                    # Marker so nested subgraph calls reuse this class
                    # instead of trying to re-wrap (which would MRO-fail).
                    "_fnx_subclass_filtered_view": True,
                },
            )
            _FILTERED_SUBCLASS_VIEW_CACHE[g_type] = view_type
    return view_type(graph, filter_node=filter_node, filter_edge=filter_edge)




def _copy_preserving_insertion_order(self, as_view=False):
    """Insertion-order-preserving copy for graph classes.

    The Rust clone path canonicalizes undirected endpoints in a few
    constructor/copy paths. Upstream NetworkX preserves the public edge
    orientation from insertion order, so rebuild via the Python edge
    view.

    br-r37-c1-3tlkj: nx.Graph.copy() is a *shallow* copy — the
    documented contract reads "if an attribute is a container, that
    container is shared by the original and the copy." Previously
    we used ``_deepcopy`` for graph/node/edge attrs, which produced
    independent containers (a stronger invariant than nx). Code
    relying on shared mutation of nested attrs (a documented and
    sometimes-load-bearing nx behavior) silently broke. Mirror nx's
    ``dict(...)`` / ``self.graph.update(self.graph)`` semantics.
    Note: copy._deepcopy(G) — the Python built-in — still routes
    through ``__deepcopy__`` and remains a true deep copy.
    """
    if as_view is True:
        return _generic_filtered_graph_view(self)

    # br-r37-c1-8uh84: native insertion-order-preserving clone for exact
    # MultiGraph/MultiDiGraph. The generic path below walks
    # self.edges(keys=True, data=True) via the MultiAdjacencyView lambda chain
    # into add_edges_from (~2100x slower than nx). The native copy reuses the
    # live edge/node attr dicts (shallow .copy()), preserving node + edge order
    # and public endpoint orientation. Gated on exact type so subclasses /
    # filtered views keep the generic rebuild.
    # br-r37-c1-93mx3: an assigned private store must be honoured, so it cannot
    # take the native fast path — that clones the NATIVE storage and never sees
    # the override, so `G.copy()` came back with the native nodes where nx comes
    # back with the assigned ones. nx's copy is
    # `add_nodes_from(self._node.items())` + `add_edges_from(self.edges(...))`:
    # nodes from the override, edges from the still-native `_adj`, UNIONED — so
    # endpoints reachable only through `_adj` reappear. The generic rebuild
    # below has exactly that shape and reproduces nx's answer once the edge view
    # reads the adjacency (br-r37-c1-ka7fd).
    if type(self) in (Graph, DiGraph, MultiGraph, MultiDiGraph) and not (
        _captured_private_overrides(self)
    ):
        target = vars(self).get(_SHARED_STORAGE_SOURCE, self)
        native_copy = getattr(target, "_native_copy", None)
        if native_copy is not None:
            res = native_copy()
            if target is not self:
                res.graph.clear()
                res.graph.update(self.graph)
            return res

    result = type(self)()
    # Shallow: result.graph is a new dict but its values are shared
    # with self.graph (same as nx's G.graph.update(self.graph)).
    result.graph.update(self.graph)
    result.add_nodes_from(
        (node, dict(attrs)) for node, attrs in self.nodes(data=True)
    )
    # br-r37-c1-vbe1o: under assigned private storage, networkx's copy() does NOT
    # go through the edge VIEW — it iterates the raw mapping:
    #
    #     add_edges_from((u, v, d.copy()) for u, nbrs in self._adj.items()
    #                                     for v, d in nbrs.items())
    #
    # The difference is visible and not academic: the undirected edge view emits
    # each edge once via a seen-set, so a one-sided row like {'ZZ': {'b': {}}}
    # is SKIPPED (its partner 'b' was already seen) and 'ZZ' never reaches the
    # copy. The raw double loop has no dedup, so networkx's copy carries the node
    # and fnx's did not. Measured: nx.copy() -> [ZZ, a, b], fnx -> [a, b], while
    # BOTH report nodes(data=True) == [a, b] and edges(data=True) == [(a, b)] —
    # so the views agree and only copy() diverged.
    if _captured_private_overrides(self):
        adjacency = self._adj
        if self.is_multigraph():
            result.add_edges_from(
                (u, v, key, dict(attrs))
                for u, nbrs in adjacency.items()
                for v, keydict in nbrs.items()
                for key, attrs in keydict.items()
            )
        else:
            result.add_edges_from(
                (u, v, dict(attrs))
                for u, nbrs in adjacency.items()
                for v, attrs in nbrs.items()
            )
        return result
    if self.is_multigraph():
        # Use 4-tuples so an edge attribute literally named "key" doesn't
        # collide with add_edge's positional key parameter.
        result.add_edges_from(
            (u, v, key, dict(attrs))
            for u, v, key, attrs in self.edges(keys=True, data=True)
        )
    else:
        result.add_edges_from(
            (u, v, dict(attrs)) for u, v, attrs in self.edges(data=True)
        )
    return result


def _subgraph_with_view(subgraph_impl):
    @_wraps(subgraph_impl)
    def subgraph(self, nodes):
        filt = _subgraph_filter_from_nbunch(self, nodes)
        # br-r37-c1-7en5i: nx COMPOSES a subgraph-of-a-subgraph onto the
        # ORIGINAL graph (a nested view's ._graph is the root), so node
        # iteration uses the ROOT length for the node_ok_shorter threshold
        # (2*len(keep) < len(root)) and yields keep-set order. fnx CHAINED
        # (._graph = the outer VIEW, length = outer) so it took the other
        # branch -> divergent node order + edge orientation, and missed the
        # native-row fast paths. Collapse a pure node-set / default-edge
        # chain onto its concrete root: filt already only holds nodes visible
        # all the way up self, so a root view filtered by filt IS the nested
        # subgraph.
        if (
            filt is not None
            and getattr(self, "_filter_edge_is_default", False)
            and isinstance(getattr(self, "_filter_node", None), _NodeSetFilter)
        ):
            root = self._graph
            while (
                isinstance(root, _FilteredGraphView)
                and getattr(root, "_filter_edge_is_default", False)
                and isinstance(getattr(root, "_filter_node", None), _NodeSetFilter)
            ):
                root = root._graph
            if type(root) in (Graph, DiGraph, MultiGraph, MultiDiGraph):
                return _generic_filtered_graph_view(root, filter_node=filt)
        return _generic_filtered_graph_view(self, filter_node=filt)

    return subgraph


def _graph_to_directed_copy(self):
    # br-r37-c1-todirnative: native Rust deep-copying Graph->DiGraph for exact
    # Graph type (no nx private storage, default to_directed_class). Builds the
    # DiGraph in Rust in nx's adjacency order, deep-copying attrs — ~4x faster
    # than the per-arc Python add_edge loop below. Subclasses / nx-private
    # storage / custom to_directed_class fall through to the generic rebuild.
    if (
        type(self) is Graph
        and not _has_networkx_private_storage(self)
        and self.to_directed_class() is DiGraph
    ):
        native = getattr(self, "_native_to_directed_deepcopy", None)
        if native is not None:
            return native()
    result = self.to_directed_class()()
    result.graph.update(_deepcopy(self.graph))
    result.add_nodes_from((node, _deepcopy(attrs)) for node, attrs in self.nodes(data=True))
    for source in self:
        for target, attrs in self[source].items():
            result.add_edge(source, target, **_deepcopy(attrs))
    return result


def _multigraph_to_directed_copy(self):
    if (
        type(self) is MultiGraph
        and not _has_networkx_private_storage(self)
        and self.to_directed_class() is MultiDiGraph
    ):
        native = getattr(self, "_native_to_directed_deepcopy", None)
        if native is not None:
            return native()

    result = self.to_directed_class()()
    result.graph.update(_deepcopy(self.graph))
    result.add_nodes_from((node, _deepcopy(attrs)) for node, attrs in self.nodes(data=True))
    result.add_edges_from(
        (source, target, key, _deepcopy(attrs))
        for source in self
        for target, keyed_attrs in self.adj[source].items()
        for key, attrs in keyed_attrs.items()
    )
    return result


def _digraph_to_directed_copy(self):
    result = self.to_directed_class()()
    result.graph.update(_deepcopy(self.graph))
    result.add_nodes_from((node, _deepcopy(attrs)) for node, attrs in self.nodes(data=True))
    result.add_edges_from(
        (source, target, _deepcopy(attrs))
        for source in self
        for target, attrs in self.adj[source].items()
    )
    return result


def _multidigraph_to_directed_copy(self):
    if (
        type(self) is MultiDiGraph
        and not _has_networkx_private_storage(self)
        and self.to_directed_class() is MultiDiGraph
    ):
        native = getattr(self, "_native_to_directed_deepcopy", None)
        if native is not None:
            return native()

    result = self.to_directed_class()()
    result.graph.update(_deepcopy(self.graph))
    result.add_nodes_from((node, _deepcopy(attrs)) for node, attrs in self.nodes(data=True))
    result.add_edges_from(
        (source, target, key, _deepcopy(attrs))
        for source in self
        for target, keyed_attrs in self.adj[source].items()
        for key, attrs in keyed_attrs.items()
    )
    return result


def _wraps_without_signature_poisoning(impl, wrapper):
    """Copy ``__name__``, ``__qualname__``, ``__doc__``, and
    ``__module__`` from the Rust impl onto the Python wrapper, but do
    NOT set ``__wrapped__`` — that attribute would make
    ``inspect.signature`` follow back to the empty Rust signature
    (br-r37-c1-5npb6). Keeping the metadata aligned matters for
    error-message formatting, which uses ``__qualname__``."""
    for attr in ("__name__", "__qualname__", "__doc__", "__module__"):
        try:
            value = getattr(impl, attr)
        except AttributeError:
            continue
        try:
            setattr(wrapper, attr, value)
        except (AttributeError, TypeError):
            pass
    return wrapper


def _graph_to_directed_with_view(to_directed_impl):
    def to_directed(self, as_view=False):
        if as_view is True:
            return _generic_directed_graph_view(self)
        return _graph_to_directed_copy(self)

    return _wraps_without_signature_poisoning(to_directed_impl, to_directed)


def _multigraph_to_directed_with_view(to_directed_impl):
    def to_directed(self, as_view=False):
        if as_view is True:
            return _generic_directed_graph_view(self)
        return _multigraph_to_directed_copy(self)

    return _wraps_without_signature_poisoning(to_directed_impl, to_directed)


def _digraph_to_directed_with_view(to_directed_impl):
    def to_directed(self, as_view=False):
        if as_view is True:
            return _generic_directed_graph_view(self)
        return _digraph_to_directed_copy(self)

    return _wraps_without_signature_poisoning(to_directed_impl, to_directed)


def _multidigraph_to_directed_with_view(to_directed_impl):
    def to_directed(self, as_view=False):
        if as_view is True:
            return _generic_directed_graph_view(self)
        return _multidigraph_to_directed_copy(self)

    return _wraps_without_signature_poisoning(to_directed_impl, to_directed)




def _to_undirected_with_view(to_undirected_impl):
    def to_undirected(self, as_view=False):
        if as_view is True:
            return _generic_undirected_graph_view(self)
        if (
            type(self) is MultiGraph
            and not _has_networkx_private_storage(self)
            and self.to_undirected_class() is MultiGraph
        ):
            native = getattr(self, "_native_to_undirected_deepcopy", None)
            if native is not None:
                return native()

        result = self.to_undirected_class()()
        result.graph.update(_deepcopy(self.graph))
        result.add_nodes_from(
            (node, _deepcopy(attrs)) for node, attrs in self.nodes(data=True)
        )
        if self.is_multigraph():
            result.add_edges_from(
                (u, v, key, _deepcopy(attrs))
                for u, v, key, attrs in self.edges(keys=True, data=True)
            )
        else:
            result.add_edges_from(
                (u, v, _deepcopy(attrs)) for u, v, attrs in self.edges(data=True)
            )
        return result

    return _wraps_without_signature_poisoning(to_undirected_impl, to_undirected)


def _directed_to_undirected_with_view(to_undirected_impl):
    def to_undirected(self, reciprocal=False, as_view=False):
        if as_view is True:
            return _generic_undirected_graph_view(self)
        if reciprocal is not True:
            if self.is_multigraph():
                if (
                    type(self) is MultiDiGraph
                    and not _has_networkx_private_storage(self)
                    and self.to_undirected_class() is MultiGraph
                ):
                    native = getattr(self, "_native_to_undirected_deepcopy", None)
                    if native is not None:
                        return native()

                # Iterate in original-direction order so the undirected
                # edge orientation matches upstream nx, which preserves
                # (u, v) as added (the rust to_undirected_impl
                # canonicalises endpoints and diverges from nx on
                # MultiDiGraph where an edge was added one-way).
                result = self.to_undirected_class()()
                result.graph.update(_deepcopy(self.graph))
                result.add_nodes_from(
                    (node, _deepcopy(attrs)) for node, attrs in self.nodes(data=True)
                )
                result.add_edges_from(
                    (u, v, key, _deepcopy(attrs))
                    for u in self
                    for v, keyed_attrs in self.adj[u].items()
                    for key, attrs in keyed_attrs.items()
                )
                return result

            # br-r37-c1-l5ve7: native bulk path for the exact-type case —
            # the Python add_edges_from walk paid ~1.1M interpreter calls
            # on a 12k-edge graph.
            if (
                type(self) is DiGraph
                and not _has_networkx_private_storage(self)
                and self.to_undirected_class() is Graph
            ):
                native = getattr(self, "_native_to_undirected_deepcopy", None)
                if native is not None:
                    return native()

            result = self.to_undirected_class()()
            result.graph.update(_deepcopy(self.graph))
            result.add_nodes_from(
                (node, _deepcopy(attrs)) for node, attrs in self.nodes(data=True)
            )
            result.add_edges_from(
                (u, v, _deepcopy(attrs))
                for u in self
                for v, attrs in self.adj[u].items()
            )
            return result

        # br-r37-c1-fiitj: the exact classes take the native deep copy with the
        # reciprocal filter, as reciprocal=False already does; the Python
        # rebuild below ran 0.56-0.59x networkx.
        if (
            (type(self) is DiGraph and self.to_undirected_class() is Graph)
            or (type(self) is MultiDiGraph and self.to_undirected_class() is MultiGraph)
        ) and not _has_networkx_private_storage(self):
            native = getattr(self, "_native_to_undirected_deepcopy", None)
            if native is not None:
                return native(reciprocal=True)

        result = self.to_undirected_class()()
        result.graph.update(_deepcopy(self.graph))
        result.add_nodes_from((node, _deepcopy(attrs)) for node, attrs in self.nodes(data=True))
        # br-cc-recip: the reciprocal filter iterated ``self.adj[u]`` /
        # ``self.pred[u]`` (the pure-Python keydict views) O(|E|) times -> 0.03x
        # (DiGraph, 68ms) / 0.08x (MultiDiGraph). Read the edges via the FAST
        # native ``edges()`` and test reciprocity as O(1) set membership on the
        # directed ``(u, v, key)`` / ``(u, v)`` triples. ``edges()`` walks the
        # adjacency node-major (same order as the old view loop), and
        # ``(v, u, key) in edge_set`` is exactly ``key in self.pred[u][v]``, so
        # the kept edges, their order, and the deepcopied attrs are byte-identical.
        if self.is_multigraph():
            _edges = list(self.edges(keys=True, data=True))
            _edge_set = {(u, v, key) for u, v, key, _ in _edges}
            result.add_edges_from(
                (u, v, key, _deepcopy(attrs))
                for u, v, key, attrs in _edges
                if (v, u, key) in _edge_set
            )
        else:
            _edges = list(self.edges(data=True))
            _edge_set = {(u, v) for u, v, _ in _edges}
            result.add_edges_from(
                (u, v, _deepcopy(attrs))
                for u, v, attrs in _edges
                if (v, u) in _edge_set
            )
        return result

    return _wraps_without_signature_poisoning(to_undirected_impl, to_undirected)
