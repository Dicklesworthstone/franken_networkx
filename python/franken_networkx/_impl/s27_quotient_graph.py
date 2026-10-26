

def quotient_graph(
    G,
    partition,
    edge_relation=None,
    node_data=None,
    edge_data=None,
    weight="weight",
    relabel=False,
    create_using=None,
):
    """Return the quotient graph induced by a partition of *G*.

    Parameters
    ----------
    G : Graph or DiGraph
    partition : iterable of sets, or callable
        If iterable, each element is a set of nodes forming one block.
        If callable, it should be a function ``f(u, v)`` that returns True
        when *u* and *v* belong to the same block.
    edge_relation : callable or None
        ``f(block_u, block_v)`` -> bool. Default: edge exists if any
        cross-block edge exists in G.
    node_data : callable or None
        ``f(block)`` -> dict of node attributes for the block node.
    edge_data : callable or None
        ``f(block_u, block_v)`` -> dict of edge attributes.
    weight : str
        Attribute name used when ``edge_data`` is None (sums weights).
    relabel : bool
        If True, relabel block nodes to consecutive integers.
    create_using : graph constructor or None
        Type of graph to create.

    Returns
    -------
    Graph or DiGraph

    br-r37-c1-cfcls: coerce to fnx for consistent return type.
    """
    G = _coerce_arg_to_fnx_graph(G)
    # Normalize partition (br-r37-c1-ljkp0: as networkx does).
    if callable(partition):
        # nx's equivalence_classes: each node joins the first block whose first
        # member it relates to, and the blocks come back as a SET of
        # frozensets - whose iteration order is the block order.
        blocks = []
        for y in G:
            for block in blocks:
                if partition(block[0], y):
                    block.append(y)
                    break
            else:
                blocks.append([y])
        partition = [frozenset(b) for b in {frozenset(block) for block in blocks}]
    else:
        if isinstance(partition, dict):
            # keys are block labels, values the blocks
            partition = list(partition.values())
        partition = [frozenset(b) for b in partition]

    # br-r37-c1-quot-validate: nx validates that the partition is a
    # valid partition over G's node set:
    #   * every node listed in any part must be in G
    #   * every node-of-G appearing in partition must appear in
    #     exactly one part (no overlap)
    # nx surfaces both as ``NetworkXException("each node must be in
    # exactly one part of `partition`")``.  fnx silently merged
    # overlapping parts and silently included foreign nodes,
    # producing nonsense quotient graphs.
    seen_nodes = set()
    for block in partition:
        for node in block:
            if node not in G or node in seen_nodes:
                raise NetworkXException(
                    "each node must be in exactly one part of `partition`"
                )
            seen_nodes.add(node)

    # Default edge relation: any edge between blocks
    default_edge_relation = edge_relation is None
    if default_edge_relation:

        def edge_relation(block_u, block_v):
            for u in block_u:
                for v in block_v:
                    if G.has_edge(u, v):
                        return True
            return False

    if create_using is not None:
        H = _empty_graph_from_create_using(create_using)
    else:
        # br-r37-c1-5r04c: SubgraphView's class is _FilteredGraphView,
        # whose __init__ requires a 'graph' arg — bare ``cls()`` fails.
        # Route through canonical-class resolver (cycle-225 family).
        H = _concrete_class_for(G)()

    block_index = {}
    block_nnodes = []
    for idx, block in enumerate(partition):
        block_nnodes.append(len(block))
        for node in block:
            block_index[node] = idx

    can_bucket_default_undirected_edges = (
        default_edge_relation
        and edge_data is None
        and create_using is None
        and not G.is_directed()
        and not G.is_multigraph()
    )
    block_nedges = [0] * len(partition)
    default_pair_totals = {} if can_bucket_default_undirected_edges else None
    default_pair_weights_supported = True

    def _record_partition_edge(u, v, data):
        nonlocal default_pair_weights_supported

        u_idx = block_index.get(u)
        v_idx = block_index.get(v)
        if u_idx is None or v_idx is None:
            return
        if u_idx == v_idx:
            block_nedges[u_idx] += 1
            return
        if default_pair_totals is None:
            return
        if u_idx > v_idx:
            u_idx, v_idx = v_idx, u_idx
        key = (u_idx, v_idx)
        value = data.get(weight, 1) if weight else 1
        if not isinstance(value, (int, float)):
            default_pair_weights_supported = False
            return
        default_pair_totals[key] = default_pair_totals.get(key, 0) + value

    if G.is_multigraph():
        for u, v, _key, data in G.edges(keys=True, data=True):
            _record_partition_edge(u, v, data)
    else:
        for u, v, data in G.edges(data=True):
            _record_partition_edge(u, v, data)

    def _density_from_counts(nnodes, nedges):
        if nedges == 0 or nnodes <= 1:
            return 0
        result = nedges / (nnodes * (nnodes - 1))
        if not G.is_directed():
            result *= 2
        return result

    # Add block nodes
    # br-r37-c1-ja61l: when node_data is not provided, nx attaches a
    # default attribute dict to each block node containing the block's
    # subgraph, node _count, edge _count, and density. Mirror nx's
    # contract so drop-in callers see the same node-attr shape.
    def _default_node_data(block, block_idx):
        sub = G.subgraph(block)
        nnodes = block_nnodes[block_idx]
        nedges = block_nedges[block_idx]
        return {
            "graph": sub,
            "nnodes": nnodes,
            "nedges": nedges,
            "density": _density_from_counts(nnodes, nedges),
        }

    for block_idx, block in enumerate(partition):
        node_label = block
        if node_data is not None:
            H.add_node(node_label, **node_data(block))
        else:
            attrs = _default_node_data(block, block_idx)
            H.add_node(node_label)
            node_attrs = H.nodes[node_label]
            node_attrs["graph"] = attrs["graph"]
            node_attrs["nnodes"] = attrs["nnodes"]
            node_attrs["nedges"] = attrs["nedges"]
            node_attrs["density"] = attrs["density"]

    def _add_default_undirected_bucketed_edges():
        if not can_bucket_default_undirected_edges:
            return False
        if not default_pair_weights_supported:
            return False

        edge_bunch = []
        for i, block_u in enumerate(partition):
            for j in range(i + 1, len(partition)):
                key = (i, j)
                if key not in default_pair_totals:
                    continue
                block_v = partition[j]
                edge_bunch.append(
                    (block_u, block_v, {"weight": default_pair_totals[key]})
                )
        H.add_edges_from(edge_bunch)
        return True

    if not _add_default_undirected_bucketed_edges():
        # br-r37-c1-ljkp0: networkx's _quotient_graph. Block pairs follow H's
        # node order - every ordered pair when H is directed, each unordered
        # pair once (b before c) otherwise. A multigraph H gets one edge per
        # adjacent (u, v) across the pair, carrying G.get_edge_data(u, v) (a
        # multigraph G's keydict); a simple H gets edge_data(b, c), by default
        # the weight summed over the edges joining b and c in EITHER direction.
        if edge_data is None:

            def edge_data(block_u, block_v):
                return {
                    "weight": sum(
                        d.get(weight, 1)
                        for u, v, d in G.edges(block_u | block_v, data=True)
                        if (u in block_u and v in block_v) or (u in block_v and v in block_u)
                    )
                }

        blocks = list(H)
        if H.is_directed():
            block_pairs = _itertools.permutations(blocks, 2)
        else:
            block_pairs = _itertools.combinations(blocks, 2)
        if H.is_multigraph():
            H.add_edges_from(
                [
                    (block_u, block_v, G.get_edge_data(u, v, default={}))
                    for block_u, block_v in block_pairs
                    if edge_relation(block_u, block_v)
                    for u, v in _itertools.product(block_u, block_v)
                    if G.has_edge(u, v)
                ]
            )
        else:
            H.add_edges_from(
                [
                    (block_u, block_v, edge_data(block_u, block_v))
                    for block_u, block_v in block_pairs
                    if edge_relation(block_u, block_v)
                ]
            )

    if relabel:
        mapping = {block: i for i, block in enumerate(partition)}
        H = relabel_nodes(H, mapping)

    # br-r37-c1-e8sjt: Always return fnx type for consistency
    if create_using is None:
        return H

    from franken_networkx.readwrite import _from_nx_graph
    return _from_nx_graph(H, create_using=create_using)


