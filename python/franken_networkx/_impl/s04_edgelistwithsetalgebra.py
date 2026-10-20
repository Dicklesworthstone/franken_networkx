

class _EdgeListWithSetAlgebra(list):
    """List subclass that supports set-algebra operators.

    br-r37-c1-ih59i: it also carries `__repr__`, because inheriting
    `list.__repr__` printed these views as bare list syntax where networkx
    prints `ClassName([...])` — visible on any `print()` or log of a view, and
    on all three classes whose data views subclass this one. Simple `Graph` was
    already correct because its `EdgeDataView` is an `object` subclass rather
    than a list, which is what identified this as the defect rather than the
    convention.

    Returned by MultiGraph.edges(keys=...) / MultiDiGraph.edges(keys=...)
    so the result matches upstream NetworkX's set-like behaviour
    (expressions like edges | {...}, edges & {...}, edges == set) without
    breaking existing callers that iterate the value as a list.

    br-r37-c1-af0ig: it is also a LIVE view. The contents are materialised
    eagerly (so that argument errors still raise at call time, as nx's do),
    but every read first checks the graph's revision token and re-materialises
    if the graph has moved on. Without that, a view bound before a mutation
    served deleted edges and hid added ones — networkx's views are live, and
    fnx's own Graph.edges(...) already was, via the object-based EdgeDataView.
    """

    # br-r37-c1-5pjt3: CLASS-LEVEL DEFAULTS for every optional `_fnx_` slot, so
    # the reads below can be ordinary attribute lookups instead of
    # `getattr(self, name, None)`. Counted by wrapping `builtins.getattr` around
    # one warm `list(G.edges(["n1"]))`: 19 of the 27 getattr calls on MultiGraph
    # and MultiDiGraph, and 9 of 15 on DiGraph, were this idiom. Priced at 24.0
    # ns/site against 8.5 ns/site for a class-default lookup with the attribute
    # PRESENT - the usual case here - so the idiom was costing about 15.5 ns
    # each, ~295 ns of MultiGraph's 6517 ns call.
    #
    # A DEFAULT IS NOT A NO-OP FOR `hasattr`. `_live_called_edge_view` used to
    # ask `if not hasattr(result, "_fnx_token")`, which a class default makes
    # permanently True; that branch is now an `is None` test. Anything else that
    # probes these names with `hasattr`, `vars()` or `__dict__` has to know that
    # an unset slot still answers from the class - `vars()` does NOT show it.
    _fnx_live_graph = None
    _fnx_guard_graph = None
    _fnx_guard_edge_count = False
    _fnx_nbunch_rows = None
    _fnx_token = None
    _fnx_rebuild = None
    _fnx_lazy_rows = None
    _fnx_len_hint = None
    _fnx_frozen_nbunch = None
    _fnx_contains_call = None
    _fnx_contains_spec = None
    # br-r37-c1-p1tyz: True for a data=<key> view, whose rows hold attribute
    # VALUES - an attribute write moves no revision token, so such a view is
    # re-read on every access instead of only when the structure changed.
    _fnx_holds_values = False
    _fnx_attr_epoch = None
    _fnx_read_once = False

    def _fnx_membership_spec(self):
        """br-r37-c1-ex1s6: the _called_edge_view_spec of the call that made
        this view, built once; False when there is none (a list handed to
        _guarded_edge_list directly, a call networkx's signature does not
        describe)."""
        spec = self._fnx_contains_spec
        if spec is None:
            call = self._fnx_contains_call
            spec = (None if call is None else _called_edge_view_spec(*call)) or False
            self._fnx_contains_spec = spec
        return spec

    def _fnx_take_len_hint(self):
        """True when a len() call immediately preceded this iteration."""
        hint = self._fnx_len_hint
        if hint is None:
            return False
        self._fnx_len_hint = None
        # br-r37-c1-ORTRUTH: `is None`, never `or` — the same rule _fnx_refresh
        # states three lines below. An EMPTY graph is FALSY, so `or` silently
        # discards a live graph that has been cleared and falls through to the
        # guard graph (or to None), which is precisely the mutation
        # br-r37-c1-af0ig was filed for. That bead fixed the refresh path and
        # left this sibling on `or`.
        #
        # HONESTLY SCOPED: I could NOT reach the divergent state through the
        # public API. On the paths I exercised neither attribute is set, so the
        # expression returns None either way and the two forms agree. This is a
        # consistency fix that removes a latent trap, not a demonstrated bug —
        # the unit test below drives the helper directly because that is the
        # only way I could distinguish the two forms.
        graph = self._fnx_live_graph
        if graph is None:
            graph = self._fnx_guard_graph
        return graph is not None and hint == _edge_list_freshness_token(graph)

    def _fnx_walk_live_rows(self, spec):
        """br-r37-c1-u5tyh: yield out of the LIVE adjacency rows.

        networkx captures ``[(n, adjdict[n]) for n in nbunch]`` once and walks
        those row dicts, so its mutate-during-iteration behaviour is whatever
        CPython says about the dict under iteration. Reproducing that means
        walking the same objects, not guarding a materialised copy.

        Directed out-edges are NOT deduplicated by the second endpoint — that
        dedup belongs to the undirected view only.
        """
        row_kind, nbunch, data = spec
        graph = self._fnx_live_graph
        if graph is None:
            return None
        rows = []
        for node in nbunch:
            row = _cached_adj_row_keydict(
                graph, row_kind, node, lambda: getattr(graph, row_kind)[node]
            )
            if row is None:
                return None
            rows.append((node, row))

        def _walk():
            for node, row in rows:
                for nbr, edge_data in row.items():
                    yield (node, nbr, edge_data) if data else (node, nbr)

        return _walk()

    def _fnx_refresh(self, values=True):
        """Re-materialise if the graph has changed since this was built.

        Costs one attribute read and a tuple compare when nothing has changed,
        which is the overwhelmingly common case (build a view, read it once).
        A view with no rebuild thunk — one handed straight to
        ``_guarded_edge_list`` rather than produced through a decorated
        ``__call__`` — keeps its old snapshot behaviour rather than guessing.
        """
        rebuild = self._fnx_rebuild
        if rebuild is None:
            return
        # `is None`, never `or`: an EMPTY graph is falsy, so `or` silently
        # skipped the refresh for exactly the mutation that empties one —
        # G.clear() — which is the case that most needs it.
        graph = self._fnx_live_graph
        if graph is None:
            graph = self._fnx_guard_graph
        if graph is None:
            return
        token = _edge_list_freshness_token(graph)
        moved = token is not None and token != self._fnx_token
        if not moved:
            if not (values and self._fnx_holds_values):
                return
            attr_epoch = _edge_attr_freshness_token(graph)
            if (
                not self._fnx_read_once
                and attr_epoch is not None
                and attr_epoch == self._fnx_attr_epoch
            ):
                self._fnx_read_once = True
                return
        # br-r37-c1-2pia7: the graph moved — if it moved by removing one of the
        # nodes this view's nbunch was resolved to, nx raises rather than
        # answering with the survivors. Checked only on a token change, so an
        # unchanged graph pays nothing.
        frozen = self._fnx_frozen_nbunch
        if moved and frozen is not None:
            for node in frozen:
                if node not in graph:
                    raise KeyError(node)
        fresh = rebuild()
        # list.__iter__ / list.__getitem__ deliberately: the rebuilt object is
        # itself a live view, and going through its own __iter__ would re-enter
        # this machinery (and its fail-fast guard) for no reason.
        list.__setitem__(self, slice(None), list(list.__iter__(fresh)))
        self._fnx_token = token
        if self._fnx_holds_values:
            self._fnx_attr_epoch = _edge_attr_freshness_token(graph)
            self._fnx_read_once = True

    def _fnx_project_live_values(self, base_iter):
        spec = self._fnx_membership_spec()
        if not spec:
            return base_iter
        graph, _kind, multi, data, default, keys, _nodes, _view_form = spec

        def _project():
            if self._fnx_take_len_hint():
                yield from base_iter
                return
            if not multi:
                for u, v, val in base_iter:
                    dd = graph.get_edge_data(u, v)
                    if isinstance(dd, _Mapping):
                        val = dd.get(data, default)
                    yield (u, v, val)
            elif keys:
                for u, v, k, val in base_iter:
                    dd = graph.get_edge_data(u, v, k)
                    if isinstance(dd, _Mapping):
                        val = dd.get(data, default)
                    yield (u, v, k, val)
            else:
                pair_offsets = {}
                for u, v, val in base_iter:
                    idx = pair_offsets.get((u, v), 0)
                    pair_offsets[(u, v)] = idx + 1
                    kd = graph.get_edge_data(u, v)
                    if isinstance(kd, _Mapping) and idx < len(kd):
                        dd = list(kd.values())[idx]
                        if isinstance(dd, _Mapping):
                            val = dd.get(data, default)
                    yield (u, v, val)

        return _project()

    def __iter__(self):
        # br-r37-c1-u5tyh: a `list(view)` asks for the length first and nothing
        # can run in between, so it keeps the materialised contents. An
        # explicit `for e in view:` CAN interleave user code, and that is where
        # networkx's semantics live — walk the live rows and let CPython supply
        # them, exactly as the Graph path does.
        len_hint = self._fnx_take_len_hint()
        spec = self._fnx_lazy_rows
        if spec is not None and not len_hint:
            walk = self._fnx_walk_live_rows(spec)
            if walk is not None:
                return walk
        self._fnx_refresh()
        graph = self._fnx_guard_graph
        if graph is None:
            base_iter = list.__iter__(self)
            if not len_hint and self._fnx_holds_values:
                return self._fnx_project_live_values(base_iter)
            return base_iter
        guard_edge_count = self._fnx_guard_edge_count
        nbunch_rows = self._fnx_nbunch_rows
        # br-r37-c1-hihrf: the native guarded iterator carries the coarse
        # "anything changed" rule in Rust. An nbunch view needs networkx's row
        # rule, so it takes the Python guard - the same one simple Graph's
        # EdgeDataView already uses, which is why that class was already
        # faithful. Non-nbunch iteration is untouched and keeps the native path.
        if (
            nbunch_rows is None
            and guard_edge_count
            and not _has_networkx_private_storage(graph)
            and (len_hint or not self._fnx_holds_values)
        ):
            native_iter = getattr(graph, "_native_guarded_edge_list_iter", None)
            if native_iter is not None:
                return native_iter(self)
        guarded = _FailFastEdgeIterator(
            graph,
            list.__iter__(self),
            guard_edge_count=guard_edge_count,
            nbunch_rows=nbunch_rows,
            # br-r37-c1-8c7m5: unconditionally True, was `graph.is_multigraph()`.
            # A DETACHED ROW IS NOT AN EMPTY ROW on any class: `G.clear()`
            # empties the outer adjacency dict and `remove_node` deletes one
            # entry, neither touches the row dicts, and networkx is holding
            # those objects — so it drains their pre-mutation contents whether
            # the graph is a multigraph or not. The multigraph test was the
            # scope of the bead that introduced it, not a property of the rule;
            # measured, widening it fixes DiGraph `edges(nb, data=<key>)`
            # raising RuntimeError after a clear where nx completes, and moves
            # nothing else.
            ignore_removed_nbunch_row=True,
            refresh_rows=self._fnx_rematerialise_rows,
            initial_rows=self,
        )
        if not len_hint and self._fnx_holds_values:
            return self._fnx_project_live_values(guarded)
        return guarded

    def _fnx_rematerialise_rows(self):
        """br-r37-c1-u5tyh: rebuild this view's contents mid-iteration.

        Handed to the nbunch guard, which calls it ONLY after it has seen the
        graph move and decided the move is not one networkx raises for. At that
        point networkx is still walking, and still walking the graph's own row
        dicts, so its remaining answer reflects the mutation and this view's
        pre-built list does not.

        Returns None when there is no rebuild thunk (a list handed straight to
        `_guarded_edge_list` rather than produced through a decorated `__call__`)
        or when rebuilding raises, so the caller keeps the previous behaviour
        rather than guessing. In particular a node the view's nbunch named may
        have been removed, which nx reports by raising from `adjdict[n]` — that
        is `_fnx_refresh`'s job on the next read, not this one's.
        """
        rebuild = self._fnx_rebuild
        if rebuild is None:
            return None
        try:
            return list(list.__iter__(rebuild()))
        except Exception:  # noqa: BLE001 - an unrebuildable view keeps its list
            return None

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

    def __eq__(self, other):
        # br-mgedgeeq: nx's MultiEdgeView inherits from _Set, so
        # `MG.edges(keys=True) == {...}` compares as sets. fnx's list
        # subclass previously required another list for equality.
        self._fnx_refresh()
        if isinstance(other, (set, frozenset)):
            return set(self) == other
        return list.__eq__(self, other)

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq

    # br-r37-c1-af0ig: the remaining read paths. The set-algebra operators
    # above already refresh, because every one of them goes through
    # ``set(self)`` and therefore ``__iter__``. These five reach list's C
    # slots directly, so they would otherwise answer from the stale buffer —
    # ``len(view)`` in particular, which is how most callers size a view.
    def __len__(self):
        # A count does not read values, so only a structural move rebuilds here.
        self._fnx_refresh(values=False)
        if self._fnx_lazy_rows is not None or self._fnx_holds_values:
            graph = self._fnx_live_graph
            if graph is None:
                graph = self._fnx_guard_graph
            if graph is not None:
                self._fnx_len_hint = _edge_list_freshness_token(graph)
        return list.__len__(self)

    def __contains__(self, item):
        # br-r37-c1-ex1s6: a view from a call answers as networkx's does, by
        # a row lookup (_called_edge_view_contains), not by scanning the list.
        spec = self._fnx_membership_spec()
        if spec:
            return _called_edge_view_contains(spec, item)
        self._fnx_refresh()
        return list.__contains__(self, item)

    # NO __getitem__ REFRESH, deliberately and measured. Defining __getitem__
    # on a list subclass takes the native guarded-edge iterator off the
    # C-level list protocol and routes every element through a Python call:
    # list(DiGraph.edges(data=True)) on 4k edges went 0.167ms -> 2.20ms, a 13x
    # regression on the library's hottest accessor, for a method networkx does
    # not even support (nx's data views raise TypeError on subscripting, so
    # `v[0]` is fnx-only surface with nothing to be in parity with).
    #
    # The consequence, stated plainly: `v[0]` can hand back an element from
    # before a mutation while `list(v)`, `len(v)`, `in` and `repr(v)` are all
    # live. Indexing one of these views straddling a mutation is outside both
    # nx's API and any in-tree caller.

    def __repr__(self):
        # br-r37-c1-ih59i: print like networkx — `ClassName([...])` — instead of
        # the bare `[...]` that `list.__repr__` gives. The refresh below is
        # unchanged and still runs first: these are LIVE views, so a repr must
        # reflect the current graph.
        #
        # Simple `Graph` was already correct because its `EdgeDataView` is an
        # `object` subclass rather than a list, which is what identified this as
        # a defect in the list-backed views rather than a house convention.
        #
        # GUARDED ON A PUBLIC NAME, deliberately. `MultiGraph.edges(nbunch)` and
        # `MultiDiGraph.edges(nbunch)` still hand back this BASE class rather
        # than a canonically-named subclass, so `type(self).__name__` there is
        # the private `_EdgeListWithSetAlgebra`. Printing that would leak an
        # internal class into user-visible output — worse than the bare list it
        # replaces — so those keep the list form until the class-name half of
        # this bead is fixed. The shapes whose class is already canonically
        # named gain networkx's exact repr.
        self._fnx_refresh()
        name = type(self).__name__
        if name.startswith("_"):
            return list.__repr__(self)
        return f"{name}({list.__repr__(self)})"

    def __str__(self):
        self._fnx_refresh()
        return list.__str__(self)

    def __reduce__(self):
        # br-r37-c1-af0ig: the liveness machinery is a closure over the graph
        # and the call arguments, and none of that is picklable — a list
        # subclass otherwise pickles its instance __dict__ and takes the
        # rebuild lambda with it, which broke the round-trip locked by
        # br-r37-c1-edv-pkl. Pickle a refreshed, DETACHED snapshot: the graph
        # does not travel with the view, so a restored view has nothing to be
        # live against, which is what it was before this class became live.
        self._fnx_refresh()
        return (type(self), (list(list.__iter__(self)),))

    __hash__ = None


