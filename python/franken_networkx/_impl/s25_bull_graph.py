

def bull_graph(create_using=None):
    """Return the bull graph."""
    if create_using is None:
        g = _rust_bull_graph()
        # br-r37-c1-61kez: Rust fast path skipped the name tag.
        g.graph["name"] = "Bull Graph"
        return g
    return _classic_named_graph_from_adjlist(
        {0: [1, 2], 1: [0, 2, 3], 2: [0, 1, 4], 3: [1], 4: [2]},
        create_using=create_using,
        name="Bull Graph",
    )


def circular_ladder_graph(n, create_using=None):
    """Return the circular ladder graph.

    Degenerate cases (``n < 3``) use the pure-Python fallback path
    — the rust primitive rejects those with ``n must be >= 3``,
    but upstream nx returns degenerate-but-valid graphs for
    n ∈ {0, 1, 2} (franken_networkx-uwa6w).

    br-r37-c1-3bdal: use the generator-native path only where it is
    order-compatible.
    """
    if create_using is None and isinstance(n, _numbers.Integral) and n >= 3:
        return _rust_circular_ladder_graph_native(int(n))

    G = ladder_graph(n, create_using)
    G.add_edge(0, n - 1)
    G.add_edge(n, 2 * n - 1)
    return G


def ladder_graph(n, create_using=None):
    """Return the ladder graph.

    Degenerate case ``n == 0`` is an empty graph (matches upstream
    nx). br-r37-c1-iw2hz: drop the Rust fast path — it drifted
    adj[n-1] order from nx (e.g. fnx adj[4] = [0,5] vs nx [5,0]).
    The Python construction below already matches nx.
    """
    G = empty_graph(2 * n, create_using)
    if G.is_directed():
        raise NetworkXError("Directed Graph not supported")
    # br-r37-c1-ladderbatch: one add_edges_from instead of three — only the first
    # call hit the native bulk path; the 2nd/3rd saw a non-fresh graph and fell to
    # the per-edge add_edge tax. chain preserves the exact (rail-0, rail-1, rungs)
    # emission order so edge + adj order stay byte-identical to nx's three calls.
    G.add_edges_from(
        _itertools.chain(
            _itertools.pairwise(range(n)),
            _itertools.pairwise(range(n, 2 * n)),
            ((v, v + n) for v in range(n)),
        )
    )
    return G


def lollipop_graph(m, n, create_using=None):
    """Return the lollipop graph."""
    m_value, m_nodes = _nodes_or_number_local(m)
    M = len(m_nodes)
    if M < 2:
        raise NetworkXError("Invalid description: m should indicate at least 2 nodes")

    # br-r37-c1-iw2hz: drop the Rust fast path — it drifted adj of
    # the bell-vs-stick joining node (e.g. fnx adj[3] = [2,4] vs
    # nx [4,2]). The Python construction below already matches nx.
    n_value, n_nodes = _nodes_or_number_local(n)
    if isinstance(m_value, _numbers.Integral) and isinstance(n_value, _numbers.Integral):
        n_nodes = list(range(M, M + n_value))
    N = len(n_nodes)

    G = complete_graph(m_nodes, create_using)
    if G.is_directed():
        raise NetworkXError("Directed Graph not supported")

    _add_nodes_in_order(G, n_nodes)
    if N > 1:
        G.add_edges_from(_itertools.pairwise(n_nodes))

    if len(G) != M + N:
        raise NetworkXError("Nodes must be distinct in containers m and n")

    if M > 0 and N > 0:
        G.add_edge(m_nodes[-1], n_nodes[0])
    return G


def tadpole_graph(m, n, create_using=None):
    """Return the tadpole graph.

    br-tadm2: nx.tadpole_graph accepts m=2 (degenerate cycle = single
    edge). The Rust binding requires m>=3 and raised NetworkXError.
    Route m<3 cases through the Python path so the m=2 degenerate case
    (plus any tail) produces the same output as nx.
    """
    m_value, m_nodes = _nodes_or_number_local(m)
    M = len(m_nodes)
    if M < 2:
        raise NetworkXError("Invalid description: m should indicate at least 2 nodes")

    n_value, n_nodes = _nodes_or_number_local(n)
    if (
        create_using is None
        and isinstance(m_value, _numbers.Integral)
        and isinstance(n_value, _numbers.Integral)
        and m_value >= 3
    ):
        return _rust_tadpole_graph(m_value, n_value)

    if isinstance(m_value, _numbers.Integral) and isinstance(n_value, _numbers.Integral):
        n_nodes = list(range(M, M + n_value))

    G = cycle_graph(m_nodes, create_using)
    if G.is_directed():
        raise NetworkXError("Directed Graph not supported")

    G.add_edges_from(_itertools.pairwise([m_nodes[-1], *n_nodes]))
    return G


def wheel_graph(n, create_using=None):
    """Return the wheel graph.

    br-r37-c1-o97vk RESOLVED (u-major-hoist arc, 1123e2bf8): the rim
    drift was never the kernel's fault — rust_graph_to_py_standalone's
    edges_ordered() rebuild hoisted the closing rim edge. With the
    converter now cloning wholesale, the rust path matches nx at all
    sizes (verified n=5,6,7,10) — restore the native fast path.
    """
    n_value, nodes = _nodes_or_number_local(n)
    G = empty_graph(nodes, create_using)
    if G.is_directed():
        raise NetworkXError("Directed Graph not supported")

    # br-r37-c1-starwheel-bulk: the native _rust_wheel_graph kernel was ~2x
    # SLOWER than this single bulk build (its dual-rep PyGraph construction
    # substrate exceeds the batch path). Drop it; collect hub spokes + the rim
    # cycle into ONE add_edges_from. Byte-exact: hub edges ((hub,rim[0]),...)
    # then the cyclic rim ((rim[0],rim[1]),...,(rim[-1],rim[0])) match nx's
    # add_edges_from((hub,node)..) + pairwise(rim, cyclic=True), and edges() is
    # node-iteration-determined.
    if len(nodes) > 1:
        hub, *rim = nodes
        edges = [(hub, node) for node in rim]
        if len(rim) > 1:
            edges.extend(_itertools.pairwise(rim))
            edges.append((rim[-1], rim[0]))
        G.add_edges_from(edges)
    return G


def diamond_graph(create_using=None):
    """Return the diamond graph."""
    if create_using is None:
        g = _rust_diamond_graph()
        # br-r37-c1-61kez: Rust fast path skipped the name tag.
        g.graph["name"] = "Diamond Graph"
        return g
    return _classic_named_graph_from_adjlist(
        {0: [1, 2], 1: [0, 2, 3], 2: [0, 1, 3], 3: [1, 2]},
        create_using=create_using,
        name="Diamond Graph",
    )


def house_graph(create_using=None):
    """Return the house graph."""
    if create_using is None:
        g = _rust_house_graph()
        # br-r37-c1-61kez: Rust fast path skipped the name tag.
        g.graph["name"] = "House Graph"
        return g
    return _classic_named_graph_from_adjlist(
        {0: [1, 2], 1: [0, 3], 2: [0, 3, 4], 3: [1, 2, 4], 4: [2, 3]},
        create_using=create_using,
        name="House Graph",
    )


