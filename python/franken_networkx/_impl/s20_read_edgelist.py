

def read_edgelist(
    path,
    comments="#",
    delimiter=None,
    create_using=None,
    nodetype=None,
    data=True,
    edgetype=None,
    encoding="utf-8",
    *,
    backend=None,
    **backend_kwargs,
):
    """Read a graph from a list of edges.

    Delegates to NetworkX's parser (br-rdedge) so nx-written files round-trip
    and all nx kwargs (``nodetype``, ``create_using``, ``data``, ...) are
    honoured. The Rust-native ``read_edgelist`` only accepts ``(path,)``.
    """
    mode = backend_kwargs.pop("mode", None)
    _validate_backend_dispatch_keywords("read_edgelist", backend, backend_kwargs)
    if mode is not None or _rust_get_compatibility_mode() == "hardened":
        return _read_edgelist_in_mode(
            path,
            mode,
            comments=comments,
            delimiter=delimiter,
            create_using=create_using,
            nodetype=nodetype,
            data=data,
            encoding=encoding,
        )
    if (
        comments == "#"
        and delimiter is None
        and (create_using is None or create_using is Graph)
        and nodetype is None
        and (data is True or data is False)
        and edgetype is None
        and encoding == "utf-8"
        and (isinstance(path, str) or hasattr(path, "__fspath__"))
    ):
        p_str = path if isinstance(path, str) else str(path.__fspath__())
        if not p_str.endswith((".gz", ".bz2")):
            try:
                native = _fnx.read_edgelist_simple(
                    p_str,
                    "data_true" if data is True else "data_false",
                )
                if native is not None:
                    return native
            except Exception:
                pass
        native = _read_edgelist_simple_via_open_file(
            path,
            encoding,
            "data_true" if data is True else "data_false",
        )
        if native is not None:
            return native

    from .readwrite import parse_edgelist as _parse_edgelist

    return _read_decoded_lines_via_open_file(
        path,
        encoding,
        lambda lines: _parse_edgelist(
            lines,
            comments=comments,
            delimiter=delimiter,
            create_using=create_using,
            nodetype=nodetype,
            data=data,
        ),
        keep_str_lines=True,
    )


def _read_decoded_lines_via_open_file(path, encoding, parse, *, keep_str_lines=False):
    """Open ``path`` under the ``open_file`` contract (str/Path/file handle,
    gzip/bz2 by suffix) and feed decoded lines to ``parse``.

    ``keep_str_lines``: a text-mode handle yields str lines, which nx's
    read_edgelist passes through undecoded; its adjlist readers decode every
    line, so they raise on one (br-r37-c1-6luun)."""

    def _read(fobj):
        if keep_str_lines:
            return parse(
                line if isinstance(line, str) else line.decode(encoding) for line in fobj
            )
        return parse(line.decode(encoding) for line in fobj)

    return _open_path_and_call(path, "rb", _read)


def _read_edgelist_simple_via_open_file(path, encoding, mode):
    """Bulk-decode a default edge list and hand one payload to Rust."""

    def _read(fobj):
        return _fnx.parse_edgelist_simple_text(fobj.read().decode(encoding), mode)

    return _open_path_and_call(path, "rb", _read)


def read_adjlist(
    path,
    comments="#",
    delimiter=None,
    create_using=None,
    nodetype=None,
    encoding="utf-8",
    *,
    backend=None,
    **backend_kwargs,
):
    """Read a graph from an adjacency list.

    br-r37-c1-rdadjnative: route to the native ``parse_adjlist`` (bulk node +
    edge construction, byte-exact node/edge order vs nx) instead of delegating
    the entire parse+build to nx and converting the result — that paid nx's
    per-node graph ops PLUS an fnx<-nx conversion (~3.8x slower, 0.26x). nx's
    ``open_file`` still handles the path / gzip / bz2 / encoding edge cases, so
    behaviour is unchanged; only the parser + builder become native.
    """
    mode = backend_kwargs.pop("mode", None)
    _validate_backend_dispatch_keywords("read_adjlist", backend, backend_kwargs)
    if mode is not None or _rust_get_compatibility_mode() == "hardened":
        if (
            comments == "#"
            and delimiter is None
            and (create_using is None or create_using is Graph)
            and nodetype is None
        ):
            return _rust_read_adjlist(path, mode=mode)
    if (
        comments == "#"
        and delimiter is None
        and nodetype is None
        and encoding == "utf-8"
        and isinstance(path, str)
        and not path.endswith((".gz", ".bz2"))
        and (create_using is None or create_using is Graph)
    ):
        native = _fnx.read_adjlist_simple(path)
        if native is not None:
            return native
    from .readwrite import parse_adjlist as _parse_adjlist

    return _read_decoded_lines_via_open_file(
        path,
        encoding,
        lambda lines: _parse_adjlist(
            lines,
            comments=comments,
            delimiter=delimiter,
            create_using=create_using,
            nodetype=nodetype,
        ),
    )


def write_adjlist(G, path, comments="#", delimiter=" ", encoding="utf-8"):
    """Write a graph as an adjacency list.

    br-r37-c1-wadj-parity: previously the simple-graph default path
    used a Rust-native writer that omitted the timestamped comment
    header AND the trailing newline that nx writes. That broke
    byte-level diff parity for tooling that compares snapshots
    across libraries (and could affect line-oriented readers that
    require newline-terminated files). Always delegate to nx for
    byte-exact output. The Rust writer remains available via
    private name for callers that explicitly want the no-header
    variant; the public `write_adjlist` matches nx exactly.
    """
    # br-cc-wadj-genfast: string/tuple-node graphs paid a full _to_nx(G) conversion
    # inside _write_adjlist_via_nx (0.59x vs nx). fnx's generate_adjlist is byte-
    # identical to nx's, and nx.write_adjlist is exactly its header + a write loop
    # over it, so drive that directly and skip the conversion. Int-labelled graphs
    # keep the existing delegated path (already a win). Byte-exact incl. the GMT
    # header (same-second timestamp, as nx's own snapshots are compared).
    if not _edgelist_native_writer_preserves_node_labels(G):
        return _write_adjlist_generate_fast(G, path, comments, delimiter, encoding)
    return _write_adjlist_via_nx(
        G, path, comments=comments, delimiter=delimiter, encoding=encoding
    )


def write_graphml(
    G,
    path,
    encoding="utf-8",
    prettyprint=True,
    infer_numeric_types=False,
    named_key_ids=False,
    edge_id_from_attribute=None,
):
    """Write GraphML with the full attribute and default-metadata contract.

    The delegated writer preserves its backend's byte-level output. Keep
    the existing simple-graph rejection of unsupported attribute values,
    while admitting the numeric scalar types that GraphML can represent.
    """
    _GRAPHML_OK_TYPES = (bool, int, float, str)
    if not G.is_multigraph():
        for src_iter in (G.nodes(data=True), G.edges(data=True)):
            for record in src_iter:
                data = record[-1]
                if not isinstance(data, dict):
                    continue
                for value in data.values():
                    if not isinstance(value, _GRAPHML_OK_TYPES):
                        try:
                            _graphml_xml_type(value)
                        except TypeError:
                            raise NetworkXError(
                                f"GraphML writer does not support {type(value)} "
                                f"as data values."
                            ) from None
        _validate_graph_graphml_attrs(getattr(G, "graph", {}))
    return _write_graphml_via_nx(
        G,
        path,
        encoding=encoding,
        prettyprint=prettyprint,
        infer_numeric_types=infer_numeric_types,
        named_key_ids=named_key_ids,
        edge_id_from_attribute=edge_id_from_attribute,
    )