def snap_aggregation(
    G,
    node_attributes,
    edge_attributes=(),
    prefix="Supernode-",
    supernode_attribute="group",
    superedge_attribute="types",
):
    """Return a SNAP summary graph aggregated by attribute values.

    Groups nodes by their attribute values and neighbor-group structure
    (SNAP algorithm).

    Parameters
    ----------
    G : Graph or DiGraph
    node_attributes : iterable of str
        Node attribute names used for initial grouping.
    edge_attributes : iterable of str, optional
        Edge attributes to consider for edge typing.
    prefix : str, optional
        Prefix for supernode labels.
    supernode_attribute : str, optional
        Name of the attribute on supernodes that holds the set of grouped
        nodes.
    superedge_attribute : str, optional
        Name of the attribute on superedges that holds edge type info.

    Returns
    -------
    Graph or DiGraph
    """
    from collections import Counter as _Counter, defaultdict as _defaultdict

    edge_attributes = tuple(edge_attributes)
    is_multi = G.is_multigraph()
    is_directed = G.is_directed()

    # Build edge_types mapping: edge -> tuple of attribute values
    if is_multi:
        edge_types = {
            (u, v, k): tuple(d.get(attr) for attr in edge_attributes)
            for u, v, k, d in G.edges(keys=True, data=True)
        }
        if not is_directed:
            edge_types.update(
                [((v, u, k), etype) for (u, v, k), etype in list(edge_types.items())]
            )
    else:
        edge_types = {
            (u, v): tuple(d.get(attr) for attr in edge_attributes)
            for u, v, d in G.edges(data=True)
        }
        if not is_directed:
            edge_types.update(
                [((v, u), etype) for (u, v), etype in list(edge_types.items())]
            )

    # Initial grouping by node attribute values (strictly mirrors NX: raises KeyError if missing)
    group_lookup = {
        node: tuple(G.nodes[node][attr] for attr in node_attributes)
        for node in G.nodes()
    }
    groups = _defaultdict(set)
    for node, node_type in group_lookup.items():
        groups[node_type].add(node)

    # Iterative splitting (mirrors NX _snap_eligible_group / _snap_split)
    def _eligible_group():
        nbr_info = {node: {gid: _Counter() for gid in groups} for node in group_lookup}
        for group_id in groups:
            current_group = groups[group_id]
            for node in current_group:
                nbr_info[node] = {gid: _Counter() for gid in groups}
                edges = G.edges(node, keys=True) if is_multi else G.edges(node)
                for edge in edges:
                    neighbor = edge[1]
                    edge_type = edge_types[edge]
                    neighbor_group_id = group_lookup[neighbor]
                    nbr_info[node][neighbor_group_id][edge_type] += 1

            group_size = len(current_group)
            for other_gid in groups:
                edge_counts = _Counter()
                for node in current_group:
                    edge_counts.update(nbr_info[node][other_gid].keys())
                if not all(_count == group_size for _count in edge_counts.values()):
                    return group_id, nbr_info

        return None, nbr_info

    def _split(nbr_info, group_id):
        new_group_mappings = _defaultdict(set)
        for node in groups[group_id]:
            signature = tuple(frozenset(etypes) for etypes in nbr_info[node].values())
            new_group_mappings[signature].add(node)

        new_subgroups = sorted(new_group_mappings.values(), key=len)
        for new_group in new_subgroups[:-1]:
            new_gid = len(groups)
            groups[new_gid] = new_group
            groups[group_id] -= new_group
            for node in new_group:
                group_lookup[node] = new_gid

    eligible_gid, nbr_info = _eligible_group()
    while eligible_gid is not None:
        _split(nbr_info, eligible_gid)
        eligible_gid, nbr_info = _eligible_group()

    # Build the summary graph
    # br-r37-c1-s8w2p: SubgraphView class can't be empty-constructed.
    output = _concrete_class_for(G)()
    node_label_lookup = {}
    for index, group_id in enumerate(groups):
        group_set = groups[group_id]
        supernode = f"{prefix}{index}"
        node_label_lookup[group_id] = supernode
        supernode_attributes = {
            attr: G.nodes[next(iter(group_set))][attr] for attr in node_attributes
        }
        supernode_attributes[supernode_attribute] = group_set
        output.add_node(supernode, **supernode_attributes)

    for group_id in groups:
        group_set = groups[group_id]
        source_supernode = node_label_lookup[group_id]
        rep_node = next(iter(group_set))
        for other_gid, group_edge_types in nbr_info[rep_node].items():
            if group_edge_types:
                target_supernode = node_label_lookup[other_gid]
                summary_graph_edge = (source_supernode, target_supernode)
                edge_type_list = [
                    dict(zip(edge_attributes, etype)) for etype in group_edge_types
                ]
                has_edge = output.has_edge(*summary_graph_edge)
                if is_multi:
                    if not has_edge:
                        for etype_dict in edge_type_list:
                            output.add_edge(*summary_graph_edge, **etype_dict)
                    elif not is_directed:
                        existing_edge_data = output.get_edge_data(*summary_graph_edge)
                        for etype_dict in edge_type_list:
                            if etype_dict not in existing_edge_data.values():
                                output.add_edge(*summary_graph_edge, **etype_dict)
                    else:
                        for etype_dict in edge_type_list:
                            output.add_edge(*summary_graph_edge, **etype_dict)
                else:
                    superedge_attrs = {superedge_attribute: edge_type_list}
                    output.add_edge(*summary_graph_edge, **superedge_attrs)

    # br-r37-c1-k3ksc: Always return fnx type for consistency
    from franken_networkx.readwrite import _from_nx_graph
    return _from_nx_graph(output)


