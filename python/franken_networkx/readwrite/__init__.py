"""Pure-Python graph I/O helpers layered on top of the core bindings."""

import ast
from io import BytesIO
from pathlib import Path


def _normalize_lines(lines):
    """Normalize a string or iterable into a list of text lines."""
    if isinstance(lines, str):
        return lines.splitlines()
    return list(lines)


def _new_graph(create_using=None):
    """Return an empty FrankenNetworkX graph from *create_using*."""
    import franken_networkx as fnx

    if create_using is None:
        return fnx.Graph()
    if isinstance(create_using, type):
        return create_using()
    create_using.clear()
    return create_using


def _to_nx_create_using(create_using=None):
    """Return an empty NetworkX graph matching the requested output shape."""
    import networkx as nx

    if create_using is None:
        return None

    graph = create_using() if isinstance(create_using, type) else create_using

    if graph.is_multigraph():
        return nx.MultiDiGraph() if graph.is_directed() else nx.MultiGraph()
    return nx.DiGraph() if graph.is_directed() else nx.Graph()


def _to_nx(G):
    """Convert a FrankenNetworkX graph into a NetworkX graph for delegated formats."""
    from franken_networkx.backend import _fnx_to_nx

    return _fnx_to_nx(G)


def _strip_comment(line, comments):
    """Strip inline comments and return the cleaned line (empty string if comment-only)."""
    if comments:
        idx = line.find(comments)
        if idx >= 0:
            line = line[:idx]
    return line.strip()


def _empty_like_nx_graph(graph, create_using=None):
    """Build an empty FrankenNetworkX graph matching the NetworkX result shape."""
    import franken_networkx as fnx

    if create_using is None:
        if graph.is_multigraph():
            return fnx.MultiDiGraph() if graph.is_directed() else fnx.MultiGraph()
        return fnx.DiGraph() if graph.is_directed() else fnx.Graph()

    if isinstance(create_using, type):
        return create_using()

    create_using.clear()
    return create_using


def _from_nx_graph(graph, create_using=None):
    """Convert a NetworkX graph into the FrankenNetworkX Python surface."""
    result = _empty_like_nx_graph(graph, create_using=create_using)

    for key, value in graph.graph.items():
        result.graph[key] = value

    for node, attrs in graph.nodes(data=True):
        result.add_node(node, **attrs)

    if graph.is_multigraph():
        for left, right, key, attrs in graph.edges(keys=True, data=True):
            if isinstance(key, int) and not isinstance(key, bool):
                result.add_edge(left, right, key=key, **attrs)
            else:
                # Franken multigraph bindings currently only accept integer keys.
                # Preserve the edge payload and deterministic iteration order even
                # when NetworkX produced a richer key type.
                result.add_edge(left, right, **attrs)
    else:
        for left, right, attrs in graph.edges(data=True):
            result.add_edge(left, right, **attrs)

    return result


def _from_nx_graph_or_graphs(graph_or_graphs, create_using=None):
    """Convert one NetworkX graph or a list of graphs into FrankenNetworkX objects."""
    if isinstance(graph_or_graphs, list):
        return [_from_nx_graph(graph) for graph in graph_or_graphs]
    return _from_nx_graph(graph_or_graphs, create_using=create_using)


def _read_bytes(path):
    """Read bytes from a path-like or file-like object."""
    if hasattr(path, "read"):
        data = path.read()
    else:
        data = Path(path).read_bytes()
    if isinstance(data, str):
        return data.encode("ascii")
    return bytes(data)


def _write_bytes(path, data):
    """Write bytes to a path-like or file-like object."""
    if hasattr(path, "write"):
        try:
            path.write(data)
        except TypeError:
            path.write(data.decode("ascii"))
        return None
    Path(path).write_bytes(data)
    return None


def _graph6_data_to_n(data):
    """Decode the graph6 variable-length node count prefix."""
    if data[0] <= 62:
        return data[0], data[1:]
    if data[1] <= 62:
        return (data[1] << 12) + (data[2] << 6) + data[3], data[4:]
    return (
        (data[2] << 30)
        + (data[3] << 24)
        + (data[4] << 18)
        + (data[5] << 12)
        + (data[6] << 6)
        + data[7],
        data[8:],
    )