def _multigraph_edges(self):
    return _MultiGraphEdgeView(self)


class _MultiDiGraphEdgeView(_fnx.MultiDiGraphEdgeView):
    _fnx_edge_kind = "out"  # br-r37-c1-ex1s6: see _nx_edge_view_contains

    def __init__(self, graph):
        self._graph = graph

    def __getnewargs__(self):
        return (self._graph,)

    def __iter__(self):
        # br-multiiterkeys: see _MultiGraphEdgeView — default iteration
        # yields 3-tuples ``(u, v, key)`` matching nx.MultiEdgeView's
        # default iter contract; the ``G.edges()`` call form still
        # defaults to 2-tuples via the keys=False default.
        # br-r37-c1-c5zn8: directed sibling of the private direct-iteration
        # materialization above.
        return _direct_multi_edge_iter(self, MultiDiGraph)

    def __len__(self):
        return self._graph.number_of_edges()

    def __contains__(self, edge):
        # br-r37-c1-edgeviewcontains: see _MultiGraphEdgeView.__contains__.
        # nx's OutMultiEdgeView accepts any 2- or 3-element iterable; the
        # previous ``isinstance(edge, tuple)`` guard rejected lists.
        try:
            N = len(edge)
        except TypeError:
            raise
        # br-r37-c1-6fs77: a 2-element spec means key ZERO — see the undirected
        # twin. nx's ``k = 0`` default is not "any key".
        # br-r37-c1-ki2ni: UNPACK, do not subscript. networkx's
        # MultiEdgeView.__contains__ does `u, v, k = e`, and indexing here was a
        # real divergence as well as slower: a 3-element SET is Sized but not
        # subscriptable, so `{'a','b',0} in M.edges` raised
        # `TypeError: 'set' object is not subscriptable` where networkx unpacks
        # it and answers False. One UNPACK_SEQUENCE also replaces three
        # BINARY_SUBSCR on the hot path, which matters because the wrapper — not
        # the lookup — is the cost here: measured 503.3ns for `t in M.edges`
        # against 261.7ns for the bound `has_edge` underneath it, i.e. 241.6ns of
        # Python, where networkx's own wrapper is 34.9ns.
        if N == 3:
            u, v, key = edge
        elif N == 2:
            u, v = edge
            key = 0
        else:
            raise ValueError("MultiEdge must have length 2 or 3")
        # br-r37-c1-6fs77 perf half: see the undirected twin. `has_edge` is
        # oriented on a directed multigraph, so it answers this directly.
        # br-r37-c1-lvlu7: TypeError is NOT caught — see the undirected twin.
        # br-r37-c1-ki2ni: unreachable private-storage walk removed — see the
        # undirected twin. Assigning `_adj` / `_node` / `_succ` / `_pred` swaps
        # `G.edges` for `_AssignedPrivateEdgeView`, so an `OutMultiEdgeView`
        # only ever exists on a graph with no private storage and the
        # `_has_networkx_private_storage` probe could never be True here.
        try:
            return self._graph.has_edge(u, v, key)
        except KeyError:
            return False
        except TypeError:
            # br-r37-c1-ex1s6: see the undirected twin - an unhashable key
            # against a pair that is not there is False.
            if self._graph.has_edge(u, v):
                raise
            return False

    def __call__(self, nbunch=None, data=False, keys=False, default=None):
        # br-r37-c1-msf5j: live wrapper for default args (see
        # _MultiGraphEdgeView.__call__).
        if nbunch is None and data is False and keys is False:
            return _OutMultiEdgeDataCallView(self._graph, directed=True)
        if (
            nbunch is None
            and data is False
            and keys is True
            and type(self._graph) is MultiDiGraph
            and not _has_networkx_private_storage(self._graph)
        ):
            return self
        # br-r37-c1-tmuly: build the edge list from the native MultiDiGraphEdgeView
        # (iterates inner.edges_ordered() in nx order, reusing the live edge attr
        # dicts) instead of the pure-Python triple-loop over succ[source].items()
        # — the latter walks the MultiAdjacencyView lambda chain per element
        # (~3000-7000x slower than nx). The native view only understands
        # data in {False, True, <str attr>} (parse_view_data); `data=None` (an
        # explicit attr name None) and other non-str hashable attr names keep the
        # br-r37-c1-mdgoutedge (cc): directed edges() == out_edges() — route the
        # iterable-nbunch data=False/True case to the dominating out_edges kernels
        # (the _native_edge_view nbunch path is only ~0.66-0.89x). No-build reuse.
        _it_nb = nbunch is not None and _nbunch_is_iterable_bunch(
            self._graph, nbunch
        )
        if _it_nb and (data is False or data is True):
            kname = (
                "_native_mdg_out_edges_nbunch_data"
                if data is True
                else "_native_mdg_out_edges_nbunch_no_data"
            )
            native = getattr(self._graph, kname, None)
            if native is not None:
                try:
                    if data is True:
                        native_res = _digraph_out_edges_data_cache(
                            self._graph, nbunch, native, keys
                        )
                    else:
                        native_res = _nbunch_data_cache(
                            self._graph, "_fnx_mdg_out_edges_nb_nodata_cache",
                            nbunch, native, keys,
                        )
                except TypeError as exc:
                    raise NetworkXError(str(exc))
                if native_res is not None:
                    nres = _EdgeListWithSetAlgebra(native_res)
                    if data is not False:
                        return _guarded_edge_list(
                            _wrap_edge_data_view(nres, _OutMultiEdgeDataView),
                            self._graph,
                            guard_edge_count=True,
                            nbunch_rows=_resolved_nbunch_rows(self._graph, nbunch),
                        )
                    if keys:
                        # br-r37-c1-mdgoutedge (cc): keys=True (data=False) wraps in
                        # the canonical _OutMultiEdgesKeysView (a list-wrapper) — NOT
                        # _OutMultiEdgeView (a _DiEdgeMethodView needing (graph,method),
                        # which raised TypeError once the keys=True kernel un-gated).
                        # br-r37-c1-hihrf: with an nbunch nx serves this from
                        # OutMultiEdgeDataView, whose containment differs.
                        return _guarded_edge_list(
                            _wrap_edge_data_view(nres, _OutMultiEdgeDataKeysView),
                            self._graph,
                            guard_edge_count=True,
                            nbunch_rows=_resolved_nbunch_rows(self._graph, nbunch),
                        )
                    # br-r37-c1-hihrf: nx names this OutMultiEdgeDataView. THIS
                    # is the live return for `MDG.edges(nbunch)` - the native
                    # no-data fast path - and it handed back an unnamed list.
                    return _guarded_edge_list(
                        _wrap_edge_data_view(nres, _OutMultiEdgeDataView),
                        self._graph,
                        guard_edge_count=True,
                        nbunch_rows=_resolved_nbunch_rows(self._graph, nbunch),
                    )
        if _it_nb and data is not False and data is not True and not keys:
            native = getattr(self._graph, "_native_mdg_out_edges_nbunch_data_key", None)
            if native is not None:
                try:
                    # br-r37-c1-outedgesnbattr (cc): native now takes a keys arg (False here).
                    # br-r37-c1-p1tyz: values are not memoized (they go stale).
                    native_res = native(nbunch, data, default, keys)
                except TypeError as exc:
                    raise NetworkXError(str(exc))
                if native_res is not None:
                    result = _EdgeListWithSetAlgebra(native_res)
                    return _guarded_edge_list(
                        _wrap_edge_data_view(result, _OutMultiEdgeDataView),
                        self._graph,
                        guard_edge_count=True,
                        nbunch_rows=_resolved_nbunch_rows(self._graph, nbunch),
                    )
        result = _EdgeListWithSetAlgebra()
        if data is False or data is True or isinstance(data, str):
            native_list = (
                getattr(self._graph, "_native_edge_view_list", None)
                if nbunch is None
                else None
            )
            if native_list is not None:
                result = _EdgeListWithSetAlgebra(native_list(data, keys, default))
            else:
                result.extend(
                    self._graph._native_edge_view()(nbunch, data, keys, default)
                )
        else:
            for source in self._graph.nbunch_iter(nbunch):
                for target, keyed_attrs in self._graph.succ[source].items():
                    for key, attrs in keyed_attrs.items():
                        if keys:
                            result.append(
                                (source, target, key, attrs.get(data, default))
                            )
                        else:
                            result.append((source, target, attrs.get(data, default)))
        # br-r37-c1-mgcall (cycle 213): see _MultiGraphEdgeView.__call__
        # — wrap in OutMultiEdgeDataView when data is requested so
        # ``type(MDG.edges(data=True)).__name__`` matches nx.
        if data is not False:
            return _guarded_edge_list(
                _wrap_edge_data_view(result, _OutMultiEdgeDataView),
                self._graph,
                guard_edge_count=True,
                nbunch_rows=(
                    _resolved_nbunch_rows(self._graph, nbunch)
                ),
            )
        # br-r37-c1-mekvc (cycle 214): keys=True (data=False) wraps
        # in canonical ``OutMultiEdgeView`` so both
        # ``type(view).__name__`` and ``(u, v) in view`` match nx.
        #
        # br-r37-c1-hihrf: left alone for the same reason as the undirected
        # twin - the wrapper carries containment semantics that nx decides
        # differently for this spelling, so the name cannot move on its own.
        if keys:
            return _guarded_edge_list(
                _wrap_edge_data_view(result, _OutMultiEdgesKeysView),
                self._graph,
                guard_edge_count=True,
                nbunch_rows=(
                    _resolved_nbunch_rows(self._graph, nbunch)
                ),
            )
        # br-r37-c1-hihrf: nx names this OutMultiEdgeDataView; fnx returned a
        # bare list. Pure naming, as in the undirected twin.
        return _guarded_edge_list(
            _wrap_edge_data_view(result, _OutMultiEdgeDataView),
            self._graph,
            guard_edge_count=True,
            nbunch_rows=(
                _resolved_nbunch_rows(self._graph, nbunch)
            ),
        )

    keys = _multi_edge_keys
    items = _multi_edge_items
    values = _multi_edge_values
    get = _multi_edge_get

    def __eq__(self, other):
        # br-r37-c1-eveq: see _DiGraphEdgeView.__eq__.
        from collections.abc import Set as _Set
        if isinstance(other, _MultiDiGraphEdgeView):
            return set(self) == set(other)
        if isinstance(other, _Set):
            return set(self) == set(other)
        return NotImplemented

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq

    # br-r37-c1-viewhash: nx's OutEdgeView / MultiEdgeView /
    # OutMultiEdgeView all inherit from ``collections.abc.Mapping``
    # (``__hash__ = None``), so ``hash(G.edges)`` raises TypeError.
    # fnx previously returned ``id(self._graph)`` here, silently
    # accepting the view as hashable — diverging on a contract that
    # drop-in callers rely on (``except TypeError: ...`` around
    # accidental view-in-set patterns).
    __hash__ = None

    # br-r37-c1-iev-setops: see _DiEdgeMethodView. _Set comparison +
    # algebra operators for nx parity.
    def __le__(self, other):
        return set(self) <= set(other) if hasattr(other, "__iter__") else NotImplemented

    def __lt__(self, other):
        return set(self) < set(other) if hasattr(other, "__iter__") else NotImplemented

    def __ge__(self, other):
        return set(self) >= set(other) if hasattr(other, "__iter__") else NotImplemented

    def __gt__(self, other):
        return set(self) > set(other) if hasattr(other, "__iter__") else NotImplemented

    def isdisjoint(self, other):
        return set(self).isdisjoint(other)

    def __and__(self, other):
        return set(self) & set(other)

    def __or__(self, other):
        return set(self) | set(other)

    def __sub__(self, other):
        return set(self) - set(other)

    def __xor__(self, other):
        return set(self) ^ set(other)

    # Reflected forms: see _MultiGraphEdgeView (networkx's OutMultiEdgeView is a
    # collections.abc.Set, so ``set & MDG.edges(keys=True)`` must work).
    __rand__ = __and__
    __ror__ = __or__
    __rxor__ = __xor__

    def __rsub__(self, other):
        return set(other) - set(self)


