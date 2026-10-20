

def _add_edges_from_materialized(raw, raw_add_edge):
    def add_edges_from(self, ebunch_to_add, **attr):
        # br-r37-c1-832s6: for a (u, v) pair networkx's add_edges_from does
        # exactly add_edge(u, v, **attr) - the same None and hash checks, in the
        # same order - so a bunch of a few plain pairs goes straight to the
        # native add_edge. The batch probes, the validation pass and the raw
        # call below cost ~2.5 us a call where networkx's whole add_edges_from
        # costs ~1 us, and graphs grown a few edges per call paid it on every
        # step. The class's own add_edge, not self.add_edge: networkx's
        # add_edges_from never calls an add_edge a subclass overrides.
        if type(ebunch_to_add) in (list, tuple) and len(ebunch_to_add) < _TINY_EDGE_BUNCH:
            for _e in ebunch_to_add:
                if type(_e) is not tuple or len(_e) != 2:
                    break
            else:
                _add_plain_pairs(self, raw_add_edge, ebunch_to_add, attr)
                return None
        # br-r37-c1-ey5n2: no pass over the pairs for ones already in the graph.
        # Without attrs, re-adding an edge is networkx's no-op (its row keeps
        # the key and the dict), and the native batches skip an existing pair;
        # the pass was the guard from when a native re-add reset the edge's
        # attributes, and it cost a Python walk of every pair against a
        # snapshot of every edge - most of an append onto a non-empty graph.
        if not attr and isinstance(ebunch_to_add, (list, tuple)):
            native_batch = getattr(self, "_try_add_edges_from_batch", None)
            if native_batch is not None and native_batch(ebunch_to_add):
                return None
        # br-r37-c1-aefitexc (cycle 216): nx's add_edges_from iterates
        # the ebunch and adds each edge inline.  When the input is a
        # generator (or any iterator) that raises mid-stream, edges
        # yielded BEFORE the exception are persisted on the graph.
        # fnx previously ran ``list(ebunch_to_add)`` atomically, so
        # any exception during iteration discarded all previously
        # yielded edges.  Drop-in code using
        # ``try: g.add_edges_from(gen()) except: ...`` (a common
        # pattern) saw the graph in a different state on fnx vs nx.
        # Preserve partial progress by iterating manually for
        # non-list/tuple inputs and capturing the iteration exception
        # to re-raise after the (possibly partial) edges are added.
        if isinstance(ebunch_to_add, (list, tuple)):
            materialized = list(ebunch_to_add)
            iteration_exc = None
        elif _ebunch_reads_graph(ebunch_to_add, self):
            # The ebunch reads this graph: insert as it yields, as networkx
            # does, so it sees every edge added before it (br-r37-c1-imddi).
            # A (u, v) pair is networkx's add_edge(u, v, **attr); any other
            # shape goes through this function as a one-edge list for its
            # validation and errors.
            for _e in ebunch_to_add:
                if type(_e) is tuple and len(_e) == 2:
                    _add_plain_pairs(self, raw_add_edge, (_e,), attr)
                else:
                    add_edges_from(self, [_e], **attr)
            return None
        else:
            materialized = []
            iteration_exc = None
            try:
                for _e in ebunch_to_add:
                    materialized.append(_e)
            except BaseException as _exc:
                iteration_exc = _exc
            # br-aefgenbatch: a generator/iterator input never reached the
            # native plain-edge batch fast path at the top of this function
            # (that gate only fires for list/tuple inputs). Once the iterator
            # is fully materialized — with no mid-stream iteration error and
            # no broadcast **attr — retry the same fast path on the
            # materialized list so generator-fed builders
            # (from_dict_of_lists, complete_bipartite_graph, the grid /
            # circulant generators, and nx-internal ``add_edges_from(gen)``
            # calls) get the bulk insert instead of the per-edge validation
            # loop + per-edge Rust add_edge. _try_add_edges_from_batch is
            # atomic (no mutation when it returns False), so any
            # non-plain-2-tuple bunch falls through to the exact per-edge
            # parity path below — byte-identical to passing the same list
            # directly (the list gate above already trusts it).
            if iteration_exc is None and not attr:
                native_batch = getattr(self, "_try_add_edges_from_batch", None)
                if native_batch is not None and native_batch(materialized):
                    return None
        # br-r37-c1-aeflist: nx.Graph.add_edges_from accepts each edge
        # as ANY 2- or 3-element iterable (tuple OR list), via the
        # bare ``u, v = e[:2]`` unpack inside the loop.  The Rust raw
        # path only accepts tuples and raises
        # ``TypeError('each edge must be a tuple (u, v) or
        # (u, v, attr_dict)')`` on lists.  Convert non-tuple sized
        # iterables to tuples before delegating — preserves the
        # canonical nx idiom ``G.add_edges_from([[u, v], ...])``.
        #
        # br-r37-c1-aefnone: nx's reference implementation gates each
        # edge with ``ne = len(e)`` and raises NetworkXError(f"Edge
        # tuple {e} must be a 2-tuple or 3-tuple.") on bad arity, or
        # propagates the canonical TypeError("object of type X has no
        # len()") for ``len()``-less inputs (None, int, ...). The
        # Rust raw path instead emitted a generic
        # ``TypeError("each edge must be a tuple (u, v) or (u, v,
        # attr_dict)")`` for both shapes — diverging on exception
        # CLASS for the list-arity case (NetworkXError vs TypeError),
        # which broke drop-in callers using ``except
        # nx.NetworkXError`` to detect malformed edge inputs.
        # Replicate the len-based gate here so both error contracts
        # match nx exactly before delegating.
        # br-r37-c1-77ux3: nx.add_edges_from processes edges INLINE — each
        # edge is validated and added one at a time (see nx.Graph.add_edges_from:
        # ``for e in ebunch_to_add: ne = len(e); ...``).  So when a malformed
        # edge raises mid-batch, every VALID edge before it persists on the
        # graph, AND the failing edge's partial node state persists too: nx
        # creates node ``u`` *before* it examines ``v``, so an edge like
        # ``(1, None)`` leaves node 1 in the graph before the ``v is None``
        # ValueError fires.  fnx historically validated the whole batch up front
        # (three pre-passes below) and added NOTHING on any error, leaving the
        # graph empty where nx keeps the good prefix.  Replicate nx's inline
        # semantics: find the first offending edge, add the valid prefix via the
        # fast bulk Rust path, reproduce the failing edge's partial node, then
        # raise the same nx-shaped error.  The error contracts are unchanged:
        #   * NetworkXError("Edge tuple {e} must be a 2-tuple or 3-tuple.") on
        #     bad arity for tuples/lists/strings (br-r37-c1-icuqb / aef-tupshape)
        #   * the canonical ``TypeError`` from ``len(e)`` for len()-less items
        #     (None, int, ...) (br-r37-c1-aefnone)
        #   * ValueError("None cannot be a node") for a None endpoint
        #     (br-r37-c1-83r45)
        #   * TypeError('unhashable type: ...') for an unhashable endpoint
        #     (br-r37-c1-m0io3)
        # and lists are still normalised to tuples for the Rust path
        # (br-r37-c1-aeflist).
        _unset = _ADD_EDGES_UNSET
        first_error = None
        partial_node = _unset
        valid_count = len(materialized)
        for i, edge in enumerate(materialized):
            if isinstance(edge, tuple):
                normalized = edge
            else:
                # strings/bytes/lists are sized iterables nx gates with len(e);
                # a len()-less item raises the canonical TypeError, which nx
                # propagates only AFTER the valid prefix has been added.
                try:
                    len(edge)
                except TypeError as exc:
                    first_error = exc
                    valid_count = i
                    break
                normalized = tuple(edge)
            if len(normalized) not in (2, 3):
                first_error = NetworkXError(
                    f"Edge tuple {edge} must be a 2-tuple or 3-tuple.",
                )
                valid_count = i
                break
            u = normalized[0]
            v = normalized[1]
            # nx validates+creates u before it looks at v.
            if u is None:
                first_error = ValueError("None cannot be a node")
                valid_count = i
                break
            try:
                _HASH_PROBE.get(u)
            except TypeError as exc:
                first_error = exc
                valid_count = i
                break
            if v is None:
                first_error = ValueError("None cannot be a node")
                valid_count = i
                partial_node = u  # nx has already created node u
                break
            try:
                _HASH_PROBE.get(v)
            except TypeError as exc:
                first_error = exc
                valid_count = i
                partial_node = u
                break
            materialized[i] = normalized
        if first_error is None:
            if _simple_add_edges_from_touches_existing_plain_edge(self, materialized):
                _add_plain_pairs(self, raw_add_edge, materialized, attr)
                if iteration_exc is not None:
                    raise iteration_exc
                return None
            result = raw(self, materialized, **attr)
            if iteration_exc is not None:
                raise iteration_exc
            return result
        # nx-inline parity: persist the valid prefix and the failing edge's
        # partial node, then raise the same error nx would have raised at that
        # edge (which also pre-empts any later generator iteration_exc, exactly
        # as nx stops pulling the ebunch the moment an edge raises).
        if valid_count:
            raw(self, materialized[:valid_count], **attr)
        if partial_node is not _unset:
            self.add_node(partial_node)
        raise first_error

    return add_edges_from


