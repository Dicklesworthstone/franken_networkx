

_RAW_ADD_EDGE_BY_CLASS = {
    Graph: Graph.add_edge,
    DiGraph: DiGraph.add_edge,
    MultiGraph: MultiGraph.add_edge,
    MultiDiGraph: MultiDiGraph.add_edge,
}
_RAW_ADD_EDGE_METHODS = tuple(_RAW_ADD_EDGE_BY_CLASS.values())

_RAW_ADD_NODES_FROM_BY_CLASS = {
    Graph: Graph.add_nodes_from,
    DiGraph: DiGraph.add_nodes_from,
    MultiGraph: MultiGraph.add_nodes_from,
    MultiDiGraph: MultiDiGraph.add_nodes_from,
}
_RAW_ADD_NODES_FROM_METHODS = tuple(_RAW_ADD_NODES_FROM_BY_CLASS.values())


def _assigned_private_add_edges_from(self, ebunch_to_add, **attr):
    """add_edges_from for a graph carrying assigned private storage.

    networkx builds this on add_edge, so fixing add_edge fixed it there. fnx's is
    a native kernel that never reaches the corrected path — the same asymmetry
    add_nodes_from showed. Each batch method therefore needs its own shadow; the
    sweep is what says which ones still do.

    Arities are networkx's: (u, v) and (u, v, datadict) for simple graphs, plus
    (u, v, key, datadict) and the ambiguous 3-tuple for multigraphs, where the
    third element is a KEY if it is not a mapping.
    """
    owner = _shared_unsplit_owner(self)
    if owner is not None:
        raw = _RAW_ADD_EDGES_FROM_BY_CLASS.get(type(owner))
        if raw is not None:
            return raw(owner, ebunch_to_add, **attr)
        return owner.add_edges_from(ebunch_to_add, **attr)
    multi = self.is_multigraph()
    keys = [] if multi else None
    for e in ebunch_to_add:
        ne = len(e)
        key = None
        if ne == 4 and multi:
            u, v, key, dd = e
        elif ne == 3:
            u, v, dd = e
        elif ne == 2:
            u, v = e
            dd = {}
        else:
            raise NetworkXError(f"Edge tuple {e!r} must be a 2-tuple, 3-tuple or 4-tuple.")
        merged = dict(attr)
        try:
            merged.update(dd)
        except (TypeError, ValueError):
            if not multi or ne != 3:
                raise
            key = dd
        if multi:
            keys.append(_assigned_private_add_edge_multi_data(self, u, v, key, merged))
        else:
            _assigned_private_add_edge_simple_data(self, u, v, merged)
    return keys


def _assigned_private_add_weighted_edges_from(
    self, ebunch_to_add, weight="weight", **attr
):
    """networkx: add_edges_from((u, v, {weight: d}) for u, v, d in ebunch)."""
    owner = _shared_unsplit_owner(self)
    if owner is not None:
        raw = _RAW_ADD_WEIGHTED_BY_CLASS.get(type(owner))
        if raw is not None:
            return raw(owner, ebunch_to_add, weight=weight, **attr)
        return owner.add_weighted_edges_from(ebunch_to_add, weight=weight, **attr)
    _assigned_private_add_edges_from(
        self,
        ((u, v, {weight: d}) for u, v, d in ebunch_to_add),
        **attr,
    )


_RAW_ADD_EDGES_FROM_BY_CLASS = {
    Graph: Graph.add_edges_from,
    DiGraph: DiGraph.add_edges_from,
    MultiGraph: MultiGraph.add_edges_from,
    MultiDiGraph: MultiDiGraph.add_edges_from,
}
_RAW_ADD_EDGES_FROM_METHODS = tuple(_RAW_ADD_EDGES_FROM_BY_CLASS.values())

_RAW_ADD_WEIGHTED_BY_CLASS = {
    Graph: Graph.add_weighted_edges_from,
    DiGraph: DiGraph.add_weighted_edges_from,
    MultiGraph: MultiGraph.add_weighted_edges_from,
    MultiDiGraph: MultiDiGraph.add_weighted_edges_from,
}
_RAW_ADD_WEIGHTED_METHODS = tuple(_RAW_ADD_WEIGHTED_BY_CLASS.values())


def _assigned_private_mappings(self, storage):
    """Every assigned mapping this graph carries, adjacency-side first."""
    out = []
    for key in (_PRIVATE_ADJ_OVERRIDE, _PRIVATE_SUCC_OVERRIDE, _PRIVATE_PRED_OVERRIDE):
        mapping = storage.get(key)
        if mapping is not None and mapping not in out:
            out.append(mapping)
    return out


def _assigned_private_remove_node(self, n):
    """remove_node for a graph carrying assigned private storage (br-r37-c1-wv3cu).

    networkx deletes the node's row AND every back-reference to it:

        nbrs = list(_adj[n]); del _node[n]
        for u in nbrs: del _adj[u][n]
        del _adj[n]

    The back-references are the part that a naive `del mapping[n]` misses — the
    node would vanish from the keys while still appearing inside its neighbours'
    rows, which is a corrupt graph rather than a partial fix.

    Existence is decided by the ASSIGNED mapping, since that is the storage: a
    node present only natively is still absent as far as networkx is concerned.
    """
    storage = vars(self)
    owner = _shared_unsplit_owner(self, storage)
    if owner is not None:
        raw = _RAW_REMOVE_NODE_BY_CLASS.get(type(owner))
        if raw is not None:
            return raw(owner, n)
        return owner.remove_node(n)
    target = storage.get(_SHARED_STORAGE_SOURCE, self)
    mappings = _assigned_private_mappings(self, storage)
    node_map = storage.get(_PRIVATE_NODE_OVERRIDE)

    # networkx's order decides the contract, and it needs BOTH:
    #
    #     nbrs = list(_adj[n])      # KeyError if absent from the adjacency
    #     del _node[n]              # KeyError if absent from the node mapping
    #
    # so a node present in an assigned `_adj` but not in `_node` RAISES, and so
    # does the reverse. My first version accepted either and got remove_node('a')
    # right while breaking remove_node('ZZ') — the sweep went 32 to 30 instead of
    # 32 to 7, which is what said the authority was wrong rather than missing.
    if n not in self._adj or n not in self._node:
        graph_kind = "digraph" if self.is_directed() else "graph"
        raise NetworkXError(f"The node {n} is not in the {graph_kind}.")

    directed_mapping_data = None
    if self.is_directed():
        forward, backward = _assigned_private_edge_targets(self, storage)
        # Capture both sides before the native removal mutates its own rows.
        # A private `_succ` can coexist with a native `_pred`, and looking up
        # the latter afterwards turns NetworkX's successful removal into a
        # KeyError merely because fnx has already removed the native node.
        successors = (
            list(forward.get(n, ())) if forward is not None else list(self._succ[n])
        )
        predecessors = (
            list(backward.get(n, ())) if backward is not None else list(self._pred[n])
        )
        directed_mapping_data = (forward, backward, successors, predecessors)

    raw = _private_native_method(target, _RAW_REMOVE_NODE_BY_CLASS)
    if raw is not None:
        try:
            raw(target, n)
        except Exception:  # noqa: BLE001 - absent natively is fine; storage rules
            pass

    if node_map is not None:
        node_map.pop(n, None)
    if self.is_directed():
        assert directed_mapping_data is not None
        forward, backward, successors, predecessors = directed_mapping_data
        # DiGraph.remove_node uses successors to edit `_pred`, and predecessors
        # to edit `_succ`.  With only one side assigned, it must not scan every
        # row in that mapping: an edge visible only on the assigned successor
        # side has no matching native predecessor and therefore survives, just
        # as it does in NetworkX's split private storage.
        if forward is not None:
            for predecessor in predecessors:
                row = forward.get(predecessor)
                if row is not None:
                    row.pop(n, None)
            forward.pop(n, None)
        if backward is not None:
            for successor in successors:
                row = backward.get(successor)
                if row is not None:
                    row.pop(n, None)
            backward.pop(n, None)
    else:
        for mapping in mappings:
            for nbr in list(mapping.get(n, ())):
                row = mapping.get(nbr)
                if row is not None:
                    row.pop(n, None)
            for row in mapping.values():
                row.pop(n, None)
            mapping.pop(n, None)


