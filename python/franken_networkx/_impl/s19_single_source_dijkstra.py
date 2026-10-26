

def single_source_dijkstra(G, source, target=None, cutoff=None, weight="weight"):
    """Single-source weighted shortest paths from ``source``.

    Returns ``(distances, paths)`` dicts keyed by node. If ``target`` is
    provided, returns the ``(distance, path)`` to that specific target.
    Mirrors ``networkx.single_source_dijkstra``.
    """
    # NetworkX constructs a source set, including its unhashable-source error.
    sources = {source}
    # Authoritative Python rows must survive view coercion, including cutoffs
    # and callable weights. The path-only entrypoint calls this one too.
    if _point_query_uses_private_rows(G):
        return _multi_source_dijkstra_inproc(
            G, sources, target=target, cutoff=cutoff, weight=weight
        )
    # br-r37-c1-e861i: materialize SubgraphView first (view family).
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-efv3d: the `_graph_has_nonunit_weight` delegation gate was
    # OBSOLETE — its comment ("the Rust single_source_dijkstra ignores the
    # weight attribute") is stale: `_raw_single_source_dijkstra(G, weight=...)`
    # respects weights, and the native path below already reproduces nx's
    # distances, int/float typing, cutoff, and heap-pop order. Forcing every
    # weighted graph through the fnx->nx conversion + nx Python Dijkstra made
    # weighted single_source_dijkstra ~2.6x slower than nx for no reason.
    # Verified byte-exact (repr incl. type+order) on a 50-case int/float/mixed
    # x cutoff x directed sweep. Only the genuinely-unhandleable cases
    # (negative / +inf / non-numeric / callable weight) still delegate, via
    # `_should_delegate_dijkstra_to_networkx`.
    # br-r37-c1-0kvxh: directed multigraphs have a native Dijkstra walk with
    # finalize-order predecessors, so source-wide path queries need not collapse
    # every parallel edge into a temporary DiGraph before answering. The native
    # result carries both dictionaries; single_source_dijkstra_path delegates here
    # and receives the same path dictionary.
    if G.is_directed() and G.is_multigraph() and isinstance(weight, str):
        # br-cc-mgssd-target: with a concrete target and no cutoff,
        # single_source_dijkstra is a single-pair query — route straight to the
        # native MDG target kernels (the SAME byte-exact path/length kernels
        # dijkstra_path/dijkstra_path_length already use for their 45-48x wins)
        # and return ``(distance, path)``, skipping the O(|E|) Python min-weight
        # collapse this branch otherwise pays (0.25x -> ~20x). The kernels decline
        # (return None) on the cases that must delegate, exactly as dijkstra_path
        # relies on; we then fall through to the collapse. Verified byte-exact
        # incl. int/float distance typing (120/120 int+float x targets).
        if target is not None and cutoff is None:
            if source not in G:
                raise NodeNotFound(f"Node {source} not found in graph")
            if target not in G:
                raise NetworkXNoPath(f"No path to {target}.")
            # br-r37-c1-04z53.9172: same bypass as dijkstra_path/_length.
            if _should_delegate_dijkstra_to_networkx(G, weight):
                return _multi_source_dijkstra_inproc(
                    G, {source}, target=target, cutoff=cutoff, weight=weight
                )
            try:
                _len = _raw_multidigraph_dijkstra_path_length_target(
                    G, source, target, weight=weight
                )
                _path = _raw_multidigraph_dijkstra_path_target(
                    G, source, target, weight=weight
                )
            except NetworkXNoPath:
                raise NetworkXNoPath(f"No path to {target}.") from None
            if _len is not None and _path is not None:
                return _len, _path
        if source not in G:
            raise NodeNotFound(f"Node {source} not found in graph")
        if _sp_weights_need_networkx_for_type_parity(G, weight):
            return _multi_source_dijkstra_inproc(
                G, {source}, target=target, cutoff=cutoff, weight=weight
            )
        _direct = _raw_mdg_ss_dijkstra(G, source, weight=weight, cutoff=cutoff)
        if _direct is None:
            return _multi_source_dijkstra_inproc(
                G, {source}, target=target, cutoff=cutoff, weight=weight
            )
        dists, paths = _direct
        if target is not None:
            if target not in dists:
                raise NetworkXNoPath(f"No path to {target}.")
            return dists[target], paths[target]
        return dists, paths
    route = _dijkstra_weight_route(G, weight)
    if route == "networkx":
        return _multi_source_dijkstra_inproc(
            G, {source}, target=target, cutoff=cutoff, weight=weight
        )
    check_rows = route == "rows"
    # br-r37-c1-k4pod: pre-check membership so we get nx's exact
    # 'Node X not found in graph' wording.  The Rust binding emits
    # ``"Source '<repr>' is not in G"`` with quoted repr — distinct
    # enough that users matching on the message string break.
    if source not in G:
        raise NodeNotFound(f"Node {source} not found in graph")
    try:
        if target is not None and cutoff is None and isinstance(weight, str):
            if target not in G:
                if check_rows:
                    # networkx walks the whole component (reading its weights) first.
                    raise _WeightRowsUnverified
                raise NetworkXNoPath(f"No path to {target}.")
            _ptt = getattr(_fnx, "dijkstra_path_to_target", None)
            if _ptt is not None:
                _sync_rust_edge_attrs(G, edge_only=True)
                length, all_int, path = _ptt(G, source, target, weight, check_rows)
                return (int(length) if all_int else float(length), path)
        # br-r37-c1-qnj0n: a float cutoff, or an int a float holds exactly, bounds
        # the native search as networkx bounds its own (NaN and +inf compare as
        # there: unbounded). Any other cutoff keeps the view below, which compares
        # it the Python way.
        if (
            cutoff is None
            or type(cutoff) is float
            or (type(cutoff) is int and -(2**53) <= cutoff <= 2**53)
        ):
            dists, paths = _raw_single_source_dijkstra(
                G, source, weight=weight, cutoff=cutoff, check_rows=check_rows
            )
        else:
            dists, paths = _raw_single_source_dijkstra(
                G, source, weight=weight, check_rows=check_rows
            )
            dists, paths = _single_source_dijkstra_cutoff_view(source, dists, paths, cutoff)
    except _WeightRowsUnverified:
        dists = None
    if dists is None:
        return _rerun_with_weight_scan(
            single_source_dijkstra, G, source, target=target, cutoff=cutoff, weight=weight
        )
    # br-r37-c1-0opkc: the raw binding now emits distances with nx's
    # observable int/float type directly from the selected path metadata, so
    # this combined API no longer needs a Python-side edge scan or path walk.
    if target is not None:
        if target not in dists:
            raise NetworkXNoPath(f"No path to {target}.")
        return dists[target], paths[target]
    # br-r37-c1-0opkc: the raw binding emits both dicts in nx's Dijkstra
    # finalize (heap-pop) order. Preserve that insertion order directly.
    return dists, paths


def single_source_dijkstra_path(G, source, cutoff=None, weight="weight"):
    """Single-source weighted shortest paths from ``source``.

    Returns a dict ``{target: path}`` keyed by every reachable node.
    Mirrors ``networkx.single_source_dijkstra_path``.
    """
    # br-gauntlet-perf1: ``single_source_dijkstra`` runs the IDENTICAL
    # delegation gate + edge-weight scans; pre-gating here ran the O(E) Python
    # edge scans a second time per call. Delegate straight through — the
    # ``paths`` returned are identical.
    _, paths = single_source_dijkstra(G, source, cutoff=cutoff, weight=weight)
    return paths


