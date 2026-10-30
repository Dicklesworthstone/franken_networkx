

class AtlasView(_Mapping):
    # br-r37-c1-rgmef: True only on a private twin, which makes the
    # shared __getitem__ below build writable rows.
    _fnx_private_rows = False
    # br-r37-c1-ey6ob: class-level defaults for multigraph cells constructed
    # via `_OBJECT_NEW(AtlasView)` in `AdjacencyView.__getitem__`.
    _fnx_owner = None
    _fnx_row_kind = "adj"

    # br-r37-c1-2ndmw: CLASS-LEVEL DEFAULTS for the three fields whose only
    # constructor value is None. An instance attribute that is written solely by
    # a later cache fill can start life on the class: reads resolve to this same
    # None through the normal attribute protocol, and the first write still
    # shadows it per instance. Three STORE_ATTRs leave the constructor, which is
    # 52 percent of a multigraph `G[u][v]` (318.1 ns of 606.5 ns at K=2000) and
    # is paid FRESH on every subscript, because networkx returns a new wrapper
    # per call on a multigraph and caching this view would be a parity break
    # (`row[v] is row[v]` is False in networkx — pinned in
    # test_multigraph_row_view_contract.py).
    #
    # THEY ARE NOT FREE FOR EVERY VIEW, WHICH IS WHY `__init__` STILL STORES
    # THEM ON THE NON-MULTI SHAPE. A class default is a MISS in the instance
    # dict, so every read of a never-written field pays the type-dict fallback
    # on top. That is the right trade for a multigraph CELL, which is
    # constructed per subscript and whose `__getitem__` short-circuits on
    # `_fnx_multi_edge_owner` before touching any of the fields. It is the wrong
    # trade for a simple-graph row (today a Graph or DiGraph SUBCLASS's, or one
    # of a graph with assigned private storage; exact Graph and DiGraph rows are
    # the native AtlasView), which is built once and then reads `_fnx_kd_cache`
    # and `_fnx_edge_fast` on EVERY subscript. Measured when DiGraph rows were
    # still this class: making them unconditionally class-level moved
    # `DiGraph G[u][v]` from 0.4911/0.5185x to 0.4778/0.4627x, a disjoint 4-5
    # percent LOSS, while the multigraph rows gained. The branch below buys the
    # construction saving only where the reads do not pay for it.
    _fnx_kd_cache = None
    _fnx_edge_fast = None
    # br-r37-c1-hotrow: the per-ROW constants of the native fast path, bundled
    # so the hot subscript loads ONE attribute instead of three. Written the
    # first time the fast path resolves, alongside `_fnx_edge_fast`.
    _fnx_hot = None
    # br-r37-c1-2ndmw: the multigraph CELL's resolved atlas — the native
    # `MultiKeyDictView` for one (u, v) pair — memoised on first use.
    #
    # `_atlas_getter` on a cell is `lambda: row._atlas()[v]`, so it RE-RESOLVED
    # the pair through the native row on every single operation, and that
    # resolution is O(node key length) twice over (it canonicalises `v`, hashes
    # both endpoint keys inside `has_edge`, and clones the row key into the new
    # view). Measured on a warm cell, `G[u][v][k]`:
    #
    #     K=3     fnx 769.6 ns   nx  71.0 ns   0.093x   of which _atlas()  423.4
    #     K=2000  fnx 3300.1 ns  nx  51.3 ns   0.018x   of which _atlas() 2933.0
    #
    # so at long keys 89 percent of an edge-attribute read was re-deriving a
    # handle it already had. The `MultiKeyDictView` reads THROUGH to the graph
    # on every call — key add/remove and attribute writes are all visible
    # through a held one — so memoising the handle changes no answer while the
    # pair exists, and where it does change one it moves TOWARD networkx: see
    # `_atlas` below.
    #
    # Class default, not a constructor store, because the cell is constructed
    # per subscript (see the note above); non-cell views store it per instance.
    _fnx_captured_atlas = None

    def __init__(
        self,
        atlas_getter,
        owner=None,
        row_node=None,
        row_kind="adj",
        multi_edge_owner=None,
    ):
        # br-r37-c1-2ndmw: these were KEYWORD-ONLY, and the star cost more than
        # every attribute store put together. Measured on this interpreter
        # (3.13.7), the identical body called with four keywords is 262.3 ns and
        # positionally is 130.1 ns — 132 ns of pure name matching on a call that
        # networkx answers end to end in 129.9 ns. They stay keyword-ACCEPTING,
        # so no existing call site changes meaning; only the hot multigraph cell
        # construction in `AdjacencyView.__getitem__` passes positionally.
        self._atlas_getter = atlas_getter
        self._fnx_owner = owner
        self._fnx_row_node = row_node
        self._fnx_row_kind = row_kind
        # br-r37-c1-u4gjj: an AtlasView nested below a concrete multigraph row
        # represents one edge pair's {key: attrs} mapping. Iterating the native
        # MultiKeyDictView materializes its key vector on every call; retain a
        # keys-only dict on this already-lazy public view so repeated iteration
        # is a C-level dict iterator. Values still come from _atlas(), keeping
        # live edge-attribute identity and avoiding hidden attr materialization.
        self._fnx_multi_edge_owner = multi_edge_owner
        # br-r37-c1-spg9n: ((nodes_seq, edges_seq), keydict) — the row's
        # {nbr: <value>} keydict, cached on the (already per-node-cached) view so
        # iteration/len/membership are pure-Python dict ops like nx's
        # iter/len/in over self._adj[n] (3-5x slower -> parity). The keydict is
        # the same object the graph-level row cache holds; both rebuild on any
        # structural change (nodes_seq/edges_seq token).
        #   `_fnx_kd_cache` — class default None, see above.
        # br-r37-c1-ey6ob: memoised owner._fnx_edge_attr_dict_fast. None = not
        # looked up yet, False = looked up and absent, else the bound method.
        #   `_fnx_edge_fast` — class default None, see above.
        if multi_edge_owner is None:
            # Not a multigraph cell: this view will be read many times per
            # construction, so pay the stores once and keep every later read
            # an instance-dict hit. See the class-default note above.
            self._fnx_kd_cache = None
            self._fnx_edge_fast = None
            self._fnx_hot = None
            # NOT `_fnx_captured_atlas`: only a cell ever reads it, and `_atlas`
            # checks `_fnx_multi_edge_owner` before it, so a non-cell view never
            # touches the attribute at all and does not need the store.

    def _atlas(self):
        # br-r37-c1-2ndmw: serve the memoised cell atlas. Only a multigraph cell
        # ever fills this, and only after its first resolution, so a view whose
        # getter genuinely re-evaluates keeps re-evaluating.
        #
        # AND IT IS A PARITY FIX, not only a cost one. When the LAST parallel
        # edge of a pair is removed, networkx's `G[u][v]` keeps serving the
        # keydict object it captured — empty — because an `AtlasView` in
        # networkx holds the dict itself:
        #
        #     nx   after removing every key:  sorted(cell) == []   cell[0] -> KeyError(0)
        #     fnx  before this change:        sorted(cell) -> KeyError('b')
        #
        # fnx re-resolved the pair, found it gone, and raised the ROW's KeyError
        # from an operation on a cell the caller already holds. Holding the
        # native view instead reproduces networkx exactly, including the key in
        # the error. The re-add case still diverges (networkx shows the stale
        # empty dict where fnx shows the new keys), and it diverged identically
        # before this change — it is not introduced here.
        # THE MULTI CHECK COMES FIRST, and the order is measured, not stylistic.
        # `_atlas()` is shared by every AtlasView in the module, so a memo probe
        # ahead of it charges two extra attribute reads to views that can never
        # fill it. Reading `_fnx_captured_atlas` first cost the `DiGraph G[u][v]`
        # control 0.5149x -> 0.4702x, a disjoint 9 percent on a row this lever
        # does not touch. Gating on `_fnx_multi_edge_owner` — already an
        # instance attribute every other method on this class reads — leaves the
        # non-cell path at ONE extra read and no extra store.
        if self._fnx_multi_edge_owner is not None:
            atlas = self._fnx_captured_atlas
            if atlas is None:
                getter = self._atlas_getter
                if type(getter) is AdjacencyView:
                    row = getter._fnx_captured_row
                    atlas = (getter._atlas() if row is None else row)[self._fnx_row_node]
                else:
                    atlas = getter()
                self._fnx_captured_atlas = atlas
            return atlas
        getter = self._atlas_getter
        if type(getter) is AdjacencyView:
            row = getter._fnx_captured_row
            return (getter._atlas() if row is None else row)[self._fnx_row_node]
        return getter()

    def _multi_edge_keydict(self, materialize):
        # br-r37-c1-2ndmw: WARM PATH FIRST, and `materialize` is positional now.
        #
        # This helper is what `__len__`, `__iter__`, `__contains__` and `keys()`
        # all go through on a multigraph cell, and it re-ran the full guard set
        # on every one of them. Decomposed on a warm cell, `len(cell)` is
        # 349.7 ns against networkx's 51.0 ns, and 265.0 ns of that is this
        # call:
        #
        #     _has_networkx_private_storage(owner)   ~77 ns   (a CALL frame)
        #     type(owner) not in (MG, MDG)           ~49 ns
        #     (owner.nodes_seq, owner.edges_seq)     ~48 ns   (two PyO3 getters)
        #     the keyword-only `materialize`         ~30 ns
        #     len(keydict) itself                     17.5 ns
        #
        # THE TYPE CHECK IS SKIPPABLE ON THE WARM PATH, and the reason is an
        # invariant rather than an optimism: a non-None `_fnx_kd_cache` on a
        # view whose `_fnx_multi_edge_owner` is not None can ONLY have been
        # written by the cold path below, which checks the type against THIS
        # same owner object — and an object's type does not change under it.
        # (`_keydict` reaches its own non-multi cache fill only when
        # `_fnx_multi_edge_owner` IS None, so the two never share an entry.)
        # Pinned by test_warm_keydict_is_only_reachable_after_the_cold_guards.
        #
        # THE PRIVATE-STORAGE CHECK IS NOT SKIPPABLE, because an nx-compatible
        # `_adj` can be assigned to the owner AFTER this cache was filled, and
        # then the row's authority changes. It stays — inlined, because the
        # helper's own comment records that ~30 ns of its 91.9 ns is the call
        # frame, and this is the one place that calls it per element access.
        owner = self._fnx_multi_edge_owner
        cached = self._fnx_kd_cache
        if cached is not None and owner is not None:
            storage = owner.__dict__
            if not (
                _PRIVATE_NODE_OVERRIDE in storage
                or _PRIVATE_ADJ_OVERRIDE in storage
                or _PRIVATE_SUCC_OVERRIDE in storage
                or _PRIVATE_PRED_OVERRIDE in storage
            ):
                try:
                    if cached[0] == (owner.nodes_seq, owner.edges_seq):
                        return cached[1]
                except AttributeError:
                    return None
        if owner is None or (cached is None and not materialize):
            return None
        if type(owner) not in (MultiGraph, MultiDiGraph):
            return None
        if _has_networkx_private_storage(owner):
            return None
        try:
            token = (owner.nodes_seq, owner.edges_seq)
        except AttributeError:
            return None
        if cached is not None and cached[0] == token:
            return cached[1]
        if not materialize:
            return None
        keydict = dict.fromkeys(self._atlas())
        self._fnx_kd_cache = (token, keydict)
        return keydict

    def _keydict(self):
        if self._fnx_multi_edge_owner is not None:
            return self._multi_edge_keydict(True)
        owner = self._fnx_owner
        if owner is None:
            return None
        try:
            tok = (owner.nodes_seq, owner.edges_seq)
        except AttributeError:
            return None
        cached = self._fnx_kd_cache
        if cached is not None and cached[0] == tok:
            return cached[1]
        keydict = _cached_adj_row_keydict(
            owner, self._fnx_row_kind, self._fnx_row_node, self._atlas
        )
        if keydict is not None:
            # Token-checked: this class serves only subclass and
            # private-storage rows now, where the untokened live row that exact
            # Graph/DiGraph rows hold (br-r37-c1-v9auw) does not apply.
            self._fnx_kd_cache = (tok, keydict)
        return keydict

    def __len__(self):
        # MEASURED AND REJECTED: routing a simple row's length to
        # `len(self._atlas())`. The atlas cost 383.0ns against the keydict's
        # 64.6ns on the same row, so that "simplification" would have been a
        # 3.6x REGRESSION. The body below picks the cheaper of the two.
        if self._fnx_multi_edge_owner is not None:
            # Do not pay the owner/private/token helper on the cold length-only
            # path: the native exact-size method is the shipped 118-153x seam.
            if self._fnx_kd_cache is not None:
                keydict = self._multi_edge_keydict(False)
                if keydict is not None:
                    return len(keydict)
            return len(self._atlas())
        keydict = self._keydict()
        if keydict is not None:
            return len(keydict)
        return len(self._atlas())

    def __iter__(self):
        keydict = self._keydict()
        if keydict is not None:
            return iter(keydict)
        return iter(self._atlas())

    def __contains__(self, node):
        # nx: ``v in G[u]`` is ``v in self._adj[u]`` (dict membership; hashes v,
        # TypeError on unhashable). Serve from the keydict so it is pure-Python.
        if self._fnx_multi_edge_owner is not None:
            if self._fnx_kd_cache is not None:
                keydict = self._multi_edge_keydict(False)
                if keydict is not None:
                    return node in keydict
            try:
                self._atlas()[node]
            except KeyError:
                # br-r37-c1-ex1s6: the native view answers KeyError for an
                # unhashable key too; networkx's dict raises TypeError.
                _HASH_PROBE.get(node)
                return False
            except TypeError:
                _HASH_PROBE.get(node)
                raise
            return True
        keydict = self._keydict()
        if keydict is not None:
            return node in keydict
        try:
            self._atlas()[node]
        except KeyError:
            _HASH_PROBE.get(node)
            return False
        except TypeError:
            _HASH_PROBE.get(node)
            raise
        return True

    def __getitem__(self, node):
        # The multiedge cache is keys-only by design; values must continue to
        # come from the live native view so G[u][v][key] retains the exact edge
        # attribute dict object.
        if self._fnx_multi_edge_owner is not None:
            try:
                atlas = self._fnx_captured_atlas
                if atlas is None:
                    atlas = self._atlas()
                return atlas[node]
            except KeyError:
                _HASH_PROBE.get(node)  # br-r37-c1-ex1s6: as __contains__
                raise
            except TypeError:
                _HASH_PROBE.get(node)
                raise
        # br-r37-c1-spg9n: G[u][v] edge-attr access. The cached row keydict's
        # VALUES are the live edge_py_attrs dicts (keydict[v] is G[u][v]; attr
        # mutations reflect), so serve from it — pure-Python dict lookup, no PyO3
        # round-trip, identity-preserving. keydict[node] raises KeyError(node)
        # with the original key, matching nx's self._adj[u][v].
        #
        # br-r37-c1-atlasget (cc): serve from an ALREADY-WARM keydict (pure
        # Python, covers iterated/repeated rows), else take a single-edge O(1)
        # native fast path INSTEAD of building the whole row keydict. Distinct
        # G[u][v] (the common `for u, v in G.edges(): G[u][v][...]` pattern) was
        # 0.04x vs nx precisely because each cold access built u's entire row
        # (O(degree)); the single-edge fetch returns the SAME live edge_py_attrs
        # dict materialize_edge_py_attrs(u, v) caches, so identity + mutation
        # reflection match the keydict path exactly.
        owner = self._fnx_owner
        cached = self._fnx_kd_cache
        if cached is not None and owner is not None:
            try:
                if cached[0] == (owner.nodes_seq, owner.edges_seq):
                    return cached[1][node]
            except (AttributeError, TypeError):
                pass
        if owner is not None:
            # br-r37-c1-ey6ob: resolve the single-edge accessor ONCE per row view
            # instead of on every subscript. A `getattr(owner, name, None)` costs
            # about 70 ns against ~16 ns for a plain attribute load, and it ran on
            # every `G[u][v]` — the largest single component of the Python frame
            # around a 204 ns native call. `False` is the "looked and it is not
            # there" sentinel, so an owner without the accessor is not re-probed
            # either. This is the binding AdjacencyView already does for
            # `native_len` / `native_iter`, applied one level down.
            # br-r37-c1-hotrow: read the bundled per-row constants. This block
            # used to load `_fnx_edge_fast`, `_fnx_row_kind` and
            # `_fnx_row_node` separately on EVERY subscript, and all three are
            # fixed for the life of the row. Bundling them costs one tuple at
            # first use and turns three attribute loads into one plus an unpack.
            hot = self._fnx_hot
            if hot is not None:
                fast, row_node, is_pred = hot
                _HASH_PROBE.get(node)  # nx's TypeError, and nx's WORDING for it
                d = fast(node, row_node) if is_pred else fast(row_node, node)
                if d is not None:
                    return d
                raise KeyError(node)
            fast = self._fnx_edge_fast
            if fast is None:
                fast = getattr(owner, "_fnx_edge_attr_dict_fast", None)
                self._fnx_edge_fast = False if fast is None else fast
            if fast:
                _HASH_PROBE.get(node)  # nx's TypeError, and nx's WORDING for it
                row_node = self._fnx_row_node
                is_pred = self._fnx_row_kind == "pred"
                # Bundle for every later subscript on this row.
                self._fnx_hot = (fast, row_node, is_pred)
                d = fast(node, row_node) if is_pred else fast(row_node, node)
                if d is not None:
                    return d
                raise KeyError(node)
        keydict = self._keydict()
        if keydict is not None:
            return keydict[node]
        return self._atlas()[node]

    def __repr__(self):
        # br-r37-c1-k147g: nx.AtlasView prints the underlying mapping
        # (e.g. ``AtlasView({1: {}})``); without an explicit __repr__
        # Python falls back to ``<franken_networkx.AtlasView object at 0x...>``.
        return f"AtlasView({dict(self._atlas())!r})"

    def __str__(self):
        # br-r37-c1-mpv5x: nx.AtlasView.__str__ returns the bare dict
        # ('{1: {}}'), not the wrapped repr.
        return str(dict(self._atlas()))

    def copy(self):
        """br-atlascp: nx.AtlasView has a dict-style copy(). nx internals
        like ``to_dict_of_dicts`` do ``nbrdict.copy()`` on the adj value,
        which crashed on fnx because AtlasView lacked the method. Return
        a plain dict snapshot of the underlying mapping.
        """
        return {
            k: v.copy() if hasattr(v, "copy") else dict(v) if hasattr(v, "items") else v
            for k, v in self._atlas().items()
        }

    def __reduce__(self):
        # br-r37-c1-viewpkl: the `_atlas_getter` is a closure over a
        # graph descriptor, which pickle cannot serialize (lambdas /
        # local functions). nx's matching views pickle as snapshots of
        # the underlying dict; match that contract by reconstructing
        # via a module-level factory that wraps the snapshot.
        return (_reconstruct_atlas_view, (self.copy(),))