def house_x_graph(create_using=None):
    """Return the house-X graph.

    br-r37-c1-iw2hz: always use the Python construction; the Rust
    fast-path drifted adj order on multiple nodes.
    """
    graph = house_graph(create_using=create_using)
    graph.add_edges_from([(0, 3), (1, 2)])
    graph.graph["name"] = "House-with-X-inside Graph"
    return graph


def cubical_graph(create_using=None):
    """Return the cubical graph.

    br-canonicaledge: the Rust fast-path ``_rust_cubical_graph`` uses a
    different node-labelling convention than nx (edges ``1-5`` and
    ``3-7`` instead of nx's ``1-7`` and ``3-5``). Always use the
    Python adjlist path so the edges match nx exactly.
    """
    return _classic_named_graph_from_adjlist(
        {
            0: [1, 3, 4],
            1: [0, 2, 7],
            2: [1, 3, 6],
            3: [0, 2, 5],
            4: [0, 5, 7],
            5: [3, 4, 6],
            6: [2, 5, 7],
            7: [1, 4, 6],
        },
        create_using=create_using,
        name="Platonic Cubical Graph",
    )


def petersen_graph(create_using=None):
    """Return the Petersen graph."""
    if create_using is None:
        g = _rust_petersen_graph()
        # br-r37-c1-61kez: Rust fast path skipped the name tag.
        g.graph["name"] = "Petersen Graph"
        return g
    return _classic_named_graph_from_adjlist(
        {
            0: [1, 4, 5],
            1: [0, 2, 6],
            2: [1, 3, 7],
            3: [2, 4, 8],
            4: [3, 0, 9],
            5: [0, 7, 8],
            6: [1, 8, 9],
            7: [2, 5, 9],
            8: [3, 5, 6],
            9: [4, 6, 7],
        },
        create_using=create_using,
        name="Petersen Graph",
    )


def tetrahedral_graph(create_using=None):
    """Return the tetrahedral graph."""
    if create_using is None:
        g = _rust_tetrahedral_graph()
        # br-r37-c1-61kez: Rust fast path skipped the name tag.
        g.graph["name"] = "Platonic Tetrahedral Graph"
        return g
    graph = complete_graph(4, create_using=create_using)
    graph.graph["name"] = "Platonic Tetrahedral Graph"
    return graph


def sedgewick_maze_graph(create_using=None):
    """Return the small maze from Sedgewick's *Algorithms in C++*.

    ``create_using`` matches networkx's public signature; build the
    edge list directly so nx's adj-order contract is preserved
    (br-r37-c1-iw2hz: the Rust fast path drifted adj[0]/adj[4] order).
    """
    G = empty_graph(0, create_using)
    G.add_nodes_from(range(8))
    G.add_edges_from([(0, 2), (0, 7), (0, 5)])
    G.add_edges_from([(1, 7), (2, 6)])
    G.add_edges_from([(3, 4), (3, 5)])
    G.add_edges_from([(4, 5), (4, 7), (4, 6)])
    G.graph["name"] = "Sedgewick Maze"
    return G


def desargues_graph(create_using=None):
    """Return the Desargues graph.

    br-canonicaledge: always use the LCF construction path; the Rust
    fast-path used a different node labelling that diverged from nx.
    """
    graph = LCF_graph(20, [5, -5, 9, -9], 5, create_using=create_using)
    graph.graph["name"] = "Desargues Graph"
    return graph


def dodecahedral_graph(create_using=None):
    """Return the dodecahedral graph.

    br-r37-c1-iw2hz RESOLVED (generators arc): the kernel now emits
    nx's exact LCF sequence — native route re-enabled for the default
    case.
    """
    if create_using is None:
        from franken_networkx._fnx import dodecahedral_graph as _rust_dodecahedral

        graph = _rust_dodecahedral()
        graph.graph["name"] = "Dodecahedral Graph"
        return graph
    graph = LCF_graph(
        20,
        [10, 7, 4, -4, -7, 10, -4, 7, -7, 4],
        2,
        create_using=create_using,
    )
    graph.graph["name"] = "Dodecahedral Graph"
    return graph


def heawood_graph(create_using=None):
    """Return the Heawood graph.

    br-r37-c1-iw2hz: always use the LCF construction path; the Rust
    fast-path drifted adj order from nx.
    """
    graph = LCF_graph(14, [5, -5], 7, create_using=create_using)
    graph.graph["name"] = "Heawood Graph"
    return graph


def moebius_kantor_graph(create_using=None):
    """Return the Moebius-Kantor graph.

    br-canonicaledge: always use the LCF construction.
    """
    graph = LCF_graph(16, [5, -5], 8, create_using=create_using)
    graph.graph["name"] = "Moebius-Kantor Graph"
    return graph


def octahedral_graph(create_using=None):
    """Return the octahedral graph.

    br-canonicaledge: always use the Python adjlist path.
    """
    return _classic_named_graph_from_adjlist(
        {0: [1, 2, 3, 4], 1: [2, 3, 5], 2: [4, 5], 3: [4, 5], 4: [5]},
        create_using=create_using,
        name="Platonic Octahedral Graph",
    )


def truncated_cube_graph(create_using=None):
    """Return the truncated cube graph.

    br-r37-c1-iw2hz: always use the Python adjlist path; the Rust
    fast-path drifted adj[1] order from nx (fnx [0,14,11] vs
    nx [0,11,14]).
    """
    return _classic_named_graph_from_adjlist(
        {
            0: [1, 2, 4],
            1: [11, 14],
            2: [3, 4],
            3: [6, 8],
            4: [5],
            5: [16, 18],
            6: [7, 8],
            7: [10, 12],
            8: [9],
            9: [17, 20],
            10: [11, 12],
            11: [14],
            12: [13],
            13: [21, 22],
            14: [15],
            15: [19, 23],
            16: [17, 18],
            17: [20],
            18: [19],
            19: [23],
            20: [21],
            21: [22],
            22: [23],
        },
        create_using=create_using,
        name="Truncated Cube Graph",
    )


def truncated_tetrahedron_graph(create_using=None):
    """Return the truncated tetrahedron graph.

    br-r37-c1-iw2hz: always use the Python construction; the Rust
    fast-path drifted adj[2] order from nx.
    """
    graph = path_graph(12, create_using=create_using)
    graph.add_edges_from([(0, 2), (0, 9), (1, 6), (3, 11), (4, 11), (5, 7), (8, 10)])
    graph.graph["name"] = "Truncated Tetrahedron Graph"
    return graph


def chvatal_graph(create_using=None):
    """Return the Chvatal graph."""
    if create_using is None:
        g = _rust_chvatal_graph()
        # br-r37-c1-61kez: Rust fast path skipped the name tag.
        g.graph["name"] = "Chvatal Graph"
        return g
    return _classic_named_graph_from_adjlist(
        {
            0: [1, 4, 6, 9],
            1: [2, 5, 7],
            2: [3, 6, 8],
            3: [4, 7, 9],
            4: [5, 8],
            5: [10, 11],
            6: [10, 11],
            7: [8, 11],
            8: [10],
            9: [10, 11],
        },
        create_using=create_using,
        name="Chvatal Graph",
    )