def _assigned_private_remove_edge(self, u, v, key=None):
    """remove_edge: drop the pair from every assigned mapping, both directions."""
    storage = vars(self)
    multi = self.is_multigraph()
    owner = _shared_unsplit_owner(self, storage)
    if owner is not None:
        raw = _RAW_REMOVE_EDGE_BY_CLASS.get(type(owner))
        if raw is not None:
            return raw(owner, u, v, key) if (multi and key is not None) else raw(owner, u, v)
        return owner.remove_edge(u, v, key) if (multi and key is not None) else owner.remove_edge(u, v)
    target = storage.get(_SHARED_STORAGE_SOURCE, self)
    if self.is_directed():
        forward, backward = _assigned_private_edge_targets(self, storage)
        targets = [(forward, u, v)] if forward is not None else []
        if backward is not None:
            targets.append((backward, v, u))
    else:
        adjacency = storage.get(_PRIVATE_ADJ_OVERRIDE)
        targets = [(adjacency, u, v), (adjacency, v, u)] if adjacency is not None else []

    # Assigning `_node` does not replace the edge mapping.  In that split state
    # the native adjacency remains NetworkX's authority for remove_edge.
    if not targets:
        raw = _private_native_method(target, _RAW_REMOVE_EDGE_BY_CLASS)
        if raw is not None:
            return raw(target, u, v, key) if (multi and key is not None) else raw(target, u, v)

    forward_mapping, forward_u, forward_v = targets[0]
    if forward_mapping is None or forward_v not in forward_mapping.get(forward_u, {}):
        raise NetworkXError(f"The edge {u}-{v} is not in the graph.")

    if multi:
        keydict = forward_mapping[forward_u][forward_v]
        # Select and validate without mutating a live native keydict yet.
        # The native remover detaches its last key's row; deleting through the
        # keydict first would leave a registered empty native ghost pair.
        if key is None:
            if not keydict:
                raise KeyError("popitem(): dictionary is empty")
            key = next(reversed(keydict))
        else:
            try:
                keydict[key]
            except KeyError as exc:
                raise NetworkXError(
                    f"The edge {u}-{v} with key {key} is not in the graph."
                ) from exc

    # Use the underlying writer so validation remains with the assigned row,
    # and perform the public wrapper's cache invalidation ourselves.
    raw = _private_native_method(target, _NATIVE_REMOVE_EDGE_BY_CLASS)
    if raw is not None:
        try:
            raw(target, u, v, key) if (multi and key is not None) else raw(target, u, v)
            _invalidate_adjacency_row_caches(target)
        except Exception:  # noqa: BLE001 - the assigned mapping is the authority
            pass

    seen = set()
    removed_keydicts = set()
    for mapping, a, b in targets:
        if mapping is None or (id(mapping), a, b) in seen:
            continue
        seen.add((id(mapping), a, b))
        row = mapping.get(a)
        if row is None or b not in row:
            continue
        if multi:
            keydict = row[b]
            if id(keydict) not in removed_keydicts:
                keydict.pop(key, None)
                removed_keydicts.add(id(keydict))
            if not keydict:
                row.pop(b, None)
        else:
            row.pop(b, None)


def _assigned_private_remove_edges_from(self, ebunch):
    """NetworkX's tolerant batch removal, routed through assigned storage."""
    owner = _shared_unsplit_owner(self)
    if owner is not None:
        raw = _RAW_REMOVE_EDGES_FROM_BY_CLASS.get(type(owner))
        if raw is not None:
            return raw(owner, ebunch)
        return owner.remove_edges_from(ebunch)
    multi = self.is_multigraph()
    for edge in ebunch:
        try:
            if multi:
                _assigned_private_remove_edge(self, *edge[:3])
            else:
                u, v = edge[:2]
                _assigned_private_remove_edge(self, u, v)
        except NetworkXError:
            # ``remove_edges_from`` ignores edges that are absent at the time
            # each entry is visited; singular ``remove_edge`` must still raise.
            continue


def _assigned_private_clear(self):
    """clear(): networkx empties the assigned mappings themselves."""
    storage = vars(self)
    owner = _shared_unsplit_owner(self, storage)
    if owner is not None:
        raw = _RAW_CLEAR_BY_CLASS.get(type(owner))
        if raw is not None:
            raw(owner)
        else:
            owner.clear()
        self.graph.clear()
        return
    target = storage.get(_SHARED_STORAGE_SOURCE, self)
    raw = _private_native_method(target, _RAW_CLEAR_BY_CLASS)
    if raw is not None:
        raw(target)
    self.graph.clear()
    node_map = storage.get(_PRIVATE_NODE_OVERRIDE)
    if node_map is not None:
        node_map.clear()
    for mapping in _assigned_private_mappings(self, storage):
        mapping.clear()


def _assigned_private_clear_edges(self):
    """clear_edges(): rows survive, their contents do not."""
    storage = vars(self)
    owner = _shared_unsplit_owner(self, storage)
    if owner is not None:
        raw = _RAW_CLEAR_EDGES_BY_CLASS.get(type(owner))
        if raw is not None:
            return raw(owner)
        return owner.clear_edges()
    target = storage.get(_SHARED_STORAGE_SOURCE, self)
    raw = _private_native_method(target, _RAW_CLEAR_EDGES_BY_CLASS)
    if raw is not None:
        raw(target)
    for mapping in _assigned_private_mappings(self, storage):
        for row in mapping.values():
            row.clear()


_RAW_REMOVE_NODE_BY_CLASS = {
    Graph: Graph.remove_node,
    DiGraph: DiGraph.remove_node,
    MultiGraph: MultiGraph.remove_node,
    MultiDiGraph: MultiDiGraph.remove_node,
}
_RAW_REMOVE_NODE_METHODS = tuple(_RAW_REMOVE_NODE_BY_CLASS.values())

_RAW_REMOVE_EDGE_BY_CLASS = {
    Graph: Graph.remove_edge,
    DiGraph: DiGraph.remove_edge,
    MultiGraph: MultiGraph.remove_edge,
    MultiDiGraph: MultiDiGraph.remove_edge,
}
_RAW_REMOVE_EDGE_METHODS = tuple(_RAW_REMOVE_EDGE_BY_CLASS.values())

_NATIVE_REMOVE_EDGE_BY_CLASS = {
    Graph: _GRAPH_REMOVE_EDGE,
    DiGraph: _DIGRAPH_REMOVE_EDGE,
    MultiGraph: _MULTIGRAPH_REMOVE_EDGE,
    MultiDiGraph: _MULTIDIGRAPH_REMOVE_EDGE,
}

_RAW_REMOVE_EDGES_FROM_BY_CLASS = {
    Graph: Graph.remove_edges_from,
    DiGraph: DiGraph.remove_edges_from,
    MultiGraph: MultiGraph.remove_edges_from,
    MultiDiGraph: MultiDiGraph.remove_edges_from,
}
_RAW_REMOVE_EDGES_FROM_METHODS = tuple(_RAW_REMOVE_EDGES_FROM_BY_CLASS.values())

_RAW_CLEAR_BY_CLASS = {
    Graph: Graph.clear,
    DiGraph: DiGraph.clear,
    MultiGraph: MultiGraph.clear,
    MultiDiGraph: MultiDiGraph.clear,
}
_RAW_CLEAR_METHODS = tuple(_RAW_CLEAR_BY_CLASS.values())

_RAW_CLEAR_EDGES_BY_CLASS = {
    Graph: Graph.clear_edges,
    DiGraph: DiGraph.clear_edges,
    MultiGraph: MultiGraph.clear_edges,
    MultiDiGraph: MultiDiGraph.clear_edges,
}
_RAW_CLEAR_EDGES_METHODS = tuple(_RAW_CLEAR_EDGES_BY_CLASS.values())


def _assigned_private_has_edge_simple(self, u, v):
    owner = _shared_unsplit_owner(self)
    if owner is not None:
        raw = _DIGRAPH_PRIVATE_AWARE_HAS_EDGE if owner.is_directed() else _GRAPH_PRIVATE_AWARE_HAS_EDGE
        return raw(owner, u, v)
    _HASH_PROBE.get(u)
    _HASH_PROBE.get(v)
    # br-r37-c1-vbe1o: NO node-view probe. nx is `v in self._adj[u]` with the
    # KeyError caught, so the ADJACENCY is the sole authority on whether `u`
    # exists. `u not in self` asked the node view, and under an assigned `_adj`
    # carrying a node the native store lacks it returned False where nx returns
    # True -- a SILENT wrong boolean, with `get_edge_data` inheriting it through
    # its `self.has_edge(...)` delegation and answering None where nx answers {}.
    #
    # The `except KeyError` below already produces nx's answer for a genuinely
    # absent `u`, so the probe was never load-bearing, only wrong. This function
    # is an instance shadow installed ONLY on graphs carrying private storage, so
    # ordinary graphs never reach it and no perf claim is needed.
    try:
        # br-r37-c1-vbe1o: the RAW `_adj`, not the public `adj`. networkx reads
        # `self._adj[u]` here; now that the public accessor returns a read-only
        # view, going through it would hand back AtlasView rows where networkx
        # hands back plain dicts.
        neighbors = self._adj[u]
    except KeyError:
        return False
    return v in neighbors


