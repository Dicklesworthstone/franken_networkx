

def single_source_shortest_path_length(G, source, cutoff=None):
    """Return a dict of shortest path lengths from ``source`` to every
    reachable node. Matches NetworkX: raises
    NodeNotFound('Source {src} is not in G') when the source isn't in
    the graph.

    br-r37-c1-ssspview: ``_coerce_arg_to_fnx_graph`` materializes native-root
    SubgraphView / restricted_view / EdgeSubgraphView
    inputs to a concrete fnx graph before the Rust kernel runs.  The
    Rust binding reads the parent's adjacency directly and silently
    ignores the view filter without this materialization — sister
    bug to the ``shortest_path`` / ``shortest_path_length`` view
    handling.
    An exact reverse view over a concrete root uses native predecessor BFS
    without copying. Other native-root reverse-view chains still materialize
    safely. Private-root views walk current Python rows without a native copy.
    """
    root = _reverse_view_root(G)
    if root is not None and (
        cutoff is None or isinstance(cutoff, int) and 0 <= cutoff <= _sys.maxsize
    ):
        if source not in G:
            raise NodeNotFound(f"Source {source} is not in G")
        lengths = {source: 0}
        for parent, node in _bfs_edges_raw(root, source, reverse=True, depth_limit=cutoff):
            lengths[node] = lengths[parent] + 1
        return lengths
    if not _point_query_uses_private_rows(G):
        G = _coerce_arg_to_fnx_graph(G)
    if source not in G:
        raise NodeNotFound(f"Source {source} is not in G")
    if _has_networkx_private_storage(G):
        # br-r37-c1-mub4s: assigned Python adjacency is authoritative. Native
        # storage can still contain hidden edges, even on an exact graph class.
        # Match the oracle's level order and len(adj) early exit, not len(G).
        adj = G._adj
        count = len(adj)
        seen = {source}
        lengths = {source: 0}
        frontier = [source]
        level = 0
        limit = float("inf") if cutoff is None else cutoff
        while frontier and limit > level:
            level += 1
            current, frontier = frontier, []
            for node in current:
                for neighbor in adj[node]:
                    if neighbor not in seen:
                        seen.add(neighbor)
                        frontier.append(neighbor)
                        lengths[neighbor] = level
                if len(seen) == count:
                    return lengths
        return lengths
    # Rust returns results in BFS discovery order (br-r37-c1-bapbi), so no reordering needed.
    return _raw_single_source_shortest_path_length(G, source, cutoff)

# Algorithm functions — dominating set
from franken_networkx._fnx import (
    dominating_set as _raw_dominating_set,
    is_dominating_set as _raw_is_dominating_set,
)


def is_dominating_set(G, nbunch):
    """Return True if ``nbunch`` is a dominating set of ``G``.

    # br-r37-c1-hdhe3: the Rust kernel ``_raw_is_dominating_set`` has
    # ``require_undirected`` and rejects directed input. nx supports
    # DiGraph / MultiDiGraph for is_dominating_set (checks coverage
    # via out-neighbors / successors).
    """
    # br-r37-c1-0555d: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_directed():
        testset = {n for n in nbunch if n in G}
        dominated = set(testset)
        for n in testset:
            dominated.update(G[n])
        return len(dominated) == len(G)
    return _raw_is_dominating_set(G, nbunch)


def dominating_set(G, start_with=None):
    """Return a dominating set of G.

    Parameters
    ----------
    G : graph
        An undirected graph.
    start_with : node, optional
        Node to add to the dominating set first.

    Returns
    -------
    set
        A dominating set of G.
    """
    # br-r37-c1-lj6bo: native start_with port — small greedy dominating-
    # set algorithm (algorithm 7 in nx's reference). Avoid the
    # fnx_to_nx graph-conversion round-trip the prior delegate paid.
    # br-r37-c1-02djy: bypass G[u] AtlasView via raw _GRAPH_NEIGHBORS /
    # _DIGRAPH_NEIGHBORS binding when the graph has no nx-private
    # storage and isn't a multigraph — same wrapper-bypass pattern as
    # find_cliques (lgyq8) and square_clustering (7t95c). Profiling
    # showed ~50% of pre-bypass time was AtlasView dispatch.
    # br-r37-c1-0555d: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-domstart: nx defaults start_with to
    # ``arbitrary_element(set(G))`` == ``next(iter(set(G)))`` and then runs
    # the greedy from there. The Rust ``_raw_dominating_set`` used a
    # different seed/order, so default-start results diverged from nx on
    # ~50% of graphs (the set is still a valid dominating set, just not
    # nx's). Compute nx's exact default seed and reuse the matching greedy
    # below so the chosen set is identical. (Empty graph keeps fnx's set()
    # return rather than nx's StopIteration leak.)
    # br-r37-c1-04z53: the same greedy is valid for directed graphs because
    # ``G[v]`` iterates successors, matching nx. Empty directed graphs
    # raise StopIteration matching NetworkX.
    if start_with is None:
        if len(G) == 0:
            if G.is_directed():
                raise StopIteration
            result = _raw_dominating_set(G)
            return set(result) if not isinstance(result, set) else result
        start_with = next(iter(set(G)))
    if start_with not in G:
        raise NetworkXError(f"node {start_with} is not in G")
    _raw_nbrs = _raw_neighbors_dispatch(G)
    if _raw_nbrs is not None:
        all_nodes = set(G)
        dominating: set = {start_with}
        dominated = set(_raw_nbrs(G, start_with))
        remaining = all_nodes - dominated - dominating
        while remaining:
            v = remaining.pop()
            undom_nbrs = set(_raw_nbrs(G, v)) - dominating
            dominating.add(v)
            dominated |= undom_nbrs
            remaining -= undom_nbrs
        return dominating
    # Multigraph / private-storage path: stay on G[u].
    all_nodes = set(G)
    dominating = {start_with}
    dominated = set(G[start_with])
    remaining = all_nodes - dominated - dominating
    while remaining:
        v = remaining.pop()
        undom_nbrs = set(G[v]) - dominating
        dominating.add(v)
        dominated |= undom_nbrs
        remaining -= undom_nbrs
    return dominating

# Algorithm functions — community detection
from franken_networkx._fnx import (
    louvain_communities as _raw_louvain_communities,
    modularity as _raw_modularity,
)