def frucht_graph(create_using=None):
    """Return the Frucht graph.

    br-r37-c1-iw2hz RESOLVED (generators arc): the kernel now emits
    nx's exact construction (cycle(7) + nx's edge list in its order) —
    native route re-enabled for the default case.
    """
    if create_using is None:
        from franken_networkx._fnx import frucht_graph as _rust_frucht

        graph = _rust_frucht()
        graph.graph["name"] = "Frucht Graph"
        return graph
    graph = cycle_graph(7, create_using=create_using)
    graph.add_edges_from(
        [
            (0, 7),
            (1, 7),
            (2, 8),
            (3, 9),
            (4, 9),
            (5, 10),
            (6, 10),
            (7, 11),
            (8, 11),
            (8, 9),
            (10, 11),
        ]
    )
    graph.graph["name"] = "Frucht Graph"
    return graph


def icosahedral_graph(create_using=None):
    """Return the icosahedral graph.

    br-canonicaledge: always use the Python adjlist path.
    """
    return _classic_named_graph_from_adjlist(
        {
            0: [1, 5, 7, 8, 11],
            1: [2, 5, 6, 8],
            2: [3, 6, 8, 9],
            3: [4, 6, 9, 10],
            4: [5, 6, 10, 11],
            5: [6, 11],
            7: [8, 9, 10, 11],
            8: [9],
            9: [10],
            10: [11],
        },
        create_using=create_using,
        name="Platonic Icosahedral Graph",
    )


def krackhardt_kite_graph(create_using=None):
    """Return the Krackhardt kite graph."""
    if create_using is None:
        g = _rust_krackhardt_kite_graph()
        # br-r37-c1-61kez: Rust fast path skipped the name tag.
        g.graph["name"] = "Krackhardt Kite Social Network"
        return g
    return _classic_named_graph_from_adjlist(
        {
            0: [1, 2, 3, 5],
            1: [0, 3, 4, 6],
            2: [0, 3, 5],
            3: [0, 1, 2, 4, 5, 6],
            4: [1, 3, 6],
            5: [0, 2, 3, 6, 7],
            6: [1, 3, 4, 5, 7],
            7: [5, 6, 8],
            8: [7, 9],
            9: [8],
        },
        create_using=create_using,
        name="Krackhardt Kite Social Network",
    )


def null_graph(create_using=None):
    """Return the null graph."""
    if create_using is None:
        return _rust_null_graph()
    return empty_graph(0, create_using=create_using)


def trivial_graph(create_using=None):
    """Return the trivial graph."""
    if create_using is None:
        return _rust_trivial_graph()
    return empty_graph(1, create_using=create_using)


def circulant_graph(n, offsets, create_using=None):
    """Return the circulant graph on n nodes with the given offsets.

    br-circself: nx allows n=0 (empty graph) and produces self-loops
    when an offset is divisible by n (e.g. n=1 with offset=1, or n=2
    with offset=2). The Rust binding rejected n=0 entirely and silently
    dropped self-loops, breaking parity with nx.

    br-r37-c1-iw2hz: also drop the Rust fast path even for the strict
    non-self-loop case — it drifted adj order from nx (e.g. for
    circulant(7, [1,2]) fnx adj[0] = [1,2,5,6] vs nx [6,5,1,2]).
    The Python construction matches nx exactly.
    """
    offsets_list = list(offsets)
    G = empty_graph(n, create_using)
    # br-r37-c1-circulantbatch: combine the two edge passes into ONE add_edges_from.
    # The previous second call saw a non-fresh graph and fell back to the per-edge
    # add_edge tax. ``for sign in (-1, 1)`` keeps the exact ``(i-j) pass then (i+j)
    # pass`` emission order, so the edge insertion (and adj) order stays byte-
    # identical to nx's two separate calls.
    G.add_edges_from(
        (i, (i + sign * j) % n)
        for sign in (-1, 1)
        for i in range(n)
        for j in offsets_list
    )
    return G


def paley_graph(p, create_using=None):
    """Return the Paley graph or digraph of order p.

    br-paleydir: nx.paley_graph's default return class is DiGraph (the
    fnx Rust fast path incorrectly defaulted to an undirected Graph).
    Route through the Python path so the default class + edge set match
    nx.
    """
    graph = empty_graph(0, create_using=create_using, default=DiGraph)
    if graph.is_multigraph():
        raise NetworkXError("`create_using` cannot be a multigraph.")

    square_set = {(x**2) % p for x in range(1, p) if (x**2) % p != 0}
    # br-r37-c1-paleybatch (cc): one add_edges_from over the same (x outer, square
    # inner) order instead of per-edge add_edge (construction tax, 0.25x vs nx).
    # No pre-add of nodes — add_edges_from inserts them in the same edge-discovery
    # order as the per-edge loop, so node + edge iteration order is byte-identical
    # (verified vs current fnx AND nx for p in {5,13,17,101,103,107}).
    graph.add_edges_from(
        (x, (x + square) % p) for x in range(p) for square in square_set
    )
    graph.graph["name"] = f"paley({p})"
    return graph


def chordal_cycle_graph(p, create_using=None):
    """Return the chordal cycle graph on p nodes.

    br-chordalmg: nx.chordal_cycle_graph default return class is
    MultiGraph (self-loops + parallel edges from the (left, right, chord)
    additions). fnx's Rust fast path returned a simple Graph, dropping
    parallels. Route through the Python path always.
    """
    graph = empty_graph(0, create_using=create_using, default=MultiGraph)
    if graph.is_directed() or not graph.is_multigraph():
        raise NetworkXError("`create_using` must be an undirected multigraph.")

    # br-r37-c1-genbatch (cc): batch the 3*p edges through one add_edges_from (LIST,
    # multigraph-safe) — same (x, left/right/chord) order + auto-keys, byte-identical.
    # Int keys -> 0.46x -> 0.91x (near parity).
    edges = []
    for x in range(p):
        left = (x - 1) % p
        right = (x + 1) % p
        chord = pow(x, p - 2, p) if x > 0 else 0
        edges.append((x, left))
        edges.append((x, right))
        edges.append((x, chord))
    graph.add_edges_from(edges)
    graph.graph["name"] = f"chordal_cycle_graph({p})"
    return graph


def pappus_graph():
    """Return the Pappus graph.

    br-canonicaledge: LCF construction matches nx's canonical
    labelling. Previously fnx delegated to the Rust binding which
    used a different node-permutation (edges like 10-4, 8-2 instead
    of nx's 1-7 family).
    """
    graph = LCF_graph(18, [5, 7, -7, 7, -7, -5], 3)
    graph.graph["name"] = "Pappus Graph"
    return graph


def hoffman_singleton_graph():
    """Return the Hoffman-Singleton graph.

    br-canonicaledge: matches nx's canonical node labelling
    exactly. The Rust binding used a different permutation.
    """
    return _hoffman_singleton_impl()