# br-r37-c1-ey6ob: warm `AtlasView`'s PEP 412 `ht_cached_keys` via `__init__`
# once at import so `_OBJECT_NEW(AtlasView)` in `AdjacencyView.__getitem__`
# writes into inline values (`STORE_ATTR_INSTANCE_VALUE`) instead of de-sharing
# the class keys table.
AtlasView(None, None, None, "adj", True)

# The native Graph-row route below implements the full mapping protocol in
# Rust. ``#[pyclass(mapping)]`` sets CPython's mapping flag, but does not make
# an extension type a virtual ``collections.abc.Mapping`` subclass on its own.
# Register it once so callers see the same abstract type as NetworkX's view.
_Mapping.register(_fnx.AtlasView)


class _MultiEdgeKeydict(dict):
    """A multigraph edge's keydict: ``G.get_edge_data(u, v)`` / ``G._adj[u][v]``.

    br-r37-c1-rc0923-epic-honest-measurement-vbneu.3. networkx returns its own
    storage dict here, so this is a real ``dict``: json, pickle, copy, ``|`` and
    ``isinstance(d, dict)`` behave as in networkx (pickle/copy give a plain
    ``dict``, like networkx's). The graph keeps its contents in step with every
    edge mutation (from Rust, through the C-level dict API, which bypasses the
    overrides below). Writes made through it are forwarded to the graph —
    inserting a key adds an edge, deleting one removes it — as they are in
    networkx. Once the graph drops it (node removal, ``clear``, the pair's last
    edge removed through the graph) ``_fnx_graph`` is ``None`` and it is an
    ordinary dict.
    """

    __slots__ = ("_fnx_graph", "_fnx_u", "_fnx_v")

    def __init__(self, *args, **kwargs):
        self._fnx_graph = None
        dict.__init__(self, *args, **kwargs)

    def __setitem__(self, key, datadict):
        graph = self._fnx_graph
        if graph is None:
            dict.__setitem__(self, key, datadict)
        else:
            graph._fnx_keydict_store(self._fnx_u, self._fnx_v, key, datadict)

    def __delitem__(self, key):
        graph = self._fnx_graph
        if graph is None:
            dict.__delitem__(self, key)
        else:
            graph._fnx_keydict_remove(self, self._fnx_u, self._fnx_v, key)

    def pop(self, key, *default):
        if len(default) > 1:
            raise TypeError(f"pop expected at most 2 arguments, got {1 + len(default)}")
        if key in self:
            datadict = self[key]
            del self[key]
            return datadict
        if default:
            return default[0]
        raise KeyError(key)

    def popitem(self):
        if not self:
            raise KeyError("popitem(): dictionary is empty")
        key = next(reversed(self))
        datadict = self[key]
        del self[key]
        return key, datadict

    def clear(self):
        for key in list(self):
            del self[key]

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = {} if default is None else default
        return self[key]

    def update(self, other=(), /, **kwargs):
        if hasattr(other, "keys"):
            for key in other.keys():
                self[key] = other[key]
        else:
            for key, datadict in other:
                self[key] = datadict
        for key, datadict in kwargs.items():
            self[key] = datadict

    def __ior__(self, other):
        self.update(other)
        return self

    def __reduce__(self):
        return (dict, (dict(self),))