def _modularity_backend_impl(G, communities, weight="weight", resolution=1):
    """Compute the modularity of a partition of ``G``.

    br-r37-c1-ecua7: nx exposes ``modularity`` only at
    ``nx.community.modularity`` (and ``nx.algorithms.community.modularity``)
    — ``nx.modularity`` raises ``AttributeError``. fnx mirrors that
    namespace contract by keeping this implementation private and
    routing it through the backend dispatch table. Users call via
    ``fnx.community.modularity(G, ...)``; the dispatcher routes the fnx
    graph back through ``franken_networkx.backend._SUPPORTED_ALGORITHMS``
    which maps ``"modularity"`` to this private implementation.

    Matches upstream NetworkX: raises ``NotAPartition`` when the
    community sets do not form a valid partition of ``G.nodes`` —
    either because nodes are missing or because a node appears in
    more than one community.
    """
    # Coerce to concrete Python sets for the partition check; keep the
    # original sequence (order preserved) for the Rust call. Now that
    # the Rust exception hierarchy imports nx's classes directly
    # (br-nxexcbases), `NotAPartition` is
    # nx.algorithms.community.quality.NotAPartition and takes the
    # (G, collection) positional pair, formatting the message itself.
    community_list = list(communities)
    node_set = set(G.nodes())
    seen: set = set()
    for community in community_list:
        for node in community:
            if node in seen or node not in node_set:
                raise _NotAPartition(G, community_list)
            seen.add(node)
    if seen != node_set:
        raise _NotAPartition(G, community_list)
    # br-modzero: nx.community.modularity raises ZeroDivisionError on a
    # graph with zero edges (the 2m divisor is 0). fnx used to silently
    # return 0.0 from the Rust path — diverging from nx's runtime
    # contract. Partition errors are checked first (above) so the
    # precondition order matches nx.
    if G.number_of_edges() == 0:
        raise ZeroDivisionError("division by zero")
    # br-r37-c1-moddir: the Rust ``_raw_modularity`` computes the *undirected*
    # modularity (k_i*k_j / 2m) even for DiGraph/MultiDiGraph; nx uses the
    # directed Leicht-Newman formula (k_i^in * k_j^out / m).
    # br-r37-c1-q9uy6: evaluated here on the fnx graph itself, as networkx
    # writes it - the same degree dicts, the same `G.edges(comm, data=weight,
    # default=1)` walk in the same order and the same sums, so the float is
    # networkx's to the last bit - instead of converting the whole graph to a
    # networkx graph on every call (0.16-0.17x networkx).
    if G.is_directed():
        out_degree = dict(G.out_degree(weight=weight))
        in_degree = dict(G.in_degree(weight=weight))
        m = sum(out_degree.values())
        norm = 1 / m**2

        def _directed_contribution(community):
            comm = set(community)
            l_c = sum(
                wt for u, v, wt in G.edges(comm, data=weight, default=1) if v in comm
            )
            out_degree_sum = sum(out_degree[u] for u in comm)
            in_degree_sum = sum(in_degree[u] for u in comm)
            return l_c / m - resolution * out_degree_sum * in_degree_sum * norm

        return sum(map(_directed_contribution, community_list))
    # br-r37-c1-nim1v / br-r37-c1-modsnapshot: weighted inputs must delegate to
    # nx's reference implementation (the snapshot/Rust paths are unweighted).
    # The old guard called _graph_has_nonunit_weight, which is a HISTORICAL
    # no-op that ALWAYS returns False (it only syncs Rust attrs) — so genuinely
    # weighted graphs were silently computed UNWEIGHTED. This bug was masked
    # while fnx.community.modularity re-exported nx's function; routing the
    # public entry to this backend impl exposed it. Use the real detector
    # _graph_has_explicit_nonunit_weight (native fast path + edge-walk
    # fallback). weight=None => unit weights => not weighted.
    weighted = weight is not None and _graph_has_explicit_nonunit_weight(G, weight)
    if weighted:
        # cc-modweightednative: the weighted case used to build a whole nx.Graph
        # copy (_networkx_graph_for_parity) and run nx's modularity on it — ~0.23x
        # nx (the O(E) conversion + nx's per-community edges(comm) generator walk).
        # Instead run nx's EXACT reduced formula directly on the fnx graph's native
        # (byte-exact) degree/edges views, materializing each community's
        # edges(comm, data) to a LIST first so the intra-community weight sum is a
        # plain builtins.sum over a Python list (fnx's per-element EdgeDataView
        # __next__ dispatch was the real cost) — SAME elements, SAME order, SAME
        # Neumaier compensation as nx, so byte-identical (verified 300 mixed
        # float/int graphs + partitions, 0 diffs incl ULP). No nx.Graph copy.
        # 0.23x -> ~0.68x (3.2x self). Undirected only (directed handled above);
        # deg_sum==0 (edges present but zero total weight) raises ZeroDivisionError
        # exactly as nx's `1/deg_sum**2`.
        degrees = dict(G.degree(weight=weight))
        deg_sum = sum(degrees.values())
        if deg_sum == 0:
            raise ZeroDivisionError("division by zero")
        m = deg_sum / 2.0
        norm = 1.0 / (deg_sum * deg_sum)

        def _community_contribution(community):
            comm = set(community)
            edge_list = list(G.edges(comm, data=weight, default=1))
            l_c = sum(wt for u, v, wt in edge_list if v in comm)
            deg_c = sum(degrees[u] for u in comm)
            return l_c / m - resolution * deg_c * deg_c * norm

        return sum(_community_contribution(c) for c in community_list)
    # br-r37-c1-modsnapshot: the native Rust _raw_modularity kernel is
    # substrate-bound (~60ms / 30x nx on a 1200-node graph). At THIS point the
    # graph is undirected, unweighted, has >0 edges, and community_list is a
    # validated partition, so compute nx's reduced formula
    # Q = sum_c [ L_c/m - gamma*(k_c/2m)^2 ] directly over a native degree dict
    # and ONE native edge pass (0.76x nx). L_c counts each intra-community edge
    # once — including a self-loop once — matching nx's G.edges(comm) sum.
    deg = dict(G.degree())
    two_m = sum(deg.values())
    m = two_m / 2.0
    norm = 1.0 / (two_m * two_m)
    cid = {}
    for idx, community in enumerate(community_list):
        for node in community:
            cid[node] = idx
    intra = [0] * len(community_list)
    for u, v in G.edges():
        cu = cid.get(u)
        if cu is not None and cu == cid.get(v):
            intra[cu] += 1
    ksum = [0] * len(community_list)
    for node, d in deg.items():
        c = cid.get(node)
        if c is not None:
            ksum[c] += d
    return sum(
        intra[c] / m - resolution * ksum[c] * ksum[c] * norm
        for c in range(len(community_list))
    )



# Algorithm functions — graph operators
from franken_networkx._fnx import (
    union as _raw_union,
    intersection as _raw_intersection,
    compose as _raw_compose,
    difference as _raw_difference,
    symmetric_difference as _raw_symmetric_difference,
    degree_histogram as _raw_degree_histogram,
)


def _operator_output_class(G, H=None):
    """Pick the fnx output class for a binary/unary graph _operator.

    br-r37-c1-opmsg: nx splits the type-mismatch error message
    along two axes — directedness and multigraphness — rather
    than emitting one combined "same type" message.  Match
    exactly so caller-side string checks align.
    """
    if H is not None:
        if G.is_directed() != H.is_directed():
            raise NetworkXError(
                "All graphs must be directed or undirected."
            )
        if G.is_multigraph() != H.is_multigraph():
            raise NetworkXError(
                "All graphs must be graphs or multigraphs."
            )
    return _concrete_class_for(G)


def _concrete_class_for(G):
    """Return the fnx canonical concrete class for ``G``.

    br-r37-c1-k7dct: ``type(G)`` for a SubgraphView is the synthetic
    ``_FilteredGraphView`` subclass whose ``__init__`` requires a
    ``graph`` arg, so callers that do ``cls()`` blow up downstream
    (intersection / difference / symmetric_difference / compose /
    disjoint_union / relabel_nodes all rebuild via ``cls()``).
    Mirror nx by returning the canonical concrete class for the view's
    (directed, multigraph) flavor.

    br-r37-c1-cfcls: Always return fnx types, not nx types. When G is
    an nx.Graph, we still want fnx output for drop-in parity.
    """
    directed = G.is_directed()
    multigraph = G.is_multigraph()
    if directed and multigraph:
        return MultiDiGraph
    if directed:
        return DiGraph
    if multigraph:
        return MultiGraph
    return Graph


# br-r37-c1-coercefast: the exact concrete fnx classes, for the pass-through
# check at the top of ``_coerce_arg_to_fnx_graph``. A frozenset of TYPES is
# looked up by hash; the ``isinstance`` chain it precedes walks an MRO per call.
_CONCRETE_FNX_GRAPH_TYPES = frozenset((Graph, DiGraph, MultiGraph, MultiDiGraph))