def _multidigraph_edges(self):
    return _MultiDiGraphEdgeView(self)


def _simple_graph_adjacency(self):
    owner = _shared_unsplit_owner(self)
    if owner is not None:
        return _simple_graph_adjacency(owner)
    # br-r37-c1-vbe1o: a graph carrying ASSIGNED private storage yields that
    # mapping's rows, exactly as networkx does (`iter(self._adj.items())`). The
    # native paths below read the Rust store and cannot see it, and the final
    # fallback iterates the node view, so a node carried only by an assigned
    # `_adj` never appeared at all.
    #
    # The PRIVATE `_adj` on purpose: the public `adj` is now a read-only view,
    # and networkx hands out the live raw rows here.
    if _nbunch_membership_container(self) is not None:
        return iter(self._adj.items())
    # br-adjiter: nx.Graph.adjacency() returns a dict_itemiterator — an
    # iterator, not a materialised list. User code calling
    # ``next(G.adjacency())`` TypeErrored on fnx previously. Yield
    # lazily so the contract matches.
    #
    # br-r37-c1-adjdict: nx yields ``(node, inner_dict)`` where the
    # inner is a real ``dict`` (the underlying _adj[node] storage —
    # mutating it adds edges).  fnx's ``self.adj[node]`` returns an
    # ``AtlasView`` (a read-only _Mapping wrapper), so
    # ``isinstance(adj, dict)`` returned False on fnx.  The
    # AtlasView's underlying storage is Rust-bound and not directly
    # exposable as a Python ``dict`` reference, so we materialise a
    # snapshot ``dict(adj_view)`` for type parity.  Drop-in callers
    # expecting LIVE-mutation semantics (rare; uncommon in real
    # usage) should use ``G.adj[node]`` directly — that path still
    # returns the AtlasView for set-attribute mutation through the
    # Rust storage.
    if isinstance(self, _FilteredGraphView):
        return ((node, FilterAtlas(self, node)) for node in self)
    # br-r37-c1-adjshare: serve from the (nodes_seq, edges_seq)-keyed cache via
    # ``adjacency_dict_shared`` — the SAME fast integer-CSR rebuild that
    # to_dict_of_dicts uses, but assembled with SHARED rows (no per-row copy).
    # nx's adjacency() hands out the live ``_adj[node]`` rows (two calls yield the
    # SAME row object); the shared assembly matches that AND drops the per-call
    # O(V+E) row-copy that ``to_dict_of_dicts_undirected`` pays for its isolation
    # contract (~7x slower than nx). Identical inner-dict refs (``d[u][v] is
    # G[u][v]``) + node x nbr order; iterating its items yields the same
    # (node, inner) pairs nx's adjacency() does. Returns None for non-exact graph
    # types (falls through to the legacy native dict / AtlasView path).
    if type(self) is Graph or type(self) is DiGraph:
        shared = _fnx.adjacency_dict_shared(self)
        if shared is not None:
            return iter(shared.items())
    # br-r37-c1-gadj: build the nested {node: {nbr: attrs}} snapshot natively
    # (reusing the live edge attr dicts, in node x nbr adjacency order) instead
    # of materialising dict(self.adj[node]) via the per-element AtlasView lambda
    # chain (~150x slower than nx). _FilteredGraphView (handled above) has no
    # _native_adjacency_dict, so the gate is exact-graph only.
    native = getattr(self, "_native_adjacency_dict", None)
    if native is not None:
        return iter(native().items())
    return ((node, dict(self.adj[node])) for node in self)