_fnx._set_multigraph_keydict_class(_MultiEdgeKeydict)


class _EdgeAttrDict(dict):
    """An edge's attribute dict: ``G[u][v]``, ``G.edges[u, v]``,
    ``G.get_edge_data(u, v)``, the dicts ``G.edges(data=True)`` yields.

    br-r37-c1-urjxk. networkx's is a plain ``dict``; this one reports every
    write to its graph, which keeps a Rust copy of the attributes for its
    native kernels. A caller can keep the dict and write it at any later time
    - ``d = G[u][v]; shortest_path_length(G, ...); d["weight"] = 5`` - and the
    kernels went on reading the copy they had synced before the write. Reads,
    ``isinstance(d, dict)``, json, ``|``, ``d.copy()``, pickle and ``copy``
    behave as networkx's (the copies are plain ``dict``s); ``type(d) is dict``
    is False, as it already is for the multigraph keydict.
    """

    __slots__ = ()
    _fnx_watch = None

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        if self._fnx_watch is not None:
            self._fnx_watch.note(self)

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        if self._fnx_watch is not None:
            self._fnx_watch.note(self)

    def pop(self, key, *default):
        value = dict.pop(self, key, *default)
        if self._fnx_watch is not None:
            self._fnx_watch.note(self)
        return value

    def popitem(self):
        item = dict.popitem(self)
        if self._fnx_watch is not None:
            self._fnx_watch.note(self)
        return item

    def setdefault(self, key, default=None):
        if key in self:
            return dict.__getitem__(self, key)
        dict.__setitem__(self, key, default)
        if self._fnx_watch is not None:
            self._fnx_watch.note(self)
        return default

    def update(self, *args, **kwargs):
        dict.update(self, *args, **kwargs)
        if self._fnx_watch is not None:
            self._fnx_watch.note(self)

    def clear(self):
        dict.clear(self)
        if self._fnx_watch is not None:
            self._fnx_watch.note(self)

    def __ior__(self, other):
        dict.update(self, other)
        if self._fnx_watch is not None:
            self._fnx_watch.note(self)
        return self

    def __reduce__(self):
        return (dict, (dict(self),))

    def __deepcopy__(self, memo):
        # br-r37-c1-uwvq4: what copy.deepcopy makes of networkx's plain dict
        # (copy._deepcopy_dict: a new plain dict, registered in the memo before
        # its items are copied) - __reduce__ reached the same through a
        # reconstruction at twice the cost.
        copied = {}
        memo[id(self)] = copied
        for key, value in dict.items(self):
            copied[_deepcopy(key, memo)] = _deepcopy(value, memo)
        return copied


class _SlottedEdgeAttrDict(_EdgeAttrDict):
    __slots__ = ("_fnx_watch",)

    def __init__(self, *args, **kwargs):
        self._fnx_watch = None
        dict.__init__(self, *args, **kwargs)


# networkx's edge attr dict is a dict, and type(G[u][v]).__name__ says so -
# code that reports a value's type (and the held-row parity locks) reads the
# name. Pickle and copy never look the class up by name: __reduce__ hands
# them a plain dict.
_EdgeAttrDict.__name__ = _EdgeAttrDict.__qualname__ = "dict"
_SlottedEdgeAttrDict.__name__ = _SlottedEdgeAttrDict.__qualname__ = "dict"
_fnx._set_edge_attr_dict_class(_EdgeAttrDict, _SlottedEdgeAttrDict)


def _graph_is_filtered(graph, _depth=0):
    """True when nx would be serving this graph through a FilterAtlas.

    ``_FilteredGraphView`` is defined much further down this module, so it is
    looked up at call time rather than captured at import.

    A reverse view wrapping a subgraph keeps the filtered wording — nx's
    reverse is a thin relabelling over the same filtered adjacency — so the
    ``_graph`` chain is walked. The depth cap is a cycle guard, not a limit
    anyone should be reaching.
    """
    filtered_cls = globals().get("_FilteredGraphView")
    if filtered_cls is not None and isinstance(graph, filtered_cls):
        return True
    base = getattr(graph, "_graph", None)
    if base is not None and base is not graph and _depth < 4:
        return _graph_is_filtered(base, _depth + 1)
    return False


def _atlas_is_filtered(atlas):
    """Recognize filtered atlases even through nested public view wrappers."""
    filtered = tuple(
        cls
        for cls in (
            globals().get("_FilteredAdjacencyView"),
            globals().get("_FilteredNeighborMap"),
        )
        if cls is not None
    )
    wrappers = tuple(
        cls
        for cls in (
            globals().get("AdjacencyView"),
            globals().get("MultiAdjacencyView"),
            globals().get("AtlasView"),
        )
        if cls is not None
    )
    seen = set()
    while id(atlas) not in seen:
        if isinstance(atlas, filtered):
            return True
        if not isinstance(atlas, wrappers):
            return False
        # Filtered multigraph rows can have two public AdjacencyView layers,
        # and a simple filtered graph's pred rows two AtlasView layers
        # (br-r37-c1-7jhpr). Only unwrap our known mappings, and stop if an
        # assigned getter cycles.
        seen.add(id(atlas))
        atlas = atlas._atlas()
    return False