def _coerce_arg_to_fnx_graph(G):
    """br-r37-c1-i2uub: coerce an nx.Graph-typed arg to the matching
    fnx graph class so PyO3-bound Rust operators (which strictly
    accept fnx-typed graphs) work transparently on mixed inputs.

    Pass-through for graphs already of fnx type. For nx graphs, route
    through ``franken_networkx.readwrite._from_nx_graph`` which builds
    the corresponding fnx graph with the same nodes/edges/attrs.

    br-r37-c1-ajhcl: ``_FilteredGraphView`` (SubgraphView /
    EdgeSubgraphView / subgraph_view / restricted_view / reverse_view)
    isinstance-passes the canonical fnx Graph types because they're
    added as a second base for parity, but their filtered node/edge
    set lives entirely in Python — Rust ``_raw_*`` helpers read the
    parent's Rust adjacency directly and silently ignore the filter,
    silently producing wrong answers for connected_components /
    is_connected / number_connected_components / difference /
    symmetric_difference and any other Rust path. Materialize views
    to a concrete fnx graph (preserving only the view's visible
    nodes + edges + attrs) before crossing the Rust boundary.
    """
    # br-r37-c1-coercefast: the overwhelmingly common argument is a graph that is
    # ALREADY a concrete fnx class, and for it this function is a pass-through -
    # but it reached that conclusion only after three failed `isinstance` view
    # checks, each walking an MRO, and a fourth `isinstance` against a 4-tuple.
    # This helper is called at the top of 244 public functions, so that is a
    # per-call tax on essentially the whole API surface.
    #
    # An EXACT type check is safe here and an `isinstance` one would not be: the
    # view classes below deliberately SUBCLASS the canonical fnx types (they are
    # added as a second base for isinstance parity), which is exactly why they
    # must be tested before the `isinstance` branch at the end. `type(G) in ...`
    # cannot match a subclass, so a view can never take this path.
    #
    # Behaviour is unchanged for everything else, including a user subclass of
    # fnx.Graph: it misses this check, finds all three view checks False, and
    # reaches the same `isinstance` pass-through it does today.
    if type(G) in _CONCRETE_FNX_GRAPH_TYPES:
        owner = _shared_unsplit_owner(G)
        if owner is not None:
            return owner
        if not _has_networkx_private_storage(G):
            return G
        return _materialize_view(G)
    if isinstance(G, _FilteredGraphView):
        return _materialize_view(G)
    # br-r37-c1-revview: _ReverseDirectedView and _ReverseMultiDirectedView
    # subclass DiGraph/MultiDiGraph respectively, so they isinstance-pass
    # the canonical-type check below; but their Rust ``inner`` graph
    # still holds the ORIGINAL (non-reversed) adjacency, so any Rust
    # kernel reads through the reverse and silently produces wrong
    # answers (sister bug class to the SubgraphView dispatch trap
    # fixed in br-r37-c1-gshwt / br-r37-c1-2cyfr).  Materialize the
    # view's reversed edges into a fresh fnx DiGraph.
    if isinstance(G, _ReverseDirectedViewBase):
        return _materialize_view(G)
    # br-r37-c1-convview: ``G.to_directed(as_view=True)`` and
    # ``G.to_undirected(as_view=True)`` return dynamic subclasses of
    # ``_ConversionGraphViewBase + DiGraph/Graph`` whose Rust
    # ``inner`` still holds the SOURCE adjacency (directed when
    # converting from directed → undirected, undirected when
    # converting from undirected → directed).  The synthetic view
    # transforms iteration in Python; Rust kernels see right through
    # it and produce wrong answers.  Same fix shape: materialize the
    # view into a fresh fnx graph with correct Rust storage.
    if isinstance(G, _ConversionGraphViewBase):
        return _materialize_view(G)
    if isinstance(G, (Graph, DiGraph, MultiGraph, MultiDiGraph)):
        return G
    try:
        import networkx as _nx_for_coerce

        if isinstance(G, _nx_for_coerce.Graph):
            from franken_networkx.readwrite import _from_nx_graph
            return _from_nx_graph(G)
    except ImportError:
        pass
    return G


def _view_filter_cache_token(view):
    """Describe only filter state whose behavior is known without calling it.

    User callbacks can depend on closure variables, object attributes, or
    node data that do not advance the root graph's structural/edge epochs.
    Their output must therefore be evaluated again for every materialization.
    A built-in node-set filter has known membership semantics, but its set is
    mutable, so retain a snapshot rather than the filter object's identity.
    """
    if not view._filter_edge_is_default:
        return None
    if view._filter_node_is_default:
        return (), ()
    node_filter = view._filter_node
    if type(node_filter) is _NodeSetFilter and type(node_filter.nodes) is set:
        nodes = tuple(node_filter.nodes)
        return tuple(map(id, nodes)), nodes
    if (
        isinstance(node_filter, _types.FunctionType)
        and not node_filter.__closure__
        and not node_filter.__defaults__
        and not node_filter.__kwdefaults__
        and not node_filter.__code__.co_names
    ):
        return (id(node_filter), node_filter.__code__), node_filter
    return None


def _view_node_attribute_snapshot(view, root):
    """Track shallow node-data changes without comparing arbitrary values.

    Node dictionaries have no mutation epoch. Their values may be arrays or
    user objects whose equality is unsuitable for a cache key. Retain their
    identities and keep the original objects alive alongside the cache, so an
    address cannot be reused after an attribute is replaced or removed.
    Nested containers remain shared by the materialization's shallow copy.
    """
    if (
        type(root) in (Graph, DiGraph)
        and _native_graph_has_any_attrs is not None
        and _native_graph_has_any_attrs(root) is False
    ):
        return (), ()
    token = []
    retained = []
    for node, attrs in view.nodes(data=True):
        if not attrs:
            continue
        items = tuple(attrs.items())
        token.append((id(node), tuple((id(key), id(value)) for key, value in items)))
        retained.append((node, items))
    return tuple(token), retained


def _materialize_view(view):
    """The concrete fnx graph a view shows - a filtered view
    (br-r37-c1-ajhcl), a reverse view or a to_directed / to_undirected
    conversion view - for callers that hand it to Rust: a view's own Rust
    storage is empty, so a kernel given the view itself sees no nodes.

    br-r37-c1-4rhw0: built by the view's own copy(), which yields the same
    graph dict, node / edge attr copies and node, edge and adjacency-row
    order as the Python builders this replaced, on its native fast paths:
    subgraph(800) of gnp(1000, 0.01) 1.7 ms against 4.7 ms, a to_directed
    view of it 9.1 ms against 20.8 ms.

    br-r37-c1-jft0i: cached on the view, keyed on the monotonic
    (nodes_seq, edges_seq) of the graph at the ROOT of the view chain - the
    counters of an intermediate view are its empty base's and never move,
    so a view of a view keyed on them kept a stale graph after the root
    changed.

    br-r37-c1-u9a13: and on the root's edge-attribute epoch. The counters
    move on structure only, so after G[u][v]['weight'] = x (or a write
    through a held dict, or set_edge_attributes) every native call on the
    view computed on the copy's old weights - shortest_path_length 2.0
    where networkx answers 3.0. The epoch moves on exactly those writes and
    not on reads or syncs, so a loop of calls on an unchanged view still
    hits - on all four classes, a MultiGraph's attr dicts reporting their
    writes too (not caching a MultiGraph view instead cost 26 ms a call:
    has_path on a 900-node view 0.00x networkx). The concrete graph shares
    the view's graph dict, as networkx's views do.
    """
    root = view
    filter_tokens = []
    filter_references = []
    filters_cacheable = True
    while True:
        if isinstance(root, _FilteredGraphView):
            snapshot = _view_filter_cache_token(root)
            if snapshot is None:
                filters_cacheable = False
            else:
                token, references = snapshot
                filter_tokens.append(token)
                filter_references.append(references)
        inner = getattr(root, "_graph", None)
        if inner is None:
            break
        root = inner
    cache_key = None
    ns = getattr(root, "nodes_seq", None)
    es = getattr(root, "edges_seq", None)
    # Assigned Python rows can change without moving native counters/epochs.
    # Such roots must be walked anew rather than reuse a stale native copy.
    if (
        root is not view
        and filters_cacheable
        and ns is not None
        and es is not None
        and not _has_networkx_private_storage(root)
    ):
        try:
            epoch = _fnx.edge_attr_epoch(root)
        except TypeError:
            epoch = None
        node_token, node_references = _view_node_attribute_snapshot(view, root)
        cache_key = (id(root), ns, es, epoch, tuple(filter_tokens), node_token)
        cached = view.__dict__.get("_fnx_materialized_cache")
        if cached is not None and cached[0] == cache_key:
            return cached[1]

    out = _native_view_copy(view)
    if out is None:
        out = view.copy()
    # br-r37-c1-u9a13: networkx's views share the parent's graph dict; the
    # concrete graph shares it too (as copy.copy's result does), so a graph
    # attribute written after the cache was filled is there without a check.
    vars(out)[_GRAPH_ATTR_OVERRIDE] = view.graph
    out._fnx_register_gc_dict(vars(out))
    # br-r37-c1-36v6r: copy() fills each row in edge-walk order (networkx's
    # copy() does too), but the view's rows - which networkx's kernels walk -
    # are its root's rows filtered, swapped through a reverse view: bfs /
    # dfs / traversal order on subgraph, restricted_view and edge_subgraph
    # views of a Graph, and every pred-row reader on a directed view,
    # followed the copy's order instead.
    row_root = _view_row_root(view)
    if (
        row_root is not None
        and row_root[0].is_directed() == out.is_directed()
        and row_root[0].is_multigraph() == out.is_multigraph()
    ):
        root, swap, shortest_keep = row_root
        if out.is_directed():
            out._fnx_reorder_rows_like(root, swap)
        else:
            out._fnx_reorder_rows_like(root)
        if out.is_multigraph() and shortest_keep is not None:
            _set_node_set_ordered_rows(view, root, out, shortest_keep)
    else:
        # A conversion view in the chain: its rows are no graph's rows (a
        # to_undirected view's are set unions), so hand them over as read.
        nodes = list(out)
        if out.is_directed():
            rows = ([list(view.succ[n]) for n in nodes], [list(view.pred[n]) for n in nodes])
        elif type(view) is _UNDIRECTED_CONVERSION_VIEW_TYPES[out.is_multigraph()] and type(
            view._graph
        ) is (MultiDiGraph if out.is_multigraph() else DiGraph):
            rows = ([list(_union_row(view._graph, n)) for n in nodes],)
        else:
            rows = ([list(view.adj[n]) for n in nodes],)
        if out.is_multigraph():  # a multigraph takes (node, row) pairs
            rows = tuple(zip(nodes, side) for side in rows)
        out._fnx_set_row_orders(*rows)
    if cache_key is not None:
        view.__dict__["_fnx_materialized_cache"] = (
            cache_key,
            out,
            (root, filter_references, node_references),
        )
    return out