def _multigraph_adjacency(self):
    """br-adjiter: return a generator matching nx.MultiGraph.adjacency.

    br-r37-c1-adjdict: nx yields ``(node, inner_dict)`` where
    ``inner_dict`` is a real ``dict`` mapping neighbour → keyed-attrs.
    fnx's ``self.adj[node]`` returned an ``AdjacencyView``,
    breaking ``isinstance(adj, dict)`` in drop-in code.  Materialise
    a snapshot dict for type parity (recursive: each neighbour's
    keyed-attrs map is also unwrapped from AtlasView to dict).
    """
    owner = _shared_unsplit_owner(self)
    if owner is not None:
        return _multigraph_adjacency(owner)
    # br-r37-c1-mdadj: build the nested {node: {nbr: {key: attrs}}} snapshot
    # natively (reusing the live edge attr dicts, in node x nbr x key order)
    # instead of unwrapping self.adj[node] via the per-element MultiAdjacencyView
    # lambda chain (~33000x slower than nx). Identical snapshot; iterating the
    # native dict's items yields the same (node, inner_dict) pairs.
    # br-r37-c1-vbe1o: a graph carrying ASSIGNED private storage yields that
    # mapping's rows, exactly as networkx does (`iter(self._adj.items())`). The
    # native paths below read the Rust store and cannot see it, and the final
    # fallback iterates the node view, so a node carried only by an assigned
    # `_adj` never appeared at all.
    #
    # The PRIVATE `_adj` on purpose: the public `adj` is now a read-only view,
    # and networkx hands out the live raw rows here.
    if _nbunch_membership_container(self) is not None:
        return iter(self._adj.items())

    native = getattr(self, "_native_adjacency_dict", None)
    if native is not None:
        return iter(native().items())

    def _unwrap(view):
        return {nbr: dict(keys) for nbr, keys in view.items()}
    return ((node, _unwrap(self.adj[node])) for node in self)


# br-r37-c1-c8xop: previously saved Graph.copy / DiGraph.copy /
# MultiGraph.copy / MultiDiGraph.copy as module-level aliases here
# (_GRAPH_COPY etc) but they were never read elsewhere — dead code.