def _remove_edges_from_materialized(raw):
    """br-rmvbunch: nx internals call
    ``g.remove_edges_from(nx.selfloop_edges(g))``. The generator reads
    self._adj while the remove_edges_from call holds a mutable borrow
    — Rust raises 'Already mutably borrowed'. Materialize the iterable
    before the Rust call.

    Parameter name matches nx (br-r37-c1-wcdm3): ``ebunch``.

    br-r37-c1-reflist: nx.Graph.remove_edges_from accepts each edge
    as ANY 2- or 3-element iterable (tuple OR list); the Rust raw
    path raises ``TypeError("each element must be a (u, v) tuple")``
    on lists.  Convert non-tuple sized iterables to tuples before
    the raw call — preserves the canonical nx idiom
    ``G.remove_edges_from([[u, v], ...])``.
    """
    def remove_edges_from(self, ebunch):
        # br-r37-c1-refitexc (cycle 217): nx's remove_edges_from
        # iterates and removes each edge inline.  When the input is
        # a generator that raises mid-stream, edges yielded BEFORE
        # the exception are removed.  fnx previously called
        # ``list(ebunch)`` atomically, so any iteration exception
        # discarded all yielded removals.  Sister of cycle 216
        # (br-r37-c1-aefitexc) for ``add_edges_from``.
        if isinstance(ebunch, (list, tuple)):
            materialized = list(ebunch)
            iteration_exc = None
        elif _ebunch_reads_graph(ebunch, self):
            # The ebunch reads this graph: remove as it yields, as networkx
            # does, so it sees every edge removed before it (br-r37-c1-apelp).
            # Each one-edge list keeps this function's validation and errors.
            for _e in ebunch:
                remove_edges_from(self, [_e])
            return None
        else:
            materialized = []
            iteration_exc = None
            try:
                for _e in ebunch:
                    materialized.append(_e)
            except BaseException as _exc:
                iteration_exc = _exc
        # br-r37-c1 mutation-state batch 2: nx removes INLINE — a
        # malformed element mid-bunch raises nx's exact error AFTER the
        # valid prefix has been removed. Simple graphs do ``u, v = e[:2]``
        # (None -> 'not subscriptable' TypeError, short tuple -> unpack
        # ValueError, unhashable -> TypeError from the adjacency probe);
        # multigraphs do ``self.remove_edge(*e[:3])`` (short tuple ->
        # the remove_edge missing-argument TypeError). fnx previously
        # screened/normalized the whole bunch and silently DROPPED
        # malformed elements while removing everything else.
        is_multi = self.is_multigraph()
        first_error = None
        valid_count = len(materialized)
        for i, edge in enumerate(materialized):
            try:
                sliced = edge[:3] if is_multi else edge[:2]
            except TypeError as exc:
                first_error = exc
                valid_count = i
                break
            if len(sliced) < 2:
                if is_multi:
                    first_error = TypeError(
                        f"{type(self).__name__}.remove_edge() missing 1 "
                        "required positional argument: 'v'"
                    )
                else:
                    first_error = ValueError(
                        f"not enough values to unpack (expected 2, got {len(sliced)})"
                    )
                valid_count = i
                break
            try:
                _HASH_PROBE.get(sliced[0])
                _HASH_PROBE.get(sliced[1])
                if is_multi and len(sliced) > 2:
                    _HASH_PROBE.get(sliced[2])
            except TypeError as exc:
                first_error = exc
                valid_count = i
                break
            if (
                not isinstance(edge, tuple)
                and not isinstance(edge, (str, bytes))
                and hasattr(edge, "__len__")
                and 2 <= len(edge) <= 3
            ):
                materialized[i] = tuple(edge)
        if first_error is None:
            result = raw(self, materialized)
            _invalidate_adjacency_row_caches(self)
            if iteration_exc is not None:
                raise iteration_exc
            return result
        if valid_count:
            raw(self, materialized[:valid_count])
            _invalidate_adjacency_row_caches(self)
        raise first_error

    return remove_edges_from


def _remove_nodes_from_materialized(raw):
    """Same materialisation guard as remove_edges_from, parameter name
    aligned to nx's ``nodes`` (br-r37-c1-wcdm3).

    br-r37-c1-i9whv: nx raises TypeError on unhashable items (its
    ``del self._node[n]`` raises before the missing-node KeyError).
    fnx silently iterated past unhashable nodes. Hash-check up
    front so unhashable inputs raise TypeError matching nx.
    """
    def remove_nodes_from(self, nodes):
        # br-r37-c1-rnfitexc (cycle 217): generator-partial-progress
        # parity with nx (sister of cycle 216 br-r37-c1-aefitexc and
        # cycle 217 br-r37-c1-refitexc).  ``list(nodes)`` atomically
        # discarded yielded removals on iteration exception; nx
        # iterates and removes inline.
        if isinstance(nodes, (list, tuple)):
            materialized = list(nodes)
            iteration_exc = None
        elif _ebunch_reads_graph(nodes, self):
            # The iterable reads this graph: remove as it yields, as networkx
            # does, so it sees every node removed before it (br-r37-c1-apelp).
            for _n in nodes:
                remove_nodes_from(self, [_n])
            return None
        else:
            materialized = []
            iteration_exc = None
            try:
                for _n in nodes:
                    materialized.append(_n)
            except BaseException as _exc:
                iteration_exc = _exc
        # br-r37-c1 mutation-state batch 2: nx removes INLINE — the
        # unhashable TypeError (from ``del self._node[n]``) fires AFTER
        # the valid prefix has been removed. The old whole-bunch hash
        # gate (br-r37-c1-i9whv) raised before removing anything,
        # leaving nx-divergent state.
        first_error = None
        valid_count = len(materialized)
        for i, n in enumerate(materialized):
            try:
                _HASH_PROBE.get(n)
            except TypeError as exc:
                first_error = exc
                valid_count = i
                break
        if first_error is None:
            removed_before = set()
            for n in materialized:
                if n not in removed_before and n in self:
                    _detach_rows_before_node_removal(self, n, removed_before=removed_before)
                    removed_before.add(n)
            result = raw(self, materialized)
            _invalidate_adjacency_row_caches(self)
            if iteration_exc is not None:
                raise iteration_exc
            return result
        if valid_count:
            removed_before = set()
            for n in materialized[:valid_count]:
                if n not in removed_before and n in self:
                    _detach_rows_before_node_removal(self, n, removed_before=removed_before)
                    removed_before.add(n)
            raw(self, materialized[:valid_count])
            _invalidate_adjacency_row_caches(self)
        raise first_error

    return remove_nodes_from


Graph.add_edges_from = _add_edges_from_materialized(
    _GRAPH_RAW_ADD_EDGES_FROM, _GRAPH_ADD_EDGE_RAW
)
DiGraph.add_edges_from = _add_edges_from_materialized(
    _DIGRAPH_RAW_ADD_EDGES_FROM, _DIGRAPH_ADD_EDGE_RAW
)
Graph.remove_edges_from = _remove_edges_from_materialized(_GRAPH_RAW_REMOVE_EDGES_FROM)
DiGraph.remove_edges_from = _remove_edges_from_materialized(_DIGRAPH_RAW_REMOVE_EDGES_FROM)
MultiGraph.remove_edges_from = _remove_edges_from_materialized(_MULTIGRAPH_RAW_REMOVE_EDGES_FROM)
MultiDiGraph.remove_edges_from = _remove_edges_from_materialized(_MULTIDIGRAPH_RAW_REMOVE_EDGES_FROM)
Graph.remove_nodes_from = _remove_nodes_from_materialized(_GRAPH_RAW_REMOVE_NODES_FROM)
DiGraph.remove_nodes_from = _remove_nodes_from_materialized(_DIGRAPH_RAW_REMOVE_NODES_FROM)
MultiGraph.remove_nodes_from = _remove_nodes_from_materialized(_MULTIGRAPH_RAW_REMOVE_NODES_FROM)
MultiDiGraph.remove_nodes_from = _remove_nodes_from_materialized(_MULTIDIGRAPH_RAW_REMOVE_NODES_FROM)


# ---------------------------------------------------------------------------
# Constructor: absorb dict-of-dicts input (franken_networkx-lc3em).
#
# The Rust ``__init__`` accepts iterables of 2- or 3-tuples as edge lists,
# but silently drops edges when the caller passes a nx-style dict-of-dicts
# (e.g. ``{u: {v: attrs_dict}}``). Upstream nx's ``to_networkx_graph``
# converter decodes that shape. Mirror it at the Python layer so the four
# graph classes accept every input format the nx constructor does.
# ---------------------------------------------------------------------------