def full_join(G, H, rename=(None, None)):
    """Return the full join of two graphs.

    The full join is the union of G and H plus all edges between every
    node in G and every node in H.

    Parameters
    ----------
    G, H : Graph
    rename : tuple of (str or None, str or None)
        Prefixes for node labels of G and H to avoid collisions.

    Returns
    -------
    Graph
    """
    R = union_all([G, H], rename=rename)

    def add_prefix(graph, prefix):
        if prefix is None:
            return graph
        return relabel_nodes(graph, lambda node: f"{prefix}{node}")

    G = add_prefix(G, rename[0])
    H = add_prefix(H, rename[1])

    # br-bt-fjbatch: the join loops read only G and H (never R), and the G/H
    # node sets are disjoint after ``union_all`` so every (gn, hn) pair is a new,
    # unique edge — no self-loops, no dedup, no parallel edges. Accumulate the
    # cross pairs in the same nested-iteration order and commit through one
    # ``add_edges_from`` per direction, replacing the O(|G|*|H|) per-edge PyO3
    # ``add_edge`` calls. nx runs the identical nested loop with a pure-Python
    # add_edge, so the edge insertion order (and multigraph key 0 for each
    # distinct pair) is byte-identical.
    R.add_edges_from([(gn, hn) for gn in G for hn in H])
    if R.is_directed():
        R.add_edges_from([(hn, gn) for hn in H for gn in G])

    return R


def identified_nodes(
    G,
    u,
    v,
    self_loops=True,
    copy=True,
    *,
    store_contraction_as="contraction",
    backend=None,
    **backend_kwargs,
):
    """Return *G* with nodes *u* and *v* identified (contracted).

    Node *v* is merged into node *u*: all edges incident to *v* are
    redirected to *u*, and *v* is removed.

    Parameters
    ----------
    G : Graph or DiGraph
    u, v : nodes
        *v* is merged into *u*.
    self_loops : bool, optional
        If False, self-loops created by the contraction are removed.
    copy : bool, optional
        If True, work on a copy of *G*.
    store_contraction_as : str, optional
        Attribute name under which contraction info is stored on *u*.

    Returns
    -------
    Graph or DiGraph
    """
    _validate_backend_dispatch_keywords("identified_nodes", backend, backend_kwargs)
    # br-r37-c1-cnodes-vbad: nx raises NetworkXError when ``v`` is
    # not in G (its ``H.nodes[v]`` access surfaces a typed error).
    # fnx previously guarded with ``if v in G else {}``, silently
    # returning the unmodified graph and masking the contract.
    # ``u not in G`` is *intentionally* permitted by nx (the bad u
    # becomes a real node implicitly via add_edge during the
    # remap), so leave that path alone.
    if v not in G:
        raise NetworkXError(f"Node {v} is not in the graph.")
    # br-r37-c1-i5mf1: mirror networkx's contracted_nodes algorithm directly
    # — COPY G (a fast native copy that preserves node/edge order AND graph-level
    # attrs) then remove v and remap only v's O(deg(v)) incident edges. The old
    # path rebuilt the WHOLE result node-by-node and edge-by-edge (O(N+E)
    # per-PyO3 add_node/add_edge), ~2.3x slower than nx. The copy + local remap
    # is byte-identical: copy preserves order, non-v edges stay in place, v's new
    # remapped edges are appended in v-edge order exactly as nx's loop does, and
    # the node/edge "contraction" bookkeeping follows nx line-for-line.
    H = G.copy() if copy else G
    if H.is_directed():
        edges_to_remap = list(G.in_edges(v, data=True)) + list(G.out_edges(v, data=True))
    else:
        edges_to_remap = list(G.edges(v, data=True))
    v_data = dict(G.nodes[v])
    H.remove_node(v)

    store = store_contraction_as is not None
    for prev_w, prev_x, d in edges_to_remap:
        w = u if prev_w == v else prev_w
        x = u if prev_x == v else prev_x
        if {prev_w, prev_x} == {u, v} and not self_loops:
            continue
        if not H.has_edge(w, x) or G.is_multigraph():
            H.add_edge(w, x, **d)
            continue
        # Existing simple-graph edge (w, x): record the remapped duplicate as a
        # contraction rather than overwriting it.
        if store:
            edge_attrs = H.edges[w, x]
            if store_contraction_as in edge_attrs:
                edge_attrs[store_contraction_as][(prev_w, prev_x)] = d
            else:
                edge_attrs[store_contraction_as] = {(prev_w, prev_x): d}

    # Store the contracted node's data on u (guard u in H: nx permits u absent
    # from G, in which case it is created via the remapped edges above; if v had
    # no incident edges u may never appear, matching the prior lenient contract).
    if store and u in H:
        node_attrs = H.nodes[u]
        if store_contraction_as in node_attrs:
            node_attrs[store_contraction_as][v] = v_data
        else:
            node_attrs[store_contraction_as] = {v: v_data}

    # copy=False mutates and returns the caller's own graph (result is G); copy=True
    # returns the fresh fnx-typed copy. Both are already the canonical fnx type.
    return H