def _multigraph_collapse_min_weight(G, weight):
    """br-cc-mgdijkstra: collapse a multigraph to a simple MIN-weight graph for the
    dijkstra family (nx's multigraph shortest path uses the min weight over each
    pair's parallel edges). ONE pass over ``edges(keys, data)`` that BOTH validates
    the weights (returns ``(None, True)`` -> caller delegates to nx on non-numeric /
    negative / +inf, the exact ``_should_delegate_dijkstra_to_networkx`` predicate)
    AND accumulates the per-pair minimum. Returns ``(simple_graph, False)`` on
    success. The native multigraph dijkstra kernel is ~4-5x slower than nx's Python
    dijkstra and the weight gate has no native multigraph variant, so this + the fast
    simple-graph kernel replaces both (0.08-0.27x -> 0.35-0.63x)."""
    simple = DiGraph() if G.is_directed() else Graph()
    simple.add_nodes_from(G)
    best = {}
    # br-r37-c1-6eaq6: the raw kernel adds in f64, so int weights whose
    # magnitudes total past 2**53 delegate - the bound the simple classes'
    # native scan applies; a sum past it came back a rounded float where
    # networkx adds Python ints exactly.
    int_total = 0
    for _u, _v, _k, _attrs in G.edges(keys=True, data=True):
        # br-r37-c1-r9k2m: `_numbers.Real` is an ABSTRACT BASE CLASS, so every
        # `isinstance` against it runs `__instancecheck__` -> `_abc_subclasscheck`
        # rather than a C-level type check. At two per edge that dominated the
        # whole collapse: cProfile on an 800-node MultiGraph counted 6400
        # `_abc._abc_instancecheck` calls costing 1341us, plus 808us of
        # `__instancecheck__` and 791us of `__subclasscheck__`, inside a 4392us
        # helper. Check the CONCRETE types first and fall back to the ABC only
        # for exotic numerics (numpy scalars, Fraction, ...).
        #
        # `type(x) is int` is False for `bool` -- bool is a SUBCLASS of int -- so
        # the exact-type test already excludes the case the original spelled out
        # with a separate `isinstance(_raw, bool)`, and booleans simply fall
        # through to the ABC branch where they behaved identically before.
        if isinstance(_attrs, dict) and weight in _attrs:
            _raw = _attrs[weight]
            _rt = type(_raw)
            if _rt is not float and _rt is not int:
                if not isinstance(_raw, bool) and not isinstance(_raw, _numbers.Real):
                    return None, True
        _val = _attrs.get(weight, 1)
        _vt = type(_val)
        if _vt is int:
            # An int is Real and can be neither NaN nor infinite.
            if _val < 0:
                return None, True
            int_total += _val
            if int_total > 2**53:
                return None, True
        elif _vt is float:
            # br-r37-c1-kn5cu: NaN DELEGATES. It used to be waved through here,
            # and the graph this builds then went to
            # `_raw_single_source_dijkstra_path_length`, which substitutes the
            # DEFAULT WEIGHT 1 for a NaN - so an undirected MultiGraph carrying
            # one NaN edge returned a plausible finite distance where networkx
            # returns nan (a->b 1.0 and a->c 2.0 against nan and nan). The
            # collapse itself was never wrong: it stores the NaN and dijkstra on
            # the collapsed graph is correct. What was wrong is that this is the
            # one route that reaches the raw kernel WITHOUT
            # `_should_delegate_dijkstra_to_networkx`, which answers True on a
            # NaN and is why the simple-graph spelling has always been right.
            # `_multigraph_collapse_min_weight_bellman` already delegates on
            # NaN; this is the sibling that did not.
            if _math.isnan(_val):
                return None, True
            if _val < 0 or (_math.isinf(_val) and _val > 0):
                return None, True
        elif isinstance(_val, _numbers.Real):
            # Same rule for the exotic numerics (numpy float64/float32,
            # Fraction, Decimal): a NaN reaches the same raw kernel.
            if _math.isnan(_val):
                return None, True
            if _val < 0 or (_math.isinf(_val) and _val > 0):
                return None, True
        # br-r37-c1-3dtn4: a weight whose TYPE cannot survive an f64 kernel
        # delegates, for the same reason NaN does - this collapse hands its
        # result to a raw kernel, and by the time that returns, a Fraction has
        # already become a plain float and cannot be recovered. This is the
        # multigraph half of that bead: the simple classes were right because
        # their gate consults the native exactness scan, and this route consults
        # nothing.
        if not _sp_weight_type_survives_the_f64_kernel(_val):
            return None, True
        _pair = (_u, _v)
        _cur = best.get(_pair)
        if _cur is None or _val < _cur:
            best[_pair] = _val
    simple.add_edges_from((_u, _v, {weight: _w}) for (_u, _v), _w in best.items())
    return simple, False


def _multigraph_collapse_min_weight_bellman(G, weight):
    """br-cc-mgdijkstra: Bellman-Ford variant of the min-weight collapse. Bellman-Ford
    KEEPS negative weights (valid), so validate + delegate only on NaN / +/-inf /
    non-numeric — the exact multigraph predicate of
    ``_should_delegate_bellman_ford_path_to_networkx`` (``_has_nan_or_inf_edge_weight``
    OR ``_has_nonnumeric_edge_weight``). One pass: returns ``(None, True)`` to delegate,
    else ``(simple_min_weight_graph, False)``. Negatives (and hence negative cycles) are
    preserved by the per-pair min, so NetworkXUnbounded detection stays byte-exact.

    br-r37-c1-mg7hw: cache the collapse against revision token + edge_attrs_dirty.
    Recomputing per call is 75.3% of bellman_ford_path_length (41.5M of 55.1M Ir at N=800).
    A cache hit cuts per-call cost to ~13.6M Ir/call (3.6x self, 1.315x vs NetworkX).
    Guarded by `not edge_attrs_dirty` and `not _has_networkx_private_storage(G)`, so any
    in-place attribute mutation, private storage override, or structural change safely
    invalidates the cache (pinned by collapse_cache_staleness.py).
    """
    token = None
    if _native_dijkstra_weight_cache_token is not None and not _has_networkx_private_storage(G):
        try:
            token = _native_dijkstra_weight_cache_token(G)
        except Exception:
            token = None
    if token is not None:
        _n_seq, _e_seq, _edge_attrs_dirty, _attr_rewrites = token
        if not _edge_attrs_dirty:
            _cache_key = (weight, _n_seq, _e_seq, _attr_rewrites)
            _cached = vars(G).get("_fnx_bellman_collapse_cache")
            if _cached is not None and _cached[0] == _cache_key:
                return _cached[1]

    simple = DiGraph() if G.is_directed() else Graph()
    simple.add_nodes_from(G)
    best = {}
    int_total = 0  # br-r37-c1-6eaq6: see _multigraph_collapse_min_weight
    for _u, _v, _k, _attrs in G.edges(keys=True, data=True):
        if isinstance(_attrs, dict) and weight in _attrs:
            _value = _attrs[weight]
            # br-r37-c1-r9k2m: same ABC cost as the dijkstra collapse above.
            _vt = type(_value)
            if _vt is int:
                # Real, never NaN or infinite - but past 2**53 in total the
                # kernel's f64 sums round.
                int_total += abs(_value)
                if int_total > 2**53:
                    res = (None, True)
                    if token is not None and not token[2]:
                        vars(G)["_fnx_bellman_collapse_cache"] = ((weight, token[0], token[1]), res)
                    return res
            elif _vt is float:
                if _math.isnan(_value) or _math.isinf(_value):
                    res = (None, True)
                    if token is not None and not token[2]:
                        vars(G)["_fnx_bellman_collapse_cache"] = ((weight, token[0], token[1]), res)
                    return res
            elif not isinstance(_value, bool):
                if not isinstance(_value, _numbers.Real):
                    res = (None, True)
                    if token is not None and not token[2]:
                        vars(G)["_fnx_bellman_collapse_cache"] = ((weight, token[0], token[1]), res)
                    return res
                if isinstance(_value, float) and (
                    _math.isnan(_value) or _math.isinf(_value)
                ):
                    res = (None, True)
                    if token is not None and not token[2]:
                        vars(G)["_fnx_bellman_collapse_cache"] = ((weight, token[0], token[1]), res)
                    return res
        _val = _attrs.get(weight, 1)
        # br-r37-c1-3dtn4: a weight whose TYPE cannot survive an f64 kernel
        # delegates, for the same reason NaN does - this collapse hands its
        # result to a raw kernel, and by the time that returns, a Fraction has
        # already become a plain float and cannot be recovered. This is the
        # multigraph half of that bead: the simple classes were right because
        # their gate consults the native exactness scan, and this route consults
        # nothing.
        if not _sp_weight_type_survives_the_f64_kernel(_val):
            res = (None, True)
            if token is not None and not token[2]:
                vars(G)["_fnx_bellman_collapse_cache"] = ((weight, token[0], token[1]), res)
            return res
        _pair = (_u, _v)
        _cur = best.get(_pair)
        if _cur is None or _val < _cur:
            best[_pair] = _val
    simple.add_edges_from((_u, _v, {weight: _w}) for (_u, _v), _w in best.items())
    res = (simple, False)
    if token is not None and not token[2]:
        vars(G)["_fnx_bellman_collapse_cache"] = ((weight, token[0], token[1]), res)
    return res


