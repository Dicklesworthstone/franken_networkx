

def _should_delegate_bellman_ford_path_to_networkx(G, weight):
    """Fast, cached delegation gate for ``bellman_ford_path``.

    Delegates on callable / non-str weight and on NaN / +/-inf / non-numeric edge
    values (nx's relaxation treats NaN/inf as unreachable / negative-cycle and
    raises ``TypeError`` on a non-numeric ``+``). Unlike the Dijkstra gate,
    NEGATIVE weights are valid for Bellman-Ford and do NOT trigger delegation.
    Reuses the single-pass native edge-weight scan (reads ``edge_py_attrs``
    directly) and caches the result on the graph keyed by its revision token, so
    repeated single-pair queries on the same graph don't re-scan every edge.
    """
    if callable(weight) or not isinstance(weight, str):
        return True
    if not G.is_multigraph():
        scan = _cached_native_weight_scan(G, weight)
        if scan is not None:
            _has_negative, has_nonfinite, has_nonnumeric = scan
            return bool(has_nonfinite or has_nonnumeric)
    return _has_nan_or_inf_edge_weight(G, weight) or _has_nonnumeric_edge_weight(G, weight)


def _should_delegate_bellman_ford_to_networkx(weight, G=None):
    if callable(weight):
        return True
    # br-r37-c1-blu7u: route any non-string weight (including
    # ``None`` and ints / floats / bytes / tuples) to nx — the
    # PyO3 binding's ``weight: str`` signature type-rejects.
    if not isinstance(weight, str):
        return True
    # br-r37-c1-djk-strw (sibling): route non-numeric edge values
    # to nx so its TypeError contract on ``+`` propagates.
    if G is not None and _has_nonnumeric_edge_weight(G, weight):
        return True
    # br-r37-c1-bfnannumeric: route NaN / +/-inf edge weights to nx —
    # fnx's Rust path writes them through as distance values (instead
    # of treating them as unreachable / negative-cycle as nx does).
    if G is not None and _has_nan_or_inf_edge_weight(G, weight):
        return True
    return False


def _should_delegate_floyd_warshall_to_networkx(weight):
    if callable(weight):
        return True
    # br-r37-c1-blu7u: same — non-string weights would TypeError on
    # the Rust side; nx silently uses default-1 weights.
    return not isinstance(weight, str)


def _should_delegate_astar_to_networkx(weight, cutoff=None):
    if callable(weight) or cutoff is not None:
        return True
    # br-r37-c1-blu7u: PyO3 binding rejects non-string weights
    # (including ``None``).
    return not isinstance(weight, str)


def _astar_weight_scan_needed(G, weight):
    """Return True when the negative/inf/nonnumeric weight scans must run.

    br-r37-c1-astgate: those scans are O(|E|) and only meaningful when the graph
    actually carries the ``weight`` attribute. For a simple graph with no such
    attribute (the common unweighted case) all three are vacuously False, so a
    single cheap native attr-presence probe lets A* skip three O(|E|) passes.
    Multigraphs and (defensively) a missing native binding keep the full scan
    path. ``inner`` must already be synced before this is called.
    """
    if not isinstance(weight, str):
        return True
    if G.is_multigraph() or _native_has_edge_attr is None:
        return True
    try:
        return bool(_native_has_edge_attr(G, weight))
    except Exception:
        return True


def _should_delegate_negative_edge_cycle_to_networkx(G, weight, heuristic):
    # br-r37-c1-f0i2s: route any non-string weight to nx (PyO3
    # binding's ``weight: str`` signature type-rejects ``None`` / ints
    # / floats / bytes / tuples).  Mirrors br-r37-c1-blu7u's central-
    # gate fix for dijkstra / bellman_ford / floyd_warshall / astar.
    return (
        G.is_directed()
        or callable(weight)
        or not isinstance(weight, str)
        or not isinstance(heuristic, bool)
        or not heuristic
    )


def _raise_translated_networkx_exception(exc):
    import networkx as nx

    if isinstance(exc, nx.NetworkXException):
        translated_type = globals().get(type(exc).__name__)
        if (
            isinstance(translated_type, type)
            and issubclass(translated_type, Exception)
            and translated_type is not type(exc)
        ):
            raise translated_type(*exc.args) from exc
    raise exc


def _call_networkx_for_parity(name, G, /, *args, **kwargs):
    import networkx as nx

    # br-parityrec: if the user configured the nx dispatcher to route to
    # franken_networkx (``nx.config.backend_priority = ["franken_networkx"]``),
    # then calling `getattr(nx, name)(...)` re-enters the dispatcher and
    # bounces right back into this helper — infinite recursion. Forcing
    # ``backend="networkx"`` here bypasses dispatch so parity fallbacks
    # always reach nx's pure-Python implementation. nx's `_dispatchable`
    # decorator honours an explicit `backend` kwarg even when the function
    # is already dispatched.
    kwargs.setdefault("backend", "networkx")
    try:
        result = getattr(nx, name)(_networkx_graph_for_parity(G), *args, **kwargs)
    except Exception as exc:
        _raise_translated_networkx_exception(exc)

    if isinstance(result, _Iterator):
        def _wrapped_iterator():
            try:
                yield from result
            except Exception as exc:
                _raise_translated_networkx_exception(exc)

        return _wrapped_iterator()

    return result


def _call_networkx_for_dijkstra_parity(name, G, /, *args, **kwargs):
    import networkx as nx

    kwargs.setdefault("backend", "networkx")
    try:
        result = getattr(nx, name)(
            _networkx_graph_for_dijkstra_parity(G), *args, **kwargs
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)

    if isinstance(result, _Iterator):
        def _wrapped_iterator():
            try:
                yield from result
            except Exception as exc:
                _raise_translated_networkx_exception(exc)

        return _wrapped_iterator()

    return result


def _complement_via_nx(G):
    """Private helper: retained for internal compatibility; returns complement(G)."""
    return complement(G)


def _random_generator_subset(seq, m, rng):
    """Return m unique elements from a repeated-node population."""
    targets = set()
    while len(targets) < m:
        targets.add(rng.choice(seq))
    return targets


def _call_networkx_submodule_for_parity(submodule_path, name, G, /, *args, **kwargs):
    """Same contract as ``_call_networkx_for_parity`` but resolves the
    callable from a dotted nx submodule path (e.g.
    ``"algorithms.community"``) for functions that upstream nx does
    not re-export at the top level.
    """
    import importlib

    submodule = importlib.import_module(f"networkx.{submodule_path}")
    # br-parityrec: mirror the top-level helper's dispatch-bypass. Without
    # this, `nx.config.backend_priority = ["franken_networkx"]` causes the
    # submodule call to re-enter fnx → infinite recursion.
    kwargs.setdefault("backend", "networkx")
    try:
        result = getattr(submodule, name)(
            _networkx_graph_for_parity(G), *args, **kwargs
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)

    if isinstance(result, _Iterator):
        def _wrapped_iterator():
            try:
                yield from result
            except Exception as exc:
                _raise_translated_networkx_exception(exc)

        return _wrapped_iterator()

    return result


def _validate_shortest_path_length_source_query(G, source, weight, method):
    if weight is None:
        if source not in G:
            raise NodeNotFound(f"Source {source} is not in G")
        return

    if method == "dijkstra":
        {source}
    else:
        _HASH_PROBE.get(source)

    if source in G:
        return

    if method == "dijkstra":
        raise NodeNotFound(f"Node {source} not found in graph")

    raise NodeNotFound(f"Source {source} not in G")


def _weight_function(G, weight):
    """Returns a function that returns the weight of an edge.
    Matches networkx.algorithms.shortest_paths.weighted._weight_function.
    """
    if callable(weight):
        return weight
    if G.is_multigraph():
        return lambda u, v, d: min(attr.get(weight, 1) for attr in d.values())
    return lambda u, v, data: data.get(weight, 1)


