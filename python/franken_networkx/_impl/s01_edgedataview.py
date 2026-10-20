

def _nx_edge_view_contains_by_has_edge(graph, e, kind, multi):
    """_nx_edge_view_contains's answer and exceptions through
    graph.has_edge, for a graph or view whose rows are dearer to build than
    has_edge is to ask - a filtered or conversion view builds a row object
    per lookup (4.5-9 us a probe against has_edge's 0.8-1). networkx's row
    lookups hash the row's node, then the neighbour, then the key, and each
    raises its TypeError only if the lookups before it succeeded. has_edge
    raises for an unhashable node or key itself, as often as networkx or
    more, never less (it hashes u first; an in view's first lookup is
    pred[v], hence v's probe up front), so the probes that decide which of
    its TypeErrors networkx raises run only once it has raised."""
    if multi:
        n = len(e)
        if n == 3:
            u, v, k = e
        elif n == 2:
            u, v = e
            k = 0
        else:
            raise ValueError("MultiEdge must have length 2 or 3")
    elif kind == "undirected":
        try:
            u, v = e[:2]
        except ValueError:
            return False
    else:
        u, v = e
    if kind == "in":
        _HASH_PROBE.get(v)
    try:
        return graph.has_edge(u, v, k) if multi else graph.has_edge(u, v)
    except TypeError as err:
        raised = err
    first, second = (v, u) if kind == "in" else (u, v)
    _HASH_PROBE.get(first)
    try:
        _HASH_PROBE.get(second)
    except TypeError:
        if first in graph:  # networkx got the row, then hashed the neighbour
            raise
        return False
    if multi:
        try:
            _HASH_PROBE.get(k)
        except TypeError:
            if graph.has_edge(u, v):  # an existing pair's keydict hashes k
                raise
            return False
    raise raised


def _nx_edge_report_tail(dd, data, default):
    # What a data view appends to (u, v) / (u, v, k) for one edge.
    if data is True:
        return (dd,)
    if data is False:
        return ()
    return (dd[data],) if data in dd else (default,)


def _nx_edge_data_view_contains(adj, e, kind, multi, data, default, keys, nbunch):
    """The edge DATA views - what G.edges(nbunch, data, ...) returns;
    `nbunch` is the node set the view was built on, or None."""
    u, v = e[:2]
    if nbunch is not None:
        if kind == "out":
            outside = u not in nbunch
        elif kind == "in":
            outside = v not in nbunch
        else:
            outside = u not in nbunch and v not in nbunch
        if outside:
            return False
    try:
        cell = adj[v][u] if kind == "in" else adj[u][v]
    except KeyError:
        if not (multi and kind == "undirected"):
            return False
        try:
            cell = adj[v][u]
        except KeyError:
            return False
    if not multi:
        return e == (u, v) + _nx_edge_report_tail(cell, data, default)
    if keys is True:
        k = e[2]
        if kind == "in":
            dd = cell[k]  # networkx's InMultiEdgeDataView lets this KeyError out
        else:
            try:
                dd = cell[k]
            except KeyError:
                return False
        return e == (u, v, k) + _nx_edge_report_tail(dd, data, default)
    return any(e == (u, v) + _nx_edge_report_tail(dd, data, default) for dd in cell.values())


def _edge_rows(graph, kind):
    # The adjacency an edge view of `kind` looks its rows up in.
    if kind == "in":
        return graph.pred
    return graph.succ if kind == "out" else graph.adj