def single_source_dijkstra_path_length(G, source, cutoff=None, weight="weight"):
    """Single-source weighted shortest path lengths from ``source``.

    Returns a dict ``{target: distance}``. Mirrors
    ``networkx.single_source_dijkstra_path_length``.
    """
    # Match NetworkX's source-set validation rather than a dict-key probe.
    sources = {source}
    if _point_query_uses_private_rows(G):
        if source not in G:
            raise NodeNotFound(f"Node {source} not found in graph")
        # Do not build quadratic path output for a length-only query.
        return _dijkstra_multisource_inproc(
            G, sources, _weight_function(G, weight), cutoff=cutoff
        )
    G = _coerce_arg_to_fnx_graph(G)
    # Directed multigraphs retain their specialized length-only kernel;
    # undirected multigraphs use the native order-preserving projection below.
    if G.is_multigraph() and isinstance(weight, str):
        if G.is_directed():
            if source not in G:
                raise NodeNotFound(f"Node {source} not found in graph")
            # br-r37-c1-3dtn4: the DIRECTED multigraph takes its own kernel and
            # never touches the collapse, so the type gate has to be repeated
            # here - this was the last of the six cells, and it is the reason
            # MultiDiGraph kept flattening Fraction/Decimal/numpy after the
            # undirected half was fixed.
            if _sp_weights_need_networkx_for_type_parity(G, weight):
                return _multi_source_dijkstra_inproc(
                    G, {source}, cutoff=cutoff, weight=weight
                )[0]
            _direct = _raw_mdg_ss_dijkstra_path_length(
                G, source, weight=weight, cutoff=cutoff
            )
            if _direct is not None:
                return _direct
            return _multi_source_dijkstra_inproc(
                G, {source}, cutoff=cutoff, weight=weight
            )[0]
        # Undirected multigraphs continue through the shared exactness gate
        # below. The native length kernel already projects parallel minima and
        # restores each original neighbor row's order. The Python edge-major
        # collapse changed FIFO ties, even though its distances were correct.
    # br-r37-c1-dijknone: weight=None means "every edge weighs 1", which the
    # native kernel already computes for any attribute no edge carries.
    weight_arg = weight
    weight = _dijkstra_weight_for_none(G, weight)
    route = _dijkstra_weight_route(G, weight)
    if route == "networkx":
        return _multi_source_dijkstra_inproc(
            G, {source}, cutoff=cutoff, weight=weight
        )[0]
    if source not in G:
        raise NodeNotFound(f"Node {source} not found in graph")
    # br-r37-c1-1kor1: the raw length-only kernel now preserves nx's
    # integer-vs-float distance types and applies cutoff during relaxation, so
    # this API no longer needs to materialize full paths just to repair types.
    try:
        return _raw_single_source_dijkstra_path_length(
            G,
            source,
            weight=weight,
            cutoff=cutoff,
            check_rows=route == "rows",
        )
    except _WeightRowsUnverified:
        pass
    return _rerun_with_weight_scan(
        single_source_dijkstra_path_length, G, source, cutoff=cutoff, weight=weight_arg
    )


def single_source_bellman_ford(G, source, target=None, weight="weight"):
    """Single-source weighted shortest paths from ``source`` via Bellman-Ford.

    Returns ``(distances, paths)`` dicts keyed by reachable node. If ``target``
    is given, returns ``(distance, path)`` to that node alone. Handles negative
    edge weights; raises ``NetworkXUnbounded`` on negative cycles.
    """
    if _point_query_uses_private_rows(G):
        return _single_source_bellman_ford_inproc(
            G, source, target=target, weight=weight
        )
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-ybw1s: nx-shaped TypeError on unhashable source.
    _HASH_PROBE.get(source)
    # br-cc-mgbfpath: a DIRECTED multigraph collapses to the simple min-weight
    # DiGraph byte-EXACTLY for the all-targets (dist, path) dicts — the collapsed
    # out-adjacency order == the multigraph's, so SPFA relaxes in the same order
    # and emits the two dicts in nx's exact first-discovery key order (verified
    # 210/210 incl. NEGATIVE weights, order-sensitive). Replaces the slow native
    # nested-bucket kernel (0.26x -> ~0.5x, matching the length twin's collapse).
    # target!=None keeps delegating (unverified here); UNDIRECTED MG stays native
    # (collapse reorders per-node adjacency -> dict-order + path divergence).
    if (
        target is None
        and G.is_directed()
        and G.is_multigraph()
        and isinstance(weight, str)
    ):
        _simple, _delegate = _multigraph_collapse_min_weight_bellman(G, weight)
        if _delegate:
            return _single_source_bellman_ford_inproc(
                G, source, target=target, weight=weight
            )
        return single_source_bellman_ford(_simple, source, weight=weight)
    # br-bfignoreweight: same weight-ignoring bug as dijkstra — the
    # Rust Bellman-Ford returns hop-_count distances on weighted input.
    # Run in-process on weighted / delegated input.
    if (
        target is not None
        or _should_delegate_bellman_ford_to_networkx(weight)
        or _binding_self_syncs_gate(G, weight)
    ):
        return _single_source_bellman_ford_inproc(
            G,
            source,
            target=target,
            weight=weight,
        )
    # br-r37-c1-k4pod: pre-check for nx's exact 'Source X not in G'
    # wording (no quoted repr).
    if source not in G:
        raise NodeNotFound(f"Source {source} not in G")
    # br-r37-c1-e9rea: the kernel emits dist/path dicts in nx's SPFA
    # first-discovery order (NOT distance-sorted — e.g. a node at distance 3
    # can precede one at distance 2). Trust that order directly; do not sort.
    dists, paths = _raw_single_source_bellman_ford(G, source, weight=weight)
    # weighted sp batch 2: nx preserves int distances for all-int weights.
    if _sp_edge_weights_all_int(G, weight):
        dists = _sp_coerce_dist_to_int(dists)
    else:
        # br-r37-c1-srczero: per-path int-type propagation (see helper).
        dists = _sp_propagate_int_types(G, weight, dists, paths)
    return dists, paths


def single_source_bellman_ford_path(G, source, weight="weight"):
    """Single-source weighted shortest paths from ``source`` via Bellman-Ford.

    Returns a dict ``{target: path}`` keyed by reachable node. Handles negative
    edge weights; raises ``NetworkXUnbounded`` on negative cycles reachable
    from ``source``.
    """
    if _point_query_uses_private_rows(G):
        return _single_source_bellman_ford_inproc(G, source, weight=weight)[1]
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-ybw1s: nx-shaped TypeError on unhashable source.
    _HASH_PROBE.get(source)
    # br-cc-mgbfpath: DIRECTED multigraph -> collapse to the simple min-weight
    # DiGraph + fast simple kernel (byte-exact all-targets path dict incl. nx's
    # SPFA first-discovery key order, verified 210/210 incl. negatives). Replaces
    # the slow native nested-bucket kernel (0.43x -> ~0.5x). UNDIRECTED MG stays
    # native (collapse reorders per-node adjacency -> dict-order/path divergence).
    if G.is_directed() and G.is_multigraph() and isinstance(weight, str):
        _simple, _delegate = _multigraph_collapse_min_weight_bellman(G, weight)
        if _delegate:
            return _single_source_bellman_ford_inproc(
                G, source, weight=weight
            )[1]
        return single_source_bellman_ford_path(_simple, source, weight=weight)
    # br-bfignoreweight: delegate weighted inputs.
    if _should_delegate_bellman_ford_to_networkx(weight) or _binding_self_syncs_gate(G, weight):
        return _single_source_bellman_ford_inproc(
            G, source, weight=weight
        )[1]
    # br-r37-c1-jxvsu: pre-check for nx's exact 'Source X not in G'
    # wording — Rust binding emits a quoted-repr 'Source \'X\' is
    # not in G' variant.
    if source not in G:
        raise NodeNotFound(f"Source {source} not in G")
    # br-r37-c1-e9rea: the kernel emits the path dict in nx's SPFA
    # first-discovery order (not distance-sorted). Trust it directly.
    return _raw_single_source_bellman_ford_path(G, source, weight=weight)