def _dijkstra_multisource_inproc(
    G, sources, weight, pred=None, paths=None, cutoff=None, target=None
):
    """Uses Dijkstra's algorithm to find shortest weighted paths in-process.
    Matches networkx.algorithms.shortest_paths.weighted._dijkstra_multisource.
    """
    import heapq as _heapq
    import itertools as _itertools

    pred_dict = pred if paths is None or pred is not None else {}
    G_succ = G._adj
    # NetworkX swaps the private mappings directly for reverse views. Public
    # neighbor adapters can wrap a malformed row and change its .items() error.
    # Unwrap only these unfiltered adapters, keeping every filter/conversion.
    while isinstance(G_succ, _ReverseAdjacencyView) and _point_query_uses_private_rows(G):
        parent = G_succ._view._graph
        G_succ = parent._succ if G_succ._reverse else parent._pred

    dist = {}
    seen = {}
    c = _itertools.count()
    fringe = []
    for source in sources:
        seen[source] = 0
        _heapq.heappush(fringe, (0, next(c), source))
    number_of_sources = len(seen)
    while fringe:
        (dist_v, _, v) = _heapq.heappop(fringe)
        if v in dist:
            continue
        dist[v] = dist_v
        if v == target:
            break
        for u, e in G_succ[v].items():
            cost = weight(v, u, e)
            if cost is None:
                continue
            vu_dist = dist_v + cost
            if cutoff is not None and vu_dist > cutoff:
                continue
            if u in dist:
                u_dist = dist[u]
                if vu_dist < u_dist:
                    raise ValueError("Contradictory paths found:", "negative weights?")
                elif pred is not None and vu_dist == u_dist:
                    pred_dict[u].append(v)
            elif u not in seen or vu_dist < seen[u]:
                seen[u] = vu_dist
                _heapq.heappush(fringe, (vu_dist, next(c), u))
                if pred_dict is not None:
                    pred_dict[u] = [v]
            elif pred is not None and vu_dist == seen[u]:
                pred_dict[u].append(v)

    if paths is not None:
        if target is None:
            for v in _itertools.islice(dist, number_of_sources, None):
                paths[v] = paths[pred_dict[v][0]] + [v]
        else:
            path = paths[target] = [target]
            while (current_preds := pred_dict.get(path[-1])) is not None:
                path.append(current_preds[0])
            path.reverse()

    return dist


def _multi_source_dijkstra_inproc(G, sources, target=None, cutoff=None, weight="weight"):
    """In-process multi-source / single-source Dijkstra shortest paths and lengths."""
    if not sources:
        raise ValueError("sources must not be empty")
    for s in sources:
        if s not in G:
            raise NodeNotFound(f"Node {s} not found in graph")
    if target in sources:
        return (0, [target])
    weight_fn = _weight_function(G, weight)
    paths = {source: [source] for source in sources}
    dist = _dijkstra_multisource_inproc(
        G, sources, weight_fn, paths=paths, cutoff=cutoff, target=target
    )
    if target is None:
        return (dist, paths)
    try:
        return (dist[target], paths[target])
    except KeyError as err:
        raise NetworkXNoPath(f"No path to {target}.") from err


def _dijkstra_path_length_inproc(G, source, target, weight="weight"):
    """In-process Dijkstra shortest path length matching NetworkX's contract."""
    if source not in G:
        raise NodeNotFound(f"Node {source} not found in graph")
    if source == target:
        return 0
    weight_fn = _weight_function(G, weight)
    length = _dijkstra_multisource_inproc(G, [source], weight_fn, target=target)
    try:
        return length[target]
    except KeyError as err:
        raise NetworkXNoPath(f"Node {target} not reachable from {source}") from err


def _dijkstra_predecessor_and_distance_inproc(G, source, cutoff=None, weight="weight"):
    """In-process Dijkstra predecessor and distance dictionaries matching NetworkX."""
    if source not in G:
        raise NodeNotFound(f"Node {source} is not found in the graph")
    weight_fn = _weight_function(G, weight)
    pred = {source: []}
    dist = _dijkstra_multisource_inproc(
        G, [source], weight_fn, pred=pred, cutoff=cutoff
    )
    return (pred, dist)


def _floyd_warshall_predecessor_and_distance_inproc(G, weight="weight"):
    """In-process Floyd-Warshall predecessor and distance dictionaries matching NetworkX."""
    from collections import defaultdict as _defaultdict
    dist = _defaultdict(lambda: _defaultdict(lambda: float("inf")))
    for u in G:
        dist[u][u] = 0
    pred = _defaultdict(dict)
    undirected = not G.is_directed()
    for u, v, d in G.edges(data=True):
        e_weight = d.get(weight, 1.0)
        dist[u][v] = min(e_weight, dist[u][v])
        pred[u][v] = u
        if undirected:
            dist[v][u] = min(e_weight, dist[v][u])
            pred[v][u] = v
    for w in G:
        dist_w = dist[w]
        for u in G:
            dist_u = dist[u]
            for v in G:
                d = dist_u[w] + dist_w[v]
                if dist_u[v] > d:
                    dist_u[v] = d
                    pred[u][v] = pred[w][v]
    return dict(pred), dict(dist)


def average_shortest_path_length(G, weight=None, method=None):
    """Return the average shortest path length.

    Matches ``networkx.average_shortest_path_length`` signature.
    """
    # br-r37-c1-10xrd: materialize SubgraphView so the Rust path sees
    # the filtered nodes/edges (and correctly raises NetworkXError
    # when the view is disconnected). Same view-coerce family as
    # br-r37-c1-ajhcl / -c7xg2 / -2dbnk.
    G = _coerce_arg_to_fnx_graph(G)
    _SUPPORTED_METHODS = (
        None, "unweighted", "dijkstra", "bellman-ford",
        "floyd-warshall", "floyd-warshall-numpy",
    )
    if method not in _SUPPORTED_METHODS:
        raise ValueError(f"method not supported: {method}")
    # br-asplint: nx returns literal int 0 for the single-node graph
    # (no divisions happen on that code path); fnx's Rust-native path
    # returns 0.0 float. Match nx's exact type so isinstance(..., int)
    # checks downstream don't diverge.
    n = G.number_of_nodes()
    if n == 1:
        return 0
    # In-process exact Floyd-Warshall variants
    if method in ("floyd-warshall", "floyd-warshall-numpy"):
        if G.is_directed() and not is_strongly_connected(G):
            raise NetworkXError("Graph is not strongly connected.")
        if not G.is_directed() and not is_connected(G):
            raise NetworkXError("Graph is not connected.")
        if method == "floyd-warshall":
            all_pairs = floyd_warshall(G, weight=weight)
            s = sum(sum(t.values()) for t in all_pairs.values())
        else:
            s = float(floyd_warshall_numpy(G, weight=weight).sum())
        return s / (n * (n - 1))
    if weight is not None and method in (None, "dijkstra") and _should_delegate_dijkstra_to_networkx(G, weight):
        if G.is_directed() and not is_strongly_connected(G):
            raise NetworkXError("Graph is not strongly connected.")
        if not G.is_directed() and not is_connected(G):
            raise NetworkXError("Graph is not connected.")
        s = sum(
            l
            for u in G
            for l in single_source_dijkstra_path_length(G, u, weight=weight).values()
        )
        return s / (n * (n - 1))
    if isinstance(weight, str):
        # br-r37-c1-4tmgq: the native kernel reads the Rust attr store; push any
        # post-construction Python-side edge attribute writes down first. The
        # sync is a no-op when the store is clean.
        _sync_rust_edge_attrs(G, edge_only=True)
    return _raw_average_shortest_path_length(G, weight=weight, method=method)