def _native_view_copy(view):
    """br-r37-c1-8xp4a: the view's concrete graph built natively from its
    root, or None to walk the view (view.copy()). A reverse view of a
    concrete DiGraph / MultiDiGraph is its root's native reverse copy - the
    same nodes, edges, keys and attribute values as the walk at a fraction
    of its cost; its rows are then put in the view's order below, as the
    walk's are."""
    if type(view) is _ReverseDirectedView or type(view) is _ReverseMultiDirectedView:
        root = view._graph
        native = _NATIVE_REVERSE.get(type(root))
        if native is not None and not _has_networkx_private_storage(root):
            return native(root)
    return None


def _reverse_view_root(G):
    """br-r37-c1-8xp4a: the concrete root an exact reverse view reads, or None.

    A reverse view's successor rows ARE its root's predecessor rows, in their
    order, so a traversal that follows successors on the view is the root's
    traversal over predecessors - bfs_edges(view) is bfs_edges(root,
    reverse=True), descendants(view) is ancestors(root) - with nothing to copy.
    The materialised route built the root's whole reverse copy per call
    (0.41x networkx for a fresh-view bfs_edges on a DiGraph). Same eligibility
    as _native_view_copy: an exact reverse view over a concrete class without
    networkx private storage."""
    if type(G) is _ReverseDirectedView or type(G) is _ReverseMultiDirectedView:
        root = G._graph
        if _NATIVE_REVERSE.get(type(root)) is not None and not _has_networkx_private_storage(
            root
        ):
            return root
    return None


def _view_row_root(view):
    """(root, swap, shortest_keep) when every view from ``view`` down to
    the concrete graph at the root of its chain keeps the root's row order -
    a filtered view iterates each parent row with entries filtered out
    (networkx's FilterAtlas has no ``.nodes`` shortcut for a row), a
    reverse view swaps succ and pred - else None: conversion views
    (to_undirected's rows are a set union) and a root whose rows live in
    networkx private storage. ``shortest_keep`` is the size of the smallest
    node set a filtered view in the chain filters on, None if none does: a
    multigraph row longer than twice that can iterate the set instead (see
    _set_node_set_ordered_rows)."""
    swap = False
    shortest_keep = None
    node = view
    while True:
        if isinstance(node, _FilteredGraphView):
            try:  # the view's own rule: an unsized .nodes never iterates
                size = len(node._filter_node.nodes)
            except (AttributeError, TypeError):
                size = None
            if size is not None and (shortest_keep is None or size < shortest_keep):
                shortest_keep = size
            node = node._graph
        elif isinstance(node, _ReverseDirectedViewBase):
            swap = not swap
            node = node._graph
        else:
            break
    if (
        not isinstance(node, (Graph, DiGraph, MultiGraph, MultiDiGraph))
        or isinstance(node, _ConversionGraphViewBase)
        or _has_networkx_private_storage(node)
    ):
        return None
    return node, swap, shortest_keep


def _set_node_set_ordered_rows(view, root, out, shortest_keep):
    """networkx's filtered MULTIGRAPH row iterates the view's node set
    instead of its parent row once the row holds more than twice as many
    neighbours as the set has nodes (FilterMultiInner reads NODE_OK.nodes;
    br-r37-c1-0ek49), so the root's row order - which ``out`` was given -
    is wrong for such a row. A row in the chain is never longer than its
    node's degree in the root, so only nodes whose root degree passes twice
    the smallest set can have one; their rows are handed over as the view
    reads them."""
    threshold = 2 * shortest_keep
    if threshold >= len(root):  # no row holds more neighbours than the graph has nodes
        return
    nodes = [n for n, d in root.degree(list(out)) if d > threshold]
    if not nodes:
        return
    if out.is_directed():
        out._fnx_set_row_orders(
            [(n, list(view.succ[n])) for n in nodes], [(n, list(view.pred[n])) for n in nodes]
        )
    else:
        out._fnx_set_row_orders([(n, list(view.adj[n])) for n in nodes])


def _rebuild_operator_output(output, cls):
    """Rebuild a generic fnx Graph (what the Rust operator returns) as
    an instance of ``cls`` (the caller's graph class).

    The Rust binding always returns an undirected ``Graph`` regardless
    of input class (franken_networkx-47bag). Copy nodes + edges across
    into a freshly-minted ``cls()`` so callers see the expected class.
    Data dicts are preserved.
    """
    if type(output) is cls:
        return output
    rebuilt = cls()
    rebuilt.graph.update(dict(output.graph))
    rebuilt.add_nodes_from((n, dict(d)) for n, d in output.nodes(data=True))
    if rebuilt.is_multigraph():
        # When the Rust output is simple and we're rebuilding into a
        # Multi*, assign integer keys to each edge.
        if output.is_multigraph():
            rebuilt.add_edges_from(
                (u, v, k, dict(d))
                for u, v, k, d in output.edges(keys=True, data=True)
            )
        else:
            rebuilt.add_edges_from(
                (u, v, dict(d)) for u, v, d in output.edges(data=True)
            )
    else:
        rebuilt.add_edges_from(
            (u, v, dict(d)) for u, v, d in output.edges(data=True)
        )
    return rebuilt


def _copy_attrs_into(rebuilt, G, H=None):
    """Merge node + edge attributes from G (and H, if given) into
    ``rebuilt``. H's attrs win on overlap (nx.compose semantics).
    """
    for node, attrs in G.nodes(data=True):
        if node in rebuilt:
            rebuilt.nodes[node].update(dict(attrs))
    if rebuilt.is_multigraph():
        if G.is_multigraph():
            for u, v, key, attrs in G.edges(keys=True, data=True):
                if rebuilt.has_edge(u, v, key):
                    rebuilt[u][v][key].update(dict(attrs))
        else:
            for u, v, attrs in G.edges(data=True):
                if rebuilt.has_edge(u, v):
                    rebuilt[u][v][0].update(dict(attrs))
    else:
        for u, v, attrs in G.edges(data=True):
            if rebuilt.has_edge(u, v):
                rebuilt[u][v].update(dict(attrs))
    if H is not None:
        # H attrs win on overlap
        for node, attrs in H.nodes(data=True):
            if node in rebuilt:
                rebuilt.nodes[node].update(dict(attrs))
        if rebuilt.is_multigraph():
            if H.is_multigraph():
                for u, v, key, attrs in H.edges(keys=True, data=True):
                    if rebuilt.has_edge(u, v, key):
                        rebuilt[u][v][key].update(dict(attrs))
            else:
                for u, v, attrs in H.edges(data=True):
                    if rebuilt.has_edge(u, v):
                        rebuilt[u][v][0].update(dict(attrs))
        else:
            for u, v, attrs in H.edges(data=True):
                if rebuilt.has_edge(u, v):
                    rebuilt[u][v].update(dict(attrs))
    return rebuilt