def single_source_bellman_ford_path_length(G, source, weight="weight"):
    """Single-source weighted shortest path lengths from ``source`` via Bellman-Ford.

    Returns a dict ``{target: distance}`` keyed by reachable node. Handles
    negative edge weights; raises ``NetworkXUnbounded`` on negative cycles
    reachable from ``source``.
    """
    if _point_query_uses_private_rows(G):
        return _bellman_ford_inproc(G, [source], _weight_function(G, weight))
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-ybw1s: nx-shaped TypeError on unhashable source.
    _HASH_PROBE.get(source)
    # br-bfignoreweight: delegate weighted inputs.
    if _should_delegate_bellman_ford_to_networkx(weight):
        return _bellman_ford_inproc(G, [source], _weight_function(G, weight))
    # br-cc-mgdijkstra: multigraph Bellman-Ford LENGTH -> collapse parallels to the
    # simple min-weight graph (keep negatives; delegate NaN/inf/nonnumeric) + fast
    # simple kernel. Length is order-independent -> byte-exact. This also fixes the
    # pre-existing bad-weight divergence (the native multigraph kernel was reached
    # for NaN/inf/nonnumeric weights the collapse now delegates to nx).
    if G.is_multigraph() and isinstance(weight, str):
        _simple, _delegate = _multigraph_collapse_min_weight_bellman(G, weight)
        if _delegate:
            return _bellman_ford_inproc(G, [source], _weight_function(G, weight))
        return single_source_bellman_ford_path_length(_simple, source, weight=weight)
    if _binding_self_syncs_gate(G, weight):
        return _bellman_ford_inproc(G, [source], _weight_function(G, weight))
    # br-r37-c1-jxvsu: same exact wording fix as
    # single_source_bellman_ford_path — Rust binding emits a
    # quoted-repr variant.
    if source not in G:
        raise NodeNotFound(f"Source {source} not in G")
    # br-r37-c1-3dtn4: a weight type the f64 kernel cannot round-trip goes to
    # networkx - Fraction, Decimal and numpy scalars (np.int64 included, whose
    # networkx sum stays np.int64) are what the weight route's scan flags as
    # inexact, exactly as the type-parity gate did; negatives stay native.
    # br-r37-c1-0g2tj: the kernel types each distance as networkx's sum does
    # (int while every relaxation that set it added ints) and emits the dict in
    # SPFA first-discovery order, so there is no Python re-typing pass and no
    # second, paths-carrying traversal for mixed weights (br-r37-c1-z8mfa ran
    # one, br-r37-c1-srczero re-derived types from its paths). After a write
    # the call checks the rows it read instead of every weight (svsam).
    route = _bellman_ford_weight_route(G, weight)
    if route == "networkx":
        return _bellman_ford_inproc(G, [source], _weight_function(G, weight))
    try:
        return _raw_single_source_bellman_ford_path_length(
            G, source, weight=weight, check_rows=route == "rows"
        )
    except _WeightRowsUnverified:
        pass
    return _rerun_with_weight_scan(
        single_source_bellman_ford_path_length, G, source, weight=weight
    )


def all_pairs_dijkstra_path(G, cutoff=None, weight="weight"):
    """_Iterator of ``(source, paths)`` pairs via Dijkstra.

    ``paths`` is a dict ``{target: path-list}``. Mirrors
    ``networkx.all_pairs_dijkstra_path``.
    """
    for node in G:
        yield node, single_source_dijkstra_path(G, node, cutoff=cutoff, weight=weight)


def all_pairs_dijkstra_path_length(G, cutoff=None, weight="weight"):
    """_Iterator of ``(source, lengths)`` pairs via Dijkstra.

    ``lengths`` is a dict ``{target: distance}``. Mirrors
    ``networkx.all_pairs_dijkstra_path_length``.
    """
    # Keep length-only queries on their typed single-source kernels, never a
    # paths-carrying traversal. Re-projecting a multigraph per row is deliberate:
    # a cached projection would hide changes to parallel keys or weights.
    for node in G:
        yield node, single_source_dijkstra_path_length(G, node, cutoff=cutoff, weight=weight)


def all_pairs_bellman_ford_path(G, weight="weight"):
    """_Iterator of ``(source, paths)`` pairs via Bellman-Ford.

    ``paths`` is a dict ``{target: path-list}``. Handles negative weights.
    Mirrors ``networkx.all_pairs_bellman_ford_path``.
    """
    if _point_query_uses_private_rows(G):
        for node in G:
            yield node, single_source_bellman_ford_path(G, node, weight=weight)
        return
    G = _coerce_arg_to_fnx_graph(G)
    # br-bfignoreweight: delegate weighted inputs to nx.
    if _should_delegate_bellman_ford_to_networkx(weight) or _binding_self_syncs_gate(G, weight):
        for node in G:
            yield (node, single_source_bellman_ford_path(G, node, weight=weight))
        return
    # br-r37-c1-sk5be: iterate outer keys in node-insertion order
    # matching nx (Rust dict yields in arbitrary order).
    raw = _raw_all_pairs_bellman_ford_path(G, weight=weight)
    for node in G.nodes():
        if node in raw:
            # br-r37-c1-e9rea: the kernel already yields each source's paths in
            # nx's SPFA first-discovery order (not distance-sorted), so trust it.
            yield (node, dict(raw[node]))


def all_pairs_bellman_ford_path_length(G, weight="weight"):
    """_Iterator of ``(source, lengths)`` pairs via Bellman-Ford.

    ``lengths`` is a dict ``{target: distance}``. Handles negative weights.
    Mirrors ``networkx.all_pairs_bellman_ford_path_length``.
    """
    if _point_query_uses_private_rows(G):
        for node in G:
            yield node, dict(single_source_bellman_ford_path_length(G, node, weight=weight))
        return
    G = _coerce_arg_to_fnx_graph(G)
    # br-bfignoreweight: delegate weighted inputs to nx.
    if _should_delegate_bellman_ford_to_networkx(weight) or _binding_self_syncs_gate(G, weight):
        for node in G:
            yield (node, dict(single_source_bellman_ford_path_length(G, node, weight=weight)))
        return
    # weighted sp batch 2: nx preserves int distances for all-int weights.
    _coerce = _sp_edge_weights_all_int(G, weight)
    if not _coerce and not _sp_edge_weights_all_float(G, weight):
        # Mixed int/float weights: nx keeps a distance an int only where every
        # edge on its path is int (int + int stays int), which the float kernel
        # cannot tell; the per-source path re-derives it (as the Dijkstra
        # all-pairs twin does through _sp_propagate_int_types).
        for node in G:
            yield (node, dict(single_source_bellman_ford_path_length(G, node, weight=weight)))
        return
    # br-r37-c1-sk5be: iterate outer keys in node-insertion order
    # matching nx (Rust dict yields in arbitrary order).
    raw = _raw_all_pairs_bellman_ford_path_length(G, weight=weight)
    for node in G.nodes():
        if node in raw:
            # br-r37-c1-e9rea: the kernel already yields each source's lengths in
            # nx's SPFA first-discovery order (not distance-sorted), so trust it.
            inner = dict(raw[node])
            if _coerce:
                inner = _sp_coerce_dist_to_int(inner)
            elif node in inner:
                # nx seeds dist = {source: 0}: the source's own distance is the
                # int 0 whatever the weights; the kernel's is a float. Assigning
                # to the existing key keeps its position.
                inner[node] = 0
            yield (node, inner)


def floyd_warshall(G, weight="weight"):
    """All-pairs shortest path lengths via the Floyd-Warshall algorithm.

    Returns a dict-of-dicts ``{u: {v: distance}}`` for every pair of nodes.
    Handles negative edge weights (no negative cycles); time complexity is
    O(|V|^3). Mirrors ``networkx.floyd_warshall``.
    """
    # br-r37-c1-fwnumpy: nx.floyd_warshall is a PURE-PYTHON O(|V|^3) triple
    # loop; fnx used to delegate to it (+ a full fnx->nx conversion) -> ~0.7x.
    # Compute the all-pairs distance matrix with a numpy-vectorised
    # Floyd-Warshall instead (min-plus over the adjacency matrix), then format
    # the dict-of-dicts in nx's EXACT defaultdict insertion order. ~34x FASTER
    # than nx, byte-exact (values, int/float type, and inner+outer key order).
    # Multigraph (to_numpy_array sums parallel edges, nx FW takes their min),
    # callable / non-string weight, and graphs mixing int and float weights
    # (nx's per-pair value type would then be path-dependent) still delegate.
    G = _coerce_arg_to_fnx_graph(G)
    if (
        _should_delegate_floyd_warshall_to_networkx(weight)
        or G.is_multigraph()
        or _fw_weight_kind(G, weight) == "mixed"
    ):
        return _floyd_warshall_predecessor_and_distance_inproc(G, weight=weight)[1]
    return _floyd_warshall_numpy(G, weight)


def _fw_weight_kind(G, weight):
    """Classify edge-weight homogeneity for floyd_warshall: ``"int"`` (every
    edge carries an integer weight), ``"float"`` (every edge is float OR uses
    the default 1.0 because the attr is absent), or ``"mixed"`` (a blend of int
    and float — or a bool / non-numeric weight). nx's Floyd-Warshall preserves
    Python int arithmetic, so an all-int graph yields int distances and a
    unit/float graph yields float distances; ``"mixed"`` is delegated because
    the per-pair value type would be shortest-path-dependent.

    br-r37-c1-6eaq6: ints whose magnitudes total more than 2**53 are
    ``"mixed"`` too. The vectorised path adds them as float64, so a path sum
    past 2**53 came back rounded - 2**62 weights summed one off - where
    networkx adds Python ints exactly. The total bounds every path sum.
    """
    saw_int = False
    saw_float = False
    int_total = 0
    for _u, _v, edge_data in G.edges(data=True):
        if weight in edge_data:
            value = edge_data[weight]
            if isinstance(value, bool):
                return "mixed"
            if isinstance(value, int):
                saw_int = True
                int_total += abs(value)
                if int_total > 2**53:
                    return "mixed"
            elif isinstance(value, float):
                saw_float = True
            else:
                return "mixed"
        else:
            saw_float = True  # nx defaults the missing weight to 1.0 (float)
    if saw_int and saw_float:
        return "mixed"
    return "int" if saw_int else "float"