def dijkstra_path(G, source, target, weight="weight"):
    """Return the shortest weighted path from ``source`` to ``target`` in ``G``.

    Mirrors ``networkx.dijkstra_path``: returns a list of nodes along
    the shortest path. Raises ``NetworkXNoPath`` if no path exists and
    ``NodeNotFound`` if ``source`` is missing.
    """
    # Private rows override Rust storage, including through live views. Query
    # them before coercion can materialize a stale native graph.
    if _point_query_uses_private_rows(G):
        return _multi_source_dijkstra_inproc(G, {source}, target=target, weight=weight)[1]
    # br-r37-c1-phy2p: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if weight is None:
        sources = {source}  # Match NetworkX's set-key TypeError, not dict wording.
        if source not in G:
            raise NodeNotFound(f"Node {source} not found in graph")
        # None is also the source-wide target sentinel in NetworkX. Subclasses
        # can supply custom Python rows/attributes and retain that traversal.
        if target is not None and type(G) in _CONCRETE_FNX_GRAPH_TYPES:
            target in sources  # NetworkX hash-checks the target against sources.
            native = _fnx.dijkstra_path_to_target(G, source, target, None)
            if native is not None:
                return native[2]
        # A None-keyed attribute is a real weight, not an ignored one. The
        # native unit-weight specialization declines rather than guessing.
        return _multi_source_dijkstra_inproc(G, sources, target=target, weight=None)[1]
    # br-r37-c1-c4agn: hash-check for nx-shaped TypeError parity.
    _HASH_PROBE.get(source)
    _HASH_PROBE.get(target)
    # br-cc-mgdijkstra-dir: a DIRECTED multigraph collapses to a simple min-weight
    # DiGraph byte-EXACTLY even for the PATH (unlike undirected MG, where edges()'
    # canonical direction reorders per-node adjacency and perturbs tie-breaking).
    # In a directed multigraph edges(keys,data) is node-major over OUT-edges, so the
    # collapsed DiGraph's adjacency order == the multigraph's out-adjacency order ->
    # identical heap-push/tie-break -> byte-identical predecessor chain. Verified.
    if G.is_directed() and G.is_multigraph() and isinstance(weight, str):
        if source not in G:
            raise NodeNotFound(f"Node {source} not found in graph")
        if target not in G:
            raise NetworkXNoPath(f"No path to {target}.")
        # br-r37-c1-04z53.9172: see dijkstra_path_length — the raw MultiDiGraph
        # kernel is entered before the delegation predicate, and its own
        # "return None to delegate" rule has no exactness dimension.
        if _should_delegate_dijkstra_to_networkx(G, weight):
            return single_source_dijkstra(G, source, target=target, weight=weight)[1]
        try:
            _direct = _raw_multidigraph_dijkstra_path_target(
                G, source, target, weight=weight
            )
        except NetworkXNoPath:
            raise NetworkXNoPath(f"No path to {target}.") from None
        if _direct is not None:
            return _direct
        _simple, _delegate = _multigraph_collapse_min_weight(G, weight)
        if _delegate:
            return single_source_dijkstra(G, source, target=target, weight=weight)[1]
        return dijkstra_path(_simple, source, target, weight=weight)
    route = _dijkstra_weight_route(G, weight)
    if route == "networkx":
        return single_source_dijkstra(G, source, target=target, weight=weight)[1]
    if source not in G:
        raise NodeNotFound(f"Node {source} not found in graph")
    if target not in G:
        if route == "rows":
            # networkx walks the whole component (reading its weights) first.
            return _rerun_with_weight_scan(dijkstra_path, G, source, target, weight)
        raise NetworkXNoPath(f"No path to {target}.")
    # br-r37-c1-lc2qy (cc): native single-pair Dijkstra with TARGET early-exit — stops
    # when the target finalizes and reconstructs only the target's predecessor chain,
    # skipping both the exploration past the target and single_source_dijkstra_path's
    # all-paths String construction (~60% of its cost). The predecessor chain is built
    # identically to single_source_dijkstra_path, so the path is byte-identical to nx
    # (verified 1245/1245). The edge-only sync (a no-op for clean graphs) covers
    # post-construction weight mutation. Falls back to single_source for callable weight.
    _ptt = getattr(_fnx, "dijkstra_path_to_target", None)
    if _ptt is not None and isinstance(weight, str):
        _sync_rust_edge_attrs(G, edge_only=True)
        try:
            _length, _all_int, path = _ptt(G, source, target, weight, route == "rows")
        except NetworkXNoPath:
            raise NetworkXNoPath(f"No path to {target}.") from None
        except _WeightRowsUnverified:
            path = None
        if path is None:
            return _rerun_with_weight_scan(dijkstra_path, G, source, target, weight)
        return path
    paths = single_source_dijkstra_path(G, source, weight=weight)
    if target not in paths:
        raise NetworkXNoPath(f"No path to {target}.")
    return paths[target]


def _build_paths_from_predecessors(sources, target, pred):
    """Compute all simple paths to target, given predecessors, terminating at sources."""
    if target not in pred:
        raise NetworkXNoPath(f"Target {target} cannot be reached from given sources")

    seen = {target}
    stack = [[target, 0]]
    top = 0
    while top >= 0:
        node, i = stack[top]
        if node in sources:
            yield [p for p, n in reversed(stack[: top + 1])]
        if len(pred[node]) > i:
            stack[top][1] = i + 1
            next_node = pred[node][i]
            if next_node in seen:
                continue
            else:
                seen.add(next_node)
            top += 1
            if top == len(stack):
                stack.append([next_node, 0])
            else:
                stack[top][:] = [next_node, 0]
        else:
            seen.discard(node)
            top -= 1


def _inner_bellman_ford_inproc(
    G,
    sources,
    weight,
    pred,
    dist=None,
    heuristic=True,
):
    from collections import deque as _deque

    for s in sources:
        if s not in G:
            raise NodeNotFound(f"Source {s} not in G")

    if pred is None:
        pred = {v: [] for v in sources}

    if dist is None:
        dist = {v: 0 for v in sources}

    nonexistent_edge = (None, None)
    pred_edge = {v: None for v in sources}
    recent_update = {v: nonexistent_edge for v in sources}

    G_succ = G._adj
    inf = float("inf")
    n = len(G)

    count = {}
    q = _deque(sources)
    in_q = set(sources)
    while q:
        u = q.popleft()
        in_q.remove(u)

        if all(pred_u not in in_q for pred_u in pred[u]):
            dist_u = dist[u]
            for v, e in G_succ[u].items():
                dist_v = dist_u + weight(u, v, e)

                if dist_v < dist.get(v, inf):
                    if heuristic:
                        if v in recent_update[u]:
                            pred[v].append(u)
                            return v

                        if v in pred_edge and pred_edge[v] == u:
                            recent_update[v] = recent_update[u]
                        else:
                            recent_update[v] = (u, v)

                    if v not in in_q:
                        q.append(v)
                        in_q.add(v)
                        count_v = count.get(v, 0) + 1
                        if count_v == n:
                            return v

                        count[v] = count_v
                    dist[v] = dist_v
                    pred[v] = [u]
                    pred_edge[v] = u

                elif dist.get(v) is not None and dist_v == dist.get(v):
                    pred[v].append(u)

    return None


def _bellman_ford_inproc(
    G,
    source,
    weight,
    pred=None,
    paths=None,
    dist=None,
    target=None,
    heuristic=True,
):
    if pred is None:
        pred = {v: [] for v in source}

    if dist is None:
        dist = {v: 0 for v in source}

    negative_cycle_found = _inner_bellman_ford_inproc(
        G,
        source,
        weight,
        pred,
        dist,
        heuristic,
    )
    if negative_cycle_found is not None:
        raise NetworkXUnbounded("Negative cycle detected.")

    if paths is not None:
        sources = set(source)
        dsts = [target] if target is not None else pred
        for dst in dsts:
            gen = _build_paths_from_predecessors(sources, dst, pred)
            paths[dst] = next(gen)

    return dist