def _assigned_private_has_edge_multi(self, u, v, key=None):
    owner = _shared_unsplit_owner(self)
    if owner is not None:
        raw = (
            _MULTIDIGRAPH_PRIVATE_AWARE_HAS_EDGE
            if owner.is_directed()
            else _MULTIGRAPH_PRIVATE_AWARE_HAS_EDGE
        )
        return raw(owner, u, v, key)
    _HASH_PROBE.get(u)
    _HASH_PROBE.get(v)
    if key is not None:
        _HASH_PROBE.get(key)
    # br-r37-c1-vbe1o: same authority fix as the simple variant above.
    try:
        # br-r37-c1-vbe1o: the RAW `_adj`, not the public `adj`. networkx reads
        # `self._adj[u]` here; now that the public accessor returns a read-only
        # view, going through it would hand back AtlasView rows where networkx
        # hands back plain dicts.
        neighbors = self._adj[u]
    except KeyError:
        return False
    if v not in neighbors:
        return False
    if key is not None:
        return key in neighbors[v]
    return True


def _assigned_private_get_edge_data_simple(self, u, v, default=None):
    owner = _shared_unsplit_owner(self)
    if owner is not None:
        raw = (
            _DIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA
            if owner.is_directed()
            else _GRAPH_PRIVATE_AWARE_GET_EDGE_DATA
        )
        return raw(owner, u, v, default)
    _HASH_PROBE.get(u)
    _HASH_PROBE.get(v)
    if not self.has_edge(u, v):
        return default
    # br-r37-c1-vbe1o: raw `_adj` -- networkx returns the live attr dict here,
    # and the public view would wrap it in an AtlasView.
    return self._adj[u][v]


def _assigned_private_get_edge_data_multi(
    self, u, v, key=None, default=None
):
    owner = _shared_unsplit_owner(self)
    if owner is not None:
        raw = (
            _MULTIDIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA
            if owner.is_directed()
            else _MULTIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA
        )
        return raw(owner, u, v, key, default)
    _HASH_PROBE.get(u)
    _HASH_PROBE.get(v)
    if key is not None:
        _HASH_PROBE.get(key)
    storage = self.__dict__
    if _PRIVATE_ADJ_OVERRIDE not in storage and _PRIVATE_SUCC_OVERRIDE not in storage:
        # Assigning only _node (or _pred) leaves _adj native. Its writable
        # facade wraps keydicts, but get_edge_data must return the raw dict.
        target = storage.get(_SHARED_STORAGE_SOURCE, self)
        raw = (
            _MULTIDIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA
            if target.is_directed()
            else _MULTIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA
        )
        return raw(target, u, v, key, default)
    if not self.has_edge(u, v, key):
        return default
    # br-r37-c1-vbe1o: raw `_adj`, as networkx does.
    edge_data = self._adj[u][v]
    if key is not None:
        return edge_data[key]
    return edge_data


def _assigned_private_digraph_successors(self, n):
    _HASH_PROBE.get(n)
    try:
        return iter(self._succ[n])
    except KeyError as exc:
        raise NetworkXError(f"The node {n} is not in the digraph.") from exc


def _assigned_private_graph_neighbors(self, n):
    _HASH_PROBE.get(n)
    try:
        return iter(self._adj[n])
    except KeyError as exc:
        raise NetworkXError(f"The node {n} is not in the graph.") from exc


def _assigned_private_digraph_predecessors(self, n):
    _HASH_PROBE.get(n)
    try:
        return iter(self._pred[n])
    except KeyError as exc:
        raise NetworkXError(f"The node {n} is not in the digraph.") from exc


# br-r37-c1-8itxk: (class, method-name) -> is the class's binding one of
# the raw PyO3 methods we are allowed to shadow. Keyed on the CLASS, so a
# subclass gets its own answer; populated on first use of each pair.
_SHADOWABLE_RAW_METHOD_CACHE: dict = {}


_CLASS_SHADOWS_NOTHING_CACHE = {}


def _class_shadows_nothing(owner_type):
    """True when neither a reader nor a writer can be shadowed on this class.

    The widest installation plan includes every candidate in narrower states.
    Sharing that plan avoids a second, incomplete eligibility list: overriding
    all read methods does not make inherited native mutation methods safe for
    assigned storage. Reverse views still have an empty plan because their
    classes override readers and mutation methods alike.
    """
    known = _CLASS_SHADOWS_NOTHING_CACHE.get(owner_type)
    if known is None:
        known = not _shadow_plan(owner_type, True, True)
        _CLASS_SHADOWS_NOTHING_CACHE[owner_type] = known
    return known


_SHADOW_PLAN_CACHE = {}


def _shadow_plan(owner_type, node_override, any_override):
    """The (name, fallback, raw_methods) triples this CLASS can actually shadow.

    br-r37-c1-shplan: everything decided here is a property of the class and the
    two override booleans, none of which can change under a live instance, so it
    is computed once and reused. The MRO walk that decides class eligibility is
    still the same one, still memoised per (class, name) in
    `_SHADOWABLE_RAW_METHOD_CACHE`; this just stops re-asking for candidates
    that were never eligible.
    """
    key = (owner_type, node_override, any_override)
    plan = _SHADOW_PLAN_CACHE.get(key)
    if plan is not None:
        return plan

    multi = issubclass(owner_type, (MultiGraph, MultiDiGraph))
    directed = issubclass(owner_type, (DiGraph, MultiDiGraph))
    candidates = []
    if node_override:
        candidates.append(("has_node", _assigned_private_has_node, _RAW_HAS_NODE_METHODS))
        candidates.append(
            ("number_of_nodes", _assigned_private_number_of_nodes, _RAW_NUMBER_OF_NODES_METHODS)
        )
        candidates.append(
            ("order", _assigned_private_number_of_nodes, _RAW_NUMBER_OF_NODES_METHODS)
        )
    if any_override:
        candidates.append((
            "has_edge",
            _assigned_private_has_edge_multi if multi else _assigned_private_has_edge_simple,
            _RAW_HAS_EDGE_METHODS,
        ))
        # br-r37-c1-wv3cu: the WRITE side. networkx mutates the assigned mapping
        # in place, so a graph carrying one needs add_node routed there as well
        # as to the native store.
        candidates.append(("add_node", _assigned_private_add_node, _RAW_ADD_NODE_METHODS))
        candidates.append(
            ("add_nodes_from", _assigned_private_add_nodes_from, _RAW_ADD_NODES_FROM_METHODS)
        )
        candidates.append(("remove_node", _assigned_private_remove_node, _RAW_REMOVE_NODE_METHODS))
        candidates.append(("remove_edge", _assigned_private_remove_edge, _RAW_REMOVE_EDGE_METHODS))
        candidates.append(
            ("remove_edges_from", _assigned_private_remove_edges_from, _RAW_REMOVE_EDGES_FROM_METHODS)
        )
        candidates.append(("clear", _assigned_private_clear, _RAW_CLEAR_METHODS))
        candidates.append(("clear_edges", _assigned_private_clear_edges, _RAW_CLEAR_EDGES_METHODS))
        candidates.append(
            ("add_edges_from", _assigned_private_add_edges_from, _RAW_ADD_EDGES_FROM_METHODS)
        )
        candidates.append((
            "add_weighted_edges_from",
            _assigned_private_add_weighted_edges_from,
            _RAW_ADD_WEIGHTED_METHODS,
        ))
        candidates.append((
            "add_edge",
            _assigned_private_add_edge_multi if multi else _assigned_private_add_edge_simple,
            _RAW_ADD_EDGE_METHODS,
        ))
        candidates.append((
            "get_edge_data",
            _assigned_private_get_edge_data_multi if multi else _assigned_private_get_edge_data_simple,
            _RAW_GET_EDGE_DATA_METHODS,
        ))
        if directed:
            candidates.append((
                "neighbors", _assigned_private_digraph_successors, _RAW_DIGRAPH_NEIGHBOR_METHODS
            ))
            candidates.append((
                "successors", _assigned_private_digraph_successors, _RAW_DIGRAPH_NEIGHBOR_METHODS
            ))
            candidates.append((
                "predecessors", _assigned_private_digraph_predecessors, _RAW_DIRECTED_PREDECESSOR_METHODS
            ))
        elif multi:
            candidates.append((
                "neighbors", _assigned_private_graph_neighbors, _RAW_MULTIGRAPH_NEIGHBOR_METHODS
            ))

    eligible = []
    for name, fallback, raw_methods in candidates:
        cache_key = (owner_type, name)
        ok = _SHADOWABLE_RAW_METHOD_CACHE.get(cache_key)
        if ok is None:
            class_method = next(
                (
                    base.__dict__[name]
                    for base in owner_type.__mro__
                    if name in base.__dict__
                ),
                None,
            )
            ok = any(class_method is raw_method for raw_method in raw_methods)
            _SHADOWABLE_RAW_METHOD_CACHE[cache_key] = ok
        if ok:
            eligible.append((name, fallback, raw_methods))

    plan = tuple(eligible)
    _SHADOW_PLAN_CACHE[key] = plan
    return plan


