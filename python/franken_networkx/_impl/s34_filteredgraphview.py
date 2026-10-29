

class _FilteredGraphView:
    adjlist_inner_dict_factory = dict
    adjlist_outer_dict_factory = dict
    edge_attr_dict_factory = dict
    graph_attr_dict_factory = dict
    node_attr_dict_factory = dict
    node_dict_factory = dict

    def __new__(cls, graph=None, *args, **kwargs):
        # br-r37-c1-pgfd2: build an EMPTY Rust base. The filtered-view classes
        # mix this in with the canonical PyO3 ``Graph`` (for isinstance
        # parity), whose ``__new__`` eagerly copies the parent ``graph``'s
        # entire node + edge set into the view's own Rust storage on every
        # construction — O(|V|+|E|) per ``subgraph_view`` / ``G.subgraph()``
        # call. That storage is dead weight: every query method below
        # (__iter__/nodes/edges/adjacency/neighbors/number_of_*/size/degree/
        # has_node/has_edge/copy) is overridden to answer through
        # ``self._graph`` plus the filters, never the base's own adjacency.
        # ``super().__new__(cls)`` (cls's MRO routes to the Graph base)
        # allocates an empty graph in O(1); ``__init__`` wires up the live
        # filtered view. (Also removes the stale-base hazard that forced the
        # ``has_node`` override.)
        if (
            graph is None
            and not args
            and not kwargs
            and cls.__new__ is _FilteredGraphView.__new__
        ):
            return _new_empty_graph_for_view_class(cls)
        return super().__new__(cls)

    def __init__(self, graph, *, filter_node=None, filter_edge=None):
        _store = self.__dict__
        self._fnx_register_gc_dict(_store)
        fast_init = (
            not _store
            and type(graph) in _FILTERED_GRAPH_VIEW_TYPES_SOURCE_TYPES
            and type(self) in _FILTERED_GRAPH_VIEW_TYPES.values()
            and (
                type(self).__setattr__ is _graph_setattr_with_cached_public_adj
                or type(self).__setattr__ is _digraph_setattr_with_cached_public_adjacency
                or type(self).__setattr__ is _multigraph_setattr_with_cached_public_adj
                or type(self).__setattr__ is _multidigraph_setattr_with_cached_public_adjacency
            )
        )
        _store["_graph"] = graph
        # br-r37-c1-fgv-graph-id: nx's subgraph_view / copy(as_view=
        # True) shares the parent's ``graph`` dict by reference —
        # ``view.graph is parent.graph`` must hold so subsequent
        # mutations to the parent's graph attrs are visible through
        # the view.  ``self.graph = graph.graph`` looks like an
        # assignment, but the _GraphAttrsDescriptor.__set__ on the
        # canonical Graph base class intercepts the assignment and
        # clears+updates the existing Rust-native dict instead of
        # storing the ref — losing identity.  Bypass the descriptor
        # by writing directly to the override slot in vars(self).
        _store[_GRAPH_ATTR_OVERRIDE] = graph.graph
        _store["_filter_node"] = filter_node or (lambda node: True)
        # br-r37-c1-h8vqr: the NODE-filter twin of the edge flag just below,
        # which already existed. Without it `_node_visible` calls a no-op lambda
        # for every node it checks, and it is the hottest helper on every
        # filtered walk -- cProfile counted 170 calls to answer a THREE-NODE
        # degree query, because it runs once per endpoint of every edge visited.
        # `edge_subgraph`, `restricted_view` and `subgraph_view(filter_edge=...)`
        # all leave the node filter at its default, so this is the common shape
        # rather than a corner.
        _store["_filter_node_is_default"] = (
            filter_node is None or filter_node is _subgraph_view_no_filter_default
        )
        _store["_filter_edge_is_default"] = (
            filter_edge is None or filter_edge is _subgraph_view_no_filter_default
        )
        _store["_filter_edge"] = filter_edge or (lambda *args: True)
        # br-r37-c1-h8vqr: whether the PARENT is a multigraph is fixed for the
        # life of this view -- it is a property of the parent's class, and the
        # parent cannot change class underneath us. `_edge_visible` consulted it
        # per EDGE through `self.is_multigraph()` -> `self._graph.is_multigraph()`,
        # two Python frames deep, and cProfile counted 129 such calls to answer a
        # THREE-NODE degree query (25.5us of 192us). Resolve it once here.
        #
        # `is_multigraph()` itself is left delegating rather than answering from
        # this flag: it is public API, a caller may reach it on a view whose
        # parent was swapped by some path this constructor never saw, and the
        # per-edge saving is already taken below.
        _store["_fnx_parent_is_multigraph"] = graph.is_multigraph()
        if fast_init:
            _store["frozen"] = True
            _store["nodes"] = NodeView(self)
        else:
            self.frozen = True
            self.nodes = NodeView(self)
        # br-r37-c1-batchov: build all three views BEFORE assigning any, so the
        # three private overrides can go through the funnel in one pass. The
        # factory only reads `is_multigraph()` and closes over `self`, so no
        # view ever depended on a previous assignment.
        adj_view = _filtered_public_adjacency_view(self)
        if graph.is_directed():
            succ_view = _filtered_public_adjacency_view(self)
            pred_view = _filtered_public_adjacency_view(self, reverse=True)
            if fast_init:
                _store[_PRIVATE_ADJ_OVERRIDE] = adj_view
                self._fnx_set_private_adj_override()
                _store[_PRIVATE_SUCC_OVERRIDE] = succ_view
                self._fnx_set_private_dir_override()
                _store[_PRIVATE_PRED_OVERRIDE] = pred_view
                self._fnx_set_private_dir_override()
                _install_private_method_shadows(self, _store)
            else:
                _set_private_overrides(
                    self,
                    (
                        (_PRIVATE_ADJ_OVERRIDE, adj_view),
                        (_PRIVATE_SUCC_OVERRIDE, succ_view),
                        (_PRIVATE_PRED_OVERRIDE, pred_view),
                    ),
                )
        else:
            if fast_init:
                _store[_PRIVATE_ADJ_OVERRIDE] = adj_view
                self._fnx_set_private_adj_override()
                _install_private_method_shadows(self, _store)
            else:
                self.adj = adj_view

    def _fnx_native_graph(self):
        # br-r37-c1-4rhw0: the concrete graph this view shows, for native
        # kernels - fnx-python's extract_graph calls this for any view it is
        # handed. The view's own Rust storage is empty (br-r37-c1-pgfd2), so a
        # kernel reading it saw no nodes at all.
        return _materialize_view(self)

    def __iter__(self):
        filter_nodes = getattr(self._filter_node, "nodes", None)
        if filter_nodes is not None:
            try:
                node_filter_shorter = 2 * len(filter_nodes) < len(self._graph)
            except TypeError:
                node_filter_shorter = False
            if node_filter_shorter:
                for node in filter_nodes:
                    if node in self._graph:
                        yield node
                return
        # br-r37-c1-x3829: we are iterating the PARENT's own nodes, so the
        # membership half of `_node_visible` - `node in self._graph` - is
        # provably true for every node yielded here and was a wasted C-level
        # containment check per node per walk. And when the node filter is the
        # default there is no predicate to apply either, so the whole walk is
        # the parent's iteration. Measured on restricted_view, which walks every
        # parent node: 0.2747x against networkx at 800 nodes, 0.8970x after.
        #
        # `_node_visible` is left untouched for every OTHER caller - membership
        # is load-bearing there, because those nodes arrive from outside the
        # parent (`__contains__`, `_nbunch`, `_edge_visible`).
        if self._filter_node_is_default:
            yield from self._graph
            return
        filter_node = self._filter_node
        for node in self._graph:
            if filter_node(node):
                yield node

    def __bool__(self):
        return _view_bool(self)

    def __repr__(self):
        return _view_repr(self)

    def __len__(self):
        # br-r37-c1-vlenall: a view whose NODE filter is the default admits every
        # parent node, so its length IS the parent's - no counting needed. The
        # fallback below is `sum(1 for _ in self)`, an O(N) walk, and
        # `G.copy(as_view=True)` was taking it: 31.6us at 200 nodes, 497.3us at
        # 3200 (15.7x growth) against networkx's flat 0.07-0.09us, which proxies
        # the parent's mapping. CONSTRUCTION was flat at 0.68x - only the read grew.
        #
        # `_filter_node_is_default` is this constructor's own flag and is exactly
        # right: verified True for copy(as_view=True) (len == parent len) and
        # False for subgraph() and edge_subgraph() (len < parent len). An EDGE
        # filter cannot remove a NODE, so a default node filter is sufficient.
        if getattr(self, "_filter_node_is_default", False):
            return len(self._graph)
        length = getattr(self._filter_node, "length", None)
        if length is not None:
            return length
        filter_nodes = getattr(self._filter_node, "nodes", None)
        if filter_nodes is not None:
            return sum(1 for node in filter_nodes if node in self._graph)
        # br-r37-c1-h0t5k: the counting fallback. `sum(1 for _ in self)` pays
        # THREE Python-level frame operations per node - the genexpr resumes,
        # `__iter__`'s generator resumes, and the filter is called - to produce a
        # number that only needs the filter's answer. Reaching past `__iter__` to
        # the parent and letting `map`/`sum` loop in C leaves ONE frame per node,
        # the predicate call itself, which is irreducible for a Python filter.
        #
        # Reaching past `__iter__` is equivalent HERE and nowhere else: control
        # only arrives at this line when the filter is non-default and carries
        # neither `.length` nor `.nodes` - precisely the case where `__iter__`
        # walks the parent applying the filter and nothing else. The three
        # branches above all return before this point.
        #
        # `bool` is not decoration: a filter may return any truthy value and
        # `sum` would ADD it. networkx counts nodes, so the map must too.
        #
        # The three sibling `sum(1 for _ in self)` fallbacks in this file are NOT
        # this lever and are deliberately untouched - they dedup through a
        # `yielded` set, filter on edge visibility, or honour a reverse flag, so
        # their `__iter__` is not a bare parent walk.
        return sum(map(bool, map(self._filter_node, self._graph)))

    def __contains__(self, node):
        return self._node_visible(node)

    def has_node(self, n):
        # br-r37-c1-fgv-has-node: ``__contains__`` correctly
        # delegates to ``_node_visible`` (which re-checks the
        # parent's current node set + the filter), but
        # ``has_node`` was inherited from the canonical Graph
        # base class (added as a second base for isinstance
        # parity, br-r37-c1-rcd0e) and went through the Rust-
        # native node lookup against the synthetic view's
        # uninitialised Rust state.  Result: ``parent.remove_
        # node(n)`` left ``view.has_node(n)`` returning True
        # forever — a stale-view defect breaking nx's "view
        # tracks parent mutations" contract.  Mirror nx by
        # routing through ``_node_visible``.
        return self._node_visible(n)

    def __getitem__(self, node):
        return self.adj[node]

    def __getattr__(self, name):
        if name in _FILTERED_VIEW_MUTATORS:
            return _frozen
        # br-r37-c1-fvgetattr: an attribute MISS must not materialise the parent.
        # The old body was `return getattr(self.copy(), name)`, and copy() walks
        # the PARENT: hasattr on a four-node subgraph of a 3200-node parent cost
        # 394us and raised AttributeError anyway - 0.0008x against networkx,
        # growing linearly in the parent with no floor. Misses are ordinary:
        # hasattr, duck-typing probes, copy, pickle and repr machinery all ask
        # for names a graph does not have.
        #
        # When this runs the name is already absent from the whole MRO, so the
        # copy can only help for attributes that exist as INSTANCE state. A
        # memoised ONE-EDGE graph of the parent's class carries that state and
        # costs nothing, so it answers "could this exist?" without the parent.
        # If there is no `_graph` (an object mid-construction, or a view shape
        # that does not keep one) the old behaviour is kept unchanged.
        if name.startswith("__") or name == "_graph":
            raise AttributeError(name)
        parent = self.__dict__.get("_graph")
        if parent is not None:
            parent_cls = type(parent)
            probe = _FILTERED_VIEW_ATTR_PROBE.get(parent_cls)
            if probe is None:
                probe = parent_cls()
                probe.add_edge("__fnx_attr_probe_u__", "__fnx_attr_probe_v__")
                _FILTERED_VIEW_ATTR_PROBE[parent_cls] = probe
            if not hasattr(probe, name):
                raise AttributeError(
                    f"{type(self).__name__!r} object has no attribute {name!r}"
                )
        return getattr(self.copy(), name)

    # br-r37-c1-fgvfrz: peer commit 9b9f47f2 (br-r37-c1-rcd0e) added
    # Graph/DiGraph/MultiGraph/MultiDiGraph as a SECOND base class for
    # the _FILTERED_GRAPH_VIEW_TYPES synthetics, so isinstance(sg,
    # fnx.Graph) is True. But that change moved the canonical class's
    # mutation methods (add_node, add_edge, ...) into the synthetic
    # MRO BEFORE __getattr__ ever gets consulted — so mutating a
    # subgraph view became a silent no-op (the call goes to
    # Graph.add_node which targets unset Rust state on the synthetic
    # instance), violating the documented frozen-graph contract that
    # nx enforces by raising NetworkXError("Frozen graph can't be
    # modified"). Explicitly shadow each mutator on _FilteredGraphView
    # so it's found in MRO before the inherited canonical method.
    add_node = _frozen
    add_nodes_from = _frozen
    remove_node = _frozen
    remove_nodes_from = _frozen
    add_edge = _frozen
    add_edges_from = _frozen
    add_weighted_edges_from = _frozen
    remove_edge = _frozen
    remove_edges_from = _frozen
    clear = _frozen
    clear_edges = _frozen
    update = _frozen

    def is_directed(self):
        return self._graph.is_directed()

    def is_multigraph(self):
        return self._graph.is_multigraph()

    def _node_visible(self, node):
        # br-r37-c1-h8vqr: skip the no-op predicate call when the node filter is
        # the default. Membership alone IS the answer then, and `in` is a C-level
        # containment check against the parent.
        if self._filter_node_is_default:
            return node in self._graph
        return node in self._graph and self._filter_node(node)

    def _edge_visible(self, u, v, key=None):
        if not (self._node_visible(u) and self._node_visible(v)):
            return False
        # br-r37-c1-h8vqr: the cached flag, not `self.is_multigraph()` -- see
        # __init__. This runs once per EDGE on every filtered walk.
        if self._fnx_parent_is_multigraph:
            return self._filter_edge(u, v, key)
        return self._filter_edge(u, v)

    def _nbunch(self, nbunch):
        if nbunch is None:
            return list(self)
        if self._node_visible(nbunch):
            return [nbunch]
        try:
            return [node for node in nbunch if self._node_visible(node)]
        except TypeError:
            return []

    def nodes(self, data=False):
        if data:
            return [
                (node, _node_attrs_for_view_graph(self._graph, node))
                for node in self
            ]
        return list(self)

    def adjacency(self):
        if self.is_multigraph():
            return ((node, self.adj[node]) for node in self)
        return ((node, FilterAtlas(self, node)) for node in self)

    def _edges(self, nbunch=None, data=False, keys=False):
        nodes = self._nbunch(nbunch)
        # cc-rvfast: concrete-parent fast path for a NON-default edge filter
        # (restricted_view and other generic filter_edge closures). The generic
        # slow path below accesses ``self.adj[source][target]`` per edge, routing
        # every endpoint through ``_node_visible`` (``__contains__`` +
        # ``_private_override`` + ``predicate``) and per-edge ``is_multigraph`` /
        # ``vars`` — ``restricted_view(G).edges()`` ran ~0.13x nx. When the parent
        # is a CONCRETE simple graph and no nbunch is given, walk its native
        # adjacency rows once and apply the raw filters directly: target visibility
        # via the precomputed visible-node set (== ``filter_node`` for a concrete
        # parent, since every row target is a parent node) and the raw
        # ``filter_edge`` closure in the SAME single orientation, row order, and
        # undirected ``seen`` dedup as the slow ``self.adj`` path. Byte-identical.
        if (
            nbunch is None
            and not isinstance(data, str)
            and data is not None
            and not keys
            and type(self._graph) in (Graph, DiGraph)
            # br-r37-c1-ktsxn: a NODE-SET filter_node keeps the node-set chain
            # path further down, which is faster still. Without this guard the
            # relaxed gate above captured `G.subgraph()` and
            # `subgraph_view(show_nodes)` into THIS branch and measured them
            # 0.92x -- an 8% regression on the two most common spellings, caught
            # by carrying them as controls. Same guard the multigraph sibling
            # below already applies, and for the same reason.
            and getattr(getattr(self, "_filter_node", None), "nodes", None) is None
        ):
            parent = self._graph
            filter_edge = self._filter_edge
            # br-r37-c1-ktsxn: this fast path was gated to a NON-default edge
            # filter, so an arbitrary callable `filter_node` with the DEFAULT
            # edge filter fell between two fast paths and took the generic
            # `self.adj[source][target]` walk. Measured on 400 nodes / 1600
            # edges, `len(list(view.edges))`: `subgraph()` 3.050x and
            # `subgraph_view(show_nodes)` 3.814x (node-set chain path),
            # `restricted_view` 2.582x (this path) -- and
            # `subgraph_view(lambda)` 0.134x with no path at all. Three of the
            # four siblings were covered; this is the fourth.
            #
            # `unfiltered` short-circuits BEFORE the call, so the non-default
            # path that already used this branch pays one boolean test and
            # never loses its filter.
            unfiltered = self._filter_edge_is_default
            visible_set = set(nodes)
            fast = []
            if parent.is_directed():
                # br-cvsubedges: per-source `_fast_succ_row` rebuilds the WHOLE
                # native adjacency each call (O(V*(V+E))); hoist the snapshot out of
                # the loop exactly as the node-set chain path below does. na_row is
                # the O(deg) live-attr row used only for the data=True merge.
                na_keys = getattr(parent, "_native_adjacency_keys", None)
                na_adj = getattr(parent, "_native_adjacency_dict", None)
                na_row = getattr(parent, "_native_successor_row_dict", None)
                # br-r37-c1-w2zqe: read only the rows asked for. The hoist above
                # took this from O(V*(V+E)) to O(V+E), which reads like a fix and
                # measures like one at ONE parent size — but O(V+E) is still the
                # whole parent where networkx is O(rows), so the ratio kept
                # degrading without bound from a better starting point. Measured
                # on DiGraph.edge_subgraph(5 edges).edges(): 0.2078x at N=500 and
                # 0.0004x at N=32000, where fnx spends 28.9 ms against networkx's
                # 11 us, and `us/N` RISES with N (372n -> 905n) so it is worse
                # than linear in the parent.
                #
                # This is the SAME defect and the SAME remedy as
                # br-r37-c1-thssf, one branch over: that bead fixed the
                # default-edge-filter path used by subgraph(), and this is the
                # NON-default one used by edge_subgraph() and restricted_view().
                # Fixing one branch of a routine and not its sibling is exactly
                # the partially-applied-fix trap thssf was written about.
                #
                # `na_row` is the per-source accessor already bound here for the
                # data=True merge. Its key ORDER and VALUES were verified equal
                # to both whole-graph snapshots over EVERY node at two parent
                # sizes before substituting; the old `live.get(target,
                # keyrow[target])` fallback implied they might disagree, and they
                # do not — with `keyrow` now BEING `live`, that fallback is
                # self-referential and drops out.
                if not data and na_row is not None:
                    for source in nodes:
                        for target in na_row(source):
                            if target in visible_set and (unfiltered or filter_edge(source, target)):
                                fast.append((source, target))
                elif data and na_row is not None:
                    for source in nodes:
                        live = na_row(source)
                        for target in live:
                            if target in visible_set and (unfiltered or filter_edge(source, target)):
                                fast.append((source, target, live[target]))
                elif not data and na_keys is not None:
                    # Retained for a parent that exposes the whole-graph snapshot
                    # but not the per-row accessor.
                    succ_keys = dict(na_keys())
                    for source in nodes:
                        for target in succ_keys[source]:
                            if target in visible_set and (unfiltered or filter_edge(source, target)):
                                fast.append((source, target))
                elif data and na_adj is not None:
                    full = na_adj()
                    for source in nodes:
                        keyrow = full[source]
                        for target in keyrow:
                            if target in visible_set and (unfiltered or filter_edge(source, target)):
                                fast.append((source, target, keyrow[target]))
                else:
                    for source in nodes:
                        row = _fast_succ_row(parent, source)
                        for target in row:
                            if target in visible_set and (unfiltered or filter_edge(source, target)):
                                fast.append(
                                    (source, target, row[target]) if data else (source, target)
                                )
            else:
                seen = set()
                for source in nodes:
                    row = _fast_adj_row(parent, source)
                    for target in row:
                        if target in seen or target not in visible_set:
                            continue
                        if not (unfiltered or filter_edge(source, target)):
                            continue
                        fast.append(
                            (source, target, row[target]) if data else (source, target)
                        )
                    seen.add(source)
            return fast
        # cc-rvfastmg: multigraph sibling of cc-rvfast — restricted_view (closure
        # filter_node + non-default filter_edge) over a CONCRETE multigraph. The
        # slow path pays per-edge FilterMultiAdjacency machinery
        # (MultiGraph/MultiDiGraph restricted_view.edges() ran 0.11-0.14x). Walk the
        # native per-node row ({target: keydict}, O(deg) — the multigraph
        # `_fast_succ_row`/`_fast_adj_row` use per-row native dicts, NOT the O(V)
        # whole-graph rebuild that simple DiGraph uses) in ROW order (a closure
        # filter_node yields nx's FilterMultiInner atlas order — verified byte-exact,
        # no `_multigraph_filtered_target_order` reorder, which is set-filter-only),
        # apply the visible-node set to each target and the raw (u, v, key)
        # filter_edge to each parallel edge. Gated to a CLOSURE filter_node (no
        # `.nodes` set) so a node-set filter — which CAN take nx's reordered
        # intersection order — keeps the slow/node-set path.
        if (
            nbunch is None
            and not self._filter_edge_is_default
            and getattr(getattr(self, "_filter_node", None), "nodes", None) is None
            and not isinstance(data, str)
            and data is not None
            and type(self._graph) in (MultiGraph, MultiDiGraph)
        ):
            parent = self._graph
            filter_edge = self._filter_edge
            visible_set = set(nodes)
            fast = []

            def _emit_mg(source, target, keydict):
                for key, attrs in keydict.items():
                    if not filter_edge(source, target, key):
                        continue
                    if data and keys:
                        fast.append((source, target, key, attrs))
                    elif data:
                        fast.append((source, target, attrs))
                    elif keys:
                        fast.append((source, target, key))
                    else:
                        fast.append((source, target))

            if parent.is_directed():
                for source in nodes:
                    row = _fast_succ_row(parent, source)
                    for target in row:
                        if target in visible_set:
                            _emit_mg(source, target, row[target])
            else:
                seen = set()
                for source in nodes:
                    row = _fast_adj_row(parent, source)
                    for target in row:
                        if target in seen or target not in visible_set:
                            continue
                        _emit_mg(source, target, row[target])
                    seen.add(source)
            return fast
        # br-r37-c1-r3gjb/TealSpring nested-view pass: for chains of
        # default-edge, node-set subgraph views, walk the concrete parent's
        # native PLAIN-dict rows once. Source order stays `nodes` above. Simple
        # rows keep concrete row order and gate against the intersection set;
        # multigraph rows replay each filter layer's node_ok_shorter set-vs-row
        # ordering branch so parallel-edge edge order remains byte-identical.
        parent, filter_chain, visible_keep = _default_node_set_filter_chain(self)
        if (
            parent is not None
            and not isinstance(data, str)
            and data is not None
            and type(parent) in (Graph, DiGraph)
        ):
            fast = []
            if self.is_directed():
                # br-cvsubedges (cc): the per-source _fast_succ_row(parent, source)
                # calls parent._native_adjacency_dict()[source] — a WHOLE-GRAPH
                # adjacency rebuild EVERY call => O(V*(V+E)). list(subgraph.edges())
                # was 0.009x (111x slower than nx). Hoist the whole-graph snapshot
                # out of the loop: key-only for data=False; for data=True keep
                # _fast_succ_row's live-attr merge but snapshot the key/order rows
                # once (the live per-node row is O(deg)). Byte-identical output.
                na_keys = getattr(parent, "_native_adjacency_keys", None)
                na_adj = getattr(parent, "_native_adjacency_dict", None)
                na_row = getattr(parent, "_native_successor_row_dict", None)
                # br-r37-c1-thssf: read ONLY the rows asked for. The hoist above
                # took this from O(V*(V+E)) to O(V+E), but O(V+E) is still the
                # WHOLE parent graph for a subgraph of ten nodes, and networkx is
                # O(rows) — so the loss grew without bound with the parent's size
                # (0.0015x at N=32000, 667x slower than nx) while the Graph,
                # MultiGraph and MultiDiGraph siblings stayed flat and winning.
                # The per-row accessor is already bound here for the data merge;
                # it carries identical key order and identical values to the
                # whole-graph snapshot (verified over every node at two sizes),
                # so this is the same output at O(sum of the requested degrees).
                if na_row is not None:
                    for source in nodes:
                        row = na_row(source)
                        for target in row:
                            if target in visible_keep:
                                fast.append(
                                    (source, target, row[target])
                                    if data
                                    else (source, target)
                                )
                elif not data and na_keys is not None:
                    succ_keys = dict(na_keys())
                    for source in nodes:
                        for target in succ_keys[source]:
                            if target in visible_keep:
                                fast.append((source, target))
                elif data and na_adj is not None:
                    full = na_adj()
                    for source in nodes:
                        keyrow = full[source]
                        for target in keyrow:
                            if target in visible_keep:
                                fast.append((source, target, keyrow[target]))
                else:
                    for source in nodes:
                        row = _fast_succ_row(parent, source)
                        for target in row:
                            if target not in visible_keep:
                                continue
                            fast.append(
                                (source, target, row[target])
                                if data
                                else (source, target)
                            )
            else:
                seen = set()
                for source in nodes:
                    row = _fast_adj_row(parent, source)
                    for target in row:
                        if target not in visible_keep or target in seen:
                            continue
                        fast.append((source, target, row[target]) if data else (source, target))
                    seen.add(source)
            return fast
        if (
            parent is not None
            and not isinstance(data, str)
            and data is not None
            and type(parent) in (MultiGraph, MultiDiGraph)
        ):
            # br-r37-c1-ag2sx: multigraph variant of the edge fast path. Walks
            # the native parent PLAIN-dict {nbr: keydict} row once per source
            # (vs re-materialising self.adj[source][target] per target), in the
            # SAME node_ok_shorter order nx's FilterMultiInner uses (keep order
            # when 2*len(keep) < len(row), else row order), then iterates the
            # keydict for parallel edges. Gating on `target in keep` (O(1)).
            fast = []
            directed = self.is_directed()

            def _emit_keys(out, source, target, keydict):
                for key, attrs in keydict.items():
                    if data and keys:
                        out.append((source, target, key, attrs))
                    elif data:
                        out.append((source, target, attrs))
                    elif keys:
                        out.append((source, target, key))
                    else:
                        out.append((source, target))

            if directed:
                for source in nodes:
                    row = _fast_succ_row(parent, source)
                    for target in _multigraph_filtered_target_order(row, filter_chain):
                        _emit_keys(fast, source, target, row[target])
            else:
                seen = set()
                for source in nodes:
                    row = _fast_adj_row(parent, source)
                    for target in _multigraph_filtered_target_order(row, filter_chain):
                        if target in seen:
                            continue
                        _emit_keys(fast, source, target, row[target])
                    seen.add(source)
            return fast
        result = []
        if self.is_directed():
            for source in nodes:
                for target in self.adj[source]:
                    if self.is_multigraph():
                        for key, attrs in self.adj[source][target].items():
                            if data and keys:
                                result.append((source, target, key, attrs))
                            elif data:
                                result.append((source, target, attrs))
                            elif keys:
                                result.append((source, target, key))
                            else:
                                result.append((source, target))
                    else:
                        # br-cvedges (cc): only materialize the conversion-view attr
                        # dict (self.adj[u][v] is a per-edge merge/copy) when data is
                        # actually requested — list(view.edges()) was fetching+dropping
                        # it per edge.
                        if data:
                            result.append((source, target, self.adj[source][target]))
                        else:
                            result.append((source, target))
            return result

        seen = set()
        for source in nodes:
            for target in self.adj[source]:
                if target in seen:
                    continue
                if self.is_multigraph():
                    for key, attrs in self.adj[source][target].items():
                        if data and keys:
                            result.append((source, target, key, attrs))
                        elif data:
                            result.append((source, target, attrs))
                        elif keys:
                            result.append((source, target, key))
                        else:
                            result.append((source, target))
                else:
                    attrs = self.adj[source][target]
                    if data:
                        result.append((source, target, attrs))
                    else:
                        result.append((source, target))
            seen.add(source)
        return result

    @property
    def edges(self):
        # br-r37-c1-fevname: nx exposes subgraph-view edges with the
        # canonical per-class name (EdgeView for Graph, OutEdgeView
        # for DiGraph, MultiEdgeView for MultiGraph, OutMultiEdgeView
        # for MultiDiGraph). Dispatch based on the underlying graph's
        # directionality and multi-ness so ``type(S.edges).__name__``
        # matches nx exactly.
        # br-r37-c1-b3cnf follow-up: cache the wrapper so
        # ``sg.edges is sg.edges`` matches nx's @cached_property.
        cache = vars(self)
        view = cache.get("_fnx_view_edges")
        if view is not None:
            return view
        directed = self.is_directed()
        multi = self.is_multigraph()
        if multi and directed:
            cls = _FilteredOutMultiEdgeView
        elif multi:
            cls = _FilteredMultiEdgeView
        elif directed:
            cls = _FilteredOutEdgeView
        else:
            cls = _FilteredGraphEdgeView
        view = cls(self)
        cache["_fnx_view_edges"] = view
        return view

    def neighbors(self, node):
        if not self._node_visible(node):
            raise _traversal_missing_source_error(self, node)
        return iter(self.adj[node])

    def successors(self, node):
        return self.neighbors(node)

    def predecessors(self, node):
        if not self.is_directed():
            return self.neighbors(node)
        if not self._node_visible(node):
            raise _traversal_missing_source_error(self, node)
        return iter(self.pred[node])

    def has_edge(self, u, v, key=None):
        if self.is_multigraph():
            if not self._graph.has_edge(u, v, key):
                return False
            if key is not None:
                return self._edge_visible(u, v, key)
            return any(self._edge_visible(u, v, edge_key) for edge_key in self._graph[u][v])
        if not self._graph.has_edge(u, v):
            return False
        return self._edge_visible(u, v)

    def number_of_nodes(self):
        return len(self)

    def order(self):
        # The synthetic view owns no Rust nodes, so it must not inherit the
        # canonical class's raw ``order`` descriptor.
        return self.number_of_nodes()

    def number_of_edges(self, u=None, v=None):
        if u is None and v is None:
            edge_subgraph_count = self._edge_subgraph_number_of_edges()
            if edge_subgraph_count is not None:
                return edge_subgraph_count
            return len(self._edges(keys=self.is_multigraph()))
        if self.is_multigraph():
            # br-r37-c1-dvvme: networkx's MultiGraph.number_of_edges(u, v) is
            # len(self._adj[u][v]) with every KeyError - an absent u or v,
            # v=None - answered 0.
            if v is None or not self._graph.has_edge(u, v):
                return 0
            return sum(
                1
                for edge_key in self._graph[u][v]
                if self._edge_visible(u, v, edge_key)
            )
        # br-r37-c1-dvvme: networkx's is `v in self._adj[u]`, so an absent u
        # raises the view adjacency's KeyError ("Key 9 not found", networkx's
        # FilterAdjacency) - fnx answered 0, or a bare KeyError(u) for v=None.
        return 1 if v in self.adj[u] else 0

    def _edge_subgraph_number_of_edges(self):
        selected_edges = getattr(
            self._filter_edge, "_fnx_edge_subgraph_selected_edges", None
        )
        if selected_edges is None:
            return None

        parent = self._graph
        if self.is_multigraph():
            if self.is_directed():
                return sum(
                    1
                    for u, v, key in selected_edges
                    if parent.has_edge(u, v, key)
                )

            count = 0
            seen = set()
            for u, v, key in selected_edges:
                edge = (u, v, key)
                if edge in seen:
                    continue
                seen.add(edge)
                seen.add((v, u, key))
                if parent.has_edge(u, v, key):
                    count += 1
            return count

        if self.is_directed():
            return sum(1 for u, v in selected_edges if parent.has_edge(u, v))

        count = 0
        seen = set()
        for u, v in selected_edges:
            edge = (u, v)
            if edge in seen:
                continue
            seen.add(edge)
            seen.add((v, u))
            if parent.has_edge(u, v):
                count += 1
        return count

    def size(self, weight=None):
        # br-r37-c1-fgv-size: the canonical Graph.size inherited from
        # the second base class delegates to the Rust raw size which
        # reads the parent's full Rust state without honoring the
        # view's filters.  Result: ``view.size(weight="w")`` summed
        # the parent's full edge weight (including filtered-out
        # edges) instead of the visible subset.  Override to walk
        # the filtered edges() iterator so the contract matches nx's
        # ``sum(d for _, d in view.degree(weight=w)) / 2``.
        if weight is None:
            return self.number_of_edges()
        if self.is_multigraph():
            total = sum(
                attrs.get(weight, 1)
                for _, _, _, attrs in self.edges(keys=True, data=True)
            )
        else:
            total = sum(
                attrs.get(weight, 1)
                for _, _, attrs in self.edges(data=True)
            )
        return float(total)

    def _copy_type(self):
        if self.is_directed():
            return MultiDiGraph if self.is_multigraph() else DiGraph
        return MultiGraph if self.is_multigraph() else Graph

    def _induced_node_order(self, filter_nodes):
        """nx's ``FilterAtlas.__iter__`` node order, resolved at C speed.

        Mirrors ``__iter__`` exactly — keep-set iteration order when the keep
        set is under half the parent, else parent order — but tests membership
        against a materialized ``set(parent)`` so neither branch pays fnx's
        Python-level ``__contains__`` (~0.8us) once per node.
        """
        parent = self._graph
        try:
            keep_shorter = 2 * len(filter_nodes) < len(parent)
        except TypeError:
            return None
        if keep_shorter:
            parent_nodes = set(parent)
            return [node for node in filter_nodes if node in parent_nodes]
        return [node for node in parent if node in filter_nodes]

    def _copy_induced_multi_fast(self):
        """br-r37-c1-pzw49: the multigraph half of the induced-copy fast path.

        Multigraphs fell through to the generic filtered view, which re-tests
        node visibility per endpoint and adds nodes and edges one call at a
        time — cProfile at 40 copies of a 2000-node keep set showed
        ``_node_visible`` alone at 10000 calls per copy. Walking only the kept
        rows is the same work the simple-graph builder below already does.

        WHAT MADE THIS NON-OBVIOUS, and why an earlier attempt of mine was
        wrongly refuted: networkx's ORDER here comes from two applications of
        the ``FilterAtlas`` rule, and they use different atlases.

          * NODE order: keep-set order when ``2 * len(keep) < len(G)``, else
            parent order.
          * INNER ROW order: keep-set order when ``2 * len(keep) < len(row)``,
            else parent row order — and this branch exists for multigraphs at
            all only because ``FilterMultiInner`` carries ``NODE_OK.nodes``,
            which a simple graph's ``FilterAtlas`` does not (br-r37-c1-9uod6).

        With a keep set of half the graph the row test is FALSE (rows are far
        shorter than the keep set) while with a small keep set it is TRUE, so
        both branches are live in ordinary use. Verified 0 order divergences
        over 72 cases spanning six keep fractions at three PYTHONHASHSEEDs.
        """
        parent = self._graph
        # MULTIGRAPH ONLY, and that is a measured decision rather than a
        # simplification. new/old wall clock, lower is better, two independent
        # runs at N=4000:
        #
        #     MultiGraph     frac 0.1  0.590 / 0.623
        #                    frac 0.5  0.652 / 0.574
        #                    frac 0.9  0.772 / 0.817     consistent 1.2-1.7x
        #
        #     MultiDiGraph   frac 0.5  faster in one run, 1.047 in the next
        #                    frac 0.8  0.904
        #                    frac 0.9  1.145  (SLOWER)
        #
        # MultiDiGraph's runs disagree in SIGN, so there is no reliable win to
        # take and one measured regression at a large keep set. Adopting it
        # there on the strength of a single favourable run is exactly the
        # mistake this file keeps recording. Left on the generic path.
        if type(parent) is not MultiGraph:
            return None
        if not self._filter_edge_is_default or not isinstance(
            self._filter_node, _NodeSetFilter
        ):
            return None
        if _has_networkx_private_storage(parent):
            return None
        if self._copy_type() is not type(parent):
            return None

        # Iterate the filter's OWN set, never a rebuilt one. networkx's
        # FilterAtlas iterates ``NODE_OK.nodes`` itself, and set ITERATION order
        # depends on insertion history — so ``{n for n in ...}`` produces the
        # same members in a different order and silently changes the result's
        # node order. A first draft of this did exactly that and diverged on 12
        # of 144 cases at two of three hash seeds while passing at the third.
        within = self._filter_node.nodes
        if 2 * len(within) < len(parent):
            ordered = [node for node in within if node in parent]
        else:
            ordered = [node for node in parent.nodes() if node in within]

        result = self._copy_type()()
        result.graph.update(dict(parent.graph))
        for node in ordered:
            result.add_node(node, **dict(_node_attrs_for_view_graph(parent, node)))
        directed = parent.is_directed()
        seen = set()
        for source in ordered:
            row = parent.succ[source] if directed else parent[source]
            candidates = within if 2 * len(within) < len(row) else row
            for target in candidates:
                if target not in within or target not in row:
                    continue
                if not directed and target in seen:
                    continue
                keydict = row[target]
                for edge_key in keydict:
                    result.add_edge(source, target, key=edge_key, **keydict[edge_key])
            # AFTER the row, so a self-loop still emits (br-r37-c1-6yimw).
            if not directed:
                seen.add(source)
        return result

    def _copy_induced_simple_fast(self):
        # br-r37-c1-esgfast: handle a non-default filter_edge too (e.g.
        # edge_subgraph) — apply the edge predicate directly in the
        # native raw_neighbors loop below instead of falling to the
        # O(parent) FilterAdjacency chain (~970k _node_visible calls).
        if self.is_multigraph():
            return self._copy_induced_multi_fast()
        if type(self._graph) not in (Graph, DiGraph):
            return None
        raw_neighbors = _raw_neighbors_dispatch(self._graph)
        if raw_neighbors is None:
            return None

        # br-r37-c1-indsub: fully native induced-subgraph materialization for
        # the pure node-set filter (``G.subgraph(nbunch).copy()``, and the whole
        # k_core/k_shell/k_crust/k_corona family). The Python builder below still
        # crosses the PyO3 boundary once per node (attr dict) and twice per EDGE
        # (get_edge_data + the add_edges_from tuple) — 395ms for the 158k-edge
        # k=10 core of ca-AstroPh. Hand Rust the resolved node order instead and
        # let it walk the adjacency itself.
        #
        # Only the O(|V|) ORDER is resolved here: nx's node order is CPython
        # set-iteration order whenever ``2 * len(keep) < len(G)`` (the common
        # case — a k-core keeps well under half the graph), and that is not
        # reproducible from Rust. The inner row order needs no such handoff,
        # since nx's ``FilterAdjacency.__getitem__`` wraps the row filter in a
        # plain closure with no ``.nodes`` attribute and so always iterates the
        # parent's row.
        if (
            self._filter_edge_is_default
            and isinstance(self._filter_node, _NodeSetFilter)
            # br-r37-c1-5cqc2: ...but only when the keep set is a large enough
            # share of the parent. The native kernel walks the whole parent, so
            # for a SMALL keep set it is far slower than the pure-Python builder
            # below, which touches only the kept nodes and their rows. Measured
            # fallback/native at N=8000, below 1.0 meaning the Python builder is
            # faster:
            #
            #     keep      10     100     400    1600    4000    7000
            #     Graph    0.050   0.206   0.565   1.235   2.295   1.678
            #     DiGraph  0.044   0.137   0.396   0.890   1.704   1.853
            #
            # so the crossover is around N/10 for Graph and N/3 for DiGraph.
            # N/10 is at or under both. Below it the whole call was O(parent):
            # G.subgraph(10).copy() measured 0.0093x (Graph) and 0.0043x
            # (DiGraph) against networkx at N=32000, and nx.ego_graph — which is
            # subgraph(...).copy() underneath — rounded to 0.000x on all four
            # classes. This gate does not change the k-core family the kernel was
            # written for: those keep well over a tenth of the graph.
            and not _induced_keep_is_small(self._filter_node.nodes, self._graph)
        ):
            native_induced = getattr(self._graph, "_native_induced_subgraph_copy", None)
            if native_induced is not None:
                order = self._induced_node_order(self._filter_node.nodes)
                if order is not None:
                    return native_induced(order)

        nodes = list(self)
        node_set = set(nodes)
        result = self._copy_type()()
        result.graph.update(dict(self.graph))
        node_rows = []
        node_attrs_empty = True
        int_nodes_only = True
        for node in nodes:
            if type(node) is not int or not -(1 << 63) <= node < (1 << 63):
                int_nodes_only = False
            attrs = dict(_node_attrs_for_view_graph(self._graph, node))
            if attrs:
                node_attrs_empty = False
            node_rows.append((node, attrs))
        if node_attrs_empty:
            fast_add_int_nodes = getattr(result, "_fast_add_int_nodes", None)
            if int_nodes_only and fast_add_int_nodes is not None:
                try:
                    fast_add_int_nodes(nodes)
                except (OverflowError, TypeError):
                    result.add_nodes_from(nodes)
            else:
                result.add_nodes_from(nodes)
        else:
            result.add_nodes_from(node_rows)

        edge_rows = []
        get_edge_data = self._graph.get_edge_data
        edge_default = self._filter_edge_is_default
        filter_edge = self._filter_edge
        if self.is_directed():
            for source in nodes:
                for target in raw_neighbors(self._graph, source):
                    if target in node_set and (
                        edge_default or filter_edge(source, target)
                    ):
                        edge_rows.append(
                            (source, target, dict(get_edge_data(source, target)))
                        )
        else:
            seen = set()
            for source in nodes:
                for target in raw_neighbors(self._graph, source):
                    if target in seen or target not in node_set:
                        continue
                    # Match the slow path's _edge_visible orientation
                    # exactly: it calls filter_edge(source, target) for
                    # the edge as iterated (single orientation). An OR
                    # over both would break exclusion filters like
                    # restricted_view.
                    if not edge_default and not filter_edge(source, target):
                        continue
                    edge_rows.append(
                        (source, target, dict(get_edge_data(source, target)))
                    )
                seen.add(source)
        result.add_edges_from(edge_rows)
        return result

    def to_directed_class(self):
        return MultiDiGraph if self.is_multigraph() else DiGraph

    def to_undirected_class(self):
        return MultiGraph if self.is_multigraph() else Graph

    def copy(self, as_view=False):
        if as_view is True:
            return _generic_filtered_graph_view(self)

        fast_copy = self._copy_induced_simple_fast()
        if fast_copy is not None:
            return fast_copy

        result = self._copy_type()()
        result.graph.update(dict(self.graph))
        result.add_nodes_from((node, dict(attrs)) for node, attrs in self.nodes(data=True))
        # br-r37-c1-edgesubcopy (cc): edge_subgraph views store their selected
        # edges on filter_edge. Iterating the filtered VIEW's edges() pays
        # per-edge view-wrapper overhead (41ms .copy() on a 2k-edge multigraph);
        # apply the same (set-lookup) filter_edge directly to the NATIVE parent
        # edges — same filter, same parent-iteration order => byte-identical
        # (0 fails across Graph/DiGraph/MultiGraph/MultiDiGraph), 135x faster on
        # the edge build. The node filter is implied by filter_edge here.
        _fe = getattr(self, "_filter_edge", None)
        _selected = getattr(_fe, "_fnx_edge_subgraph_selected_edges", None)
        if _selected is not None:
            parent = self._graph
            # br-r37-c1-vcopynb: scan only the ENDPOINTS the selection touches.
            # The whole-parent scan above is right when the selection is most of
            # the parent and O(parent) when it is three edges of 3200: copying a
            # four-node view cost 82us at a 200-node parent and 384us at 3200
            # (6.95x growth for an unchanged request) while networkx stayed flat
            # at ~31us, the ratio falling 0.4079x -> 0.2542x -> 0.0812x with no
            # floor. Restricting the scan to the selection's endpoints visits the
            # same nodes in the same sequence and merely skips nodes holding no
            # selected edge, so the emitted edge ORDER is unchanged - verified
            # against networkx over 4 classes x 3 parent sizes x 4 selection
            # sizes, 0 divergences including order. Guarded on endpoint count so
            # a selection spanning most of the parent keeps the whole-parent scan.
            _endpoints = None
            try:
                _endpoints = {n for e in _selected for n in e[:2]}
            except TypeError:
                _endpoints = None
            _use_nbunch = (
                _endpoints is not None
                and len(_endpoints) * 4 < parent.number_of_nodes()
            )
            if self.is_multigraph():
                _src = (
                    parent.edges(list(_endpoints), keys=True, data=True)
                    if _use_nbunch
                    else parent.edges(keys=True, data=True)
                )
                result.add_edges_from(
                    (u, v, key, dict(attrs))
                    for u, v, key, attrs in _src
                    if _fe(u, v, key)
                )
            else:
                _src = (
                    parent.edges(list(_endpoints), data=True)
                    if _use_nbunch
                    else parent.edges(data=True)
                )
                result.add_edges_from(
                    (u, v, dict(attrs)) for u, v, attrs in _src if _fe(u, v)
                )
            return result
        if self.is_multigraph():
            # 4-tuple shape avoids the ``key=key, **attrs`` collision when an
            # edge attribute is literally named "key" (franken_networkx-9x7r0).
            # br-edgekeyedbatch (bt): materialize as a LIST (not a generator) so the
            # native keyed edges-only batch engages (nodes were already added above,
            # so the graph is node-populated + edgeless) — the generator shape skips
            # the batch dispatch (`isinstance(ebunch, (list, tuple))`) and pays the
            # per-edge PyO3 loop (~0.46x vs nx on a MultiDiGraph subgraph copy).
            result.add_edges_from(
                [
                    (u, v, key, dict(attrs))
                    for u, v, key, attrs in self.edges(keys=True, data=True)
                ]
            )
        else:
            result.add_edges_from(
                (u, v, dict(attrs)) for u, v, attrs in self.edges(data=True)
            )
        return result

    def __reduce__(self):
        # br-r37-c1-fgv-pkl: the synthetic _FILTERED_GRAPH_VIEW_TYPES
        # subclasses are dynamically created at import time with names
        # that SHADOW the public Graph/DiGraph/etc. classes (same
        # __qualname__, same __module__) — pickle's qualname-based
        # lookup finds the public class, sees `lookup is not type(self)`
        # because the synthetic is a different class object, and
        # crashes with PicklingError("not the same object as
        # franken_networkx.Graph"). Snapshot the filtered view as a
        # real (non-view) graph copy at pickle time; restoration
        # reconstructs through the canonical class so the result is
        # independent of the original (matching nx, where unpickling
        # `pickle.dumps(G.subgraph(...))` returns a
        # plain Graph).
        return (_reconstruct_filtered_view_as_copy, (self.copy(),))

    def __copy__(self):
        # br-r37-c1-fgvcopy: nx's ``copy.copy(G.subgraph(...))``
        # returns a frozen Graph with the same content. fnx
        # inherited ``Graph.__copy__`` (= ``_graph_shallowcopy``)
        # which does ``type(self)()`` — fails for filtered-view
        # synthetics that require a graph argument.  Materialise via
        # ``self.copy()`` (canonical Graph) and freeze for nx parity.
        result = self.copy()
        try:
            from networkx import freeze as _nx_freeze
            return _nx_freeze(result)
        except Exception:
            return result

    def __deepcopy__(self, memo):
        # br-r37-c1-fgvcopy: nx's ``copy._deepcopy`` of a subgraph
        # also returns a frozen graph.  Freeze the deep-copied result.
        copied = _deepcopy(self.copy(), memo)
        memo[id(self)] = copied
        try:
            from networkx import freeze as _nx_freeze
            return _nx_freeze(copied)
        except Exception:
            return copied