_GRAPH_INIT = Graph.__init__
_DIGRAPH_INIT = DiGraph.__init__
_MULTIGRAPH_INIT = MultiGraph.__init__
_MULTIDIGRAPH_INIT = MultiDiGraph.__init__


def _multigraph_input_is_4level(data):
    """Detect whether a dict-of-dicts payload is the 4-level multigraph
    shape ``{u: {v: {key: attrs_dict, ...}, ...}, ...}`` versus the
    3-level simple shape ``{u: {v: attrs_dict, ...}, ...}``.

    nx's ``MultiGraph.__init__`` resolves this ambiguity by trying the
    4-level interpretation first and falling back to 3-level on any
    failure (see ``networkx/classes/multigraph.py``). We mirror that
    preference structurally: any innermost non-dict value forces the
    3-level interpretation; otherwise default to 4-level (which
    handles empty-inner ``{u: {v: {}}}`` cases the same way nx does —
    a no-op, no edge added).

    br-r37-c1-14pu1: previously every multigraph dict-of-dicts payload
    was treated as 4-level, so ``MultiGraph({1:{2:{'w':1}}})`` produced
    edge ``(1,2,'w')`` (key='w', no attrs) instead of ``(1,2,0,{'w':1})``.
    """
    for nbrs in data.values():
        if not isinstance(nbrs, dict):
            # Mixed dict-of-list / dict-of-dict input — 4-level not
            # applicable to non-dict entries; the decoder handles
            # those branches separately.
            continue
        for inner in nbrs.values():
            if not isinstance(inner, dict):
                # 3-level edge attrs sit here; would not parse as
                # {key: attrs}.
                return False
            for innermost in inner.values():
                if not isinstance(innermost, dict):
                    return False
    return True


def _decode_dict_of_dicts_into(self, data, is_multigraph, multigraph_input=None):
    """Populate ``self`` from an nx-style dict-of-dicts (or dict-of-list)
    payload.

    Shapes accepted (matching nx's ``to_networkx_graph``):
    - simple graph:
        - ``{u: {v: attrs_dict, ...}, ...}``       (dict-of-dict)
        - ``{u: [v1, v2, ...], ...}``              (dict-of-list)
    - multigraph:
        - ``{u: {v: {key: attrs_dict, ...}, ...}, ...}``  (dict-of-dict-of-dict)
        - ``{u: {v: attrs_dict, ...}, ...}``              (dict-of-dict, 3-level)
        - ``{u: [v1, v2, ...], ...}``                     (dict-of-list)

    Mirrors ``nx.convert.from_dict_of_dicts`` semantics. For multigraph
    inputs the 4-level (``multigraph_input=True``) vs 3-level
    (``multigraph_input=False``) interpretation is selected by the
    explicit caller-provided ``multigraph_input`` flag, or auto-detected
    structurally when ``multigraph_input is None``.

    br-r37-c1-9m2vs: dict-of-list input was previously skipped via
    ``if not isinstance(nbrs, dict): continue``, silently dropping
    every edge.

    br-r37-c1-14pu1: (a) auto-detect 3-level vs 4-level multigraph
    dict-of-dicts and accept the explicit ``multigraph_input`` flag;
    (b) for dict-of-list input into an undirected MultiGraph, dedupe
    the symmetric adjacency representation by tracking already-
    processed source nodes (matching ``nx.from_dict_of_lists``).
    Otherwise ``MultiGraph({1:[2,3], 2:[1,3], 3:[1,2]})`` produced 6
    edges instead of nx's 3.
    """
    if is_multigraph and multigraph_input is None:
        multigraph_input = _multigraph_input_is_4level(data)

    # Pre-compute whether to dedupe dict-of-list input. nx's
    # from_dict_of_lists only dedupes for undirected MultiGraph.
    dedupe_dict_of_list = is_multigraph and not self.is_directed()
    seen_sources = set() if dedupe_dict_of_list else None

    # br-r37-c1-13tp1: nx.from_dict_of_dicts dedupes the symmetric
    # adjacency of an UNDIRECTED MultiGraph 3-level dict-of-dicts input
    # (non-multigraph_input). It tracks already-seen (u, v) pairs and adds
    # each edge exactly once under key=0:
    #     seen = set()
    #     for u, nbrs in d.items():
    #         for v, data in nbrs.items():
    #             if (u, v) not in seen:
    #                 G.add_edge(u, v, key=0); G[u][v][0].update(data)
    #             seen.add((v, u))
    # Without this, MultiGraph({u: {v: a}, v: {u: a}}) produced two edges
    # (auto keys 0 and 1) instead of nx's single (u, v, 0).
    dedupe_pairs = is_multigraph and not multigraph_input and not self.is_directed()
    seen_pairs = set() if dedupe_pairs else None

    # br-r37-c1-decodedir (cc): pure non-multigraph dict-of-dicts -> ONE
    # add_edges_from. The per-edge ``self.add_edge(u,v); self[u][v].update(...)``
    # loop below is O(N^2) for a DiGraph (per-edge directed adjacency-view
    # __getitem__: 911ms @ n=800 = 0.003x vs nx) and ~6x slow even undirected
    # (0.17x). Emitting (u, v, attrs) triples is byte-identical to the loop:
    # add_edges_from sets/updates the edge data dict (last-writer-wins on the
    # symmetric undirected reverse, exactly like the loop), same node + edge
    # order. Gated to ALL-dict values (dict-of-list / non-dict shapes keep the
    # general loop below). add_nodes_from(data) preserves isolated sources.
    if not is_multigraph and data and all(
        isinstance(_nbrs, dict) for _nbrs in data.values()
    ):
        self.add_nodes_from(data)
        self.add_edges_from(
            (u, v, dict(inner) if isinstance(inner, dict) else {})
            for u, nbrs in data.items()
            for v, inner in nbrs.items()
        )
        return

    # cc-dolctor: simple-graph dict-of-LIST fast path. The general per-node loop
    # below commits each edge with a per-edge ``self.add_edge(u, v)`` (O(E) PyO3),
    # so ``Graph({u: [v, ...]})`` ran ~0.36x nx even though the standalone
    # ``from_dict_of_lists`` — identical result — is >1x. Mirror it exactly: build
    # ONE deduped batch (an undirected dict-of-list lists every edge twice; drop
    # the symmetric reverse so the whole set commits through the bulk
    # ``add_edges_from`` instead of bailing to the per-edge path) and add it in a
    # single call. ``add_nodes_from(data)`` adds the source nodes in dict order
    # (isolated sources preserved) exactly as ``from_dict_of_lists`` does, so node
    # AND edge order stay byte-identical to nx. Gated to a CLEAN dict-of-list
    # (every value a non-dict, non-str/bytes iterable) so mixed / dict-of-dict /
    # string-valued / non-iterable shapes keep the general loop's exact semantics.
    if not is_multigraph and data and all(
        not isinstance(_nbrs, (dict, str, bytes)) and hasattr(_nbrs, "__iter__")
        for _nbrs in data.values()
    ):
        self.add_nodes_from(data)
        if self.is_directed():
            batch = [(u, v) for u, nbrs in data.items() for v in nbrs]
        else:
            seen = set()
            batch = []
            for u, nbrs in data.items():
                for v in nbrs:
                    if u != v and (v, u) in seen:
                        continue
                    batch.append((u, v))
                    seen.add((u, v))
        self.add_edges_from(batch)
        return

    # cc-mgdodctor: 4-level multigraph dict-of-dicts fast path (the
    # ``to_dict_of_dicts`` roundtrip). The general per-edge loop below does
    # ``add_edge(u,v,key=key)`` + ``self[u][v][key].update(...)`` per edge — an
    # O(E) PyO3 adjacency-view chain that ran MultiGraph(dod) at ~0.24x nx. Build
    # ONE keyed ``(u, v, key, attrs)`` batch and commit via ``add_edges_from``.
    # Undirected input lists every edge twice (``dod[u][v][k]`` and
    # ``dod[v][u][k]``); dedupe the symmetric ``(v,u,key)`` reverse exactly as
    # ``nx.convert.from_dict_of_dicts`` does so each edge commits once and the
    # whole set uses the bulk keyed batch (the reverse duplicates otherwise bail
    # it to the per-edge path). Gated to a clean dict-of-dicts value shape so
    # 3-level / dict-of-list / mixed inputs keep the general loop's exact
    # semantics. ``add_nodes_from(data)`` preserves isolated sources.
    if is_multigraph and multigraph_input and data and all(
        isinstance(_nbrs, dict) for _nbrs in data.values()
    ):
        self.add_nodes_from(data)
        batch = []
        if self.is_directed():
            for u, nbrs in data.items():
                for v, inner in nbrs.items():
                    if isinstance(inner, dict):
                        for key, attrs in inner.items():
                            batch.append(
                                (u, v, key, dict(attrs) if isinstance(attrs, dict) else {})
                            )
        else:
            seen = set()
            for u, nbrs in data.items():
                for v, inner in nbrs.items():
                    if isinstance(inner, dict):
                        for key, attrs in inner.items():
                            if (u, v, key) not in seen:
                                batch.append(
                                    (u, v, key, dict(attrs) if isinstance(attrs, dict) else {})
                                )
                            seen.add((v, u, key))
        self.add_edges_from(batch)
        return

    # cc-mgdolctor: multigraph dict-of-LIST fast path. Mirrors
    # ``nx.convert.from_dict_of_lists`` for multigraphs: undirected dedupes the
    # symmetric representation by already-processed SOURCE node (each edge added
    # once when its earlier-listed endpoint is the source), directed keeps every
    # ``(u, v)`` — both committed through the bulk auto-key ``add_edges_from``
    # instead of the general loop's per-edge ``add_edge``. Gated to a clean
    # dict-of-list value shape so other shapes keep the general loop.
    if is_multigraph and data and all(
        not isinstance(_nbrs, (dict, str, bytes)) and hasattr(_nbrs, "__iter__")
        for _nbrs in data.values()
    ):
        self.add_nodes_from(data)
        batch = []
        if self.is_directed():
            for u, nbrs in data.items():
                for v in nbrs:
                    batch.append((u, v))
        else:
            seen = set()
            for u, nbrs in data.items():
                for v in nbrs:
                    if v not in seen:
                        batch.append((u, v))
                seen.add(u)
        self.add_edges_from(batch)
        return

    # br-r37-c1-fo8zw: seed ALL source nodes in dict-key order first, exactly
    # like nx.convert.from_dict_of_dicts / from_dict_of_lists
    # (``G.add_nodes_from(d)`` before any edge). The general per-source loop
    # below adds target nodes as edges are discovered, so without this the node
    # order interleaves source/target discovery instead of "all keys, then
    # edge-order targets". Previously the Rust ``__new__`` pre-absorbed the dict
    # keys as nodes, masking this; the fo8zw ctor guards stop absorbing dict
    # inputs, so the canonical order must be established here.
    self.add_nodes_from(data)
    for u, nbrs in data.items():
        self.add_node(u)
        if isinstance(nbrs, dict):
            for v, inner in nbrs.items():
                if is_multigraph:
                    if multigraph_input:
                        # 4-level: inner is {key: attrs_dict}; only add
                        # v (and the edge) when at least one key is
                        # present.
                        if isinstance(inner, dict) and inner:
                            for key, attrs in inner.items():
                                self.add_edge(u, v, key=key)
                                self[u][v][key].update(
                                    dict(attrs) if isinstance(attrs, dict) else {}
                                )
                        # else: empty inner — do NOT add v (matches nx)
                    else:
                        # 3-level: inner IS the edge-attr dict.
                        if dedupe_pairs:
                            # Undirected MultiGraph: add each symmetric
                            # pair once under key=0 (nx parity).
                            if (u, v) not in seen_pairs:
                                self.add_edge(u, v, key=0)
                                if isinstance(inner, dict):
                                    self[u][v][0].update(dict(inner))
                            seen_pairs.add((v, u))
                        else:
                            # Directed MultiGraph: auto key, no dedup
                            # (matches nx add_edges_from of (u, v, data)).
                            self.add_edge(u, v)
                            if isinstance(inner, dict):
                                # Apply to the most recently added key
                                # (auto-incremented). MultiGraph stores edge
                                # data under the auto key; use the same key
                                # the add_edge call returned.
                                keys = list(self[u][v].keys())
                                if keys:
                                    self[u][v][keys[-1]].update(dict(inner))
                else:
                    # Simple graph: inner is the edge-attr dict.
                    self.add_edge(u, v)
                    if isinstance(inner, dict):
                        self[u][v].update(dict(inner))
            if dedupe_dict_of_list:
                seen_sources.add(u)
            continue
        # Non-dict value: treat as iterable of neighbour nodes
        # (nx.from_dict_of_lists semantic). Strings/bytes are valid
        # nodes themselves, so we don't iterate them character-by-
        # character.
        if isinstance(nbrs, (str, bytes)):
            if dedupe_dict_of_list:
                seen_sources.add(u)
            continue
        try:
            iterable = iter(nbrs)
        except TypeError:
            if dedupe_dict_of_list:
                seen_sources.add(u)
            continue
        for v in iterable:
            if dedupe_dict_of_list and v in seen_sources:
                # Edge (u,v) already added when v was the source.
                continue
            self.add_edge(u, v)
        if dedupe_dict_of_list:
            seen_sources.add(u)