def _hoffman_singleton_impl():
    """Construct the Hoffman-Singleton graph with NetworkX canonical labelling."""
    G = Graph()
    for i in range(5):
        for j in range(5):
            G.add_edge(("pentagon", i, j), ("pentagon", i, (j - 1) % 5))
            G.add_edge(("pentagon", i, j), ("pentagon", i, (j + 1) % 5))
            G.add_edge(("pentagram", i, j), ("pentagram", i, (j - 2) % 5))
            G.add_edge(("pentagram", i, j), ("pentagram", i, (j + 2) % 5))
            for k in range(5):
                G.add_edge(("pentagon", i, j), ("pentagram", k, (i * k + j) % 5))
    G = convert_node_labels_to_integers(G)
    G.graph["name"] = "Hoffman-Singleton Graph"
    return G


def tutte_graph(create_using=None):
    """Return the Tutte graph.

    br-canonicaledge: always use the Python adjlist path.
    """
    return _classic_named_graph_from_adjlist(
        {
            0: [1, 2, 3],
            1: [4, 26],
            2: [10, 11],
            3: [18, 19],
            4: [5, 33],
            5: [6, 29],
            6: [7, 27],
            7: [8, 14],
            8: [9, 38],
            9: [10, 37],
            10: [39],
            11: [12, 39],
            12: [13, 35],
            13: [14, 15],
            14: [34],
            15: [16, 22],
            16: [17, 44],
            17: [18, 43],
            18: [45],
            19: [20, 45],
            20: [21, 41],
            21: [22, 23],
            22: [40],
            23: [24, 27],
            24: [25, 32],
            25: [26, 31],
            26: [33],
            27: [28],
            28: [29, 32],
            29: [30],
            30: [31, 33],
            31: [32],
            34: [35, 38],
            35: [36],
            36: [37, 39],
            37: [38],
            40: [41, 44],
            41: [42],
            42: [43, 45],
            43: [44],
        },
        create_using=create_using,
        name="Tutte's Graph",
    )


def generalized_petersen_graph(n, k, *, create_using=None):
    """Return the generalized Petersen graph G(n, k).

    br-r37-c1-gpcanon (cc): the native ``_rust_generalized_petersen_graph`` produced an
    ISOMORPHIC graph with a DIFFERENT node labelling (e.g. node 7 before 6 at n=5) and
    dropped the ``name`` graph attr — diverging from nx byte-for-byte — AND was ~1.7x
    slower than nx. Build it in Python instead (cycle_graph + the spoke/inner-star edges
    in nx's exact order); batched through one add_edges_from it is byte-identical to nx
    (node + edge order + name) and beats the native kernel (0.58x -> 0.86x). Same
    canonical-labelling routing family as pappus_graph / hoffman_singleton_graph.
    """
    if n <= 2:
        raise NetworkXError(f"n >= 3 required. Got {n=}")
    if k < 1 or k > n / 2:
        raise NetworkXError(f" Got {n=} {k=}. Need 1 <= k <= n/2")

    G = cycle_graph(range(n), create_using=create_using)
    if G.is_directed():
        raise NetworkXError("Directed Graph not supported in create_using")
    edges = []
    for i in range(n):
        edges.append((i, n + i))
        edges.append((n + i, n + (i + k) % n))
    G.add_edges_from(edges)
    G.graph["name"] = f"Generalized Petersen Graph GP({n}, {k})"
    return G


def windmill_graph(n, k):
    """Generate a windmill graph with n cliques of size k sharing one node.

    br-windvalid: nx raises NetworkXError on n<2 or k<2 with specific
    messages. The Rust binding either accepted n in {0,1} (producing a
    malformed graph) or rejected with the wrong message. Match nx's
    validation exactly so invalid inputs fail with the right wording
    instead of silently producing a non-windmill graph.
    """
    if n < 2:
        raise NetworkXError("A windmill graph must have at least two cliques")
    if k < 2:
        raise NetworkXError("The cliques must have at least two nodes")
    return _rust_windmill_graph(k, n)


def complete_multipartite_graph(*subset_sizes):
    """Return the complete multipartite graph over the given subsets.

    Each argument is either an integer partition size or an iterable of node
    labels for that partition. Mixing the two kinds raises
    ``NetworkXError`` with the same message as upstream NetworkX. Every node
    receives a ``subset`` attribute equal to the index of its partition.
    """
    if len(subset_sizes) == 0:
        return Graph()

    int_sizes: list[int] | None = None
    if all(isinstance(s, int) for s in subset_sizes):
        int_sizes = list(subset_sizes)
        if any(size < 0 for size in int_sizes):
            raise NetworkXError(
                f"Negative number of nodes not valid: {subset_sizes}"
            )
    else:
        # Reject mixed-type input with NetworkX's exact wording. Only accept
        # all-iterables when every argument is a non-int iterable.
        for item in subset_sizes:
            if isinstance(item, int):
                raise NetworkXError("Arguments must be all ints or all iterables")
            try:
                iter(item)
            except TypeError as err:
                raise NetworkXError(
                    "Arguments must be all ints or all iterables"
                ) from err

    if int_sizes is not None:
        offset = 0
        subsets = []
        for size in int_sizes:
            subsets.append(range(offset, offset + size))
            offset += size
    else:
        subsets = [list(item) for item in subset_sizes]

    # br-r37-c1-multipartite-bulk: the native _rust_complete_multipartite_graph
    # kernel is ~2.3x SLOWER than this Python build for the int path (its
    # dual-rep PyGraph construction substrate exceeds nx's add_edges_from on the
    # dense cross-partition edge set; the per-node subset loop was negligible).
    # Build it exactly like nx: subset-attributed nodes per block, then ONE bulk
    # add_edges_from over every cross-partition pair (a single native batch
    # instead of per-pair calls). Byte-exact — same node/edge stream as nx and
    # edges() is node-iteration-determined.
    graph = Graph()
    # br-r37-c1-multipartitenodes: one attributed add_nodes_from instead of a
    # per-partition loop (only the first call hit the native node-batch; later
    # calls fell to per-node add_node). Same node order (partition-major) and
    # ``subset`` attr per node, byte-identical to the per-partition build.
    graph.add_nodes_from(
        (node, {"subset": partition_index})
        for partition_index, subset in enumerate(subsets)
        for node in subset
    )
    graph.add_edges_from(
        edge
        for left, right in _itertools.combinations(subsets, 2)
        for edge in _itertools.product(left, right)
    )
    return graph