def _install_private_method_shadows(self, storage):
    """Restore mapping-aware dispatch only on instances that need it.

    br-r37-c1-qmi5w: ordinary graphs install the raw PyO3 ``has_node`` and
    ``number_of_nodes`` descriptors on their classes, avoiding a Python frame
    on every primitive call. NetworkX utilities can replace ``G._node`` with a
    Python mapping, though, so that setter shadows the raw descriptors on that
    one instance with the old mapping-aware behavior.

    br-r37-c1-6q4wl extends the same mechanism to ``has_edge``. Any assigned
    NetworkX private store makes edge membership mapping-backed, while ordinary
    graphs call the raw descriptor whose Rust body now owns the hash contract.

    br-r37-c1-57ba1 extends it to ``get_edge_data`` under the identical private
    storage predicate; raw methods own endpoint/key hashing and ordinary
    attribute-dict materialization.

    br-r37-c1-heyxu extends it to the directed ``neighbors`` / ``successors``
    descriptors. Their raw methods return live dict-key iterators; assigned
    NetworkX stores keep the corresponding mapping-backed iterator only on that
    instance.

    Private multigraph neighbor and directed predecessor iterators likewise
    retain the assigned dict itself, rather than an iterator over a copied row.

    Do not replace a user-supplied instance method or a subclass override. The
    tracked bound-method identities also let deepcopy/pickle distinguish these
    internal shadows from genuine public instance attributes.
    """
    owner_type = type(self)
    # br-r37-c1-vaayu: nothing on this class is shadowable, so the whole body
    # below is a no-op. Matches the `else` branch at the end exactly.
    if _class_shadows_nothing(owner_type):
        storage.pop(_PRIVATE_NODE_METHOD_SHADOWS, None)
        storage.pop(_PRIVATE_SHADOW_STATE, None)
        return

    previous = storage.get(_PRIVATE_NODE_METHOD_SHADOWS) or {}

    # br-r37-c1-shwst: which shadows this instance needs is decided ENTIRELY by
    # the two booleans below plus the class, and the class cannot change under a
    # live instance. A filtered view assigns THREE private overrides at
    # construction and every assignment re-ran this whole body, re-binding and
    # re-storing an identical set of methods.
    #
    # The guard is deliberately NOT "previous is non-empty". It compares the
    # recorded state, because a later assignment CAN legitimately widen the set -
    # adding a node override after an adj override moves (False, True) to
    # (True, True) and genuinely needs has_node/number_of_nodes/order installed.
    # Skipping on non-emptiness alone would silently drop those.
    node_override = _PRIVATE_NODE_OVERRIDE in storage or _SHARED_STORAGE_SOURCE in storage
    any_override = node_override or (
        _PRIVATE_ADJ_OVERRIDE in storage
        or _PRIVATE_SUCC_OVERRIDE in storage
        or _PRIVATE_PRED_OVERRIDE in storage
    )
    state = (node_override, any_override)
    if previous and storage.get(_PRIVATE_SHADOW_STATE) == state:
        # Only skip while every shadow we installed is still OURS. A caller that
        # replaced one with its own method must fall through, because the
        # per-name rule below is for exactly that case and it is not ours to
        # guess.
        for shadow_name, shadow_bound in previous.items():
            if storage.get(shadow_name) is not shadow_bound:
                break
        else:
            return

    installed = {}
    # br-r37-c1-shplan: the CLASS-eligible subset is computed once per
    # (class, state) instead of re-testing every candidate on every
    # construction. It used to call an `install` closure for all THIRTEEN
    # candidate names on a fresh instance; measured on a filtered view, exactly
    # ONE of them (`get_edge_data`) is class-eligible on Graph, DiGraph,
    # MultiGraph and MultiDiGraph alike, so twelve calls per view built a cache
    # key, missed nothing, and returned. That was 2.245us of a 15.812us
    # `G.subgraph(64)` - 14.2% of the whole construction - and a fresh view can
    # never hit the state guard above, because `previous` starts empty.
    #
    # Only the CLASS half of the decision is planned. The per-INSTANCE rule -
    # never replace a method the caller supplied, tracked through `previous` -
    # still runs for each planned name, unchanged.
    for name, fallback, raw_methods in _shadow_plan(owner_type, node_override, any_override):
        current = storage.get(name, _PRIVATE_MISSING)
        if current is not _PRIVATE_MISSING and current is not previous.get(name):
            continue
        bound = fallback.__get__(self, owner_type)
        storage[name] = bound
        installed[name] = bound

    if installed:
        storage[_PRIVATE_NODE_METHOD_SHADOWS] = installed
        storage[_PRIVATE_SHADOW_STATE] = state
    else:
        storage.pop(_PRIVATE_NODE_METHOD_SHADOWS, None)
        storage.pop(_PRIVATE_SHADOW_STATE, None)


def _set_private_override(self, attr_name, value):
    # br-r37-c1-wbwkb: an override installed AFTER a plain accessor read must
    # re-dispatch to the assigned-view branch, so drop what the descriptor
    # memoised first (and only that).
    storage = vars(self)
    cached = storage.get(_DESCRIPTOR_CACHED_VIEWS)
    if cached:
        for name in cached:
            storage.pop(name, None)
        storage.pop(_DESCRIPTOR_CACHED_VIEWS, None)
    if attr_name == _PRIVATE_ADJ_OVERRIDE:
        _discard_public_views_for_private_adj_reset(self)
    # br-r37-c1-vaayu: the explicit registration that used to sit here was
    # redundant. Every class's __setattr__ wrapper ends in
    # `self._fnx_register_gc_dict(vars(self))` — verified on all four — and the
    # only names this helper is ever called with are the four
    # `_fnx_private_*_override` keys, none of which is in any class's
    # public-adjacency early-return set ({adj, succ, pred}), so the setattr
    # below ALWAYS reaches that registration with the same dict object.
    # `vars(self)` is identity-stable, so registering twice registered the same
    # dict twice. Cost was a getattr plus a PyO3 call on each of the three
    # override assignments a reverse view makes at construction.
    setattr(self, attr_name, value)
    if attr_name == _PRIVATE_NODE_OVERRIDE:
        mark_private_node_override = getattr(self, "_fnx_set_private_node_override", None)
        if mark_private_node_override is not None:
            mark_private_node_override()
    elif attr_name == _PRIVATE_ADJ_OVERRIDE:
        # br-r37-c1-ef8rt: `EdgeView.__getitem__` is a native slot, so the
        # adjacency override has to reach the Rust side the same way the node
        # override does. `_adj` can be assigned without `_node`, so the node
        # flag cannot stand in for it.
        mark_private_adj_override = getattr(self, "_fnx_set_private_adj_override", None)
        if mark_private_adj_override is not None:
            mark_private_adj_override()
    elif attr_name in (_PRIVATE_SUCC_OVERRIDE, _PRIVATE_PRED_OVERRIDE):
        # br-r37-c1-ppiei: same funnel, same reason, one level down. The
        # directed multigraph accessors are native slots, so an assigned
        # `_succ` or `_pred` has to reach the Rust side exactly as `_adj` does;
        # `_succ` can be assigned without `_adj`, so the adj flag cannot stand
        # in for it. Undirected classes never take this branch and the getattr
        # guard covers any class that does not define the marker.
        mark_private_dir_override = getattr(self, "_fnx_set_private_dir_override", None)
        if mark_private_dir_override is not None:
            mark_private_dir_override()
    # br-r37-c1-2r06n: drop cached degree views so they are rebuilt knowing this
    # graph now carries private storage. The views resolve that question ONCE, in
    # __init__, to keep it off the per-lookup path -- which is only sound if an
    # assignment cannot outlive the answer. It otherwise can: the view is cached
    # in this same instance dict and was measured being reused across the
    # assignment, still holding the native counter that cannot see the new store.
    _drop = vars(self)
    _drop.pop("_fnx_view_out_degree", None)
    _drop.pop("_fnx_view_in_degree", None)
    _drop.pop("_fnx_view_degree", None)
    # br-r37-c1-degprop / br-r37-c1-2nrff: drop assigned view caches on override reset.
    _drop.pop("_fnx_view_degree_assigned", None)
    _drop.pop("_fnx_view_nodes_assigned", None)
    _drop.pop("_fnx_view_edges_assigned", None)
    # br-r37-c1-2r06n: and the G[node] row cache, so a row cached BEFORE this
    # assignment cannot be served after it. The multigraph `__getitem__` paths
    # consult private storage only on a cache MISS, which is what keeps the warm
    # path free — that is sound only if the assignment forces a miss.
    _drop.pop("_fnx_getitem_atlas_cache", None)
    _install_private_method_shadows(self, storage)