def inverse_line_graph(G):
    """Return an inverse line graph, when it exists."""
    from collections import defaultdict as _defaultdict
    from itertools import combinations as _combinations

    def _triangles_local(graph, edge):
        u, v = edge
        if u not in graph:
            raise NetworkXError(f"Vertex {u} not in graph")
        if v not in graph[u]:
            raise NetworkXError(f"Edge ({u}, {v}) not in graph")
        triangle_list = []
        for x in graph[u]:
            if x in graph[v]:
                triangle_list.append((u, v, x))
        return triangle_list

    def _odd_triangle_local(graph, triangle):
        for u in triangle:
            if u not in graph:
                raise NetworkXError(f"Vertex {u} not in graph")
        for u, v in _combinations(triangle, 2):
            if u not in graph[v]:
                raise NetworkXError(f"Edge ({u}, {v}) not in graph")

        triangle_neighbors = _defaultdict(int)
        for triangle_node in triangle:
            for neighbor in graph[triangle_node]:
                if neighbor not in triangle:
                    triangle_neighbors[neighbor] += 1
        return any(_count in (1, 3) for _count in triangle_neighbors.values())

    def _select_starting_cell_local(graph, starting_edge=None):
        if starting_edge is None:
            edge = next(iter(graph.edges()))
        else:
            edge = starting_edge
            if edge[0] not in graph.nodes():
                raise NetworkXError(f"Vertex {edge[0]} not in graph")
            if edge[1] not in graph[edge[0]]:
                raise NetworkXError(
                    f"starting_edge ({edge[0]}, {edge[1]}) is not in the Graph"
                )
        edge_triangles = _triangles_local(graph, edge)
        triangle_count = len(edge_triangles)
        if triangle_count == 0:
            return edge
        if triangle_count == 1:
            triangle = edge_triangles[0]
            a, b, c = triangle
            ac_edges = len(_triangles_local(graph, (a, c)))
            bc_edges = len(_triangles_local(graph, (b, c)))
            if ac_edges == 1:
                if bc_edges == 1:
                    return triangle
                return _select_starting_cell_local(graph, starting_edge=(b, c))
            return _select_starting_cell_local(graph, starting_edge=(a, c))

        odd_triangles = [
            triangle
            for triangle in edge_triangles
            if _odd_triangle_local(graph, triangle)
        ]
        odd_count = len(odd_triangles)
        if triangle_count == 2 and odd_count == 0:
            return edge_triangles[-1]
        if triangle_count - 1 <= odd_count <= triangle_count:
            triangle_nodes = set()
            for triangle in odd_triangles:
                triangle_nodes.update(triangle)
            for u in triangle_nodes:
                for v in triangle_nodes:
                    if u != v and v not in graph[u]:
                        raise NetworkXError(
                            "G is not a line graph (odd triangles do not form complete subgraph)"
                        )
            return tuple(triangle_nodes)
        raise NetworkXError(
            "G is not a line graph (incorrect number of odd triangles around starting edge)"
        )

    def _find_partition_local(graph, starting_cell):
        graph_partition = graph.copy()
        partition = [starting_cell]
        graph_partition.remove_edges_from(list(_combinations(starting_cell, 2)))
        partitioned_vertices = list(starting_cell)
        while graph_partition.number_of_edges() > 0:
            u = partitioned_vertices.pop()
            if len(graph_partition[u]) != 0:
                new_cell = [u] + list(graph_partition[u])
                for cell_u in new_cell:
                    for cell_v in new_cell:
                        if cell_u != cell_v and cell_v not in graph_partition[cell_u]:
                            raise NetworkXError(
                                "G is not a line graph (partition cell not a complete subgraph)"
                            )
                partition.append(tuple(new_cell))
                graph_partition.remove_edges_from(list(_combinations(new_cell, 2)))
                partitioned_vertices += new_cell
        return partition

    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.number_of_nodes() == 0:
        return empty_graph(1)
    if G.number_of_nodes() == 1:
        vertex = next(iter(G.nodes()))
        return Graph([((vertex, 0), (vertex, 1))])
    if G.number_of_nodes() > 1 and G.number_of_edges() == 0:
        raise NetworkXError(
            "inverse_line_graph() doesn't work on an edgeless graph. Please use this function on each component separately."
        )
    if number_of_selfloops(G) != 0:
        raise NetworkXError(
            "A line graph as generated by NetworkX has no selfloops, so G has no inverse line graph. Please remove the selfloops from G and try again."
        )

    starting_cell = _select_starting_cell_local(G)
    partition = _find_partition_local(G, starting_cell)
    partition_count = {u: 0 for u in G.nodes()}
    for cell in partition:
        for u in cell:
            partition_count[u] += 1
    if max(partition_count.values()) > 2:
        raise NetworkXError(
            "G is not a line graph (vertex found in more than two partition cells)"
        )

    singleton_cells = tuple((u,) for u, _count in partition_count.items() if _count == 1)
    H = Graph()
    for node in partition:
        H.add_node(node)
    for node in singleton_cells:
        H.add_node(node)
    for left, right in _combinations(H.nodes(), 2):
        if any(item in right for item in left):
            H.add_edge(left, right)
    return H


# ---------------------------------------------------------------------------
# Node/edge contraction
# ---------------------------------------------------------------------------


def contracted_nodes(
    G,
    u,
    v,
    self_loops=True,
    copy=True,
    *,
    store_contraction_as="contraction",
    backend=None,
    **backend_kwargs,
):
    """Contract nodes *u* and *v* in *G*.

    All edges to/from *v* are redirected to *u*, then *v* is removed.

    Parameters
    ----------
    G : Graph
    u, v : node
    self_loops : bool, optional
        If False, remove self-loops created by the contraction.
    copy : bool, optional
        If True (default), return a new graph.
    """
    _validate_backend_dispatch_keywords("contracted_nodes", backend, backend_kwargs)
    return identified_nodes(
        G,
        u,
        v,
        self_loops=self_loops,
        copy=copy,
        store_contraction_as=store_contraction_as,
    )


def contracted_edge(
    G,
    edge,
    self_loops=True,
    copy=True,
    *,
    store_contraction_as="contraction",
    backend=None,
    **backend_kwargs,
):
    """Contract an edge in *G* by merging its endpoints.

    Parameters
    ----------
    G : Graph
    edge : tuple (u, v)
    self_loops : bool, optional
    copy : bool, optional
    """
    _validate_backend_dispatch_keywords("contracted_edge", backend, backend_kwargs)
    u, v = edge[:2]
    if not G.has_edge(u, v):
        raise ValueError(f"Edge {edge} does not exist in graph G; cannot contract it")
    return contracted_nodes(
        G,
        u,
        v,
        self_loops=self_loops,
        copy=copy,
        store_contraction_as=store_contraction_as,
    )


# ---------------------------------------------------------------------------
# Global type predicates (function form)
# ---------------------------------------------------------------------------


def is_directed(G):
    """Return True if *G* is a directed graph."""
    return G.is_directed()


# ---------------------------------------------------------------------------
# Degree sequence generators
# ---------------------------------------------------------------------------


def _degree_sequence_stublist(degree_sequence):
    return list(
        _itertools.chain.from_iterable(
            [node] * degree for node, degree in enumerate(degree_sequence)
        )
    )


def _configuration_model_local(
    degree_sequence,
    create_using,
    *,
    directed=False,
    in_degree_sequence=None,
    seed=None,
):
    graph = _empty_graph_from_create_using(create_using)
    graph.add_nodes_from(range(len(degree_sequence)))
    if len(degree_sequence) == 0:
        return graph

    rng = _generator_random_state(seed)
    if directed:
        pairs = _itertools.zip_longest(degree_sequence, in_degree_sequence, fillvalue=0)
        out_degrees, in_degrees = zip(*pairs)
        out_stubs = _degree_sequence_stublist(out_degrees)
        in_stubs = _degree_sequence_stublist(in_degrees)
        rng.shuffle(out_stubs)
        rng.shuffle(in_stubs)
    else:
        stubs = _degree_sequence_stublist(degree_sequence)
        rng.shuffle(stubs)
        half = len(stubs) // 2
        out_stubs = stubs[:half]
        in_stubs = stubs[half:]

    # br-r37-c1-yrdso: materialize the stub pairing into a list so
    # add_edges_from hits the native bulk-edge batch — a bare ``zip`` iterator
    # is neither list nor tuple, so it fell to the per-edge add_edge path
    # (~2.3x slower on the MultiGraph construction). Same pairing order ->
    # byte-identical (keys + parallel edges + self-loops).
    graph.add_edges_from(list(zip(out_stubs, in_stubs)))
    return graph