def _single_source_bellman_ford_inproc(G, source, target=None, weight="weight"):
    if source == target:
        if source not in G:
            raise NodeNotFound(f"Node {source} is not found in the graph")
        return (0, [source])

    weight_fn = _weight_function(G, weight)

    paths = {source: [source]}
    dist = _bellman_ford_inproc(G, [source], weight_fn, paths=paths, target=target)
    if target is None:
        return (dist, paths)
    try:
        return (dist[target], paths[target])
    except KeyError as err:
        msg = f"Node {target} not reachable from {source}"
        raise NetworkXNoPath(msg) from err


def _bellman_ford_path_length_inproc(G, source, target, weight="weight"):
    if source == target:
        if source not in G:
            raise NodeNotFound(f"Node {source} not found in graph")
        return 0

    weight_fn = _weight_function(G, weight)

    length = _bellman_ford_inproc(G, [source], weight_fn, target=target)

    try:
        return length[target]
    except KeyError as err:
        raise NetworkXNoPath(f"node {target} not reachable from {source}") from err


def bellman_ford_path(G, source, target, weight="weight"):
    """Return the shortest path from ``source`` to ``target`` via Bellman-Ford.

    Handles negative edge weights (Dijkstra requires non-negative).
    Mirrors ``networkx.bellman_ford_path``. Raises ``NetworkXUnbounded``
    on negative cycles, ``NetworkXNoPath`` if no path exists.
    """
    if _point_query_uses_private_rows(G):
        return _single_source_bellman_ford_inproc(
            G, source, target=target, weight=weight
        )[1]
    # br-r37-c1-bfpathnative: the native single-pair Bellman-Ford kernel now
    # returns nx-identical PATHS — verified on 240 directed/undirected pairs incl.
    # negative weights and multigraph parallel edges, 0 mismatches (the old
    # br-r37-c1-9axrp "returns incorrect paths" note is stale). Route to it
    # instead of paying the full fnx->nx conversion (~5.4x). The kernel's error
    # TYPES/MESSAGES diverge from nx, so the wrapper owns the nx error contract:
    # NodeNotFound("Source ... not in G") for a missing source;
    # NetworkXNoPath("Target ... cannot be reached from given sources") for an
    # unreachable OR missing target (nx does not check target existence); and
    # NetworkXUnbounded("Negative cycle detected.") on a negative cycle. Callable
    # / non-str weight stays on the nx parity path (the kernel needs a str attr).
    G = _coerce_arg_to_fnx_graph(G)
    # nx hashes source/target during traversal, so unhashable nodes raise
    # ``TypeError: unhashable type: ...``. fnx's graph ``__contains__`` swallows
    # that TypeError (returns False), so validate hashability explicitly to match
    # nx's contract before the ``source in G`` membership test below.
    _HASH_PROBE.get(source)
    _HASH_PROBE.get(target)
    # br-cc-mgbfpath: a DIRECTED multigraph collapses to the simple min-weight
    # DiGraph byte-EXACTLY for the PATH (like dijkstra_path — directed
    # edges(keys,data) is node-major over OUT-edges, so the collapsed DiGraph's
    # adjacency order == the multigraph's out-adjacency order, giving identical
    # relaxation/tie-break -> identical predecessor chain; verified 720/720 incl.
    # negative weights). The native multigraph Bellman-Ford kernel walks nested
    # per-pair buckets and is ~3.3x slower than the collapse + fast simple kernel
    # (0.16x -> ~0.52x, matching the already-shipped bellman_ford_path_length
    # collapse). Bellman-Ford keeps negatives, so the collapse validates+delegates
    # only NaN/inf/non-numeric (via _multigraph_collapse_min_weight_bellman). The
    # UNDIRECTED MultiGraph path is NOT collapse-safe (edges()' canonical
    # direction reorders per-node adjacency -> 1/720 tie-break path divergence),
    # so it stays on the byte-exact native kernel below.
    if G.is_directed() and G.is_multigraph() and isinstance(weight, str):
        _simple, _delegate = _multigraph_collapse_min_weight_bellman(G, weight)
        if _delegate:
            return _single_source_bellman_ford_inproc(
                G, source, target=target, weight=weight
            )[1]
        return bellman_ford_path(_simple, source, target, weight=weight)
    # Delegate to in-process Bellman-Ford for: callable / non-str weight, and
    # NaN/inf or non-numeric edge values. Bellman-Ford legitimately allows
    # NEGATIVE weights, so — unlike the Dijkstra gate — a negative edge does NOT
    # trigger fallback.
    route = _bellman_ford_weight_route(G, weight)
    if route == "networkx":
        return _single_source_bellman_ford_inproc(
            G, source, target=target, weight=weight
        )[1]
    if source not in G:
        raise NodeNotFound(f"Source {source} not in G")
    # nx's single_source_bellman_ford short-circuits source == target to
    # ``[source]`` BEFORE any relaxation, so it never detects a negative cycle in
    # that case; the native kernel runs the full relaxation and would raise.
    # Mirror nx's early return.
    if source == target:
        return [source]
    if target not in G:
        # networkx walks the source's component (reading its weights) before
        # it finds the target missing, so a negative cycle there wins.
        if route == "rows":
            return _rerun_with_weight_scan(bellman_ford_path, G, source, target, weight)
        single_source_bellman_ford_path_length(G, source, weight=weight)
        raise NetworkXNoPath(f"Target {target} cannot be reached from given sources")
    try:
        return _raw_bellman_ford_path(
            G, source, target, weight=weight, check_rows=route == "rows"
        )
    except NetworkXUnbounded:
        raise NetworkXUnbounded("Negative cycle detected.")
    except (NetworkXNoPath, NodeNotFound):
        raise NetworkXNoPath(
            f"Target {target} cannot be reached from given sources"
        )
    except _WeightRowsUnverified:
        pass
    return _rerun_with_weight_scan(bellman_ford_path, G, source, target, weight)


def _point_query_uses_private_rows(G):
    """Private root rows must be queried before a view is copied to Rust."""
    if type(G) in _CONCRETE_FNX_GRAPH_TYPES:
        return _has_networkx_private_storage(G)
    root = G
    while isinstance(root, (_FilteredGraphView, _ReverseDirectedViewBase, _ConversionGraphViewBase)):
        # Synthetic views install private adapters even on a native root.
        # Those markers alone must not disqualify the ordinary native route.
        root = root._graph
    return isinstance(root, (Graph, DiGraph, MultiGraph, MultiDiGraph)) and _has_networkx_private_storage(root)