class EdgeDataView:
    """Live view over ``G.edges(data=..., nbunch=...)`` matching nx's
    EdgeDataView contract (br-r37-c1-sf1ku).

    The Rust EdgeView's ``__call__`` materialises a list eagerly. nx's
    EdgeDataView is a true view over the graph — mutations after the
    view is captured are reflected on iteration. This wrapper stores
    the call site's resolved kwargs and re-invokes the underlying
    edge_view_call on each access (iter / len / contains / repr) so
    drop-in code that captures a view and iterates after mutating gets
    nx's live semantics. Class name aligned to ``EdgeDataView`` so
    ``type(view).__name__`` checks match nx.
    """

    def __init__(self, edge_view_call, view_self, *, data, default, nbunch_list, graph=None):
        self._call = edge_view_call
        self._view = view_self
        self._data = data
        self._default = default
        self._nbunch_list = nbunch_list
        # br-r37-c1-w5sa7: nx raises ``NetworkXError("Node X in
        # sequence nbunch is not a valid node.")`` when nbunch
        # contains an unhashable element; previously fnx leaked a
        # bare ``TypeError("unhashable type: 'list'")`` from
        # ``set(nbunch_list)``.  Build the set element-by-element so
        # we can translate the failure into nx's exact wording.
        if nbunch_list is None:
            self._nbset = None
        else:
            try:
                self._nbset = set(nbunch_list)
            except TypeError:
                for item in nbunch_list:
                    try:
                        _HASH_PROBE.get(item)
                    except TypeError:
                        raise NetworkXError(
                            f"Node {item} in sequence nbunch is not a valid node."
                        )
                # Should be unreachable — set() failed but every
                # element hashes individually; re-raise the original.
                raise
            # br-edgenbunchdedup (bt): nx's EdgeDataView builds
            # ``nbunch = dict.fromkeys(viewer._graph.nbunch_iter(nbunch))`` —
            # an ORDER-PRESERVING DEDUP — so a node repeated in nbunch has its
            # incident edges emitted ONCE (the per-node ``seen`` set only blocks
            # double-emission across endpoints, not a repeated nbunch node). fnx
            # walked the raw list, so e.g. ``G.edges([1, 1])`` on a simple Graph
            # emitted node 1's edges twice. Dedup here (set() above already proved
            # every element hashable) so the native + fallback + count paths all
            # match nx. The DiGraph/MultiGraph nbunch kernels dedup internally.
            self._nbunch_list = list(dict.fromkeys(nbunch_list))
        # br-r37-c1-dc14n: graph reference (when known) lets the
        # adj-walk path compute edges in nx-matching adj order. Look
        # up via the global EdgeView->Graph map populated by the
        # _private_aware_edges property if not provided.
        if graph is None:
            try:
                graph = _EDGE_VIEW_GRAPH_OWNER.get(id(view_self))
            except (NameError, TypeError):
                graph = None
        self._graph = graph
        # br-r37-c1-2pia7: nx resolves the nbunch ONCE, here in __init__:
        #
        #   nbunch = dict.fromkeys(viewer._graph.nbunch_iter(nbunch))
        #   self._nodes_nbrs = lambda: [(n, adjdict[n]) for n in nbunch]
        #
        # so the node SET is frozen now while the adjacency behind it stays
        # live. This view re-invokes the call on every read (that is what makes
        # it live at all), and it kept the caller's RAW nbunch — so a node that
        # was absent at construction became live later and started contributing
        # its edges, which nx never does. Freeze it to what exists now.
        #
        # The frozen list is also what lets a read tell that one of ITS nodes
        # has since been removed, which nx reports by raising from adjdict[n];
        # see _raise_if_frozen_nbunch_node_removed.
        self._len_handoff = None
        self._nbunch_nodes_seq = None
        if self._nbunch_list is not None and graph is not None:
            self._nbunch_list = [n for n in self._nbunch_list if n in graph]
            # Node revision at freeze time — see below.
            self._nbunch_nodes_seq = getattr(graph, "nodes_seq", None)

    def _raise_if_frozen_nbunch_node_removed(self):
        """br-r37-c1-2pia7: nx's ``adjdict[n]`` raises once n is gone.

        nx's lambda indexes the adjacency for every frozen nbunch node on each
        iteration, so removing one of them turns a later read into a KeyError
        rather than a quietly shorter answer. fnx's walks skip absent nodes —
        correct for a node the caller named that never existed, wrong for one
        that was resolved into the frozen set and has since been removed.

        Gated on ``nodes_seq``, which is the whole point of doing it this way:
        the scan is O(len(nbunch)) and these views are read repeatedly, so
        running it unconditionally cost 0.64-0.90x on the nbunch paths (worst:
        ``len(G.edges(nbunch))`` over every node). Only a NODE-set change can
        invalidate a frozen node, and ``nodes_seq`` moves on exactly that — so
        edge churn, the common case, costs one integer compare.
        """
        graph = self._graph
        if self._nbunch_list is None or graph is None:
            return
        expected = self._nbunch_nodes_seq
        if expected is not None:
            current = getattr(graph, "nodes_seq", None)
            if current is not None and current == expected:
                return
        for node in self._nbunch_list:
            if node not in graph:
                raise KeyError(node)

    def _materialize(self):
        self._raise_if_frozen_nbunch_node_removed()
        data = self._data
        default = self._default
        data_is_none = data is None
        rust_data = False if data_is_none else data
        # br-r37-c1-edgesdatakey: nx.EdgeView.__call__ accepts ANY
        # value for ``data`` and uses it as a dict-key into each edge
        # attrs via ``attrs.get(data, default)`` — so callables /
        # ints / tuples / etc. all return the default since they
        # aren't typical attr keys.  fnx's Rust binding declared
        # ``data: bool | str`` and raised
        # ``TypeError("data must be True, False, or a string
        # attribute name")`` on any other type.  Compute in Python
        # for parity when ``data`` is a non-string non-bool key.
        if not data_is_none and not isinstance(data, (bool, str)):
            return self._materialize_data_as_key(data, default)
        if self._nbunch_list is not None and self._graph is not None:
            # br-r37-c1-dc14n: nx's edges(nbunch) iterates nbunch in
            # user-given order and for each node yields edges (u, v)
            # in adj[u] order, skipping edges where v has already
            # been seen via this iteration. The Rust path returned
            # edges in G.nodes()-order filtered by nbunch — mismatched
            # iteration order. Replicate nx's algorithm explicitly so
            # G.edges(nbunch) matches nx's contract on undirected
            # graphs. (Directed/multigraph go through different
            # EdgeView classes which already match nx.)
            return self._materialize_via_adj_walk(data, default, data_is_none)
        result = self._call(
            self._view,
            data=rust_data,
            nbunch=self._nbunch_list,
            default=default,
        )
        if data_is_none:
            result = [edge + (default,) for edge in result]
        return list(result)

    def _materialize_data_as_key(self, data, default):
        """nx-shape ``edges(data=arbitrary_key)`` — yield (u, v, attrs.get(key, default))."""
        # Reuse the bool=True path to get edges-with-attr-dict, then
        # project each (u, v, attrs) -> (u, v, attrs.get(data, default)).
        result = self._call(
            self._view,
            data=True,
            nbunch=self._nbunch_list,
            default=default,
        )
        projected = []
        for entry in result:
            if len(entry) == 3:
                u, v, attrs = entry
                val = attrs.get(data, default) if isinstance(attrs, dict) else default
                projected.append((u, v, val))
            elif len(entry) == 4:
                # MultiGraph: (u, v, key, attrs)
                u, v, k, attrs = entry
                val = attrs.get(data, default) if isinstance(attrs, dict) else default
                projected.append((u, v, k, val))
            else:
                projected.append(entry)
        return projected

    def _walk_rows_lazily(self, data, default, data_is_none):
        """br-r37-c1-u5tyh: iterate the LIVE rows, as networkx does.

        networkx's nbunch edge view builds ``[(n, adjdict[n]) for n in nbunch]``
        at iteration start and then walks each captured row dict. Its
        mutate-during-iteration behaviour is therefore not a policy at all — it
        is whatever CPython says when the dict you are walking is resized. That
        is why nx completes when an unrelated node is added but raises when an
        edge is added to a node whose row is being iterated.

        fnx materialised the whole edge list up front and wrapped it in a
        seq-token guard, which raises on ANY structural change. Against nx that
        was wrong in both directions at once: it raised where nx completes
        (adding a node, removing an unrelated node, clear) and completed where
        nx raises (adding an edge onto a row under iteration).

        Yielding out of the live row dicts gets all of it right for free, with
        no guard and no token. Returns None when the rows are not available, so
        the caller can fall back.
        """
        graph = self._graph
        # br-r37-c1-8qxi9: one preamble for the whole nbunch, not one per node.
        rows = _cached_adj_row_keydicts(
            graph, "adj", self._nbunch_list, lambda node: lambda: graph[node]
        )
        if rows is None:
            return None

        def _walk():
            seen = set()
            for node, row in rows:
                for nbr, edge_data in row.items():
                    if nbr in seen:
                        continue
                    if data is False:
                        yield (node, nbr)
                    elif data is True:
                        yield (node, nbr, edge_data)
                    elif data_is_none:
                        yield (node, nbr, default)
                    else:
                        yield (node, nbr, edge_data.get(data, default))
                seen.add(node)

        return _walk()

    def _materialize_via_adj_walk(self, data, default, data_is_none):
        """Mirror nx's UndirectedEdgeView.__call__ when nbunch is set:
        walk nbunch_list in user order, for each node iterate
        adj[node] yielding (u, v) plus optional data, skipping
        edges where the second endpoint has already been visited."""
        graph = self._graph
        # br-r37-c1-aq6jv: for a SMALL nbunch, crossing into Rust costs more than
        # doing the walk in Python. The native kernel below is ~3.7us of fixed
        # cost per call regardless of how little it is asked for, while
        # networkx does the whole single-node call in ~4.2us — so at nbunch=1
        # fnx was 0.356x purely on the boundary crossing.
        #
        # The per-row keydict cache already holds each row as a LIVE Python dict
        # (the same persistent mirror neighbors() iterates, invalidated by the
        # nodes_seq/edges_seq token), so a warm walk touches no PyO3 at all.
        # This is nx's own algorithm and order: nbunch order outer, adjacency
        # order inner, second endpoint deduped via `seen`, and the node joins
        # `seen` AFTER its row so a self-loop still emits (br-r37-c1-6yimw).
        #
        # Threshold is measured, not guessed — see the bead: the crossover
        # against the native kernel is between 10 and 100 rows.
        if (
            type(graph) is Graph
            and self._nbunch_list is not None
            and (
                len(self._nbunch_list) <= _EDGES_NBUNCH_PY_WALK_MAX
                or len(self._nbunch_list) <= _edges_nbunch_py_walk_limit(graph)
            )
        ):
            # No private-storage probe here: _cached_adj_row_keydict already
            # returns None for those graphs, and it was the second such call
            # per edges() invocation.
            # br-r37-c1-8qxi9: one preamble for the whole nbunch, not one per node.
            rows = _cached_adj_row_keydicts(
                graph, "adj", self._nbunch_list, lambda node: lambda: graph[node]
            )
            if rows is not None:
                seen = set()
                result = []
                append = result.append
                for node, row in rows:
                    for nbr, edge_data in row.items():
                        if nbr in seen:
                            continue
                        if data is False:
                            append((node, nbr))
                        elif data is True:
                            # The LIVE attr dict, exactly as nx and the native
                            # kernel yield — not a copy.
                            append((node, nbr, edge_data))
                        elif data_is_none:
                            append((node, nbr, default))
                        else:
                            append((node, nbr, edge_data.get(data, default)))
                    seen.add(node)
                return result

        # br-r37-c1-ipm32: a native kernel walks ONLY the nbunch rows in Rust
        # (nx UndirectedEdgeView(nbunch) order + undirected dedup), attaching the
        # SAME live edge dict object nx yields (via edge_py_attrs) — no full-graph
        # to_dict_of_dicts overbuild, no per-edge AtlasView/dict() copy. This
        # walks only the requested rows, so it BEATS nx (the earlier
        # to_dict_of_dicts routing overbuilt the whole graph for a partial
        # nbunch). data=False / data=None skip the dict attach entirely.
        if type(graph) is Graph and self._nbunch_list is not None and type(data) is str:
            # br-r37-c1-p1tyz: an attribute's VALUES, read natively from each
            # edge's live dict or the store - no dict built per edge. Not
            # memoized: writing an attribute does not move edges_seq, so a
            # remembered value could be stale.
            rows = _fnx.edges_nbunch_data(graph, self._nbunch_list, data, default)
            if rows is not None:
                return rows
        elif type(graph) is Graph and self._nbunch_list is not None:
            # br-r37-c1-gnbmemo: the last member of the nbunch edge-view family
            # to get the memo. `with_data` rides in native_args, so the
            # attrs/no-attrs shapes cannot answer for each other.
            #
            # ALIASING NOTE, because the `data is True` branch below returns this
            # list DIRECTLY and its comment relied on it being freshly built per
            # call: `_nbunch_data_cache` returns the native's own fresh list on a
            # miss and a NEW `list(...)` over the cached tuple on a hit, so the
            # caller never receives the cached container itself. The tuples and
            # attr dicts inside are shared, which is what nx's live-view
            # semantics require.
            rows = _nbunch_data_cache(
                graph,
                "_fnx_simple_edges_nb_cache",
                self._nbunch_list,
                lambda nb, flag: _fnx.edges_nbunch_data(graph, nb, flag),
                data is True,
            )
            if rows is not None:
                if data is False:
                    return [(u, v) for u, v, _d in rows]
                if data is True:
                    # br-r37-c1-04z53 (cc): the native kernel already emits
                    # exactly (u, v, attrs) 3-tuples for data=True, so the old
                    # `[(u, v, d) for u, v, d in rows]` comprehension rebuilt an
                    # identical tuple per edge (a wasted O(E) unpack+repack — the
                    # dominant cost in _materialize_via_adj_walk). Return the
                    # native list directly (byte-identical; it is freshly built
                    # per call, so no aliasing).
                    return rows
                if data_is_none:
                    return [(u, v, default) for u, v, _d in rows]
        # Fallback for views / subclasses the native kernel declines: per-node
        # AtlasView walk (br-r37-c1-6yimw: add node to ``seen`` AFTER its inner
        # loop so self-loop edges where nbr == node are still emitted).
        seen = set()
        result = []
        for node in self._nbunch_list:
            if node not in graph:
                # nx skips missing nbunch nodes silently.
                continue
            for nbr, edge_data in graph[node].items():
                if nbr in seen:
                    continue
                if data is False:
                    result.append((node, nbr))
                elif data is True:
                    result.append((node, nbr, dict(edge_data)))
                elif data_is_none:
                    result.append((node, nbr, default))
                else:
                    result.append((node, nbr, edge_data.get(data, default)))
            seen.add(node)
        return result

    def _reorder(self, edge):
        if not isinstance(edge, tuple) or len(edge) < 2:
            return edge
        u, v = edge[0], edge[1]
        rest = edge[2:]
        if u in self._nbset:
            return edge
        if v in self._nbset:
            return (v, u) + rest
        return edge

    def __iter__(self):
        # br-r37-c1-aq6jv: consume the handoff from an immediately preceding
        # __len__ (see there). Popped, never reused.
        handoff = self._len_handoff
        rows = None
        if handoff is not None:
            self._len_handoff = None
            token, cached = handoff
            if token is not None and token == _edge_list_freshness_token(self._graph):
                rows = cached
        if rows is not None:
            # Came straight from the __len__ of the same list(); no user code
            # can have run in between, so there is nothing to guard against.
            return iter(rows)
        # br-r37-c1-u5tyh: an explicit `for e in view:` CAN interleave user
        # code, and that is where networkx's semantics live. Walk the live rows
        # so CPython supplies them.
        if (
            self._graph is not None
            and self._nbunch_list is not None
            and type(self._graph) is Graph
            and (
                len(self._nbunch_list) <= _EDGES_NBUNCH_PY_WALK_MAX
                or len(self._nbunch_list) <= _edges_nbunch_py_walk_limit(self._graph)
            )
            and (self._data is False or self._data is True)
        ):
            self._raise_if_frozen_nbunch_node_removed()
            lazy = self._walk_rows_lazily(
                self._data, self._default, self._data is None
            )
            if lazy is not None:
                return lazy
        if (
            self._nbunch_list is None
            and self._data is not None
            and isinstance(self._data, (bool, str))
        ):
            rows = self._call(
                self._view,
                data=self._data,
                nbunch=None,
                default=self._default,
            )
        else:
            rows = self._materialize()
        if self._graph is None:
            return iter(rows)
        # br-r37-c1-hihrf: a native nbunch result is materialised, but NetworkX
        # only raises if the row it is currently walking changed.  The row guard
        # preserves that contract for nbunches above the lazy-walk gate.  Its
        # native snapshot reuses public node-index lookasides for exact scalar
        # keys, so repeated long-key views do not recreate canonical strings.
        # br-r37-c1-8c7m5: the `data=<key>` spelling has no lazy walk — the gate
        # just above admits only `data is False or data is True`, because the
        # walk yields the raw attribute dict and this form needs
        # `attrs.get(key, default)`. So it arrives here, materialised, and was
        # then STALE for every mutation networkx reads through: a later row
        # grown or shrunk, a self-loop added, all invisible.
        #
        # Two arguments close it, and both are needed. `refresh_rows` lets the
        # guard rebuild at the moment it has decided networkx would NOT raise —
        # which is exactly when networkx is still reading the changed rows.
        # `guard_edge_count` is what makes that moment arrive at all for an
        # EDGE-only mutation: without it the guard watches `nodes_seq` alone, so
        # `remove_edge` in a later row moved nothing it was looking at and the
        # trigger never fired. Every multigraph nbunch path already passes it.
        #
        # ONLY WITH AN NBUNCH, and that qualifier is measured rather than
        # cautious. With no nbunch there are no rows to check, so
        # `_FailFastEdgeIterator` falls to its COARSE branch, where watching the
        # edge sequence means raising on any edge change at all — including
        # re-adding an edge that already exists, which networkx reads straight
        # through because its adjacency dict did not resize. Passing it
        # unconditionally fixed 192 cells and broke 6, all of them this shape.
        # `ignore_removed_nbunch_row` because A DETACHED ROW IS NOT AN EMPTY ROW,
        # and that is not a multigraph rule even though the only other call site
        # passes `graph.is_multigraph()`. `G.clear()` empties the OUTER adjacency
        # dict and leaves the row dicts alone; networkx is holding those, so it
        # drains their pre-mutation contents on any class. Without this the live
        # row-size check runs against a node that is gone and reports a resize:
        # `G.edges(nb, data=<key>)` raised RuntimeError after a clear where nx
        # completes, on both simple classes. The `data=False`/`data=True`
        # spellings never showed it because they take the lazy walk instead.
        return _FailFastEdgeIterator(
            self._graph,
            rows,
            guard_edge_count=self._nbunch_list is not None,
            nbunch_rows=self._nbunch_list,
            ignore_removed_nbunch_row=True,
            refresh_rows=self._rematerialise_rows,
        )

    def _rematerialise_rows(self):
        """Rebuild this view's rows mid-iteration; None if it cannot.

        br-r37-c1-8c7m5, the `EdgeDataView` twin of
        `_EdgeListWithSetAlgebra._fnx_rematerialise_rows`. Called by the nbunch
        guard only after it has seen the graph move and ruled out a raise.
        """
        try:
            return self._materialize()
        except Exception:  # noqa: BLE001 - an unrebuildable view keeps its rows
            return None

    def __len__(self):
        if self._nbunch_list is None and self._graph is not None:
            try:
                if not _has_networkx_private_storage(self._graph):
                    return self._graph.number_of_edges()
            except (AttributeError, NameError, TypeError):
                pass
        # br-r37-c1-ipm32: ``list(view)`` calls ``__len__`` (size hint) THEN
        # ``__iter__``; counting the nbunch edges natively (no PyObject build)
        # avoids materializing the whole tuple list twice. Simple Graph only;
        # otherwise fall back to the materialize-based count.
        elif self._nbunch_list is not None and type(self._graph) is Graph:
            # br-r37-c1-2pia7: the native count skips absent nodes, so it must
            # not run before the frozen-nbunch check that _materialize does —
            # otherwise len() answers a number where nx raises.
            self._raise_if_frozen_nbunch_node_removed()
            # br-r37-c1-aq6jv: for a SMALL nbunch the walk is cheaper than the
            # native count, and `list(view)` asks for the length and then
            # immediately iterates — so materialise once and hand the SAME list
            # to the __iter__ that follows. The handoff is safe only because no
            # user code can run between CPython's length-hint call and the
            # __iter__ of the same list(): the cache is consumed once and
            # dropped, so it can never serve a later read across a mutation.
            # br-r37-c1-p1tyz: rows of attribute VALUES are never handed off.
            # CPython's list() takes the iterator BEFORE the length hint, so the
            # handoff outlives the list() that made it and serves the NEXT
            # iteration; its token moves on structure only, so a value read
            # there after an attribute write was the old one.
            if (self._data is True or self._data is False) and (
                len(self._nbunch_list) <= _EDGES_NBUNCH_PY_WALK_MAX
                or len(self._nbunch_list) <= _edges_nbunch_py_walk_limit(self._graph)
            ):
                rows = self._materialize()
                # Stamped with the graph revision: `len(v)` and the `list(v)`
                # that follows it are adjacent in CPython, but a CALLER can do
                # len(v), mutate, then iterate — and that must see the
                # mutation. Without the stamp this handoff reintroduced exactly
                # the staleness br-r37-c1-af0ig removed, which is how the test
                # for it caught this.
                self._len_handoff = (_edge_list_freshness_token(self._graph), rows)
                return len(rows)
            count = _fnx.edges_nbunch_count(self._graph, self._nbunch_list)
            if count is not None:
                return count
        return len(self._materialize())

    def __contains__(self, item):
        # br-r37-c1-ex1s6: networkx's EdgeDataView.__contains__, a row lookup
        # against the node set the view was built on (the frozen nbunch).
        graph = self._graph
        if graph is None:
            return item in self._materialize()
        nbunch = self._nbunch_list
        if nbunch is not None:
            # A dict, as networkx's: an unhashable probe is worded as a key.
            nbunch = self.__dict__.get("_fnx_nbunch_set")
            if nbunch is None:
                nbunch = self._fnx_nbunch_set = dict.fromkeys(self._nbunch_list)
        return _nx_edge_data_view_contains(
            graph.adj, item, "undirected", False, self._data, self._default, False, nbunch
        )

    def __repr__(self):
        return f"EdgeDataView({self._materialize()!r})"

    def __str__(self):
        # br-r37-c1-mpv5x: nx EdgeDataView.__str__ is str(list(self)).
        return str(self._materialize())

    def __eq__(self, other):
        if hasattr(other, "__iter__"):
            return list(self._materialize()) == list(other)
        return NotImplemented

    __hash__ = None

    def __reduce__(self):
        # br-r37-c1-edv-pkl: EdgeDataView holds `self._call`, a
        # wrapper_descriptor on the Rust EdgeView type
        # (`<slot wrapper '__call__' of 'franken_networkx.EdgeView'
        # objects>`). Pickle's qualname lookup for that descriptor
        # found the Python-side `class EdgeView` (different from the
        # Rust type that owns the descriptor) and crashed with
        # PicklingError("not the same object as
        # franken_networkx.EdgeView"). Same class-shadowing pattern
        # as br-r37-c1-{cip5m, k66wf, neb6c, 2vxhk, ld4oo, 8crof}.
        # Snapshot the materialized list at pickle time — restore as
        # a plain list (matches nx's snapshot semantics on the
        # restored EdgeDataView).
        return (list, (list(self._materialize()),))

    def __copy__(self):
        # br-r37-c1-vcopy (cycle 212): copy.copy(G.edges.data())
        # returns EdgeDataView in nx (live wrapper).  fnx previously
        # fell through to ``__reduce__``-driven snapshot → plain
        # list.  Live wrapper matches nx.
        return self

    def __deepcopy__(self, memo):
        # SNAPSHOT semantics — independent of subsequent G mutations.
        # Materialise edges + attrs into a new fnx Graph, return its
        # EdgeView.data() so type EdgeDataView is preserved AND
        # mutations don't leak.
        snapshot = self._materialize()
        G_new = Graph()
        if isinstance(self._data, bool) and self._data:
            # snapshot is [(u, v, attrs), ...]
            G_new.add_edges_from(snapshot)
        elif isinstance(self._data, bool):
            # data=False: snapshot is [(u, v), ...]
            G_new.add_edges_from(snapshot)
        else:
            # data='attr': snapshot is [(u, v, value_or_default), ...]
            # Reconstruct attrs dict.
            for u, v, value in snapshot:
                G_new.add_edge(u, v, **{self._data: value})
        return G_new.edges.data(
            data=self._data,
            default=self._default,
        )