def union(G, H, rename=()):
    """Return the union of graphs G and H.

    Parameters
    ----------
    G : graph
        A graph.
    H : graph
        A graph.
    rename : tuple, optional
        A 2-tuple of names to prepend to node names in G and H respectively.
        Default is ().

    Returns
    -------
    Graph
        A new graph with the nodes and edges from both G and H.
    """
    # br-r37-c1-i2uub: accept nx-typed inputs by coercing to fnx
    # graphs (matches nx's permissive duck-typing on mixed inputs).
    G = _coerce_arg_to_fnx_graph(G)
    H = _coerce_arg_to_fnx_graph(H)
    if rename:
        # br-r37-c1-kmxke: union_all natively supports rename (nx's own
        # union IS union_all([G, H], rename)). The old
        # _union_with_rename_via_parity round-trip (2x fnx->nx conversion
        # + nx union + per-edge _from_nx_graph rebuild) made
        # union(rename=...) ~6.4x slower than nx.
        return union_all([G, H], rename=rename)
    # br-r37-c1-union-order: nx checks the type-mismatch
    # (directed-vs-undirected, graph-vs-multigraph) BEFORE the
    # disjoint-nodes check.  Previously fnx checked
    # disjoint-nodes first, so a Graph + DiGraph with overlapping
    # node sets reported "node sets not disjoint" instead of the
    # more fundamental "must be directed or undirected" — the
    # disjoint check is meaningless when the graphs aren't even
    # the same kind.  Run the type check first.
    cls = _operator_output_class(G, H)
    # br-r37-c1-union-disjoint: nx raises NetworkXError("The node
    # sets of the graphs are not disjoint.") on overlapping inputs
    # before any merging happens. Previously fnx silently merged,
    # which matches `compose` behavior but breaks the documented
    # `union` contract — the docstring above already says "names of
    # nodes must be unique" (in nx's docstring; fnx's was missing
    # the same warning). Match nx's raise so callers don't silently
    # lose attribute data when nodes collide.
    # br-r37-c1-l5ve7: canonical-key disjointness via the native index
    # for the exact-type case (the Python set(G) built full PyObject
    # sets — ~24ms on 3k+3k nodes).
    if type(G) is Graph and type(H) is Graph:
        _disjoint = getattr(G, "_native_nodes_disjoint", None)
        disjoint = _disjoint(H) if _disjoint is not None else set(G).isdisjoint(H)
    else:
        disjoint = set(G).isdisjoint(H)
    if not disjoint:
        raise NetworkXError(
            "The node sets of the graphs are not disjoint.\n"
            "Use `rename` to specify prefixes for the graphs or use\n"
            "disjoint_union(G1, G2, ..., GN).",
        )
    # br-unionsinglepass: build the union in ONE attributed construction pass
    # instead of native _raw_union (which DROPS every attribute) +
    # _rebuild_operator_output + a slow _copy_attrs_into walk that re-queried
    # both inputs per node/edge via has_edge / __getitem__ (the ~11x tax). This
    # also FIXES a parity bug: the old pipeline dropped the graph-level
    # attribute dict entirely (`union(G, H).graph == {}` instead of nx's merged
    # `{**G.graph, **H.graph}`). Node sets are disjoint here, so a plain
    # add_*_from with data carries every attribute; later graph (H) wins on
    # any graph-attr key clash, matching networkx's union_all.
    # br-r37-c1-l5ve7: with disjoint inputs nx's union output is
    # STATEMENT-IDENTICAL to compose (union_all == compose_all minus the
    # disjointness check, which already passed above) — reuse the native
    # single-pass compose binding for the exact Graph x Graph case.
    if (
        type(G) is Graph
        and type(H) is Graph
        and cls is Graph
        and not _has_networkx_private_storage(G)
        and not _has_networkx_private_storage(H)
    ):
        native = getattr(G, "_native_compose", None)
        if native is not None:
            return native(H)
    rebuilt = cls()
    rebuilt.graph.update(G.graph)
    rebuilt.graph.update(H.graph)
    rebuilt.add_nodes_from(G.nodes(data=True))
    rebuilt.add_nodes_from(H.nodes(data=True))
    if rebuilt.is_multigraph():
        # br-edgekeyedbatch (bt): union requires DISJOINT node sets, so G's and H's
        # keyed edges never collide — combine both into ONE list and commit in a
        # single add_edges_from. The combined 4-tuple LIST on the node-populated
        # edgeless ``rebuilt`` engages the native keyed edges-only batch (was 0.40x:
        # two separate add_edges_from of VIEWS — a view isn't list/tuple so it skips
        # the batch dispatch, and the second ran per-edge on a non-fresh graph).
        rebuilt.add_edges_from(
            list(G.edges(keys=True, data=True)) + list(H.edges(keys=True, data=True))
        )
    else:
        # br-r37-c1-unionlist (cc): the node sets are disjoint (checked above), so G's
        # and H's edges never collide — combine both into ONE list and commit in a
        # single add_edges_from on the node-populated, edgeless ``rebuilt``. The old
        # two separate add_edges_from(VIEW) passed a VIEW (not list/tuple, so it skips
        # the native batch gate and pays materialize+retry) AND ran the second on a
        # non-fresh graph (a wasted touches-existing pre-scan). One LIST on a fresh
        # graph engages the native batch directly: 0.49x -> 1.15x (mirrors the
        # multigraph branch just above).
        rebuilt.add_edges_from(list(G.edges(data=True)) + list(H.edges(data=True)))
    return rebuilt


def compose(G, H):
    """Return the composition of G and H — G ∪ H with H's attrs winning on overlap."""
    cls = _operator_output_class(G, H)
    # br-r37-c1-l5ve7: native single-pass for the exact Graph x Graph
    # case (the Python loop below pays per-node/edge interpreter calls).
    if (
        type(G) is Graph
        and type(H) is Graph
        and cls is Graph
        and not _has_networkx_private_storage(G)
        and not _has_networkx_private_storage(H)
    ):
        native = getattr(G, "_native_compose", None)
        if native is not None:
            return native(H)
    # br-r37-c1-composedir (cc): native single-pass for exact DiGraph x DiGraph
    # (directed compose was 0.74x via the Python replay). PyDiGraph._native_compose
    # returns None for row-display-override graphs, falling back to the replay below.
    if (
        type(G) is DiGraph
        and type(H) is DiGraph
        and cls is DiGraph
        and not _has_networkx_private_storage(G)
        and not _has_networkx_private_storage(H)
    ):
        native = getattr(G, "_native_compose", None)
        if native is not None:
            result = native(H)
            if result is not None:
                return result
    # Build directly in Python so edge insertion/orientation follows
    # nx.compose exactly: graph G first, then H with H attrs winning.
    # This also keeps the multigraph path away from the Rust edge-view
    # ``keys=True`` collision fixed under franken_networkx-47bag.
    out = cls()
    out.graph.update(dict(G.graph))
    out.graph.update(dict(H.graph))
    # br-r37-c1-composenodebatch (cc): batch the node merge through add_nodes_from
    # instead of the per-node add_node loop (the dominant cost of directed compose,
    # ~0.62x vs nx; edges already batch below). add_nodes_from((node, attrs))
    # adds-or-updates exactly like nx's compose (H's overlapping nodes update G's,
    # new ones are added) and, unlike ``add_node(node, **attrs)``, does not unpack
    # attrs as kwargs so non-string node-attr keys are handled (nx parity).
    out.add_nodes_from(G.nodes(data=True))
    out.add_nodes_from(H.nodes(data=True))
    if G.is_multigraph():
        # br-r37-c1-mgcompose: pre-merge G's then H's keyed edges in Python (H's data
        # UPDATES a shared (u,v,key), exactly as nx's second add_edges_from overwrites
        # in place; new H edges append) so the result has each (u,v,key) ONCE in
        # G-then-H-new order, then commit them through ONE fresh native keyed-with-data
        # batch — instead of two add_edges_from where H's runs per-edge on a non-fresh
        # graph (add_edge_with_key_and_attrs = 2 record_decision/edge). MultiGraph lacks
        # the native method (getattr -> None) and falls through to add_edges_from.
        _edge_map = {}
        for u, v, key, d in G.edges(keys=True, data=True):
            _edge_map[(u, v, key)] = dict(d)
        for u, v, key, d in H.edges(keys=True, data=True):
            _slot = _edge_map.get((u, v, key))
            if _slot is None:
                _edge_map[(u, v, key)] = dict(d)
            else:
                _slot.update(d)
        _all_edges = [(u, v, key, data) for (u, v, key), data in _edge_map.items()]
        # br-edgekeyedbatch (bt): the keyed edges-only batch (via
        # _try_add_attr_edges_from_batch — out is node-populated + edgeless, every
        # endpoint already a node, each (u,v,key) deduped above) is faster than
        # _native_add_keyed_edges_with_data for the common int-node case (28.9 vs
        # 43ms at n=400^2). Try it first; keep _native for the non-int case where the
        # int batch bails (returns False = nothing added, so the fallbacks are safe).
        _batch = getattr(out, "_try_add_attr_edges_from_batch", None)
        if _batch is None or not _batch(_all_edges):
            _native = getattr(out, "_native_add_keyed_edges_with_data", None)
            if _native is None or not _native(_all_edges):
                out.add_edges_from(_all_edges)
    else:
        out.add_edges_from((u, v, dict(d)) for u, v, d in G.edges(data=True))
        out.add_edges_from((u, v, dict(d)) for u, v, d in H.edges(data=True))
    return out