def _validate_graph_graphml_attrs(graph_attrs):
    if not isinstance(graph_attrs, dict):
        return
    ok = (bool, int, float, str)
    for name, value in graph_attrs.items():
        # Readers always create the default dictionaries, even when empty.
        # The writer consumes these and the graph ID as control metadata,
        # rather than serializing them as ordinary graph attribute values.
        if name in {"id", "node_default", "edge_default"}:
            continue
        if not isinstance(value, ok):
            try:
                _graphml_xml_type(value)
            except TypeError:
                raise NetworkXError(
                    f"GraphML writer does not support {type(value)} as data values."
                ) from None


def _read_graphml_mode_payload(path):
    """Buffer input with NetworkX's path/compression and ownership contract."""
    from pathlib import Path

    def read_all(stream):
        # ElementTree accepts read(size)-only streams and keeps reading after
        # short reads. Buffer them the same way before choosing a parser.
        first = stream.read(65536)
        if not first:
            return first
        chunks = [first]
        while True:
            chunk = stream.read(65536)
            if not chunk:
                return first[:0].join(chunks)
            chunks.append(chunk)

    # NetworkX's decorator opens str/Path arguments with suffix decompression.
    # ElementTree opens other non-file-like sources literally, including bytes
    # paths, arbitrary PathLike objects, and file descriptors.
    if not isinstance(path, (str, Path)) and not hasattr(path, "read"):
        with open(path, "rb") as stream:
            return read_all(stream)
    return _open_path_and_call(path, "rb", read_all)


class _GraphMLBufferedInput:
    """Replay the first read while retaining the original recovery protocol."""

    def __init__(self, payload, source):
        stream_type = _io.StringIO if isinstance(payload, str) else _io.BytesIO
        self._replay = stream_type(payload)
        self._source = source

    def read(self, *args, **kwargs):
        stream = self._source if self._replay is None else self._replay
        return stream.read(*args, **kwargs)

    def __getattr__(self, name):
        attribute = getattr(self._source, name)
        if name != "seek":
            return attribute

        def seek(*args, **kwargs):
            result = attribute(*args, **kwargs)
            self._replay = None
            return result

        return seek


def _graphml_from_mode_payload(
    payload, *, node_type=str, edge_key_type=int, force_multigraph=False,
    mode=None, parse_string=False,
):
    """Apply native validation/recovery without losing the decoder's options."""
    stream_type = _io.StringIO if isinstance(payload, str) else _io.BytesIO
    graph = _fnx.validate_graphml(stream_type(payload), mode=mode)
    records = graph.decision_records()
    recovered = any(record["action"] == "full_validate" for record in records)
    if not recovered:
        # Native validation remains authoritative. A clean document still
        # needs the complete key/multigraph/type contract; the simple native
        # report alone cannot preserve parallel edges or lexical edge IDs.
        if parse_string:
            from .readwrite import _parse_graphml_via_nx

            converted = _parse_graphml_via_nx(
                payload, node_type=node_type,
                edge_key_type=edge_key_type, force_multigraph=force_multigraph,
            )
        else:
            converted = _read_graphml_via_nx(
                stream_type(payload), node_type=node_type,
                edge_key_type=edge_key_type, force_multigraph=force_multigraph,
            )
        _fnx.copy_readwrite_policy(graph, converted)
        return converted
    parallel = any(
        record["rationale"] == "graphml parallel edges require multigraph reconstruction"
        for record in records
    )
    if parallel or force_multigraph or edge_key_type is not int:
        raise NetworkXNotImplemented(
            "GraphML recovery with parallel edges or non-default multigraph/key options "
            "is not supported"
        )
    if node_type is not str:
        mapping = {}
        for node in graph:
            converted_node = node_type(node)
            # Native canonicalization also supports ingestion values that
            # are not legal NetworkX labels. This public API requires keys.
            # Dict insertion, not hash(), preserves the interpreter's
            # mapping-key TypeError wording (including Python 3.14).
            {converted_node: None}
            mapping[node] = converted_node
        # The existing native relabel kernel retains the parser's runtime
        # policy, ledger, attrs and insertion order for non-merging labels.
        converted = graph._native_relabel_copy(mapping)
        if converted is not None:
            graph = converted
        else:
            # Merging labels take the general relabel path. Reuse the
            # original graph afterwards: a freshly constructed graph would
            # lose recovery decisions (and could inherit the ambient mode).
            with compatibility_mode(graph.mode):
                converted = relabel_nodes(graph, mapping, copy=True)
            graph.clear()
            _copy_graph_into(converted, graph)
    return graph


def read_graphml(
    path,
    node_type=str,
    edge_key_type=int,
    force_multigraph=False,
    *,
    backend=None,
    **backend_kwargs,
):
    """Read a graph in GraphML format.

    Strict reads share the string parser's native route and option guards.
    Explicit modes and hardened reads use the native recovery policy; typed
    node labels retain that policy and its decision ledger.
    """
    mode = backend_kwargs.pop("mode", None)
    _validate_backend_dispatch_keywords("read_graphml", backend, backend_kwargs)
    if mode is not None or _rust_get_compatibility_mode() == "hardened":
        return _graphml_from_mode_payload(
            _read_graphml_mode_payload(path), node_type=node_type,
            edge_key_type=edge_key_type, force_multigraph=force_multigraph,
            mode=mode,
        )
    # Use the same parser for str/Path inputs and caller-owned streams.
    # Its guards retain the full decoder for parallel edges and merging labels.
    # The parser's fallback calls NetworkX directly, so this cannot recurse.
    # Literal bytes/custom paths retain the original reader: its namespace
    # recovery tries to seek the original source, which is observable on errors.
    from pathlib import Path

    if (
        (node_type is str or node_type is int)
        and edge_key_type is int
        and not force_multigraph
        and (isinstance(path, (str, Path)) or hasattr(path, "read"))
    ):
        def read(source):
            payload = _read_graphml_mode_payload(source)
            return _parse_graphml_payload(
                payload, node_type=node_type, parse_string=False, file_source=source
            )

        # Keep owned files open through fallback. NetworkX's missing-namespace
        # recovery seeks the original stream to zero, which can expose a prefix
        # before its initial position or raise on a nonseekable/sized-only stream.
        return _open_path_and_call(path, "rb", read)
    return _read_graphml_via_nx(
        path,
        node_type=node_type,
        edge_key_type=edge_key_type,
        force_multigraph=force_multigraph,
    )