# add_edge is each class's native kernel, with no Python wrapper. All four
# kernels reject None and unhashable endpoints, and an unhashable multigraph
# key, with networkx's exception type, args and partial-state order (u is
# created before v is examined; both endpoints before a bad key raises), since
# br-r37-c1-aeshim. The wrapper that sat here repeated those checks and, after
# br-r37-c1-weightupdate-9rts1 removed its has_edge probe and Python-side
# merge, did nothing else: it cost one Python frame per call. Pinned by
# tests/python/test_native_add_edge_validates_endpoints.py and
# tests/python/test_repeat_add_edge_keeps_store_clean.py.
_GRAPH_ADD_EDGE_RAW = Graph.add_edge
_DIGRAPH_ADD_EDGE_RAW = DiGraph.add_edge
_MULTIGRAPH_ADD_EDGE_RAW = MultiGraph.add_edge
_MULTIDIGRAPH_ADD_EDGE_RAW = MultiDiGraph.add_edge
_GRAPH_ADD_NODE_RAW = Graph.add_node
_DIGRAPH_ADD_NODE_RAW = DiGraph.add_node
_MULTIGRAPH_ADD_NODE_RAW = MultiGraph.add_node
_MULTIDIGRAPH_ADD_NODE_RAW = MultiDiGraph.add_node
_GRAPH_FAST_ADD_INT_NODES_RANGE_STOP = getattr(
    Graph, "_fast_add_int_nodes_range_stop", None
)
_GRAPH_FAST_ADD_INT_NODES = getattr(Graph, "_fast_add_int_nodes", None)


def _make_none_rejecting_add_node(raw_add_node):
    """Wrap ``add_node`` to reject ``None`` and unhashable types
    matching nx's contract.

    br-nonenode: nx.Graph.add_node(None) raises
    ``ValueError("None cannot be a node")``. fnx's Rust binding
    silently accepted None (and also had confused has_node(None)
    vs has_node('None') behavior). Guarding at the Python edge
    preserves drop-in semantics.

    br-r37-c1-m0io3: nx also raises ``TypeError: unhashable type:
    '<type>'`` when given an unhashable node (list, set, dict).
    fnx's Rust binding silently absorbed the unhashable as a
    Python-id-keyed entry. Guard via ``hash(node)`` here so the
    exact TypeError surfaces before the Rust dispatch.
    """

    def add_node(self, node_for_adding, **attr):
        if node_for_adding is None:
            raise ValueError("None cannot be a node")
        _HASH_PROBE.get(node_for_adding)
        # br-r37-c1-kwsplit: call WITHOUT the dict unpack when there are no
        # attributes. `f(a, **{})` is exactly `f(a)`, but CPython still
        # builds and splats the empty mapping: measured on the raw PyO3
        # add_node, `raw(F, 1)` is 414.1ns against `raw(F, 1, **{})` at
        # 481.2ns - 67ns of pure ceremony on a call that is otherwise ~550ns.
        # The no-attribute form is the overwhelmingly common one.
        if attr:
            return raw_add_node(self, node_for_adding, **attr)
        return raw_add_node(self, node_for_adding)

    return add_node


Graph.add_node = _make_none_rejecting_add_node(_GRAPH_ADD_NODE_RAW)
DiGraph.add_node = _make_none_rejecting_add_node(_DIGRAPH_ADD_NODE_RAW)
MultiGraph.add_node = _make_none_rejecting_add_node(_MULTIGRAPH_ADD_NODE_RAW)
MultiDiGraph.add_node = _make_none_rejecting_add_node(_MULTIDIGRAPH_ADD_NODE_RAW)


_GRAPH_ADD_NODE = Graph.add_node
_DIGRAPH_ADD_NODE = DiGraph.add_node
_MULTIGRAPH_ADD_NODE = MultiGraph.add_node
_MULTIDIGRAPH_ADD_NODE = MultiDiGraph.add_node


def _make_add_nodes_from(
    add_node, fast_add_int_nodes_range_stop=None, fast_add_int_nodes=None
):
    """Build an ``add_nodes_from`` matching the NetworkX contract.

    nx dispatches via hashability: if ``n`` is hashable, it is added as a
    single node; if unhashable (the only reachable case is a 2-tuple whose
    second element is a dict), it is unpacked as ``(node, attrs)``. The
    Rust-level override (br-grid2d-adjacent bug found by review) unpacks
    every 2-tuple, which silently drops the second element and collapses
    tuple-labeled nodes like (0, 1), (0, 2) into [0].
    """

    def add_nodes_from(self, nodes_for_adding, **attr):
        if (
            not attr
            and fast_add_int_nodes_range_stop is not None
            and type(self) is Graph
            and type(nodes_for_adding) is range
            and nodes_for_adding.start == 0
            and nodes_for_adding.step == 1
        ):
            try:
                fast_add_int_nodes_range_stop(self, nodes_for_adding.stop)
                return
            except OverflowError:
                pass
        # br-r37-c1-ow0ie: every native path below takes a concrete container, so
        # a graph, a node view or a generator argument - ``H.add_nodes_from(G)``,
        # ``H.add_nodes_from(G.nodes(data=True))``, the way networkx's own
        # builders copy a node set - fell to the per-node loop at 0.66-0.88x
        # networkx while the same nodes as a list ran 1.6-2.5x. Buffer it and
        # take the list paths - unless it can read the graph while it is
        # consumed (networkx adds each node before pulling the next): through
        # its iterator, or as a view of this graph, whose edges or degree pairs
        # would be new nodes that networkx's live iteration raises on. One that
        # says it is shorter than a batch goes node by node; a one-shot iterator
        # does not know its length, so its first batch-minimum go node by node -
        # exact, and all a short one needs - before the rest is weighed.
        if (
            not attr
            and type(nodes_for_adding) not in (list, tuple, set, range)
            and type(self) in (Graph, DiGraph, MultiGraph, MultiDiGraph)
        ):
            bound_add_node = add_node.__get__(self, type(self))
            nodes_iter = iter(nodes_for_adding)
            if nodes_iter is nodes_for_adding:
                head = _itertools.islice(nodes_iter, _NODE_BATCH_MIN)
                if _add_nodes_one_by_one(self, bound_add_node, head, attr) < _NODE_BATCH_MIN:
                    return
            elif _length_hint(nodes_for_adding, _NODE_BATCH_MIN) < _NODE_BATCH_MIN or (
                len(self) and _view_holds_graph(nodes_for_adding, self)
            ):
                _add_nodes_one_by_one(self, bound_add_node, nodes_iter, attr)
                return
            if not _ebunch_reads_graph(nodes_iter, self):
                _add_nodes_buffered(self, bound_add_node, nodes_iter)
                return
            nodes_for_adding = nodes_iter
        # br-r37-c1-u2jod: bulk native fast path for a concrete list/tuple/set of
        # plain ints (the common ``add_nodes_from(list(range(n)))`` /
        # ``add_nodes_from(other_int_graph)`` shape, plus br-r37-c1-zvwgo's
        # ``intersection_all`` int-set shape) — one PyO3 crossing + a Rust loop
        # instead of a per-element Python loop. The native binding validates
        # atomically and raises ``TypeError`` (non-int / bool element) or
        # ``OverflowError`` (out of i64) BEFORE mutating, so we fall through to
        # the general loop with no partial state. Restricted to re-iterable
        # concrete containers so a one-shot iterable is never half-consumed.
        if (
            not attr
            and fast_add_int_nodes is not None
            and type(self) is Graph
            and type(nodes_for_adding) in (list, tuple, set, range)
        ):
            try:
                fast_add_int_nodes(self, nodes_for_adding)
                return
            except (TypeError, OverflowError):
                pass
        # br-r37-c1-digbatch: DiGraph's native int-node fast path (range / int
        # list / tuple / set). Without it DiGraph.add_nodes_from(range) fell to the
        # per-node loop (0.33x nx) and the int list hit the attributed batch (0.54x);
        # PyDiGraph._fast_add_int_nodes does one bulk extend_nodes_unrecorded. Raises
        # TypeError/OverflowError on any non-int element so a (node, attrs) batch or
        # mixed input falls through to the attributed batch / per-node loop below.
        if (
            not attr
            and type(self) in (DiGraph, MultiGraph, MultiDiGraph)
            and type(nodes_for_adding) in (range, list, tuple, set)
        ):
            try:
                self._fast_add_int_nodes(nodes_for_adding)
                return
            except (TypeError, OverflowError):
                pass
        # br-r37-c1-nodebatch: native attributed-node batch on a FRESH simple
        # Graph — one bulk extend_nodes_with_attrs_unrecorded instead of the
        # per-node add_node loop below (~3.4x nx on attributed construction;
        # relabel/union/convert all funnel through here). Returns False (no
        # mutation) for any shape it can't replicate exactly, so the per-node
        # loop still owns every error and partial-prefix contract.
        if (
            not attr
            and type(self) in (Graph, DiGraph, MultiGraph, MultiDiGraph)
            and type(nodes_for_adding) in (list, tuple)
        ):
            try:
                if self._try_add_nodes_from_batch(nodes_for_adding):
                    return
            except Exception:
                pass
        _add_nodes_one_by_one(self, add_node.__get__(self, type(self)), nodes_for_adding, attr)

    return add_nodes_from


# The names add_node binds itself: an attribute spelled like one cannot travel
# as a keyword.
_ADD_NODE_PARAMETER_NAMES = frozenset(("self", "node_for_adding"))
# The smallest node list the native batches take; add_nodes_from buffers a lazy
# argument to reach them only when it may hold this many.
_NODE_BATCH_MIN = 8