def _copy_constructor_graph_source(self, source, *, is_multigraph, attr):
    """Populate constructor target from another graph in public edge order.

    br-graphtodigraph: when target is directed and source is undirected,
    nx expands each undirected edge into both directions (matching
    ``source.to_directed()`` semantics). Previously we iterated
    ``source.edges(data=True)`` which yields each undirected edge once,
    so DiGraph(Graph) silently dropped half the directed edges —
    number_of_edges() was N/2 of what nx returned, breaking
    second_order_centrality and any other algorithm that depends on
    the bidirected view.
    """
    # br-r37-c1-dgctor: DiGraph(Graph) fast path — native bidirected
    # shallow copy in one pass (adjacency-row edge order, matching nx's
    # from_dict_of_dicts walk; the Python expand loop below emits
    # u->v,v->u adjacent which DIVERGES from nx succ/pred row order, and
    # paid per-edge DiGraph.add_edges_from ~9.4x nx). The kernel replaces
    # ALL of self's state wholesale, which is exactly the clear()+rebuild
    # this function otherwise performs — including discarding whatever the
    # Rust __new__ already absorbed from `source` (the old path paid that
    # absorb AND a full clear() AND the Python rebuild). Exact types only;
    # the kernel returns False (fall through) on anything else.
    if (
        type(self) is DiGraph
        and type(source) is Graph
        and _fnx.digraph_absorb_graph_bidirected(self, source)
    ):
        if attr:
            self.graph.update(attr)
        return

    # br-r37-c1-gelud: Graph(DiGraph) native absorb - networkx's
    # from_dict_of_dicts(D.adj) walk, a reciprocal pair merging into one edge
    # whose dict the second direction updates. The Python rebuild below paid
    # add_nodes_from + add_edges_from over the source's views (0.43x). The
    # kernel reads the native store, so an assigned private store keeps the
    # rebuild.
    if (
        type(self) is Graph
        and type(source) is DiGraph
        and not _has_networkx_private_storage(source)
        and _fnx.graph_absorb_digraph(self, source)
    ):
        if attr:
            self.graph.update(attr)
        return

    # br-r37-c1-1o74q: MultiGraph(Graph) native absorb fast path — the per-edge
    # Python rebuild was ~2.1-2.6x slower than nx. Build the MultiGraph inner
    # directly from the simple source (node-major canonical edge order, key 0),
    # matching nx byte-for-byte. Kernel returns False (fall through) on mixed-
    # display rows or non-round-tripping attrs.
    if (
        type(self) is MultiGraph
        and type(source) is Graph
        and _fnx.multigraph_absorb_graph(self, source)
    ):
        if attr:
            self.graph.update(attr)
        return

    # br-r37-c1-k1k74: MultiDiGraph(Graph) native absorb — exact fnx simple
    # graph source, bidirected key-0 target, no Python edge-list replay.
    if (
        type(self) is MultiDiGraph
        and type(source) is Graph
        and self._fnx_absorb_graph_bidirected(source)
    ):
        if attr:
            self.graph.update(attr)
        return

    # br-r37-c1-mdgdig (cc): MultiDiGraph(DiGraph) native absorb — directional
    # analog of the Graph-source path above. The general Python replay below
    # paid MultiDiGraph.add_edges_from per edge (~28ms / 8000 edges → MDG(DiG)
    # was ~0.41x nx); even attr-free 2-tuples hit that substrate. Build the
    # MDG inner directly from the simple DiGraph source (node-major successor
    # order, key 0, shallow-copied attrs). Kernel returns False (fall through)
    # on mixed-display rows or non-round-tripping attrs.
    if (
        type(self) is MultiDiGraph
        and type(source) is DiGraph
        and self._fnx_absorb_digraph_keyed(source)
    ):
        if attr:
            self.graph.update(attr)
        return

    # br-r37-c1-s0d4x: same-exact-type ctor — nx's cls(G) structure is
    # identical to G.copy() (probed all four classes: nodes, edges+data,
    # adjacency/pred rows, graph attrs, shallow attr-dict copying).
    # Wholesale-absorb the native copy instead of the Python re-add walk
    # (DiGraph(DiGraph) was 4.4-5.0x slower than nx).
    if type(self) is type(source) and type(self) in (
        Graph,
        DiGraph,
        MultiGraph,
        MultiDiGraph,
    ):
        absorb = getattr(self, "_fnx_absorb_copy", None)
        if absorb is not None:
            absorb(source)
            if attr:
                self.graph.update(attr)
            return

    self.clear()
    self.graph.update(dict(getattr(source, "graph", {})))
    if attr:
        self.graph.update(attr)
    self.add_nodes_from((node, dict(attrs)) for node, attrs in source.nodes(data=True))
    target_is_directed = self.is_directed()
    source_is_directed = source.is_directed()
    expand_undirected_to_directed = target_is_directed and not source_is_directed

    if source.is_multigraph():
        if is_multigraph:
            if expand_undirected_to_directed:
                edges = []
                for u, v, key, attrs in source.edges(keys=True, data=True):
                    edges.append((u, v, key, dict(attrs)))
                    if u != v:
                        edges.append((v, u, key, dict(attrs)))
                self.add_edges_from(edges)
            elif source_is_directed and not target_is_directed:
                # br-r37-c1-bt8m4: collapsing directed -> undirected, nx's
                # from_dict_of_dicts walks adjacency CELLS with a `seen`
                # reverse-pair skip: the FIRST direction encountered keeps
                # ALL its parallel keys; the reverse direction is skipped
                # ENTIRELY (attrs never merge across directions). The old
                # flat add_edges_from let the reverse direction's attrs
                # overwrite (last-wins) — MultiGraph(MultiDiGraph) diverged.
                groups = {}
                for u, v, key, attrs in source.edges(keys=True, data=True):
                    groups.setdefault((u, v), []).append((key, dict(attrs)))
                seen = set()
                edges = []
                for (u, v), items in groups.items():
                    if (u, v) in seen:
                        continue
                    seen.add((v, u))
                    for key, attrs in items:
                        edges.append((u, v, key, attrs))
                self.add_edges_from(edges)
            else:
                self.add_edges_from(
                    (u, v, key, dict(attrs))
                    for u, v, key, attrs in source.edges(keys=True, data=True)
                )
        else:
            if expand_undirected_to_directed:
                edges = []
                for u, v, _key, attrs in source.edges(keys=True, data=True):
                    edges.append((u, v, dict(attrs)))
                    if u != v:
                        edges.append((v, u, dict(attrs)))
                self.add_edges_from(edges)
            elif source_is_directed and not target_is_directed:
                # br-r37-c1-bt8m4: Graph(MultiDiGraph) — same reverse-pair
                # skip; parallel keys within the kept direction merge in key
                # order (nx's per-key G[u][v].update inside the cell visit).
                groups = {}
                for u, v, _key, attrs in source.edges(keys=True, data=True):
                    groups.setdefault((u, v), []).append(dict(attrs))
                seen = set()
                edges = []
                for (u, v), datas in groups.items():
                    if (u, v) in seen:
                        continue
                    seen.add((v, u))
                    for d in datas:
                        edges.append((u, v, d))
                self.add_edges_from(edges)
            else:
                self.add_edges_from(
                    (u, v, dict(attrs))
                    for u, v, _key, attrs in source.edges(keys=True, data=True)
                )
    elif is_multigraph:
        if expand_undirected_to_directed:
            # br-r37-c1-1o74q: MultiDiGraph(Graph) — the source is simple, so
            # each directed endpoint pair appears at most ONCE. Emitting 3-tuples
            # ``(u, v, attrs)`` lets the directed-multigraph ``add_edges_from``
            # auto-assign key 0 (lowest unused == 0 on a fresh graph) — byte-
            # identical to the explicit ``(u, v, 0, attrs)`` 4-tuple but routed
            # through the native attributed-batch fast-path instead of the
            # per-edge add_edge loop (~2.46x faster; was ~3.3x slower than nx).
            # NB: this win is directed-only — for the undirected MultiGraph
            # targets below, the symmetric auto-key lookup makes 3-tuples SLOWER,
            # so those keep the explicit-key 4-tuple form.
            edges = []
            for u, v, attrs in source.edges(data=True):
                edges.append((u, v, dict(attrs)))
                if u != v:
                    edges.append((v, u, dict(attrs)))
            self.add_edges_from(edges)
        elif source_is_directed and not target_is_directed:
            # br-r37-c1-bt8m4: MultiGraph(DiGraph) — reverse-pair skip,
            # first direction wins (nx keeps ONE key-0 edge, not two
            # parallels and not last-wins attrs).
            seen = set()
            edges = []
            for u, v, attrs in source.edges(data=True):
                if (u, v) in seen:
                    continue
                seen.add((v, u))
                edges.append((u, v, 0, dict(attrs)))
            self.add_edges_from(edges)
        else:
            # MultiGraph(Graph) / MultiDiGraph(DiGraph): the explicit-key 4-tuple
            # is at-or-faster than auto-key here (the 3-tuple win is specific to
            # the undirected-source -> directed-multi expansion above).
            self.add_edges_from(
                (u, v, 0, dict(attrs)) for u, v, attrs in source.edges(data=True)
            )
    else:
        if expand_undirected_to_directed:
            edges = []
            for u, v, attrs in source.edges(data=True):
                edges.append((u, v, dict(attrs)))
                if u != v:
                    edges.append((v, u, dict(attrs)))
            self.add_edges_from(edges)
        else:
            self.add_edges_from(
                (u, v, dict(attrs)) for u, v, attrs in source.edges(data=True)
            )