def gnm_random_graph(n, m, seed=None, directed=False, *, create_using=None):
    """Return a G(n,m) random graph with exactly *m* edges.

    Parameters
    ----------
    n : int
        Number of nodes.
    m : int
        Number of edges.
    seed : int or None, optional
    directed : bool, optional
        If True, return a directed graph. Default is False.
    create_using : graph, optional
        Graph instance to use for creating the graph.

    Returns
    -------
    Graph
    """
    # br-r37-c1-ols3t: nx's py_random_state, resolved first (a NaN or other
    # invalid seed raises its ValueError here); the kernels draw from an int
    # or stream a random.Random's state - None is the global random._inst.
    kernel_seed = _kernel_seed(seed)
    default = DiGraph if directed else Graph
    graph = _checked_create_using(
        create_using,
        directed=directed,
        multigraph=False,
        default=default,
    )
    # br-r37-c1-gnm-neg: nx raises NetworkXError on negative ``n``;
    # fnx previously silently returned an empty graph (range(n)
    # yielded nothing). Match nx's structural-error contract — same
    # fix shape as br-r37-c1-{rgg-neg, pjf7g, srgg-neg, trgg-neg,
    # 60f9n, waxman-neg, gtg-neg, hszkp}.
    if isinstance(n, int) and n < 0:
        raise NetworkXError(f"Negative number of nodes not valid: {n}")
    # br-r37-c1-gnmnative: route to the native gnm rejection sampler (byte-exact
    # PythonRandom draw sequence — fnx-generators has nx-parity tests), skipping
    # the per-edge Python randint loop the pure-Python sampler below pays (~0.80x
    # nx -> faster). Gate: non-negative int n/m (the native binding takes usize,
    # and negative m must give nx's 0-edge graph via the Python path) and a
    # seed the kernel reproduces (br-r37-c1-ols3t: any int, and any exact
    # random.Random - None included - by streaming its state).
    if (
        create_using is None
        and _rust_gnm_random_graph is not None
        and isinstance(n, int)
        and isinstance(m, int)
        and m >= 0
        and kernel_seed is not None
    ):
        if directed:
            return _rust_gnm_random_digraph(n, m, seed=kernel_seed)
        return _rust_gnm_random_graph(n, m, seed=kernel_seed)
    # br-r37-c1-cdf1v: nx's py_random_state - a random.Random / numpy seed is
    # drawn from as it is (random.Random(seed) raised TypeError on one).
    rng = _generator_random_state(seed)
    # br-r37-c1-gnmdir: directed G(n,m) is the SAME rejection sampler but with ORDERED
    # edges and max_edges = n*(n-1); reproduce it natively (-> fnx DiGraph) instead of
    # delegating to nx, which returned a raw nx.DiGraph — gnm_random_graph was the ONLY
    # directed generator leaking an nx type, and that nx result then taxed EVERY downstream
    # fnx call with an nx->fnx conversion (~1.8ms each; the realistic construct-and-use
    # workflow was 2.86x SLOWER than this native path, and the native path beats nx 1.06x).
    G = empty_graph(n, create_using=graph, default=default)
    if n < 2:
        return G
    edges_added = set()
    max_edges = n * (n - 1) if directed else n * (n - 1) // 2
    # br-r37-c1-gnmcomplete: nx returns complete_graph(n) when m saturates, BEFORE drawing
    # any RNG — combinations(range(n), 2) order (undirected) / permutations(range(n), 2)
    # order (directed = complete_graph(n, DiGraph)), NOT the rejection-sampling order.
    if m >= max_edges:
        if directed:
            G.add_edges_from((u, v) for u in range(n) for v in range(n) if u != v)
        else:
            G.add_edges_from((u, v) for u in range(n) for v in range(u + 1, n))
        return G
    m = min(m, max_edges)
    # br-r37-c1-yrdso: this G(n,m) sampler is pure Python (it reproduces nx's
    # exact ``random.Random`` draw sequence; the native kernel is bypassed for
    # ``directed``/``create_using`` parity). The per-edge ``G.add_edge`` PyO3
    # round-trip dominated — ~2.7x nx on (1000, 8000). Collect the accepted
    # endpoints (same rejection-sampling order) and commit them through ONE
    # ``add_edges_from`` (the optimized batch path): byte-identical edge set and
    # insertion order, but ~2.8x faster (now beats nx). No RNG/algorithm change.
    edge_list = []
    while len(edges_added) < m:
        u = rng.randint(0, n - 1)
        v = rng.randint(0, n - 1)
        if u != v:
            edge = (u, v) if directed else (min(u, v), max(u, v))
            if edge not in edges_added:
                edges_added.add(edge)
                edge_list.append((u, v))
    G.add_edges_from(edge_list)
    return G


# ---------------------------------------------------------------------------
# Additional connectivity
# ---------------------------------------------------------------------------


def _planarity_graph_for_certificate(G):
    import networkx as nx

    try:
        from franken_networkx.backend import _fnx_to_nx

        return _fnx_to_nx(G)
    except AttributeError:
        if hasattr(G, "nodes") and hasattr(G, "edges"):
            return G
        graph = nx.Graph()
        graph.add_nodes_from(G)
        return graph


def _digraph_matches_undirected_edge_order(G):
    idx = {u: i for i, u in enumerate(G.nodes)}
    n = len(idx)
    adj_lr = [[] for _ in range(n)]
    seen = set()
    for u, v in G.edges():
        iu, iv = idx[u], idx[v]
        if iu == iv:
            continue
        key = (iu, iv) if iu < iv else (iv, iu)
        if key not in seen:
            seen.add(key)
            adj_lr[iu].append(iv)
            adj_lr[iv].append(iu)
    adj_pe = [[] for _ in range(n)]
    seen_pe = set()
    for iu in range(n):
        for iv in adj_lr[iu]:
            key = (iu, iv) if iu < iv else (iv, iu)
            if key not in seen_pe:
                seen_pe.add(key)
                adj_pe[iu].append(iv)
                adj_pe[iv].append(iu)
    return adj_lr == adj_pe


def _has_native_planarity_storage(G):
    if not isinstance(G, (Graph, DiGraph, MultiGraph, MultiDiGraph)):
        return False
    inst_dict = getattr(G, "__dict__", None)
    if inst_dict and ("_adj" in inst_dict or "_succ" in inst_dict):
        return False
    cls = type(G)
    if cls in (Graph, DiGraph, MultiGraph, MultiDiGraph):
        return True
    return getattr(cls, "_adj", None) in (
        Graph._adj,
        DiGraph._adj,
        MultiGraph._adj,
        MultiDiGraph._adj,
    )


def _check_planarity_certificate(G, counterexample=False, recursive=False):
    if _has_native_planarity_storage(G):
        is_undirected = isinstance(G, (Graph, MultiGraph))
        if not counterexample and type(G) is Graph:
            try:
                node_count = G.number_of_nodes()
                edge_count = G.number_of_edges()
                if (
                    node_count >= 3
                    and edge_count > (3 * node_count) - 6
                    and _fnx.planarity_euler_reject(G)
                ):
                    return False, None
            except (AttributeError, TypeError, NetworkXError):
                pass
        # Native LR planarity test: settles non-planar graphs natively, returning
        # either (False, None) when counterexample=False, or extracting a native
        # Kuratowski subgraph certificate when counterexample=True.
        # Planar graphs receive the native Boyer-Myrvold PlanarEmbedding certificate.
        try:
            if not _fnx.is_planar_lr(G):
                if counterexample:
                    cex = _fnx.kuratowski_subgraph(G)
                    return False, cex
                return False, None
            if is_undirected or _digraph_matches_undirected_edge_order(G):
                data = _fnx.planar_embedding_data(G)
                if data is not None:
                    from networkx.algorithms.planarity import PlanarEmbedding

                    embedding = PlanarEmbedding()
                    embedding.add_nodes_from(node for node, _ in data)
                    embedding.set_data(dict(data))
                    return True, embedding
        except (AttributeError, TypeError, NetworkXError):
            pass

    from networkx.algorithms import planarity as nx_planarity

    graph = _planarity_graph_for_certificate(G)
    if recursive:
        result = nx_planarity.check_planarity_recursive(
            graph,
            counterexample=counterexample,
            backend="networkx",
        )
    else:
        result = nx_planarity.check_planarity(
            graph, counterexample=counterexample, backend="networkx"
        )

    # br-r37-c1-rcg8f: return the Kuratowski counterexample as an fnx graph.
    # ``get_counterexample`` already converts, so one module handed back two
    # different types for the same object — `fnx.Graph` from one entry point and
    # `networkx.classes.graph.Graph` from the other. Every other graph-returning
    # surface here (``complete_to_chordal_graph``, ``subgraph().copy()``,
    # ``k_core``) returns fnx types, and planarity.py's own docstring promises it.
    #
    # Gated on ``is_planar`` being False, which is exact: the PLANAR branch's
    # certificate is a ``PlanarEmbedding``, deliberately kept as networkx's class
    # so isinstance and ``check_structure()`` keep working, and it must not be
    # converted. Only the non-planar counterexample is a plain Graph.
    is_planar, certificate = result
    if not is_planar and certificate is not None:
        from franken_networkx.readwrite import _from_nx_graph

        return is_planar, _from_nx_graph(certificate)
    return result