_PRIVATE_NODE_OVERRIDE = "_fnx_private_node_override"
_PRIVATE_ADJ_OVERRIDE = "_fnx_private_adj_override"
_PRIVATE_SUCC_OVERRIDE = "_fnx_private_succ_override"
_PRIVATE_PRED_OVERRIDE = "_fnx_private_pred_override"
_PRIVATE_MISSING = object()

# br-r37-c1-s8obc: assigning ``g._node = {...}`` does NOT land in ``vars(g)`` —
# it is intercepted and stashed under ``_fnx_private_node_override``, with method
# shadows installed alongside it. Every copy path then skipped it, because they
# all skip ``key.startswith("_fnx_")``, so the clone silently reverted to the
# native store: ``'x' in g`` was True and ``'x' in copy.copy(g)`` was False.
# networkx has no such interception — the mapping lives in ``__dict__`` and rides
# along on the default copy protocol — so this was a real divergence.
#
# Re-apply through the PUBLIC name rather than copying the private key across.
# Assignment re-runs the installer, so the method shadows are rebuilt bound to
# the CLONE; copying ``_fnx_private_*`` directly would leave the clone carrying
# shadows still bound to the original graph.
_PRIVATE_OVERRIDE_PUBLIC_NAMES = (
    (_PRIVATE_NODE_OVERRIDE, "_node"),
    (_PRIVATE_ADJ_OVERRIDE, "_adj"),
    (_PRIVATE_SUCC_OVERRIDE, "_succ"),
    (_PRIVATE_PRED_OVERRIDE, "_pred"),
)
_SHARED_STORAGE_SOURCE = "_fnx_shared_storage_source"