def shortest_path(
    G, source=None, target=None, weight=None, method="dijkstra",
    *, backend=None, **backend_kwargs,
):
    """Compute shortest paths in ``G``.

    With both ``source`` and ``target``: returns a single path. With only one,
    returns a dict keyed by the other endpoint. With neither, returns an
    iterator of ``(source, paths_dict)`` pairs. ``method`` selects the weighted
    algorithm (``"dijkstra"`` or ``"bellman-ford"``); set ``weight=None`` for
    unweighted BFS. Mirrors ``networkx.shortest_path``.
    """
    # br-r37-c1-spbk: nx adds `backend=None, **backend_kwargs` to all
    # dispatchable functions via the @_dispatchable decorator. Drop-in
    # code that does `nx.shortest_path(G, ..., backend='networkx')`
    # crashed on fnx with `TypeError: shortest_path() got an unexpected
    # keyword argument 'backend'`. Match the dispatch surface.
    _validate_backend_dispatch_keywords("shortest_path", backend, backend_kwargs)
    if _point_query_uses_private_rows(G):
        if method not in ("dijkstra", "bellman-ford"):
            raise ValueError(f"method not supported: {method}")
        if source is None and target is None:
            if weight is None:
                return all_pairs_shortest_path(G)
            if method == "bellman-ford":
                return all_pairs_bellman_ford_path(G, weight=weight)
            return all_pairs_dijkstra_path(G, weight=weight)
        if source is None or target is None:
            endpoint = target if source is None else source
            H = G.reverse(copy=False) if source is None and G.is_directed() else G
            if weight is None:
                paths = single_source_shortest_path(H, endpoint)
            elif method == "bellman-ford":
                paths = single_source_bellman_ford_path(H, endpoint, weight=weight)
            else:
                paths = single_source_dijkstra_path(H, endpoint, weight=weight)
            if source is None:
                return {node: list(reversed(path)) for node, path in paths.items()}
            return paths
        if weight is None:
            return bidirectional_shortest_path(G, source, target)
        if method == "bellman-ford":
            return bellman_ford_path(G, source, target, weight=weight)
        return bidirectional_dijkstra(G, source, target, weight=weight)[1]
    # br-r37-c1-phy2p: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if method not in ("dijkstra", "bellman-ford"):
        raise ValueError(f"method not supported: {method}")
    if _path_query_has_missing_nodes(G, source=source, target=target):
        if source is not None and target is not None:
            if weight is None:
                return bidirectional_shortest_path(G, source, target)
            if method == "bellman-ford":
                return bellman_ford_path(G, source, target, weight=weight)
            return bidirectional_dijkstra(G, source, target, weight=weight)[1]
        if source is not None and target is None:
            if weight is None:
                return single_source_shortest_path(G, source)
            if method == "bellman-ford":
                return single_source_bellman_ford_path(G, source, weight=weight)
            return single_source_dijkstra_path(G, source, weight=weight)
        if source is None and target is not None:
            H = G.reverse(copy=False) if G.is_directed() else G
            if weight is None:
                paths = single_source_shortest_path(H, target)
            elif method == "bellman-ford":
                paths = single_source_bellman_ford_path(H, target, weight=weight)
            else:
                paths = single_source_dijkstra_path(H, target, weight=weight)
            return {u: list(reversed(p)) for u, p in paths.items()}
    if isinstance(weight, str) and source is not None and target is not None:
        # br-r37-c1-spw (cc): the weighted SINGLE-PAIR case must match nx's path
        # tie-break. nx.shortest_path routes weighted point-to-point through
        # bidirectional_dijkstra (dijkstra) / bellman_ford_path - whose specific path
        # among equal-weight alternatives differs from the native _raw_shortest_path
        # single-pair kernel (n30yf class). fnx's bidirectional_dijkstra /
        # bellman_ford_path are byte-identical to nx, so route through them.
        # br-r37-c1-04z53.9171 / br-r37-c1-svsam: both own their weight
        # validation (including the row-checked route after a write), and a point
        # query ended in them whichever way a gate here answered - so a
        # whole-graph weight scan here only made the call O(E).
        if method == "bellman-ford":
            return bellman_ford_path(G, source, target, weight=weight)
        return bidirectional_dijkstra(G, source, target, weight=weight)[1]
    if weight is not None:
        if method == "dijkstra" and _should_delegate_dijkstra_to_networkx(G, weight):
            if source is not None and target is not None:
                return bidirectional_dijkstra(G, source, target, weight=weight)[1]
            if source is not None and target is None:
                return single_source_dijkstra_path(G, source, weight=weight)
            if source is None and target is not None:
                H = G.reverse(copy=False) if G.is_directed() else G
                paths = single_source_dijkstra_path(H, target, weight=weight)
                return {u: list(reversed(p)) for u, p in paths.items()}
            return all_pairs_dijkstra_path(G, weight=weight)
        if method == "bellman-ford" and _should_delegate_bellman_ford_to_networkx(weight, G):
            if source is not None and target is not None:
                return bellman_ford_path(G, source, target, weight=weight)
            if source is not None and target is None:
                return single_source_bellman_ford_path(G, source, weight=weight)
            if source is None and target is not None:
                H = G.reverse(copy=False) if G.is_directed() else G
                paths = single_source_bellman_ford_path(H, target, weight=weight)
                return {u: list(reversed(p)) for u, p in paths.items()}
            return all_pairs_bellman_ford_path(G, weight=weight)
    if weight is None and source is not None and target is not None:
        # br-gauntlet-sp-bidir: nx.shortest_path routes the unweighted
        # point-to-point case through ``bidirectional_shortest_path``, whose
        # meet-in-the-middle predecessor construction selects one specific path
        # among equal-length alternatives. ``_raw_shortest_path`` used a plain
        # forward BFS, returning a different (still valid, same length) path and
        # breaking byte-for-byte parity on grids / regular graphs / any graph
        # with multiple shortest paths. fnx's ``bidirectional_shortest_path``
        # already matches nx exactly (incl. the NetworkXNoPath wording and the
        # source==target single-node path), so delegate to it.
        return bidirectional_shortest_path(G, source, target)
    if weight is None and source is not None and target is None:
        # br-r37-c1-spsrc (cc): nx.shortest_path(G, source) returns EXACTLY
        # single_source_shortest_path(G, source). fnx's single_source kernel is
        # ~1.6x faster than nx, but shortest_path fell through to the
        # _raw_shortest_path source-only path which was ~2x SLOWER than the
        # single_source kernel (0.72-0.84x vs nx). Route to the fast kernel —
        # byte-identical (both match nx exactly, 15/15 parity incl. BFS-discovery
        # key order and the source self-path).
        return single_source_shortest_path(G, source)
    if weight is None and source is None and target is None:
        # cc-spapsp: nx.shortest_path(G) (all pairs, unweighted) dispatches to
        # all_pairs_shortest_path. Route there — it uses the index-emitter fast
        # path (cc-apspidx) — instead of falling through to _raw_shortest_path's
        # all-pairs branch, which materialized a String-cloned dict-of-dicts
        # (~0.76x nx). Byte-identical: same (source, paths_dict) generator
        # contract, same BFS-discovery inner-key order, same source node order.
        return all_pairs_shortest_path(G)
    if isinstance(weight, str):
        # br-gauntlet-sp-weightsync: the weighted path runs the native
        # ``_raw_shortest_path`` kernel, which reads edge weights from the Rust
        # ``inner`` adjacency. ``shortest_path`` historically relied on
        # ``_should_delegate_dijkstra_to_networkx`` syncing ``inner`` as a side
        # effect, but that gate now uses a fast scan over ``edge_py_attrs`` that
        # skips the sync. Without an explicit sync here, a post-construction
        # weight mutation (``G.edges[u, v]["weight"] = w``) is invisible to the
        # native kernel and it returns a NON-OPTIMAL path (e.g. weight 22 vs the
        # true 12). Sync ``inner`` before the kernel, matching dijkstra_path.
        # br-r37-c1-syncedgeonly: edge-only sync (reads edge weights, not node
        # attrs) — skips the full sync's unguarded O(N) node-attr rebuild.
        _sync_rust_edge_attrs(G, edge_only=True)
    result = _raw_shortest_path(G, source=source, target=target, weight=weight, method=method)
    if source is None and target is None and isinstance(result, dict):
        # networkx returns a generator of (source, paths_dict) pairs when both
        # endpoints are omitted (dispatches to all_pairs_*). The Rust native
        # path materializes the full dict-of-dicts; convert to match contract.
        return ((src, paths) for src, paths in result.items())
    # weighted sp batch (supersedes br-r37-c1-62jy2): the binding now
    # emits dicts in the KERNEL's order — BFS discovery (unweighted),
    # dijkstra finalize order, bellman-ford SPFA discovery order — which
    # is nx's exact contract. The old distance-re-sort here actively
    # BROKE bellman-ford parity (nx does NOT distance-sort SPFA output).
    return result