def _discard_public_views_for_private_adj_reset(self):
    """Mirror networkx's public-cache reset when ``_adj`` is reassigned.

    A private adjacency assignment is a structural replacement in networkx, so
    its cache resetter discards user values under the affected public names as
    well as genuinely memoised views.  FNX previously discarded only names still
    recorded in ``_fnx_descriptor_cached_views``; assigning ``G.degree = value``
    intentionally removes that marker, making the value survive a later
    ``G._adj = mapping`` unlike networkx.

    ``nodes`` stays user-owned.  Directed graphs also reset the successor-side
    cached surface; ``pred`` and ``in_edges`` are deliberately untouched, which
    is the split the live networkx resetter exposes.
    """
    storage = vars(self)
    names = {"adj", "edges", "degree"}
    if isinstance(self, (DiGraph, MultiDiGraph)):
        names.update(("succ", "in_degree", "out_degree", "out_edges"))
    for name in names:
        storage.pop(name, None)
    cached = storage.get(_DESCRIPTOR_CACHED_VIEWS)
    if cached is not None:
        cached.difference_update(names)
        if not cached:
            storage.pop(_DESCRIPTOR_CACHED_VIEWS, None)


class _CachedViewDescriptor:
    """br-r37-c1-wbwkb / br-r37-c1-2nrff: nx's ``@cached_property`` mechanism
    for fnx's private-override-aware accessors.

    networkx installs ``nodes`` / ``edges`` / ``degree`` / ``adj`` / ``succ`` /
    ``pred`` / ``in_edges`` / ``out_edges`` / ``in_degree`` / ``out_degree`` as
    ``@cached_property`` — a NON-data descriptor — so after the first access the
    view lives in the instance ``__dict__`` and every later access is a C-level
    dict hit with no Python frame at all, for both ordinary and private-storage
    graphs. ``_set_private_override`` and ``_set_private_overrides`` drop all
    entries recorded in ``_DESCRIPTOR_CACHED_VIEWS`` whenever ``_node`` /
    ``_adj`` / ``_succ`` / ``_pred`` is assigned or reassigned, matching
    networkx's ``_CachedPropertyResetter*`` descriptors.
    """

    def __init__(self, build, name, assigned_key=None):
        self._build = build
        self._name = name
        self._assigned_key = assigned_key
        self.__doc__ = getattr(build, "__doc__", None)

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        view = self._build(obj)
        storage = vars(obj)
        register_gc_dict = getattr(obj, "_fnx_register_gc_dict", None)
        if register_gc_dict is not None:
            register_gc_dict(storage)
        storage[self._name] = view
        cached = storage.get(_DESCRIPTOR_CACHED_VIEWS)
        if cached is None:
            storage[_DESCRIPTOR_CACHED_VIEWS] = {self._name}
        else:
            cached.add(self._name)
        return view



def _set_private_overrides(self, pairs):
    """Install SEVERAL private overrides through the funnel in ONE pass.

    br-r37-c1-batchov: a directed filtered view assigns three of them at
    construction, and each assignment re-ran the whole funnel: the
    descriptor-memo drop, five cached-view pops, and the shadow installer. Only
    the `setattr` and the native marker are genuinely per-attribute; the rest
    answers the same question three times. Measured on
    `DiGraph.subgraph(64)`, the three `_set_private_override` calls were 7.6% of
    construction tottime and the three installer calls another 8%.

    The end state is identical, and that is checkable rather than hopeful: the
    second and third installer calls already returned immediately via the
    br-r37-c1-shwst state guard - same state, shadows still ours - so dropping
    them removes work that had no effect. The drop and the pops are idempotent,
    so doing them once before the writes leaves the same instance dict.

    Callers must build every value BEFORE calling, because nothing runs between
    the writes any more. That is why the filtered-view constructor now
    materialises its three adjacency views first; `_filtered_public_adjacency_view`
    only reads `is_multigraph()` and closes over `view`, so it never depended on
    a previous assignment.
    """
    storage = vars(self)
    cached = storage.get(_DESCRIPTOR_CACHED_VIEWS)
    if cached:
        for name in cached:
            storage.pop(name, None)
        storage.pop(_DESCRIPTOR_CACHED_VIEWS, None)
    if any(attr_name == _PRIVATE_ADJ_OVERRIDE for attr_name, _ in pairs):
        _discard_public_views_for_private_adj_reset(self)
    for attr_name, value in pairs:
        setattr(self, attr_name, value)
        # The marker is fired per attribute, exactly as the single-override
        # funnel does. Two directed overrides share one marker and it is NOT
        # deduplicated here: whether that native call is idempotent is not
        # something this change is entitled to assume.
        if attr_name == _PRIVATE_NODE_OVERRIDE:
            mark = getattr(self, "_fnx_set_private_node_override", None)
        elif attr_name == _PRIVATE_ADJ_OVERRIDE:
            mark = getattr(self, "_fnx_set_private_adj_override", None)
        elif attr_name in (_PRIVATE_SUCC_OVERRIDE, _PRIVATE_PRED_OVERRIDE):
            mark = getattr(self, "_fnx_set_private_dir_override", None)
        else:
            mark = None
        if mark is not None:
            mark()
    storage.pop("_fnx_view_out_degree", None)
    storage.pop("_fnx_view_in_degree", None)
    storage.pop("_fnx_view_degree", None)
    storage.pop("_fnx_view_degree_assigned", None)
    storage.pop("_fnx_view_nodes_assigned", None)
    storage.pop("_fnx_view_edges_assigned", None)
    storage.pop("_fnx_getitem_atlas_cache", None)
    _install_private_method_shadows(self, storage)