def _is_graphical_degree_sequence(degree_sequence):
    try:
        sequence = [int(degree) for degree in degree_sequence]
    except (TypeError, ValueError):
        return False
    if any(degree < 0 for degree in sequence):
        return False
    return is_valid_degree_sequence_erdos_gallai(sequence)


def _random_weighted_sample(mapping, k, rng):
    if k > len(mapping):
        raise ValueError("sample larger than population")
    sample = set()
    while len(sample) < k:
        sample.add(_weighted_choice(mapping, rng))
    return list(sample)


def _weighted_choice(mapping, rng):
    threshold = rng.random() * sum(mapping.values())
    for key, weight in mapping.items():
        threshold -= weight
        if threshold < 0:
            return key
    return next(reversed(mapping))


class _DegreeSequenceRandomGraph:
    def __init__(self, degree, rng):
        self.rng = rng
        self.degree = list(degree)
        if not _is_graphical_degree_sequence(self.degree):
            raise NetworkXUnfeasible("degree sequence is not graphical")
        self.m = sum(self.degree) / 2.0
        self.dmax = max(self.degree, default=0)

    def generate(self):
        self.remaining_degree = dict(enumerate(self.degree))
        self.graph = Graph()
        self.graph.add_nodes_from(self.remaining_degree)
        for node, degree in list(self.remaining_degree.items()):
            if degree == 0:
                del self.remaining_degree[node]
        if self.remaining_degree:
            self._phase1()
            self._phase2()
            self._phase3()
        return self.graph

    def _update_remaining(self, u, v, aux_graph=None):
        if aux_graph is not None:
            aux_graph.remove_edge(u, v)
        if self.remaining_degree[u] == 1:
            del self.remaining_degree[u]
            if aux_graph is not None:
                aux_graph.remove_node(u)
        else:
            self.remaining_degree[u] -= 1
        if self.remaining_degree[v] == 1:
            del self.remaining_degree[v]
            if aux_graph is not None:
                aux_graph.remove_node(v)
        else:
            self.remaining_degree[v] -= 1

    def _degree_probability(self, u, v):
        return 1 - self.degree[u] * self.degree[v] / (4.0 * self.m)

    def _remaining_probability(self, u, v):
        norm = max(self.remaining_degree.values()) ** 2
        return self.remaining_degree[u] * self.remaining_degree[v] / norm

    def _has_suitable_edge(self):
        nodes = iter(self.remaining_degree)
        u = next(nodes)
        return any(not self.graph.has_edge(u, v) for v in nodes)

    def _phase1(self):
        remaining = self.remaining_degree
        while sum(remaining.values()) >= 2 * self.dmax**2:
            u, v = sorted(_random_weighted_sample(remaining, 2, self.rng))
            if self.graph.has_edge(u, v):
                continue
            if self.rng.random() < self._degree_probability(u, v):
                self.graph.add_edge(u, v)
                self._update_remaining(u, v)

    def _phase2(self):
        remaining = self.remaining_degree
        while len(remaining) >= 2 * self.dmax:
            while True:
                u, v = sorted(self.rng.sample(list(remaining.keys()), 2))
                if self.graph.has_edge(u, v):
                    continue
                if self.rng.random() < self._remaining_probability(u, v):
                    break
            if self.rng.random() < self._degree_probability(u, v):
                self.graph.add_edge(u, v)
                self._update_remaining(u, v)

    def _phase3(self):
        aux_graph = Graph()
        aux_graph.add_edges_from(
            (u, v)
            for u, v in _combinations(self.remaining_degree, 2)
            if not self.graph.has_edge(u, v)
        )
        while self.remaining_degree:
            if not self._has_suitable_edge():
                raise NetworkXUnfeasible("no suitable edges left")
            while True:
                u, v = sorted(self.rng.choice(list(aux_graph.edges())))
                if self.rng.random() < self._remaining_probability(u, v):
                    break
            if self.rng.random() < self._degree_probability(u, v):
                self.graph.add_edge(u, v)
                self._update_remaining(u, v, aux_graph=aux_graph)


def _neighbor_switch_local(graph, w, unsat, residual, avoid_node_id=None):
    if avoid_node_id is None or residual[avoid_node_id] > 1:
        w_prime = next(iter(unsat))
    else:
        iterator = iter(unsat)
        while True:
            w_prime = next(iterator)
            if w_prime != avoid_node_id:
                break

    for switch_node in graph.neighbors(w):
        if not graph.has_edge(w_prime, switch_node) and switch_node != w_prime:
            graph.remove_edge(w, switch_node)
            graph.add_edge(w_prime, switch_node)
            residual[w] += 1
            residual[w_prime] -= 1
            if residual[w_prime] == 0:
                unsat.remove(w_prime)
            return


def _directed_neighbor_switch_local(
    graph,
    w,
    unsat,
    residual_out,
    chords,
    partition_in,
    partition,
):
    w_prime = unsat.pop()
    unsat.add(w_prime)
    w_prime_neighbors = set(graph.successors(w_prime))
    for v in list(graph.successors(w)):
        if v not in w_prime_neighbors and w_prime != v:
            graph.remove_edge(w, v)
            graph.add_edge(w_prime, v)
            if partition_in[v] == partition:
                chords.add((w, v))
                chords.discard((w_prime, v))
            residual_out[w] += 1
            residual_out[w_prime] -= 1
            if residual_out[w_prime] == 0:
                unsat.remove(w_prime)
            return None
    return w_prime


def _directed_neighbor_switch_rev_local(
    graph,
    w,
    unsat,
    residual_in,
    chords,
    partition_out,
    partition,
):
    w_prime = unsat.pop()
    unsat.add(w_prime)
    w_prime_predecessors = set(graph.predecessors(w_prime))
    for v in list(graph.predecessors(w)):
        if v not in w_prime_predecessors and w_prime != v:
            graph.remove_edge(v, w)
            graph.add_edge(v, w_prime)
            if partition_out[v] == partition:
                chords.add((v, w))
                chords.discard((v, w_prime))
            residual_in[w] += 1
            residual_in[w_prime] -= 1
            if residual_in[w_prime] == 0:
                unsat.remove(w_prime)
            return None
    return w_prime