def _edge_view_call_with_nbunch_first(edge_view_call):
    _unset = object()

    def wrapped(self, *args, **kwargs):
        # br-r37-c1-aq6jv: short-circuit the overwhelmingly common call shape —
        # ONE positional list nbunch, with at most a `data=` keyword. The
        # normalisation below is general enough to cover single-node, tuple-key,
        # str/bytes and three-positional forms, and paid ~2.5us per call to
        # establish that none of them applies. A `list` cannot be a node (it is
        # unhashable), so every one of those questions has a known answer here.
        # Everything the fast path skips is a CHECK, not work: the resulting
        # EdgeDataView is constructed with exactly the same arguments.
        if type(args) is tuple and not args:
            if not kwargs:
                return edge_view_call(self, data=False, nbunch=None, default=None)
            if len(kwargs) == 1 and "data" in kwargs:
                data_kw = kwargs["data"]
                if data_kw is False:
                    return edge_view_call(self, data=False, nbunch=None, default=None)
                return EdgeDataView(
                    edge_view_call,
                    self,
                    data=data_kw,
                    default=None,
                    nbunch_list=None,
                )
        if type(args) is tuple and len(args) == 1 and type(args[0]) is list:
            if not kwargs:
                return EdgeDataView(
                    edge_view_call, self, data=False, default=None, nbunch_list=args[0]
                )
            if len(kwargs) == 1 and "data" in kwargs:
                return EdgeDataView(
                    edge_view_call,
                    self,
                    data=kwargs["data"],
                    default=None,
                    nbunch_list=args[0],
                )
        nbunch = kwargs.pop("nbunch", _unset)
        data = kwargs.pop("data", _unset)
        default = kwargs.pop("default", _unset)
        if kwargs:
            unexpected = next(iter(kwargs))
            # br-r37-c1-callerrqual: nx qualifies this error with the
            # view's class name — e.g. ``OutEdgeView.__call__() got
            # an unexpected keyword argument 'badarg'``.
            raise TypeError(
                f"{type(self).__name__}.__call__() got an unexpected "
                f"keyword argument '{unexpected}'"
            )

        if len(args) > 3:
            raise TypeError(
                f"__call__() takes from 1 to 4 positional arguments but {len(args) + 1} were given"
            )
        if len(args) >= 1:
            if nbunch is not _unset:
                raise TypeError("__call__() got multiple values for argument 'nbunch'")
            nbunch = args[0]
        if len(args) >= 2:
            if data is not _unset:
                raise TypeError("__call__() got multiple values for argument 'data'")
            data = args[1]
        if len(args) == 3:
            if default is not _unset:
                raise TypeError("__call__() got multiple values for argument 'default'")
            default = args[2]

        if nbunch is _unset:
            nbunch = None
        if data is _unset:
            data = False
        if default is _unset:
            default = None
        # br-edgesnb: nx.EdgeView accepts a single node as nbunch
        # (yielding edges incident to that node). The Rust edge_view_call
        # expects None or an iterable; a single node like `u = 0` raised
        # TypeError: 'int' object is not iterable. Detect single-node
        # nbunch by trying to iterate it; fall back to `[nbunch]`.
        nbunch_list = None
        single_node_nbunch = False
        if nbunch is not None:
            owner = _EDGE_VIEW_GRAPH_OWNER.get(id(self))
            # br-r37-c1-m7mbh: nx.nbunch_iter checks ``if nbunch in self``
            # FIRST, so a hashable nbunch that is itself a node (e.g. a
            # tuple key like ``(0, 0)`` in grid_2d_graph) is treated as a
            # single node — NOT iterated into its components.  fnx only
            # special-cased str/bytes and non-iterables, so a tuple node
            # got split into ``[0, 0]`` and ``G.edges((0, 0))`` returned
            # ``[]``.  Detect the whole-nbunch-is-a-node case up front to
            # mirror nx's contract for tuple-keyed (and any hashable
            # iterable) node graphs.  ``x in owner`` swallows TypeError
            # for unhashable nbunch (lists/sets) and returns False, so
            # those fall through to sequence handling unchanged.
            whole_is_node = False
            # br-r37-c1-aq6jv: a `list` is UNHASHABLE, so it can never be a node
            # key — the membership probe below could only ever raise TypeError
            # and be swallowed. Raising and catching an exception on every
            # ordinary `G.edges([...])` call is pure overhead, and the list form
            # is the common one. Sets/dicts are equally unhashable but rarer, so
            # they keep the general path rather than growing the check.
            if (
                owner is not None
                and type(nbunch) is not list
                and not isinstance(nbunch, (str, bytes))
            ):
                try:
                    whole_is_node = nbunch in owner
                except TypeError:
                    whole_is_node = False
            if whole_is_node:
                nbunch = [nbunch]
            else:
                try:
                    iter(nbunch)
                    if isinstance(nbunch, (str, bytes)):
                        # br-edgesnb (legacy): fnx wraps strings as
                        # single-node nbunch for ergonomics — nx
                        # iterates string chars instead.  Preserve
                        # the silent-skip behaviour for missing
                        # string nodes (do NOT mark as single_node)
                        # to stay drop-in compatible with both nx's
                        # silent-iteration AND fnx's existing
                        # string-node handling.
                        nbunch = [nbunch]
                except TypeError:
                    # True single non-iterable (int, etc) — nx raises
                    # NetworkXError on missing node; see
                    # br-r37-c1-edges-snnb below.
                    nbunch = [nbunch]
                    single_node_nbunch = True
            # Materialize nbunch so we can both pass it to Rust and use
            # it to reorder the returned edge tuples below.
            nbunch_list = [n for n in nbunch]
            # br-r37-c1-edges-snnb: nx's EdgeView with a SINGLE
            # non-iterable hashable nbunch raises ``NetworkXError(f"Node
            # {n} is not in the graph.")`` when the node is missing —
            # distinct from the silent-skip contract for an iterable
            # nbunch (``G.edges([99])`` returns []).  fnx previously
            # wrapped single-node nbunch into ``[nbunch]`` and lost the
            # distinction, silently returning ``[]``.  Validate against
            # the owning graph for the single-node case to restore
            # nx's typed-error contract.
            if single_node_nbunch and nbunch_list:
                if owner is not None and nbunch_list[0] not in owner:
                    raise NetworkXError(
                        f"Node {nbunch_list[0]} is not in the graph."
                    )
        # When data is non-False or nbunch is given, return a live
        # EdgeDataView wrapper (br-r37-c1-sf1ku) instead of a list
        # snapshot. The wrapper re-invokes edge_view_call on each access.
        if nbunch_list is not None or data is not False:
            return EdgeDataView(
                edge_view_call,
                self,
                data=data,
                default=default,
                nbunch_list=nbunch_list,
            )
        # data=False, no nbunch — return the live Rust EdgeView directly.
        return edge_view_call(self, data=False, nbunch=None, default=default)

    return wrapped