def _shared_unsplit_owner(self, storage=None):
    """Return the shared storage owner when ``self`` is an un-split shallow copy."""
    if storage is None:
        storage = self.__dict__
    root = storage.get(_SHARED_STORAGE_SOURCE)
    if root is None:
        return None
    if (
        _PRIVATE_NODE_OVERRIDE in storage
        or _PRIVATE_ADJ_OVERRIDE in storage
        or _PRIVATE_SUCC_OVERRIDE in storage
        or _PRIVATE_PRED_OVERRIDE in storage
    ):
        return None
    root_storage = root.__dict__
    if (
        _PRIVATE_NODE_OVERRIDE in root_storage
        or _PRIVATE_ADJ_OVERRIDE in root_storage
        or _PRIVATE_SUCC_OVERRIDE in root_storage
        or _PRIVATE_PRED_OVERRIDE in root_storage
    ):
        return None
    return root


def _captured_private_overrides(graph):
    """Return {public_name: assigned_mapping} for each private store override."""
    storage = vars(graph)
    return {
        public: storage[key]
        for key, public in _PRIVATE_OVERRIDE_PUBLIC_NAMES
        if key in storage
    }


def _reapply_private_overrides(target, overrides):
    """Re-assign captured private stores onto ``target`` via the public names."""
    for public, value in overrides.items():
        try:
            setattr(target, public, value)
        except Exception:
            # A class that rejects the assignment keeps its native store; that is
            # strictly better than half-applying one of the four.
            pass