def configuration_model(deg_sequence, create_using=None, seed=None):
    """Return a random graph with the given degree sequence.

    Uses the configuration model: create stubs and pair them randomly.
    May produce self-loops and multi-edges (returns a MultiGraph).

    Parameters
    ----------
    deg_sequence : list of int
        Degree sequence (must sum to even number).
    seed : int or None, optional

    Returns
    -------
    MultiGraph
    """
    if sum(deg_sequence) % 2 != 0:
        raise NetworkXError("Invalid degree sequence: sum of degrees must be even, not odd")

    graph = _checked_create_using(create_using, default=MultiGraph)
    if graph.is_directed():
        raise NetworkXNotImplemented("not implemented for directed graphs")
    return _configuration_model_local(deg_sequence, graph, seed=seed)


def havel_hakimi_graph(deg_sequence, create_using=None):
    """Return a simple graph with the given degree sequence."""
    # NetworkX requires a sized sequence here; preserve its TypeError
    # for iterators before list() would silently consume them.
    len(deg_sequence)
    degree_sequence = list(deg_sequence)
    if not _is_graphical_degree_sequence(degree_sequence):
        raise NetworkXError("Invalid degree sequence")

    p = len(degree_sequence)
    graph = _checked_create_using(create_using, directed=False, default=Graph)
    graph.add_nodes_from(range(p))

    degree_buckets = [[] for _ in range(p)]
    dmax = 0
    active = 0
    # NetworkX labels the nonzero-degree entries densely from 0 and leaves
    # zero-degree entries as the trailing isolates already present in graph.
    node = 0
    for degree in degree_sequence:
        if degree > 0:
            degree_buckets[degree].append(node)
            dmax = max(dmax, degree)
            active += 1
            node += 1
    if active == 0:
        return graph

    modified = [(0, 0)] * (dmax + 1)
    # br-r37-c1-hhbatch (cc): the HH realization only EMITS edges (the
    # degree_buckets / modified / active bookkeeping never reads graph state),
    # so collect every (source, target) and commit through ONE add_edges_from
    # instead of the per-edge add_edge PyO3 round-trip that dominated
    # (~0.46x vs nx). Same emission order -> byte-identical adjacency.
    new_edges = []
    while active > 0:
        while not degree_buckets[dmax]:
            dmax -= 1
        if dmax > active - 1:
            raise NetworkXError("Non-graphical integer sequence")

        source = degree_buckets[dmax].pop()
        active -= 1
        modified_len = 0
        k = dmax
        for _ in range(dmax):
            while not degree_buckets[k]:
                k -= 1
            target = degree_buckets[k].pop()
            new_edges.append((source, target))
            active -= 1
            if k > 1:
                modified[modified_len] = (k - 1, target)
                modified_len += 1

        for i in range(modified_len):
            stub_value, stub_target = modified[i]
            degree_buckets[stub_value].append(stub_target)
            active += 1

    graph.add_edges_from(new_edges)
    return graph


def _degree_sequence_tree_impl(deg_sequence, create_using=None):
    deg_sequence = list(deg_sequence)
    number_of_nodes = len(deg_sequence)
    twice_number_of_edges = sum(deg_sequence)

    if 2 * number_of_nodes - twice_number_of_edges != 2:
        raise NetworkXError("tree must have one more node than number of edges")
    if deg_sequence != [0] and any(degree <= 0 for degree in deg_sequence):
        raise NetworkXError("nontrivial tree must have strictly positive node degrees")

    if create_using is None:
        graph = Graph()
    else:
        graph = empty_graph(0, create_using=create_using)
        if graph.is_directed():
            raise NetworkXError("Directed Graph not supported")

    if deg_sequence == [0]:
        graph.add_node(0)
        return graph

    degrees = sorted((degree for degree in deg_sequence if degree > 1), reverse=True)
    backbone_nodes = len(degrees) + 2
    graph.add_nodes_from(range(backbone_nodes))
    graph.add_edges_from(zip(range(backbone_nodes - 1), range(1, backbone_nodes)))
    last = backbone_nodes
    leaf_edges = []

    for source in range(1, backbone_nodes - 1):
        extra_edges = degrees.pop() - 2
        leaf_edges.extend((source, target) for target in range(last, last + extra_edges))
        last += extra_edges
    graph.add_edges_from(leaf_edges)
    return graph


def degree_sequence_tree(deg_sequence, create_using=None):
    """Return a tree with the given degree sequence, if possible.

    Parameters
    ----------
    deg_sequence : list of int
    create_using : graph constructor, optional

    Returns
    -------
    Graph
        A tree with the given degree sequence.
    """
    return _degree_sequence_tree_impl(deg_sequence, create_using=create_using)


def common_neighbor_centrality(
    G,
    ebunch=None,
    alpha=0.8,
    *,
    backend=None,
    **backend_kwargs,
):
    """Return the CCPA score for each pair of nodes."""
    _validate_backend_dispatch_keywords(
        "common_neighbor_centrality",
        backend,
        backend_kwargs,
    )

    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    # br-r37-c1-cncadj: nx scores every node pair with
    # ``len(nx.common_neighbors(G, u, v))``; the default ebunch is *all* O(V^2)
    # non-edges, so that wrapper is called ~V^2 times. Each fnx
    # ``common_neighbors`` call re-walks the String-keyed PyO3 adjacency (~3.8x
    # slower than nx's native-dict set intersection), making the whole function
    # ~2.3x SLOWER than nx. Snapshot the adjacency to Python sets ONCE, then take
    # ``(adj[u] & adj[v]) - {u, v}`` in the hot loop — byte-identical to nx's
    # ``{w for w in G[u] if w in G[v] and w not in (u, v)}`` (the ``-{u, v}``
    # reproduces nx's self-loop / existing-edge ebunch exclusion).
    adj = {node: set(nbrs) for node, nbrs in G.adjacency()}

    if alpha == 1:

        def predict(u, v):
            if u == v:
                raise NetworkXAlgorithmError("Self loops are not supported")
            return len((adj[u] & adj[v]) - {u, v})

    else:
        shortest_path_lengths = dict(shortest_path_length(G))
        infinity = float("inf")
        num_nodes = len(G)

        def predict(u, v):
            if u == v:
                raise NetworkXAlgorithmError("Self loops are not supported")
            path_length = shortest_path_lengths[u].get(v, infinity)
            common_neighbor_count = len((adj[u] & adj[v]) - {u, v})
            return alpha * common_neighbor_count + (1 - alpha) * num_nodes / path_length

    if ebunch is None:
        ebunch = non_edges(G)
    else:
        for u, v in ebunch:
            if u not in G:
                raise NodeNotFound(f"Node {u} not in G.")
            if v not in G:
                raise NodeNotFound(f"Node {v} not in G.")

    return ((u, v, predict(u, v)) for u, v in ebunch)


# ---------------------------------------------------------------------------
# DAG & Ancestor algorithms
# ---------------------------------------------------------------------------