def _floyd_warshall_numpy(G, weight):
    """Vectorised Floyd-Warshall returning nx's exact dict-of-dicts.

    The distance matrix is built with the same min-plus recurrence networkx
    uses (so float arithmetic is bit-identical), then the nested
    ``defaultdict`` is materialised in networkx's exact key-insertion order:
    each ``dist[u]`` starts with ``u`` (the int-0 diagonal), then its
    edge-neighbours in ``G.edges()`` yield order, then the remaining nodes in
    ``G.nodes()`` order — matching nx's ``defaultdict`` access pattern.
    """
    import math as _math
    import numpy as _np
    from collections import defaultdict as _defaultdict

    nodes = list(G)
    n = len(nodes)
    if n == 0:
        return {}
    index_of = {node: i for i, node in enumerate(nodes)}
    matrix = to_numpy_array(G, nodelist=nodes, weight=weight, nonedge=_np.inf)
    _np.fill_diagonal(matrix, 0.0)
    for k in range(n):
        matrix = _np.minimum(
            matrix, matrix[:, k][:, None] + matrix[k, :][None, :]
        )
    as_int = _fw_weight_kind(G, weight) == "int"

    dist = _defaultdict(lambda: _defaultdict(lambda: float("inf")))
    for u in nodes:
        dist[u][u] = 0
    undirected = not G.is_directed()
    for ue, ve, edge_data in G.edges(data=True):
        w = edge_data.get(weight, 1.0)
        dist[ue][ve] = min(w, dist[ue][ve])
        if undirected:
            dist[ve][ue] = min(w, dist[ve][ue])
    for u in nodes:
        row = dist[u]
        iu = index_of[u]
        for v in nodes:
            if v == u:
                continue
            value = matrix[iu, index_of[v]]
            if _math.isinf(value):
                row[v] = float("inf")
            elif as_int:
                row[v] = int(value)
            else:
                row[v] = float(value)
        diagonal = matrix[iu, iu]
        if diagonal != 0:  # only a negative cycle moves the diagonal off int 0
            row[u] = int(diagonal) if as_int else float(diagonal)
    return dict(dist)


def floyd_warshall_predecessor_and_distance(G, weight="weight"):
    """All-pairs predecessors and distances via the Floyd-Warshall algorithm.

    Returns ``(predecessors, distances)``: predecessors is a nested dict
    suitable for ``reconstruct_path``, distances mirrors ``floyd_warshall``.
    Mirrors ``networkx.floyd_warshall_predecessor_and_distance``.
    """
    G = _coerce_arg_to_fnx_graph(G)
    return _floyd_warshall_predecessor_and_distance_inproc(G, weight=weight)


# Additional centrality algorithms
from franken_networkx._fnx import (
    in_degree_centrality as _raw_in_degree_centrality,
    out_degree_centrality as _raw_out_degree_centrality,
    group_degree_centrality as _raw_group_degree_centrality,
    group_in_degree_centrality as _raw_group_in_degree_centrality,
    group_out_degree_centrality as _raw_group_out_degree_centrality,
)


def _raise_not_impl_for_undirected_if_needed(exc):
    """br-r37-c1-4elbw helper: translate Rust binding's custom
    'X is not defined for undirected graphs.' message to nx's
    standard 'not implemented for undirected type'."""
    if "not defined for undirected" in str(exc):
        return NetworkXNotImplemented("not implemented for undirected type")
    return None


def in_degree_centrality(G, *, backend=None, **backend_kwargs):
    """Compute in-degree centrality for nodes in a directed graph.

    br-midegcent: the Rust _raw_in_degree_centrality treated parallel
    multi-edges as a single edge on MultiDiGraph inputs, so every node
    got in-degree=1 after normalization instead of the correct
    parallel-counted in-degree. Recompute from G.in_degree() (which
    already counts multi-edges correctly) for multigraphs to match nx.
    """
    _validate_backend_dispatch_keywords("in_degree_centrality", backend, backend_kwargs)
    # br-r37-c1-rg8jh: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-n7rgh: nx is @not_implemented_for('undirected'). The
    # MultiGraph (undirected + multi) branch fell through to
    # G.in_degree() which doesn't exist on undirected and raised
    # AttributeError. Add the type guard so MG and Graph alike raise
    # NetworkXNotImplemented matching nx.
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    # br-r37-c1-2fx0w: multigraphs take this path too - G.in_degree() counts
    # parallel edges, and a one-node graph is {n: 1} as in nx (the old
    # multigraph branch answered 0).
    # br-r37-c1-idcnative (cc): _raw_in_degree_centrality builds the result dict
    # through PyO3 per node (0.51-0.62x vs nx) AND ULP-drifts from nx's f64
    # d*(1.0/(n-1.0)) (native!=nx on n>=1500; also returns float 1.0 vs nx's int 1
    # for n==1). nx's own {n: d*s} dict-comp over the in_degree view is byte-exact
    # AND 1.23x (beats nx). Run nx's algorithm verbatim.
    n = len(G)
    if n <= 1:
        return {node: 1 for node in G}
    s = 1.0 / (n - 1.0)
    return {node: d * s for node, d in G.in_degree()}


def out_degree_centrality(G, *, backend=None, **backend_kwargs):
    """Compute out-degree centrality for nodes in a directed graph.

    br-midegcent: same multigraph fix as in_degree_centrality — the
    Rust path undercounted parallel edges on MultiDiGraph.
    """
    _validate_backend_dispatch_keywords("out_degree_centrality", backend, backend_kwargs)
    # br-r37-c1-rg8jh: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-n7rgh: same undirected guard as in_degree_centrality.
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    # br-r37-c1-2fx0w: multigraphs share this path, as in in_degree_centrality.
    # br-r37-c1-idcnative (cc): same as in_degree_centrality — _raw_out_degree_
    # centrality is slower (PyO3 dict-build) AND ULP-drifts from nx; nx's verbatim
    # {n: d*s} dict-comp over the out_degree view is byte-exact + 1.23x.
    n = len(G)
    if n <= 1:
        return {node: 1 for node in G}
    s = 1.0 / (n - 1.0)
    return {node: d * s for node, d in G.out_degree()}


def _average_path_weight(G, path, weight=None):
    path_length = len(path) - 1
    if path_length <= 0:
        return 0
    if weight is None:
        return 1 / path_length
    total_weight = sum(G.edges[u, v][weight] for u, v in _itertools.pairwise(path))
    return total_weight / path_length


def local_reaching_centrality(
    G,
    v,
    paths=None,
    weight=None,
    normalized=True,
    *,
    backend=None,
    **backend_kwargs,
):
    """Returns the local reaching centrality of a node."""
    _validate_backend_dispatch_keywords(
        "local_reaching_centrality", backend, backend_kwargs
    )

    total_weight = G.size(weight=weight)
    if total_weight > 0 and len(G) == 1:
        raise NetworkXError(
            "local_reaching_centrality of a single node with self-loop not well-defined"
        )

    if paths is None:
        # br-r37-c1-lrcdist: for weight=None the negative-weight guard is
        # vacuous -- nx computes ``any(None in data and data[None] < 0 ...)``,
        # which is False for every graph that does not key an edge attribute by
        # the literal ``None`` object. Skipping it avoids materializing the whole
        # ``edges(data=True)`` view (~12ms at n=1500), the real bottleneck.
        if weight is not None and is_negatively_weighted(G, weight=weight):
            raise NetworkXError("edge weights must be positive")
        if total_weight <= 0:
            raise NetworkXError("Size of G must be positive")
        if weight is None:
            # the weight=None result only consumes BFS
            # distances -- directed needs the reachable-set size, undirected
            # needs sum(1/dist). The old path built full shortest_path node
            # lists (O(N * path_len) materialization) just to take len()/recompute
            # 1/(len(path)-1). single_source_shortest_path_length yields the
            # same reachable set + distances in identical BFS-discovery order,
            # so this is byte-identical to nx (same fast path proven for
            # global_reaching_centrality, br-r37-c1-04z53). ~8x faster.
            denom = len(G) - 1
            # br-r37-c1-ai5i9: nx computes paths via ``shortest_path(G, v)``
            # whose missing-source error is ``Source {v} not in G`` (no "is").
            # The lrcdist perf path uses single_source_shortest_path_length,
            # whose error says "is not in G" — reproduce nx's exact wording at
            # nx's precedence (after the Size-of-G check above).
            if v not in G:
                raise NodeNotFound(f"Source {v} not in G")
            dist = single_source_shortest_path_length(G, v)
            if G.is_directed():
                return (len(dist) - 1) / denom
            return sum(1.0 / d for d in dist.values() if d > 0) / denom

        def as_distance(u, v_, d):
            return total_weight / d.get(weight, 1)

        paths = shortest_path(G, source=v, weight=as_distance)

    if weight is None and G.is_directed():
        return (len(paths) - 1) / (len(G) - 1)

    if normalized and weight is not None:
        norm = G.size(weight=weight) / G.size()
    else:
        norm = 1

    sum_avg_weight = sum(
        _average_path_weight(G, path, weight=weight) for path in paths.values()
    ) / norm
    return sum_avg_weight / (len(G) - 1)