def _graph6_n_to_data(n):
    """Encode a graph6 variable-length node count prefix."""
    if n <= 62:
        return [n]
    if n <= 258047:
        return [63, (n >> 12) & 0x3F, (n >> 6) & 0x3F, n & 0x3F]
    return [
        63,
        63,
        (n >> 30) & 0x3F,
        (n >> 24) & 0x3F,
        (n >> 18) & 0x3F,
        (n >> 12) & 0x3F,
        (n >> 6) & 0x3F,
        n & 0x3F,
    ]


def _graph6_values(data):
    """Convert ASCII graph6/sparse6 payload bytes into 6-bit values."""
    values = [byte - 63 for byte in data]
    if any(value < 0 or value > 63 for value in values):
        raise ValueError("each input character must be in range(63, 127)")
    return values


def _graph6_bits(values):
    """Yield bits from graph6 6-bit values, most-significant bit first."""
    for value in values:
        for shift in (5, 4, 3, 2, 1, 0):
            yield (value >> shift) & 1


def _bits_to_graph6_bytes(bits):
    """Pack a bit list into graph6 6-bit ASCII payload bytes."""
    if len(bits) % 6:
        bits = [*bits, *([0] * (6 - (len(bits) % 6)))]
    output = bytearray()
    for index in range(0, len(bits), 6):
        chunk = bits[index : index + 6]
        value = 0
        for bit in chunk:
            value = (value << 1) | bit
        output.append(value + 63)
    return bytes(output)


def _format_nodes_for_graph6(G, nodes):
    """Return the node ordering used by graph6 writers."""
    if nodes is None:
        return list(G.nodes())
    return list(nodes)


def _format_nodes_for_sparse6(G, nodes):
    """Return the sorted node ordering used by NetworkX sparse6 writers."""
    if nodes is None:
        return sorted(G.nodes())
    return sorted(nodes)


def _ensure_undirected_for_graph6(G, operation, *, reject_multigraph):
    """Raise NetworkX-compatible errors for unsupported graph6/sparse6 writes."""
    import franken_networkx as fnx

    if G.is_directed():
        raise fnx.NetworkXNotImplemented("not implemented for directed type")
    if reject_multigraph and G.is_multigraph():
        raise fnx.NetworkXNotImplemented("not implemented for multigraph type")


def _graph6_has_edge(G, left, right):
    """Return whether an edge exists, ignoring self-loop-only format details."""
    return G.has_edge(left, right)


def _sparse6_edges(G, mapping):
    """Return sparse6 edge pairs as integer labels, preserving parallel edges."""
    edges = []
    if G.is_multigraph():
        raw_edges = ((u, v) for u, v, _key in G.edges(keys=True))
    else:
        raw_edges = G.edges()
    for u, v in raw_edges:
        if u in mapping and v in mapping:
            left = mapping[u]
            right = mapping[v]
            edges.append((max(left, right), min(left, right)))
    return sorted(edges)


def parse_adjlist(
    lines, comments="#", delimiter=None, create_using=None, nodetype=None
):
    """Parse an adjacency-list line stream into a FrankenNetworkX graph."""
    G = _new_graph(create_using)
    for line in _normalize_lines(lines):
        line = _strip_comment(line, comments)
        if not line:
            continue
        vlist = line.strip().split(delimiter)
        u = vlist.pop(0)
        if nodetype is not None:
            u = nodetype(u)
        G.add_node(u)
        for v in vlist:
            if nodetype is not None:
                v = nodetype(v)
            G.add_edge(u, v)
    return G


def parse_edgelist(
    lines,
    comments="#",
    delimiter=None,
    create_using=None,
    nodetype=None,
    data=True,
):
    """Parse an edge-list line stream into a FrankenNetworkX graph."""
    G = _new_graph(create_using)
    for line in _normalize_lines(lines):
        line = _strip_comment(line, comments)
        if not line:
            continue
        # Split the line into tokens
        if isinstance(data, bool) and data:
            # Format: u v {key:val, ...}  -- data is a Python dict literal
            # Find the dict portion if present
            brace = line.find("{")
            if brace >= 0:
                head = line[:brace].strip()
                tail = line[brace:]
                tokens = head.split(delimiter)
                edgedata = dict(ast.literal_eval(tail))
            else:
                tokens = line.strip().split(delimiter)
                edgedata = {}
        elif isinstance(data, bool) and not data:
            tokens = line.strip().split(delimiter)
            edgedata = {}
        else:
            # data is a list of (name, type) tuples
            tokens = line.strip().split(delimiter)
            edge_tokens = tokens[2:]
            tokens = tokens[:2]
            edgedata = {}
            for (name, tp), val in zip(data, edge_tokens):
                edgedata[name] = tp(val)

        if len(tokens) < 2:
            continue
        u = tokens[0]
        v = tokens[1]
        if nodetype is not None:
            u = nodetype(u)
            v = nodetype(v)
        G.add_edge(u, v, **edgedata)
    return G