class NodeDataView:
    """Live view over ``G.nodes(data=...)`` matching nx's NodeDataView
    contract (br-r37-c1-j2vof).

    The Rust NodeView's ``__call__(data=True)`` returns a NodeView
    object (class name ``NodeView``); the data='attr' path used to
    return a Python list. nx returns a ``NodeDataView`` in both cases.
    This wrapper re-invokes the underlying Rust call (or rebuilds the
    attr-projection list) on each access (iter / len / contains / repr)
    so mutations are reflected and class-name introspection matches.
    """

    def __init__(self, node_view_call, view_self, *, data, default):
        self._call = node_view_call
        self._view = view_self
        self._data = data
        self._default = default

    def _materialize(self):
        data = self._data
        default = self._default
        if data is True:
            # br-r37-c1-4b5ie: nodes(data=True) is the (node, attr_dict) items —
            # serve from each class's nodes_seq-keyed node_data_mirror via its
            # native items() (the SAME cache the attr path below uses). Graph was
            # already routed here; DiGraph/MultiGraph/MultiDiGraph fell through to
            # the fresh ``self._call`` rebuild (5.5-9.4x slower than nx). The
            # cached dicts are live so ``for u, d in G.nodes(data=True): d['x']=1``
            # still persists.
            native_items = _NODE_VIEW_NATIVE_ITEMS.get(type(self._view))
            if native_items is not None:
                return native_items(self._view)
        if isinstance(data, bool):
            # Rust path: returns a NodeView; iterate its content directly.
            return list(self._call(self._view, data, default))
        # br-r37-c1-4b5ie: the attr-projection path used ``self._view[node]``
        # PER NODE — a Rust ``NodeView.__getitem__`` PyO3 round-trip x N (~5x nx).
        # Get the live (node, attr_dict) pairs in ONE shot (the native
        # ``_SIMPLE_GRAPH_NODE_VIEW_ITEMS`` fast path for simple graphs, the
        # bulk data=True call otherwise) and project the attribute in Python with
        # the same ``dict.get(data, default)``. Identical node order + values,
        # dicts are live so mutations still reflect — now faster than nx.
        # br-r37-c1-4b5ie: every graph class has a native ``items()`` that
        # serves the (node, attr_dict) pairs from its nodes_seq-keyed
        # node_data_mirror (built once, reused while the node set is unchanged).
        # Route the attr projection through it so Graph/DiGraph/MultiGraph/
        # MultiDiGraph all skip rebuilding the pairs in Python; values + node
        # order are byte-identical (same node_py_attrs source) and the dicts are
        # live so in-place mutations still reflect.
        native_items = _NODE_VIEW_NATIVE_ITEMS.get(type(self._view))
        if native_items is not None:
            pairs = native_items(self._view)
        else:
            pairs = self._call(self._view, True, None)
        return [(node, attrs.get(data, default)) for node, attrs in pairs]

    def __iter__(self):
        return iter(self._materialize())

    def __len__(self):
        # br-r37-c1-9hkgu: a NodeDataView is a bijection with the node set (one
        # (node, data) entry per node), so its length is just the node count —
        # ``len(self._view)`` is O(1) native. The old ``len(self._materialize())``
        # built the entire (node, dict) list a SECOND time on every ``list(view)``
        # (CPython calls __len__ for the size hint, then __iter__), doubling the
        # cost of this very hot view. nx parity: nx.NodeDataView.__len__ is
        # likewise ``len(self._nodes)``.
        return len(self._view)

    def __contains__(self, item):
        # br-r37-c1-nv-hash: mirror nx.NodeDataView.__contains__ —
        # try the bare-node lookup first; if that raises (e.g.
        # unhashable), unpack ``item`` as a (node, data) 2-tuple
        # and check both halves.  This silently handles list-as-
        # 2-tuple-of-(node, data) without false TypeErrors that
        # would otherwise leak from the NodeView hash-check
        # introduced by the same bead.
        # br-r37-c1-ex1s6: but networkx does NOT guard that unpack - an
        # unhashable probe that is not a pair, [0] or (0, 1, {}), raises its
        # ValueError / TypeError; only the hashable-miss unpack below is.
        try:
            node_in = item in self._view
        except TypeError:
            n, d = item
            return n in self._view and self[n] == d
        if node_in is True:
            return True
        try:
            n, d = item
        except (TypeError, ValueError):
            return False
        return n in self._view and self[n] == d

    def __getitem__(self, key):
        # nx NodeDataView supports view[node] -> attrs / value.
        data = self._data
        default = self._default
        if isinstance(data, bool):
            attrs = self._view[key]
            return dict(attrs) if data else None
        return self._view[key].get(data, default)

    def __repr__(self):
        if isinstance(self._data, bool) and not self._data:
            return f"NodeDataView({self._materialize()!r}, data=False)"
        if isinstance(self._data, bool):
            return f"NodeDataView({dict(self._materialize())!r})"
        return f"NodeDataView({dict(self._materialize())!r}, data={self._data!r})"

    def __str__(self):
        # br-r37-c1-mpv5x: nx NodeDataView.__str__ is str(list(self)).
        # br-r37-c1-cxa7j: _materialize() returns dict_items for the cached
        # data=True simple-graph fast path (f4d74a6e9), so str() would render
        # "dict_items([...])" instead of nx's bare "[(n, {...}), ...]". Wrap in
        # list() to match nx for every data form (attr path already returns a
        # list; list() of a list is a cheap copy).
        return str(list(self._materialize()))

    def __eq__(self, other):
        if hasattr(other, "__iter__"):
            return list(self._materialize()) == list(other)
        return NotImplemented

    __hash__ = None

    def __copy__(self):
        # br-r37-c1-vcopy (cycle 212): copy.copy(G.nodes.data())
        # returns NodeDataView in nx (live wrapper). fnx previously
        # fell through to default snapshot → plain list.  Live
        # wrapper matches nx.
        return self

    def __deepcopy__(self, memo):
        # SNAPSHOT semantics — independent of subsequent G mutations.
        # Materialise the underlying view into a new fnx Graph and
        # return ITS NodeDataView so type is preserved AND snapshot
        # is independent.
        snapshot = [(node, dict(self._view[node])) for node in self._view]
        G_new = Graph()
        G_new.add_nodes_from(snapshot)
        return type(self)(
            type(G_new.nodes).__call__,
            G_new.nodes,
            data=self._data,
            default=self._default,
        )

    def __reduce__(self):
        # br-r37-c1-ndv-pkl: NodeDataView holds `self._call`, a
        # wrapper_descriptor on the Rust NodeView type
        # (`<slot wrapper '__call__' of 'franken_networkx.NodeView'
        # objects>`). Pickle's qualname lookup for that descriptor
        # finds `fnx.NodeView` (the Python-side _Mapping subclass at
        # line 23932), sees it's a different class object than
        # `_SIMPLE_GRAPH_NODE_VIEW_TYPE` (the Rust type that owns
        # the descriptor), and crashes with PicklingError("not the
        # same object as franken_networkx.NodeView"). Same
        # class-shadowing pattern as br-r37-c1-{cip5m, k66wf, neb6c}.
        # Snapshot the materialized list at pickle time — restore
        # as a plain list (matches nx's snapshot semantics on
        # restored NodeDataView).
        return (list, (list(self._materialize()),))