def _missing_node_key_error(graph, node, atlas=None):
    """br-r37-c1-k4nsd: the KeyError nx raises for an absent node.

    nx has two different wordings and fnx had them exactly SWAPPED — the
    filtered views said the bare key where nx says "Key n not found", and the
    reverse view said "Key n not found" where nx says the bare key:

        graph              probe            networkx                fnx (before)
        G.subgraph(...)    adj['zzz']       KeyError('Key zzz ...') KeyError('zzz')
        G.reverse()        adj['zzz']       KeyError('zzz')         KeyError('Key zzz ...')

    A plain graph raises the bare key in both, which is why the wording has to
    be decided per graph rather than per class: fnx's AdjacencyView serves
    plain AND filtered graphs, so it cannot simply pick one.

    The bare-key form also preserves the key's TYPE (int / tuple / ...) in
    ``args``, which br-keystr deliberately established; the filtered form is a
    formatted string in nx too, so both sides match nx exactly.
    """
    if _graph_is_filtered(graph) or (atlas is not None and _atlas_is_filtered(atlas)):
        return KeyError(f"Key {node} not found")
    return KeyError(node)


class AdjacencyView(_Mapping):
    # br-r37-c1-rgmef: True only on a private twin, which makes the
    # shared __getitem__ below build writable rows.
    _fnx_private_rows = False

    def __init__(
        self,
        atlas_getter,
        *,
        owner=None,
        row_kind="adj",
        native_len=None,
        native_iter=None,
        multi_edge_owner=None,
    ):
        self._atlas_getter = atlas_getter
        self._fnx_owner = owner
        self._fnx_row_kind = row_kind
        # br-r37-c1-u4gjj: metadata only, not an outer-row cache. It lets a
        # captured G[u][v] AtlasView cache that pair's key iteration while this
        # AdjacencyView remains live across structural edge updates.
        self._fnx_multi_edge_owner = multi_edge_owner
        # br-r37-c1-9ias7: (nodes_seq, edges_seq) -> the dict.fromkeys snapshot
        # __iter__ has to build for the dict_keyiterator type contract. It was
        # rebuilt on EVERY iteration of the same row, which is what made
        # list(MultiGraph.adj[u]) 0.307x while the simple-graph row — whose
        # native iterator skips fromkeys entirely — was already 0.951x.
        self._fnx_keys_snapshot = None
        # br-r37-c1-4rgsf: outer simple-graph adjacency views bind the raw
        # PyO3 node-count descriptor once. ``len(G.adj)`` is exactly the native
        # adjacency owner count, so avoid rebuilding the native adjacency
        # wrapper through _atlas_getter on every call. Inner row, filtered,
        # reverse, reconstructed, and snapshot views pass no native_len and
        # retain the mapping fallback below.
        self._fnx_native_len = native_len
        # br-r37-c1-krg59: the native Graph/DiGraph node iterator already
        # serves a live ``dict_keyiterator`` over the incrementally maintained
        # node-key mirror. Outer simple adjacency has exactly the same key set,
        # so bind that raw descriptor once instead of rebuilding an O(N)
        # ``dict.fromkeys`` merely to recover the same iterator runtime type.
        # Ownerless, filtered, reverse, reconstructed, and snapshot views pass
        # no native iterator and retain the mapping fallback.
        self._fnx_native_iter = native_iter
        # br-r37-c1-spg9n: (nodes_seq, {node: AtlasView}) cache. The returned
        # AtlasView reads its row live from Rust, so it stays valid across EDGE
        # changes; only node add/remove (which bumps nodes_seq) needs a fresh
        # one. Lets repeated G[n] / G.adj[n] skip the per-call existence probe +
        # AtlasView construction (6x slower than nx -> parity).
        self._fnx_atlas_cache = None
        # br-r37-c1-fr4me: the CAPTURED row, when the getter is known to be a
        # constant. br-r37-c1-znpkv's multigraph rows are built as
        # ``AdjacencyView(lambda row=native(node): row)`` — a closure that
        # returns the same object forever — and reaching it cost TWO Python
        # frames per membership test, ``_atlas()`` plus the lambda itself.
        # Holding the row directly removes both. Set by the caller that knows
        # the getter is constant; every other view leaves it None and keeps the
        # getter, because their getters genuinely re-evaluate.
        self._fnx_captured_row = None

    def _atlas(self):
        row = self._fnx_captured_row
        if row is not None:
            return row
        return self._atlas_getter()

    def __len__(self):
        native_len = self._fnx_native_len
        if native_len is not None:
            return native_len()
        # br-r37-c1-mgrowatlas: inline the captured-row memo that `_atlas()`
        # reads on its own first line. `len()` slot-dispatches into this Python
        # frame and the body then spent a SECOND Python frame in `_atlas()` to
        # do nothing but return an attribute it had already stored.
        #
        # Measured on a MultiGraph row, per call: len(row) 131.7ns against
        # networkx's 64.2ns (0.49x), with `_atlas()` alone costing 54.5ns of
        # that and `len(self._fnx_captured_row)` costing 56.2ns - i.e. the memo
        # is already warm and the frame was most of the gap.
        #
        # The memo is filled before the first `__len__` and stays LIVE: verified
        # across add_edge, a parallel add, remove_edge and remove_node on both
        # multigraph classes, with the captured object still agreeing with
        # networkx and with a freshly fetched atlas at every step. `_atlas()`
        # already returns that same object (`r._atlas() is r._atlas()` is True),
        # so this is a frame removal, not a new cache and not a liveness change.
        row = self._fnx_captured_row
        if row is not None:
            return len(row)
        return len(self._atlas())

    def __iter__(self):
        native_iter = self._fnx_native_iter
        if native_iter is not None:
            return native_iter()
        # br-r37-c1-adjitype (cycle 219): nx's ``AdjacencyView.__iter__``
        # returns ``iter(self._atlas)`` where ``_atlas`` is a Python
        # dict, yielding a ``dict_keyiterator``.  fnx's ``_atlas()``
        # returns a Rust-bound view whose ``__iter__`` returns
        # ``NodeIterator`` — diverging on ``type(iter(G.adj)).__name__``.
        # Sister of cycle 218 (br-r37-c1-nbritype) for
        # ``neighbors``/``successors``/``predecessors``.  Materialise
        # via ``dict.fromkeys`` so the iterator runtime type is
        # ``dict_keyiterator``.
        #
        # br-r37-c1-9ias7: that fromkeys is an O(degree) dict build and it ran
        # on EVERY iteration of the same row. Snapshot it against the graph's
        # (nodes_seq, edges_seq) revision, which moves on any structural change
        # to the key set; an attribute write cannot change the keys, so it
        # correctly does not invalidate. Only a row that knows its owner can be
        # keyed this way — the rest keep the unconditional rebuild.
        owner = self._fnx_multi_edge_owner
        if owner is not None:
            try:
                token = (owner.nodes_seq, owner.edges_seq)
            except AttributeError:
                return iter(dict.fromkeys(self._atlas()))
            cached = self._fnx_keys_snapshot
            if cached is not None and cached[0] == token:
                return iter(cached[1])
            keys = dict.fromkeys(self._atlas())
            self._fnx_keys_snapshot = (token, keys)
            return iter(keys)
        return iter(dict.fromkeys(self._atlas()))

    def __contains__(self, node):
        # br-r37-c1-hcn5w: answer membership from the ROW, not by building a
        # value. Without this, `v in G.adj[u]` fell through to the Mapping ABC,
        # whose __contains__ is `try: self[key]` — so a membership test
        # constructed the whole inner keydict view and threw it away. That was
        # 1.18us of the 1.6us on MultiGraph, and it is why `v in G.adj[u]`
        # (0.244x) was worse than the len() next to it.
        #
        # br-r37-c1-i9whv contract: an UNHASHABLE key is nx's TypeError, not
        # False. The explicit hash is required, not decorative — the native
        # atlas's own __contains__ answers False for an unhashable argument, so
        # delegating alone REGRESSED the multigraphs (they used to raise via
        # the ABC's __getitem__, which hashed on the way to building the value).
        # It also fixes simple Graph, which answered False here before this
        # change because the ABC's except clause catches only KeyError.
        #
        # br-r37-c1-fr4me: on a CAPTURED row, go straight at it. cProfile put
        # this whole lookup at four Python frames on a multigraph — this
        # __contains__, MultiAdjacencyView.__getitem__, _atlas() and the
        # capture lambda — against ONE on simple Graph, whose row is a native
        # view with a C-level contains slot. Two of those four are pure
        # indirection: _atlas() is `return self._atlas_getter()` and the getter
        # is a closure over a fixed object. The row lookup was never the cost;
        # the frames were.
        #
        # br-r37-c1-mh4sg: a CAPTURED row no longer needs the explicit hash.
        # The native MultiAtlasView / MultiDiAtlasView used to answer False for
        # an unhashable key rather than raising — the same gap br-r37-c1-espyz
        # closed on the simple AtlasView — so this line WAS the TypeError
        # contract and removing it first would have been a silent parity
        # regression bought with 66 ns. They now carry the guard themselves, so
        # the captured path raises from the view and the hash is genuinely
        # redundant there.
        #
        # The fallback keeps it. `_atlas()` can return shapes whose membership
        # guarantee has not been established one by one, and a contract that
        # holds only for the paths someone happened to check is not a contract.
        row = self._fnx_captured_row
        if row is not None:
            return node in row
        _HASH_PROBE.get(node)
        return node in self._atlas()

    def __getitem__(self, node):
        # br-r37-c1-ey6ob: on a captured public multigraph row (where
        # `_fnx_captured_row` is set and `_fnx_owner` / `_fnx_private_rows` are
        # None / False), check membership directly against the captured row and
        # construct the fresh `AtlasView` cell via `_OBJECT_NEW(AtlasView)` + 3
        # inline-value attribute stores without allocating a closure per call.
        atlas = self._fnx_captured_row
        if atlas is not None:
            if node not in atlas:
                try:
                    atlas[node]
                except KeyError as exc:
                    raise _missing_node_key_error(self._fnx_owner, node, atlas=atlas) from exc
            view = _OBJECT_NEW(AtlasView)
            view._atlas_getter = self
            view._fnx_row_node = node
            view._fnx_multi_edge_owner = self._fnx_multi_edge_owner
            return view
        # br-r37-c1-spg9n: warm fast-path — a token-valid cached AtlasView for
        # this row is returned directly (the view live-reads its row from Rust,
        # so it reflects later edge changes; the nodes_seq token only drops it on
        # node add/remove). ``cache.get(node)`` hashes ``node`` so unhashable
        # nodes raise TypeError exactly as nx's ``self._adj[node]`` does.
        owner = self._fnx_owner
        cache = self._fnx_atlas_cache
        if owner is not None:
            seq = owner.nodes_seq
            if cache is None or cache[0] != seq:
                cache = (seq, {})
                self._fnx_atlas_cache = cache
            view = cache[1].get(node)
            if view is not None:
                return view
        # br-r37-c1-i9whv: hash-check for nx-shaped TypeError on
        # unhashable nodes (instead of falling through to KeyError).
        #
        # br-r37-c1-2ndmw: LOAD-BEARING ON THE FALLBACK, and the reason is not
        # only unhashable keys — a `_atlas()` whose membership contract has not
        # been established one by one cannot be trusted to raise, and a contract
        # that holds only for the paths someone happened to check is not a
        # contract. So the getter path keeps it.
        _HASH_PROBE.get(node)
        atlas = self._atlas()
        # br-r37-c1-2ndmw: ask for EXISTENCE, do not build a value to throw away.
        #
        # This was `atlas[node]` inside a bare try, used purely as a presence
        # probe with its result discarded. On a multigraph row the atlas is a
        # native `MultiAtlasView` whose `__getitem__` allocates a whole
        # `MultiKeyDictView` (cloning this row's node key on the way), and the
        # `AtlasView` built below re-derives that exact value lazily through
        # its own getter — so the object was constructed, dropped, and then
        # constructed again on first use. Measured on the multigraph cell at
        # 2000-character keys, the discarded construction was 830.4 ns of a
        # 1724.4 ns call: 48.2 percent of the work went into an object nobody
        # ever read. `in` answers the same question through `has_edge` without
        # materialising anything.
        #
        # THE ABSENT PATH IS DELIBERATELY UNCHANGED. It still goes through
        # `__getitem__`, so the exception, its args and the `from exc`
        # chaining are exactly what they were — this is why `in` is never
        # trusted to construct the error, and why a `__contains__` that
        # disagreed with `__getitem__` in the absent direction still produces
        # the right exception. Only the PRESENT path changes, and only by not
        # building a value that was already being thrown away.
        if node not in atlas:
            try:
                atlas[node]
            except KeyError as exc:
                # br-keystr: preserve the original key type (int/tuple/...)
                # in the KeyError args instead of the Rust side's str repr.
                # br-r37-c1-k4nsd: ...unless the atlas underneath is a FILTERED
                # one, which already raised nx's FilterAtlas wording — flattening
                # that to the bare key is what made subgraphs disagree with nx.
                # The atlas is inspected rather than the caught message, because
                # a message-based test could not tell nx's wording apart from a
                # Rust-side str repr, which is exactly what br-keystr must keep
                # rewriting.
                raise _missing_node_key_error(owner, node, atlas=atlas) from exc
        if self._fnx_private_rows:
            if type(owner) is Graph and not _has_networkx_private_storage(owner):
                # br-r37-c1-rgmef: Graph's public row is the NATIVE AtlasView
                # (br-r37-c1-ey6ob's C-slot win), so its private twin has to be a
                # subclass of that same native type — anything else would make the
                # private row's read methods differ from the public row's, which
                # test_private_adj_read_path_stays_native.py forbids by
                # measurement. This is what the `subclass` attribute on the
                # pyclass was added for; the flag is certified at no cost on G[u]
                # (1.1587x before / 1.1580x after vs networkx, common-mode 0.9999).
                view = _private_writable_class(_fnx.AtlasView)(owner, node)
                # 2b0a6eb64 moved this call into the sibling branches and left
                # this one without it: Graph._adj[u][v] = ... then raised
                # "this private view has no owning graph to write to".
                _private_mark_child(self, view, owner, node)
            elif type(owner) is DiGraph and not _has_networkx_private_storage(owner):
                # The public DiGraph row is the native AtlasView too, so its
                # private twin is the same writable subclass, on the same side.
                view = _private_writable_class(_fnx.AtlasView)(
                    owner, node, self._fnx_row_kind == "pred"
                )
                _private_mark_child(self, view, owner, node)
            elif (
                getattr(self, "_fnx_multi_edge_owner", None) is not None
                or (owner is not None and getattr(owner, "is_multigraph", lambda: False)())
            ):
                multigraph_owner = (
                    getattr(self, "_fnx_write_owner", None)
                    or self._fnx_multi_edge_owner
                    or owner
                )
                parent_node = getattr(self, "_fnx_write_node", None)
                if parent_node is not None and not _has_networkx_private_storage(multigraph_owner):
                    if getattr(self, "_fnx_write_kind", "adj") == "pred":
                        return multigraph_owner.get_edge_data(node, parent_node)
                    return multigraph_owner.get_edge_data(parent_node, node)
                if parent_node is not None and getattr(self, "_fnx_write_kind", "adj") == "pred":
                    storage = vars(multigraph_owner)
                    if (
                        _PRIVATE_PRED_OVERRIDE not in storage
                        and (
                            _PRIVATE_ADJ_OVERRIDE in storage
                            or _PRIVATE_SUCC_OVERRIDE in storage
                        )
                    ):
                        # Replacing only forward storage leaves this side
                        # native. Public get_edge_data reads the assigned
                        # forward pair, so obtain the native predecessor's
                        # actual live keydict instead of wrapping it.
                        target = storage.get(_SHARED_STORAGE_SOURCE, multigraph_owner)
                        get_data = _private_native_method(target, _RAW_GET_EDGE_DATA_BY_CLASS)
                        if get_data is not None:
                            return get_data(target, node, parent_node)
                view = _private_writable_class(AtlasView)(
                    lambda: self._atlas()[node],
                    owner=owner,
                    row_node=node,
                    row_kind=self._fnx_row_kind,
                    multi_edge_owner=self._fnx_multi_edge_owner,
                )
                _private_mark_child(self, view, owner, node)
            else:
                # br-r37-c1-rgmef: identical read construction, writable class.
                view = _private_writable_class(AtlasView)(
                    lambda: self._atlas()[node],
                    owner=owner,
                    row_node=node,
                    row_kind=self._fnx_row_kind,
                    multi_edge_owner=self._fnx_multi_edge_owner,
                )
                _private_mark_child(self, view, owner, node)
        elif type(owner) is Graph and not _has_networkx_private_storage(owner):
            # br-r37-c1-ey6ob: the native AtlasView owns a C-level
            # ``__getitem__`` slot, so the cold G[u][v] path avoids the
            # Python AtlasView frame while retaining the same persistent row
            # mirror for Mapping-wide operations and detached-row parity.
            view = _fnx.AtlasView(owner, node)
        elif type(owner) is DiGraph and not _has_networkx_private_storage(owner):
            # The same native row for a DiGraph's successor or predecessor
            # side, under the same class name networkx uses for both. The
            # Python AtlasView's frame was the whole directed/undirected gap
            # on G[u][v] (br-r37-c1-ktsxn, br-r37-c1-ey6ob).
            view = _fnx.AtlasView(owner, node, self._fnx_row_kind == "pred")
        else:
            # br-r37-c1-2ndmw: POSITIONAL. Same five arguments, same order as the
            # signature; keyword matching alone was 132 ns of this 606.5 ns call.
            view = AtlasView(
                lambda: self._atlas()[node],
                owner,
                node,
                self._fnx_row_kind,
                self._fnx_multi_edge_owner,
            )
        if owner is not None:
            cache[1][node] = view
        return view

    def __repr__(self):
        # br-r37-c1-k147g: print the underlying mapping like nx does.
        return f"AdjacencyView({self.copy()!r})"

    def __str__(self):
        # br-r37-c1-mpv5x: bare-dict str like nx.
        return str(self.copy())

    def copy(self):
        """br-adjcp: nx.to_dict_of_dicts does ``nbrdict.copy()`` on the
        adjacency value; AdjacencyView (used for MultiGraph inner) had
        no copy() method. Return a plain dict-of-dicts snapshot.
        """
        return {
            k: v.copy() if hasattr(v, "copy") else dict(v) if hasattr(v, "items") else v
            for k, v in self._atlas().items()
        }

    def __reduce__(self):
        # br-r37-c1-viewpkl: see AtlasView.__reduce__.
        return (_reconstruct_adjacency_view, (self.copy(),))