def shortest_path_length(G, source=None, target=None, weight=None, method="dijkstra"):
    """Return shortest path length between source and target.

    If *source* and *target* are both None, return an iterator over
    ``(node, dict)`` pairs for all nodes.
    If only *source* is given, return a dict mapping target to length.
    If both are given, return a single number.
    Matches ``networkx.shortest_path_length``.

    Native-root views materialize as needed; private-root queries
    walk their current Python rows without copying to native storage.
    """
    if _point_query_uses_private_rows(G):
        if method not in ("dijkstra", "bellman-ford"):
            raise ValueError(f"method not supported: {method}")
        if source is None and target is None:
            if weight is None:
                return all_pairs_shortest_path_length(G)
            if method == "bellman-ford":
                return all_pairs_bellman_ford_path_length(G, weight=weight)
            return all_pairs_dijkstra_path_length(G, weight=weight)
        if source is None or target is None:
            endpoint = target if source is None else source
            H = G.reverse(copy=False) if source is None and G.is_directed() else G
            if weight is None:
                return single_source_shortest_path_length(H, endpoint)
            if method == "bellman-ford":
                return single_source_bellman_ford_path_length(H, endpoint, weight=weight)
            return single_source_dijkstra_path_length(H, endpoint, weight=weight)
        if weight is None:
            return len(bidirectional_shortest_path(G, source, target)) - 1
        if method == "bellman-ford":
            return bellman_ford_path_length(G, source, target, weight=weight)
        return dijkstra_path_length(G, source, target, weight=weight)
    G = _coerce_arg_to_fnx_graph(G)
    if method not in ("dijkstra", "bellman-ford"):
        raise ValueError(f"method not supported: {method}")
    if _path_query_has_missing_nodes(G, source=source, target=target):
        if source is not None and target is not None:
            if weight is None:
                return len(bidirectional_shortest_path(G, source, target)) - 1
            if method == "bellman-ford":
                return bellman_ford_path_length(G, source, target, weight=weight)
            if weight is not None:
                return dijkstra_path_length(G, source, target, weight=weight)
            return len(bidirectional_shortest_path(G, source, target)) - 1
        if source is not None and target is None:
            _validate_shortest_path_length_source_query(G, source, weight, method)
            if weight is not None:
                if method == "bellman-ford":
                    return dict(single_source_bellman_ford_path_length(G, source, weight=weight))
                return dict(single_source_dijkstra_path_length(G, source, weight=weight))
            return dict(single_source_shortest_path_length(G, source))
        if source is None and target is not None:
            H = G.reverse(copy=False) if G.is_directed() else G
            _validate_shortest_path_length_source_query(H, target, weight, method)
            if weight is not None:
                if method == "bellman-ford":
                    return dict(single_source_bellman_ford_path_length(H, target, weight=weight))
                return dict(single_source_dijkstra_path_length(H, target, weight=weight))
            return dict(single_source_shortest_path_length(H, target))

    if weight is not None:
        # br-cc-mgdijkstra / br-r37-c1-svsam: with a SOURCE given, the dijkstra
        # weight-validity gate is redundant - the dispatch routes through
        # dijkstra_path_length / single_source_dijkstra_path_length whichever way
        # it answers, and both validate + delegate bad weights themselves (for a
        # multigraph via the min-weight collapse, for a simple graph through the
        # row-checked route after a write). Running the O(|E|) gate too was DOUBLE
        # work (shortest_path_length(MG,source) 0.45x vs the collapse funcs'
        # 0.58x), and after a write it made a point query O(E). Only the
        # source-less dispatches still need it.
        if (
            method == "dijkstra"
            and source is None
            and _should_delegate_dijkstra_to_networkx(G, weight)
        ):
            if source is not None and target is not None:
                return dijkstra_path_length(G, source, target, weight=weight)
            if source is not None and target is None:
                return dict(single_source_dijkstra_path_length(G, source, weight=weight))
            if source is None and target is not None:
                H = G.reverse(copy=False) if G.is_directed() else G
                return dict(single_source_dijkstra_path_length(H, target, weight=weight))
            return all_pairs_dijkstra_path_length(G, weight=weight)
        if method == "bellman-ford" and _should_delegate_bellman_ford_to_networkx(weight):
            if source is not None and target is not None:
                return bellman_ford_path_length(G, source, target, weight=weight)
            if source is not None and target is None:
                return dict(single_source_bellman_ford_path_length(G, source, weight=weight))
            if source is None and target is not None:
                H = G.reverse(copy=False) if G.is_directed() else G
                return dict(single_source_bellman_ford_path_length(H, target, weight=weight))
            return all_pairs_bellman_ford_path_length(G, weight=weight)

    if source is not None and target is not None:
        if weight is not None and method == "bellman-ford":
            return bellman_ford_path_length(G, source, target, weight=weight)
        if weight is not None:
            return dijkstra_path_length(G, source, target, weight=weight)
        try:
            return _shortest_path_length_raw(G, source, target, weight=weight)
        except NetworkXNoPath:
            # br-r37-c1-t27ad: same canonical-key leak as
            # bidirectional_shortest_path above.
            _reraise_no_path_with_display_keys(source, target)

    if source is not None:
        _validate_shortest_path_length_source_query(G, source, weight, method)
        if weight is not None:
            if method == "bellman-ford":
                return dict(single_source_bellman_ford_path_length(G, source, weight=weight))
            return dict(single_source_dijkstra_path_length(G, source, weight=weight))
        return dict(single_source_shortest_path_length(G, source))

    if target is not None:
        if weight is not None:
            if method == "bellman-ford":
                H = G.reverse(copy=False) if G.is_directed() else G
                return dict(single_source_bellman_ford_path_length(H, target, weight=weight))
            if G.is_directed():
                if isinstance(weight, str) and not G.is_multigraph():
                    return dict(
                        _raw_single_target_dijkstra_path_length(
                            G, target, weight=weight
                        )
                    )
                return dict(
                    single_source_dijkstra_path_length(
                        G.reverse(copy=False), target, weight=weight
                    )
                )
            return dict(single_source_dijkstra_path_length(G, target, weight=weight))
        return dict(single_target_shortest_path_length(G, target))
        
    if weight is not None:
        if method == "bellman-ford":
            all_pairs = dict(all_pairs_bellman_ford_path_length(G, weight=weight))
        else:  # dijkstra
            all_pairs = dict(all_pairs_dijkstra_path_length(G, weight=weight))
    else:
        # all_pairs_shortest_path_length now returns a generator of pairs;
        # materialise once to support repeated source-key lookups below.
        all_pairs = dict(all_pairs_shortest_path_length(G))
    return ((node, all_pairs[node]) for node in G.nodes())


def has_path(G, source, target):
    """Return ``True`` if a path exists between ``source`` and ``target``.

    Equivalent to checking whether ``target`` is reachable from ``source`` in
    ``G``. Mirrors ``networkx.has_path``.
    """
    # br-r37-c1-rg8jh: accept nx-typed inputs.
    private_rows = _point_query_uses_private_rows(G)
    if not private_rows:
        G = _coerce_arg_to_fnx_graph(G)
    if source not in G:
        raise NodeNotFound(f"Source {source} is not in G")
    if target not in G:
        raise NodeNotFound(f"Target {target} is not in G")
    if private_rows:
        try:
            bidirectional_shortest_path(G, source, target)
        except NetworkXNoPath:
            return False
        return True
    return _raw_has_path(G, source, target)


# Algorithm functions — connectivity
from franken_networkx._fnx import (
    approx_local_node_connectivity_undirected_rust as _raw_approx_local_node_connectivity_undirected,
    articulation_points as _raw_articulation_points,
    bridges as _raw_bridges,
    connected_components as _raw_connected_components,
    edge_connectivity as _raw_edge_connectivity,
    is_connected as _raw_is_connected,
    minimum_node_cut as _raw_minimum_node_cut,
    node_connectivity as _raw_node_connectivity,
    number_connected_components as _raw_number_connected_components,
)