def _node_view_call_with_attr_support(node_view_call):
    _unset = object()

    def wrapped(self, *args, **kwargs):
        data = kwargs.pop("data", _unset)
        default = kwargs.pop("default", _unset)
        if kwargs:
            unexpected = next(iter(kwargs))
            # br-r37-c1-callerrqual: nx qualifies this error with
            # the view's class name — e.g. ``NodeView.__call__() got
            # an unexpected keyword argument 'badarg'``.
            raise TypeError(
                f"{type(self).__name__}.__call__() got an unexpected "
                f"keyword argument '{unexpected}'"
            )

        if len(args) > 2:
            raise TypeError(
                f"__call__() takes from 1 to 3 positional arguments but {len(args) + 1} were given"
            )
        if len(args) >= 1:
            if data is not _unset:
                raise TypeError("__call__() got multiple values for argument 'data'")
            data = args[0]
        if len(args) == 2:
            if default is not _unset:
                raise TypeError("__call__() got multiple values for argument 'default'")
            default = args[1]

        if data is _unset:
            data = False
        if default is _unset:
            default = None
        # br-r37-c1-f8gi1: data=False with no kwargs must return a LIVE
        # node view — i.e. ``self`` — so subsequent graph mutations are
        # visible when the captured view is iterated again. Matches nx's
        # NodeView.__call__() returning self. The Rust-side
        # MultiGraphNodeView / MultiDiGraphNodeView ``__call__`` returns
        # a frozen list when invoked through the FFI; bypass it here.
        # Graph and DiGraph were already correct because their Rust
        # ``__call__`` returns self for default args, but uniformly
        # returning ``self`` keeps the contract consistent across all
        # four classes and avoids future drift.
        if data is False:
            return self
        # data=True or data='attr' return a NodeDataView wrapper
        # (br-r37-c1-j2vof).
        return NodeDataView(
            node_view_call, self, data=data, default=default
        )

    return wrapped


