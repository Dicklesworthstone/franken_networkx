

def _random_unlabeled_rooted_forest_exact(n, q, cache_trees, cache_forests, seed):
    """Return an exact random unlabeled rooted forest as ``(edges, node_count, roots)``."""
    if n == 0:
        return [], 0, []

    j, d = _select_jd_forests(n, q, cache_forests, seed)
    forest_edges, forest_nodes, roots = _random_unlabeled_rooted_forest_exact(
        n - j * d,
        q,
        cache_trees,
        cache_forests,
        seed,
    )
    tree_edges, tree_nodes = _random_unlabeled_rooted_tree_exact(d, cache_trees, seed)
    for _ in range(j):
        roots.append(forest_nodes)
        forest_edges.extend((left + forest_nodes, right + forest_nodes) for left, right in tree_edges)
        forest_nodes += tree_nodes
    return forest_edges, forest_nodes, roots


# br-r37-c1-cdf1v: networkx's Wilf sampler for FREE (unrooted) trees -
# _num_trees, _bicenter and _random_unlabeled_tree, verbatim, over the exact
# rooted helpers above - so random_unlabeled_tree draws networkx's tree for
# every seed kind (it ran the labeled Prüfer generator on its own RNG).
def _num_trees(n, cache_trees):
    """Return the number of unlabeled trees with ``n`` nodes."""
    r = _num_rooted_trees(n, cache_trees) - sum(
        [
            _num_rooted_trees(j, cache_trees) * _num_rooted_trees(n - j, cache_trees)
            for j in range(1, n // 2 + 1)
        ]
    )
    if n % 2 == 0:
        r += _math.comb(_num_rooted_trees(n // 2, cache_trees) + 1, 2)
    return r


def _bicenter(n, cache, seed):
    """Return a random bicentroidal tree on ``n`` nodes as ``(edges, node_count)``."""
    t, t_nodes = _random_unlabeled_rooted_tree_exact(n // 2, cache, seed)
    if seed.randint(0, _num_rooted_trees(n // 2, cache)) == 0:
        t2, t2_nodes = t, t_nodes
    else:
        t2, t2_nodes = _random_unlabeled_rooted_tree_exact(n // 2, cache, seed)
    t.extend([(n1 + (n // 2), n2 + (n // 2)) for n1, n2 in t2])
    t.append((0, n // 2))
    return t, t_nodes + t2_nodes


def _random_unlabeled_tree(n, cache_trees, cache_forests, seed):
    """Return a uniformly random unlabeled tree as ``(edges, node_count)``."""
    if n % 2 == 1:
        p = 0
    else:
        p = _math.comb(_num_rooted_trees(n // 2, cache_trees) + 1, 2)
    if seed.randint(0, _num_trees(n, cache_trees) - 1) < p:
        return _bicenter(n, cache_trees, seed)
    f, n_f, r = _random_unlabeled_rooted_forest_exact(
        n - 1, (n - 1) // 2, cache_trees, cache_forests, seed
    )
    for i in r:
        f.append((i, n_f))
    return f, n_f + 1


# ---------------------------------------------------------------------------
# Additional conversion
# ---------------------------------------------------------------------------


def _json_graph_from_flags(directed=False, multigraph=False):
    """Return the graph class implied by JSON graph payload flags."""
    if multigraph:
        return MultiDiGraph() if directed else MultiGraph()
    return DiGraph() if directed else Graph()


def _json_graph_to_tuple(value):
    """Convert JSON list nodes into tuple nodes, including nested lists."""
    if not isinstance(value, (tuple, list)):
        return value
    return tuple(_json_graph_to_tuple(item) for item in value)


def _add_json_multiedge(graph, source, target, edge_key, edge_attrs):
    """Add a multiedge preserving the edge key from JSON payload.

    br-multikey-jsonrt: the Rust MultiGraph binding now accepts string /
    arbitrary keys directly (post-exception-hierarchy rebuild), so
    preserve whatever key appears in the JSON rather than re-assigning
    a fresh int. nx.node_link_graph preserves the key attribute as-is;
    this restores round-trip parity for string-keyed multigraphs.
    """
    if edge_key is None:
        actual_key = graph.add_edge(source, target)
    else:
        actual_key = graph.add_edge(source, target, key=edge_key)
    # br-r37-c1-mgaek: O(1) native get_edge_data instead of graph[s][t][k],
    # which rebuilds the full MultiAdjacencyView per edge (O(E) -> O(E^2) in the
    # from_dict_of_dicts / node_link_graph construction loops).
    if edge_attrs:
        graph.get_edge_data(source, target, actual_key).update(edge_attrs)


def adjacency_data(G, attrs={"id": "id", "key": "key"}):  # noqa: B006
    """Return adjacency-data format suitable for JSON serialization.

    The ``attrs`` default is the same dict literal nx uses so that
    ``inspect.signature`` introspection matches upstream — even though
    a mutable default is normally a smell, networkx ships it that way
    and drop-in callers rely on the introspectable default.
    """
    if attrs is None:
        attrs = {"id": "id", "key": "key"}
    multigraph = G.is_multigraph()
    id_ = attrs["id"]
    key = None if not multigraph else attrs["key"]
    if id_ == key:
        raise NetworkXError("Attribute names are not unique.")

    # br-r37-c1-9kpev native fast path REMOVED (cc, adjdataedgeattr): the Rust
    # adjacency_data_simple binding copied edge attrs from the Python edge
    # MIRROR (edge_py_attrs), which is EMPTY for batch-built simple graphs —
    # add_weighted_edges_from / add_edges_from commit edge attrs straight into
    # the native CgseValue store and leave the mirror lazy. So on any graph
    # built with the bulk edge APIs the native serializer silently DROPPED
    # every edge attribute (e.g. `weight`), corrupting JSON round-trips. Route
    # exact simple Graph through G.adjacency() instead: its rows read the store
    # correctly AND the cached outer/row dicts make it byte-exact + ~1.2-1.3x
    # faster than nx (vs the buggy native path's 0.79x). Simple DiGraph,
    # multigraphs and any subclass / filtered view use the correct per-node
    # G[node] loop below.
    if type(G) is Graph:
        return {
            "directed": False,
            "multigraph": False,
            "graph": list(G.graph.items()),
            "nodes": [{**node_attrs, id_: node} for node, node_attrs in G.nodes(data=True)],
            "adjacency": [
                [{**edge_attrs, id_: nbr} for nbr, edge_attrs in nbrs.items()]
                for _, nbrs in G.adjacency()
            ],
        }

    if type(G) is DiGraph:
        # Successor adjacency built from the bulk store-backed edge view.
        # G.edges(data=True) yields out-edges grouped by source in node order
        # and, within a source, in successor (adjacency) order — exactly nx's
        # per-node G[node] iteration — so grouping by source reproduces nx's
        # adjacency list byte-for-byte while avoiding the slow per-node
        # AdjacencyView materialisation (0.26x -> faster).
        nodelist = list(G)
        index = {node: i for i, node in enumerate(nodelist)}
        adjacency = [[] for _ in nodelist]
        for u, v, edge_attrs in G.edges(data=True):
            adjacency[index[u]].append({**edge_attrs, id_: v})
        return {
            "directed": True,
            "multigraph": False,
            "graph": list(G.graph.items()),
            "nodes": [{**node_attrs, id_: node} for node, node_attrs in G.nodes(data=True)],
            "adjacency": adjacency,
        }

    data = {
        "directed": G.is_directed(),
        "multigraph": multigraph,
        "graph": list(G.graph.items()),
        "nodes": [],
        "adjacency": [],
    }
    for node, node_attrs in G.nodes(data=True):
        data["nodes"].append({**node_attrs, id_: node})
        neighbors = []
        # br-r37-c1-nodekeys: G[node] is the native O(deg) row; G.adj[node]
        # re-materialises the whole (Multi)AdjacencyView per node -> TIMEOUT on
        # a MultiGraph. Same {nbr: keydict}/{nbr: attrs} shape + order.
        nbrdict = G[node]
        if multigraph:
            for nbr, keydict in nbrdict.items():
                for edge_key, edge_attrs in keydict.items():
                    neighbors.append({**edge_attrs, id_: nbr, key: edge_key})
        else:
            for nbr, edge_attrs in nbrdict.items():
                neighbors.append({**edge_attrs, id_: nbr})
        data["adjacency"].append(neighbors)
    return data


def node_link_data(
    G,
    *,
    source="source",
    target="target",
    name="id",
    key="key",
    edges="edges",
    nodes="nodes",
):
    """Return node-link data suitable for JSON serialization.

    All overrides for the ``source``/``target``/``name``/``key``/
    ``edges``/``nodes`` field names are keyword-only, matching nx's
    public signature. This locks out positional misuse like
    ``node_link_data(G, "from_", "to_")`` which nx rejects with
    ``TypeError: takes 1 positional argument but 3 were given``.
    """
    internal_names = [source, target, name]
    if G.is_multigraph():
        internal_names.append(key)
    if len(set(internal_names)) != len(internal_names):
        raise NetworkXError("Attribute names are not unique.")

    # br-r37-c1-9kpev native fast path REMOVED (cc, adjdataedgeattr): like
    # adjacency_data, node_link_data_simple copied edge attrs from the Python
    # edge MIRROR, which is empty for batch-built simple graphs (attrs live in
    # the native CgseValue store) — so it silently DROPPED every edge attribute
    # on graphs built with add_weighted_edges_from / add_edges_from, corrupting
    # node-link JSON. The comprehension fallback below sources edges from
    # G.edges(data=True), which reads the store correctly and stays byte-exact
    # with nx for both directed and undirected inputs.
    # cc-nldmaterialize: iterate the RAW materialized view lists, not the
    # _FailFastEdgeIterator/_gen-guarded generators. `_materialize()` (present on
    # every NodeDataView and the simple-Graph EdgeDataView) returns the exact same
    # (node, attrs)/(u, v, attrs) tuples in the same order, but skips the per-element
    # mutation-guard `__next__` dispatch (1.85x on the edge walk: 0.73->0.39ms at
    # 3000 edges) — node_link_data never mutates G mid-build, so the guard is pure
    # overhead. `hasattr` fallback keeps the guarded path for views without it
    # (DiGraph/Multi edge views), which are already >= nx. Byte-identical.
    _node_view = G.nodes(data=True)
    _node_iter = (
        _node_view._materialize()
        if hasattr(_node_view, "_materialize")
        else _node_view
    )
    payload = {
        "directed": G.is_directed(),
        "multigraph": G.is_multigraph(),
        "graph": dict(G.graph),
        nodes: [{**node_attrs, name: node} for node, node_attrs in _node_iter],
    }
    edge_payloads = []
    if G.is_multigraph():
        _edge_view = G.edges(keys=True, data=True)
        _edge_iter = (
            _edge_view._materialize()
            if hasattr(_edge_view, "_materialize")
            else _edge_view
        )
        for u, v, edge_key, edge_attrs in _edge_iter:
            edge_payloads.append(
                {
                    **edge_attrs,
                    source: u,
                    target: v,
                    key: edge_key,
                }
            )
    else:
        _edge_view = G.edges(data=True)
        _edge_iter = (
            _edge_view._materialize()
            if hasattr(_edge_view, "_materialize")
            else _edge_view
        )
        for u, v, edge_attrs in _edge_iter:
            edge_payloads.append({**edge_attrs, source: u, target: v})
    payload[edges] = edge_payloads
    return payload


def adjacency_graph(
    data,
    directed=False,
    multigraph=True,
    attrs={"id": "id", "key": "key"},  # noqa: B006
):
    """Return a graph from adjacency-data format.

    The ``attrs`` default mirrors nx's mutable-dict default so the
    introspected signature matches upstream. ``None`` is also accepted
    for backwards compatibility with earlier fnx callers.
    """
    if attrs is None:
        attrs = {"id": "id", "key": "key"}
    multigraph = data.get("multigraph", multigraph)
    directed = data.get("directed", directed)
    graph = _json_graph_from_flags(directed=directed, multigraph=multigraph)
    id_ = attrs["id"]
    key = None if not multigraph else attrs["key"]
    graph.graph.update(dict(data.get("graph", [])))

    # br-r37-c1-jbldr: batch node + (simple-graph) edge construction. The prior
    # per-node add_node + nodes[node].update and per-edge add_edge +
    # graph[u][v].update paid the PyO3-boundary + adjacency-view __getitem__ cost
    # once PER node/edge (~4.3x nx). add_nodes_from((node, attrs)) / add_edges_from
    # ((u, v, attrs)) commit them in one bulk insertion: same insertion order,
    # same per-element attr-update semantics (add_edges_from merges the attr dict
    # into the edge exactly like the old .update), so output is byte-identical.
    # The multigraph path keeps the per-edge key-aware _add_json_multiedge.
    mapping = []
    node_batch = []
    for node_payload in data["nodes"]:
        node_data = node_payload.copy()
        node = node_data.pop(id_)
        mapping.append(node)
        node_batch.append((node, node_data))
    graph.add_nodes_from(node_batch)

    if not multigraph:
        edge_batch = []
        for index, adjacency in enumerate(data["adjacency"]):
            source = mapping[index]
            for target_payload in adjacency:
                target_data = target_payload.copy()
                target = target_data.pop(id_)
                edge_batch.append((source, target, target_data))
        graph.add_edges_from(edge_batch)
    else:
        for index, adjacency in enumerate(data["adjacency"]):
            source = mapping[index]
            for target_payload in adjacency:
                target_data = target_payload.copy()
                target = target_data.pop(id_)
                edge_key = target_data.pop(key, None)
                _add_json_multiedge(graph, source, target, edge_key, target_data)
    return graph


def node_link_graph(
    data,
    directed=False,
    multigraph=True,
    *,
    source="source",
    target="target",
    name="id",
    key="key",
    edges="edges",
    nodes="nodes",
    backend=None,
    **backend_kwargs,
):
    """Build a graph from node-link data.

    Field-name overrides (``source`` / ``target`` / ``name`` / ``key``
    / ``edges`` / ``nodes``) are keyword-only to match networkx's
    public signature. ``directed``/``multigraph`` flags remain
    positional for backwards compat with both libraries.
    """
    mode = backend_kwargs.pop("mode", None)
    _validate_backend_dispatch_keywords("node_link_graph", backend, backend_kwargs)
    if mode is not None:
        with compatibility_mode(mode):
            return node_link_graph(
                data,
                directed=directed,
                multigraph=multigraph,
                source=source,
                target=target,
                name=name,
                key=key,
                edges=edges,
                nodes=nodes,
                backend=backend,
                **backend_kwargs,
            )
    multigraph = data.get("multigraph", multigraph)
    directed = data.get("directed", directed)
    graph = _json_graph_from_flags(directed=directed, multigraph=multigraph)
    key = None if not multigraph else key
    graph.graph.update(dict(data.get("graph", {})))

    # br-r37-c1-jbldr: batch node + (simple-graph) edge construction (same lever
    # as adjacency_graph). Per-node add_node(**data) + per-edge add_edge(**data)
    # each paid the PyO3-boundary cost once per element (~2.0x nx); add_nodes_from
    # / add_edges_from commit them in one bulk insertion with the same order and
    # the same attr-merge semantics, so output is byte-identical. The `next(counter)`
    # default arg is evaluated per node exactly as before. Multigraph keeps the
    # per-edge key-aware path.
    counter = _count()
    node_batch = []
    for node_payload in data[nodes]:
        node = _json_graph_to_tuple(node_payload.get(name, next(counter)))
        node_data = {str(k): v for k, v in node_payload.items() if k != name}
        node_batch.append((node, node_data))
    graph.add_nodes_from(node_batch)

    if not multigraph:
        edge_batch = []
        for edge_payload in data[edges]:
            source_node = _json_graph_to_tuple(edge_payload[source])
            target_node = _json_graph_to_tuple(edge_payload[target])
            edge_data = {
                str(k): v
                for k, v in edge_payload.items()
                if k != source and k != target
            }
            edge_batch.append((source_node, target_node, edge_data))
        graph.add_edges_from(edge_batch)
    else:
        for edge_payload in data[edges]:
            source_node = _json_graph_to_tuple(edge_payload[source])
            target_node = _json_graph_to_tuple(edge_payload[target])
            edge_key = edge_payload.get(key, None)
            edge_data = {
                str(k): v
                for k, v in edge_payload.items()
                if k != source and k != target and k != key
            }
            _add_json_multiedge(
                graph,
                source_node,
                target_node,
                edge_key,
                edge_data,
            )
    return graph


# ---------------------------------------------------------------------------
# Additional centrality / metrics
# ---------------------------------------------------------------------------


def _centrality_weight_function(G, weight):
    if callable(weight):
        return weight
    if G.is_multigraph():
        return lambda u, v, d: min(attr.get(weight, 1) for attr in d.values())
    return lambda u, v, data: data.get(weight, 1)


def _single_source_shortest_path_basic_local(G, source, cutoff=None):
    stack = []
    predecessors = {node: [] for node in G}
    sigma = dict.fromkeys(G, 0.0)
    distances = {source: 0}
    sigma[source] = 1.0
    queue = _deque([source])
    while queue:
        node = queue.popleft()
        stack.append(node)
        node_distance = distances[node]
        node_sigma = sigma[node]
        if cutoff is not None and node_distance >= cutoff:
            continue
        for neighbor in G[node]:
            if neighbor not in distances:
                queue.append(neighbor)
                distances[neighbor] = node_distance + 1
            if distances[neighbor] == node_distance + 1:
                sigma[neighbor] += node_sigma
                predecessors[neighbor].append(node)
    return stack, predecessors, sigma, distances


def _single_source_dijkstra_path_basic_local(G, source, weight, cutoff=None):
    weight_fn = _centrality_weight_function(G, weight)
    stack = []
    predecessors = {node: [] for node in G}
    sigma = dict.fromkeys(G, 0.0)
    distances = {}
    sigma[source] = 1.0
    seen = {source: 0}
    counter = _count()
    queue = []
    _heappush(queue, (0, next(counter), source, source))
    while queue:
        distance, _, pred, node = _heappop(queue)
        if node in distances:
            continue
        sigma[node] += sigma[pred]
        stack.append(node)
        distances[node] = distance
        for neighbor, edge_data in G[node].items():
            edge_weight = weight_fn(node, neighbor, edge_data)
            if edge_weight is None:
                continue
            total_distance = distance + edge_weight
            if cutoff is not None and total_distance > cutoff:
                continue
            if neighbor not in distances and (
                neighbor not in seen or total_distance < seen[neighbor]
            ):
                seen[neighbor] = total_distance
                _heappush(queue, (total_distance, next(counter), node, neighbor))
                sigma[neighbor] = 0.0
                predecessors[neighbor] = [node]
            elif neighbor not in distances and total_distance == seen[neighbor]:
                sigma[neighbor] += sigma[node]
                predecessors[neighbor].append(node)
    return stack, predecessors, sigma, distances


def _rescale_betweenness_local(
    betweenness, n, *, normalized, directed, endpoints=True, sampled_nodes=None
):
    source_count = None if sampled_nodes is None else len(sampled_nodes)
    pair_nodes = n if endpoints else n - 1
    if pair_nodes < 2:
        return betweenness

    source_scale = pair_nodes if source_count is None else source_count

    if source_count is None or endpoints:
        if normalized:
            scale = 1 / (source_scale * (pair_nodes - 1))
        else:
            correction = 1 if directed else 2
            scale = pair_nodes / (source_scale * correction)
        if scale != 1:
            for key in betweenness:
                betweenness[key] *= scale
        return betweenness

    if normalized:
        scale_source = (
            1 / ((source_scale - 1) * (pair_nodes - 1))
            if source_scale > 1
            else _math.nan
        )
        scale_nonsource = 1 / (source_scale * (pair_nodes - 1))
    else:
        correction = 1 if directed else 2
        scale_source = (
            pair_nodes / ((source_scale - 1) * correction)
            if source_scale > 1
            else _math.nan
        )
        scale_nonsource = pair_nodes / (source_scale * correction)

    sampled_nodes = set(sampled_nodes)
    for key in betweenness:
        betweenness[key] *= scale_source if key in sampled_nodes else scale_nonsource
    return betweenness


def _add_edge_keys_local(G, betweenness, weight=None):
    weight_fn = _centrality_weight_function(G, weight)
    edge_betweenness = dict.fromkeys(G.edges(keys=True), 0.0)
    for u, v in betweenness:
        edge_dict = G[u][v]
        edge_weight = weight_fn(u, v, edge_dict)
        keys = [key for key in edge_dict if weight_fn(u, v, {key: edge_dict[key]}) == edge_weight]
        edge_value = betweenness[(u, v)] / len(keys)
        for key in keys:
            edge_betweenness[(u, v, key)] = edge_value
    return edge_betweenness


def _accumulate_subset_local(betweenness, stack, predecessors, sigma, source, targets):
    delta = dict.fromkeys(stack, 0.0)
    target_set = set(targets) - {source}
    while stack:
        node = stack.pop()
        coeff = (delta[node] + 1.0) / sigma[node] if node in target_set else delta[node] / sigma[node]
        for pred in predecessors[node]:
            delta[pred] += sigma[pred] * coeff
        if node != source:
            betweenness[node] += delta[node]
    return betweenness


def _accumulate_endpoints_local(betweenness, stack, predecessors, sigma, source):
    betweenness[source] += len(stack) - 1
    delta = dict.fromkeys(stack, 0.0)
    while stack:
        node = stack.pop()
        coeff = (1.0 + delta[node]) / sigma[node]
        for pred in predecessors[node]:
            delta[pred] += sigma[pred] * coeff
        if node != source:
            betweenness[node] += delta[node] + 1.0
    return betweenness, delta


def _accumulate_edges_subset_local(
    betweenness, stack, predecessors, sigma, source, targets
):
    delta = dict.fromkeys(stack, 0.0)
    target_set = set(targets)
    while stack:
        node = stack.pop()
        for pred in predecessors[node]:
            if node in target_set:
                contribution = (sigma[pred] / sigma[node]) * (1.0 + delta[node])
            else:
                contribution = delta[node] / len(predecessors[node])
            edge = (pred, node) if (pred, node) in betweenness else (node, pred)
            betweenness[edge] += contribution
            delta[pred] += contribution
        if node != source:
            betweenness[node] += delta[node]
    return betweenness


def _accumulate_percolation_local(
    percolation, stack, predecessors, sigma, source, states, state_sum
):
    delta = dict.fromkeys(stack, 0.0)
    while stack:
        node = stack.pop()
        coeff = (1 + delta[node]) / sigma[node]
        for pred in predecessors[node]:
            delta[pred] += sigma[pred] * coeff
        if node != source:
            percolation_weight = states[source] / (state_sum - states[node])
            percolation[node] += delta[node] * percolation_weight
    return percolation


def _edge_load_from_source_local(G, source, cutoff=None):
    _, predecessors, _, distances = _single_source_shortest_path_basic_local(
        G, source, cutoff=cutoff
    )
    ordered_nodes = [
        node for node, _ in sorted(distances.items(), key=lambda item: item[1])
    ]
    between = {}
    for u, v in G.edges():
        between[(u, v)] = 1.0
        between[(v, u)] = 1.0

    while ordered_nodes:
        node = ordered_nodes.pop()
        num_paths = len(predecessors[node])
        for pred in predecessors[node]:
            if predecessors[pred]:
                num_paths = len(predecessors[pred])
                for parent in predecessors[pred]:
                    between[(pred, parent)] += between[(node, pred)] / num_paths
                    between[(parent, pred)] += between[(pred, node)] / num_paths
    return between


def _load_centrality_from_source_local(G, source, cutoff=None, weight=None):
    if weight is None:
        predecessors, distances = predecessor(
            G, source, cutoff=cutoff, return_seen=True
        )
    else:
        predecessors, distances = dijkstra_predecessor_and_distance(
            G,
            source,
            cutoff=cutoff,
            weight=weight,
        )

    # networkx's _node_betweenness sorts (length, vert) PAIRS: ties at one
    # distance go in node-value order, and nodes that do not compare raise
    # TypeError there (br-r37-c1-f0uiy). A key on the distance alone kept
    # the ties in discovery order and never raised.
    onodes = [(distance, node) for node, distance in distances.items()]
    onodes.sort()
    ordered_nodes = [node for distance, node in onodes if distance > 0]
    between = dict.fromkeys(distances, 1.0)

    while ordered_nodes:
        node = ordered_nodes.pop()
        if node in predecessors:
            num_paths = len(predecessors[node])
            for pred in predecessors[node]:
                if pred == source:
                    break
                between[pred] += between[node] / num_paths

    for node in between:
        between[node] -= 1.0
    return between


def _group_preprocessing_local(G, group_nodes, weight):
    sigma = {}
    delta = {}
    distances = {}
    betweenness = dict.fromkeys(G, 0.0)

    for source in G:
        if weight is None:
            stack, predecessors, sigma[source], distances[source] = (
                _single_source_shortest_path_basic_local(G, source)
            )
        else:
            stack, predecessors, sigma[source], distances[source] = (
                _single_source_dijkstra_path_basic_local(G, source, weight)
            )
        betweenness, delta[source] = _accumulate_endpoints_local(
            betweenness,
            stack,
            predecessors,
            sigma[source],
            source,
        )
        for node in delta[source]:
            if source != node:
                delta[source][node] += 1.0
            if weight is not None:
                sigma[source][node] /= 2.0

    path_betweenness = {node: dict.fromkeys(G, 0.0) for node in group_nodes}
    for group_node1 in group_nodes:
        for group_node2 in group_nodes:
            if group_node2 not in distances[group_node1]:
                continue
            for node in G:
                if (
                    group_node2 in distances[node]
                    and group_node1 in distances[node]
                    and distances[node][group_node2]
                    == distances[node][group_node1] + distances[group_node1][group_node2]
                ):
                    path_betweenness[group_node1][group_node2] += (
                        delta[node][group_node2]
                        * sigma[node][group_node1]
                        * sigma[group_node1][group_node2]
                        / sigma[node][group_node2]
                    )

    return path_betweenness, sigma, distances


def _load_value_rank(G):
    """Each node's position in ``sorted(G.nodes())``, in node order - the
    tie order of networkx's ``sorted((length, vert))`` walk in load
    centrality - or ``None`` when the nodes do not sort."""
    nodes = list(G.nodes())
    try:
        order = sorted(nodes)
    except TypeError:
        return None
    rank = {node: i for i, node in enumerate(order)}
    return [rank[node] for node in nodes]


def load_centrality(
    G,
    v=None,
    cutoff=None,
    normalized=True,
    weight=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Return the load centrality for each node.

    Load centrality is similar to betweenness centrality but counts the
    fraction of shortest paths through each node without normalization
    by the number of shortest paths.

    For unweighted graphs, this is equivalent to betweenness centrality.
    """
    G = _coerce_arg_to_fnx_graph(G)
    _validate_backend_dispatch_keywords(
        "newman_betweenness_centrality", backend, backend_kwargs
    )

    # br-r37-c1-3wzcj: the Rust ``load_centrality`` implements Newman's load
    # (split-equally-among-predecessors), not Brandes' betweenness. networkx
    # walks each source's reached nodes as sorted((length, vert)) from the end,
    # so ties at one distance go in node-VALUE order; the kernel takes that
    # order as ranks (br-r37-c1-f0uiy - in BFS order the last bit of 13-19% of
    # the values was off networkx's), and nodes that do not sort fall through
    # to the parity path, as the weighted route below does.
    # br-r37-c1-mgisol (cc): a MULTIgraph's load is its simple projection's -
    # parallel edges do not change node-sequence shortest paths, and with the
    # value order fixed the projection's row order cannot change the sums.
    # br-r37-c1-96x14: networkx's v= path sums v's per-source load in node
    # order and scales it exactly as its whole-graph path does that node, so
    # the whole-graph kernel's value for v IS its answer - where the Python
    # loop below redid all V sources' work in Python. A v that is not a node
    # (networkx: 0.0) or is unhashable (TypeError) keeps that loop.
    single = v is not None and v in G
    if (v is None or single) and cutoff is None and weight is None:
        value_rank = _load_value_rank(G)
        if value_rank is not None:
            if G.is_multigraph():
                _proj = (DiGraph if G.is_directed() else Graph)()
                _proj.add_nodes_from(G.nodes())
                _proj.add_edges_from(G.edges())
                loads = _raw_load_centrality(
                    _proj, normalized=normalized, value_rank=value_rank
                )
            else:
                loads = _raw_load_centrality(
                    G, normalized=normalized, value_rank=value_rank
                )
            return loads[v] if single else loads

    # br-r37-c1-loadw: weighted load centrality (a string `weight` key,
    # whole-graph, no cutoff) ran a pure-Python per-source Newman loop
    # (~1.8s n=400, 4.4x SLOWER than nx). Route to the native weighted Newman
    # kernel (Dijkstra SSSP, parallel, byte-exact). nx orders its per-source
    # `onodes` by `(length, vert)` using node VALUES, so pass the value rank
    # (`sorted(G.nodes())` position) to reproduce that tie-break exactly.
    # Mirror the dijkstra/astar weight contract; callable/non-string weight,
    # multigraph, cutoff, negative/+inf/non-numeric weight, or nodes that are
    # not mutually sortable all fall through to the parity path / nx.
    if (
        (v is None or single)
        and cutoff is None
        and isinstance(weight, str)
        and not G.is_multigraph()
    ):
        _sync_rust_edge_attrs(G)
        if not (
            _has_negative_edge_weight_for_dijkstra(G, weight, _skip_sync=True)
            or _has_positive_infinity_edge_weight_for_dijkstra(G, weight, _skip_sync=True)
            or _has_nonnumeric_edge_weight(G, weight, _skip_sync=True)
        ):
            value_rank = _load_value_rank(G)
            if value_rank is not None:
                loads = _raw_load_centrality_weighted(
                    G, weight, value_rank, normalized
                )
                return loads[v] if single else loads

    if v is not None:
        betweenness = 0.0
        for source in G:
            source_load = _load_centrality_from_source_local(
                G,
                source,
                cutoff=cutoff,
                weight=weight,
            )
            betweenness += source_load[v] if v in source_load else 0.0
        if normalized:
            order = G.order()
            if order <= 2:
                return betweenness
            betweenness *= 1.0 / ((order - 1) * (order - 2))
        return betweenness

    betweenness = dict.fromkeys(G, 0.0)
    for source in betweenness:
        source_load = _load_centrality_from_source_local(
            G,
            source,
            cutoff=cutoff,
            weight=weight,
        )
        for node, value in source_load.items():
            betweenness[node] += value
    if normalized:
        order = G.order()
        if order > 2:
            scale = 1.0 / ((order - 1) * (order - 2))
            for node in betweenness:
                betweenness[node] *= scale
    return betweenness


def _degree_xy_pairs_fast(G, x, y, weight, nodes):
    """Native vectorized ``(deg_x, deg_y)`` degree pairs (one per directed
    adjacency entry), matching ``node_degree_xy``'s MULTISET for the common case:
    ``weight is None``, ``nodes is None``, simple non-multigraph, no self-loops.

    Derives the pairs from the native sparse adjacency in a single vectorized pass
    instead of walking the slow DegreeView/EdgeView wrappers. The result is
    returned in adjacency order (not networkx's ``set(G)`` traversal order), which
    is fine for consumers that are invariant to pair order (Pearson's r). Returns
    ``(du, dv)`` float arrays, or ``None`` when the fast path does not apply.
    """
    import numpy as np

    if nodes is not None:
        return None
    if G.is_multigraph() or G.number_of_edges() == 0:
        return None
    # br-r37-c1-degxywt: handle weighted degree too. to_scipy_sparse_array(weight=
    # <attr>) carries each edge's weight (default 1 for a missing attr, matching
    # nx's degree(weight=...) accumulation), so A.sum gives the WEIGHTED degree.
    # weight=None gives the binary adjacency (count degree). Either way the pairs
    # are still one-per-adjacency-entry, matching node_degree_xy's multiset.
    try:
        A = to_scipy_sparse_array(G, weight=weight, format="coo")
    except Exception:
        return None
    # br-r37-c1-degxyloop: self-loops used to bail here. They ARE handleable.
    # nx's node_degree_xy walks ``G.edges(u)`` per node, so an undirected
    # self-loop (u, u) yields the (deg_u, deg_u) pair exactly ONCE (u appears as
    # its own neighbour once) — matching the single (u, u) diagonal entry the
    # symmetric COO carries. The only correction needed undirected is the degree:
    # to_scipy puts A[u,u]=1 per self-loop (nx's default convention) but nx's
    # degree counts an undirected self-loop as +2, so add A.diagonal() back. The
    # directed case needs nothing: out/in already count a self-loop once each and
    # the single diagonal entry maps to the single directed (u, u) edge.
    if G.is_directed():
        sel = {
            "out": np.asarray(A.sum(axis=1)).ravel(),
            "in": np.asarray(A.sum(axis=0)).ravel(),
        }
        if x not in sel or y not in sel:
            return None
        du = sel[x][A.row]
        dv = sel[y][A.col]
    else:
        deg = np.asarray(A.sum(axis=1)).ravel() + A.diagonal()
        du = deg[A.row]
        dv = deg[A.col]
    return du.astype(float), dv.astype(float)


def degree_pearson_correlation_coefficient(G, x="out", y="in", weight=None, nodes=None):
    """Return the degree-degree Pearson correlation coefficient.

    For undirected graphs, this is equivalent to
    ``degree_assortativity_coefficient``.
    """
    import scipy as sp

    # br-degpearsonfast: the default path materialized every (deg_x, deg_y) pair
    # through node_degree_xy, which walks the slow DegreeView/EdgeView wrappers
    # (~6x slower than networkx). Pearson's r is invariant to the ORDER of the
    # (x, y) pairs, so when no subset/weight/self-loops are in play we can derive
    # the pairs from the native sparse adjacency in one vectorized pass and get
    # the same coefficient (to float tolerance, as the assortativity tests use).
    fast = _degree_xy_pairs_fast(G, x, y, weight, nodes)
    if fast is not None:
        du, dv = fast
        return float(sp.stats.pearsonr(du, dv)[0])

    values = list(node_degree_xy(G, x=x, y=y, weight=weight, nodes=nodes))
    left, right = zip(*values)
    return float(sp.stats.pearsonr(left, right)[0])


# average_degree was an fnx-only convenience function — removed in
# br-r37-c1-j57zz to mirror nx (which has no such top-level function).
# Equivalent: 2 * G.number_of_edges() / G.number_of_nodes().


def generalized_degree(G, nodes=None):
    """Return the generalized degree for each node.

    The generalized degree counts the number of triangles each edge
    participates in.

    Parameters
    ----------
    G : Graph
    nodes : iterable, optional

    Returns
    -------
    dict
        ``{node: _Counter}`` where _Counter maps triangle _count to
        number of edges with that many triangles.
    """
    # br-r37-c1-mnziq: nx decorator order makes 'directed' fire first
    # on MultiDiGraph.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")

    if nodes is None:
        # br-r37-c1-distidx: native triangle-distribution kernel for the
        # all-nodes case instead of the Python _triangles_and_degree_iter_local
        # neighbor-intersection loop. Wrap each value as Counter to match nx's
        # return type and iterate G to preserve node order. Verified vs nx.
        from collections import Counter as _gd_counter
        if number_of_selfloops(G) == 0:
            kr = dict(_fnx.generalized_degree_rust(G))
            return {node: _gd_counter(dict(kr[node])) for node in G}
        # br-r37-c1-gdself (cc): the native kernel counts a self-loop as a neighbour
        # (spurious triangles in the distribution); nx excludes self-loops. For the
        # rare self-loop case fall to the self-loop-correct Python triangle iterator
        # (the same one the nbunch path uses), preserving G's node order.
        return {
            node: _gd
            for node, _deg, _t, _gd in _triangles_and_degree_iter_local(G, G)
        }

    selected_nodes, single_node = _triangle_selection(G, nodes)
    # br-r37-c1-gdsub (cc): native subset kernel for an exact simple Graph with no
    # self-loops (same gate + per-node distribution as the nodes=None fast path; the
    # kernel counts self-loops as neighbours, so self-loop graphs keep the Python
    # triangle iterator). Computes only selected_nodes — O(|S|*deg^2), no whole-graph
    # walk — vs the per-node `_triangles_and_degree_iter_local` port (0.76-0.81x). The
    # Counter wrap + selected_nodes order match the port and nx byte-for-byte.
    if (
        type(G) is Graph
        and len(selected_nodes) >= 32
        and number_of_selfloops(G) == 0
    ):
        # len>=32 guard: the O(E) number_of_selfloops gate + binding overhead only
        # pays off once the subset is non-trivial; tiny subsets on large graphs keep
        # the O(|S|*deg) Python port (no whole-graph selfloop scan). Native wins
        # 2.6-4x for |S|>=100.
        from collections import Counter as _gd_counter

        kr = dict(_fnx.generalized_degree_rust_subset(G, list(selected_nodes)))
        generalized_degrees = {
            node: _gd_counter(dict(kr[node])) for node in selected_nodes
        }
        if single_node:
            return generalized_degrees[nodes]
        return generalized_degrees
    generalized_degrees = {
        node: generalized_degree_counter
        for node, _, _, generalized_degree_counter in _triangles_and_degree_iter_local(
            G, selected_nodes
        )
    }

    if single_node:
        return generalized_degrees[nodes]
    return generalized_degrees


def _all_pairs_node_connectivity_inproc(G, nbunch=None, flow_func=None):
    from franken_networkx.connectivity import (
        build_auxiliary_node_connectivity,
        local_node_connectivity,
    )
    from franken_networkx.flow import build_residual_network, edmonds_karp

    nodes = list(G) if nbunch is None else set(nbunch)
    result = {node: {} for node in nodes}
    auxiliary = build_auxiliary_node_connectivity(G)
    residual = build_residual_network(auxiliary, "capacity")
    solver = edmonds_karp if flow_func is None else flow_func
    directed = G.is_directed()
    pairs = (
        _itertools.permutations(nodes, 2)
        if directed
        else _itertools.combinations(nodes, 2)
    )
    for source, target in pairs:
        value = local_node_connectivity(
            G,
            source,
            target,
            flow_func=solver,
            auxiliary=auxiliary,
            residual=residual,
        )
        result[source][target] = value
        if not directed:
            result[target][source] = value
    return result


def all_pairs_node_connectivity(
    G, nbunch=None, flow_func=None, *, backend=None, **backend_kwargs
):
    """Return node connectivity between all pairs.

    Returns
    -------
    dict of dicts
        ``result[u][v]`` is the node connectivity between u and v.
    """
    _validate_backend_dispatch_keywords(
        "all_pairs_node_connectivity", backend, backend_kwargs
    )
    _validate_flow_func_selector(flow_func)
    # br-r37-c1-1y7h1: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # The bulk Rust helper projects onto an undirected graph. Directed inputs
    # need ordered pairs over the node-split digraph, while a caller's solver
    # must compute every pair. Reuse one auxiliary and residual graph for both
    # cases so the callback sees the same graph objects throughout the batch.
    if G.is_directed() or flow_func is not None:
        return _all_pairs_node_connectivity_inproc(
            G,
            nbunch=nbunch,
            flow_func=flow_func,
        )
    # NetworkX normalizes an explicit nbunch to a set, including its iteration
    # order. Materialize it once: consuming a generator again below previously
    # made the full/near-full and multigraph routes return an empty result.
    nodes = list(G) if nbunch is None else list(set(nbunch))
    if (
        nbunch is not None
        and type(G) is Graph
        and len(nodes) <= len(G) // 2
        and all(node in G for node in nodes)
    ):
        flat = _fnx.all_pairs_node_connectivity_rust(G, nodes)
    else:
        flat = _fnx.all_pairs_node_connectivity_rust(G)

    result = {node: {} for node in nodes}
    missing = object()
    for left, right in _itertools.combinations(nodes, 2):
        if left not in G:
            raise KeyError(left)
        if right not in G:
            raise KeyError(right)
        conn = flat.get((left, right), missing)
        if conn is missing:
            conn = flat.get((right, left), missing)
        if conn is missing:
            raise KeyError(right)
        result[left][right] = conn
        result[right][left] = conn
    return result
















































def voronoi_cells(G, center_nodes, weight="weight"):
    """Return Voronoi cells around the given centers.

    br-voronoicell: the Rust voronoi_cells_rust (a) ignored the
    ``weight`` kwarg (so weighted graphs returned unweighted-BFS
    cells) and (b) assigned some nodes to the wrong center even
    on the unweighted case. Concrete failure: on a 4-node cycle
    0→1→2→3→0 plus shortcut 0→2(w=2) with centers {0, 2}, node 3
    is 1 hop from center 2 but 2 hops from center 0 — fnx put 3
    in center 0's cell; nx correctly puts it in center 2's cell.
    Delegate to nx for the full weighted-Dijkstra implementation.
    """
    center_nodes = list(center_nodes)
    if not center_nodes:
        # Match nx exactly (br-r37-c1-95ayv): ValueError, not
        # NetworkXError; message is "sources must not be empty".
        raise ValueError("sources must not be empty")
    return _voronoi_cells_impl(G, center_nodes, weight=weight)


def _voronoi_cells_impl(G, center_nodes, *, weight):
    """Voronoi cells via fnx's native ``multi_source_dijkstra_path``.

    br-voronoinative: previously delegated to nx via
    ``_call_networkx_for_parity`` because the Rust ``voronoi_cells_rust``
    kernel ignored ``weight`` and mis-assigned some nodes (see
    ``voronoi_cells``). Rebuild it on fnx's own (correct, fast)
    ``multi_source_dijkstra_path`` plus the standard nearest-center
    inversion — identical to nx's algorithm
    (``nearest = {v: p[0] ...}``; group by center; collect ``unreachable``)
    — which drops the ``_fnx_to_nx`` conversion the delegation paid. The
    result is bit-identical to nx (weighted/unweighted, directed,
    disconnected, single-center, key order, bad-center NodeNotFound):
    4.6ms -> 1.3ms (gap 4.41x -> 1.14x).
    """
    nearest = _voronoi_nearest_centers(G, center_nodes, weight=weight)
    cells = {}
    for node, center in nearest.items():
        cells.setdefault(center, set()).add(node)
    unreachable = set(G) - set(nearest)
    if unreachable:
        cells["unreachable"] = unreachable
    return cells


def _voronoi_nearest_centers(G, sources, *, weight):
    """Return networkx's ``nearest = {v: p[0] for v, p in paths.items()}``
    for ``paths = multi_source_dijkstra_path(G, sources)`` - keys in the
    paths dict's (settle) order, which the Voronoi cells' sets are grown in.

    br-voronoinearest / br-r37-c1-2z0mw: voronoi_cells needs only the source
    each node's path starts from, so the paths are never built. br-r37-c1-ygt3z:
    the search is multi_source_dijkstra's own, on the rows networkx walks, in
    its nearest_sources mode, taking the route multi_source_dijkstra takes. The
    source-propagating kernel it replaces searched a rebuilt projection whose
    reordered rows changed the settle order among equal distances - and with it
    each cell set's iteration order (cells were thought order-insensitive).
    """
    G = _coerce_arg_to_fnx_graph(G)
    if not G.is_multigraph() and isinstance(weight, str):
        route = _dijkstra_weight_route(G, weight)
        if route != "networkx" and not _binding_self_syncs_gate(G, weight):
            for s in sources:
                if s not in G:
                    raise NodeNotFound(f"Node {s} not found in graph")
            try:
                pairs, _ = _raw_multi_source_dijkstra(
                    G,
                    sources,
                    weight=weight,
                    check_rows=route == "rows",
                    nearest_sources=True,
                )
            except _WeightRowsUnverified:
                pairs = None
            if pairs is not None:
                return dict(pairs)
    paths = multi_source_dijkstra_path(G, sources, weight=weight)
    return {v: p[0] for v, p in paths.items()}


def _default_binary_heap():
    """Return ``networkx.utils.heaps.BinaryHeap`` lazily.

    Used as the default sentinel for ``heap=`` arguments so the
    ``inspect.signature`` introspection matches networkx exactly.
    """
    from networkx.utils.heaps import BinaryHeap
    return BinaryHeap


_BINARY_HEAP_DEFAULT = _default_binary_heap()


def _stoer_wagner_native_domain(G, weight, heap):
    """Keep f64 contraction arithmetic inside a faithful Python domain."""
    import math

    if (
        type(G) is not Graph
        or _has_networkx_private_storage(G)
        or not isinstance(weight, str)
        or heap is not _BINARY_HEAP_DEFAULT
    ):
        return False
    integer_total = 0
    float_total = 0.0
    has_integer = False
    has_float = False
    for u, v, attrs in G.edges(data=True):
        if u == v:
            continue
        value = attrs.get(weight, 1)
        if type(value) is int:
            if value < 0:
                return False
            has_integer = True
            integer_total += value
            # Every intermediate integral contraction weight is a sum of
            # original nonnegative weights, so this also bounds all phases.
            if integer_total > (1 << 53):
                return False
        elif type(value) is float:
            if value < 0 or not math.isfinite(value):
                return False
            has_float = True
            float_total += value
            if not math.isfinite(float_total):
                return False
        else:
            return False
        # A mixed graph can have an entirely integral winning cut. The f64
        # result cannot retain that cut's Python type, even for small inputs.
        if has_integer and has_float:
            return False
    return True


def _stoer_wagner_fallback(G, weight="weight", heap=_BINARY_HEAP_DEFAULT):
    from franken_networkx.backend import _fnx_to_nx

    try:
        return _nx.algorithms.connectivity.stoerwagner.stoer_wagner(
            _fnx_to_nx(G), weight=weight, heap=heap, backend="networkx"
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)


def stoer_wagner(
    G, weight="weight", heap=_BINARY_HEAP_DEFAULT, *, backend=None, **backend_kwargs
):
    """Return the Stoer-Wagner global minimum cut value and partition.

    Parameters
    ----------
    G : Graph
        Undirected graph (must be connected).
    weight : str, optional
        Edge attribute name for weights (default ``"weight"``).
    heap : class, optional
        Heap class for the priority queue. Default
        ``networkx.utils.heaps.BinaryHeap`` (matches nx's default
        sentinel for signature introspection). Custom heap classes run
        through the Python contraction implementation.

    Returns
    -------
    cut_value : number
        Weight of the minimum cut, preserving the input arithmetic.
    partition : tuple of lists
        The two lists of nodes that form the minimum cut partition.
    """
    _validate_backend_dispatch_keywords("stoer_wagner", backend, backend_kwargs)
    from franken_networkx._fnx import stoer_wagner as _rust_stoer_wagner

    # br-r37-c1-tqimg: nx is @not_implemented_for('multigraph') and
    # @not_implemented_for('directed') (multigraph is the inner /
    # first-fired decorator). Reject before the < 2 / connectivity
    # guards so the contract matches nx exactly.
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    # br-swmsg: match nx's three distinct error-message wordings for the
    # preconditions (fewer-than-two-nodes vs disconnected) so drop-in
    # code with regex pytest.raises(..., match=...) against upstream
    # keeps working. The Rust path raises one generic message.
    if len(G) < 2:
        raise NetworkXError("graph has less than two nodes.")
    if not is_connected(G):
        raise NetworkXError("graph is not connected.")
    # br-r37-c1-egxmz: nx rejects negative weights with
    # NetworkXError('graph has a negative-weighted edge') before
    # running the Stoer-Wagner contraction.  The Rust binding silently
    # produced a meaningless result on negative inputs; mirror nx's
    # precondition here so callers relying on the documented contract
    # don't silently get wrong cuts.
    if isinstance(weight, str):
        for u, v, attrs in G.edges(data=True):
            if u == v or not isinstance(attrs, dict):
                continue
            w = attrs.get(weight, 1)
            if isinstance(w, _numbers.Number) and not isinstance(w, bool) and w < 0:
                raise NetworkXError("graph has a negative-weighted edge.")
    # br-r37-c1-35oum: the kernel mirrors nx's phases exactly (per-phase
    # lazy-deletion heap with insertion-counter tie-breaks, copy-order
    # arbitrary_element, row-order contraction merges) and returns the
    # contraction sequence; the partition recovery below is nx's tail run
    # VERBATIM with real CPython sets — its list order is set-iteration
    # order, unreplicable in Rust but exact by construction here.
    if heap is None:
        heap = _BINARY_HEAP_DEFAULT
    from franken_networkx._fnx import stoer_wagner_phases as _rust_stoer_wagner_phases

    if not _stoer_wagner_native_domain(G, weight, heap):
        return _stoer_wagner_fallback(G, weight=weight, heap=heap)

    _sync_rust_edge_attrs(G, edge_only=True)
    cut_value, contractions, best_phase, copy_nodes = _rust_stoer_wagner_phases(
        G, weight=weight
    )
    adj = {}
    for u, v in contractions[:best_phase]:
        adj.setdefault(u, {})[v] = 1
        adj.setdefault(v, {})[u] = 1
    v = contractions[best_phase][1]
    adj.setdefault(v, {})
    # networkx _single_shortest_path_length walk (sets and all)
    seen = {}
    nextlevel = {v}
    while nextlevel:
        thislevel = nextlevel
        nextlevel = set()
        for x in thislevel:
            if x not in seen:
                seen[x] = 1
                nextlevel.update(adj.get(x, {}))
    reachable = set(seen)
    nodes = set(copy_nodes)
    partition = (list(reachable), list(nodes - reachable))
    if _stoer_wagner_weights_all_integral(G, weight):
        cut_value = (
            int(cut_value)
            if isinstance(cut_value, float) and cut_value.is_integer()
            else cut_value
        )
    return cut_value, partition


def _stoer_wagner_weights_all_integral(G, weight):
    if weight is None:
        return True
    if not isinstance(weight, str):
        return False
    for u, v, attrs in G.edges(data=True):
        if u == v:
            continue
        value = attrs.get(weight, 1) if isinstance(attrs, dict) else 1
        if isinstance(value, bool) or not isinstance(value, _numbers.Integral):
            return False
    return True


def dedensify(G, threshold, prefix=None, copy=True):
    """Return a dedensified graph by adding compressor nodes.

    Reduces edges to high-degree nodes by adding compressor nodes that
    summarize multiple edges to those high-degree nodes.

    Parameters
    ----------
    G : Graph or DiGraph
        Input graph.
    threshold : int
        Minimum degree (in-degree for directed) above which a node is
        considered high-degree. Must be >= 2.
    prefix : str or None, optional
        Prefix for compressor node labels.
    copy : bool, optional
        If True, work on a copy of *G*.

    Returns
    -------
    H : Graph or DiGraph
        Dedensified graph.
    compressor_nodes : set
        _Set of compressor node labels that were added.
    """
    if threshold < 2:
        raise NetworkXError("The degree threshold must be >= 2")

    if type(G) in (Graph, DiGraph):
        return _dedensify_simple_native_rows(G, threshold, prefix, copy)

    # Determine high-degree nodes
    if G.is_directed():
        degrees = list(G.in_degree)
    else:
        degrees = list(G.degree)
    high_degree_nodes = {n for n, d in degrees if d > threshold}

    # For each node, find which high-degree neighbors it connects to
    auxiliary = {}
    for node in G.nodes():
        if G.is_directed():
            nbrs = set(G.successors(node))
        else:
            nbrs = set(G.neighbors(node))
        high_degree_nbrs = frozenset(high_degree_nodes & nbrs)
        if high_degree_nbrs:
            auxiliary.setdefault(high_degree_nbrs, set()).add(node)

    if copy:
        H = G.copy()
    else:
        H = G

    compressor_nodes = set()
    for high_deg_group, low_deg_group in auxiliary.items():
        low_count = len(low_deg_group)
        high_count = len(high_deg_group)
        old_edges = high_count * low_count
        new_edges = high_count + low_count
        if old_edges <= new_edges:
            continue
        # Name the compressor by concatenating high-degree node names
        compression_node = "".join(str(node) for node in high_deg_group)
        if prefix:
            compression_node = str(prefix) + compression_node
        for node in low_deg_group:
            for high_node in high_deg_group:
                if H.has_edge(node, high_node):
                    H.remove_edge(node, high_node)
            H.add_edge(node, compression_node)
        for node in high_deg_group:
            H.add_edge(compression_node, node)
        compressor_nodes.add(compression_node)

    return H, compressor_nodes


def _dedensify_simple_native_rows(G, threshold, prefix, copy):
    """Dedensify exact simple fnx graphs from native row dictionaries."""
    directed = type(G) is DiGraph
    nodes = list(G)
    adjacency_row = G._native_adjacency_row_dict
    degree_row = G._native_predecessor_row_dict if directed else adjacency_row

    high_degree_nodes = {
        node for node in nodes if len(degree_row(node)) > threshold
    }

    auxiliary = {}
    for node in nodes:
        # br-r37-c1-thp6w: build the high-degree-neighbour frozenset with the
        # EXACT operation nx uses — ``high_degree_nodes & set(G[node])`` — not
        # ``high_degree_nodes.intersection(adjacency_row(node))``. The compressor
        # node name is ``"".join(str(n) for n in high_degree_nbrs)``, i.e. the
        # frozenset's ITERATION order, which is not a stable contract:
        # ``set & set`` seeds the result set by iterating the operands in nx's
        # order, while ``.intersection(<dict>)`` iterated the adjacency dict —
        # a DIFFERENT insertion order, so hash-colliding labels landed in a
        # different bucket order and the compressor name diverged from nx under
        # some binaries (surfaced as an order-fragile golden under the
        # mg-int-storage build). Using the identical ``& set(...)`` operation on
        # identical operands makes fnx's frozenset byte-identical to nx's in any
        # process. Same compression result either way (only the arbitrary name).
        high_degree_nbrs = frozenset(high_degree_nodes & set(adjacency_row(node)))
        if high_degree_nbrs:
            auxiliary.setdefault(high_degree_nbrs, set()).add(node)

    remove_edges = set() if copy else []
    add_edges = []
    compressor_nodes = set()
    prefix_text = None if prefix is None else str(prefix)

    for high_deg_group, low_deg_group in auxiliary.items():
        low_count = len(low_deg_group)
        high_count = len(high_deg_group)
        old_edges = high_count * low_count
        new_edges = high_count + low_count
        if old_edges <= new_edges:
            continue

        compression_node = "".join(str(node) for node in high_deg_group)
        if prefix_text:
            compression_node = prefix_text + compression_node

        for node in low_deg_group:
            row = adjacency_row(node)
            for high_node in high_deg_group:
                if high_node in row:
                    if copy:
                        edge_key = (
                            (node, high_node)
                            if directed
                            else frozenset((node, high_node))
                        )
                        remove_edges.add(edge_key)
                    else:
                        remove_edges.append((node, high_node))
            add_edges.append((node, compression_node))
        for node in high_deg_group:
            add_edges.append((compression_node, node))
        compressor_nodes.add(compression_node)

    if copy:
        if not add_edges:
            return G.copy(), compressor_nodes
        H = DiGraph() if directed else Graph()
        H.graph.update(G.graph)
        H.add_nodes_from((node, dict(attrs)) for node, attrs in G.nodes(data=True))
        kept_edges = []
        for u, v, attrs in G.edges(data=True):
            edge_key = (u, v) if directed else frozenset((u, v))
            if edge_key not in remove_edges:
                kept_edges.append((u, v, dict(attrs)))
        H.add_edges_from(kept_edges)
        H.add_edges_from(add_edges)
        return H, compressor_nodes

    H = G
    if remove_edges:
        H.remove_edges_from(remove_edges)
    if add_edges:
        H.add_edges_from(add_edges)
    return H, compressor_nodes