def _validate_graph_constructor_backend(graph, backend):
    """networkx's dispatchable ``Graph.__new__`` rejects a backend name that is
    not installed with ``ImportError``; ``"networkx"`` and this library's own
    name build the graph here."""
    if backend in ("networkx", "franken_networkx"):
        return
    from networkx.utils.backends import backends as _installed_backends

    if backend not in _installed_backends:
        graph.clear()
        raise ImportError(f"{backend!r} backend is not installed")


def _init_absorbing_dict_of_dicts(raw_init, is_multigraph):
    """Factory: wrap ``__init__`` so dict-of-dicts / dict-of-dict-of-dicts
    payloads are decoded — the Rust ``__new__`` already handles
    edge-list iterables and Graph instances, but silently drops dict
    inputs other than as a node-only iteration.
    """

    def __init__(self, *args, backend=None, **kwargs):
        # br-r37-c1-rc0923-epic-honest-measurement-vbneu.1: this IS networkx's
        # constructor call shape (``Graph.__new__`` is a dispatchable with
        # ``(*args, backend=None, **kwargs)``), parsed the way networkx parses
        # it — no ``__signature__`` override. ``Graph``/``DiGraph`` take one
        # positional (``incoming_graph_data``); the multigraph classes also take
        # ``multigraph_input``; everything else is a graph attribute.
        self._fnx_register_gc_dict(vars(self))
        max_positional = 2 if is_multigraph else 1
        if len(args) > max_positional:
            self.clear()
            raise TypeError(
                f"{type(self).__name__}.__init__() takes from 1 to "
                f"{max_positional + 1} positional arguments but "
                f"{len(args) + 1} were given"
            )
        for position, param in enumerate(
            ("incoming_graph_data", "multigraph_input")[:max_positional]
        ):
            if position < len(args) and param in kwargs:
                self.clear()
                raise TypeError(
                    f"{type(self).__name__}.__init__() got multiple values for "
                    f"argument '{param}'"
                )
        incoming_graph_data = args[0] if args else kwargs.pop("incoming_graph_data", None)
        if is_multigraph:
            multigraph_input = (
                args[1] if len(args) > 1 else kwargs.pop("multigraph_input", None)
            )
        else:
            multigraph_input = None
        attr = kwargs
        if backend is not None:
            _validate_graph_constructor_backend(self, backend)
        self.graph.pop("backend", None)
        # ``raw_init(self, incoming_graph_data)`` is a no-op on pyo3
        # classes where ``__new__`` consumed the data; call it with
        # no extra args just to exercise any future init logic.
        # br-r37-c1-14pu1: accept ``multigraph_input`` explicitly so it
        # reaches the dict decoder instead of being treated as a graph
        # attribute. Non-multigraph classes also accept it for nx
        # signature parity but ignore the value.
        # br-r37-c1-ctorscalar: reject scalar non-data inputs the way
        # nx.convert.to_networkx_graph does.  ``Graph(5)``,
        # ``Graph(1.5)``, ``Graph(True)``, ``Graph(complex(1, 2))``
        # all hit nx's terminal ``raise NetworkXError("Input is not a
        # known data type for conversion.")``.  fnx's Rust __new__
        # silently absorbed them as no-edge inputs, returning an
        # empty graph.  ``bool`` is captured by ``int`` (subclass).
        # str / bytes are iterable so they take a different code path
        # in nx itself; leave those for the existing edge-list
        # validation to surface ``"Input is not a valid edge list"``.
        if isinstance(incoming_graph_data, (int, float, complex)):
            self.clear()
            raise NetworkXError(
                "Input is not a known data type for conversion."
            )
        # br-r37-c1-ctoredgelist: nx.from_edgelist iterates the input
        # and unpacks each item as a 2- or 3-element edge spec; if any
        # item isn't sized-2-or-3, nx surfaces ``NetworkXError("Input
        # is not a valid edge list")`` from ``to_networkx_graph``'s
        # final _Collection branch.  fnx's Rust __new__ silently
        # absorbed lists/tuples/sets/ranges/strs/bytes of non-edge
        # items as node iterables (one node per element), producing
        # ``Graph(nodes=N, edges=0)`` instead of the expected error.
        # Pre-validate by spot-checking the items.  Skip dict /
        # Graph-instance / numpy / pandas / generator / iterator
        # (those have their own decoders); only walk concrete
        # sized containers where we can iterate non-destructively.
        if (
            incoming_graph_data is not None
            and not isinstance(incoming_graph_data, dict)
            and not (
                type(incoming_graph_data).__module__.startswith("numpy")
                and hasattr(incoming_graph_data, "shape")
            )
            and not (
                type(incoming_graph_data).__module__.startswith("pandas")
                and hasattr(incoming_graph_data, "iloc")
            )
            and not (
                hasattr(incoming_graph_data, "nodes")
                and hasattr(incoming_graph_data, "edges")
                and callable(getattr(incoming_graph_data, "is_multigraph", None))
            )
            and isinstance(
                incoming_graph_data,
                (list, tuple, set, frozenset, range, str, bytes),
            )
        ):
            # br-r37-c1-ctorlistedges: nx.from_edgelist accepts each
            # edge as ANY 2- or 3-element iterable (tuple OR list);
            # the Rust __new__ accepts only tuples and stores list
            # items as unhashable nodes-by-id.  Pre-walk the items,
            # validate they're sized-2-or-3, and remember whether
            # any list-typed elements need conversion to tuples.
            # br-r37-c1-wpt9x: MultiGraph/MultiDiGraph also accept
            # ``(u, v, key, data_dict)`` 4-tuples; the 4th element
            # must be a dict per nx's ``add_edges_from`` contract.
            is_multi = self.is_multigraph()
            # br-r37-c1-d58s8 ctor lever: the per-item Python walk
            # (isinstance/hasattr/len per edge) was 46% of
            # Graph(edges) — replaced by ONE native pass with
            # identical semantics (str/bytes invalid, no-len invalid,
            # bad lengths invalid, multi 4-tuple needs dict, non-tuple
            # flags conversion).
            from franken_networkx._fnx import (
                validate_ctor_edge_list as _validate_ctor_edge_list,
            )

            valid, needs_tuple_conversion, _endpoints_hashable = (
                _validate_ctor_edge_list(incoming_graph_data, is_multi)
            )
            if not valid:
                self.clear()
                raise NetworkXError("Input is not a valid edge list")
            if not _endpoints_hashable:
                # br-r37-c1-g438p semantics, native: unhashable
                # endpoints are not a valid edge list.
                self.clear()
                raise NetworkXError("Input is not a valid edge list")
            _skip_hash_walk = True
            if needs_tuple_conversion:
                # Rust __new__ already absorbed list items as
                # unhashable nodes-by-id.  Reset and rebuild from a
                # tuple-converted edge list — preserves nx's
                # ``Graph([[0, 1], [1, 2]])`` contract.
                raw_init(self)
                self.clear()
                converted_edges = [tuple(item) for item in incoming_graph_data]
                if attr:
                    self.graph.update(attr)
                self.add_edges_from(converted_edges)
                return
        raw_init(self)
        # br-r37-c1-g438p: the Rust __new__ silently absorbs
        # unhashable nodes (storing them by Python id) when the
        # input is an iterable of edge tuples whose endpoints are
        # unhashable types (list, set, dict). nx raises
        # ``NetworkXError("Input is not a valid edge list")`` on
        # those inputs. Validate that the just-absorbed nodes are
        # hashable, but ONLY for the passthrough path — the
        # dict / numpy / pandas / Graph special cases below clear
        # and rebuild the graph from scratch, so any bad
        # absorption from those is overwritten and doesn't need
        # to be flagged at this point.
        is_special_input = (
            incoming_graph_data is None
            or isinstance(incoming_graph_data, dict)
            or (
                type(incoming_graph_data).__module__.startswith("numpy")
                and hasattr(incoming_graph_data, "shape")
                and hasattr(incoming_graph_data, "ndim")
            )
            or (
                type(incoming_graph_data).__module__.startswith("pandas")
                and hasattr(incoming_graph_data, "iloc")
                and hasattr(incoming_graph_data, "values")
            )
            or (
                hasattr(incoming_graph_data, "nodes")
                and hasattr(incoming_graph_data, "edges")
                and callable(getattr(incoming_graph_data, "is_multigraph", None))
            )
        )
        if not is_special_input and not locals().get("_skip_hash_walk"):
            try:
                for node in list(self.nodes()):
                    _HASH_PROBE.get(node)
            except TypeError as exc:
                self.clear()
                raise NetworkXError(
                    "Input is not a valid edge list"
                ) from exc
        if attr:
            self.graph.update(attr)
        if incoming_graph_data is None:
            return
        # Only dict-of-dicts needs explicit Python decoding; __new__
        # has already absorbed edge-list and Graph-instance inputs.
        if isinstance(incoming_graph_data, dict):
            _decode_dict_of_dicts_into(
                self,
                incoming_graph_data,
                is_multigraph,
                multigraph_input=multigraph_input if is_multigraph else None,
            )
            return
        # br-r37-c1-rxigp: numpy.ndarray / pandas.DataFrame are valid
        # adjacency-matrix inputs in nx.to_networkx_graph; the Rust
        # __new__ doesn't recognize them and silently absorbs them
        # as a node-iterable (yielding an empty graph). Detect by duck
        # type — avoid importing numpy/pandas eagerly at module import.
        if (
            type(incoming_graph_data).__module__.startswith("numpy")
            and hasattr(incoming_graph_data, "shape")
            and hasattr(incoming_graph_data, "ndim")
        ):
            self.clear()
            tmp = from_numpy_array(
                incoming_graph_data,
                create_using=type(self),
            )
            _copy_constructor_graph_source(
                self, tmp, is_multigraph=is_multigraph, attr=attr,
            )
            return
        if (
            type(incoming_graph_data).__module__.startswith("pandas")
            and hasattr(incoming_graph_data, "iloc")
            and hasattr(incoming_graph_data, "values")
        ):
            self.clear()
            tmp = from_pandas_adjacency(
                incoming_graph_data,
                create_using=type(self),
            )
            _copy_constructor_graph_source(
                self, tmp, is_multigraph=is_multigraph, attr=attr,
            )
            return
        # Cross-class / cross-library instantiation:
        # - br-xmginit: fnx.Graph(fnx.MultiGraph) silently returned empty
        #   (Multi* -> simple edges dropped)
        # - br-nxgraph: fnx.Graph(nx.Graph) also silently returned empty
        #   because the Rust __new__ only knows about fnx's own graph
        #   types; it absorbs nodes from any iterable but not edges from
        #   a foreign nx graph object.
        src_is_graph = hasattr(incoming_graph_data, "nodes") \
            and hasattr(incoming_graph_data, "edges") \
            and callable(getattr(incoming_graph_data, "is_multigraph", None))
        if not src_is_graph:
            return
        # br-copyedgeord: Rust __new__ copies fnx-native undirected
        # graphs through canonical endpoint storage, which can flip
        # original edge orientation. Rebuild all graph-object inputs
        # through the public edge iterator so fnx.Graph(src) and
        # fnx.MultiGraph(src) match nx insertion-order semantics.
        _copy_constructor_graph_source(
            self,
            incoming_graph_data,
            is_multigraph=is_multigraph,
            attr=attr,
        )

    return __init__