def _add_nodes_one_by_one(graph, add_node, nodes, attr):
    """networkx's add_nodes_from loop over ``add_node`` (bound to ``graph``).

    An element that hashes is a node; one that does not is unpacked as
    ``(node, attr_dict)``. A 2-tuple holding a dict never hashes, so it is
    unpacked without asking. networkx updates the node's dict, so a non-string
    key or one of add_node's parameter names is a plain attribute there: such a
    dict goes in through ``graph.nodes[node]`` instead of keywords. Returns how
    many elements it took.
    """
    attr_as_keywords = attr.keys().isdisjoint(_ADD_NODE_PARAMETER_NAMES)
    probe = _HASH_PROBE.get
    count = 0
    for n in nodes:
        count += 1
        if type(n) is not tuple or len(n) != 2 or type(n[1]) is not dict:
            try:
                probe(n)
            except TypeError:
                pass
            else:
                if attr_as_keywords:
                    add_node(n, **attr)
                else:
                    add_node(n)
                    graph.nodes[n].update(attr)
                continue
        node, ndict = n
        if attr or type(ndict) is not dict:
            merged = dict(attr)
            merged.update(ndict)
        else:
            merged = ndict
        if all(type(key) is str for key in merged) and merged.keys().isdisjoint(
            _ADD_NODE_PARAMETER_NAMES
        ):
            add_node(node, **merged)
        else:
            add_node(node)
            graph.nodes[node].update(merged)
    return count


def _view_holds_graph(source, graph):
    """True when ``source`` is ``graph`` or a view holding it (br-r37-c1-ow0ie).

    A view's iterator can be a snapshot that never mentions the graph, while
    networkx iterates the view live - so ``G.add_nodes_from(G.edges)`` raises
    there once the first edge becomes a node. A view holds its graph directly
    (NodeView, EdgeView) or through a NodeView (NodeDataView, ItemsView), so
    two levels of referents decide; code, containers and other graphs are not
    entered - a graph view's nodes are nodes of its base already.
    """
    frontier = [source]
    graph_types = (Graph, DiGraph, MultiGraph, MultiDiGraph)
    for depth in range(3):
        following = []
        for held in frontier:
            if held is graph:
                return True
            if depth == 2 or type(held) in _VIEW_WALK_OPAQUE or isinstance(held, (type, graph_types)):
                continue
            referents = _gc.get_referents(held)
            following.extend(referents)
            if dict in map(type, referents):
                # Below 3.13 an instance's attributes sit in its __dict__, a
                # container the walk does not enter.
                try:
                    following.extend(vars(held).values())
                except TypeError:
                    pass
        frontier = following
    return False


def _add_nodes_buffered(graph, add_node, nodes_iter):
    """Add a lazy node iterable through add_nodes_from's list paths (br-r37-c1-ow0ie).

    networkx pulls one element, adds it, then pulls the next, so an element it
    rejects - ``None``, or unhashable and not a ``(node, dict)`` pair - is the
    last one it consumes, and an iterable that raises leaves every node before
    that in the graph. The buffer stops pulling at an element networkx could
    reject and adds what it holds before going on, so the graph, the exception
    and what is left in the iterator all match.
    """
    probe = _HASH_PROBE.get
    while True:
        buffered = []
        append = buffered.append
        stopped = False
        try:
            for n in nodes_iter:
                append(n)
                node = n[0] if type(n) is tuple and len(n) == 2 and type(n[1]) is dict else n
                if node is None:
                    stopped = True
                    break
                try:
                    probe(node)
                except TypeError:
                    stopped = True
                    break
        except BaseException:
            _flush_node_buffer(graph, add_node, buffered)
            raise
        _flush_node_buffer(graph, add_node, buffered)
        if not stopped:
            return


def _flush_node_buffer(graph, add_node, buffered):
    if len(buffered) >= _NODE_BATCH_MIN:
        graph.add_nodes_from(buffered)
    elif buffered:
        _add_nodes_one_by_one(graph, add_node, buffered, {})


# br-r37-c1-2gcnp: the lazy range path is safe only because GraphRef result
# materialization now delegates through ``PyGraph::py_node_key``. Lazy integer
# nodes therefore display as Python ints for native algorithm result dicts even
# when ``node_key_map`` intentionally stays sparse.
Graph.add_nodes_from = _make_add_nodes_from(
    _GRAPH_ADD_NODE,
    _GRAPH_FAST_ADD_INT_NODES_RANGE_STOP,
    _GRAPH_FAST_ADD_INT_NODES,
)
DiGraph.add_nodes_from = _make_add_nodes_from(_DIGRAPH_ADD_NODE)
MultiGraph.add_nodes_from = _make_add_nodes_from(_MULTIGRAPH_ADD_NODE)
MultiDiGraph.add_nodes_from = _make_add_nodes_from(_MULTIDIGRAPH_ADD_NODE)


def _graph_update(self, edges=None, nodes=None):
    """Match nx.Graph.update duck-typing so ``G.update(H)`` where H is a
    Graph-like object copies H's nodes, edges, and graph-level attrs into G.

    The Rust-level update only understands an edge-bunch iterable, so
    ``G.update(H)`` crashes with 'each edge must be a tuple'. nx detects a
    graph-like edges argument by checking for ``edges.nodes`` and
    ``edges.edges`` attributes (br-anftup adjacent find).
    """
    if edges is not None:
        if nodes is not None:
            self.add_nodes_from(nodes)
            self.add_edges_from(edges)
        else:
            try:
                graph_nodes = edges.nodes
                graph_edges = edges.edges
            except AttributeError:
                self.add_edges_from(edges)
            else:
                self.add_nodes_from(graph_nodes.data())
                self.add_edges_from(graph_edges.data())
                self.graph.update(edges.graph)
    elif nodes is not None:
        self.add_nodes_from(nodes)
    else:
        raise NetworkXError("update needs nodes or edges input")


# br-r37-c1-updatename: rename so Python's auto-generated TypeError on
# ``G.update(H, edges=...)`` (duplicate values for the same keyword)
# uses the canonical nx wording ``Graph.update()`` rather than fnx's
# private ``_graph_update()``.  Same shape as the DegreeView / EdgeView
# / AdjView name-only renames in cycles 157 / 166.
_graph_update.__name__ = "update"
_graph_update.__qualname__ = "Graph.update"

Graph.update = _graph_update
DiGraph.update = _graph_update
MultiGraph.update = _graph_update
MultiDiGraph.update = _graph_update


# br-r37-c1-kt0vp / br-paralleladd (bt): both multigraph kernels own key=None
# auto-allocation natively (networkx's new_edge_key search, O(1) while no int
# public key has been remapped off its internal key), so no Python auto-key
# wrapper sits in front of them. The one that did rebuilt the full parallel-key
# set on every add, making repeated parallel add_edge O(N^2).


def _code_names(code):
    """Every global or attribute name ``code`` and its nested code objects use."""
    names = set(code.co_names)
    for const in code.co_consts:
        if isinstance(const, _types.CodeType):
            names |= _code_names(const)
    return names


_EBUNCH_WALK_LEAVES = frozenset(
    (str, bytes, int, float, complex, bool, type(None), type, _types.CodeType)
)
_EBUNCH_WALK_CONTAINERS = frozenset((list, tuple, set, frozenset, dict))
_VIEW_WALK_OPAQUE = (
    _EBUNCH_WALK_LEAVES | _EBUNCH_WALK_CONTAINERS | {_types.ModuleType, _types.FunctionType}
)
_ADD_EDGE_PARAMETER_NAMES = frozenset(
    ("u_of_edge", "v_of_edge", "u_for_edge", "v_for_edge", "key")
)
# Below this many pairs Graph/DiGraph.add_edges_from calls add_edge per pair
# (br-r37-c1-832s6); it is the smallest bunch the native index batches take.
_TINY_EDGE_BUNCH = 8