def check_planarity(G, counterexample=False, *, backend=None, **backend_kwargs):
    """Check if *G* is planar and return a NetworkX-style certificate tuple.

    Parameters
    ----------
    G : Graph
    counterexample : bool, optional
        If True and the graph is not planar, return a Kuratowski subgraph as
        the certificate. Otherwise planar graphs return a PlanarEmbedding.

    Returns
    -------
    (bool, certificate)
    """
    _validate_backend_dispatch_keywords("check_planarity", backend, backend_kwargs)
    return _check_planarity_certificate(G, counterexample=counterexample)


# br-r37-c1-plr-removed: ``check_planarity_recursive``,
# ``get_counterexample``, and ``get_counterexample_recursive`` are
# exposed by nx only at ``nx.algorithms.planarity.X``; nx top-level
# raises AttributeError.  fnx had module-level Python wrappers that
# masked the contract — drop-in callers writing
# ``nx.check_planarity_recursive(G)`` got a working result on fnx.
# Available exclusively at ``fnx.algorithms.planarity.X`` (nx's
# submodule, accessible via the algorithm namespace).  Module
# ``__getattr__`` traps top-level access.

# Internal aliases retained for use by the planarity submodule
# wrappers that other fnx code exercises (so the submodule continues
# to forward to a working implementation).







def all_simple_edge_paths(
    G, source, target, cutoff=None, *, backend=None, **backend_kwargs
):
    """Yield all simple paths from source to target as edge lists.

    Parameters
    ----------
    G : Graph
    source, target : node
    cutoff : int or None, optional

    Yields
    ------
    list of (u, v) tuples
    """
    _validate_backend_dispatch_keywords(
        "all_simple_edge_paths", backend, backend_kwargs
    )
    Gc = _coerce_arg_to_fnx_graph(G)
    yield from _all_simple_edge_paths_fnx(Gc, source, target, cutoff)


def chain_decomposition(G, root=None, *, backend=None, **backend_kwargs):
    """Return the chain decomposition of *G*.

    A chain decomposition breaks a 2-edge-connected graph into chains
    (sequences of edges forming paths/cycles in a DFS tree).

    Parameters
    ----------
    G : Graph
    root : node, optional

    Yields
    ------
    list of (u, v) tuples
        Each yielded list is a chain.

    br-r37-c1-r4gg6: exact native DFS-cycle-forest path for plain fnx
    Graphs. Unsupported graph-like objects and root-error cases still route
    through the parity helper so NetworkX owns their observable exceptions.
    """
    _validate_backend_dispatch_keywords(
        "chain_decomposition",
        backend,
        backend_kwargs,
    )
    # br-r37-c1-scceager: nx is @not_implemented_for('directed','multigraph')
    # and raises EAGERLY on the call. multigraph is checked first so a
    # MultiDiGraph reports 'multigraph', matching nx.
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    G = _coerce_arg_to_fnx_graph(G)

    def _gen():
        if root is not None and root not in G:
            raise NodeNotFound(f"Root node {root} is not in graph")
        yield from _fnx.chain_decomposition(G, root)

    return _gen()


def bidirectional_dijkstra(G, source, target, weight="weight"):
    """Find shortest path using bidirectional Dijkstra search.

    Parameters
    ----------
    G : Graph
    source, target : node
    weight : str, optional

    Returns
    -------
    (length, path) : tuple

    br-dijkignoreweight: the local fallback calls dijkstra_path/_length
    which now correctly delegate weighted inputs to nx. Only stays on
    fnx's own dijkstra wrappers (which are weight-correct) for
    unit-weight cases.
    """
    if _point_query_uses_private_rows(G):
        return _bidirectional_dijkstra_local(G, source, target, weight=weight)
    # br-r37-c1-bdjkstra: directed multigraphs, callable / non-string weight,
    # and negative / non-finite / non-numeric weights still delegate to nx.
    # Undirected MultiGraph now has the exact native per-key-min kernel below.
    # Everything else runs nx's EXACT bidirectional-Dijkstra in-process on the
    # fnx graph instead of the old local fallback of ``dijkstra_path`` +
    # ``dijkstra_path_length``. That fallback (a) paid TWO full fnx->nx
    # conversions per call — ~107ms for a single-pair query on n=3000, ~100x
    # SLOWER than nx — and (b) returned the *plain* Dijkstra path, which diverges
    # from nx's *bidirectional* path on ~2% of pairs. The in-process search is
    # 14-23x faster than that delegation and byte-exact with
    # ``nx.bidirectional_dijkstra`` (450/450 incl. the bidirectional tie-break).
    if G.is_multigraph():
        if (
            G.is_directed()
            or type(G) is not MultiGraph
            or type(source) not in (str, int)
            or type(target) not in (str, int)
            or _should_delegate_dijkstra_to_networkx(
                G, weight, _require_exact_string_nodes=True, _allow_exact_integer_nodes=True
            )
        ):
            return _bidirectional_dijkstra_local(G, source, target, weight=weight)
        route = "native"
    else:
        route = _dijkstra_weight_route(G, weight)
        if route == "networkx":
            return _bidirectional_dijkstra_local(G, source, target, weight=weight)
    # br-r37-c1-ybw1s: nx checks ``source not in G`` (silent False on unhashable,
    # no hash op) and raises NodeNotFound — not TypeError.
    if source not in G:
        raise NodeNotFound(f"Source {source} is not in G")
    if target not in G:
        raise NodeNotFound(f"Target {target} is not in G")
    # br-r37-c1-k4p0b / p60i1 / 04z53.9170: simple graphs and undirected
    # MultiGraph run an all-Rust kernel, which
    # eliminates the per-explored-node Python AdjacencyView/PyDict tax (~30µs/node)
    # that left the in-process port ~6-10x slower than nx. The native kernel
    # reproduces nx's bidirectional meeting-node tie-break, shared FIFO counter, and
    # path reconstruction byte-for-byte. p60i1 (cc) added the DIRECTED kernel (forward
    # successors / backward predecessors CSR), so directed simple graphs use it too.
    if _native_bidirectional_dijkstra is not None:
        # Push any post-creation edge-attr mutations into the Rust inner graph
        # (edge-only + dirty-gated: a no-op for graphs that were never mutated
        # after construction, which keeps the single-pair query fast). We avoid
        # the heavyweight whole-graph sync, and read the int/float type back
        # from the kernel (``all_int``) rather than touching ``G[u][v]`` here —
        # that access would mark the graph attr-dirty and force a resync on the
        # next call.
        _sync_rust_edge_attrs(G, edge_only=True)
        try:
            length, all_int, path = _native_bidirectional_dijkstra(
                G, source, target, weight, route == "rows"
            )
        except _WeightRowsUnverified:
            path = None
        if path is None:
            return _rerun_with_weight_scan(bidirectional_dijkstra, G, source, target, weight)
        # The Rust kernel accumulates in f64 (byte-exact with nx's arithmetic
        # ORDER); nx preserves Python int arithmetic, so the length is int iff
        # every weight summed along the path is int/bool (else int + float ->
        # float). The f64 value is already exact — only the type is matched.
        return (int(length) if all_int else float(length), path)
    return _bidirectional_dijkstra_local(G, source, target, weight)