Graph.__init__ = _init_absorbing_dict_of_dicts(_GRAPH_INIT, is_multigraph=False)
DiGraph.__init__ = _init_absorbing_dict_of_dicts(_DIGRAPH_INIT, is_multigraph=False)
MultiGraph.__init__ = _init_absorbing_dict_of_dicts(_MULTIGRAPH_INIT, is_multigraph=True)
MultiDiGraph.__init__ = _init_absorbing_dict_of_dicts(_MULTIDIGRAPH_INIT, is_multigraph=True)

import inspect as _inspect


_GRAPH_TO_DIRECTED = Graph.to_directed
_DIGRAPH_TO_DIRECTED = DiGraph.to_directed
_MULTIGRAPH_TO_DIRECTED = MultiGraph.to_directed
_MULTIDIGRAPH_TO_DIRECTED = MultiDiGraph.to_directed
_GRAPH_TO_UNDIRECTED = Graph.to_undirected
_DIGRAPH_TO_UNDIRECTED = DiGraph.to_undirected
_MULTIGRAPH_TO_UNDIRECTED = MultiGraph.to_undirected
_MULTIDIGRAPH_TO_UNDIRECTED = MultiDiGraph.to_undirected
_GRAPH_SUBGRAPH = Graph.subgraph
_DIGRAPH_SUBGRAPH = DiGraph.subgraph
_MULTIGRAPH_SUBGRAPH = MultiGraph.subgraph
_MULTIDIGRAPH_SUBGRAPH = MultiDiGraph.subgraph
_GRAPH_NUMBER_OF_EDGES = Graph.number_of_edges
_DIGRAPH_NUMBER_OF_EDGES = DiGraph.number_of_edges
_GRAPH_REMOVE_NODE = Graph.remove_node
_DIGRAPH_REMOVE_NODE = DiGraph.remove_node
_GRAPH_REMOVE_EDGE = Graph.remove_edge
_DIGRAPH_REMOVE_EDGE = DiGraph.remove_edge
_GRAPH_NEIGHBORS = Graph.neighbors
_DIGRAPH_NEIGHBORS = DiGraph.neighbors
_DIGRAPH_SUCCESSORS = DiGraph.successors
_DIGRAPH_PREDECESSORS = DiGraph.predecessors
_GRAPH_ADJ_DESCRIPTOR = Graph.adj
_DIGRAPH_ADJ_DESCRIPTOR = DiGraph.adj
_DIGRAPH_SUCC_DESCRIPTOR = DiGraph.succ
_DIGRAPH_PRED_DESCRIPTOR = DiGraph.pred
_MULTIGRAPH_REMOVE_NODE = MultiGraph.remove_node
_MULTIGRAPH_REMOVE_EDGE = MultiGraph.remove_edge
_MULTIGRAPH_NEIGHBORS = MultiGraph.neighbors
_MULTIDIGRAPH_REMOVE_NODE = MultiDiGraph.remove_node
_MULTIDIGRAPH_REMOVE_EDGE = MultiDiGraph.remove_edge
_MULTIDIGRAPH_NEIGHBORS = MultiDiGraph.neighbors
_MULTIDIGRAPH_SUCCESSORS = MultiDiGraph.successors
_MULTIDIGRAPH_PREDECESSORS = MultiDiGraph.predecessors
_MULTIDIGRAPH_SUCC_DESCRIPTOR = MultiDiGraph.succ
_MULTIDIGRAPH_PRED_DESCRIPTOR = MultiDiGraph.pred
_EDGE_VIEW_TYPE = type(Graph().edges)
_DIEDGE_VIEW_TYPE = type(DiGraph().edges)
_EDGE_VIEW_CALL = _EDGE_VIEW_TYPE.__call__
_DIEDGE_VIEW_CALL = _DIEDGE_VIEW_TYPE.__call__
_DIGRAPH_ADJACENCY_VIEW_TYPE = type(DiGraph().pred)
_GRAPH_ADJACENCY_VIEW_TYPE = type(Graph().adj)
_MULTIGRAPH_DEGREE_DESCRIPTOR = MultiGraph.degree
_MULTIDIGRAPH_DEGREE_DESCRIPTOR = MultiDiGraph.degree
_MULTIGRAPH_ADJ_DESCRIPTOR = MultiGraph.adj
_MULTIDIGRAPH_ADJ_DESCRIPTOR = MultiDiGraph.adj
_MULTIGRAPH_NODE_VIEW_TYPE = type(MultiGraph().nodes)
_MULTIDIGRAPH_NODE_VIEW_TYPE = type(MultiDiGraph().nodes)
_MULTIGRAPH_NODE_VIEW_CALL = _MULTIGRAPH_NODE_VIEW_TYPE.__call__
_MULTIDIGRAPH_NODE_VIEW_CALL = _MULTIDIGRAPH_NODE_VIEW_TYPE.__call__