# br-r37-c1-l7ww9: no raw-slot captures for `__iter__`, `__len__` or
# `__contains__`. All three slots are private-storage aware in Rust, so nothing
# rebinds them and nothing needs to hold the original to call through.
_GRAPH_PRIVATE_AWARE_NODES = Graph.nodes
_DIGRAPH_PRIVATE_AWARE_NODES = DiGraph.nodes
_MULTIGRAPH_PRIVATE_AWARE_NODES = MultiGraph.nodes
_MULTIDIGRAPH_PRIVATE_AWARE_NODES = MultiDiGraph.nodes
_GRAPH_PRIVATE_AWARE_EDGES = Graph.edges
_DIGRAPH_PRIVATE_AWARE_EDGES = DiGraph.edges
_MULTIGRAPH_PRIVATE_AWARE_EDGES = MultiGraph.edges
_MULTIDIGRAPH_PRIVATE_AWARE_EDGES = MultiDiGraph.edges
_GRAPH_PRIVATE_AWARE_DEGREE = Graph.degree
_DIGRAPH_PRIVATE_AWARE_DEGREE = DiGraph.degree
_MULTIGRAPH_PRIVATE_AWARE_DEGREE = MultiGraph.degree
_MULTIDIGRAPH_PRIVATE_AWARE_DEGREE = MultiDiGraph.degree
_GRAPH_PRIVATE_AWARE_HAS_NODE = Graph.has_node
_DIGRAPH_PRIVATE_AWARE_HAS_NODE = DiGraph.has_node
_MULTIGRAPH_PRIVATE_AWARE_HAS_NODE = MultiGraph.has_node
_MULTIDIGRAPH_PRIVATE_AWARE_HAS_NODE = MultiDiGraph.has_node
_GRAPH_PRIVATE_AWARE_HAS_EDGE = Graph.has_edge
_DIGRAPH_PRIVATE_AWARE_HAS_EDGE = DiGraph.has_edge
_MULTIGRAPH_PRIVATE_AWARE_HAS_EDGE = MultiGraph.has_edge
_MULTIDIGRAPH_PRIVATE_AWARE_HAS_EDGE = MultiDiGraph.has_edge
_GRAPH_PRIVATE_AWARE_GET_EDGE_DATA = Graph.get_edge_data
_DIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA = DiGraph.get_edge_data
_MULTIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA = MultiGraph.get_edge_data
_MULTIDIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA = MultiDiGraph.get_edge_data
_GRAPH_PRIVATE_AWARE_NUMBER_OF_NODES = Graph.number_of_nodes
_DIGRAPH_PRIVATE_AWARE_NUMBER_OF_NODES = DiGraph.number_of_nodes
_MULTIGRAPH_PRIVATE_AWARE_NUMBER_OF_NODES = MultiGraph.number_of_nodes
_MULTIDIGRAPH_PRIVATE_AWARE_NUMBER_OF_NODES = MultiDiGraph.number_of_nodes
_GRAPH_PRIVATE_AWARE_NUMBER_OF_EDGES = Graph.number_of_edges
_DIGRAPH_PRIVATE_AWARE_NUMBER_OF_EDGES = DiGraph.number_of_edges
_MULTIGRAPH_PRIVATE_AWARE_NUMBER_OF_EDGES = MultiGraph.number_of_edges
_MULTIDIGRAPH_PRIVATE_AWARE_NUMBER_OF_EDGES = MultiDiGraph.number_of_edges
_GRAPH_PRIVATE_AWARE_NEIGHBORS = Graph.neighbors
_DIGRAPH_PRIVATE_AWARE_NEIGHBORS = DiGraph.neighbors
_DIGRAPH_PRIVATE_AWARE_SUCCESSORS = DiGraph.successors
_DIGRAPH_PRIVATE_AWARE_PREDECESSORS = DiGraph.predecessors
_MULTIGRAPH_PRIVATE_AWARE_NEIGHBORS = MultiGraph.neighbors
_MULTIDIGRAPH_PRIVATE_AWARE_NEIGHBORS = MultiDiGraph.neighbors
_MULTIDIGRAPH_PRIVATE_AWARE_SUCCESSORS = MultiDiGraph.successors
_MULTIDIGRAPH_PRIVATE_AWARE_PREDECESSORS = MultiDiGraph.predecessors