def _adjacency_view_get(self, node, default=None):
    try:
        return self[node]
    except KeyError:
        return default


# br-r37-c1-adjviewhoist: these adjacency keys/items/values view classes were
# previously DEFINED INSIDE the ``_adjacency_view_*`` helpers, so a fresh class
# object was built (``__build_class__`` + two ``type.__new__``) on EVERY
# ``.keys()/.items()/.values()`` call. Any algorithm that walks ``G.adj[u].items()``
# (or ``G.succ[u].items()``) per node paid that per-call class-construction tax —
# e.g. ``topological_sort`` was ~34x slower than nx purely from rebuilding
# ``_AdjItemsView`` once per node. Hoisted to module level (closing over the view
# via ``__init__`` instead of a local closure) the classes are built ONCE at import.
# ``__name__`` is set to the bare nx name so drop-in code branching on
# ``type(view).__name__`` still sees ``KeysView``/``ItemsView``/``ValuesView``.
from collections.abc import ItemsView as _ItemsViewABC
from collections.abc import KeysView as _KeysViewABC  # br-r37-c1-dfivn
from collections.abc import ValuesView as _ValuesViewABC  # br-r37-c1-dfivn
from collections.abc import KeysView as _KeysViewABC
from collections.abc import ValuesView as _ValuesViewABC