def _weighted_multidegree_value(graph, node, weight):
    """Return one weighted total degree without re-entering a degree view."""
    # br-r37-c1-degscalar, RE-LANDED on the fixed kernel (br-r37-c1-mgrevstore
    # 30323cfb6). The first attempt at this routing was reverted in 397a4b1b1
    # because the kernel returned an edge COUNT on a MultiDiGraph reverse copy.
    # Three sites now consult the store before defaulting, and a re-applied
    # routing measures 8 divergences on the 580-check directed sweep - exactly
    # the baseline's probe artifacts.
    if isinstance(weight, str):
        native = getattr(graph, "_native_weighted_degree_subset", None)
        if native is not None:
            try:
                pairs = native([node], weight)
            except TypeError:
                pairs = None
            if pairs:
                return pairs[0][1]

    def edge_weight(attrs):
        return attrs.get(weight, 1)

    if graph.is_directed():
        return sum(
            edge_weight(attrs)
            for keydict in graph.succ[node].values()
            for attrs in keydict.values()
        ) + sum(
            edge_weight(attrs)
            for keydict in graph.pred[node].values()
            for attrs in keydict.values()
        )

    neighbors = graph.adj[node]
    total = sum(
        edge_weight(attrs)
        for keydict in neighbors.values()
        for attrs in keydict.values()
    )
    if node in neighbors:
        total += sum(edge_weight(attrs) for attrs in neighbors[node].values())
    return total


class MultiGraphDegreeView:
    # br-r37-c1-mdvname: nx exposes MultiGraph.degree as
    # ``MultiDegreeView``. Rename the fnx wrapper class to match.
    def __repr__(self):
        return f"{type(self).__name__}({dict(self)!r})"

    def __str__(self):
        # br-r37-c1-dvvme: br-r37-c1-wu9dv gave the simple DegreeView
        # networkx's str (the list); this sibling printed its repr.
        return str(list(self))

    def __init__(self, graph, *, nodes=None, weight=None):
        self._graph = graph
        self._nodes = nodes
        self._weight = weight
        # br-r37-c1-pejo5: node revision at nbunch-resolution time.
        self._fnx_nodes_seq = getattr(graph, "nodes_seq", None)
        # br-r37-c1-ylunk: the raw view is itself live. Bind it once with this
        # public DegreeView instead of re-running descriptor binding on every
        # scalar subscript.
        self._raw_base_view = _MULTIGRAPH_DEGREE_DESCRIPTOR.__get__(
            graph, type(graph)
        )

    def __getstate__(self):
        # PyO3's raw MultiGraphDegreeView is intentionally not pickleable.
        # Rebuild it from the restored graph rather than serializing the bound
        # object; retain any user-added state on this Python wrapper.
        state = vars(self).copy()
        state.pop("_raw_base_view", None)
        return state

    def __setstate__(self, state):
        vars(self).update(state)
        self._raw_base_view = _MULTIGRAPH_DEGREE_DESCRIPTOR.__get__(
            self._graph, type(self._graph)
        )

    def _iter_nodes(self):
        if self._nodes is None:
            return iter(self._graph)
        return iter(self._nodes)

    def __len__(self):
        if self._nodes is None:
            return len(self._graph)
        return len(self._nodes)

    def __iter__(self):
        yield from _degree_view_guarded_pairs(self, self._iter_now())

    def _iter_now(self):
        # br-r37-c1-pejo5
        _degree_view_frozen_nodes_check(self)
        # br-r37-c1-mgdegiter: the UNWEIGHTED all-node walk. Both weighted
        # spellings below route to a native accumulator, and the simple classes
        # serve `dict(G.degree())` natively too - but for a multigraph the
        # unweighted case fell through to the per-node generator at the end of
        # this method, paying a Python frame plus `hash(node)` plus a lookup FOR
        # EVERY NODE. Found with scripts/read_call_scaling_probe.py: at 200->800
        # nodes `dict(G.degree())` read 12161->48161 Python calls (x3.96) on
        # MultiGraph and MultiDiGraph, against a flat 41 on Graph and DiGraph
        # where the same request is served natively.
        #
        # `_raw_base_view` is that native multigraph DegreeView, already built in
        # __init__. Iterating it directly is byte-equal to the generator it
        # replaces AND to networkx: verified pair-for-pair on both classes over a
        # fixture carrying parallel edges, a self-loop and an isolated node.
        #
        # Gated on `_weight is None` because that is exactly when `__getitem__`
        # would have delegated to `_raw_base_view[node]` anyway; a weighted view
        # must keep its own summation and is handled below.
        if self._nodes is None and self._weight is None:
            return iter(self._raw_base_view)
        # br-r37-c1-wdeg: weighted total degree over all nodes routes to the
        # native bulk accumulator, which reproduces nx's exact per-node
        # summation order and numeric type while avoiding the per-node
        # module-level degree() MultiAdjacencyView lambda walk (~16000x).
        if self._nodes is None and isinstance(self._weight, str):
            native = getattr(self._graph, "_native_weighted_degree", None)
            if native is not None:
                return iter(native(self._weight))
        # br-r37-c1-degnbw (cc): weighted nbunch (a validated node subset) routes to
        # the native weighted-subset pass instead of the per-node self[node]
        # _degree_compute loop (~0.04x). _nodes is already nbunch_iter-filtered, so
        # the native's per-node validation is a no-op; view[node] stays weighted via
        # __getitem__. getattr-guarded: MultiDiGraph falls back until its native lands.
        if self._nodes is not None and isinstance(self._weight, str):
            native = getattr(self._graph, "_native_weighted_degree_subset", None)
            if native is not None:
                return iter(native(self._nodes, self._weight))
        return ((node, self[node]) for node in self._iter_nodes())

    def __getitem__(self, node):
        # br-r37-c1-dv-subscript: nx raises ``TypeError`` on
        # unhashable subscript via the underlying dict lookup.
        # Hash-check eagerly so the nx-shaped TypeError surfaces
        # rather than the Rust raw multi DegreeView's leaked
        # KeyError.
        _HASH_PROBE.get(node)
        if self._weight is None:
            return self._raw_base_view[node]
        return _weighted_multidegree_value(self._graph, node, self._weight)

    def __bool__(self):
        return bool(len(self))

    def __call__(self, nbunch=None, weight=None):
        if weight is None:
            weight = self._weight
        if nbunch is None and weight == self._weight:
            return self
        if nbunch is None:
            return type(self)(self._graph, weight=weight)
        try:
            if nbunch in self._graph:
                if weight is None:
                    return self._raw_base_view[nbunch]
                return _weighted_multidegree_value(self._graph, nbunch, weight)
        except TypeError:
            pass
        # br-r37-c1-degnbnative (cc): unweighted multi total-degree(nbunch) — one
        # native pass (nx sums keydict lengths in Python; fnx sums in rust).
        if weight is None:
            native = getattr(self._graph, "_native_degree_pairs_subset", None)
            if native is not None:
                try:
                    pairs = native(nbunch)
                except TypeError as exc:
                    # br-r37-c1-degnbnative (cc): a single non-iterable bad node
                    # (e.g. degree(99), used by is_isolate) reaches the native call
                    # and fails try_iter; nx degree(n) raises "Node n is not in the
                    # graph." Map that case; unhashable-element messages pass through.
                    if "is not iterable" in str(exc):
                        raise NetworkXError(f"Node {nbunch} is not in the graph.")
                    raise NetworkXError(str(exc))
                return _filtered_degree_view(self, None, pairs=pairs, owner=self, graph=self._graph)
        nodes = list(self._graph.nbunch_iter(nbunch))
        return type(self)(self._graph, nodes=nodes, weight=weight)

    def __eq__(self, other):
        # br-r37-c1-dv-eq: see _WeightAwareDegreeView.__eq__.
        if isinstance(other, (MultiGraphDegreeView, MultiDiGraphDegreeView,
                              _WeightAwareDegreeView)):
            return dict(self) == dict(other)
        return NotImplemented

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq

    def __hash__(self):
        return id(self._graph)