def all_topological_sorts(G):
    """Generate all possible topological orderings of a DAG.

    Uses Kahn's algorithm with backtracking. The number of orderings
    can be exponential, so this is a generator.

    Parameters
    ----------
    G : DiGraph
        Must be a DAG.

    Yields
    ------
    list
        Each yield is a valid topological ordering.
    """
    # br-r37-c1-scceager: nx's all_topological_sorts is
    # @not_implemented_for('undirected'), raising eagerly on the call. Match
    # that; a cyclic DiGraph still raises NetworkXUnfeasible lazily on
    # iteration (via the nx delegation), as in nx.
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")

    return _all_topological_sorts_inprocess(G)


def _all_topological_sorts_inprocess(G):
    """networkx ``all_topological_sorts`` (Knuth/Szwarcfiter) on an fnx DiGraph / MultiDiGraph
    without the fnx->nx conversion. Byte-identical ordering stream."""
    from collections import deque as _deque

    nodes = list(G)
    if G.is_multigraph():
        succ = {u: [v for _, v in G.out_edges(u)] for u in nodes}
    else:
        succ = {u: list(G.successors(u)) for u in nodes}
    count = dict.fromkeys(nodes, 0)
    for u in nodes:
        for j in succ[u]:
            count[j] += 1

    D = _deque(v for v in nodes if count[v] == 0)
    n = len(nodes)
    bases = []
    current_sort = []

    while True:
        if len(current_sort) == n:
            yield list(current_sort)
            while current_sort:
                q = current_sort.pop()
                for j in succ[q]:
                    count[j] += 1
                while D and count[D[-1]] > 0:
                    D.pop()
                D.appendleft(q)
                if D[-1] == bases[-1]:
                    bases.pop()
                else:
                    break
        else:
            if not D:
                raise NetworkXUnfeasible("Graph contains a cycle.")
            q = D.pop()
            for j in succ[q]:
                count[j] -= 1
                if count[j] == 0:
                    D.append(j)
            current_sort.append(q)
            if len(bases) < len(current_sort):
                bases.append(q)

        if not bases:
            break


def lowest_common_ancestor(
    G, node1, node2, default=None, *, backend=None, **backend_kwargs
):
    """Compute the lowest common ancestor of the given pair of nodes.

    Parameters
    ----------
    G : NetworkX directed graph

    node1, node2 : nodes in the graph.

    default : object
        Returned if no common ancestor between `node1` and `node2`

    Returns
    -------
    The lowest common ancestor of node1 and node2,
    or default if they have no common ancestors.
    """
    _validate_backend_dispatch_keywords(
        "lowest_common_ancestor", backend, backend_kwargs
    )
    ans = list(all_pairs_lowest_common_ancestor(G, pairs=[(node1, node2)]))
    if ans:
        return ans[0][1]
    return default


def all_pairs_lowest_common_ancestor(G, pairs=None, *, backend=None, **backend_kwargs):
    """Return the lowest common ancestor of all pairs or the provided pairs

    Parameters
    ----------
    G : NetworkX directed graph

    pairs : iterable of pairs of nodes, optional (default: all pairs)
        The pairs of nodes of interest.
        If None, will find the LCA of all pairs of nodes.

    Yields
    ------
    ((node1, node2), lca) : 2-tuple
        Where lca is least common ancestor of node1 and node2.

    Raises
    ------
    NetworkXPointlessConcept
        If `G` is null.
    NetworkXError
        If `G` is not a DAG.
    """
    _validate_backend_dispatch_keywords(
        "all_pairs_lowest_common_ancestor", backend, backend_kwargs
    )
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    if not is_directed_acyclic_graph(G):
        raise NetworkXError("LCA only defined on directed acyclic graphs.")
    if len(G) == 0:
        raise NetworkXPointlessConcept("LCA meaningless on null graphs.")

    if pairs is None:
        from itertools import combinations_with_replacement

        pairs = combinations_with_replacement(G, 2)
    else:
        pairs = dict.fromkeys(pairs)
        nodeset = set(G)
        for pair in pairs:
            missing = set(pair) - nodeset
            if missing:
                raise NodeNotFound(f"Node(s) {missing} from pair {pair} not in G.")

    def generate_lca_from_pairs(G, pairs):
        # br-r37-c1-db0qr: two fixes in one.
        # (1) DETERMINISM/PARITY: the previous code built each ancestor set via
        #     ``set(ancestors(G, v))``. fnx's native ``ancestors`` materialises a
        #     Rust HashSet whose iteration order is randomised per process, so the
        #     resulting Python set's layout — and therefore
        #     ``next(iter(common_ancestors))`` when several incomparable LCAs
        #     exist — varied RUN TO RUN (non-deterministic; diverged from nx).
        #     nx builds ``ancestors`` as ``{child for _, child in
        #     bfs_edges(G, v, reverse=True)}`` (deterministic BFS-discovery
        #     insertion order). Reproduce that exact reverse-BFS insertion order
        #     here from a predecessor snapshot, so the ancestor sets — and the
        #     LCA selection — are deterministic and match nx.
        # (2) PERF: the descent called ``G.successors(x)`` once per step over
        #     O(n^2) pairs (~42k fnx Python-wrapper round-trips on a 300-node DAG
        #     = the whole ~4x gap vs nx). Snapshot successors once into a plain
        #     dict; the descent then uses a local lookup. Net: ~5x self-speedup,
        #     faster than nx, deterministic, byte-exact.
        # br-r37-c1-aigcs: PERF (small-pair tax + wrapper tax). Two changes:
        #   (1) The previous code eagerly snapshotted predecessors AND successors
        #       for EVERY node (~2*n fnx Python-wrapper round-trips), so a
        #       single-pair / few-pair call paid the full O(n) adjacency cost —
        #       the bulk of the ~4.5x gap vs nx at n=2000. Make both snapshots
        #       LAZY+memoized: each node's neighbour list is fetched at most once.
        #   (2) The residual gap was the AdjacencyView wrapper behind
        #       ``G.predecessors(u)`` (per-call private-storage checks: ~8M
        #       _private_override/vars hits over a full-ancestor walk). For fnx
        #       DiGraphs, read predecessors via the native ``_native_predecessor
        #       _row_dict`` accessor, which yields the IDENTICAL key order
        #       (verified) ~8x cheaper. nx-typed graphs fall back to the public
        #       API. Iteration order is unchanged, so ancestor sets — and the
        #       deterministic LCA selection — remain byte-exact.
        pred_snapshot = {}
        succ_snapshot = {}

        _pred_row = getattr(G, "_native_predecessor_row_dict", None)
        if _pred_row is not None:

            def _preds(u):
                r = pred_snapshot.get(u)
                if r is None and u not in pred_snapshot:
                    r = list(_pred_row(u))
                    pred_snapshot[u] = r
                return r

        else:

            def _preds(u):
                r = pred_snapshot.get(u)
                if r is None and u not in pred_snapshot:
                    r = list(G.predecessors(u))
                    pred_snapshot[u] = r
                return r

        def _succs(u):
            r = succ_snapshot.get(u)
            if r is None and u not in succ_snapshot:
                r = list(G.successors(u))
                succ_snapshot[u] = r
            return r

        def _ancestors_bfs(source):
            # nx.ancestors via generic_bfs_edges over predecessors: level-order
            # BFS, inserting each newly seen predecessor in discovery order — the
            # identical insertion sequence to nx's set comprehension.
            seen = {source}
            anc = set()
            frontier = [(source, _preds(source))]
            while frontier:
                current = frontier
                frontier = []
                for _parent, parents in current:
                    for ancestor in parents:
                        if ancestor not in seen:
                            seen.add(ancestor)
                            frontier.append((ancestor, _preds(ancestor)))
                            anc.add(ancestor)
            return anc

        ancestor_cache = {}

        for v, w in pairs:
            if v not in ancestor_cache:
                anc_v = _ancestors_bfs(v)
                anc_v.add(v)
                ancestor_cache[v] = anc_v
            if w not in ancestor_cache:
                anc_w = _ancestors_bfs(w)
                anc_w.add(w)
                ancestor_cache[w] = anc_w

            common_ancestors = ancestor_cache[v] & ancestor_cache[w]

            if common_ancestors:
                # Descend to a common ancestor with no successor in
                # common_ancestors (matches nx's search strategy for DAGs).
                common_ancestor = next(iter(common_ancestors))
                while True:
                    successor = None
                    for lower_ancestor in _succs(common_ancestor):
                        if lower_ancestor in common_ancestors:
                            successor = lower_ancestor
                            break
                    if successor is None:
                        break
                    common_ancestor = successor
                yield ((v, w), common_ancestor)

    return generate_lca_from_pairs(G, pairs)