def _private_override(self, attr_name):
    return vars(self).get(attr_name, _PRIVATE_MISSING)


# br-r37-c1-wbwkb (cc): instance-dict key holding the set of PUBLIC accessor
# names that a cached non-data descriptor has memoised on this graph. The
# constant is defined beside the earlier class-predicate descriptor because a
# predicate can be read while the module is still initializing. Only tracked
# names may be invalidated when a private override lands — a subgraph view sets
# its OWN ``nodes`` instance attribute (``_FilteredGraphView.__init__``) that
# never went through the descriptor, and dropping that one would expose the
# bare ``_FilteredGraphView.nodes`` function as a bound method.
_PRIVATE_NODE_METHOD_SHADOWS = "_fnx_private_node_method_shadows"
# br-r37-c1-shwst: the predicate state the shadows above were installed FOR.
# The `_fnx_` prefix is load-bearing - the copy/deepcopy path at the top of
# this file skips every key with it, so this stays out of copies and pickles.
_PRIVATE_SHADOW_STATE = "_fnx_private_shadow_state"
_RAW_HAS_NODE_METHODS = (
    _GRAPH_PRIVATE_AWARE_HAS_NODE,
    _DIGRAPH_PRIVATE_AWARE_HAS_NODE,
    _MULTIGRAPH_PRIVATE_AWARE_HAS_NODE,
    _MULTIDIGRAPH_PRIVATE_AWARE_HAS_NODE,
)
_RAW_NUMBER_OF_NODES_METHODS = (
    _GRAPH_PRIVATE_AWARE_NUMBER_OF_NODES,
    _DIGRAPH_PRIVATE_AWARE_NUMBER_OF_NODES,
    _MULTIGRAPH_PRIVATE_AWARE_NUMBER_OF_NODES,
    _MULTIDIGRAPH_PRIVATE_AWARE_NUMBER_OF_NODES,
)
_RAW_HAS_EDGE_METHODS = (
    _GRAPH_PRIVATE_AWARE_HAS_EDGE,
    _DIGRAPH_PRIVATE_AWARE_HAS_EDGE,
    _MULTIGRAPH_PRIVATE_AWARE_HAS_EDGE,
    _MULTIDIGRAPH_PRIVATE_AWARE_HAS_EDGE,
)
_RAW_GET_EDGE_DATA_METHODS = (
    _GRAPH_PRIVATE_AWARE_GET_EDGE_DATA,
    _DIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA,
    _MULTIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA,
    _MULTIDIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA,
)
_RAW_DIGRAPH_NEIGHBOR_METHODS = (
    _DIGRAPH_NEIGHBORS,
    _DIGRAPH_SUCCESSORS,
    _fnx.MultiDiGraph._native_neighbors_iter,
)
_RAW_MULTIGRAPH_NEIGHBOR_METHODS = (_fnx.MultiGraph._native_neighbors_iter,)
_RAW_DIRECTED_PREDECESSOR_METHODS = (
    _fnx.DiGraph._native_predecessors_iter,
    _fnx.MultiDiGraph._native_predecessors_iter,
)