# br-r37-c1-mdvname: ``type(MG.degree).__name__`` should return
# nx's canonical ``MultiDegreeView``.  _Set ``__name__`` so
# introspection matches.
MultiGraphDegreeView.__name__ = "MultiDegreeView"


class MultiDiGraphDegreeView:
    # br-r37-c1-mdvname: nx exposes MultiDiGraph.degree as
    # ``DiMultiDegreeView``. Rename the fnx wrapper class to match.
    def __repr__(self):
        return f"{type(self).__name__}({dict(self)!r})"

    def __str__(self):
        # br-r37-c1-dvvme: networkx's str is the list (see MultiGraphDegreeView).
        return str(list(self))

    def __init__(self, graph, *, nodes=None, weight=None):
        self._graph = graph
        self._nodes = nodes
        self._weight = weight
        # br-r37-c1-pejo5: node revision at nbunch-resolution time.
        self._fnx_nodes_seq = getattr(graph, "nodes_seq", None)
        self._raw_base_view = _MULTIDIGRAPH_DEGREE_DESCRIPTOR.__get__(
            graph, type(graph)
        )

    def __getstate__(self):
        state = vars(self).copy()
        state.pop("_raw_base_view", None)
        return state

    def __setstate__(self, state):
        vars(self).update(state)
        self._raw_base_view = _MULTIDIGRAPH_DEGREE_DESCRIPTOR.__get__(
            self._graph, type(self._graph)
        )

    def _iter_nodes(self):
        if self._nodes is None:
            return iter(self._graph)
        return iter(self._nodes)

    def __len__(self):
        if self._nodes is None:
            return len(self._graph)
        return len(self._nodes)

    def __iter__(self):
        yield from _degree_view_guarded_pairs(self, self._iter_now())

    def _iter_now(self):
        # br-r37-c1-pejo5
        _degree_view_frozen_nodes_check(self)
        # br-r37-c1-mgdegiter: the UNWEIGHTED all-node walk, directed sibling of
        # the fix in MultiDegreeView.__iter__ above. Same defect, same cause: the
        # weighted spellings route to a native accumulator and the simple classes
        # serve `dict(G.degree())` natively, but the unweighted multigraph case
        # fell through to the per-node generator at the end of this method - a
        # Python frame plus `hash(node)` plus a lookup for EVERY node.
        # scripts/read_call_scaling_probe.py read 12161->48161 Python calls across
        # 200->800 nodes (x3.96) against a flat 41 on Graph and DiGraph.
        #
        # THIS SIBLING WAS FOUND BY THE PROBE, NOT BY READING: fixing MultiGraph
        # alone left MultiDiGraph still scaling, because it is served by a
        # SEPARATE view class with its own copy of this method. Iterating
        # `_raw_base_view` is byte-equal to the generator it replaces and to
        # networkx, verified pair-for-pair over parallel edges, a self-loop and an
        # isolated node.
        if self._nodes is None and self._weight is None:
            return iter(self._raw_base_view)
        # br-r37-c1-wdeg: weighted total degree (in + out) over all nodes
        # routes to the native bulk accumulator (nx-exact succ-then-pred
        # summation order + numeric type), avoiding the per-node
        # module-level degree() MultiAdjacencyView lambda walk (~6000x).
        if self._nodes is None and isinstance(self._weight, str):
            native = getattr(self._graph, "_native_weighted_degree", None)
            if native is not None:
                return iter(native(self._weight))
        # br-r37-c1-degnbw (cc): weighted nbunch (a validated node subset) routes to
        # the native weighted-subset pass instead of the per-node self[node]
        # _degree_compute loop (~0.04x). _nodes is already nbunch_iter-filtered, so
        # the native's per-node validation is a no-op; view[node] stays weighted via
        # __getitem__. getattr-guarded: MultiDiGraph falls back until its native lands.
        if self._nodes is not None and isinstance(self._weight, str):
            native = getattr(self._graph, "_native_weighted_degree_subset", None)
            if native is not None:
                return iter(native(self._nodes, self._weight))
        return ((node, self[node]) for node in self._iter_nodes())

    def __getitem__(self, node):
        # br-r37-c1-dv-subscript: nx raises ``TypeError`` on
        # unhashable subscript via the underlying dict lookup.
        # Hash-check eagerly so the nx-shaped TypeError surfaces
        # rather than the Rust raw multi DegreeView's leaked
        # KeyError.
        _HASH_PROBE.get(node)
        if self._weight is None:
            return self._raw_base_view[node]
        return _weighted_multidegree_value(self._graph, node, self._weight)

    def __bool__(self):
        return bool(len(self))

    def __call__(self, nbunch=None, weight=None):
        if weight is None:
            weight = self._weight
        if nbunch is None and weight == self._weight:
            return self
        if nbunch is None:
            return type(self)(self._graph, weight=weight)
        try:
            if nbunch in self._graph:
                if weight is None:
                    return self._raw_base_view[nbunch]
                return _weighted_multidegree_value(self._graph, nbunch, weight)
        except TypeError:
            pass
        # br-r37-c1-degnbnative (cc): unweighted multi total-degree(nbunch) — one
        # native pass (nx sums keydict lengths in Python; fnx sums in rust).
        if weight is None:
            native = getattr(self._graph, "_native_degree_pairs_subset", None)
            if native is not None:
                try:
                    pairs = native(nbunch)
                except TypeError as exc:
                    # br-r37-c1-degnbnative (cc): a single non-iterable bad node
                    # (e.g. degree(99), used by is_isolate) reaches the native call
                    # and fails try_iter; nx degree(n) raises "Node n is not in the
                    # graph." Map that case; unhashable-element messages pass through.
                    if "is not iterable" in str(exc):
                        raise NetworkXError(f"Node {nbunch} is not in the graph.")
                    raise NetworkXError(str(exc))
                return _filtered_degree_view(self, None, pairs=pairs, owner=self, graph=self._graph)
        nodes = list(self._graph.nbunch_iter(nbunch))
        return type(self)(self._graph, nodes=nodes, weight=weight)

    def __eq__(self, other):
        # br-r37-c1-dv-eq: see _WeightAwareDegreeView.__eq__.
        if isinstance(other, (MultiGraphDegreeView, MultiDiGraphDegreeView,
                              _WeightAwareDegreeView)):
            return dict(self) == dict(other)
        return NotImplemented

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq

    def __hash__(self):
        return id(self._graph)