def global_reaching_centrality(
    G,
    weight=None,
    normalized=True,
    *,
    backend=None,
    **backend_kwargs,
):
    """Returns the global reaching centrality of a graph."""
    _validate_backend_dispatch_keywords(
        "global_reaching_centrality", backend, backend_kwargs
    )

    # br-r37-c1-lrcdist: skip the vacuous negative-weight guard for weight=None
    # (same reasoning as local_reaching_centrality) -- it otherwise materializes
    # the entire edges(data=True) view to evaluate ``None in data``.
    if weight is not None and is_negatively_weighted(G, weight=weight):
        raise NetworkXError("edge weights must be positive")

    total_weight = G.size(weight=weight)
    if total_weight <= 0:
        raise NetworkXError("Size of G must be positive")

    if weight is None:
        # br-r37-c1-04z53: unweighted fast path. The weighted formula needs full
        # shortest-path node lists, but for ``weight=None`` ``_average_path_weight``
        # only consumes ``len(path) - 1`` = the BFS distance. So we compute
        # all-pairs distances (BFS-discovery order, no path materialization) instead
        # of the O(N**2 * path_len) path reconstruction that dominated the old path.
        #
        # Bit-exactness: ``single_source_shortest_path_length`` yields distances in
        # the identical BFS-discovery order as ``shortest_path``, and we reuse the
        # builtin ``sum`` (Neumaier-compensated for floats in CPython) exactly as the
        # reference does, so every float bit matches nx (verified on a 330-graph
        # undirected+directed sweep). ~7.4x faster (182ms -> 25ms @ N=400, m=3).
        n = len(G)
        if total_weight > 0 and n == 1:
            raise NetworkXError(
                "local_reaching_centrality of a single node with self-loop not well-defined"
            )
        denom = n - 1
        if G.is_directed():
            lrc = [
                (len(single_source_shortest_path_length(G, node)) - 1) / denom
                for node in G
            ]
        else:
            lrc = [
                sum(
                    1.0 / d
                    for d in single_source_shortest_path_length(G, node).values()
                    if d > 0
                )
                / denom
                for node in G
            ]
        max_lrc = max(lrc)
        return sum(max_lrc - centrality for centrality in lrc) / denom

    def as_distance(u, v, d):
        return total_weight / d.get(weight, 1)

    shortest_paths = dict(shortest_path(G, weight=as_distance))

    lrc = [
        local_reaching_centrality(
            G,
            node,
            paths=paths,
            weight=weight,
            normalized=normalized,
        )
        for node, paths in shortest_paths.items()
    ]
    max_lrc = max(lrc)
    return sum(max_lrc - centrality for centrality in lrc) / (len(G) - 1)


def group_degree_centrality(G, S, *, backend=None, **backend_kwargs):
    """Compute group degree centrality for a node set.

    br-r37-c1-gdcdir: the Rust kernel ``_raw_group_degree_centrality``
    has ``require_undirected`` and rejects directed input. nx supports
    DiGraph for group_degree_centrality, where ``G.neighbors`` means
    successors. Rebuild that scalar formula locally to avoid converting
    the whole graph to NetworkX for directed inputs.
    """
    G = _coerce_arg_to_fnx_graph(G)
    _validate_backend_dispatch_keywords("group_degree_centrality", backend, backend_kwargs)
    for node in S:
        if node not in G:
            graph_type = "digraph" if G.is_directed() else "graph"
            raise NetworkXError(f"The node {node} is not in the {graph_type}.")
    denom = len(G.nodes()) - len(S)
    if denom == 0:
        raise ZeroDivisionError("division by zero")
    if not G.is_directed() and denom > 0:
        return _raw_group_degree_centrality(G, S)
    neighbors = set().union(*(set(G.neighbors(node)) for node in S)) - set(S)
    return len(neighbors) / denom


def group_in_degree_centrality(G, S, *, backend=None, **backend_kwargs):
    """Compute group in-degree centrality for a node set."""
    G = _coerce_arg_to_fnx_graph(G)
    _validate_backend_dispatch_keywords(
        "group_in_degree_centrality", backend, backend_kwargs
    )
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    return group_degree_centrality(G.reverse(), S)


def group_out_degree_centrality(G, S, *, backend=None, **backend_kwargs):
    """Compute group out-degree centrality for a node set."""
    G = _coerce_arg_to_fnx_graph(G)
    _validate_backend_dispatch_keywords(
        "group_out_degree_centrality", backend, backend_kwargs
    )
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    return group_degree_centrality(G, S)

# Component algorithms
from franken_networkx._fnx import (
    node_connected_component as _raw_node_connected_component,
    is_biconnected as _raw_is_biconnected,
    biconnected_components as _raw_biconnected_components,
    biconnected_component_edges as _raw_biconnected_component_edges,
    is_semiconnected as _raw_is_semiconnected,
    kosaraju_strongly_connected_components as _raw_kosaraju_strongly_connected_components,
    attracting_components as _raw_attracting_components,
    number_attracting_components as _raw_number_attracting_components,
    is_attracting_component as _raw_is_attracting_component,
)


def biconnected_component_edges(G):
    """Yield edges within each biconnected component of an undirected graph.

    _Generator function so the returned object is a true generator
    matching nx's contract (br-r37-c1-24wk3). The Rust binding returns
    a materialized list; wrapping with ``yield from`` makes the returned
    object a true ``generator`` so ``isinstance(result,
    types.GeneratorType)`` matches and short-circuit callers like
    ``next(biconnected_component_edges(huge_graph))`` don't pay for
    full materialisation.

    br-r37-c1-bcedfs: the native binding now ports nx's DFS edge-stack
    algorithm directly (edges in DFS-traversal order with nx's discovery
    direction, e.g. ('b', 'a') not canonical ('a', 'b')), so we no longer
    delegate through a full fnx->nx conversion (~3x faster).
    """
    # br-r37-c1-scceager: nx is @not_implemented_for('directed') — eager raise.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    G = _coerce_arg_to_fnx_graph(G)

    def _gen():
        yield from _raw_biconnected_component_edges(G)

    return _gen()


def kosaraju_strongly_connected_components(G, source=None):
    """Kosaraju-style strongly connected components.

    Each component is returned as a ``set`` to match networkx.

    br-r37-c1-53cwv / br-r37-c1-bgvr0: the native kernel formerly emitted SCCs
    in a sequence that didn't match nx's documented Kosaraju order, so this
    wrapper delegated to nx (a full fnx->nx conversion, ~7.2x slower than nx on
    a 200-node digraph). The native ``kosaraju_strongly_connected_components``
    kernel now mirrors nx's exact two-phase emission order (postorder on the
    reversed graph, then forward preorder in reverse postorder), verified
    byte-identical (sets AND sequence) vs nx across 100 random digraphs, so the
    no-``source`` path runs natively. A non-default ``source`` restricts nx's
    Phase-1 postorder to that source's reachable set (the native kernel is
    whole-graph only), so it keeps delegating.
    """
    # br-r37-c1-scceager: eager directed-only check (nx contract), then return
    # the generator. See strongly_connected_components.
    if not G.is_directed():
        # Preserve the standard '@not_implemented_for' error format
        # so callers see a stable message (br-r37-c1-4elbw).
        raise NetworkXNotImplemented("not implemented for undirected type")

    if source is not None:
        def _gen_source():
            post = list(dfs_postorder_nodes(G.reverse(copy=False), source=source))
            n = len(post)
            seen = set()
            while post and len(seen) < n:
                r = post.pop()
                if r in seen:
                    continue
                new = {r}
                seen.add(r)
                stack = [r]
                while stack and len(seen) < n:
                    v = stack.pop()
                    for w in G.neighbors(v):
                        if w not in seen:
                            new.add(w)
                            seen.add(w)
                            stack.append(w)
                yield new

        return _gen_source()

    # br-r37-c1-0555d: accept nx-typed inputs before the native kernel.
    fg = _coerce_arg_to_fnx_graph(G)

    def _gen():
        for component in _raw_kosaraju_strongly_connected_components(fg):
            yield set(component)

    return _gen()