def intersection(G, H):
    """Return a graph with the edges present in both G and H (same node set).

    br-r37-c1-saf8a: nx implements intersection via Python set
    intersection and ``add_nodes_from(set) / add_edges_from(set)``,
    which produces a hash-based (but stable + deterministic) node and
    edge iteration order.

    br-r37-c1-aun4c: intersection_all now replicates nx's set-based
    construction VERBATIM in pure Python (identical set iteration), so
    the nx round-trip (_intersection_via_parity: 2x fnx->nx conversion
    + per-edge rebuild, ~7x nx) is no longer needed — nx's own
    ``intersection`` is exactly ``intersection_all([G, H])``.
    """
    G = _coerce_arg_to_fnx_graph(G)
    H = _coerce_arg_to_fnx_graph(H)
    if type(G) is Graph and type(H) is Graph:
        R = Graph()
        node_intersection = set(G.nodes)
        node_intersection &= set(H.nodes)
        R.add_nodes_from(node_intersection)

        # br-r37-c1-interorder: replicate nx.intersection_all's EXACT edge-set
        # construction so the projected EDGE ORDER matches nx byte-for-byte. nx
        # builds each graph's undirected edge set WITH both orientations, then
        # intersects (``edge_intersection = G_set; edge_intersection &= H_set``).
        # The prior comprehension over only H's witness set diverged from nx's
        # set-& iteration order in hash-collision cases (~0.2%; the edge SET was
        # always correct, only list(edges()) order differed).
        g_set = set(G.edges)
        g_set.update((v, u) for u, v in list(g_set))
        h_set = set(H.edges)
        h_set.update((v, u) for u, v in list(h_set))
        edge_intersection = g_set
        edge_intersection &= h_set
        R.add_edges_from(edge_intersection)
        return _finalize_operator_result(R)
    return intersection_all([G, H])


def _intersection_via_parity(G, H):
    """br-r37-c1-nhz31: private helper keeps the public ``intersection``
    classified as PY_WRAPPER (not NX_DELEGATED) in the coverage
    matrix — same pattern as ``_sbm_impl`` / ``_hoffman_singleton_impl``.
    """
    nx_result = _nx.intersection(
        _networkx_graph_for_parity(G),
        _networkx_graph_for_parity(H),
        backend="networkx",
    )
    from franken_networkx.readwrite import _from_nx_graph
    cls = _operator_output_class(G, H)
    return _from_nx_graph(nx_result, create_using=cls())


def difference(G, H):
    """Return a graph with edges in G but not in H (same node set)."""
    # br-r37-c1-jwdzp: accept nx-typed inputs (sibling of br-r37-c1-i2uub).
    G = _coerce_arg_to_fnx_graph(G)
    H = _coerce_arg_to_fnx_graph(H)
    # br-r37-c1-aun4c: replicate installed nx VERBATIM, including the
    # check SEQUENCE (multigraph mismatch -> create_empty_copy -> node-set
    # equality — br-diffnodes' early node-set check fired before the
    # mismatch error, diverging on doubly-invalid inputs).
    # create_empty_copy(with_data=False) gives G's node order with NO
    # node/graph attrs; result edges carry NO data. The per-edge add_edge
    # loop is batched into one add_edges_from (order/dedup-identical).
    # Replaces both the _raw_difference+rebuild path (~8.4x,
    # rebuild-tax-bound) and the MultiGraph nx round-trip.
    if G.is_multigraph() != H.is_multigraph():
        raise NetworkXError("G and H must both be graphs or multigraphs.")
    # br-r37-c1-natdiff: fully-native MultiDiGraph difference — builds the result
    # in Rust (no Python EdgeView materialization of either graph's edges, no
    # per-edge add_edge, no wasted empty-copy). The node-set check moves ahead of
    # the (skipped) create_empty_copy, which never raises, so error order is
    # unchanged. Falls back to the snapshot path below if the native path declines.
    if (type(G) is MultiDiGraph and type(H) is MultiDiGraph) or (
        type(G) is MultiGraph and type(H) is MultiGraph
    ):
        if set(G) != set(H):
            raise NetworkXError("Node sets of graphs not equal")
        # cc-mgnatdiff-identity: the native multigraph difference was rewritten to a
        # lean identity-int fast path — internal-key membership (no per-edge
        # display_key_lookup), G's exact keys preserved (no re-sequencing), and NO
        # edge_py_keys mirror. It now beats the set-snapshot + keyed-batch fallback
        # (which pays a full Python edges(keys=True) materialization + re-parse) by
        # skipping all Python edge materialization. Declines (-> None) when either
        # operand has remapped/str/float keys or z6uka display overrides, in which
        # case we fall through to the proven byte-identical fallback below. The
        # node-set check above preserves the error contract before create_empty_copy.
        _native_R = G._native_difference(H)
        if _native_R is not None:
            return _native_R
    # br-r37-c1-natdiffsimple: fully-native simple-Graph difference — same lever
    # as the MultiGraph path above but for ``type(G) is Graph``. Builds the result
    # in Rust (no create_empty_copy + EdgeView set + add_edges_from). The node-set
    # check moves ahead of the (skipped) create_empty_copy, which never raises, so
    # error order is unchanged. Declines (-> None) on z6uka display overrides,
    # falling through to the snapshot path below.
    if type(G) is Graph and type(H) is Graph:
        if set(G) != set(H):
            raise NetworkXError("Node sets of graphs not equal")
        _native_R = G._native_difference(H)
        if _native_R is not None:
            return _native_R
    # br-r37-c1-natdiffsimple-di: directed sibling — fully-native simple DiGraph
    # difference (PyDiGraph::_native_difference). Same lever/error-order contract
    # as the undirected path above.
    if type(G) is DiGraph and type(H) is DiGraph:
        if set(G) != set(H):
            raise NetworkXError("Node sets of graphs not equal")
        _native_R = G._native_difference(H)
        if _native_R is not None:
            return _native_R
    R = create_empty_copy(G, with_data=False)
    if set(G) != set(H):
        raise NetworkXError("Node sets of graphs not equal")
    # br-r37-c1-diffset: snapshot H's edges into a Python set ONCE and filter
    # with C membership tests, instead of a per-edge H.has_edge() call (each a
    # PyO3 / view-machinery crossing — ~55% of the time, 1.8x nx). For
    # undirected graphs an edge is present in either orientation, so both
    # (u, v) and (v, u) go into the set. G.edges() iteration order is
    # preserved, so the result is byte-identical to the has_edge filter.
    directed = G.is_directed()
    if G.is_multigraph():
        if directed:
            h_set = set(H.edges(keys=True))
        else:
            h_set = set()
            for u, v, key in H.edges(keys=True):
                h_set.add((u, v, key))
                h_set.add((v, u, key))
        # br-r37-c1-urle5b: native (u, v, key) no-data batch on the fresh
        # result — set-op edges carry no data and the keys come straight from
        # G.edges(keys=True). Falls back to add_edges_from if the fast path
        # declines (e.g. non-fresh R / display conflict).
        _kept = [e for e in G.edges(keys=True) if e not in h_set]
        _native = getattr(R, "_native_add_keyed_edges_no_data", None)
        if _native is None or not _native(_kept):
            R.add_edges_from(_kept)
    else:
        if directed:
            h_set = set(H.edges())
        else:
            h_set = set()
            for u, v in H.edges():
                h_set.add((u, v))
                h_set.add((v, u))
        # br-r37-c1-bgqqc: materialize the filtered edge batch so Graph's
        # native list/tuple add_edges_from fast path can build the fresh
        # result in one Rust bulk insert instead of walking a generator
        # through the Python wrapper edge by edge.
        R.add_edges_from([e for e in G.edges() if e not in h_set])
    return R