class _AdjKeysView(_KeysViewABC):
    # nx internals (non_neighbors) do
    # ``graph._adj.keys() - graph._adj[node].keys() - {node}`` expecting
    # dict_keys-like views that support set-difference. The backing object is
    # normally a frozen list; AtlasView supplies its already-live row dict so
    # ``dict(G[u])`` does not first allocate a redundant neighbor-key list.
    __slots__ = ("_snapshot",)

    def __init__(self, snapshot):
        self._snapshot = snapshot

    def __iter__(self):
        return iter(self._snapshot)

    def __contains__(self, item):
        return item in self._snapshot

    def __len__(self):
        return len(self._snapshot)


_AdjKeysView.__name__ = "KeysView"


class _AdjItemsView(_ItemsViewABC):
    """Re-iterable ItemsView matching nx's contract (a one-shot generator would
    leave the second pass of ``G.edges.items()`` empty)."""

    __slots__ = ("_view",)

    def __init__(self, view):
        self._view = view

    def __iter__(self):
        view = self._view
        return ((node, view[node]) for node in view)

    def __contains__(self, item):
        try:
            key, val = item
        except (TypeError, ValueError):
            return False
        view = self._view
        return key in view and view[key] == val

    def __len__(self):
        return len(self._view)


_AdjItemsView.__name__ = "ItemsView"