def _has_networkx_private_storage(self):
    # br-r37-c1-31tby: collapse 4 ``_private_override`` calls (each a function
    # call + its own ``vars(self).get()``) into ONE ``vars(self)`` snapshot + 4
    # short-circuiting ``in`` membership checks. ``key in vars(self)`` is exactly
    # equivalent to ``vars(self).get(key, MISSING) is not MISSING`` because an
    # override is never stored AS the private ``_PRIVATE_MISSING`` sentinel.
    # This accessor is hit on every neighbors()/adjacency() call of fnx aux
    # graphs (millions of times in all_node_cuts / connectivity / flow), where
    # it was ~64% of runtime; per-call cost drops ~2.6x (318ns -> 120ns).
    # br-r37-c1-bnv3h: `self.__dict__` instead of `vars(self)`. Identical
    # semantics — `vars(x)` returns `x.__dict__` — but an attribute load rather
    # than a builtin CALL. Measured on a realistically-used 2000-node DiGraph:
    # 109.6ns -> 91.9ns, stable across repeats.
    #
    # br-r37-c1-bnv3h: MOVING THIS PROBE INTO RUST WAS TRIED AND IS SLOWER.
    # The obvious next idea, once the probe is known to be load-bearing and
    # ~117ns of a 357-546ns subscript, is to fuse it into the native
    # `get_edge_data` so the hot path makes ONE PyO3 call instead of two. A
    # `_fnx_edge_data_or_private` doing exactly that was written and measured on
    # a realistically-used 2000-node DiGraph at 2000-character keys:
    #
    #     current subscript  G.edges[u, v]              357.0 ns
    #     this probe alone                              117.3 ns
    #     plain native get_edge_data                    130.1 ns
    #     FUSED native (probe + lookup, one call)       401.3 ns
    #
    # The fused call is slower than the two separate calls (247.4ns) and slower
    # than the whole subscript it was meant to speed up. Reading the instance
    # dict from PyO3 — `slf.getattr("__dict__")` plus a `borrow_mut` and a
    # re-dispatch — costs MORE than CPython's own `self.__dict__` load, which is
    # a single specialised opcode. Rust is not automatically cheaper than
    # CPython for a CPython data-structure access.
    #
    # An `if not storage: return False` short-circuit was tried here and
    # REJECTED as a measured regression: 97.7ns against 91.9ns without it. The
    # instance dict of a real graph is NOT empty — a graph that has touched
    # `.adj` or `.edges` carries 4-6 accessor-cache entries
    # (`_fnx_view_adj`, `_fnx_getitem_atlas_cache`, `adj`, `edges`, ...) — so
    # the branch never fires and only adds a test. It looks like a 2.16x win if
    # measured on a graph whose accessors were never touched, which is not a
    # graph any caller has.
    storage = self.__dict__
    return (
        _PRIVATE_NODE_OVERRIDE in storage
        or _PRIVATE_ADJ_OVERRIDE in storage
        or _PRIVATE_SUCC_OVERRIDE in storage
        or _PRIVATE_PRED_OVERRIDE in storage
        or _SHARED_STORAGE_SOURCE in storage
    )


def _raw_neighbors_dispatch(G):
    """Return the raw Rust neighbors binding for ``G`` if it's safe to
    bypass AdjacencyView wrappers, else ``None``.

    br-r37-c1-jy2ea: centralizes the wrapper-bypass safety check used
    by find_cliques (lgyq8), square_clustering (7t95c), dominating_set
    (02djy), common_neighbors / non_neighbors (qkq2h), volume (ay2no
    via degree). Returns one of:

      - ``_GRAPH_NEIGHBORS``  for a plain ``Graph`` with no nx-
        compatibility private storage
      - ``_DIGRAPH_NEIGHBORS`` for the directed equivalent
      - ``None`` if any safety guard fails — caller should use the
        slow AdjacencyView path

    br-r37-c1-ni9va: ``isinstance(G, Graph)`` and ``isinstance(G,
    DiGraph)`` already exclude ``MultiGraph`` and ``MultiDiGraph``
    (they have independent MROs, NOT subclasses of Graph/DiGraph),
    so we don't need a separate ``G.is_multigraph()`` guard. Saves
    ~400 ns per dispatch (G.is_multigraph() ≈ 521 ns vs isinstance
    ≈ 121 ns).

    Single source of truth for "is wrapper-bypass safe on this graph".
    A future regression that introduces a new private-storage flag
    only needs to update this helper, not every callsite.

    Every graph view carries a private override (a conversion view since
    br-r37-c1-fabqo), so none reaches the raw binding, which would read the
    view's EMPTY Rust storage.
    """
    if isinstance(G, DiGraph):
        if _has_networkx_private_storage(G):
            return None
        return _DIGRAPH_NEIGHBORS
    if isinstance(G, Graph):
        if _has_networkx_private_storage(G):
            return None
        return _GRAPH_NEIGHBORS
    # Multigraph / unknown subclass / etc.: fall through.
    return None


def _cached_native_node_key_set(G, native_keys):
    # br-r37-c1-n4j4k: built from a dict of the nodes in node order, as
    # networkx's set(G._adj.keys()) is - its table sized once for every node -
    # so a copy of it (a slot-for-slot copy of a set without dummies) is laid
    # out as networkx's and iterates in its order.
    state = G.nodes_seq
    cache = vars(G)
    if cache.get("_fnx_native_node_key_set_state") != state:
        cache["_fnx_native_node_key_set_state"] = state
        cache["_fnx_native_node_key_set"] = set(dict.fromkeys(native_keys()))
    return cache["_fnx_native_node_key_set"]


def _private_node_mapping(self):
    storage = self.__dict__
    override = storage.get(_PRIVATE_NODE_OVERRIDE, _PRIVATE_MISSING)
    if override is not _PRIVATE_MISSING:
        return override
    root = storage.get(_SHARED_STORAGE_SOURCE)
    if root is not None:
        return _private_node_mapping(root)
    facade = storage.get("_fnx_priv_node")
    if facade is None:
        facade = _PrivateNodeFacade(self)
        storage["_fnx_priv_node"] = facade
        register_gc_dict = getattr(self, "_fnx_register_gc_dict", None)
        if register_gc_dict is not None:
            register_gc_dict(storage)
    return facade


def _private_adj_mapping(self, fallback):
    storage = self.__dict__
    override = storage.get(_PRIVATE_ADJ_OVERRIDE, _PRIVATE_MISSING)
    if override is not _PRIVATE_MISSING:
        return override
    root = storage.get(_SHARED_STORAGE_SOURCE)
    if root is not None:
        return fallback(root)
    return fallback(self)


def _private_directed_adj_mapping(self, fallback):
    storage = self.__dict__
    override = storage.get(_PRIVATE_ADJ_OVERRIDE, _PRIVATE_MISSING)
    if override is not _PRIVATE_MISSING:
        return override
    succ_override = storage.get(_PRIVATE_SUCC_OVERRIDE, _PRIVATE_MISSING)
    if succ_override is not _PRIVATE_MISSING:
        return succ_override
    root = storage.get(_SHARED_STORAGE_SOURCE)
    if root is not None:
        return fallback(root)
    return fallback(self)


# br-r37-c1-rgmef: the writable private adjacency surface.
#
# tests/python/test_private_adj_read_path_stays_native.py is a spec on this bead
# and it DISQUALIFIES the obvious fix by measurement: a facade wrapping the view
# costs +149 ns on `_adj[u]` and +186 ns on `_adj[u][v]` (~1.55x) on a path that
# networkx's own algorithms walk directly. I built that facade first and the
# lock caught it. What follows is the design the lock prescribes -- a SUBCLASS,
# which inherits the identical read functions and adds `__setitem__` alongside.
#
# SCOPE: Graph and DiGraph.
#   Graph,   whose public rows are the native `_fnx.AtlasView` (a `subclass`
#   DiGraph  pyclass), get a writable subclass of that native type, so the
#            private row's read methods ARE the public row's.
#   Multi*   blocked in PYTHON. A twin can be built, but its READS diverge from
#            the public view's and the lock's
#            `test_private_adj_reads_agree_with_the_public_view` catches it, so
#            they stay on the read-only view rather than land half-working.
#
# WRITE CONTEXT IS CARRIED SEPARATELY, in `_fnx_write_*` attributes set AFTER
# construction rather than through the constructor, so every read argument stays
# byte-identical to the public view's.

_PRIVATE_WRITABLE_CLASSES = {}


def _private_writable_class(base):
    """A writable subclass of `base`, memoised. Overrides nothing that reads."""
    cls = _PRIVATE_WRITABLE_CLASSES.get(base)
    if cls is None:
        cls = type(
            "Private" + base.__name__,
            (base,),
            {
                "__setitem__": _private_view_setitem,
                "__delitem__": _private_view_delitem,
                # propagates one level down: a private view builds private rows.
                "_fnx_private_rows": True,
            },
        )
        _PRIVATE_WRITABLE_CLASSES[base] = cls
    return cls


def _private_mark_writable(view, owner, node, kind):
    view._fnx_write_owner = owner
    view._fnx_write_node = node
    view._fnx_write_kind = kind
    return view