def node_connected_component(G, n):
    """Return the set of nodes in the connected component of ``n``.

    br-nccset: nx.node_connected_component returns a set; the Rust
    binding returned a list. Callers doing set ops on the result
    (issubset / intersection / ``x in result`` on large outputs)
    silently saw wrong performance/types. Coerce to set.

    br-r37-c1-c4agn: hash-check for nx-shaped TypeError parity.
    """
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    G = _coerce_arg_to_fnx_graph(G)
    _HASH_PROBE.get(n)
    # br-r37-c1-eun8y: nx's _plain_bfs indexes G._adj[n], so a missing node
    # surfaces as a bare KeyError(n) — not the native binding's
    # NodeNotFound("Node 'n' is not in G"). Match nx's exception type/args.
    if n not in G:
        raise KeyError(n)
    result = _raw_node_connected_component(G, n)
    return set(result) if not isinstance(result, set) else result


def is_biconnected(G):
    """br-isokw: ``G`` matches nx; Rust binding used ``g``."""
    # br-r37-c1-0555d: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    return _raw_is_biconnected(G)


def biconnected_components(G):
    """Generate biconnected components as sets of nodes.

    Matches upstream's ``generator[set]`` contract (franken_networkx-v1nwd).

    br-bccbowtie: the Rust ``_raw_biconnected_components`` previously
    failed to split at articulation points on graphs like the "bowtie"
    (two triangles sharing a single vertex), returning one merged
    component instead of NX's two, so this wrapper delegated to NX.

    br-r37-c1-bccdisc: the root cause was a low-link bug in the Rust
    edge-stack DFS — back edges folded in ``low[w]`` instead of
    ``discovery[w]`` (nx does ``low[parent] = min(low[parent],
    discovery[child])``). On the bowtie the shared articulation vertex
    carries ``low < disc``, so the wrong propagation defeated the
    ``low >= disc[parent]`` split test. With that fixed the native
    kernel produces byte-identical node-set components AND the same
    component sequence as the nx-delegation path (verified: 400 random
    graphs incl. trees/triangle-chains, set + sequence equality, plus
    empty/single/self-loop corners). Drop the delegation: the native
    DFS over fnx's own adjacency is ~4-5x faster than convert-to-nx +
    nx's pure-Python DFS.
    """
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-scceager: nx is @not_implemented_for('directed') — eager raise.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    def _gen():
        yield from (
            set(component) for component in _raw_biconnected_components(G)
        )

    return _gen()


# Graph generators — classic
from franken_networkx._fnx import (
    complete_graph as _rust_complete_graph,
    cycle_graph as _rust_cycle_graph,
    empty_graph as _rust_empty_graph,
    path_graph as _rust_path_graph,
    star_graph as _rust_star_graph,
)

# Graph generators — random
from franken_networkx._fnx import gnp_random_graph as _rust_gnp_random_graph
from franken_networkx._fnx import gnp_random_digraph as _rust_gnp_random_digraph
try:
    from franken_networkx._fnx import gnm_random_graph as _rust_gnm_random_graph
    from franken_networkx._fnx import gnm_random_digraph as _rust_gnm_random_digraph
except ImportError:  # pragma: no cover — defensive for partial builds
    _rust_gnm_random_graph = None
    _rust_gnm_random_digraph = None
from franken_networkx._fnx import watts_strogatz_graph as _rust_watts_strogatz_graph
from franken_networkx._fnx import barabasi_albert_graph as _rust_barabasi_albert_graph
from franken_networkx._fnx import erdos_renyi_graph as _rust_erdos_renyi_graph
from franken_networkx._fnx import (
    newman_watts_strogatz_graph as _rust_newman_watts_strogatz_graph,
)
from franken_networkx._fnx import (
    connected_watts_strogatz_graph as _rust_connected_watts_strogatz_graph,
)
from franken_networkx._fnx import random_regular_graph as _rust_random_regular_graph
from franken_networkx._fnx import (
    random_regular_edges_pyset as _rust_random_regular_edges_pyset,
)
from franken_networkx._fnx import (
    random_regular_graph_pyset_order as _rust_random_regular_graph_pyset_order,
)
from franken_networkx._fnx import (
    random_lobster_graph_lazy_int as _rust_random_lobster_graph_lazy_int,
)
from franken_networkx._fnx import powerlaw_cluster_graph as _rust_powerlaw_cluster_graph
from franken_networkx._fnx import stochastic_block_model as _rust_stochastic_block_model

# Read/write — graph I/O & Runtime mode / Audit ledger
from franken_networkx._fnx import (
    decision_records as _rust_decision_records,
    drain_decision_records as _rust_drain_decision_records,
    get_compatibility_mode as _rust_get_compatibility_mode,
    get_thread_compatibility_mode as _rust_get_thread_compatibility_mode,
    node_link_data as _rust_node_link_data,
    node_link_graph as _rust_node_link_graph,
    read_adjlist as _rust_read_adjlist,
    read_edgelist as _rust_read_edgelist,
    read_gexf as _rust_read_gexf,
    read_graphml as _rust_read_graphml,
    read_json_graph as _rust_read_json_graph,
    set_compatibility_mode as _rust_set_compatibility_mode,
    set_thread_compatibility_mode as _rust_set_thread_compatibility_mode,
    write_adjlist as _rust_write_adjlist,
    write_edgelist as _rust_write_edgelist,
    write_graphml as _rust_write_graphml,
    read_gml as _rust_read_gml,
    write_gml as _rust_write_gml,
)
from franken_networkx.readwrite import (
    from_graph6_bytes,
    from_sparse6_bytes,
    generate_adjlist,
    generate_edgelist,
    generate_gexf,
    generate_gml,
    generate_multiline_adjlist,
    generate_pajek,
    # br-r37-c1-dytcs: parse_gexf, parse_graph6, parse_sparse6 are
    # nx-readwrite-only (nx top level does not re-export them);
    # callers reach them via fnx.readwrite.X.
    parse_adjlist,
    parse_edgelist,
    parse_gml,
    parse_leda,
    parse_multiline_adjlist,
    parse_pajek,
    read_gexf,
    read_graph6,
    read_leda,
    read_multiline_adjlist,
    read_pajek,
    read_sparse6,
    read_weighted_edgelist,
    relabel_gexf_graph,
    to_graph6_bytes,
    to_sparse6_bytes,
    write_gexf,
    write_graph6,
    write_graphml_lxml,
    write_graphml_xml,
    write_multiline_adjlist,
    write_pajek,
    write_sparse6,
    write_weighted_edgelist,
)
from franken_networkx.readwrite import (
    _write_edgelist_via_nx as _write_edgelist_via_nx,
    _read_edgelist_via_nx as _read_edgelist_via_nx,
    _read_adjlist_via_nx as _read_adjlist_via_nx,
    _write_adjlist_via_nx as _write_adjlist_via_nx,
    _write_graphml_via_nx as _write_graphml_via_nx,
    _read_graphml_via_nx as _read_graphml_via_nx,
    _write_gml_via_nx as _write_gml_via_nx,
    _read_gml_via_nx as _read_gml_via_nx,
)



def _edgelist_native_writer_preserves_node_labels(G):
    if getattr(G, "lazy_int_node_stop", 0) > 0:
        return True
    return not any(isinstance(node, str) for node in G.nodes())


def _write_edgelist_generate_fast(G, path, delimiter, data, encoding):
    # br-cc-wredge-genfast: string/tuple-labelled graphs bail the native
    # `_rust_write_edgelist` and previously fell to `_write_edgelist_via_nx`,
    # which pays a full `_to_nx(G)` conversion (0.27x vs nx). fnx's own
    # `generate_edgelist` is a WIN and byte-identical to networkx's, and
    # `nx.write_edgelist` is exactly this loop over it — so drive that loop
    # directly, skipping the conversion. `open_file` matches nx's filename-or-
    # file-object contract (byte-exact 48/48 incl. directed + mixed attrs).
    from networkx.utils import open_file as _open_file

    @_open_file(1, mode="wb")
    def _emit(G, path):
        for line in generate_edgelist(G, delimiter, data):
            path.write((line + "\n").encode(encoding))

    _emit(G, path)


def _write_adjlist_generate_fast(G, path, comments, delimiter, encoding):
    # br-cc-wadj-genfast: replicate nx.write_adjlist EXACTLY (comment header with
    # argv + GMT timestamp + graph name, then the generate_adjlist write loop)
    # over fnx's fast, byte-identical generate_adjlist — skipping the _to_nx(G)
    # conversion that _write_adjlist_via_nx pays for string/tuple-node graphs.
    import sys
    import time

    from franken_networkx.utils import open_file as _open_file

    @_open_file(1, mode="wb")
    def _emit(G, path):
        pargs = comments + " ".join(sys.argv) + "\n"
        header = (
            pargs
            + comments
            + f" GMT {time.asctime(time.gmtime())}\n"
            + comments
            + f" {G.name}\n"
        )
        path.write(header.encode(encoding))
        for line in generate_adjlist(G, delimiter):
            path.write((line + "\n").encode(encoding))

    _emit(G, path)