def _assigned_private_has_node(self, n):
    return n in self


def _assigned_private_number_of_nodes(self):
    return len(self)


def _private_native_method(graph, methods):
    """Find the inherited native writer for the unassigned half of storage."""
    for base in type(graph).__mro__:
        method = methods.get(base)
        if method is not None:
            return method
    return None


def _assigned_private_add_node(
    self, node_for_adding, *, _sync_native=True, _preserve_assigned_row=False, **attr
):
    """add_node for a graph carrying assigned private storage (br-r37-c1-wv3cu).

    networkx's storage IS the assigned mapping, so `add_node` edits it in place
    and the caller sees the change through their own reference. Measured: after
    `G._adj = assigned; G.add_edge('p','q')`, nx's `assigned` holds p and q while
    fnx's did not.

    fnx can have a SPLIT store — `G._adj = {...}` leaves `_node` native — so the
    two halves are written by their own routes rather than by copying networkx's
    body verbatim:

      * the native store gains the node through the raw method, which keeps
        `_node`, node_count and every native reader consistent;
      * each ASSIGNED mapping gains its own row, which is what makes the write
        visible to the reads br-r37-c1-vbe1o just corrected.

    Attribute semantics follow networkx: a NEW node takes `attr`, an existing one
    has `attr` merged into whatever it already carries.
    """
    if node_for_adding is None:
        raise ValueError("None cannot be a node")

    storage = vars(self)
    owner = _shared_unsplit_owner(self, storage)
    if owner is not None:
        raw = _RAW_ADD_NODE_BY_CLASS.get(type(owner))
        if raw is not None:
            return raw(owner, node_for_adding, **attr)
        return owner.add_node(node_for_adding, **attr)

    target = storage.get(_SHARED_STORAGE_SOURCE, self)
    # Record membership before the native call.  Graph.add_node decides whether
    # to replace an adjacency row from `_node`, not from `_adj`; an assigned
    # `_adj` can therefore contain a stale row for a node which is new to the
    # graph.  NetworkX replaces that row rather than merging it.
    known_to_node_store = node_for_adding in self._node
    raw = _private_native_method(target, _RAW_ADD_NODE_BY_CLASS)
    if _sync_native and raw is not None:
        raw(target, node_for_adding, **attr)

    node_map = storage.get(_PRIVATE_NODE_OVERRIDE)
    if node_map is not None:
        existing = node_map.get(node_for_adding)
        if existing is None:
            node_map[node_for_adding] = dict(attr)
        else:
            existing.update(attr)

    for key in (_PRIVATE_ADJ_OVERRIDE, _PRIVATE_SUCC_OVERRIDE, _PRIVATE_PRED_OVERRIDE):
        mapping = storage.get(key)
        if mapping is not None and (
            node_for_adding not in mapping
            or (not known_to_node_store and not _preserve_assigned_row)
        ):
            mapping[node_for_adding] = {}