_MULTI_NATIVE_ROW_ATTR = {
    "adj": "_native_adjacency_row",
    "succ": "_native_successor_row",
    "pred": "_native_predecessor_row",
}


def _register_held_multigraph_row(graph, node, row):
    """Keep retired-cache rows reachable without keeping them alive (u8rs5)."""
    storage = vars(graph)
    registry = storage.get("_fnx_held_multigraph_rows")
    if registry is None:
        registry = {}
        storage["_fnx_held_multigraph_rows"] = registry
        graph._fnx_register_gc_dict(storage)
    bucket = registry.get(node)
    if bucket is None:
        bucket = {}
        registry[node] = bucket
    row_id = id(row)

    def expired(reference):
        if bucket.get(row_id) is reference:
            bucket.pop(row_id)
        # A removed/re-added node may already have a different bucket.
        if not bucket and registry.get(node) is bucket:
            registry.pop(node)

    bucket[row_id] = _weakref.ref(row, expired)


class MultiAdjacencyView(_Mapping):
    # br-r37-c1-rgmef: True only on a private twin, which makes the
    # shared __getitem__ below build writable rows.
    _fnx_private_rows = False

    def __init__(
        self,
        atlas_getter,
        *,
        owner=None,
        row_kind="adj",
        native_iter=None,
        native_contains=None,
        native_len=None,
    ):
        self._atlas_getter = atlas_getter
        # br-r37-c1-znpkv: per-row view cache, keyed on nodes_seq — the same
        # shape AdjacencyView has carried since br-r37-c1-spg9n. G.adj[u] built
        # a fresh AdjacencyView AND a fresh closure on every subscript, which
        # was 0.70us of the 0.88us that made MultiGraph len(G.adj[u]) the worst
        # row on the surface at 0.219x.
        self._fnx_row_cache = None
        # br-r37-c1-spg9n: the owning graph, for cheap membership/len/contains
        # without materialising the whole {node:{nbr:{key:attrs}}} dict. Sparse:
        # the pickle reconstructor + reverse views pass owner=None and keep the
        # _atlas() fallback.
        self._fnx_owner = owner
        self._fnx_row_kind = row_kind
        # br-r37-c1-spg9n: which native per-row binding to use for G.adj[u] so
        # the inner row view fetches ONLY node u's row (not the whole adjacency).
        self._fnx_native_row_attr = _MULTI_NATIVE_ROW_ATTR.get(row_kind)
        # br-r37-c1-yisq4: outer multigraph adjacency keys are exactly the
        # owner's live node-key mirror. Bind its raw dict iterator once so
        # __iter__ need not rebuild an O(N) dict merely to recover NetworkX's
        # ``dict_keyiterator`` type. Ownerless/private/snapshot views omit it.
        self._fnx_native_iter = native_iter
        # br-r37-c1-7icpc: outer multigraph adjacency membership is native
        # node-key membership. Bind the raw owner descriptor once so ``n in
        # G.adj`` skips the graph's private-node-aware ``__contains__`` wrapper.
        # An independent ``_node`` override must not change adjacency keys;
        # ownerless/private-adjacency views omit this binding and keep the
        # mapping fallback.
        self._fnx_native_contains = native_contains
        # br-r37-c1-2r06n: the raw, UNSHADOWED node count — the `__len__` twin of
        # the `native_contains` binding above, and bound for the same reason.
        self._fnx_native_len = native_len

    def _atlas(self):
        return self._atlas_getter()

    def __len__(self):
        # nx: len(G.adj) == number of nodes. Avoid materialising _atlas().
        #
        # br-r37-c1-2r06n: through the RAW count, not `owner.number_of_nodes()`.
        # That method is shadowed on any instance carrying private storage, so it
        # answered an assigned `_node` mapping while `__iter__` went on yielding
        # the adjacency's own keys — `len(view) != len(list(view))` on one
        # object, across all four MultiAdjacencyView users. The two numbers are
        # equal on an ordinary graph, so this is the same answer there, reached
        # without the shadow lookup.
        native_len = self._fnx_native_len
        if native_len is not None:
            return native_len()
        owner = self._fnx_owner
        if owner is not None:
            return owner.number_of_nodes()
        return len(self._atlas())

    def __contains__(self, node):
        # nx: ``n in G.adj`` is ``n in self._adj`` (dict membership) — hashes n
        # and raises TypeError on unhashable (unlike ``n in G`` which returns
        # False). hash() first to preserve that, then route node membership to
        # the owner so it is O(1) instead of rebuilding the entire multigraph
        # adjacency dict per check (was ~3ms/check => nbunch_iter 11000x slower).
        _HASH_PROBE.get(node)
        native_contains = self._fnx_native_contains
        if native_contains is not None:
            return native_contains(node)
        owner = self._fnx_owner
        if owner is not None:
            return node in owner
        return node in self._atlas()

    def __iter__(self):
        native_iter = self._fnx_native_iter
        if native_iter is not None:
            return native_iter()
        # br-r37-c1-adjitype (cycle 219): nx's iter(G.adj) is a dict_keyiterator.
        # The keys of G.adj are just the NODES, so build {node: None} from the
        # owner's node iteration (O(V)) instead of materialising the entire
        # {node:{nbr:{key:attrs}}} dict via _atlas() (O(V+E), was ~640x slower
        # than nx). dict.fromkeys(...) keeps the dict_keyiterator type that
        # ``iter(self._fnx_owner)`` (a NodeIterator) would lose.
        owner = self._fnx_owner
        if owner is not None:
            return iter(dict.fromkeys(owner))
        return iter(dict.fromkeys(self._atlas()))

    def __getitem__(self, node):
        # br-r37-c1-i7jta: probe the per-row cache FIRST. Everything this used
        # to do ahead of the cache — an explicit hash, a full `node not in
        # owner` graph-membership probe, and a getattr for the native row
        # binding — is work the cache has already answered, because a cached row
        # is EXISTENCE PROOF: rows are only cached for nodes that had one, and
        # every node removal bumps `nodes_seq`, which is the key. Same ordering
        # argument as br-r37-c1-do7g5 on `_native_adjacency_row_dict` and
        # br-r37-c1-dlqkq on `G.degree(n)`. The simple `AdjacencyView` above has
        # been cache-first since br-r37-c1-spg9n and measured 0.685x against
        # networkx where this one measured 0.337x.
        #
        # The br-r37-c1-i9whv TypeError contract survives the reorder because
        # `dict.get` hashes its argument, so an unhashable node raises TypeError
        # here exactly as the explicit `hash` did; the slow path below keeps the
        # explicit `hash` for the cache-stale and owner-less cases.
        owner = self._fnx_owner
        if owner is not None:
            cache = self._fnx_row_cache
            if cache is not None and cache[0] == owner.nodes_seq:
                view = cache[1].get(node)
                if view is not None:
                    return view
        # br-r37-c1-i9whv: hash-check for nx-shaped TypeError parity.
        _HASH_PROBE.get(node)
        # br-r37-c1-rgmef: chosen once per COLD lookup. The warm-cache return
        # above has already fired, so a cached row never reaches this.
        _row_cls = (
            _private_writable_class(AdjacencyView)
            if self._fnx_private_rows
            else AdjacencyView
        )
        if owner is not None:
            # br-r37-c1-ka7fd: membership must be tested against the ADJACENCY,
            # not the node view. networkx's `G.adj` IS `_adj`, so `G.adj[x]`
            # raises exactly when x has no adjacency row. Those two agree on an
            # ordinary graph, but an assigned `G._node = {...}` makes the node
            # view report the assigned mapping while `_adj` keeps the native
            # rows — and then this rejected 'a', a node with a real row, because
            # 'a' was absent from the override. `G.edges()` came back empty as a
            # result. Fall back to the adjacency before raising.
            if node not in owner and node not in self._atlas():
                raise KeyError(node)
            # br-r37-c1-spg9n: return a row view backed by the kind-specific
            # native per-row binding (the same one G[u] uses) so len/iter/
            # membership on G.adj[u] fetch ONLY u's row instead of rebuilding the
            # whole multigraph adjacency (len(G.adj[u]) / v in G.adj[u] were
            # ~3ms each => 16000x / 7000x slower than nx).
            native = (
                getattr(owner, self._fnx_native_row_attr, None)
                if self._fnx_native_row_attr is not None
                else None
            )
            if native is not None:
                # br-r37-c1-znpkv: the row view live-reads its row through the
                # native binding on every access, so it stays correct across
                # EDGE churn; only a node add/remove can invalidate it, and
                # nodes_seq keys the cache on exactly that. Same contract the
                # simple AdjacencyView has used since br-r37-c1-spg9n.
                cache = self._fnx_row_cache
                seq = owner.nodes_seq
                if cache is None or cache[0] != seq:
                    cache = (seq, {})
                    self._fnx_row_cache = cache
                view = cache[1].get(node)
                if view is None:
                    # br-r37-c1-znpkv: CAPTURE the row rather than re-fetching
                    # it on every access, the same move br-r37-c1-124xl made on
                    # the G[u][v] path. The returned object is a native
                    # MultiAtlasView that stays LIVE across edge churn, so a
                    # captured row still sees a later add_edge/remove_edge; node
                    # mutation advances nodes_seq and drops this cache, which is
                    # what stops a captured row outliving its node. Without the
                    # capture every len()/contains on the SAME cached view
                    # crossed the PyO3 boundary again.
                    captured = native(node)
                    native_row_iter = (
                        getattr(
                            owner,
                            "_native_predecessors_iter"
                            if self._fnx_row_kind == "pred"
                            else "_native_neighbors_iter",
                            None,
                        )
                        if not _has_networkx_private_storage(owner)
                        else None
                    )
                    view = _row_cls(
                        (lambda row=captured: row),
                        row_kind=self._fnx_row_kind,
                        multi_edge_owner=owner,
                        native_iter=(
                            (lambda fn=native_row_iter, n=node: fn(n))
                            if native_row_iter is not None
                            else None
                        ),
                    )
                    if self._fnx_private_rows:
                        _private_mark_writable(
                            view, owner, node, _private_parent_kind(self)
                        )
                    else:
                        # br-r37-c1-fr4me: the getter above is a closure over a
                        # FIXED object, so hand the row itself to the view and let
                        # membership skip both _atlas() and the lambda.
                        view._fnx_captured_row = captured
                    cache[1][node] = view
                    _register_held_multigraph_row(owner, node, view)
                return view
            row_view = _row_cls(
                lambda: self._atlas()[node],
                multi_edge_owner=owner,
            )
            if self._fnx_private_rows:
                _private_mark_writable(row_view, owner, node, _private_parent_kind(self))
            return row_view
        atlas = self._atlas()
        try:
            row = atlas[node]
        except KeyError as exc:
            # br-r37-c1-k4nsd: multigraph sibling of the AdjacencyView fix —
            # this is the owner-less path, which is the one a subgraph takes.
            raise _missing_node_key_error(owner, node, atlas=atlas) from exc
        # A private filtered row already supplies the exact lazy iterator.
        # Wrapping it again would turn that iterator into a fromkeys snapshot.
        if not self._fnx_private_rows and type(row) is AdjacencyView and row._fnx_native_iter is not None:
            return row
        row_view = _row_cls(lambda: self._atlas()[node])
        if self._fnx_private_rows:
            _private_mark_writable(row_view, owner, node, _private_parent_kind(self))
        return row_view

    def __repr__(self):
        # br-r37-c1-k147g: print the underlying mapping like nx does.
        return f"MultiAdjacencyView({self.copy()!r})"

    def __str__(self):
        # br-r37-c1-mpv5x: bare-dict str like nx.
        return str(self.copy())

    def copy(self):
        """br-adjcp: snapshot the multigraph adjacency as a plain
        dict-of-dicts-of-dicts, recursively.
        """
        out = {}
        atlas = self._atlas()
        for u, nbrs in atlas.items():
            inner = {}
            for v, keyed in nbrs.items():
                inner[v] = dict(keyed) if hasattr(keyed, "items") else keyed
            out[u] = inner
        return out

    def __reduce__(self):
        # br-r37-c1-viewpkl: see AtlasView.__reduce__.
        return (_reconstruct_multi_adjacency_view, (self.copy(),))