def write_gml(G, path, stringizer=None):
    """Write a graph in GML format.

    Delegates to NetworkX's writer (br-wgmldr / br-r37-c1-qqvu4)
    so the on-disk format matches nx byte-for-byte: nx assigns
    sequential int IDs starting at 0 and puts the original node
    value in a ``label`` field; the Rust fast path used the raw
    node value as ``id`` which broke cross-library roundtrips.
    """
    return _write_gml_via_nx(G, path, stringizer=stringizer)


def read_gml(
    path,
    label="label",
    destringizer=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Read a graph in GML format.

    Delegates to NetworkX's parser (br-rgmlnx) so typed scalar
    attributes, ``label``, and ``destringizer`` preserve upstream
    semantics. The raw Rust parser remains available as ``_fnx.read_gml``.
    """
    mode = backend_kwargs.pop("mode", None)
    _validate_backend_dispatch_keywords("read_gml", backend, backend_kwargs)
    if mode is not None or _rust_get_compatibility_mode() == "hardened":
        return _rust_read_gml(path, label=label, destringizer=destringizer, mode=mode)
    # No native fast path for the default call: the Rust parser drops
    # repeated-key lists, backslashes and +INF/NAN typing, and ignores the
    # multigraph flag (see test_read_gml_default_roundtrips_like_networkx).
    return _read_gml_via_nx(path, label=label, destringizer=destringizer)


def read_json_graph(path, *, mode=None):
    """Read a graph serialized as JSON node-link format.

    Supports optional `mode` ('strict' or 'hardened'). In hardened mode,
    bounded recovery is performed for malformed JSON or invalid edge records,
    logging events to the graph's decision record ledger.
    """
    return _rust_read_json_graph(path, mode=mode)


def is_semiconnected(G):
    """Returns True if the graph is semiconnected, False otherwise."""
    # For every pair, reachability in at least one direction is invariant.
    root = _reverse_view_root(G)
    if root is not None:
        G = root
    # br-r37-c1-0555d: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    if len(G) == 0:
        raise NetworkXPointlessConcept("Connectivity is undefined for the null graph.")
    return _raw_is_semiconnected(G)


def attracting_components(G):
    """Generates the attracting components in ``G``."""
    # br-r37-c1-0555d: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    # br-r37-c1-64xcg / br-r37-c1-n4j4k: networkx yields the sink components
    # of strongly_connected_components, in its order and as the very sets it
    # built (it walks the condensation's nodes), so each iterates in that
    # algorithm's order; the native kernel only says which components attract.
    attracting = set(_itertools.chain.from_iterable(_raw_attracting_components(G)))
    return (
        component
        for component in strongly_connected_components(G)
        if next(iter(component)) in attracting
    )


def number_attracting_components(G):
    """Returns the number of attracting components in ``G``."""
    # br-r37-c1-0555d: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    return _raw_number_attracting_components(G)


def is_attracting_component(G):
    """Returns True if ``G`` consists of a single attracting component."""
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    components = list(attracting_components(G))
    if len(components) == 1:
        return len(components[0]) == len(G)
    return False


def complete_graph(n, create_using=None, *, backend=None, **backend_kwargs):
    """Return the complete graph K_n."""
    _validate_backend_dispatch_keywords("complete_graph", backend, backend_kwargs)
    n, nodes = _nodes_or_number_local(n)
    if create_using is None and isinstance(n, _numbers.Integral):
        return _rust_complete_graph(int(n))

    # br-r37-c1-completelist: a consecutive-int node list [0..k-1] is exactly
    # K_k on the default labels, so route it to the native _rust_complete_graph
    # kernel (the int fast path) — this is the shape lollipop_graph /
    # barbell_graph pass for their (integer-m) bell, and it makes them faster
    # than nx. Byte-identical: complete_graph(list(range(k))) and
    # complete_graph(k) are the same K_k. O(V) check, cheap vs the O(V^2) edges.
    if create_using is None and list(nodes) == list(range(len(nodes))):
        return _rust_complete_graph(len(nodes))

    graph = _classic_graph_from_create_using(create_using)
    _add_nodes_in_order(graph, nodes)
    if len(nodes) > 1:
        edges = _itertools.permutations(nodes, 2) if graph.is_directed() else _combinations(nodes, 2)
        # br-r37-c1-completelist: the non-int / create_using path added the
        # O(V^2) clique edges one at a time (~125k per-edge add_edge PyO3 calls
        # for K500 = ~6x slower than nx, which uses a single G.add_edges_from).
        # Mirror nx: one bulk add_edges_from over the same combinations/
        # permutations stream — byte-identical edge enumeration, hits the native
        # batch path. Fixes complete_graph(list/create_using) and its callers
        # (lollipop_graph, barbell_graph, ...).
        graph.add_edges_from(edges)
    return graph


def cycle_graph(n, create_using=None):
    """Return the cycle graph C_n.

    br-r37-c1-o97vk RESOLVED (generators arc): the kernel's closing
    edge now emits (n-1, 0) LAST like nx's cyclic pairwise — native
    fast path re-enabled for the int/default case (verified
    n=1,2,3,4,5,8,12).
    """
    n_value, nodes = _nodes_or_number_local(n)
    if create_using is None and isinstance(n_value, _numbers.Integral) and n_value >= 0:
        from franken_networkx._fnx import cycle_graph as _rust_cycle_graph

        return _rust_cycle_graph(n_value)
    n = n_value
    graph = _classic_graph_from_create_using(create_using)
    _add_nodes_in_order(graph, nodes)
    if nodes:
        # br-r37-c1-cycbatch (cc): the create_using path emitted edges via a
        # per-edge add_edge loop (~0.39x vs nx on a directed C_n); collect the
        # cyclic pairwise stream + the wrap-around close and commit through ONE
        # add_edges_from (nx itself uses pairwise(nodes, cyclic=True)). The close
        # stays LAST (matches nx order; n=1 -> the (0,0) self-loop).
        edges = list(_itertools.pairwise(nodes))
        edges.append((nodes[-1], nodes[0]))
        graph.add_edges_from(edges)
    return graph


def empty_graph(n=0, create_using=None, default=_NETWORKX_GRAPH_DEFAULT):
    """Return the empty graph with n nodes and zero edges."""
    n, nodes = _nodes_or_number_local(n)
    default_graph_type = _classic_default_graph_type(default)
    if create_using is None and default_graph_type is Graph and isinstance(n, _numbers.Integral):
        return _rust_empty_graph(int(n))

    graph = _classic_graph_from_create_using(create_using, default=default_graph_type)
    _add_nodes_in_order(graph, nodes)
    return graph


def path_graph(n, create_using=None, *, backend=None, **backend_kwargs):
    """Return the path graph P_n."""
    _validate_backend_dispatch_keywords("path_graph", backend, backend_kwargs)
    n, nodes = _nodes_or_number_local(n)
    if create_using is None and isinstance(n, _numbers.Integral):
        return _rust_path_graph(int(n))

    graph = _classic_graph_from_create_using(create_using)
    _add_nodes_in_order(graph, nodes)
    # br-r37-c1-cycbatch (cc): batch the create_using path's pairwise edges
    # through ONE add_edges_from instead of the per-edge add_edge loop
    # (~0.38x vs nx on a directed P_n) — byte-identical edge order.
    graph.add_edges_from(_itertools.pairwise(nodes))
    return graph


def star_graph(n, create_using=None):
    """Return the star graph on n + 1 nodes."""
    n, nodes = _nodes_or_number_local(n)
    if isinstance(n, _numbers.Integral):
        nodes.append(int(n))

    graph = _classic_graph_from_create_using(create_using)
    _add_nodes_in_order(graph, nodes)
    if len(nodes) > 1:
        hub = nodes[0]
        # br-r37-c1-starwheel-bulk: the native _rust_star_graph kernel was ~2x
        # SLOWER than this single bulk add_edges_from (its dual-rep PyGraph
        # construction substrate exceeds the batch path on the n-edge star).
        # Drop it; emit all hub spokes through ONE add_edges_from. Byte-exact:
        # node order [0..n] and edge order ((hub,1),(hub,2),...) match nx.
        graph.add_edges_from((hub, node) for node in nodes[1:])
    if type(graph) is Graph:
        vars(graph)["_fnx_star_shape"] = (graph.nodes_seq, graph.edges_seq, len(nodes))
    return graph


# ---------------------------------------------------------------------------
# Bipartite algorithms — pure Python wrappers over Rust primitives
# ---------------------------------------------------------------------------








# br-r37-c1-bia-removed: ``biadjacency_matrix`` and
# ``from_biadjacency_matrix`` were never exposed at nx top level
# (only via ``nx.bipartite``).  fnx exported them at top level as
# redundant Python re-implementations, masking the AttributeError
# nx raises for drop-in callers writing ``nx.biadjacency_matrix``.
# The functions live exclusively at ``fnx.bipartite.biadjacency_
# matrix`` (which delegates to nx) per nx 3.x layout.  Module
# ``__getattr__`` traps top-level access to the same AttributeError
# nx emits.


def projected_graph(B, nodes, multigraph=False, *, backend=None, **backend_kwargs):
    """Return the projection of a bipartite graph onto one set of nodes.

    Two nodes in the projection are connected if they share a neighbor
    in the original bipartite graph. If multigraph=True, one edge is
    added per shared neighbor (returns MultiGraph).
    """
    _validate_backend_dispatch_keywords("projected_graph", backend, backend_kwargs)
    if B.is_multigraph():
        raise NetworkXError("not defined for multigraphs")

    nodes = list(nodes)
    nak = getattr(B, "_native_adjacency_keys", None)
    if nak is not None and type(B) in (Graph, DiGraph):
        directed = type(B) is DiGraph
        adj = {node: list(nbrs) for node, nbrs in nak()}
        if multigraph:
            pred = {n: set(B.pred[n]) for n in B} if directed else None
            G = MultiDiGraph() if directed else MultiGraph()
            G.graph.update(B.graph)
            G.add_nodes_from((n, B.nodes[n]) for n in nodes)
            for u in nodes:
                au = set(adj[u])
                nbrs2 = {v for nbr in adj[u] for v in adj[nbr] if v != u}
                for n in nbrs2:
                    links = au & (pred[n] if directed else set(adj[n]))
                    for l in links:
                        if not G.has_edge(u, n, l):
                            G.add_edge(u, n, key=l)
            return G
        G = DiGraph() if directed else Graph()
        G.graph.update(B.graph)
        G.add_nodes_from((n, B.nodes[n]) for n in nodes)
        proj_edges = []
        for u in nodes:
            nbrs2 = {v for nbr in adj[u] for v in adj[nbr] if v != u}
            proj_edges.extend((u, n) for n in nbrs2)
        G.add_edges_from(proj_edges)
        return G

    if multigraph:
        G = MultiDiGraph() if B.is_directed() else MultiGraph()
        G.graph.update(B.graph)
        for node in nodes:
            G.add_node(node, **dict(B.nodes[node]))
        for u in nodes:
            nbrs2 = {v for nbr in B[u] for v in B[nbr] if v != u}
            for v in nbrs2:
                if B.is_directed():
                    links = set(B[u]) & set(B.pred[v])
                else:
                    links = set(B[u]) & set(B[v])
                for link in links:
                    if not G.has_edge(u, v, link):
                        G.add_edge(u, v, key=link)
    else:
        G = DiGraph() if B.is_directed() else Graph()
        G.graph.update(B.graph)
        for node in nodes:
            G.add_node(node, **dict(B.nodes[node]))
        # br-projected-batch: the projection edge loop reads only the input B
        # (never the result G), and the projected nodes are pre-added above, so
        # the shared-neighbor pairs accumulate in the exact (u, then nbrs2-set
        # iteration) order and commit through a single add_edges_from instead of
        # an O(m) per-edge PyO3 add_edge loop. Edge + node order are unchanged
        # => byte-identical to the per-edge build.
        edges = []
        for u in nodes:
            nbrs2 = {v for nbr in B[u] for v in B[nbr] if v != u}
            edges.extend((u, v) for v in nbrs2)
        G.add_edges_from(edges)

    return G






































# ---------------------------------------------------------------------------
# Community detection — additional algorithms
# ---------------------------------------------------------------------------








# ---------------------------------------------------------------------------
# Graph attribute helpers (high-frequency NetworkX utilities)
# ---------------------------------------------------------------------------


def _edge_attribute_dict(G, edge):
    if G.is_multigraph():
        u, v, key = edge
        try:
            return G[u][v][key]
        except KeyError:
            if G.is_directed():
                raise
            return G[v][u][key]

    u, v = edge
    try:
        return G[u][v]
    except KeyError:
        if G.is_directed():
            raise
        return G[v][u]


def _native_edge_mapping_has_exact_tuple_keys(values, arity):
    """Whether *values* is safe for the native bulk edge-attribute path."""
    return type(values) is dict and all(
        type(edge) is tuple and len(edge) == arity for edge in values
    )

def set_node_attributes(G, values, name=None):
    """_Set node attributes from a dictionary or scalar.

    Parameters
    ----------
    G : Graph
        The graph to modify.
    values : dict or scalar
        If a dict keyed by node, ``values[node]`` is the attribute value.
        If a dict keyed by node mapping to dicts, each inner dict is merged
        into the node's attributes. If a scalar, set it for all nodes.
    name : str, optional
        Attribute name. Required when *values* is a dict of scalars or a scalar.
    """
    if isinstance(values, _Mapping):
        if name is not None:
            # br-r37-c1-snabulk: one native pass over the values dict
            # (was 3 PyO3 round-trips/node: has_node + G.nodes[n] +
            # setitem). node_py_attrs is the authoritative store.
            native = getattr(G, "_native_set_node_attribute_scalar", None)
            if native is not None and isinstance(values, dict):
                native(values, name)
                return
            for node, value in values.items():
                if G.has_node(node):
                    G.nodes[node][name] = value
            return

        # br-r37-c1-snabulk-dict (cc): native one-pass for the {node: attrdict}
        # form (was a per-node G.nodes[node] NodeView __getitem__ + update,
        # ~0.27x vs nx). node_py_attrs is authoritative across all graph types.
        if isinstance(values, dict):
            native = getattr(G, "_native_set_node_attributes_dict", None)
            if native is not None:
                native(values)
                return
        for node, attrs in values.items():
            if G.has_node(node):
                G.nodes[node].update(attrs)
        return

    if name is not None:
        # br-r37-c1-setattrbcast (cc): native one-pass broadcast onto every node
        # (was a per-node NodeView __getitem__ loop, ~0.22x vs nx).
        native = getattr(G, "_native_broadcast_node_attribute", None)
        if native is not None:
            native(name, values)
            return
        for node in G.nodes():
            G.nodes[node][name] = values
        return

    values.items()


def get_node_attributes(G, name, default=None):
    """Return a dictionary of node attributes keyed by node.

    Parameters
    ----------
    G : Graph
        The input graph.
    name : str
        Attribute name.

    Returns
    -------
    dict
        ``{node: value}`` for nodes that have the attribute.
    """
    # br-r37-c1-f1uff: short-circuit on the native graph_has_any_attrs check
    # (~0.08us). When it proves NO node/edge carries a Python-visible attr — the
    # common case for "is this optional attr set?" probes (weight, pos, ...) —
    # the result is trivially empty (default=None) or a uniform default, skipping
    # the per-node attribute-dict materialization tax. Otherwise use nx's single-
    # pass nodes(data=True) comprehension; the old per-node ``G.nodes[node]`` loop
    # did N separate Rust->Python attr-dict reconstructions (~2.4x slower).
    no_attrs = type(G) in (Graph, DiGraph) and _fnx.graph_has_any_attrs(G) is False
    if default is None:
        if no_attrs:
            return {}
        return {
            node: attrs[name]
            for node, attrs in G.nodes(data=True)
            if name in attrs
        }
    if no_attrs:
        return {node: default for node in G.nodes()}
    return {node: attrs.get(name, default) for node, attrs in G.nodes(data=True)}


def set_edge_attributes(G, values, name=None):
    """_Set edge attributes from a dictionary or scalar.

    Parameters
    ----------
    G : Graph
        The graph to modify.
    values : dict or scalar
        If a dict keyed by ``(u, v)``, sets the attribute per edge.
        If a scalar, sets it for all edges.
    name : str, optional
        Attribute name. Required when *values* is a scalar.
    """
    if isinstance(values, _Mapping):
        if name is not None:
            # br-r37-c1-seabulk: one native pass over the {(u,v): value}
            # dict (was per-edge G[u][v] resolve + setitem). Native sets
            # the edge_py_attrs mirror + marks edges dirty so the lazy
            # inner flush reaches the kernels. Simple graphs only (Multi
            # edge keys are 3-tuples); others fall back.
            arity = 3 if G.is_multigraph() else 2
            if _native_edge_mapping_has_exact_tuple_keys(values, arity):
                if arity == 2:
                    native = getattr(G, "_native_set_edge_attribute_scalar", None)
                    if native is not None:
                        native(values, name)
                        return
                else:
                    native = getattr(G, "_native_set_edge_attribute_scalar_multi", None)
                    if native is not None:
                        native(values, name)
                        return
            for edge, value in values.items():
                try:
                    _edge_attribute_dict(G, edge)[name] = value
                except KeyError:
                    continue
            return

        # br-r37-c1-seabulk-dict (cc): native one-pass for the {(u,v): attrdict}
        # form. The loop below resolves `G[u][v]` (a full EdgeAttrDict VIEW)
        # per edge (~0.06x vs nx's plain `G._adj[u][v].update`). Simple graphs
        # only (Multi edge keys are 3-tuples; others keep the loop).
        if (
            not G.is_multigraph()
            and _native_edge_mapping_has_exact_tuple_keys(values, 2)
        ):
            native = getattr(G, "_native_set_edge_attributes_dict", None)
            if native is not None:
                native(values)
                return
        for edge, attrs in values.items():
            try:
                _edge_attribute_dict(G, edge).update(attrs)
            except KeyError:
                continue
        return

    if name is not None:
        if G.is_multigraph():
            for u, v, key, attrs in G.edges(keys=True, data=True):
                attrs[name] = values
        else:
            # br-r37-c1-setattrbcast (cc): native one-pass broadcast onto every
            # edge (was a per-edge edges(data=True) loop, ~0.39x vs nx).
            native = getattr(G, "_native_broadcast_edge_attribute", None)
            if native is not None:
                native(name, values)
                return
            for u, v, attrs in G.edges(data=True):
                attrs[name] = values
        return

    values.items()


def get_edge_attributes(G, name, default=None):
    """Return a dictionary of edge attributes keyed by ``(u, v)``.

    Parameters
    ----------
    G : Graph
        The input graph.
    name : str
        Attribute name.

    Returns
    -------
    dict
        ``{(u, v): value}`` for edges that have the attribute.
    """
    # br-r37-c1-f1uff: same native attr-presence short-circuit as
    # get_node_attributes — an absent optional edge attr (weight, capacity, ...)
    # on an attr-free graph resolves to {} without walking edges(data=True).
    if (
        default is None
        and type(G) in (Graph, DiGraph)
        and _fnx.graph_has_any_attrs(G) is False
    ):
        return {}
    # br-r37-c1-w868y: native inner-read fast path for a simple undirected Graph
    # with scalar (int/float/bool) values — avoids the edges(data=True) EdgeView
    # walk (was 0.79x vs nx). Returns None (fall through to the exact walk below)
    # for dirty/mutated graphs, string/non-scalar values (ambiguous py->inner
    # fidelity), and default != None, so nx semantics stay byte-exact.
    if default is None and type(G) is Graph:
        native = _fnx.get_edge_attributes_native(G, name)
        if native is not None:
            return native
    result = {}
    include_missing = default is not None
    if G.is_multigraph():
        for u, v, key, attrs in G.edges(keys=True, data=True):
            if name in attrs:
                result[(u, v, key)] = attrs[name]
            elif include_missing:
                result[(u, v, key)] = default
        return result

    for u, v, attrs in G.edges(data=True):
        if name in attrs:
            result[(u, v)] = attrs[name]
        elif include_missing:
            result[(u, v)] = default
    return result


def create_empty_copy(G, with_data=True):
    """Return an empty copy of *G* (same nodes, no edges).

    Parameters
    ----------
    G : Graph
        The input graph.
    with_data : bool, optional
        If True (default), preserve node attributes.

    Returns
    -------
    H : Graph
        A graph with the same nodes but no edges.
    """
    # br-r37-c1-s8w2p: SubgraphView class can't be empty-constructed.
    H = _concrete_class_for(G)()
    # br-r37-c1-nwejh: feed add_nodes_from a CONCRETE list so its native bulk
    # int-node path can fire — the old NodeView / ``(node, dict(attrs))`` genexpr
    # forms always fell through to the per-node Python add_node loop (the whole
    # cost: ~3x slower than nx). The ``dict(attrs)`` copy was also redundant:
    # add_nodes_from copies attr-dict CONTENTS into a fresh node dict (verified —
    # it never aliases G's dicts). When no node carries attributes (the common
    # case) pass bare keys so the int fast path applies; otherwise pass the
    # (node, attrs) pairs (add_nodes_from snapshots each dict's contents).
    if with_data:
        H.graph.update(dict(G.graph))
        # Bulk-copy keys first, then merge node attrs in one native dict pass.
        # The previous ``add_nodes_from(list(G.nodes(data=True)))`` path fell
        # back to per-node add_node whenever attrs were not losslessly storable
        # in the Rust AttrMap, even though create_empty_copy only needs a shallow
        # Python-visible attr copy.
        native_keys = getattr(G, "_native_node_keys", None)
        if type(G) in (Graph, DiGraph, MultiGraph, MultiDiGraph) and native_keys is not None:
            keys = native_keys()
            if keys is not None:
                has_any_attrs = None
                if type(G) in (Graph, DiGraph):
                    try:
                        has_any_attrs = _fnx.graph_has_any_attrs(G)
                    except Exception:
                        has_any_attrs = None
                H.add_nodes_from(keys)
                if has_any_attrs is not False:
                    node_attrs = dict(G.nodes(data=True))
                    if any(node_attrs.values()):
                        set_node_attributes(H, node_attrs)
            else:
                H.add_nodes_from(list(G.nodes(data=True)))
        else:
            H.add_nodes_from(list(G.nodes(data=True)))
    else:
        keys = G._native_node_keys() if type(G) is Graph else None
        H.add_nodes_from(keys if keys is not None else list(G.nodes()))
    # br-norebuild2: H is already the canonical fnx type from
    # _concrete_class_for(G)(); the _from_nx_graph rebuild was a redundant second
    # full construction of an already-correct fnx graph.
    return H


def number_of_selfloops(G):
    """Return the number of self-loop edges in *G*."""
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-61okz: O(|V|) via has_edge probe when bypass is safe.
    # Was 300x slower than nx because it materialized selfloop_edges
    # tuples just to _count them, and selfloop_edges itself walked the
    # AdjacencyView for every node.
    # br-selfloopnative: native O(|V|) self-loop scan in Rust -- ~14x faster than
    # the per-node has_edge probe (and faster than networkx). Each node has at
    # most one self-loop in a simple graph, so the count is the node count.
    if not G.is_multigraph():
        # br-r37-c1-hkijj: `len(...)` of a node list, NOT the count-returning
        # `_fnx.number_of_selfloops_rust`, and that is deliberate. The count
        # function is exported, unreferenced, and returns identical answers on
        # every class - so replacing this line with it looks like a free cleanup
        # that drops a list materialisation. It would REGRESS DiGraph: it calls
        # `gr.undirected()`, which builds the whole O(|V| + |E|) undirected copy,
        # and that projection was the entire former cost of this function on a
        # DiGraph (~24ms at 3600 edges). `nodes_with_selfloops_rust` grew a
        # directed O(|V|) index scan precisely to avoid it. No test can catch the
        # swap - the outputs are equal - so the guard is this comment plus the
        # routing assertion in tests/python/test_selfloop_count_routing.py.
        try:
            return len(_fnx.nodes_with_selfloops_rust(G))
        except Exception:
            return sum(1 for u in G if G.has_edge(u, u))
    try:
        return _fnx.multigraph_number_of_selfloops_rust(G)
    except Exception:
        pass
    return sum(1 for _ in selfloop_edges(G))


def selfloop_edges(G, data=False, keys=False, default=None):
    """Return an iterator over self-loop edges.

    Parameters
    ----------
    G : Graph
        The input graph.
    data : string or bool, optional
        Return self-loop edges as ``(u, u)`` tuples when ``False``, or include
        edge data when ``True`` or an attribute value when set to a string.
    keys : bool, optional
        If True, include edge keys for multigraphs.
    default : Any, optional
        Default attribute value used when ``data`` names a missing attribute.

    Returns
    -------
    iterator
        _Iterator over self-loop edges.
    """
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_multigraph():
        native_edges = getattr(G, "_native_selfloop_edges", None)
        if native_edges is not None:
            try:
                return native_edges(data, keys=keys, default=default)
            except Exception:
                pass
    elif data is True:
        # br-r37-c1-slgraph (cc): native simple-Graph path for data=True ONLY. The
        # old `G[n]`/`nbrs[n]` per-self-loop-node AtlasView machinery made
        # selfloop_edges(data=True) 0.16x vs nx; the native binding emits the tuples
        # directly, handing out the LIVE attr dict so mutations persist. data=False
        # keeps its faster generator fast path below (native was ~6% slower there);
        # data="<attr>" keeps the Python value path.
        native_edges = getattr(G, "_native_selfloop_edges", None)
        if native_edges is not None:
            try:
                result = native_edges(data, default=default)
                if result is not None:
                    return result
            except Exception:
                pass
    # br-r37-c1-61okz: bypass AdjacencyView for the common case —
    # direct ``has_edge(u, u)`` probe per node skips the AtlasView
    # materialization that the original ``G.adj[node]`` walk did
    # (300-420x slower than nx). Bench on BA500: has_edge-per-node
    # is ~3x faster than raw_nbrs-per-node and ~4x faster than the
    # original AdjacencyView walk.
    _raw_nbrs = _raw_neighbors_dispatch(G)

    def adjacency_entries():
        # br-r37-c1-nodekeys: find the self-loop nodes in node-iteration order,
        # then yield (node, G[node]) — G[node] is the native O(deg) row;
        # G.adj[node] re-materialises the whole (Multi)AdjacencyView per access
        # (data/keys forms TIMED OUT on a MultiGraph). For SIMPLE graphs the
        # native nodes_with_selfloops_rust scan is fast; for MULTIGRAPHS it is
        # slow/wrong (~29ms), so probe has_edge(n, n) (native O(1)) over the
        # bulk node-key list instead.
        if not G.is_multigraph():
            try:
                sl_nodes = list(_fnx.nodes_with_selfloops_rust(G))
            except Exception:
                sl_nodes = [n for n in G if G.has_edge(n, n)]
        else:
            # br-r37-c1-selfloopmulti (cc): native rust self-loop-node scan instead
            # of the O(N) per-node has_edge(n, n) PyO3 probe (multigraph was ~0.05x).
            native_sl = getattr(G, "_native_selfloop_nodes", None)
            if native_sl is not None:
                sl_nodes = native_sl()
            else:
                native_keys = getattr(G, "_native_node_keys", None)
                source = native_keys() if native_keys is not None else G
                sl_nodes = [n for n in source if G.has_edge(n, n)]
        for node in sl_nodes:
            yield node, G[node]

    # br-r37-c1-61okz: simplest case (data=False, keys=False,
    # non-multigraph) — yield ``(n, n)`` tuples via direct has_edge
    # probe. Skips the AtlasView materialization entirely.
    if data is False and keys is False and _raw_nbrs is not None and not G.is_multigraph():
        # br-selfloopnative: native node scan (node-iteration order) instead of a
        # per-node has_edge probe.
        try:
            return ((n, n) for n in _fnx.nodes_with_selfloops_rust(G))
        except Exception:
            return ((n, n) for n in G if G.has_edge(n, n))

    if data is True:
        if G.is_multigraph():
            if keys is True:
                return (
                    (n, n, key, attrs)
                    for n, nbrs in adjacency_entries()
                    for key, attrs in nbrs[n].items()
                )
            return (
                (n, n, attrs)
                for n, nbrs in adjacency_entries()
                for attrs in nbrs[n].values()
            )
        return ((n, n, nbrs[n]) for n, nbrs in adjacency_entries())

    if data is not False:
        if G.is_multigraph():
            if keys is True:
                return (
                    (n, n, key, attrs.get(data, default))
                    for n, nbrs in adjacency_entries()
                    for key, attrs in nbrs[n].items()
                )
            return (
                (n, n, attrs.get(data, default))
                for n, nbrs in adjacency_entries()
                for attrs in nbrs[n].values()
            )
        return (
            (n, n, nbrs[n].get(data, default))
            for n, nbrs in adjacency_entries()
        )

    if G.is_multigraph():
        if keys is True:
            return (
                (n, n, key)
                for n, nbrs in adjacency_entries()
                for key in nbrs[n]
            )
        return (
            (n, n)
            for n, nbrs in adjacency_entries()
            for _ in range(len(nbrs[n]))
        )
    return ((n, n) for n, nbrs in adjacency_entries())


def nodes_with_selfloops(G):
    """Return nodes that have self-loops."""
    # br-selfloopnative: native scan -- preserves networkx's node-iteration order
    # (verified) and is much faster than walking the AdjacencyView.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-oz595: a generator, as nx's (n for n, nbrs in G._adj.items()
    # if n in nbrs) is, scanning when first advanced rather than at the call.
    return _selfloop_nodes_gen(G)


def _selfloop_nodes_gen(G):
    # br-r37-c1-mgselfloopnodes (cc): nodes_with_selfloops_rust raises on
    # multigraphs, so MG/MDG fell to the `node in G.adj[node]` generator that
    # materializes a per-node AdjacencyView (~1175x slower than nx). Route
    # multigraphs to the native _native_selfloop_nodes scan instead (node-order-
    # exact, same as selfloop_edges); simple graphs keep nodes_with_selfloops_rust.
    nodes = None
    if G.is_multigraph():
        nsl = getattr(G, "_native_selfloop_nodes", None)
        if nsl is not None:
            try:
                nodes = nsl()
            except Exception:
                nodes = None
    if nodes is None:
        try:
            nodes = _fnx.nodes_with_selfloops_rust(G)
        except Exception:
            nodes = None
    if nodes is None:
        yield from (node for node in G.adj if node in G.adj[node])
    else:
        yield from nodes


def all_neighbors(graph, node):
    """Return all neighbors of *node* in *graph* (predecessors + successors on DiGraph).

    First parameter named ``graph`` to match networkx's public signature.
    For undirected graphs, equivalent to ``graph.neighbors(node)``.
    For directed graphs, returns predecessors followed by successors.
    """
    if graph.is_directed():
        return _itertools.chain(graph.predecessors(node), graph.successors(node))
    return graph.neighbors(node)


def is_path(G, path):
    """Return whether or not the specified path exists in *G*."""
    if type(G) in (Graph, DiGraph, MultiGraph, MultiDiGraph):
        try:
            return _fnx.path_exists_rust(G, path)
        except (KeyError, TypeError):
            return False
    try:
        return all(nbr in G[node] for node, nbr in _itertools.pairwise(path))
    except (KeyError, TypeError):
        return False


def path_weight(G, path, weight):
    """Return the total cost associated with *path* using edge attribute *weight*."""
    if not is_path(G, path):
        raise NetworkXNoPath("path does not exist")

    # br-r37-c1-ykqs0: native single-call summation for simple, clean graphs —
    # avoids the per-step ``G[node]`` AtlasView/row-keydict build (the profiled
    # ~0.27x bottleneck). Returns None (fall through to the exact Python loop
    # below) for multigraphs, mutated/unsynced edge dicts, and missing/
    # non-numeric weights, so the fallback preserves byte-exact nx semantics.
    if type(G) in (Graph, DiGraph):
        native = _fnx.path_weight_rust(G, path, weight)
        if native is not None:
            return native

    cost = 0
    if G.is_multigraph():
        for node, nbr in _itertools.pairwise(path):
            cost += min(attrs[weight] for attrs in G[node][nbr].values())
        return cost

    for node, nbr in _itertools.pairwise(path):
        cost += G[node][nbr][weight]
    return cost


def add_path(G_to_add_to, nodes_for_path, **attr):
    """Add a path of edges to *G*."""
    # br-r37-c1-addpathbatch (cc): nx adds the path via ONE add_edges_from(
    # pairwise(...), **attr); fnx looped per-edge add_edge (~0.24x vs nx, 4x
    # slower even on a fresh Graph). Batch it — byte-identical edge order, and
    # add_edges_from applies **attr to every edge exactly like the loop did.
    G = G_to_add_to
    node_list = list(nodes_for_path)
    if not node_list:
        return
    if len(node_list) == 1:
        G.add_node(node_list[0])
        return
    # br-r37-c1-addpathbatch (cc): do NOT add_node(node_list[0]) before the
    # add_edges_from — on a fresh graph the explicit pre-add makes the graph
    # non-fresh and DEFEATS add_edges_from's fresh-graph batch fast path
    # (2.79ms -> 1.53ms when skipped). pairwise's first edge adds node_list[0]
    # anyway (verified identical node order), so it's redundant for len>=2.
    G.add_edges_from(_itertools.pairwise(node_list), **attr)


def add_cycle(G_to_add_to, nodes_for_cycle, **attr):
    """Add a cycle of edges to *G*."""
    # br-r37-c1-addpathbatch (cc): batch like nx's add_edges_from(pairwise(
    # nodes, cyclic=True), **attr). Single node -> the (n, n) self-loop close.
    G = G_to_add_to
    node_list = list(nodes_for_cycle)
    if not node_list:
        return
    if len(node_list) == 1:
        # single-node cycle == self-loop; the edge adds the node (no pre-add,
        # which would defeat the fresh-graph add_edges_from fast path).
        G.add_edges_from([(node_list[0], node_list[0])], **attr)
        return
    edges = list(_itertools.pairwise(node_list))
    edges.append((node_list[-1], node_list[0]))
    G.add_edges_from(edges, **attr)


def add_star(G_to_add_to, nodes_for_star, **attr):
    """Add a star of edges to *G* (first node is the center)."""
    # br-r37-c1-addpathbatch (cc): batch the hub->spoke edges through one
    # add_edges_from instead of the per-edge add_edge loop (~0.23x vs nx).
    G = G_to_add_to
    node_list = list(nodes_for_star)
    if not node_list:
        return
    center = node_list[0]
    if len(node_list) == 1:
        G.add_node(center)
        return
    # No pre-add of center: the first hub->spoke edge adds it, keeping the
    # fresh-graph add_edges_from fast path engaged (skips ~1.2ms of non-fresh tax).
    G.add_edges_from(((center, spoke) for spoke in node_list[1:]), **attr)


def _validate_product_graph_types(G, H, *, allow_directed=True, allow_multigraph=True):
    if G.is_directed() != H.is_directed():
        raise NetworkXError("G and H must be both directed or both undirected")
    if G.is_directed() and not allow_directed:
        raise NetworkXNotImplemented("not implemented for directed type")
    if (G.is_multigraph() or H.is_multigraph()) and not allow_multigraph:
        raise NetworkXNotImplemented("not implemented for multigraph type")


def _product_factors(G, H):
    """The factors a product builds from: a view materialised, as every native
    call site takes it (br-r37-c1-45koy). The edge-attribute product kernels
    take exact classes only, so a subgraph view with edge attributes took the
    O(product) Python build - lexicographic_product 0.45-0.54x networkx - for
    want of an O(factor) copy."""
    return _coerce_arg_to_fnx_graph(G), _coerce_arg_to_fnx_graph(H)


def _product_graph_class(G, H):
    if G.is_directed():
        return MultiDiGraph if (G.is_multigraph() or H.is_multigraph()) else DiGraph
    return MultiGraph if (G.is_multigraph() or H.is_multigraph()) else Graph


def _product_node_attrs(g_attrs, h_attrs):
    merged = {}
    for key in set(g_attrs) | set(h_attrs):
        merged[key] = (g_attrs.get(key), h_attrs.get(key))
    return merged


def _paired_edge_attrs(g_attrs, h_attrs):
    merged = {}
    for key in set(g_attrs) | set(h_attrs):
        merged[key] = (g_attrs.get(key), h_attrs.get(key))
    return merged


def _cross_product_edge_key(g_is_multigraph, h_is_multigraph, g_key, h_key):
    if g_is_multigraph and h_is_multigraph:
        return (g_key, h_key)
    if g_is_multigraph:
        return g_key
    if h_is_multigraph:
        return h_key
    return None


def _graph_has_any_attrs(G):
    """True if any node or edge of *G* carries a non-empty attribute dict."""
    if _native_graph_has_any_attrs is not None and not G.is_multigraph():
        try:
            native = _native_graph_has_any_attrs(G)
        except Exception:
            native = None
        if native is not None:
            return bool(native)

    if any(d for _n, d in G.nodes(data=True)):
        return True
    if G.is_multigraph():
        return any(d for *_e, d in G.edges(keys=True, data=True))
    return any(d for *_e, d in G.edges(data=True))


def _graph_has_any_edge_attrs(G):
    """True if any edge of *G* carries a non-empty attribute dict."""
    if not G.is_multigraph():
        try:
            r = _fnx.graph_has_any_edge_attrs(G)
        except Exception:
            r = None
        if r is not None:
            return bool(r)
        return any(d for *_e, d in G.edges(data=True))
    return any(d for *_e, d in G.edges(keys=True, data=True))


def _graph_has_any_node_attrs(G):
    """True if any node of *G* carries a non-empty attribute dict."""
    return any(d for _n, d in G.nodes(data=True))


def _native_graph_product(G, H, *, kind="cartesian"):
    """br-r37-c1-prodnative: native product fast path, or None to fall back.

    ``kind`` is one of ``cartesian`` / ``tensor`` / ``strong`` /
    ``lexicographic`` (br-r37-c1-prodstronglex). Gated to the case the native
    kernel reproduces exactly: simple (non-multi) graphs of matching
    directedness, with no node/edge attributes to pair. SELF-LOOPS ARE NOW
    HANDLED (br-r37-c1-prodself): the kernel enumerates each factor's edges with
    ``v >= u`` so self-loop pairs are included, and the simple-graph
    ``extend_edges_unrecorded`` inherently de-duplicates the tensor/lexicographic
    double-push of a self-loop-induced product edge (a simple Graph cannot hold a
    parallel edge), so the edge SET matches nx's idempotent ``add_edge``
    construction — even a handful of incidental self-loops no longer drops the
    whole product to the ~4x-slower Python path. Result node tuples and the
    empty-attr edge set are identical to the Python construction; only the build
    path (and insertion order, which the product parity tests canonicalise away)
    differs.

    br-r37-c1-prodnodeattr (cc): the product edge set depends ONLY on adjacency, not
    on attrs, so the kernel builds it correctly whether or not the factors carry
    NODE attrs. EDGE attrs still force the Python fallback (the kernel can't pair
    them), but node attrs are simply painted onto the structurally-correct native
    result with one add_nodes_from batch afterward — O(V_G*V_H) node paints, far
    cheaper than the O(E_product) Python edge loop. So a node-attributed (edge-attr-
    free) product goes native (~0.88x vs nx) instead of falling all the way back to
    the batch (~0.33x). Byte-identical: the paired node attrs equal
    _product_node_attrs and the edge set is the same canonical set the parity tests
    already accept for the no-attr native path.
    """
    if G.is_multigraph() or H.is_multigraph():
        # br-r37-c1-mg-product-native-kernel-9fe9f: Cartesian products of two
        # like-kind multigraphs can keep their inherited keyed-edge structure
        # native. The extension itself declines public-key/display-remap cases;
        # every other multigraph product retains the Python construction below.
        if not (kind == "cartesian" and G.is_multigraph() and H.is_multigraph()):
            return None
    if G.is_directed() != H.is_directed():
        return None
    if _graph_has_any_edge_attrs(G) or _graph_has_any_edge_attrs(H):
        return None
    fast = {
        "cartesian": _fnx.cartesian_product_fast,
        "tensor": _fnx.tensor_product_fast,
        "strong": _fnx.strong_product_fast,
        "lexicographic": _fnx.lexicographic_product_fast,
    }[kind]
    result = fast(G, H)
    if result is not None and (
        _graph_has_any_node_attrs(G) or _graph_has_any_node_attrs(H)
    ):
        # Paint paired node attrs onto the native (empty-attr) product nodes.
        result.add_nodes_from(
            ((g, h), _product_node_attrs(dict(g_attrs), dict(h_attrs)))
            for g, g_attrs in G.nodes(data=True)
            for h, h_attrs in H.nodes(data=True)
        )
    return result


def _product_edge_attrs_kwarg_safe(G, H):
    """br-prodfast (bt): True iff every edge-attribute key in G and H is a ``str``
    other than ``'key'`` — so the multigraph product loops can use the direct
    ``P.add_edge(n1, n2, key=k, **attrs)`` instead of the
    ``P.add_edges_from([(n1, n2, k, dict(attrs))])`` form. That list form exists
    ONLY to dodge the ``key=`` kwarg collision when an attr is named 'key', but it
    pays the full add_edges_from wrapper + three native batch-attempts (all bail on
    a single tuple-node edge) PER EDGE — pathological over the O(E_G x E_H) product
    edge set (multigraph tensor_product was 0.13x vs nx). ``_paired_edge_attrs``
    only UNIONs G/H attr keys (no renaming), so scanning the source graphs covers
    every product edge's keys."""
    for _g in (G, H):
        for _e in _g.edges(data=True):
            for _k in _e[-1]:
                if type(_k) is not str or _k == "key":
                    return False
    return True


def _product_add_keyed_edge(P, n1, n2, key, attrs, attr_safe):
    if attr_safe:
        P.add_edge(n1, n2, key=key, **attrs)
    else:
        P.add_edges_from([(n1, n2, key, dict(attrs))])