def _ebunch_reads_graph(ebunch, graph):
    """True when a lazy ebunch can reach ``graph`` while it is consumed (br-r37-c1-imddi).

    networkx's add_edges_from inserts each edge before pulling the next, so an
    ebunch whose filter reads the graph - ``(e for e in edges if not
    G.has_edge(*e))``, networkx's own transitive_closure - sees the edges added
    so far. Ours buffers a lazy ebunch to reach the native batches, which is the
    same thing only when nothing the ebunch runs can reach the graph. This walks
    what it can reach: a generator's locals (a closure's cells included), a
    function's cells and defaults, the globals and module attributes either
    names, and the gc referents of everything else - map, filter, zip and the
    itertools objects hold their sources there, bound methods their instance,
    fnx views their graph. Containers are entered only when small, and a
    container inside one - an edge tuple, an adjacency row - is data, not
    walked; reaching ``graph``, or failing to finish the bounded walk, means
    per-edge insertion. Only iterators are walked: a container or view ebunch
    keeps its buffered semantics. The walk costs 1.5-3.5 us a call, so fnx's
    own builders that call add_edges_from once per node or per step pass lists.
    remove_edges_from and remove_nodes_from buffer too and route the same way
    (br-r37-c1-apelp).
    """
    if not hasattr(type(ebunch), "__next__"):
        return False
    leaves = _EBUNCH_WALK_LEAVES
    graph_types = (Graph, DiGraph, MultiGraph, MultiDiGraph)
    seen = set()
    stack = [(ebunch, 0, ())]
    budget = 256
    try:
        while stack:
            obj, depth, names = stack.pop()
            if obj is graph:
                return True
            kind = type(obj)
            if depth > 8 or id(obj) in seen:
                continue
            budget -= 1
            if budget < 0:
                return True
            seen.add(id(obj))
            if kind is _types.GeneratorType:
                frame = obj.gi_frame
                if frame is None:
                    continue
                names = _code_names(obj.gi_code)
                children = list(frame.f_locals.values())
                children.extend(frame.f_globals.get(name) for name in names)
                children.append(obj.gi_yieldfrom)
            elif kind is _types.FunctionType:
                names = _code_names(obj.__code__)
                children = []
                for cell in obj.__closure__ or ():
                    try:
                        children.append(cell.cell_contents)
                    except ValueError:  # an unbound cell
                        pass
                children.extend(obj.__defaults__ or ())
                children.extend((obj.__kwdefaults__ or {}).values())
                children.extend(obj.__globals__.get(name) for name in names)
            elif kind is _types.ModuleType:
                namespace = vars(obj)
                children = [namespace.get(name) for name in names]
            elif kind in _EBUNCH_WALK_CONTAINERS:
                if len(obj) > 64:
                    continue
                children = [
                    child
                    for child in (obj.values() if kind is dict else obj)
                    if type(child) not in _EBUNCH_WALK_CONTAINERS
                ]
            elif isinstance(obj, graph_types):
                continue  # another graph: reading it is not reading this one
            else:
                children = _gc.get_referents(obj)
            for child in children:
                if type(child) not in leaves:
                    stack.append((child, depth + 1, names))
    except Exception:  # noqa: BLE001 - an exotic object: insert per edge, which is always exact
        return True
    return False


def _multi_add_edges_from(self, ebunch_to_add, **attr):
    """Re-dispatch Multi*Graph.add_edges_from so 2-tuple entries
    ``(u, v)`` auto-allocate a fresh key when an edge already exists
    at ``(u, v)`` (franken_networkx-wymzp). Matches nx contract.

    Accepted tuple shapes (from nx.MultiGraph.add_edges_from):
        (u, v)
        (u, v, data_dict)
        (u, v, key)      -- 3-tuple with non-dict key
        (u, v, key, data_dict)

    Uses add-then-mutate rather than ``add_edge(u, v, key=key, **datadict)``
    so a ``'key'`` attribute in datadict doesn't collide with the
    positional ``key`` parameter (franken_networkx-uphdr pattern).
    """
    # br-r37-c1-mgaddedges: the previous per-edge auto-key computation used
    # ``self.has_edge(u, v)`` + ``self[u][v]`` (to find the next free parallel
    # key, gap-aware: ``key = len(existing); while key in existing: key += 1``).
    # Each ``self[u][v]`` rebuilt the full MultiAdjacencyView — O(E) after every
    # edges_seq bump — making bulk construction O(E^2) (~130x slower than nx on
    # 20k edges). Replace ``self[u][v]`` with the native O(1) ``get_edge_data(u,
    # v)`` keydict (1us even on a 20k-edge graph): same gap-aware key (so mixed
    # explicit/auto keys still match nx), and route the attr mutation through the
    # O(1) ``get_edge_data(u, v, key)`` (live dict) instead of ``self[u][v]``.
    # br-r37-c1-urle5: native plain-edge fast path for the common
    # ``add_edges_from([(u, v), ...])`` shape (no **attr, all 2-tuples) on a
    # FRESH multigraph — sequential per-pair auto-keys, one bulk insert. Returns
    # False (no mutation) for any other shape, so the per-edge loop below still
    # handles 3/4-tuples, data dicts, and non-fresh graphs.
    # br-r37-c1-mgaefgen: MATERIALISE a non-re-iterable ebunch so the three
    # native batch kernels below become reachable. All of them are gated on
    # `isinstance(ebunch_to_add, (list, tuple))`, so handing this function a
    # GENERATOR disqualified every one of them and fell through to the per-edge
    # Python loop. Measured on 800 edges into a fresh graph:
    #
    #   MultiDiGraph  generator 1921.92us (0.8634x)  LIST 1018.61us (1.7198x)
    #   MultiGraph    generator 1418.31us (1.0097x)  LIST  736.77us (1.8910x)
    #
    # i.e. the SAME edges cost 1.9x more purely for arriving as a generator.
    # (DiGraph is unaffected - 1.4796x vs 1.5077x - so this is multigraph-only.)
    #
    # THE PREFIX REPLAY IS NOT OPTIONAL. networkx consumes the ebunch lazily and
    # inserts each edge as it arrives, so when the GENERATOR ITSELF raises part
    # way through, the edges yielded before that point are already in the graph:
    # a generator yielding (0,1),(1,2) and then raising leaves exactly those two
    # edges, on all four classes. A plain `list(ebunch_to_add)` would insert
    # NOTHING and re-raise, which is a silent behaviour change. Buffering
    # incrementally and flushing what was collected before re-raising reproduces
    # networkx exactly.
    #
    # A malformed ELEMENT needs no special handling: the list path already
    # matches networkx's partial progress (verified across str / 1-tuple /
    # unhashable-endpoint elements on all four classes), because the batch
    # kernels decline the shape and the per-edge loop below handles it.
    if not isinstance(ebunch_to_add, (list, tuple)):
        if _ebunch_reads_graph(ebunch_to_add, self):
            # The ebunch reads this graph: insert as it yields, as networkx
            # does, so it sees every edge added before it (br-r37-c1-imddi).
            # A (u, v) pair is networkx's add_edge(u, v, **attr) unless an
            # attr name is one of add_edge's own parameters (``key`` above
            # all); any other shape goes through this function as a one-edge
            # list. Either way the keys given are collected (br-r37-c1-xpilu).
            add_edge = self.add_edge
            pairs_direct = attr.keys().isdisjoint(_ADD_EDGE_PARAMETER_NAMES)
            keylist = []
            for _e in ebunch_to_add:
                if pairs_direct and type(_e) is tuple and len(_e) == 2:
                    keylist.append(add_edge(*_e, **attr))
                else:
                    keylist.extend(_multi_add_edges_from(self, [_e], **attr))
            return keylist
        _buffered = []
        try:
            for _e in ebunch_to_add:
                _buffered.append(_e)
        except BaseException:
            if _buffered:
                _multi_add_edges_from(self, _buffered, **attr)
            raise
        ebunch_to_add = _buffered
    # Each native batch below returns the list of keys it gave the edges -
    # networkx's return value (br-r37-c1-xpilu) - or None, having added nothing,
    # for a shape it does not take.
    if not attr and isinstance(ebunch_to_add, (list, tuple)):
        _native_batch = getattr(self, "_try_add_edges_from_batch", None)
        if _native_batch is not None and (keys := _native_batch(ebunch_to_add)) is not None:
            return keys
        # br-r37-c1-04z53.80: exact `(int, int, non-empty str)` keyed-edge
        # batch on a fresh MultiGraph. Keep this before the attributed batch so
        # string keys avoid the per-edge Python add_edge loop, but let ambiguous
        # 3-tuples (empty string / dict-able data / non-string keys) fall through
        # to the NetworkX disambiguation below.
        _native_str_key_batch = getattr(self, "_try_add_str_keyed_edges_from_batch", None)
        if (
            _native_str_key_batch is not None
            and (keys := _native_str_key_batch(ebunch_to_add)) is not None
        ):
            return keys
        # br-r37-c1-trzrx: attributed/mixed `(u, v, data)` batch on a fresh
        # MultiGraph (no **attr) — native single-commit insert instead of the
        # per-edge add_edge loop below (~3.6x nx on attributed construction).
        _native_attr_batch = getattr(self, "_try_add_attr_edges_from_batch", None)
        if _native_attr_batch is not None and (keys := _native_attr_batch(ebunch_to_add)) is not None:
            return keys
    elif attr and type(self) in (MultiGraph, MultiDiGraph) and isinstance(ebunch_to_add, (list, tuple)):
        _native_attr_batch = getattr(self, "_try_add_attr_edges_from_batch", None)
        if (
            _native_attr_batch is not None
            and (keys := _native_attr_batch(ebunch_to_add, attr)) is not None
        ):
            return keys
    if isinstance(self, MultiGraph) and not self.is_directed():
        _add_edge = _MULTIGRAPH_ADD_EDGE_RAW.__get__(self)
    else:
        _add_edge = _MULTIDIGRAPH_ADD_EDGE_RAW.__get__(self)
    keylist = []
    for e in ebunch_to_add:
        ne = len(e)
        if ne == 4:
            u, v, key, dd = e
        elif ne == 3:
            u, v, dd = e
            key = None
        elif ne == 2:
            u, v = e
            dd = {}
            key = None
        else:
            raise NetworkXError(
                f"Edge tuple {e} must be a 2-tuple, 3-tuple or 4-tuple."
            )
        # br-r37-c1-baqyi: mirror nx exactly — build the datadict BEFORE
        # add_edge (a non-dict 4th element raises with NOTHING created),
        # and a 3-tuple third becomes the KEY only when dict.update
        # raises TypeError/ValueError (dict-able iterables of pairs are
        # DATA; ddd keeps any pairs merged before the raise, like nx).
        ddd = {}
        ddd.update(attr)
        try:
            ddd.update(dd)
        except (TypeError, ValueError):
            if ne != 3:
                raise
            key = dd  # ne == 3 with non-dict-able third: it's the key
        # br-paralleladd (bt): native add_edge (key=None) now auto-allocates the
        # nx public key in O(1) (has_remapped_int_key fast path, 79876a932 +
        # 8b939e3f7), so the old per-edge ``get_edge_data(u, v)`` keydict build +
        # Python ``while key in existing`` search — O(existing) per add, O(N^2)
        # for N parallel edges on a NON-fresh graph (the native batch fast paths
        # above only fire on a fresh graph) — is dropped. add_edge returns the
        # key actually used, which the attr mutation below targets.
        actual_key = _add_edge(u, v, key=key)
        if ddd:
            self.get_edge_data(u, v, actual_key).update(ddd)
        keylist.append(actual_key)
    return keylist