def _private_write_target(view, other):
    """(owner, u, v) for writing `other` into `view`; u is None at the top level.

    `_pred[v][u] = cell` describes the edge u -> v, so a pred row swaps its
    endpoints. The row already knows its kind, so nothing new is threaded in.
    """
    owner = getattr(view, "_fnx_write_owner", None)
    if owner is None:
        raise TypeError(
            "fnx: this private view has no owning graph to write to "
            "(br-r37-c1-rgmef)"
        )
    node = getattr(view, "_fnx_write_node", None)
    if node is None:
        return owner, None, None
    kind = getattr(view, "_fnx_write_kind", "adj")
    if kind == "keydict":
        # `node` is the (u, v) pair; `other` is the edge key, handled by caller.
        return owner, node[0], node[1]
    if kind == "pred":
        return owner, other, node
    return owner, node, other


def _private_parent_kind(view):
    """The direction a child of `view` inherits.

    The WRITE kind wins over the read-side `_fnx_row_kind`, because
    `MultiAdjacencyView` does not carry the latter -- deriving it there defaulted
    every multigraph `_pred` row to "adj" and wrote its edges BACKWARDS.
    """
    return getattr(view, "_fnx_write_kind", None) or getattr(
        view, "_fnx_row_kind", "adj"
    )


def _private_mark_child(parent, child, owner, node):
    """Attach write context to a child view, one level down from `parent`.

    On a MULTIgraph the child of a ROW is a KEYDICT: `_adj[u][v]` addresses the
    edge (u, v), not a neighbour, so it carries the PAIR and a kind of its own.
    `_fnx_multi_edge_owner` is what identifies a multigraph row -- it is the
    argument such rows are built with and simple rows are not.
    """
    write_owner = getattr(parent, "_fnx_write_owner", None) or owner
    parent_node = getattr(parent, "_fnx_write_node", None)
    if parent.__dict__.get("_fnx_multi_edge_owner") is not None and parent_node is not None:
        if getattr(parent, "_fnx_write_kind", "adj") == "pred":
            pair = (node, parent_node)
        else:
            pair = (parent_node, node)
        return _private_mark_writable(child, write_owner, pair, "keydict")
    return _private_mark_writable(
        child, write_owner, node, getattr(parent, "_fnx_write_kind", None)
        or getattr(parent, "_fnx_row_kind", "adj")
    )


def _private_keydict_setitem(self, owner, u, v, key, value):
    """`_adj[u][v][key] = attrs` -- `key` is the EDGE key, not a neighbour."""
    if not isinstance(value, _Mapping):
        raise TypeError(
            "fnx: a multigraph keydict entry must be a mapping of edge "
            f"attributes; got {type(value).__name__}. networkx accepts any "
            "value because its keydict is a raw dict, but fnx stores edge "
            "attributes in a typed store with no representation for a "
            "non-mapping (br-r37-c1-rgmef)."
        )
    if owner.has_edge(u, v, key):
        existing = owner.adj[u][v][key]
        existing.clear()
        existing.update(value)
        return
    owner.add_edge(u, v, key, **dict(value))


def _private_view_setitem(self, key, value):
    """Item assignment into private storage, as networkx's raw dict allows."""
    owner, u, v = _private_write_target(self, key)
    if u is not None and getattr(self, "_fnx_write_kind", "adj") == "keydict":
        return _private_keydict_setitem(self, owner, u, v, key, value)
    if u is None:
        if not isinstance(value, _Mapping):
            raise TypeError(
                "fnx: an adjacency row must be a mapping; got "
                f"{type(value).__name__} (br-r37-c1-rgmef)."
            )
        owner.add_node(key)
        reverse = getattr(self, "_fnx_write_kind", "adj") == "pred"
        for other in list(self[key]):
            a, b = (other, key) if reverse else (key, other)
            if owner.has_edge(a, b):
                owner.remove_edge(a, b)
        row = self[key]
        for other, cell in value.items():
            row[other] = cell
        return

    if owner.is_multigraph():
        # `_adj[u][v] = {key: attrs}` replaces the whole parallel-edge set.
        if not isinstance(value, _Mapping):
            raise TypeError(
                "fnx: a multigraph adjacency row maps a neighbour to a keydict; "
                f"got {type(value).__name__} (br-r37-c1-rgmef)."
            )
        if owner.has_edge(u, v):
            for edge_key in list(owner.adj[u][v]):
                owner.remove_edge(u, v, edge_key)
        for edge_key, edge_attrs in value.items():
            if not isinstance(edge_attrs, _Mapping):
                raise TypeError(
                    "fnx: multigraph edge attributes must be a mapping; got "
                    f"{type(edge_attrs).__name__} (br-r37-c1-rgmef)."
                )
            owner.add_edge(u, v, edge_key, **dict(edge_attrs))
        return

    attrs = dict(value) if value else {}
    if owner.has_edge(u, v):
        # networkx REPLACES the cell, so the previous attributes go with it.
        existing = owner.adj[u][v]
        existing.clear()
        existing.update(attrs)
        return
    owner.add_edge(u, v, **attrs)


def _private_view_delitem(self, key):
    owner, u, v = _private_write_target(self, key)
    if u is None:
        owner.remove_node(key)
        return
    owner.remove_edge(u, v)


def _read_only_private_mapping(graph, mapping):
    """Wrap an ASSIGNED private mapping the way networkx's public accessor does.

    br-r37-c1-vbe1o: `G.adj` in networkx is a read-only view over `self._adj` --
    read-only at BOTH levels, with the inner row an AtlasView. fnx handed back
    the raw assigned dict, so `G.adj["QQ"] = {}` was ACCEPTED where networkx
    raises TypeError. The private `G._adj` is raw in networkx too, and is
    deliberately left alone: `G._adj is assigned` is True there and False for
    `G.adj`, which is the split this restores.

    The wrapper CLASS follows the graph: networkx uses MultiAdjacencyView for the
    multigraph classes and AdjacencyView for the simple ones. Using one for all
    would leave `type(G.adj)` wrong on half the classes -- caught before landing
    by comparing the type against live networkx per class.

    A plain dict is wrapped; anything already a view (the ordinary non-private
    path) is returned untouched, so this costs nothing when no storage is
    assigned.
    """
    if type(mapping) is dict:
        if graph.is_multigraph():
            return MultiAdjacencyView(lambda: mapping)
        return AdjacencyView(lambda: mapping)
    return mapping

def _private_succ_mapping(self, fallback):
    storage = self.__dict__
    override = storage.get(_PRIVATE_SUCC_OVERRIDE, _PRIVATE_MISSING)
    if override is not _PRIVATE_MISSING:
        return override
    # br-r37-c1-vbe1o: on a DIRECTED graph `_adj` and `_succ` are ONE mapping in
    # networkx — both names are bound to `_CachedPropertyResetterAdjAndSucc`,
    # whose `__set__` writes both — so `G._adj = {...}` assigns the successor
    # side. Verified directly: in nx `g._adj is g._succ` is True before any
    # assignment, and assigning either name makes the node visible through both.
    #
    # `_private_directed_adj_mapping` already reads the succ override, so the
    # `_succ`-then-read-`_adj` direction worked. This is the missing MIRROR, and
    # its absence was the whole `_adj`-on-directed group in the sweep: successors,
    # has_successor, out_degree, len(G.succ) and neighbors all read the native
    # succ view and reported a node the assigned `_adj` plainly carried.
    adj_override = storage.get(_PRIVATE_ADJ_OVERRIDE, _PRIVATE_MISSING)
    if adj_override is not _PRIVATE_MISSING:
        return adj_override
    root = storage.get(_SHARED_STORAGE_SOURCE)
    if root is not None:
        return fallback(root)
    return fallback(self)


def _private_pred_mapping(self, fallback):
    storage = self.__dict__
    override = storage.get(_PRIVATE_PRED_OVERRIDE, _PRIVATE_MISSING)
    if override is not _PRIVATE_MISSING:
        return override
    root = storage.get(_SHARED_STORAGE_SOURCE)
    if root is not None:
        return fallback(root)
    return fallback(self)


def _cached_adj_row_key_iter(owner, row_kind, row_node, row_getter):
    # Thin iter() wrapper over the cached keydict (None if uncacheable).
    keydict = _cached_adj_row_keydict(owner, row_kind, row_node, row_getter)
    return None if keydict is None else iter(keydict)


_INDUCED_NATIVE_KEEP_DIVISOR = 10


def _induced_keep_is_small(filter_nodes, parent):
    """True when an induced copy should be built in Python, not by the kernel.

    br-r37-c1-5cqc2. The native induced-subgraph kernel walks the whole parent,
    so it is the right tool only when the kept set is a large share of it. The
    divisor is the measured crossover rounded down; see the call site for the
    table. Returns False whenever the sizes cannot be established, so an unusual
    graph keeps the previous behaviour rather than silently changing route.
    """
    try:
        return _INDUCED_NATIVE_KEEP_DIVISOR * len(filter_nodes) < len(parent)
    except TypeError:
        return False