# The CURRENT class attribute, not the pre-rebinding raw: `install()` tests the
# class's live method against this tuple to decide eligibility, and `add_node`
# has since been rebound by the None-rejecting wrapper. Passing the raw
# references made the shadow silently not install -- the mutation sweep stayed at
# 82 with the code present and unreachable.
_RAW_ADD_NODE_BY_CLASS = {
    Graph: Graph.add_node,
    DiGraph: DiGraph.add_node,
    MultiGraph: MultiGraph.add_node,
    MultiDiGraph: MultiDiGraph.add_node,
}

_RAW_ADD_NODE_METHODS = tuple(_RAW_ADD_NODE_BY_CLASS.values())


def _assigned_private_edge_targets(self, storage):
    """(forward, backward) assigned mappings an edge write must reach.

    Undirected: the same mapping twice, written u->v and v->u. Directed: the succ
    side forward and the pred side backward, either of which may be absent
    because fnx allows a partial assignment where networkx does not.
    """
    adj = storage.get(_PRIVATE_ADJ_OVERRIDE)
    if self.is_directed():
        succ = storage.get(_PRIVATE_SUCC_OVERRIDE)
        if succ is None:
            succ = adj
        return succ, storage.get(_PRIVATE_PRED_OVERRIDE)
    return adj, adj