def symmetric_difference(G, H):
    """Return a graph with edges in exactly one of G, H (same node set)."""
    # br-r37-c1-jwdzp: accept nx-typed inputs (sibling of br-r37-c1-i2uub).
    G = _coerce_arg_to_fnx_graph(G)
    H = _coerce_arg_to_fnx_graph(H)
    # br-r37-c1-aun4c: replicate installed nx VERBATIM (see difference) —
    # check sequence, with_data=False copy depth, the (vestigial under the
    # equal-node-sets precondition) symmetric-difference node add, and
    # both directional edge passes, each batched into one add_edges_from.
    if G.is_multigraph() != H.is_multigraph():
        raise NetworkXError("G and H must both be graphs or multigraphs.")
    if (type(G) is MultiDiGraph and type(H) is MultiDiGraph) or (
        type(G) is MultiGraph and type(H) is MultiGraph
    ):
        if set(G) != set(H):
            raise NetworkXError("Node sets of graphs not equal")
        # cc-mgnatsymdiff-identity: the native multigraph symmetric_difference was
        # rewritten to a lean identity-int fast path — internal-key membership, each
        # operand's own keys PRESERVED (the old re-sequencing was byte-wrong for
        # pairs with non-contiguous kept keys), and NO edge_py_keys mirror. It beats
        # the set-snapshot + keyed-batch fallback (which materializes BOTH graphs'
        # edges(keys=True) into Python sets) by doing everything in Rust. Declines
        # (-> None) for remapped/str/float keys or z6uka display overrides -> proven
        # byte-identical fallback below. The set check preserves the error contract.
        _native_R = G._native_symmetric_difference(H)
        if _native_R is not None:
            return _native_R
    # br-r37-c1-natsymdiff(-di): fully-native simple Graph/DiGraph
    # symmetric_difference — same lever as the Multi* path above (G-only then
    # H-only edges, in Rust, no create_empty_copy + EdgeView sets + add_edges_from).
    # Equal-node-sets check precedes the skipped create_empty_copy (never raises),
    # so error order is unchanged. Declines (-> None) on z6uka display overrides.
    if (type(G) is Graph and type(H) is Graph) or (
        type(G) is DiGraph and type(H) is DiGraph
    ):
        if set(G) != set(H):
            raise NetworkXError("Node sets of graphs not equal")
        _native_R = G._native_symmetric_difference(H)
        if _native_R is not None:
            return _native_R
    R = create_empty_copy(G, with_data=False)
    if set(G) != set(H):
        raise NetworkXError("Node sets of graphs not equal")
    gnodes = set(G)
    hnodes = set(H)
    nodes = gnodes.symmetric_difference(hnodes)
    R.add_nodes_from(nodes)
    # br-r37-c1-diffset: snapshot each graph's edges into a Python set once
    # and filter with C membership, instead of per-edge has_edge() (two passes
    # here, so double the saved PyO3/view crossings). Undirected edges are
    # present in either orientation, so both (u, v) and (v, u) go in the set.
    if G.is_multigraph():
        if G.is_directed():
            g_set = set(G.edges(keys=True))
            h_set = set(H.edges(keys=True))
        else:
            g_set, h_set = set(), set()
            for u, v, key in G.edges(keys=True):
                g_set.add((u, v, key)); g_set.add((v, u, key))
            for u, v, key in H.edges(keys=True):
                h_set.add((u, v, key)); h_set.add((v, u, key))
        # br-r37-c1-urle5b: both directional passes carry no data and produce
        # DISJOINT (u, v, key) edges (an edge in both G and H is in neither
        # pass), so they can be added in ONE native batch on the fresh result
        # (G's edges first, matching the two-pass order). Falls back otherwise.
        _kept = [e for e in G.edges(keys=True) if e not in h_set]
        _kept += [e for e in H.edges(keys=True) if e not in g_set]
        _native = getattr(R, "_native_add_keyed_edges_no_data", None)
        if _native is None or not _native(_kept):
            R.add_edges_from(e for e in G.edges(keys=True) if e not in h_set)
            R.add_edges_from(e for e in H.edges(keys=True) if e not in g_set)
    else:
        if G.is_directed():
            g_set = set(G.edges())
            h_set = set(H.edges())
        else:
            g_set, h_set = set(), set()
            for u, v in G.edges():
                g_set.add((u, v)); g_set.add((v, u))
            for u, v in H.edges():
                h_set.add((u, v)); h_set.add((v, u))
        # br-r37-c1-bgqqc: keep the wrapper's G-only then H-only order, but
        # pass one concrete batch to the native simple-Graph construction
        # fast path.
        R.add_edges_from(
            [e for e in G.edges() if e not in h_set]
            + [e for e in H.edges() if e not in g_set]
        )
    return R


def _multigraph_diff_via_parity(name, G, H):
    """Delegate the MultiGraph variant of difference /
    symmetric_difference to nx (br-r37-c1-6sgls)."""
    import networkx as _nx_mod
    from franken_networkx.readwrite import _from_nx_graph
    nx_op = getattr(_nx_mod, name)
    nx_result = nx_op(
        _networkx_graph_for_parity(G),
        _networkx_graph_for_parity(H),
        backend="networkx",
    )
    cls = _operator_output_class(G, H)
    return _from_nx_graph(nx_result, create_using=cls())


def _union_with_rename_via_parity(G, H, rename):
    """Helper — keeps ``union`` classified as PY_WRAPPER.

    Wraps upstream nx.union (needed for ``rename`` support) and then
    rehydrates the nx.Graph result back into the fnx Python surface
    via ``_from_nx_graph`` — callers always receive an fnx graph, not
    an nx graph (franken_networkx-3ehfp).
    """
    import networkx as _nx_mod
    from franken_networkx.readwrite import _from_nx_graph

    nx_result = _nx_mod.union(
        _networkx_graph_for_parity(G),
        _networkx_graph_for_parity(H),
        rename=rename,
        backend="networkx",
    )
    # Pick the fnx target class from G (nx.union preserves G's class).
    if isinstance(G, (Graph, DiGraph, MultiGraph, MultiDiGraph)):
        create_using = type(G)()
    else:
        create_using = None
    return _from_nx_graph(nx_result, create_using=create_using)

# Algorithm functions — transitive closure/reduction
from franken_networkx._fnx import (
    multidigraph_transitive_closure as _raw_multidigraph_transitive_closure,
    transitive_closure as _raw_transitive_closure,
    transitive_reduction as _raw_transitive_reduction,
)


def transitive_closure(G, reflexive=False):
    """Return the transitive closure of ``G``.

    br-isokw: ``G`` matches nx.

    br-tcmg: nx.transitive_closure on a MultiDiGraph preserves the
    MultiDiGraph class and includes self-loops ``(u, u)`` for any
    node ``u`` that participates in a cycle (i.e. can reach itself
    via a path of length >= 1 when reflexive=False). fnx's Rust
    binding returned a plain DiGraph with no cycle self-loops.
    Delegate for multigraphs and for graphs known to contain cycles
    (where the self-loop distinction matters).
    """
    # br-r37-c1-nwkg0: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-tcreflnone: nx treats ``reflexive=None`` as the historical
    # default — it maps to False semantically but was kept as a
    # tri-value flag (None / False / True). The Rust binding is
    # strictly typed and raised TypeError on None. Normalize None to
    # False before the fast-path branch; nx still receives the original
    # value when delegating.
    # Delegate for: multigraphs (class preservation), undirected
    # (Rust binding doesn't accept them), and reflexive in {True, None}
    # (non-default). br-r37-c1-tc-cyclic: cyclic directed graphs no longer
    # delegate — the native kernel now emits cycle-induced (v, v) self-loops
    # (reachable-back BFS seeding), so it matches nx for reflexive=False on any
    # DiGraph. This drops both nx's Python compute AND the _from_nx_graph
    # rebuild of the (often dense) closure.
    if reflexive not in {None, True, False}:
        raise NetworkXError("Incorrect value for the parameter `reflexive`")
    if (
        G.is_multigraph()
        or not G.is_directed()
        or reflexive is not False
    ):
        if G.is_multigraph() and G.is_directed() and reflexive is False:
            result = _raw_multidigraph_transitive_closure(G)
            if result is not None:
                return result
        TC = G.copy()
        for v in G:
            # Lists, not nx's generators: descendants() is a set, so no target
            # repeats and the `u not in TC[v]` filter reads the same TC whether
            # the edges go in one by one or together - and a list keeps the
            # batch that a TC-reading generator would give up (br-r37-c1-imddi).
            if reflexive is None:
                TC.add_edges_from([(v, u) for u in descendants(G, v) if u not in TC[v]])
            elif reflexive:
                TC.add_edges_from(
                    [(v, u) for u in descendants(G, v) | {v} if u not in TC[v]]
                )
            else:
                # nx's `e[1] not in TC[v]` sees the edges added earlier in the
                # same pass, because its add_edges_from consumes the generator
                # lazily; edge_bfs repeats targets, so on a multigraph every
                # repeat would become another parallel edge (a 24-ring
                # MultiGraph gave 288 edges, nx 276). Replay the lazy check
                # with a seen-set and pass a list.
                seen = set(TC[v])
                new_edges = []
                for e in edge_bfs(G, v):
                    if e[1] not in seen:
                        seen.add(e[1])
                        new_edges.append((v, e[1]))
                TC.add_edges_from(new_edges)
        return TC
    result = _raw_transitive_closure(G, reflexive=False)
    # br-r37-c1-gtkxs: the Rust kernel returns a DiGraph stripped of
    # node and edge attributes. nx's transitive_closure preserves
    # them. Copy attrs from G onto the result for parity.
    # br-r37-c1-mstminattr (sibling): nx's ``TC = G.copy()`` ALSO carries the
    # graph-level attrs; the kernel drops them, so restore here too.
    if G.graph:
        result.graph.update(dict(G.graph))
    # br-r37-c1-tcbatch: nx's transitive_closure does ``TC = G.copy()`` so the
    # original edges keep their attrs for free; the native kernel strips node/edge
    # attrs, so restore them. The old per-item ``result[u][v].update(attrs)`` forced
    # a full adjacency-keydict row materialization (``_native_adjacency_dict``) for
    # EACH source node on the DENSE closure — ~90% of wall time (0.16x vs nx at 200
    # nodes). Route through add_nodes_from/add_edges_from, which write attrs straight
    # to the store. Byte-identical: the closure already contains every G node and
    # edge, so these are pure in-place attr updates (0.16x -> 1.86x vs nx).
    result.add_nodes_from((n, a) for n, a in G.nodes(data=True) if a)
    result.add_edges_from((u, v, a) for u, v, a in G.edges(data=True) if a)
    return result