def _cached_adj_row_keydicts(owner, row_kind, nodes, row_getter_for):
    """Resolve SEVERAL rows with one preamble instead of one per node.

    br-r37-c1-8qxi9: ``_cached_adj_row_keydict`` re-does its whole warm-path
    preamble — ``vars()``, the two revision reads, the token tuple build and
    compare — on every call, and the nbunch edge views call it once per node
    twice per ``edges(nbunch)`` (once to build the lazy walk, once to
    materialise). Profiled at nbunch=8 that was 16 calls at ~1us each and the
    dominant cost of the whole operation.

    The preamble answers a question about the GRAPH, not about the row, so it is
    the same answer for every node in one call. Hoist it, then read the rows
    straight out of the cache dict. Any miss — cold cache, stale token, a graph
    with private storage — falls back to the per-node function, so the result is
    identical by construction and the cache still gets populated on the way.

    Returns a list of ``(node, row)`` in the order given, or None if any row is
    unavailable (the caller then takes its own fallback path).
    """
    try:
        owner_vars = vars(owner)
    except TypeError:
        return None
    cache = owner_vars.get("_fnx_adj_row_keydict_cache")
    if cache is not None:
        try:
            if owner_vars.get("_fnx_adj_row_keydict_cache_state") == (
                owner.nodes_seq,
                owner.edges_seq,
            ):
                warm = []
                for node in nodes:
                    row = cache.get((row_kind, node))
                    if row is None:
                        break
                    warm.append((node, row))
                else:
                    return warm
        except (AttributeError, TypeError):
            pass
    rows = []
    for node in nodes:
        row = _cached_adj_row_keydict(owner, row_kind, node, row_getter_for(node))
        if row is None:
            return None
        rows.append((node, row))
    return rows


def _cached_adj_row_keydict(owner, row_kind, row_node, row_getter):
    # br-r37-c1-spg9n: return the cached ``{nbr: <row value>}`` keydict for this
    # row (caller does iter()/len()/membership). Lean warm fast-path: a
    # token-valid cached keydict is returned with ONE vars() snapshot, skipping
    # the isinstance / _has_networkx_private_storage / native-name machinery
    # below. A POPULATED cache implies owner is a concrete graph with no private
    # storage. Serves AtlasView iteration/len/contains (list(G[n]), v in G[u])
    # plus neighbors/successors/predecessors. br-r37-c1-zrsuc extends the same
    # key-only cache to multigraph neighbor iterators: their old public path
    # rebuilt a native list and temporary dict on every call, despite the
    # existing nodes_seq/edges_seq invalidation token.
    try:
        owner_vars = vars(owner)
    except TypeError:
        return None
    cache = owner_vars.get("_fnx_adj_row_keydict_cache")
    if cache is not None:
        try:
            if owner_vars.get("_fnx_adj_row_keydict_cache_state") == (
                owner.nodes_seq,
                owner.edges_seq,
            ):
                keydict = cache.get((row_kind, row_node))
                if keydict is not None:
                    return keydict
        except (AttributeError, TypeError):
            pass
    if owner is None or row_node is None:
        return None
    if not isinstance(owner, (Graph, DiGraph, MultiGraph, MultiDiGraph)):
        return None
    if _has_networkx_private_storage(owner):
        return None
    try:
        _HASH_PROBE.get(row_node)
        token = (owner.nodes_seq, owner.edges_seq)
    except (AttributeError, TypeError):
        return None

    native_name = {
        "adj": "_native_adjacency_row_dict",
        "succ": "_native_successor_row_dict",
        "pred": "_native_predecessor_row_dict",
    }.get(row_kind)

    # br-r37-c1-spg9n: serve neighbors(n) / G.succ[n] / G.pred[n] key-iteration
    # from a per-row dict cached on the graph's __dict__, keyed on
    # (nodes_seq, edges_seq). The native row dict (``_native_adjacency_row_dict``
    # etc.) is a per-CALL PyO3 round-trip — calling it unconditionally (as the old
    # code did) made every neighbors() pay that boundary (~5x slower than nx's
    # ``iter(self._adj[n])``). Building each row's dict ONCE and re-iterating the
    # cached object makes repeats pure-Python (5x -> ~1.9x of nx, 2.6x self).
    # Token-keyed, so any structural change (add/remove node or edge bumps
    # nodes_seq/edges_seq) drops the whole cache. iter() over the cached dict's
    # keys is byte-identical to ``iter(native_row(n))`` (same keys, same order).
    state_name = "_fnx_adj_row_keydict_cache_state"
    cache_name = "_fnx_adj_row_keydict_cache"
    owner_vars = vars(owner)
    if owner_vars.get(state_name) != token:
        owner_vars[state_name] = token
        owner_vars[cache_name] = {}
    cache = owner_vars[cache_name]
    cache_key = (row_kind, row_node)
    keydict = cache.get(cache_key)
    if keydict is None:
        # br-r37-c1-v9auw: the simple Graph and DiGraph native row accessors
        # return persistent PyDict mirrors in canonical adjacency order. Every
        # structural mutator maintains those mirrors in place, so use the live
        # row itself. The previous DiGraph branch rebuilt a second Python dict
        # from a whole-graph adjacency snapshot solely to recover key order;
        # the per-row accessor has carried identical order since
        # br-r37-c1-gchm1/cc-succrowoV.
        # Simple graphs already maintain persistent live row dicts. Multigraph
        # row-dict accessors materialise nested edge-key/attribute mappings, but
        # this cache needs keys only; build those once from the existing
        # neighbors iterator instead of making hidden edge data escape.
        if native_name is not None and isinstance(owner, (Graph, DiGraph)):
            native_row = getattr(owner, native_name, None)
            if native_row is not None:
                try:
                    keydict = native_row(row_node)
                except KeyError:
                    return None
        if keydict is None:
            keydict = dict.fromkeys(row_getter())
        cache[cache_key] = keydict
    return keydict


class _AssignedPrivateNodeView(_Mapping):
    def __init__(self, graph):
        self._graph = graph

    @property
    def _mapping(self):
        return _private_node_mapping(self._graph)

    def __iter__(self):
        return iter(self._mapping)

    def __len__(self):
        return len(self._mapping)

    def __contains__(self, node):
        return node in self._mapping

    def __getitem__(self, node):
        return self._mapping[node]

    def __call__(self, data=False, default=None):
        if data is False:
            return list(self)
        if data is True:
            return [(node, self[node]) for node in self]
        return [(node, self[node].get(data, default)) for node in self]

    def data(self, data=True, default=None):
        return self(data=data, default=default)

    def __and__(self, other):
        return set(self) & set(other)

    def __rand__(self, other):
        return set(other) & set(self)

    def __or__(self, other):
        return set(self) | set(other)

    def __ror__(self, other):
        return set(other) | set(self)

    def __sub__(self, other):
        return set(self) - set(other)

    def __rsub__(self, other):
        return set(other) - set(self)

    def __xor__(self, other):
        return set(self) ^ set(other)

    def __rxor__(self, other):
        return set(other) ^ set(self)


def _assigned_raw_adj(graph):
    """The RAW assigned adjacency mapping, or `graph.adj` if none is present.

    br-r37-c1-ktsxn: every reader in `_AssignedPrivateEdgeView` used to go
    through `graph.adj`, which hands back an `AdjacencyView` that wraps a fresh
    row object on every subscript. Iterating it cost 315.7us for 400 rows
    against ~20us for the underlying dict -- the wrapping, not the walk, was the
    row. `_private_override` is the reader the rest of the assigned-storage
    machinery already uses; a directed graph keeps its successors under the succ
    key. The `graph.adj` fallback keeps every caller correct if neither override
    is present, which is what makes this safe to use on the raising paths: a
    plain-dict subscript raises the same `KeyError(node)` the view does.
    """
    adj = _private_override(
        graph,
        _PRIVATE_SUCC_OVERRIDE if graph.is_directed() else _PRIVATE_ADJ_OVERRIDE,
    )
    if adj is _PRIVATE_MISSING:
        adj = _private_override(graph, _PRIVATE_ADJ_OVERRIDE)
    if adj is _PRIVATE_MISSING:
        return graph.adj
    return adj