def _reconstruct_atlas_view(snapshot):
    """Module-level pickle reconstructor for AtlasView. Wraps the
    snapshot dict in a fresh AtlasView so the type is preserved across
    pickle roundtrips (matching nx's behavior). Live-tracking is lost
    by design — the original graph descriptor reference can't survive
    pickling."""
    return AtlasView(lambda: snapshot)


def _reconstruct_adjacency_view(snapshot):
    """Module-level pickle reconstructor for AdjacencyView."""
    return AdjacencyView(lambda: snapshot)


def _reconstruct_multi_adjacency_view(snapshot):
    """Module-level pickle reconstructor for MultiAdjacencyView."""
    return MultiAdjacencyView(lambda: snapshot)


# br-r37-c1-b3cnf: nx uses @cached_property for view accessors so
# ``g.adj is g.adj`` returns True. Cache the wrapper view on the
# instance via a fnx-managed slot so repeat access returns the same
# object (matching nx's identity-preservation contract). Subgraph
# views and the underlying Rust descriptor still see live data —
# the cache only memoizes the Python wrapper instance.
def _cached_view(slot, factory):
    def _accessor(self):
        cache = vars(self)
        view = cache.get(slot)
        if view is None:
            view = factory(self)
            cache[slot] = view
        return view
    return _accessor