def write_edgelist(G, path, comments="#", delimiter=" ", data=True, encoding="utf-8"):
    """Write a graph as a list of edges.

    The default surface uses either the Rust-native writer (simple graphs) or the
    exact local generate/write loop. Non-default formatting kwargs and non-bool
    ``data`` delegate to NetworkX so their public semantics remain exact.
    """
    if comments == "#" and delimiter == " " and encoding == "utf-8":
        if data is False:
            # br-r37-c1-04z53.9187: omitting attrs needs only the exact local
            # generate/write loop; converting the whole graph through `_to_nx`
            # made real output-heavy jobs lose increasingly badly with size.
            return _write_edgelist_generate_fast(G, path, delimiter, data, encoding)
        if data is not True:
            return _write_edgelist_via_nx(
                G,
                path,
                comments=comments,
                delimiter=delimiter,
                data=data,
                encoding=encoding,
            )
        # br-r37-c1-ton6l: the multigraph half of br-r37-c1-04z53.9187.
        # That lever removed the `_to_nx(G)` conversion for SIMPLE graphs only -
        # 570.136ms to 30.158ms on a real n=10k export - and left
        # `not G.is_multigraph()` on the outer gate, so every multigraph export
        # still paid the whole-graph conversion for output networkx produces from
        # a plain loop. nx's `write_edgelist` is that loop for EVERY class:
        #
        #     for line in generate_edgelist(G, delimiter, data):
        #         path.write((line + "\n").encode(encoding))
        #
        # and fnx's `generate_edgelist` is byte-identical to networkx's for the
        # multigraph classes - verified over 96 class x data-spelling x delimiter
        # combinations, and as WRITTEN BYTES for both bool spellings, after
        # br-r37-c1-5xl85 fixed the missing-key divergence found doing exactly
        # this check. So the conversion buys nothing here either.
        #
        # The NATIVE writer stays simple-graph-only: it has no parallel-edge key
        # handling, and nothing about this change asks it to grow one. It writes
        # each edge's own dict where it has one and the stored attributes
        # otherwise - kept in insertion order since br-r37-c1-6hyf1, so an edge
        # with several attributes no longer needs the generate path
        # (br-r37-c1-x5l4x).
        if not G.is_multigraph() and _edgelist_native_writer_preserves_node_labels(G):
            return _rust_write_edgelist(G, path)
        # br-cc-wredge-genfast: default-args string/tuple-node graphs no longer
        # pay the _to_nx(G) conversion in _write_edgelist_via_nx — drive nx's
        # exact write loop over fnx's fast, byte-identical generate_edgelist.
        return _write_edgelist_generate_fast(G, path, delimiter, data, encoding)
    return _write_edgelist_via_nx(
        G, path, comments=comments, delimiter=delimiter, data=data, encoding=encoding
    )


_EDGELIST_LINE_SKIP = object()
_EDGELIST_LINE_SHORT = object()


def _parse_edgelist_line_nx(line, comments, delimiter, nodetype, data):
    """One line of ``networkx.parse_edgelist`` (3.6.1), returned instead of added.

    Returns ``_EDGELIST_LINE_SKIP`` for a comment/blank line,
    ``_EDGELIST_LINE_SHORT`` for a line nx would silently skip (< 2 fields),
    or ``(u, v, edgedata)``; raises nx's own TypeError/IndexError otherwise.
    """
    from ast import literal_eval

    if comments is not None:
        p = line.find(comments)
        if p >= 0:
            line = line[:p]
    if not line.strip():
        return _EDGELIST_LINE_SKIP
    s = line.rstrip("\n").split(delimiter)
    if len(s) < 2:
        return _EDGELIST_LINE_SHORT
    u = s.pop(0)
    v = s.pop(0)
    d = s
    if nodetype is not None:
        try:
            u = nodetype(u)
            v = nodetype(v)
        except Exception as err:
            raise TypeError(f"Failed to convert nodes {u},{v} to type {nodetype}.") from err
    if len(d) == 0 or data is False:
        return u, v, {}
    if data is True:
        try:
            edgedata_str = ",".join(d) if delimiter == "," else " ".join(d)
            return u, v, dict(literal_eval(edgedata_str.strip()))
        except Exception as err:
            raise TypeError(f"Failed to convert edge data ({d}) to dictionary.") from err
    if len(d) != len(data):
        raise IndexError(f"Edge data {d} and data_keys {data} are not the same length")
    edgedata = {}
    for (edge_key, edge_type), edge_value in zip(data, d):
        try:
            edge_value = edge_type(edge_value)
        except Exception as err:
            raise TypeError(
                f"Failed to convert {edge_key} data {edge_value} to type {edge_type}."
            ) from err
        edgedata.update({edge_key: edge_value})
    return u, v, edgedata


def _parse_edgelist_line_fnx_token(line, comments, delimiter, nodetype, data):
    """fnx's native ``left right k=v;k2=v2`` attribute-token form, accepted by
    the mode-aware reader as a fallback where the nx dict literal fails.
    Decoded by the Rust engine itself so its grammar stays the single source."""
    if data is not True or delimiter is not None:
        return None
    if comments is not None:
        p = line.find(comments)
        if p >= 0:
            line = line[:p]
    fields = line.split()
    if len(fields) != 3 or not ("=" in fields[2] or fields[2] == "-"):
        return None
    try:
        one = _rust_read_edgelist(_io.StringIO(" ".join(fields) + "\n"), mode="strict")
    except Exception:
        return None
    edges = list(one.edges(data=True))
    if len(edges) != 1:
        return None
    u, v = fields[0], fields[1]
    if nodetype is not None:
        try:
            u, v = nodetype(u), nodetype(v)
        except Exception:
            return None
    return u, v, dict(edges[0][2])


def _read_edgelist_in_mode(path, mode, *, comments, delimiter, create_using, nodetype, data, encoding):
    """Strict/hardened ``read_edgelist`` over NetworkX's edge-list format.

    br-r37-c1-rc0923-epic-silent-wrong-answers-nro4w.3: the mode-aware path used
    to hand the file to the Rust engine's own ``left right k=v`` parser, which
    treats NetworkX's dict-literal lines (exactly what ``write_edgelist``
    writes) as malformed. Hardened mode therefore "recovered" every line away
    and returned an EMPTY graph for fnx's own output, and explicit strict mode
    rejected it. Now every line is parsed the way ``networkx.parse_edgelist``
    parses it (honouring comments/delimiter/create_using/nodetype/data), with
    the native ``k=v`` token accepted as a fallback. Lines nx would silently
    skip (fewer than two fields) or reject: strict fails closed, hardened skips
    the line and records a FullValidate decision on the returned graph.
    """
    effective = mode if mode is not None else _rust_get_compatibility_mode()
    with compatibility_mode(effective):
        G = empty_graph(0, create_using)
    hardened = effective == "hardened"
    record = getattr(G, "_fnx_record_recovery", None)

    def _reject(lineno, detail, exc=None):
        reason = f"line {lineno} malformed: {detail}"
        if not hardened:
            if exc is not None:
                raise exc
            raise OSError(f"readwrite `read_edgelist` failed closed: {reason}")
        if record is not None:
            record("read_edgelist", reason)
        # nro4w.10: the ledger reaches only callers who query it; a hardened
        # recovery also arrives at the call site, as the native readers' do.
        import warnings as _warnings

        _warnings.warn(reason, RuntimeWarning, stacklevel=2)

    def _consume(lines):
        for lineno, line in enumerate(lines, 1):
            if not isinstance(line, str):
                line = line.decode(encoding)
            try:
                parsed = _parse_edgelist_line_nx(line, comments, delimiter, nodetype, data)
            except (TypeError, IndexError) as exc:
                parsed = _parse_edgelist_line_fnx_token(
                    line, comments, delimiter, nodetype, data
                )
                if parsed is None:
                    _reject(lineno, str(exc), exc)
                    continue
            if parsed is _EDGELIST_LINE_SKIP:
                continue
            if parsed is _EDGELIST_LINE_SHORT:
                _reject(lineno, "expected `left right [attrs]`")
                continue
            u, v, edgedata = parsed
            G.add_edge(u, v, **edgedata)
        return G

    if hasattr(path, "read") and not isinstance(path, (str, bytes)):
        return _consume(path)
    return _read_decoded_lines_via_open_file(path, encoding, _consume)