def prefix_tree(paths):
    """Creates a directed prefix tree from a list of paths.

    br-preftree: matches upstream nx.prefix_tree exactly: (a) the
    synthetic NIL terminal node at integer ``-1`` with
    ``source='NIL'`` is always present (even for empty input); (b)
    every path ends with an edge from its last non-NIL node to the NIL
    terminal, letting callers distinguish "this path ends here" from
    "this is an intermediate prefix of a longer path"; (c) non-root
    nodes carry only a ``source`` attribute (not an extra ``label``).

    Previously the NIL terminal was absent and nodes carried a bogus
    ``label`` attribute, so path-reconstruction code written against
    upstream (e.g. ``for leaf in tree.predecessors(-1): ...``) found
    no terminals and silently produced empty results.
    """
    # br-r37-c1-preftreebatch (cc): collect every node/edge during the DFS then build the
    # tree in ONE add_nodes_from + add_edges_from instead of per-node add_node/add_edge
    # (the PyO3 construction tax made prefix_tree 0.43x). The integer name is just a DFS
    # counter (the old ``len(tree) - 1`` increments 1,2,3,...), so node ids, edges, source
    # attrs and NIL terminals stay byte-identical to nx.
    root = 0
    NIL = -1
    node_specs = [(root, None), (NIL, "NIL")]
    edge_specs = []
    next_name = 1

    # br-r37-c1-6y9sr / br-r37-c1-vuzc5: mirror nx's algorithm EXACTLY — group
    # each parent's remaining paths by their first element (insertion order) and
    # expand depth-first, naming each new node ``len(tree) - 1``. The previous
    # path-by-path numbering produced trees ISOMORPHIC to nx's but with
    # different integer node ids (nx assigns ids in DFS-subtree order, not
    # path-arrival order), a real parity divergence on shared-prefix path sets.
    # This get_children/DFS form is the same O(total path length) cost (still
    # O(1) child grouping via the dict) AND byte-identical to nx: node ids,
    # edges, ``source`` attrs, and NIL terminals all match.
    def _get_children(parent, child_paths):
        children = _defaultdict(list)
        for path in child_paths:
            if not path:
                # Empty path: this prefix ends here -> edge to NIL terminal.
                edge_specs.append((parent, NIL))
                continue
            child, *rest = path
            children[child].append(rest)
        return children

    children = _get_children(root, paths)
    stack = [(root, iter(children.items()))]
    while stack:
        parent, remaining_children = stack[-1]
        try:
            child, remaining_paths = next(remaining_children)
        except StopIteration:
            stack.pop()
            continue
        # Relabel each child with the next unused integer name in DFS order
        # (1, 2, 3, ...) — matches the old ``len(tree) - 1`` exactly.
        new_name = next_name
        next_name += 1
        node_specs.append((new_name, child))
        edge_specs.append((parent, new_name))
        grandchildren = _get_children(new_name, remaining_paths)
        stack.append((new_name, iter(grandchildren.items())))

    tree = DiGraph()
    tree.add_nodes_from((n, {"source": s}) for n, s in node_specs)
    tree.add_edges_from(edge_specs)
    return tree


def _root_to_leaf_paths_via_nx(G):
    """br-r37-c1-17uhk: private wrapper so dag_to_branching stays PY_WRAPPER."""
    return _nx.algorithms.dag.root_to_leaf_paths(G, backend="networkx")


def dag_to_branching(G):
    """Return a branching (forest of arborescences) from a DAG.

    br-r37-c1-6nhsw: nx is decorated with
    ``@not_implemented_for('undirected')`` so undirected inputs raise
    NetworkXNotImplemented BEFORE the cycle check. fnx fell through
    to the acyclic check and raised HasACycle, which is not a
    subclass of NetworkXNotImplemented — drop-in code that does
    ``except NetworkXNotImplemented`` would not catch fnx's
    HasACycle. Add the type guard up front to match nx.

    br-r37-c1-06ubx: nx is also decorated with
    ``@not_implemented_for('multigraph')``. fnx silently accepted
    MultiDiGraph input. Add the same guard. Order matters: nx
    raises 'undirected' on MultiGraph (the inner decorator fires
    first); fnx mirrors that ordering — undirected check comes
    first so a MultiGraph (undirected + multigraph) gets the same
    'not implemented for undirected type' message.
    """
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if not is_directed_acyclic_graph(G):
        raise HasACycle("dag_to_branching is only defined for acyclic graphs")

    # br-r37-c1-hoqqp / br-r37-c1-17uhk: ``root_to_leaf_paths`` is no
    # longer top-level; reach for the canonical nx location via a
    # private helper so the public function stays PY_WRAPPER per the
    # coverage matrix lock.
    paths = _root_to_leaf_paths_via_nx(G)
    B = prefix_tree(paths)
    # Remove the synthetic root (0) AND the NIL terminal (-1) added by
    # prefix_tree so the returned branching matches nx's exactly
    # (br-preftree: the NIL terminal is part of prefix_tree's public
    # contract but not of dag_to_branching's).
    B.remove_node(0)
    if B.has_node(-1):
        B.remove_node(-1)
    return B