def _bidirectional_dijkstra_local(G, source, target, weight):
    """networkx's exact bidirectional-Dijkstra, run in-process on the fnx graph
    (no fnx->nx conversion). Mirrors ``networkx.bidirectional_dijkstra``,
    so the returned ``(length, path)`` is byte-identical — including the
    bidirectional meeting-node tie-break, which differs from a plain ``dijkstra_path``.
    """
    from heapq import heappush as _hpush, heappop as _hpop
    from itertools import count as _count

    if source not in G:
        raise NodeNotFound(f"Source {source} is not in G")
    if target not in G:
        raise NodeNotFound(f"Target {target} is not in G")
    if source == target:
        return (0, [source])
    weight_fn = _weight_function(G, weight)
    dists = [{}, {}]
    preds = [{source: None}, {target: None}]

    def _path(curr, direction):
        ret = []
        while curr is not None:
            ret.append(curr)
            curr = preds[direction][curr]
        return list(reversed(ret)) if direction == 0 else ret

    fringe = [[], []]
    seen = [{source: 0}, {target: 0}]
    counter = _count()
    _hpush(fringe[0], (0, next(counter), source))
    _hpush(fringe[1], (0, next(counter), target))
    neighbors = [G._succ, G._pred] if G.is_directed() else [G._adj, G._adj]
    finaldist = None
    meetnode = None
    direction = 1
    while fringe[0] and fringe[1]:
        direction = 1 - direction
        (dist, _, v) = _hpop(fringe[direction])
        if v in dists[direction]:
            continue
        dists[direction][v] = dist
        if v in dists[1 - direction]:
            return (finaldist, _path(meetnode, 0) + _path(preds[1][meetnode], 1))
        for w, edge_data in neighbors[direction][v].items():
            cost = weight_fn(v, w, edge_data) if direction == 0 else weight_fn(w, v, edge_data)
            if cost is None:
                continue
            vw_length = dist + cost
            if w in dists[direction]:
                if vw_length < dists[direction][w]:
                    raise ValueError("Contradictory paths found: negative weights?")
            elif w not in seen[direction] or vw_length < seen[direction][w]:
                seen[direction][w] = vw_length
                _hpush(fringe[direction], (vw_length, next(counter), w))
                preds[direction][w] = v
                if w in seen[1 - direction]:
                    final_w = vw_length + seen[1 - direction][w]
                    if finaldist is None or finaldist > final_w:
                        finaldist, meetnode = final_w, w
    raise NetworkXNoPath(f"No path between {source} and {target}.")


def attribute_mixing_dict(G, attribute, nodes=None, normalized=False):
    """Return mixing dict for a categorical node attribute.

    Returns
    -------
    dict of dicts
        ``result[a][b]`` counts edges between nodes with attribute
        values a and b.
    """
    attr_map = get_node_attributes(G, attribute)
    is_multigraph = G.is_multigraph()

    # br-r37-c1-amdcount: for the full-graph case (nodes=None) count attribute
    # pairs over the native G.edges() ONCE instead of the attribute_pairs()
    # generator -> mixing_dict two-pass over ~2*|E| tuples (~2.1x nx). An
    # undirected non-loop edge contributes (a,b) and (b,a); a self-loop (a,a)
    # once; a directed edge (a,b) once; a multigraph parallel edge once per
    # key -- identical to nx's per-(u, neighbour) G.adjacency() enumeration.
    # Inner dicts are created only when an edge produces a pair, so attribute
    # values of edge-less nodes are absent (matching the generator + the
    # matrix mapping's key set).
    if nodes is None:
        directed = G.is_directed()
        result: dict = {}

        def _add(a, b):
            # nx's mixing_dict creates an (empty) row for BOTH endpoints of
            # every pair, so an attribute value appearing only as a TARGET
            # still gets a key. Mirror that for matrix-mapping parity.
            inner = result.get(a)
            if inner is None:
                inner = result[a] = {}
            if b not in result:
                result[b] = {}
            inner[b] = inner.get(b, 0) + 1

        if is_multigraph:
            for u, v in G.edges():
                a = attr_map.get(u)
                b = attr_map.get(v)
                _add(a, b)
                if not directed and u != v:
                    _add(b, a)
        else:
            for u, v in G.edges():
                a = attr_map.get(u)
                b = attr_map.get(v)
                _add(a, b)
                if not directed and u != v:
                    _add(b, a)
        if normalized:
            total = sum(sum(row.values()) for row in result.values())
            if total:
                for row in result.values():
                    for key in row:
                        row[key] /= total
        return result

    nodes = set(nodes)

    def attribute_pairs():
        for u, nbrsdict in G._adj.items():
            if u not in nodes:
                continue
            uattr = attr_map.get(u)
            if is_multigraph:
                for v, keys in nbrsdict.items():
                    vattr = attr_map.get(v)
                    for _ in keys:
                        yield (uattr, vattr)
            else:
                for v in nbrsdict:
                    vattr = attr_map.get(v)
                    yield (uattr, vattr)

    return mixing_dict(attribute_pairs(), normalized=normalized)


def attribute_mixing_matrix(G, attribute, nodes=None, mapping=None, normalized=True):
    """Return the attribute mixing matrix.

    Returns
    -------
    numpy.ndarray
    """
    import numpy as np

    mixing = attribute_mixing_dict(G, attribute, nodes=nodes, normalized=False)
    if mapping is None:
        # br-mixmap: same fix as degree_mixing_matrix — default mapping
        # must be the set union of outer + inner keys (matching nx's
        # _dict_to_numpy_array2), not just the outer dict's insertion
        # order. Otherwise inner-only attribute values are silently
        # dropped from the matrix and row/col positions diverge from nx.
        s = set(mixing.keys())
        for _, inner in mixing.items():
            s.update(inner.keys())
        mapping = dict(zip(s, range(len(s))))

    matrix = np.zeros((len(mapping), len(mapping)))
    for left, inner in mixing.items():
        if left not in mapping:
            continue
        for right, value in inner.items():
            if right not in mapping:
                continue
            matrix[mapping[left], mapping[right]] = value
    if normalized and matrix.sum() > 0:
        matrix = matrix / matrix.sum()
    return matrix