def transitive_reduction(G):
    """Return the transitive reduction of ``G``.

    br-isokw: ``G`` matches nx; Rust binding used ``g``.

    br-r37-c1-utmy6: the Rust binding's transitive_reduction produced
    a graph whose edges() iteration order drifted from nx (e.g.
    fnx [('a','c'),('a','b'),...] vs nx [('a','b'),('a','c'),...]).
    Delegate to nx so edge iteration order matches its
    topological-DFS reduction contract exactly.
    """
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    if not is_directed_acyclic_graph(G):
        raise NetworkXError("Directed Acyclic Graph required for transitive_reduction")
    # br-r37-c1-trinproc: the parity helper round-trips fnx->nx->fnx (a full
    # O(V+E) conversion each way, ~32% of wall time / the whole 1.5x gap vs nx).
    # Run nx's exact algorithm in-process on a successor snapshot instead,
    # building the fnx result directly. ``u_nbrs`` is a real Python ``set`` and
    # the snapshot preserves successor iteration order, so the emitted edge
    # order (``for v in u_nbrs``) is byte-identical to nx's
    # ``TR.add_edges_from(... for v in u_nbrs)``. Skips both conversions.
    # br-r37-c1-rktno: a MultiDiGraph runs the same algorithm (its successor
    # rows are unique neighbours, as nx's G[u] is), and the answer is a plain
    # DiGraph for every input class, as nx's TR = nx.DiGraph() is.
    return _transitive_reduction_inprocess(G)


def _transitive_reduction_inprocess(G):
    """nx.transitive_reduction reimplemented in-process (no fnx<->nx conversion).

    Mirrors networkx's algorithm exactly: per node ``u`` (node order), start from
    ``set(succ[u])`` and subtract the descendant set of every successor, then emit
    ``(u, v)`` for each surviving ``v`` in Python-set iteration order. Using real
    Python sets over a successor snapshot reproduces nx's edge order byte-for-byte.
    """
    nodes = list(G.nodes())
    succ = {u: list(G.successors(u)) for u in nodes}

    # in-degree (== dict(G.in_degree) for a simple DiGraph)
    check_count = dict.fromkeys(nodes, 0)
    for u in nodes:
        for v in succ[u]:
            check_count[v] += 1

    def _descendants(v):
        # set of nodes reachable from v (excludes v on a DAG) — order-independent,
        # matches ``{y for x, y in nx.dfs_edges(G, v)}``.
        seen = set()
        stack = list(succ[v])
        while stack:
            x = stack.pop()
            if x not in seen:
                seen.add(x)
                stack.extend(succ[x])
        seen.discard(v)
        return seen

    R = DiGraph()
    R.add_nodes_from(nodes)
    descendants = {}
    for u in nodes:
        u_nbrs = set(succ[u])
        for v in succ[u]:
            if v in u_nbrs:
                if v not in descendants:
                    descendants[v] = _descendants(v)
                u_nbrs -= descendants[v]
            check_count[v] -= 1
            if check_count[v] == 0:
                descendants.pop(v, None)
        R.add_edges_from([(u, v) for v in u_nbrs])
    return R


def degree_histogram(G):
    """Returns a list of the frequency of each degree value."""
    # br-r37-c1-deghistdead: the native kernel existed, was exported, was
    # imported here as `_raw_degree_histogram` - and was never called. The
    # Python body below built a `Counter` over N `(node, degree)` tuples
    # instead, which is what networkx does, so the port was paying nx's
    # algorithm to match nx's answer. Measured on a 1200-node/4800-edge Graph,
    # release build, live networkx 3.6.1 in the same invocation, min of 9:
    #
    #     python body   124.2 us      networkx   158.3 us     1.27x
    #     native kernel   1.7 us                             95.17x
    #
    # THE GUARD IS THE WHOLE DESIGN, because the kernel reads the Rust store
    # directly and two shapes make that the wrong store to read:
    #
    #   * a VIEW subclasses the native class, so the kernel accepts it and its
    #     Rust base is EMPTY - measured, it returns [] where networkx returns
    #     [3, 6, 1] (br-r37-c1-kum9v is this failure for the other native fast
    #     paths). Type IDENTITY excludes it; `isinstance` would not.
    #   * a graph carrying ASSIGNED private storage answers from that mapping,
    #     not from the Rust store.
    #
    # A networkx graph passed in raises TypeError from the kernel, so it must
    # not reach it either; the type check covers that too.
    #
    # WIRING IT AS A DROP-IN COST 53 TEST FAILURES FIRST, and that is why the
    # kernel now answers `None` for the classes it cannot serve. It computed a
    # SIMPLE-graph histogram, so it disagreed wherever degree is not the
    # neighbour count:
    #
    #     Graph a-a, a-b        nx [0,1,0,1]   kernel [0,1,1]   self-loop is 2
    #     MultiGraph a-b x2     nx [0,1,1,1]   kernel [0,2,1]   multiplicity
    #     MultiDiGraph a-b x2   nx [0,0,2]     kernel [0,2]
    #
    # The self-loop half is fixed in the kernel; the multiplicity and
    # directed-reciprocal halves are not reachable from the undirected
    # projection it reads, so the binding restricts itself to undirected simple
    # graphs and returns None otherwise. `None` - not an exception and not a
    # guess - is what lets this stay a pure fast path.
    if type(G) is Graph and not _has_networkx_private_storage(G):
        native = _raw_degree_histogram(G)
        if native is not None:
            return native
    degree_view = G.degree
    if callable(degree_view):
        degree_view = degree_view()
    counts = _Counter(degree for _node, degree in degree_view)
    return [counts.get(i, 0) for i in range(max(counts) + 1 if counts else 0)]

def _adc_iter_nodes(G, nodes):
    if nodes is None:
        return list(G.nodes())
    try:
        if nodes in G:
            return [nodes]
    except TypeError:
        pass
    try:
        return [node for node in nodes if node in G]
    except TypeError:
        return []


def _adc_weighted_degree(G, node, *, incoming=False, outgoing=False, weight=None):
    if not incoming and not outgoing:
        incoming = True
        outgoing = True

    def edge_total(edge_data):
        if weight is None:
            if G.is_multigraph():
                return len(edge_data)
            return 1
        if G.is_multigraph():
            return sum(attrs.get(weight, 1) for attrs in edge_data.values())
        return edge_data.get(weight, 1)

    total = 0
    if outgoing:
        for nbr, edge_data in G[node].items():
            contribution = edge_total(edge_data)
            if not G.is_directed() and nbr == node:
                contribution *= 2
            total += contribution
    if incoming and G.is_directed():
        for nbr in G.predecessors(node):
            total += edge_total(G[nbr][node])
    return total