class _AdjValuesView(_ValuesViewABC):
    """Re-iterable ValuesView matching nx."""

    __slots__ = ("_view",)

    def __init__(self, view):
        self._view = view

    def __iter__(self):
        view = self._view
        return (view[node] for node in view)

    def __contains__(self, value):
        view = self._view
        for node in view:
            if view[node] == value:
                return True
        return False

    def __len__(self):
        return len(self._view)


_AdjValuesView.__name__ = "ValuesView"


def _adjacency_view_keys(self):
    # br-r37-c1-v9auw: concrete Graph/DiGraph AtlasView rows already own a
    # persistent native-maintained PyDict mirror. Hand that mapping directly to
    # KeysView so CPython's ``dict(mapping)`` protocol can iterate its keys
    # without first building ``list(self)`` (which also called _keydict twice,
    # via list's length hint). Other mapping wrappers retain the snapshot path.
    keydict_getter = getattr(self, "_keydict", None)
    if keydict_getter is not None:
        keydict = keydict_getter()
        if keydict is not None:
            return _AdjKeysView(keydict)
    # br-r37-c1-mgkeyslive: a LIVE atlas, not a frozen list. THIS IS A PARITY FIX
    # BEFORE IT IS A PERFORMANCE ONE.
    #
    # A multigraph row (`AdjacencyView`) has no `_keydict`, so it fell to
    # `list(self)` — an O(degree) snapshot taken at `keys()` time. networkx's
    # `KeysView` wraps the live mapping, so a HELD view tracks mutation, and fnx's
    # went stale:
    #
    #     k = G[0].keys()            nx ['1','2']        fnx ['1','2']
    #     G.add_edge(0, 3)           nx ['1','2','3']    fnx ['1','2']   <- stale
    #     G.remove_edge(0, 1)        nx ['2','3']        fnx ['1','2']   <- stale
    #
    # Graph and DiGraph never had this: their rows own a `_keydict` and take the
    # live branch above, which is why the divergence was multigraph-only.
    #
    # `_atlas()` is the memoised row view and it IS live — verified across
    # add_edge, a parallel add, remove_edge and remove_node on both multigraph
    # classes, agreeing with a freshly fetched atlas at every step
    # (br-r37-c1-mgrowatlas). It also supplies the only three operations
    # `_AdjKeysView` asks of its backing object: __iter__, __contains__, __len__.
    #
    # The frozen `list(self)` remains as the last resort for any wrapper that
    # exposes neither `_keydict` nor `_atlas`.
    atlas_getter = getattr(self, "_atlas", None)
    if atlas_getter is not None:
        atlas = atlas_getter()
        if atlas is not None:
            return _AdjKeysView(atlas)
    return _AdjKeysView(list(self))


def _adjacency_view_items(self):
    return _AdjItemsView(self)


def _adjacency_view_values(self):
    return _AdjValuesView(self)


_OBJECT_NEW = object.__new__