MultiGraph.add_edges_from = _multi_add_edges_from
MultiDiGraph.add_edges_from = _multi_add_edges_from


# br-addedgesgen: nx internals frequently call
# ``G.add_edges_from(generator_that_reads_G)`` (e.g. nx.transitive_closure
# does `TC.add_edges_from((v, e[1]) for e in ... if e[1] not in TC[v])`).
# The Rust add_edges_from mutably borrows self while iterating the ebunch,
# and the generator's inside-the-loop read of ``TC[v]`` then tries to
# acquire an immutable borrow on the same RefCell, raising
# "Already mutably borrowed". Fix: materialize the ebunch into a list at
# the Python layer before handing it to the Rust call, so the generator
# fully evaluates (reading self) before any mutable borrow starts.
_GRAPH_RAW_ADD_EDGES_FROM = Graph.add_edges_from
_DIGRAPH_RAW_ADD_EDGES_FROM = DiGraph.add_edges_from
_GRAPH_RAW_REMOVE_EDGES_FROM = Graph.remove_edges_from
_DIGRAPH_RAW_REMOVE_EDGES_FROM = DiGraph.remove_edges_from
_MULTIGRAPH_RAW_REMOVE_EDGES_FROM = MultiGraph.remove_edges_from
_MULTIDIGRAPH_RAW_REMOVE_EDGES_FROM = MultiDiGraph.remove_edges_from
_GRAPH_RAW_REMOVE_NODES_FROM = Graph.remove_nodes_from
_DIGRAPH_RAW_REMOVE_NODES_FROM = DiGraph.remove_nodes_from
_MULTIGRAPH_RAW_REMOVE_NODES_FROM = MultiGraph.remove_nodes_from
_MULTIDIGRAPH_RAW_REMOVE_NODES_FROM = MultiDiGraph.remove_nodes_from


_ADD_EDGES_UNSET = object()


def _every_edge_is_a_pair(edges):
    try:
        return all(len(edge) == 2 for edge in edges)
    except TypeError:
        return False


def _simple_add_edges_from_touches_existing_plain_edge(graph, edges):
    # True only for a bunch of PLAIN (u, v) pairs of which one already exists:
    # the caller then replays it as ``for u, v in edges``. A hit on an early
    # pair must still check the rest - a mixed bunch with a 3-tuple after the
    # hit made that replay raise "too many values to unpack". Asked only on the
    # path that carries broadcast attrs, where a re-added edge merges them
    # (br-r37-c1-ey5n2: the attr-less native batches skip an existing pair).
    if type(graph) not in (Graph, DiGraph):
        return False
    # br-r37-c1-emptyaef (cc): an empty graph has no edge that could pre-exist, so the
    # per-edge has_edge() pre-scan (O(E) PyO3 round-trips) is pure waste -- it gates the
    # native batch for from_edgelist / Graph(edgelist) / add_edges_from on a fresh graph
    # (the common construction case), doubling the work. number_of_edges() is O(1).
    edge_count = graph.number_of_edges()
    if edge_count == 0:
        return False
    # br-cc-aefsnap: the per-edge graph.has_edge(u, v) pre-scan pays one PyO3
    # round-trip (plus the Python has_edge wrapper) for EACH edge in the bunch.
    # When the existing edge set is no larger than the bunch, a single edges()
    # snapshot into a Python set + pure-Python membership checks are strictly
    # cheaper: the snapshot is O(edge_count) <= O(len(bunch)) (the per-edge scan
    # is already O(len(bunch))), and each membership test is a C-level set lookup
    # instead of a has_edge() round-trip. This is the hot path for add_edges_from
    # onto an already-populated-but-small graph and for generators that seed a
    # tiny graph then bulk-extend (barabasi_albert seeds star_graph(m) then adds
    # ~m*(n-m) edges). When edge_count > len(bunch) the snapshot would cost more
    # than the scan saves, so fall through to the per-edge has_edge path.
    try:
        bunch_len = len(edges)
    except TypeError:
        bunch_len = None
    if bunch_len is not None and edge_count <= bunch_len:
        directed = type(graph) is DiGraph
        try:
            if directed:
                existing = set(graph.edges())
            else:
                existing = {frozenset(e) for e in graph.edges()}
        except TypeError:
            existing = None
        if existing is not None:
            for edge in edges:
                try:
                    if len(edge) != 2:
                        return False
                    u, v = edge
                except TypeError:
                    return False
                try:
                    probe = (u, v) if directed else frozenset((u, v))
                    hit = probe in existing
                except TypeError:
                    # unhashable endpoint: defer to has_edge's own TypeError
                    # handling via the per-edge path below. The directed probe
                    # is a tuple, which only hashes at the membership test, so
                    # that test sits in here too (it raised a set-element
                    # TypeError before anything was added).
                    existing = None
                    break
                if hit:
                    return _every_edge_is_a_pair(edges)
            else:
                return False
    for edge in edges:
        try:
            if len(edge) != 2:
                return False
            u, v = edge
        except TypeError:
            return False
        try:
            if graph.has_edge(u, v):
                return _every_edge_is_a_pair(edges)
        except TypeError:
            return False
    return False


def _invalidate_adjacency_row_caches(graph):
    cache = vars(graph)
    if not graph.is_multigraph():
        cache.pop("_fnx_getitem_atlas_cache", None)
    cache.pop("_fnx_adj_row_keydict_cache", None)
    cache.pop("_fnx_adj_row_keydict_cache_state", None)
    for slot in ("_fnx_view_adj", "_fnx_view_succ", "_fnx_view_pred"):
        view = cache.get(slot)
        row_cache = getattr(view, "_fnx_atlas_cache", None)
        if row_cache is None:
            continue
        for row_view in row_cache[1].values():
            if hasattr(row_view, "_fnx_kd_cache"):
                row_view._fnx_kd_cache = None
        view._fnx_atlas_cache = None


def _add_plain_pairs(graph, raw_add_edge, pairs, attr):
    """Add (u, v) pairs as networkx's add_edges_from does: add_edge(u, v,
    **attr) each, through the class's own add_edge (networkx never calls one a
    subclass overrides). An attr named like one of add_edge's parameters
    (u_of_edge, v_of_edge) cannot travel as a keyword, so then the pair goes
    in bare and attr is merged into its data dict - networkx's
    datadict.update(attr) - where the keyword call raised TypeError."""
    if attr.keys().isdisjoint(_ADD_EDGE_PARAMETER_NAMES):
        for u, v in pairs:
            raw_add_edge(graph, u, v, **attr)
    else:
        for u, v in pairs:
            raw_add_edge(graph, u, v)
            graph.get_edge_data(u, v).update(attr)