def _native_len_adjacency_view(native_base):
    """br-r37-c1-5gam7: an ``AdjacencyView`` whose ``__len__`` is a C slot.

    ``G.nodes`` and ``G.edges`` already expose ``__len__`` as a
    wrapper_descriptor while ``G.adj``'s was a plain Python function — on the
    SAME graph, returning the SAME count. 48.5 ns of an 85.6 ns ``len(G.adj)``
    was the Python frame alone; the PyO3 call inside it was 10.5 ns.

    This SUBCLASSES the native view rather than returning it, so the MRO puts
    the native C slots ahead of the Python definitions while everything else —
    ``_fnx_atlas_cache``, the native-iter binding, ``keys``/``items``/
    ``values``, ``__eq__``, ``copy``, and pickling via
    ``_reconstruct_adjacency_view`` — still comes from ``AdjacencyView`` with
    no reimplementation.

    Only ``__len__`` (and ``__bool__``, which agrees) is wanted from the native
    base. Every other method it happens to define is bound back explicitly
    below, because inheriting those would silently drop Python behaviour:
    ``__getitem__`` would lose ``_fnx_atlas_cache`` and hand back a native
    AtlasView instead of the parity one, ``__iter__`` would lose the
    ``dict_keyiterator`` runtime type nx returns, and ``__repr__``/``__str__``
    would lose the nx-shaped mapping text.

    Used ONLY at the two outer construction sites below. Filtered, reverse,
    reconstructed, snapshot and inner-row views keep the pure-Python class and
    its ``native_len``-is-None fallback.
    """

    class _NativeLenAdjacencyView(native_base, AdjacencyView):
        def __new__(cls, atlas_getter, *, owner=None, **kwargs):
            # The native base's ``__new__`` takes the owning graph; it is what
            # installs the handle the C ``__len__`` reads.
            return native_base.__new__(cls, owner)

        def __init__(self, atlas_getter, **kwargs):
            AdjacencyView.__init__(self, atlas_getter, **kwargs)

        __getitem__ = AdjacencyView.__getitem__
        __iter__ = AdjacencyView.__iter__
        __repr__ = AdjacencyView.__repr__
        __str__ = AdjacencyView.__str__
        __contains__ = _Mapping.__contains__

    _NativeLenAdjacencyView.__name__ = "AdjacencyView"
    _NativeLenAdjacencyView.__qualname__ = "AdjacencyView"
    return _NativeLenAdjacencyView


def _native_len_multi_adjacency_view(native_base):
    """br-r37-c1-m1k0q: a `MultiAdjacencyView` whose `__len__` is a C slot.

    The multigraph twin of `_native_len_adjacency_view`. `len(MultiGraph.adj)`
    was 0.781x networkx while `len(DiGraph.adj)` was 1.386x — same operation,
    same number — because only the simple classes got the C-slot `__len__`.

    ONLY `__len__` (and `__bool__`, which agrees) is wanted from the native base.
    Every other method is bound back explicitly, because inheriting them would
    drop Python behaviour the multigraph view owns: the per-row cache, the
    private-storage-aware `__contains__`, and the nx-shaped repr.
    """

    class _NativeLenMultiAdjacencyView(native_base, MultiAdjacencyView):
        def __new__(cls, atlas_getter, *, owner=None, **kwargs):
            return native_base.__new__(cls, owner)

        def __init__(self, atlas_getter, **kwargs):
            MultiAdjacencyView.__init__(self, atlas_getter, **kwargs)

        __getitem__ = MultiAdjacencyView.__getitem__
        __iter__ = MultiAdjacencyView.__iter__
        __contains__ = MultiAdjacencyView.__contains__
        __repr__ = MultiAdjacencyView.__repr__

    _NativeLenMultiAdjacencyView.__name__ = "MultiAdjacencyView"
    _NativeLenMultiAdjacencyView.__qualname__ = "MultiAdjacencyView"
    return _NativeLenMultiAdjacencyView