# ---------------------------------------------------------------------------
# Additional generators
# ---------------------------------------------------------------------------


def dense_gnm_random_graph(n, m, seed=None, *, create_using=None):
    """Return a dense G(n,m) random graph."""
    rng = _generator_random_state(seed)
    graph = _checked_create_using(
        create_using,
        directed=False,
        multigraph=False,
        default=Graph,
    )
    mmax = n * (n - 1) // 2
    if m >= mmax:
        return complete_graph(n, create_using=graph)

    graph = empty_graph(n, create_using=graph)
    if n == 1:
        return graph

    # br-dense-gnm-batch: the rejection sampler never reads the graph, so
    # accepted edges accumulate in generated order and commit through a
    # single add_edges_from at the sole exit point (same lever as the
    # gnp/fast_gnp create_using paths). The rng.randrange draw sequence and
    # edge order are unchanged, so the result is byte-identical to the
    # per-edge add_edge loop while paying one PyO3 crossing instead of O(m).
    u = 0
    v = 1
    t = 0
    k = 0
    edges = []
    while True:
        if rng.randrange(mmax - t) < m - k:
            edges.append((u, v))
            k += 1
            if k == m:
                graph.add_edges_from(edges)
                return graph
        t += 1
        v += 1
        if v == n:
            u += 1
            v = u + 1


def random_labeled_tree(n, *, seed=None):
    """Return a uniformly random labeled tree."""
    rng = _generator_random_state(seed)  # br-r37-c1-cdf1v: resolved first, as nx's decorator
    if n == 0:
        raise NetworkXPointlessConcept("the null graph is not a tree")
    return _random_tree_internal(n, seed=rng)


def _generator_random_state(seed):
    """Return a stdlib random state matching NetworkX's common seed semantics."""
    import random as _random

    class _NumpyRandIntAdapter:
        def __init__(self, rng):
            self._rng = rng

        def randint(self, low, high):
            if hasattr(self._rng, "integers"):
                return int(self._rng.integers(low, high + 1))
            return int(self._rng.randint(low, high + 1))

    if seed is None or seed is _random:
        return _random._inst
    if isinstance(seed, _random.Random):
        return seed
    if isinstance(seed, int):
        return _random.Random(seed)

    try:
        import numpy as np
    except ImportError:
        np = None

    if np is not None:
        try:
            from networkx.utils.misc import PythonRandomInterface, PythonRandomViaNumpyBits
        except ImportError:
            pass
        else:
            # br-r37-c1-cdf1v: an already-wrapped numpy RNG passes through, as
            # in nx's create_py_random_state - a helper handed the wrapper its
            # caller made (random_labeled_rooted_tree -> the tree draw) must
            # keep drawing from it rather than raise.
            if isinstance(seed, (PythonRandomInterface, PythonRandomViaNumpyBits)):
                return seed
        if seed is np.random:
            try:
                from networkx.utils.misc import create_py_random_state

                return create_py_random_state(seed)
            except ImportError:
                return _NumpyRandIntAdapter(np.random.mtrand._rand)
        if isinstance(seed, np.random.Generator | np.random.RandomState):
            try:
                from networkx.utils.misc import create_py_random_state

                return create_py_random_state(seed)
            except ImportError:
                return _NumpyRandIntAdapter(seed)
    raise ValueError(f"{seed} cannot be used to generate a random.Random instance")


def _generator_tree_from_edges(edges, n_nodes, root=None, roots=None):
    """Build a FrankenNetworkX graph from edge pairs plus optional root metadata."""
    graph = Graph()
    graph.add_nodes_from(range(n_nodes))
    graph.add_edges_from(edges)
    if root is not None:
        graph.graph["root"] = root
    if roots is not None:
        graph.graph["roots"] = roots
    return graph


def _num_rooted_trees(n, cache_trees):
    """Return the number of unlabeled rooted trees with ``n`` nodes."""
    for n_i in range(len(cache_trees), n + 1):
        cache_trees.append(
            sum(
                d * cache_trees[n_i - j * d] * cache_trees[d]
                for d in range(1, n_i)
                for j in range(1, (n_i - 1) // d + 1)
            )
            // (n_i - 1)
        )
    return cache_trees[n]


def _select_jd_trees(n, cache_trees, seed):
    """Select the ``(j, d)`` pair used by the exact rooted-tree sampler."""
    p = seed.randint(0, _num_rooted_trees(n, cache_trees) * (n - 1) - 1)
    cumsum = 0
    for d in range(n - 1, 0, -1):
        for j in range(1, (n - 1) // d + 1):
            cumsum += (
                d
                * _num_rooted_trees(n - j * d, cache_trees)
                * _num_rooted_trees(d, cache_trees)
            )
            if p < cumsum:
                return j, d
    raise RuntimeError("failed to select rooted-tree decomposition")


def _random_unlabeled_rooted_tree_exact(n, cache_trees, seed):
    """Return an exact random unlabeled rooted tree as ``(edges, node_count)``."""
    if n == 1:
        return [], 1
    if n == 2:
        return [(0, 1)], 2

    j, d = _select_jd_trees(n, cache_trees, seed)
    tree_edges, tree_nodes = _random_unlabeled_rooted_tree_exact(
        n - j * d,
        cache_trees,
        seed,
    )
    subtree_edges, subtree_nodes = _random_unlabeled_rooted_tree_exact(d, cache_trees, seed)
    tree_edges.extend((0, subtree_nodes * i + tree_nodes) for i in range(j))
    for _ in range(j):
        tree_edges.extend((left + tree_nodes, right + tree_nodes) for left, right in subtree_edges)
        tree_nodes += subtree_nodes

    return tree_edges, tree_nodes


def _num_rooted_forests(n, q, cache_forests):
    """Return the number of unlabeled rooted forests with ``n`` nodes."""
    for n_i in range(len(cache_forests), n + 1):
        q_i = min(n_i, q)
        cache_forests.append(
            sum(
                d * cache_forests[n_i - j * d] * cache_forests[d - 1]
                for d in range(1, q_i + 1)
                for j in range(1, n_i // d + 1)
            )
            // n_i
        )
    return cache_forests[n]


def _select_jd_forests(n, q, cache_forests, seed):
    """Select the ``(j, d)`` pair used by the exact rooted-forest sampler."""
    p = seed.randint(0, _num_rooted_forests(n, q, cache_forests) * n - 1)
    cumsum = 0
    for d in range(q, 0, -1):
        for j in range(1, n // d + 1):
            cumsum += (
                d
                * _num_rooted_forests(n - j * d, q, cache_forests)
                * _num_rooted_forests(d - 1, q, cache_forests)
            )
            if p < cumsum:
                return j, d
    raise RuntimeError("failed to select rooted-forest decomposition")