def is_connected(G, *, backend=None, **backend_kwargs):
    """Return True if the graph is connected.

    br-r37-c1-spbk: accept nx's ``backend=None, **backend_kwargs``
    dispatch surface so drop-in code that passes ``backend='networkx'``
    works on fnx.
    """
    _validate_backend_dispatch_keywords("is_connected", backend, backend_kwargs)
    # br-r37-c1-pf5vu: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    return _raw_is_connected(G)


def number_connected_components(G, *, backend=None, **backend_kwargs):
    """Return the number of connected components.

    br-r37-c1-spbk: see is_connected.
    """
    _validate_backend_dispatch_keywords(
        "number_connected_components", backend, backend_kwargs,
    )
    # br-r37-c1-pf5vu: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    return _raw_number_connected_components(G)


def _minimum_node_cut_inproc(G, s=None, t=None, flow_func=None):
    from franken_networkx.backend import _fnx_to_nx
    H = _fnx_to_nx(G)
    try:
        return _nx.algorithms.connectivity.cuts.minimum_node_cut(
            H, s=s, t=t, flow_func=flow_func, backend="networkx"
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)


def minimum_node_cut(
    G, s=None, t=None, flow_func=None, *, backend=None, **backend_kwargs
):
    """Return the minimum node cut separating s from t.

    br-mncutG: first parameter is ``G`` to match nx exactly — the Rust
    binding exposed it as lowercase ``g``, breaking
    ``minimum_node_cut(G=graph)`` kwarg-style drop-in calls.

    br-r37-c1-5jbv9: when multiple equally-small cuts exist, the native
    ``_raw_minimum_node_cut`` binding picked a different (but equally valid)
    cut from nx. The GLOBAL (no s, t) case stays delegated for that contract.

    br-r37-c1-rguir: the LOCAL (s, t) case is de-delegated. nx's
    ``minimum_st_node_cut`` builds an all-unit-capacity node-split auxiliary
    (each node v -> vA, vB with arc vA->vB; each edge (u, v) -> uB->vA and, if
    undirected, vB->uA), runs an edmonds-karp min-cut from ``sB`` to ``tA``, and
    maps the cut arcs back to original nodes. fnx's native min-cut binding
    reproduces nx's edmonds-karp residual byte-for-byte, so building the same
    auxiliary (no explicit caps — the sentinel attr forces unit capacities) and
    rebuilding the cut from its residual partition yields a byte-identical node
    cut ~3-3.7x faster than the fnx->nx conversion.
    """
    _validate_backend_dispatch_keywords("minimum_node_cut", backend, backend_kwargs)
    G = _coerce_arg_to_fnx_graph(G)
    if (s is None) != (t is None):
        raise NetworkXError("Both source and target must be specified.")
    if flow_func is not None:
        return _minimum_node_cut_inproc(
            G, s=s, t=t, flow_func=flow_func,
        )
    if s is not None and t is not None:
        if s not in G:
            raise NetworkXError(f"node {s} not in graph")
        if t not in G:
            raise NetworkXError(f"node {t} not in graph")
        return _native_minimum_st_node_cut(G, s, t)
    # br-r37-c1-ct24s: only the global cut meets the null graph, as in nx.
    if len(G) == 0:
        raise NetworkXPointlessConcept("Connectivity is undefined for the null graph.")

    if G.is_directed():
        if not is_weakly_connected(G):
            raise NetworkXError("Input graph is not connected")
        iter_func = _itertools.permutations

        def _nbrs(v):
            return _itertools.chain(G.predecessors(v), G.successors(v))
    else:
        if not is_connected(G):
            raise NetworkXError("Input graph is not connected")
        iter_func = _itertools.combinations
        _nbrs = G.neighbors

    v = min(G, key=G.degree)
    min_cut = set(G[v])
    non_neighbors = set(G) - set(_nbrs(v)) - {v}
    for w in non_neighbors:
        this_cut = _native_minimum_st_node_cut(G, v, w)
        if len(min_cut) >= len(this_cut):
            min_cut = this_cut
    for x, y in iter_func(_nbrs(v), 2):
        if y in G[x]:
            continue
        this_cut = _native_minimum_st_node_cut(G, x, y)
        if len(min_cut) >= len(this_cut):
            min_cut = this_cut
    return min_cut


def _native_minimum_st_node_cut(G, s, t):
    """br-r37-c1-rguir: byte-exact local node cut via fnx's native min-cut on
    the all-unit-capacity node-split auxiliary (see ``minimum_node_cut``)."""
    # Adjacent endpoints cannot be separated by removing other nodes.
    if G.has_edge(s, t) or (G.is_directed() and G.has_edge(t, s)):
        return set()
    nodes = list(G)
    mapping = {node: i for i, node in enumerate(nodes)}
    directed = G.is_directed()
    aux_edges = [(f"{i}A", f"{i}B") for i in range(len(nodes))]
    for u, v in G.edges():
        aux_edges.append((f"{mapping[u]}B", f"{mapping[v]}A"))
        if not directed:
            aux_edges.append((f"{mapping[v]}B", f"{mapping[u]}A"))
    H = DiGraph()
    H.add_nodes_from(f"{i}{ab}" for i in range(len(nodes)) for ab in ("A", "B"))
    H.add_edges_from(aux_edges)
    _, (reachable, non_reachable) = _minimum_cut_raw(
        H,
        f"{mapping[s]}B",
        f"{mapping[t]}A",
        capacity="\x00__fnx_unit_node_cut__",
        edmonds_karp=True,
    )
    reachable = set(reachable)
    non_reachable = set(non_reachable)
    name_to_node = {}
    for i, node in enumerate(nodes):
        name_to_node[f"{i}A"] = node
        name_to_node[f"{i}B"] = node
    adj_h = {node: set(nbrs) for node, nbrs in H.adjacency()}
    node_cut = set()
    for a in reachable:
        for b in adj_h[a]:
            if b in non_reachable:
                node_cut.add(name_to_node[a])
                node_cut.add(name_to_node[b])
    return node_cut - {s, t}


def connected_components(G, *, backend=None, **backend_kwargs):
    """Generate connected components.

    Yields sets of nodes, one set per component. Matches the upstream
    ``networkx.connected_components`` contract (generator of sets).

    br-r37-c1-spbk: accept nx's ``backend=None, **backend_kwargs``
    dispatch surface so drop-in code that passes ``backend='networkx'``
    works on fnx.
    """
    _validate_backend_dispatch_keywords(
        "connected_components", backend, backend_kwargs,
    )
    # br-r37-c1-pf5vu: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-scceager: nx is @not_implemented_for('directed') — raise EAGERLY
    # on the call, not lazily on iteration. Return an inner generator.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    def _gen():
        yield from _raw_connected_components(G)

    return _gen()


def articulation_points(G):
    """Yield articulation points of ``G``.

    Matches upstream's generator contract (franken_networkx-v1nwd).

    br-r37-c1-rf7lr: the Rust binding now emits APs in DFS-discovery
    order using insertion-order adjacency, matching nx's
    ``_biconnected_dfs`` exactly. We can use the fast Rust path
    instead of delegating to networkx — ~50x faster on BA200, more
    at scale (br-r37-c1-9kyjl is superseded).
    """
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-scceager: nx is @not_implemented_for('directed') — eager raise.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    def _gen():
        yield from _raw_articulation_points(G)

    return _gen()