_MULTIGRAPH_NATIVE_LEN_ADJ_VIEW = _native_len_multi_adjacency_view(
    _fnx.MultiAdjacencyLenView
)
_MULTIDIGRAPH_NATIVE_LEN_ADJ_VIEW = _native_len_multi_adjacency_view(
    _fnx.MultiDiAdjacencyLenView
)


_GRAPH_NATIVE_LEN_ADJ_VIEW = _native_len_adjacency_view(_fnx.AdjacencyView)
_DIGRAPH_NATIVE_LEN_ADJ_VIEW = _native_len_adjacency_view(_fnx.DiAdjacencyView)


_GRAPH_ADJ_NATIVE_LEN = Graph.number_of_nodes
_DIGRAPH_ADJ_NATIVE_LEN = DiGraph.number_of_nodes
# br-r37-c1-l7ww9: NOT `Graph.__iter__`. Assigning `_node` replaces the node
# mapping but not the adjacency, so an adjacency view must keep reporting native
# keys; `__iter__` now honours the override itself, and this is the raw
# iteration it used to be before the wrapper was deleted.
_GRAPH_ADJ_NATIVE_ITER = Graph._fnx_native_node_iter
_DIGRAPH_ADJ_NATIVE_ITER = DiGraph._fnx_native_node_iter
_MULTIGRAPH_ADJ_NATIVE_ITER = MultiGraph._fnx_native_node_iter
_MULTIDIGRAPH_ADJ_NATIVE_ITER = MultiDiGraph._fnx_native_node_iter
_MULTIGRAPH_ADJ_NATIVE_CONTAINS = MultiGraph.has_node
_MULTIDIGRAPH_ADJ_NATIVE_CONTAINS = MultiDiGraph.has_node
# br-r37-c1-2r06n: the raw node count, bound for the same reason as the raw
# `has_node` above. `owner.number_of_nodes()` is SHADOWED on any instance
# carrying private storage, so it answers the assigned `_node` mapping -- while
# `__iter__` keeps yielding the adjacency's own keys, which an independent
# `_node` override must not change. len(view) then disagreed with
# len(list(view)) on the same object.
_MULTIGRAPH_ADJ_NATIVE_LEN = MultiGraph.number_of_nodes
_MULTIDIGRAPH_ADJ_NATIVE_LEN = MultiDiGraph.number_of_nodes


_multigraph_adj_view = _cached_view(
    "_fnx_view_adj",
    lambda self: _MULTIGRAPH_NATIVE_LEN_ADJ_VIEW(
        lambda: _MULTIGRAPH_ADJ_DESCRIPTOR.__get__(self, MultiGraph),
        owner=self,
        native_iter=_MULTIGRAPH_ADJ_NATIVE_ITER.__get__(self, MultiGraph),
        native_contains=_MULTIGRAPH_ADJ_NATIVE_CONTAINS.__get__(self, MultiGraph),
        native_len=_MULTIGRAPH_ADJ_NATIVE_LEN.__get__(self, MultiGraph),
    ),
)


_graph_adj_view = _cached_view(
    "_fnx_view_adj",
    lambda self: _GRAPH_NATIVE_LEN_ADJ_VIEW(
        lambda: _GRAPH_ADJ_DESCRIPTOR.__get__(self, Graph),
        owner=self,
        row_kind="adj",
        native_len=_GRAPH_ADJ_NATIVE_LEN.__get__(self, Graph),
        native_iter=_GRAPH_ADJ_NATIVE_ITER.__get__(self, Graph),
    ),
)


_digraph_adj_view = _cached_view(
    "_fnx_view_adj",
    lambda self: _DIGRAPH_NATIVE_LEN_ADJ_VIEW(
        lambda: _DIGRAPH_ADJ_DESCRIPTOR.__get__(self, DiGraph),
        owner=self,
        row_kind="succ",
        native_len=_DIGRAPH_ADJ_NATIVE_LEN.__get__(self, DiGraph),
        native_iter=_DIGRAPH_ADJ_NATIVE_ITER.__get__(self, DiGraph),
    ),
)


_multidigraph_adj_view = _cached_view(
    "_fnx_view_adj",
    lambda self: _MULTIDIGRAPH_NATIVE_LEN_ADJ_VIEW(
        lambda: _MULTIDIGRAPH_ADJ_DESCRIPTOR.__get__(self, MultiDiGraph),
        owner=self,
        row_kind="succ",
        native_iter=_MULTIDIGRAPH_ADJ_NATIVE_ITER.__get__(self, MultiDiGraph),
        native_contains=_MULTIDIGRAPH_ADJ_NATIVE_CONTAINS.__get__(
            self, MultiDiGraph
        ),
        native_len=_MULTIDIGRAPH_ADJ_NATIVE_LEN.__get__(self, MultiDiGraph),
    ),
)


_digraph_succ_view = _cached_view(
    "_fnx_view_succ",
    lambda self: AdjacencyView(
        lambda: _DIGRAPH_SUCC_DESCRIPTOR.__get__(self, DiGraph),
        owner=self,
        row_kind="succ",
        native_len=_DIGRAPH_ADJ_NATIVE_LEN.__get__(self, DiGraph),
        native_iter=_DIGRAPH_ADJ_NATIVE_ITER.__get__(self, DiGraph),
    ),
)


_digraph_pred_view = _cached_view(
    "_fnx_view_pred",
    lambda self: AdjacencyView(
        lambda: _DIGRAPH_PRED_DESCRIPTOR.__get__(self, DiGraph),
        owner=self,
        row_kind="pred",
        native_len=_DIGRAPH_ADJ_NATIVE_LEN.__get__(self, DiGraph),
        native_iter=_DIGRAPH_ADJ_NATIVE_ITER.__get__(self, DiGraph),
    ),
)


_multidigraph_succ_view = _cached_view(
    "_fnx_view_succ",
    lambda self: MultiAdjacencyView(
        lambda: _MULTIDIGRAPH_SUCC_DESCRIPTOR.__get__(self, MultiDiGraph),
        owner=self,
        row_kind="succ",
        native_iter=_MULTIDIGRAPH_ADJ_NATIVE_ITER.__get__(self, MultiDiGraph),
        native_contains=_MULTIDIGRAPH_ADJ_NATIVE_CONTAINS.__get__(
            self, MultiDiGraph
        ),
        native_len=_MULTIDIGRAPH_ADJ_NATIVE_LEN.__get__(self, MultiDiGraph),
    ),
)


_multidigraph_pred_view = _cached_view(
    "_fnx_view_pred",
    lambda self: MultiAdjacencyView(
        lambda: _MULTIDIGRAPH_PRED_DESCRIPTOR.__get__(self, MultiDiGraph),
        owner=self,
        row_kind="pred",
        native_iter=_MULTIDIGRAPH_ADJ_NATIVE_ITER.__get__(self, MultiDiGraph),
        native_contains=_MULTIDIGRAPH_ADJ_NATIVE_CONTAINS.__get__(
            self, MultiDiGraph
        ),
        native_len=_MULTIDIGRAPH_ADJ_NATIVE_LEN.__get__(self, MultiDiGraph),
    ),
)


# br-r37-c1-rgmef: DiGraph's private twins, each constructed with exactly the
# same arguments as the public view above it. A native-backed view class
# inherits `__new__` from `_fnx.AdjacencyView` and requires those arguments, so
# a twin cannot be cloned from instance state -- it has to be built.


def _private_marked(view, graph, kind="adj"):
    """Mark a top-level private view with the direction it represents.

    The kind is passed in rather than read off the view. `MultiAdjacencyView`
    does not carry `_fnx_row_kind`, so deriving it defaulted every multigraph
    `_pred` twin to "adj" and wrote its edges BACKWARDS -- a bug that reads
    correct at the assignment site and only shows up in `has_edge`.
    """
    return _private_mark_writable(view, graph, None, kind)


_graph_private_adj_view = _cached_view(
    "_fnx_priv_adj",
    lambda self: _private_marked(
        _private_writable_class(_GRAPH_NATIVE_LEN_ADJ_VIEW)(
            lambda: _GRAPH_ADJ_DESCRIPTOR.__get__(self, Graph),
            owner=self,
            row_kind="adj",
            native_len=_GRAPH_ADJ_NATIVE_LEN.__get__(self, Graph),
            native_iter=_GRAPH_ADJ_NATIVE_ITER.__get__(self, Graph),
        ),
        self,
        "adj",
    ),
)