def parse_gml(lines, label="label", destringizer=None):
    """Parse GML text or lines into a FrankenNetworkX graph."""
    import networkx as nx

    graph = nx.parse_gml(
        _normalize_lines(lines), label=label, destringizer=destringizer
    )
    return _from_nx_graph(graph)


def from_graph6_bytes(bytes_in):
    """Parse graph6 bytes into a FrankenNetworkX graph."""
    import franken_networkx as fnx

    data = bytes(bytes_in).rstrip(b"\n")
    if data.startswith(b">>graph6<<"):
        data = data[10:]
    values = _graph6_values(data)
    n, values = _graph6_data_to_n(values)
    expected_units = (n * (n - 1) // 2 + 5) // 6
    if len(values) != expected_units:
        raise fnx.NetworkXError(
            f"Expected {n * (n - 1) // 2} bits but got {len(values) * 6} in graph6"
        )

    graph = fnx.Graph()
    for node in range(n):
        graph.add_node(node)
    for (i, j), bit in zip(
        ((i, j) for j in range(1, n) for i in range(j)), _graph6_bits(values)
    ):
        if bit:
            graph.add_edge(i, j)
    return graph


def to_graph6_bytes(G, nodes=None, header=True):
    """Serialize a simple undirected FrankenNetworkX graph to graph6 bytes."""
    _ensure_undirected_for_graph6(G, "to_graph6_bytes", reject_multigraph=True)

    ordered_nodes = _format_nodes_for_graph6(G, nodes)
    n = len(ordered_nodes)
    if n >= 2**36:
        raise ValueError("graph6 is only defined if number of nodes is less than 2 ** 36")

    output = bytearray()
    if header:
        output.extend(b">>graph6<<")
    output.extend(value + 63 for value in _graph6_n_to_data(n))
    bits = [
        1 if _graph6_has_edge(G, ordered_nodes[i], ordered_nodes[j]) else 0
        for j in range(1, n)
        for i in range(j)
    ]
    output.extend(_bits_to_graph6_bytes(bits))
    output.extend(b"\n")
    return bytes(output)


def read_graph6(path):
    """Read graph6 data from a path or file-like object."""
    graphs = []
    for line in _read_bytes(path).splitlines():
        line = line.strip()
        if line:
            graphs.append(from_graph6_bytes(line))
    return graphs[0] if len(graphs) == 1 else graphs


def write_graph6(G, path, nodes=None, header=True):
    """Write graph6 data to a path or file-like object."""
    return _write_bytes(path, to_graph6_bytes(G, nodes=nodes, header=header))


def parse_graph6(string):
    """Parse a graph6 string into a FrankenNetworkX graph."""
    if isinstance(string, str):
        data = string.encode("ascii")
    else:
        data = bytes(string)
    return from_graph6_bytes(data)


def from_sparse6_bytes(bytes_in):
    """Parse sparse6 bytes into a FrankenNetworkX graph."""
    import franken_networkx as fnx

    data = bytes(bytes_in).rstrip(b"\n")
    if data.startswith(b">>sparse6<<"):
        data = data[11:]
    if not data.startswith(b":"):
        raise fnx.NetworkXError("Expected leading colon in sparse6")

    values = _graph6_values(data[1:])
    n, values = _graph6_data_to_n(values)
    k = 1
    while 1 << k < n:
        k += 1

    def pairs():
        chunks = iter(values)
        current = None
        remaining = 0
        while True:
            if remaining < 1:
                try:
                    current = next(chunks)
                except StopIteration:
                    return
                remaining = 6
            remaining -= 1
            bit = (current >> remaining) & 1

            x = current & ((1 << remaining) - 1)
            x_len = remaining
            while x_len < k:
                try:
                    current = next(chunks)
                except StopIteration:
                    return
                remaining = 6
                x = (x << 6) + current
                x_len += 6
            x >>= x_len - k
            remaining = x_len - k
            yield bit, x

    v = 0
    edges = []
    edge_counts = {}
    multigraph = False
    for bit, x in pairs():
        if bit == 1:
            v += 1
        if x >= n or v >= n:
            break
        if x > v:
            v = x
            continue
        edge = (min(x, v), max(x, v))
        edge_counts[edge] = edge_counts.get(edge, 0) + 1
        if edge_counts[edge] > 1:
            multigraph = True
        edges.append((x, v))

    graph = fnx.MultiGraph() if multigraph else fnx.Graph()
    for node in range(n):
        graph.add_node(node)
    for left, right in edges:
        graph.add_edge(left, right)
    return graph


def to_sparse6_bytes(G, nodes=None, header=True):
    """Serialize an undirected FrankenNetworkX graph to sparse6 bytes."""
    _ensure_undirected_for_graph6(G, "to_sparse6_bytes", reject_multigraph=False)

    ordered_nodes = _format_nodes_for_sparse6(G, nodes)
    n = len(ordered_nodes)
    if n >= 2**36:
        raise ValueError("sparse6 is only defined if number of nodes is less than 2 ** 36")

    output = bytearray()
    if header:
        output.extend(b">>sparse6<<")
    output.append(ord(":"))
    output.extend(value + 63 for value in _graph6_n_to_data(n))

    k = 1
    while 1 << k < n:
        k += 1

    def enc(value):
        return [1 if value & (1 << (k - 1 - i)) else 0 for i in range(k)]

    mapping = {node: index for index, node in enumerate(ordered_nodes)}
    bits = []
    current_v = 0
    for v, u in _sparse6_edges(G, mapping):
        if v == current_v:
            bits.append(0)
            bits.extend(enc(u))
        elif v == current_v + 1:
            current_v += 1
            bits.append(1)
            bits.extend(enc(u))
        else:
            current_v = v
            bits.append(1)
            bits.extend(enc(v))
            bits.append(0)
            bits.extend(enc(u))

    padding = (-len(bits)) % 6
    if k < 6 and n == (1 << k) and padding >= k and current_v < n - 1:
        bits.append(0)
        bits.extend([1] * ((-len(bits)) % 6))
    else:
        bits.extend([1] * padding)
    output.extend(_bits_to_graph6_bytes(bits))
    output.extend(b"\n")
    return bytes(output)


def read_sparse6(path):
    """Read sparse6 data from a path or file-like object."""
    graphs = []
    for line in _read_bytes(path).splitlines():
        line = line.strip()
        if line:
            graphs.append(from_sparse6_bytes(line))
    return graphs[0] if len(graphs) == 1 else graphs


def write_sparse6(G, path, nodes=None, header=True):
    """Write sparse6 data to a path or file-like object."""
    return _write_bytes(path, to_sparse6_bytes(G, nodes=nodes, header=header))


def parse_sparse6(string):
    """Parse a sparse6 string into a FrankenNetworkX graph."""
    if isinstance(string, str):
        data = string.encode("ascii")
    else:
        data = bytes(string)
    return from_sparse6_bytes(data)


def read_pajek(path, encoding="UTF-8"):
    """Read Pajek text through NetworkX and convert it back to FrankenNetworkX."""
    import networkx as nx

    return _from_nx_graph(nx.read_pajek(path, encoding=encoding))


def write_pajek(G, path, encoding="UTF-8"):
    """Write Pajek through NetworkX."""
    import networkx as nx

    return nx.write_pajek(G, path, encoding=encoding)


def parse_pajek(lines):
    """Parse Pajek text or lines into a FrankenNetworkX graph."""
    import networkx as nx

    return _from_nx_graph(nx.parse_pajek(_normalize_lines(lines)))


def generate_pajek(G):
    """Yield Pajek lines through NetworkX."""
    import networkx as nx

    yield from nx.generate_pajek(_to_nx(G))


def read_leda(path, encoding="UTF-8"):
    """Read LEDA text through NetworkX and convert it back to FrankenNetworkX."""
    import networkx as nx

    return _from_nx_graph(nx.read_leda(path, encoding=encoding))


def parse_leda(lines):
    """Parse LEDA text or lines into a FrankenNetworkX graph."""
    import networkx as nx

    return _from_nx_graph(nx.parse_leda(_normalize_lines(lines)))


def read_multiline_adjlist(
    path,
    comments="#",
    delimiter=None,
    create_using=None,
    nodetype=None,
    edgetype=None,
    encoding="utf-8",
):
    """Read a multiline adjacency list file into a FrankenNetworkX graph."""
    with open(path, encoding=encoding) as fh:
        lines = fh.readlines()
    return parse_multiline_adjlist(
        lines,
        comments=comments,
        delimiter=delimiter,
        create_using=create_using,
        nodetype=nodetype,
        edgetype=edgetype,
    )


def write_multiline_adjlist(G, path, delimiter=" ", comments="#", encoding="utf-8"):
    """Write a multiline adjacency list to *path*."""
    with open(path, "w", encoding=encoding) as fh:
        for line in generate_multiline_adjlist(G, delimiter=delimiter):
            fh.write(line + "\n")


def parse_multiline_adjlist(
    lines,
    comments="#",
    delimiter=None,
    create_using=None,
    nodetype=None,
    edgetype=None,
):
    """Parse multiline adjacency-list text or lines into a FrankenNetworkX graph."""
    G = _new_graph(create_using)
    it = iter(_normalize_lines(lines))
    while True:
        # Read the next non-comment, non-blank line (node header)
        try:
            header = next(it)
        except StopIteration:
            break
        header = _strip_comment(header, comments)
        if not header:
            continue
        parts = header.split(delimiter)
        node = parts[0]
        if nodetype is not None:
            node = nodetype(node)
        n_nbrs = int(parts[1]) if len(parts) > 1 else 0
        G.add_node(node)
        # Read the neighbor lines
        for _ in range(n_nbrs):
            nbr_line = next(it)
            nbr_line = _strip_comment(nbr_line, comments)
            if not nbr_line:
                continue
            nbr_parts = nbr_line.split(delimiter)
            nbr = nbr_parts[0]
            if edgetype is not None:
                nbr = edgetype(nbr)
            elif nodetype is not None:
                nbr = nodetype(nbr)
            G.add_edge(node, nbr)
    return G


def read_weighted_edgelist(
    path,
    comments="#",
    delimiter=None,
    create_using=None,
    nodetype=None,
    encoding="utf-8",
):
    """Read a weighted edge list file into a FrankenNetworkX graph.

    Each line has the format: ``u v weight``.
    """
    with open(path, encoding=encoding) as fh:
        lines = fh.readlines()
    return parse_edgelist(
        lines,
        comments=comments,
        delimiter=delimiter,
        create_using=create_using,
        nodetype=nodetype,
        data=[("weight", float)],
    )


def write_weighted_edgelist(G, path, comments="#", delimiter=" ", encoding="utf-8"):
    """Write a weighted edge list to *path*.

    Each line has the format ``u<delimiter>v<delimiter>weight``.
    """
    with open(path, "w", encoding=encoding) as fh:
        for u, v, d in G.edges(data=True):
            w = d.get("weight", 1.0)
            fh.write(delimiter.join([str(u), str(v), str(w)]) + "\n")


def generate_multiline_adjlist(G, delimiter=" "):
    """Yield multiline adjacency-list lines from a FrankenNetworkX graph.

    Format per node (two or more lines):
        node_label<delimiter>degree
        neighbor1<delimiter>{edge_data}
        neighbor2<delimiter>{edge_data}
        ...
    """
    directed = G.is_directed()
    seen = set()
    for node, adj in G.adjacency():
        if isinstance(adj, dict):
            nbr_items = list(adj.items())
        else:
            nbr_items = [(x[0] if isinstance(x, (list, tuple)) else x, {}) for x in adj]
        if not directed:
            nbr_items = [(n, d) for n, d in nbr_items if n not in seen]
        yield delimiter.join([str(node), str(len(nbr_items))])
        for nbr, d in nbr_items:
            yield delimiter.join([str(nbr), str(d)])
        seen.add(node)


def generate_adjlist(G, delimiter=" "):
    """Yield adjacency-list lines from a FrankenNetworkX graph.

    Each line has the form ``node<delimiter>neighbor1<delimiter>neighbor2 ...``.
    """
    directed = G.is_directed()
    seen = set()
    for node, adj in G.adjacency():
        if isinstance(adj, dict):
            nbrs = adj.keys()
        else:
            nbrs = [x[0] if isinstance(x, (list, tuple)) else x for x in adj]
        if not directed:
            # Only emit each undirected edge once
            nbrs = [n for n in nbrs if n not in seen]
        yield delimiter.join([str(node)] + [str(n) for n in nbrs])
        seen.add(node)


def generate_edgelist(G, delimiter=" ", data=True):
    """Yield edge-list lines from a FrankenNetworkX graph.

    Each line has the form ``u<delimiter>v<delimiter>{attr_dict}`` when *data*
    is ``True``, ``u<delimiter>v`` when *data* is ``False``, or
    ``u<delimiter>v<delimiter>val1<delimiter>val2 ...`` when *data* is a list
    of attribute keys.
    """
    if data is True:
        for u, v, d in G.edges(data=True):
            yield delimiter.join([str(u), str(v), str(d)])
    elif data is False:
        for u, v in G.edges():
            yield delimiter.join([str(u), str(v)])
    else:
        # data is a list of attribute keys
        for u, v, d in G.edges(data=True):
            bits = [str(u), str(v)]
            bits.extend(str(d.get(k, "")) for k in data)
            yield delimiter.join(bits)


def generate_gml(G, stringizer=None):
    """Yield GML lines using NetworkX's generator."""
    import networkx as nx

    yield from nx.generate_gml(G, stringizer=stringizer)


def write_graphml_xml(
    G,
    path,
    encoding="utf-8",
    prettyprint=True,
    named_key_ids=False,
    edge_id_from_attribute=None,
):
    """Write GraphML through the existing core implementation."""
    import franken_networkx as fnx

    return fnx.write_graphml(G, path)


def write_graphml_lxml(
    G,
    path,
    encoding="utf-8",
    prettyprint=True,
    named_key_ids=False,
    edge_id_from_attribute=None,
):
    """Write GraphML through the existing core implementation."""
    import franken_networkx as fnx

    return fnx.write_graphml(G, path)


def _validate_gexf_version(version):
    if version not in ("1.1draft", "1.2draft", "1.2"):
        raise ValueError("version must be one of: '1.1draft', '1.2draft', '1.2'")


def _apply_gexf_node_type(graph, node_type):
    if node_type is None:
        return graph
    import franken_networkx as fnx

    mapping = {node: node_type(node) for node in graph.nodes()}
    return fnx.relabel_nodes(graph, mapping, copy=True)


def read_gexf(path, node_type=None, relabel=False, version="1.2draft"):
    """Read GEXF using the native Rust parser."""
    import franken_networkx as fnx
    from franken_networkx import _fnx

    _validate_gexf_version(version)
    graph = _fnx.read_gexf(path)
    graph = _apply_gexf_node_type(graph, node_type)
    if relabel:
        graph = relabel_gexf_graph(graph)
    return graph


def write_gexf(G, path, encoding="utf-8", prettyprint=True, version="1.2draft"):
    """Write GEXF using the native Rust writer."""
    import franken_networkx as fnx
    from franken_networkx import _fnx

    _validate_gexf_version(version)
    if G.is_multigraph():
        raise fnx.NetworkXNotImplemented("not implemented for multigraph type")
    return _fnx.write_gexf(G, path)


def generate_gexf(G, encoding="utf-8", prettyprint=True, version="1.2draft"):
    """Yield GEXF lines using the native Rust writer."""
    import franken_networkx as fnx
    from franken_networkx import _fnx

    _validate_gexf_version(version)
    if G.is_multigraph():
        raise fnx.NetworkXNotImplemented("not implemented for multigraph type")
    yield from _fnx.write_gexf_string_rust(G).splitlines()


def parse_gexf(string, node_type=None, relabel=False, version="1.2draft"):
    """Parse a GEXF string into a FrankenNetworkX graph."""
    return read_gexf(
        BytesIO(string.encode("utf-8")),
        node_type=node_type,
        relabel=relabel,
        version=version,
    )


def relabel_gexf_graph(G):
    """Relabel a GEXF graph from internal ids to label attributes."""
    import franken_networkx as fnx

    mapping = {}
    for node, attrs in G.nodes(data=True):
        label = attrs.get("label")
        if label is not None:
            mapping[node] = label
    relabeled = fnx.relabel_nodes(G, mapping, copy=True)
    for original, label in mapping.items():
        attrs = relabeled.nodes[label]
        attrs["id"] = original
        attrs.pop("label", None)
    return relabeled