def bridges(G, root=None, *, backend=None, **backend_kwargs):
    """Generate all bridges in a graph.

    Parameters
    ----------
    G : graph
        An undirected graph.
    root : node, optional
        A node in the graph. If specified, only the bridges in the
        connected component containing root are yielded.

    Yields
    ------
    edge
        Bridges in the graph.
    """
    _validate_backend_dispatch_keywords("bridges", backend, backend_kwargs)
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-scceager: nx is @not_implemented_for('directed') — eager raise.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    def _gen():
        if root is not None:
            if root not in G:
                raise NodeNotFound(f"Root node {root} is not in graph")
            multigraph = G.is_multigraph()
            H = Graph(G) if multigraph else G
            chains = chain_decomposition(H, root=root)
            chain_edges = set(_itertools.chain.from_iterable(chains))
            H_comp = H.subgraph(node_connected_component(H, root)).copy()
            for u, v in H_comp.edges():
                if (u, v) not in chain_edges and (v, u) not in chain_edges:
                    if multigraph and len(G[u][v]) > 1:
                        continue
                    yield (u, v)
            return
        if G.is_multigraph():
            # br-zzcm9: a parallel edge pair is never a bridge — removing
            # one leaves the other connecting u and v, so connectivity is
            # preserved. The Rust native bridges pass treats the simple
            # projection, which misreports parallel pairs as bridges.
            for u, v in _raw_bridges(G):
                if len(G[u][v]) == 1:
                    yield (u, v)
            return
        # br-r37-c1-rf7lr: the Rust binding now emits bridges in
        # graph-edge-insertion order with original edge orientation,
        # matching nx.bridges() (which iterates ``H.edges`` after a chain
        # decomposition). br-r37-c1-h83lo is superseded.
        yield from _raw_bridges(G)

    return _gen()


_fnx_public_bridges = bridges


def is_tree(G, *, backend=None, **backend_kwargs):
    """Return True if ``G`` is a tree.

    A tree is a connected graph with ``n - 1`` edges and no cycles. On a
    MultiGraph, parallel edges create cycles, so br-zzcm9 requires we
    _count parallels rather than relying on the simple-projection native
    path (which overcounts nodes-without-parallels as trees).

    br-treedir: NetworkX's directed contract counts directed edges
    against ``|V| - 1`` and uses weak connectivity. The Rust binding
    collapses ``0->1, 1->0`` to a single undirected edge {0,1} and
    accepts that as a tree (n=2, m=1 → True), even though NX returns
    False (n=2, directed m=2). Handle the directed branch explicitly.
    """
    _validate_backend_dispatch_keywords("is_tree", backend, backend_kwargs)
    # br-r37-c1-pf5vu: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    n = G.number_of_nodes()
    if n == 0:
        raise NetworkXPointlessConcept("G has no nodes.")
    if G.is_directed():
        # Multigraphs _count parallels naturally via number_of_edges.
        m = G.number_of_edges()
        return m == n - 1 and is_weakly_connected(G)
    if G.is_multigraph():
        m = G.number_of_edges()  # multigraph counts parallels
        return m == n - 1 and is_connected(G)
    return _raw_is_tree(G)


def is_forest(G, *, backend=None, **backend_kwargs):
    """Return True if ``G`` is a forest (disjoint union of trees).

    MultiGraph parallels create cycles (br-zzcm9); verify each
    connected component is a tree counting parallels.

    br-treedir: same directed-edge-collapse defect as ``is_tree`` —
    the Rust binding sees ``0->1, 1->0`` as a single undirected edge
    and reports a forest. NX requires each weakly-connected component
    to have ``|E| == |V| - 1`` counting directed edges.
    """
    _validate_backend_dispatch_keywords("is_forest", backend, backend_kwargs)
    # br-r37-c1-pf5vu: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if G.number_of_nodes() == 0:
        raise NetworkXPointlessConcept("G has no nodes.")
    # br-r37-c1-isforest: a forest has |E| = |V| - (#components) <= |V| - 1,
    # so any graph with more edges than |V|-1 cannot be a forest — O(1)
    # early-exit that avoids the per-component subgraph builds below for the
    # common dense / obviously-not-a-forest case (16.9x on a 9000-edge
    # digraph). Counts directed edges / multigraph parallels, all of which
    # only inflate the count, so the bound stays sound.
    if G.number_of_edges() > G.number_of_nodes() - 1:
        return False
    if G.is_directed():
        # Every edge with its tail in a weakly-connected component has its
        # head in the SAME component, so the component's edge count is just
        # the sum of its nodes' out-degrees — no G.subgraph() construction
        # (that copy was the whole cost).
        for component in weakly_connected_components(G):
            n_edges = sum(G.out_degree(n) for n in component)
            if n_edges != len(component) - 1:
                return False
        return True
    if G.is_multigraph():
        # Undirected: both endpoints of every in-component edge are in the
        # component, so 2*|E_c| = sum of degrees (self-loops contribute 2 to
        # degree and count as 1 edge, which the //2 preserves). Parallels are
        # counted, matching the subgraph edge count exactly.
        for component in connected_components(G):
            n_edges = sum(G.degree(n) for n in component) // 2
            if n_edges != len(component) - 1:
                return False
        return True
    return _raw_is_forest(G)


def complement(G):
    """Return the graph complement of ``G``.

    For MultiGraph inputs (br-zzcm9), delegate to the upstream nx
    implementation since the Rust native complement rejects them with
    TypeError; nx's complement on a MultiGraph returns a MultiGraph
    with the non-edges (between each pair of distinct nodes, one edge
    per missing pair — matches a simple-graph complement structure).
    """
    # br-r37-c1-nwkg0: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_multigraph():
        # br-r37-c1-mgisol (cc): the native _raw_complement rejects multigraphs,
        # so MG/MDG used to round-trip through nx (_complement_via_nx: fnx->nx +
        # nx.complement + nx->fnx = ~215ms / 0.27x at n=200). nx's complement is a
        # pure structural double-loop, so build the result DIRECTLY: nodes (keys
        # only, no attrs — matches nx's add_nodes_from(G)) + every non-adjacent
        # ordered pair via the native adjacency-membership dict, committed with the
        # native batch add_edges_from. Generating (u,v) for u,v in G order
        # reproduces nx's exact edge/key sequence (undirected emits both (u,v) and
        # (v,u) -> two parallel edges per missing pair, matching nx). 0.27x->1.20x
        # (215ms->48ms, ~4.5x self); strict byte-exact 0/300 (nodes+data,
        # edges+keys, graph attrs) over MultiGraph + MultiDiGraph.
        R = (MultiDiGraph if G.is_directed() else MultiGraph)()
        R.add_nodes_from(G.nodes())
        _adj = G._native_adjacency_dict()
        _nodes = list(G.nodes())
        _edges = []
        for _u in _nodes:
            _nbrs = _adj.get(_u, ())
            for _v in _nodes:
                if _u != _v and _v not in _nbrs:
                    _edges.append((_u, _v))
        R.add_edges_from(_edges)
        return R
    return _raw_complement(G)


def _build_auxiliary_node_connectivity_fast(G):
    directed = G.is_directed()
    mapping = {node: i for i, node in enumerate(G)}
    H = DiGraph()
    for i, node in enumerate(G):
        H.add_node(f"{i}A", id=node)
        H.add_node(f"{i}B", id=node)
        H.add_edge(f"{i}A", f"{i}B", capacity=1)

    edges = []
    for source, target in G.edges():
        edges.append((f"{mapping[source]}B", f"{mapping[target]}A"))
        if not directed:
            edges.append((f"{mapping[target]}B", f"{mapping[source]}A"))
    H.add_edges_from(edges, capacity=1)
    H.graph["mapping"] = mapping
    return H


def _build_auxiliary_edge_connectivity_fast(G):
    H = DiGraph()
    H.add_nodes_from(G.nodes())
    if G.is_directed():
        H.add_edges_from(G.edges(), capacity=1)
    else:
        edges = []
        for source, target in G.edges():
            edges.extend([(source, target), (target, source)])
        H.add_edges_from(edges, capacity=1)
    return H


def _node_connectivity_inproc(G, s=None, t=None, flow_func=None):
    from franken_networkx.backend import _fnx_to_nx
    H = _fnx_to_nx(G)
    try:
        return _nx.algorithms.connectivity.connectivity.node_connectivity(
            H, s=s, t=t, flow_func=flow_func, backend="networkx"
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)