def _assigned_private_edge_node_exists(self, node, storage):
    """Apply the membership authority used by NetworkX's ``add_edge`` body."""
    if not self.is_directed() and not self.is_multigraph():
        return node in self._node
    forward, _ = _assigned_private_edge_targets(self, storage)
    if forward is not None:
        return node in forward
    if self.is_directed():
        return node in self._succ
    return node in self._adj


def _assigned_private_prepare_edge_nodes(self, u, v, storage):
    """Prepare node rows without letting the native edge writer invent nodes.

    MultiGraph and directed ``add_edge`` test their adjacency mapping, whereas
    the native graph can be missing a node which exists only in an assigned
    mapping.  Calling the native edge method first then silently inserts that
    node into the native node store.  Graph instead tests ``_node`` and must
    replace a stale assigned adjacency row for a genuinely new node.
    """
    if (
        not self.is_directed()
        and not self.is_multigraph()
        and _PRIVATE_NODE_OVERRIDE in storage
    ):
        for node in (u, v):
            if node in self._node and node not in self._adj:
                # This is Graph.add_edge's direct ``self._adj[node]`` lookup
                # after its `_node` membership check; preserve its KeyError.
                raise KeyError(node)

    forward, _ = _assigned_private_edge_targets(self, storage)
    exists = {
        u: _assigned_private_edge_node_exists(self, u, storage),
        v: _assigned_private_edge_node_exists(self, v, storage),
    }
    # With an assigned adjacency, a node can exist there while being absent
    # from fnx's native `_node`.  The raw edge writer would create it natively,
    # which NetworkX does not do for these classes.  Keep this exceptional write
    # entirely on the assigned mapping; ordinary graphs continue through Rust.
    python_only = (
        forward is not None
        and (self.is_directed() or self.is_multigraph())
        and any(exists[node] and node not in self._node for node in (u, v))
    )
    for node in (u, v):
        _assigned_private_add_node(
            self,
            node,
            _sync_native=not (python_only and exists[node]),
            _preserve_assigned_row=python_only and exists[node],
        )
    return python_only


def _assigned_private_write_edge(self, u, v, key, attr, storage):
    """Put one edge into whichever assigned mappings this graph carries."""
    forward, backward = _assigned_private_edge_targets(self, storage)
    multi = self.is_multigraph()

    def row(mapping, node):
        existing = mapping.get(node)
        if existing is None:
            existing = mapping[node] = {}
        return existing

    if multi:
        # networkx keeps ONE keydict per (u, v) and shares the attr dict between
        # both directions of an undirected edge.
        fwd_keys = row(forward, u).setdefault(v, {}) if forward is not None else None
        datadict = None
        if fwd_keys is not None:
            datadict = fwd_keys.get(key)
            if datadict is None:
                datadict = fwd_keys[key] = {}
            datadict.update(attr)
        if backward is not None and (backward is not forward or u != v):
            back_keys = row(backward, v).setdefault(u, {})
            back_keys[key] = datadict if datadict is not None else dict(attr)
        return

    datadict = None
    if forward is not None:
        fwd_row = row(forward, u)
        datadict = fwd_row.get(v)
        if datadict is None:
            datadict = {}
        datadict.update(attr)
        fwd_row[v] = datadict
        row(forward, v)
    if backward is not None:
        back_row = row(backward, v)
        back_row[u] = datadict if datadict is not None else dict(attr)
        row(backward, u)


def _assigned_private_add_edge_simple(self, u_of_edge, v_of_edge, **attr):
    """add_edge for a graph carrying assigned private storage (br-r37-c1-wv3cu)."""
    storage = vars(self)
    owner = _shared_unsplit_owner(self, storage)
    if owner is not None:
        raw = _RAW_ADD_EDGE_BY_CLASS.get(type(owner))
        if raw is not None:
            return raw(owner, u_of_edge, v_of_edge, **attr)
        return owner.add_edge(u_of_edge, v_of_edge, **attr)
    target = storage.get(_SHARED_STORAGE_SOURCE, self)
    python_only = _assigned_private_prepare_edge_nodes(self, u_of_edge, v_of_edge, storage)
    raw = _private_native_method(target, _RAW_ADD_EDGE_BY_CLASS)
    if not python_only and raw is not None:
        raw(target, u_of_edge, v_of_edge, **attr)
    _assigned_private_write_edge(self, u_of_edge, v_of_edge, None, attr, storage)


def _assigned_private_add_edge_multi(self, u_of_edge, v_of_edge, key=None, **attr):
    """Multigraph add_edge: the key is part of the address, not an attribute."""
    storage = vars(self)
    owner = _shared_unsplit_owner(self, storage)
    if owner is not None:
        raw = _RAW_ADD_EDGE_BY_CLASS.get(type(owner))
        if raw is not None:
            if key is None:
                return raw(owner, u_of_edge, v_of_edge, **attr)
            return raw(owner, u_of_edge, v_of_edge, key, **attr)
        if key is None:
            return owner.add_edge(u_of_edge, v_of_edge, **attr)
        return owner.add_edge(u_of_edge, v_of_edge, key, **attr)
    target = storage.get(_SHARED_STORAGE_SOURCE, self)
    python_only = _assigned_private_prepare_edge_nodes(self, u_of_edge, v_of_edge, storage)
    raw = _private_native_method(target, _RAW_ADD_EDGE_BY_CLASS)
    if not python_only and raw is not None:
        if key is None:
            key = raw(target, u_of_edge, v_of_edge, **attr)
        else:
            raw(target, u_of_edge, v_of_edge, key, **attr)
    elif key is None:
        forward, _ = _assigned_private_edge_targets(self, storage)
        keydict = forward.get(u_of_edge, {}).get(v_of_edge, {}) if forward else {}
        key = len(keydict)
        while key in keydict:
            key += 1
    _assigned_private_write_edge(self, u_of_edge, v_of_edge, key, attr, storage)
    return key


def _assigned_private_add_nodes_from(self, nodes_for_adding, **attr):
    """networkx delegates this to add_node; fnx's native batch does not.

    That asymmetry is why the sweep showed add_node fixed while add_nodes_from
    still diverged — the batch kernel never reached the corrected path.
    """
    owner = _shared_unsplit_owner(self)
    if owner is not None:
        raw = _RAW_ADD_NODES_FROM_BY_CLASS.get(type(owner))
        if raw is not None:
            return raw(owner, nodes_for_adding, **attr)
        return owner.add_nodes_from(nodes_for_adding, **attr)
    for node in nodes_for_adding:
        if isinstance(node, tuple) and len(node) == 2 and isinstance(node[1], dict):
            name, node_attr = node
            merged = dict(attr)
            merged.update(node_attr)
            _assigned_private_add_node(self, name, **merged)
        else:
            _assigned_private_add_node(self, node, **attr)
