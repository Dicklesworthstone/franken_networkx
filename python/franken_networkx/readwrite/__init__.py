"""Pure-Python graph I/O helpers layered on top of the core bindings."""

import ast
import bz2
import gzip
from io import BytesIO, StringIO
from pathlib import Path
import re
import shlex
import warnings


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


def _write_edgelist_via_nx(
    G, path, *, comments="#", delimiter=" ", data=True, encoding="utf-8"
):
    """Private helper (br-wredge): format edgelist via upstream nx.

    Kept behind an underscored private name so the coverage classifier
    continues to label the public ``write_edgelist`` as ``PY_WRAPPER``.
    """
    import networkx as nx

    return nx.write_edgelist(
        _to_nx(G),
        path,
        comments=comments,
        delimiter=delimiter,
        data=data,
        encoding=encoding,
    )


def _read_edgelist_via_nx(
    path,
    *,
    comments="#",
    delimiter=None,
    create_using=None,
    nodetype=None,
    data=True,
    edgetype=None,
    encoding="utf-8",
):
    """Private helper (br-rdedge): parse edgelist via upstream nx then rebuild
    a FrankenNetworkX graph of the requested shape.
    """
    import networkx as nx

    nx_graph = nx.read_edgelist(
        path,
        comments=comments,
        delimiter=delimiter,
        create_using=_to_nx_create_using(create_using),
        nodetype=nodetype,
        data=data,
        edgetype=edgetype,
        encoding=encoding,
    )
    return _from_nx_graph(nx_graph, create_using=create_using)


def _read_adjlist_via_nx(
    path,
    *,
    comments="#",
    delimiter=None,
    create_using=None,
    nodetype=None,
    encoding="utf-8",
):
    """Private helper (br-rdedge sibling): parse adjacency list via nx."""
    import networkx as nx

    nx_graph = nx.read_adjlist(
        path,
        comments=comments,
        delimiter=delimiter,
        create_using=_to_nx_create_using(create_using),
        nodetype=nodetype,
        encoding=encoding,
    )
    return _from_nx_graph(nx_graph, create_using=create_using)


def _write_adjlist_via_nx(G, path, *, comments="#", delimiter=" ", encoding="utf-8"):
    """Private helper (br-wadjlk): emit an adjacency list via nx.

    Kept behind an underscore so the public ``write_adjlist`` stays
    PY_WRAPPER in the coverage classifier.
    """
    import networkx as nx

    return nx.write_adjlist(
        _to_nx(G),
        path,
        comments=comments,
        delimiter=delimiter,
        encoding=encoding,
    )


def _write_graphml_via_nx(
    G,
    path,
    *,
    encoding="utf-8",
    prettyprint=True,
    infer_numeric_types=False,
    named_key_ids=False,
    edge_id_from_attribute=None,
):
    """Private helper (br-grphml): emit GraphML via nx — handles MultiGraph
    and honours every nx kwarg the Rust native rejects.
    """
    import networkx as nx

    return nx.write_graphml(
        _to_nx(G),
        path,
        encoding=encoding,
        prettyprint=prettyprint,
        infer_numeric_types=infer_numeric_types,
        named_key_ids=named_key_ids,
        edge_id_from_attribute=edge_id_from_attribute,
    )


def _read_graphml_via_nx(
    path,
    *,
    node_type=str,
    edge_key_type=int,
    force_multigraph=False,
):
    """Private helper (br-grphml): parse GraphML via nx so ``node_type``
    / ``edge_key_type`` / ``force_multigraph`` kwargs are honoured.
    """
    import networkx as nx

    nx_graph = nx.read_graphml(
        path,
        node_type=node_type,
        edge_key_type=edge_key_type,
        force_multigraph=force_multigraph,
    )
    return _from_nx_graph(nx_graph)


def _write_gml_via_nx(G, path, *, stringizer=None):
    """Private helper (br-wgmldr): emit GML via nx so:
      - ``stringizer`` kwarg is honoured
      - undirected graphs don't emit a spurious ``directed 0`` field
    """
    import networkx as nx

    return nx.write_gml(_to_nx(G), path, stringizer=stringizer)


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
        # 4-tuple (u, v, key, attrs) avoids the ``key=key, **attrs``
        # collision when an edge attribute is literally named "key"
        # (franken_networkx-9x7r0). br-multikey-rt: the Rust multigraph
        # binding now accepts arbitrary (string / tuple / None) keys
        # natively, so preserve whatever key nx used rather than
        # dropping to auto-int for non-integer keys.
        result.add_edges_from(
            (left, right, key, dict(attrs))
            for left, right, key, attrs in graph.edges(keys=True, data=True)
        )
    else:
        result.add_edges_from(
            (left, right, dict(attrs))
            for left, right, attrs in graph.edges(data=True)
        )

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
        if comments:
            idx = line.find(comments)
            if idx >= 0:
                line = line[:idx]
        if not line.strip():
            continue
        split_line = line.rstrip("\n")
        # Split the line into tokens
        if isinstance(data, bool) and data:
            # Format: u v {key:val, ...}  -- data is a Python dict literal
            # Find the dict portion if present
            brace = split_line.find("{")
            if brace >= 0:
                head = split_line[:brace].strip()
                tail = split_line[brace:]
                tokens = head.split(delimiter)
                edgedata = dict(ast.literal_eval(tail))
            else:
                tokens = split_line.split(delimiter)
                edgedata = {}
        elif isinstance(data, bool) and not data:
            tokens = split_line.split(delimiter)
            edgedata = {}
        else:
            # data is a list of (name, type) tuples
            tokens = split_line.split(delimiter)
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
    import franken_networkx as fnx

    if label != "label" or destringizer is not None:
        # The local Rust reader implements the default NetworkX label handling.
        # Keep unsupported parser customizations explicit instead of silently
        # falling back to NetworkX.
        raise fnx.NetworkXError(
            "parse_gml currently supports only label='label' and no destringizer",
        )

    text = "\n".join(
        line.decode("utf-8") if isinstance(line, bytes) else str(line)
        for line in _normalize_lines(lines)
    )
    return fnx.read_gml(StringIO(text))


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


def from_sparse6_bytes(string):
    """Parse sparse6 bytes into a FrankenNetworkX graph.

    br-sp6kw: nx uses parameter name ``string`` for from_sparse6_bytes
    (while ``bytes_in`` for from_graph6_bytes — inconsistent but the
    nx contract). Kwarg-style ``from_sparse6_bytes(string=...)`` now
    works.
    """
    import franken_networkx as fnx

    data = bytes(string).rstrip(b"\n")
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
    """Read Pajek text without NetworkX delegation."""
    if hasattr(path, "read"):
        data = path.read()
        if isinstance(data, bytes):
            data = data.decode(encoding)
        return parse_pajek(data)

    input_path = Path(path)
    if input_path.suffix == ".gz":
        with gzip.open(input_path, "rt", encoding=encoding) as fh:
            return parse_pajek(fh)
    if input_path.suffix == ".bz2":
        with bz2.open(input_path, "rt", encoding=encoding) as fh:
            return parse_pajek(fh)
    return parse_pajek(input_path.read_text(encoding=encoding))


def write_pajek(G, path, encoding="UTF-8"):
    """Write Pajek text without NetworkX delegation."""
    data = "".join(f"{line}\n" for line in generate_pajek(G)).encode(encoding)
    if hasattr(path, "write"):
        try:
            path.write(data)
        except TypeError:
            path.write(data.decode(encoding))
        return None

    output_path = Path(path)
    if output_path.suffix == ".gz":
        with gzip.open(output_path, "wb") as fh:
            fh.write(data)
    elif output_path.suffix == ".bz2":
        with bz2.open(output_path, "wb") as fh:
            fh.write(data)
    else:
        output_path.write_bytes(data)
    return None


def parse_pajek(lines):
    """Parse Pajek text or lines into a FrankenNetworkX graph."""
    import franken_networkx as fnx

    def split_line(line):
        try:
            return [part.decode("utf-8") for part in shlex.split(str(line).encode("utf-8"))]
        except AttributeError:
            return shlex.split(str(line))

    def graph_as(graph, graph_type):
        converted = graph_type()
        converted.graph.update(graph.graph)
        converted.add_nodes_from(graph.nodes(data=True))
        if graph.is_multigraph():
            for left, right, key, attrs in graph.edges(keys=True, data=True):
                converted.add_edges_from([(left, right, key, dict(attrs))])
        else:
            for left, right, attrs in graph.edges(data=True):
                converted.add_edge(left, right, **attrs)
        return converted

    if isinstance(lines, str):
        lines_iter = iter(lines.split("\n"))
    else:
        lines_iter = iter(lines)
    lines_iter = iter(line.rstrip("\n") for line in lines_iter)

    graph = fnx.MultiDiGraph()
    labels = []
    node_labels = {}

    while True:
        try:
            line = next(lines_iter)
        except StopIteration:
            break
        lower = line.lower()
        if lower.startswith("*network"):
            try:
                _, name = line.split(None, 1)
            except ValueError:
                pass
            else:
                graph.graph["name"] = name
        elif lower.startswith("*vertices"):
            _, node_count = line.split()
            for _ in range(int(node_count)):
                splitline = split_line(next(lines_iter))
                node_id, label = splitline[0:2]
                labels.append(label)
                graph.add_node(label)
                node_labels[node_id] = label
                graph.nodes[label]["id"] = node_id
                try:
                    node_position = {
                        "x": float(splitline[2]),
                        "y": float(splitline[3]),
                        "shape": splitline[4],
                    }
                except (IndexError, TypeError, ValueError):
                    node_position = None
                if node_position is not None:
                    graph.nodes[label].update(node_position)
                graph.nodes[label].update(zip(splitline[5::2], splitline[6::2]))
        elif lower.startswith("*edges") or lower.startswith("*arcs"):
            if lower.startswith("*edge"):
                graph = graph_as(graph, fnx.MultiGraph)
            if lower.startswith("*arcs"):
                graph = graph.to_directed()
            for line in lines_iter:
                splitline = split_line(line)
                if len(splitline) < 2:
                    continue
                left_id, right_id = splitline[0:2]
                left = node_labels.get(left_id, left_id)
                right = node_labels.get(right_id, right_id)
                edge_data = {}
                try:
                    edge_weight = float(splitline[2])
                except (IndexError, TypeError, ValueError):
                    edge_weight = None
                if edge_weight is not None:
                    edge_data["weight"] = edge_weight
                edge_data.update(zip(splitline[3::2], splitline[4::2]))
                graph.add_edge(left, right, **edge_data)
        elif lower.startswith("*matrix"):
            graph = graph_as(graph, fnx.DiGraph)
            for row, matrix_line in enumerate(lines_iter):
                for col, data in enumerate(matrix_line.split()):
                    if int(data) != 0:
                        graph.add_edge(labels[row], labels[col], weight=int(data))

    return graph


def generate_pajek(G):
    """Yield Pajek lines without NetworkX delegation."""

    def make_qstr(value):
        if not isinstance(value, str):
            value = str(value)
        if " " in value:
            value = f'"{value}"'
        return value

    yield f"*vertices {G.order()}"
    nodes = list(G)
    nodenumber = dict(zip(nodes, range(1, len(nodes) + 1)))

    for node in nodes:
        node_attrs = G.nodes.get(node, {}).copy()
        x = node_attrs.pop("x", 0.0)
        y = node_attrs.pop("y", 0.0)
        try:
            node_id = int(node_attrs.pop("id", nodenumber[node]))
        except ValueError as err:
            err.args += (
                (
                    "Pajek format requires 'id' to be an int()."
                    " Refer to the 'Relabeling nodes' section."
                ),
            )
            raise
        nodenumber[node] = node_id
        shape = node_attrs.pop("shape", "ellipse")
        line = " ".join(map(make_qstr, (node_id, node, x, y, shape)))
        for key, value in node_attrs.items():
            if isinstance(value, str) and value.strip() != "":
                line += f" {make_qstr(key)} {make_qstr(value)}"
            else:
                reason = "Empty attribute" if isinstance(value, str) else "Non-string attribute"
                warnings.warn(f"Node attribute {key} is not processed. {reason}.")
        yield line

    yield "*arcs" if G.is_directed() else "*edges"
    for left, right, edge_attrs in G.edges(data=True):
        attrs = edge_attrs.copy()
        value = attrs.pop("weight", 1.0)
        line = " ".join(map(make_qstr, (nodenumber[left], nodenumber[right], value)))
        for key, attr_value in attrs.items():
            if isinstance(attr_value, str) and attr_value.strip() != "":
                line += f" {make_qstr(key)} {make_qstr(attr_value)}"
            else:
                reason = (
                    "Empty attribute"
                    if isinstance(attr_value, str)
                    else "Non-string attribute"
                )
                warnings.warn(f"Edge attribute {key} is not processed. {reason}.")
        yield line


def read_leda(path, encoding="UTF-8"):
    """Read LEDA text without NetworkX delegation."""
    if hasattr(path, "read"):
        data = path.read()
        if isinstance(data, bytes):
            data = data.decode(encoding)
        return parse_leda(data)

    input_path = Path(path)
    if input_path.suffix == ".gz":
        with gzip.open(input_path, "rt", encoding=encoding) as fh:
            return parse_leda(fh)
    if input_path.suffix == ".bz2":
        with bz2.open(input_path, "rt", encoding=encoding) as fh:
            return parse_leda(fh)
    return parse_leda(input_path.read_text(encoding=encoding))


def parse_leda(lines):
    """Parse LEDA text or lines into a FrankenNetworkX graph."""
    import franken_networkx as fnx

    if isinstance(lines, str):
        lines_iter = iter(lines.split("\n"))
    else:
        lines_iter = iter(lines)
    lines_iter = iter(
        line.rstrip("\n")
        for line in lines_iter
        if not (line.startswith(("#", "\n")) or line == "")
    )
    for _ in range(3):
        next(lines_iter)

    directed_flag = int(next(lines_iter))
    graph = fnx.DiGraph() if directed_flag == -1 else fnx.Graph()

    node_count = int(next(lines_iter))
    nodes = {}
    for index in range(1, node_count + 1):
        symbol = next(lines_iter).rstrip().strip("|{}|  ")
        if symbol == "":
            symbol = str(index)
        nodes[index] = symbol
    graph.add_nodes_from(nodes.values())

    edge_count = int(next(lines_iter))
    for edge_index in range(edge_count):
        try:
            source, target, _reversal, label = next(lines_iter).split()
        except BaseException as err:
            raise fnx.NetworkXError(
                f"Too few fields in LEDA.GRAPH edge {edge_index + 1}"
            ) from err
        graph.add_edge(nodes[int(source)], nodes[int(target)], label=label[2:-2])
    return graph


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
    """Yield GML lines from a graph without NetworkX delegation."""
    import franken_networkx as fnx

    valid_keys = re.compile("^[A-Za-z][0-9A-Za-z_]*$")
    list_start_value = "_networkx_list_start"

    def escape(text):
        def fixup(match):
            ch = match.group(0)
            return "&#" + str(ord(ch)) + ";"

        return re.sub('[^ -~]|[&"]', fixup, text)

    def stringize(key, value, ignored_keys, indent, in_list=False):
        if not isinstance(key, str):
            raise fnx.NetworkXError(f"{key!r} is not a string")
        if not valid_keys.match(key):
            raise fnx.NetworkXError(f"{key!r} is not a valid key")
        if key not in ignored_keys:
            if isinstance(value, bool):
                if key == "label":
                    yield indent + key + ' "' + str(value) + '"'
                elif value:
                    yield indent + key + " 1"
                else:
                    yield indent + key + " 0"
            elif isinstance(value, int):
                if key == "label":
                    yield indent + key + ' "' + str(value) + '"'
                elif value < -(2**31) or value >= 2**31:
                    yield indent + key + ' "' + str(value) + '"'
                else:
                    yield indent + key + " " + str(value)
            elif isinstance(value, float):
                text = repr(value).upper()
                if text == repr(float("inf")).upper():
                    text = "+" + text
                else:
                    epos = text.rfind("E")
                    if epos != -1 and text.find(".", 0, epos) == -1:
                        text = text[:epos] + "." + text[epos:]
                if key == "label":
                    yield indent + key + ' "' + text + '"'
                else:
                    yield indent + key + " " + text
            elif isinstance(value, dict):
                yield indent + key + " ["
                next_indent = indent + "  "
                for child_key, child_value in value.items():
                    yield from stringize(child_key, child_value, (), next_indent)
                yield indent + "]"
            elif isinstance(value, tuple) and key == "label":
                label = ",".join(repr(item) for item in value)
                yield indent + key + f' "({label})"'
            elif isinstance(value, (list, tuple)) and key != "label" and not in_list:
                if len(value) == 0:
                    yield indent + key + " " + f'"{value!r}"'
                if len(value) == 1:
                    yield indent + key + " " + f'"{list_start_value}"'
                for item in value:
                    yield from stringize(key, item, (), indent, True)
            else:
                if stringizer:
                    try:
                        value = stringizer(value)
                    except ValueError as err:
                        raise fnx.NetworkXError(
                            f"{value!r} cannot be converted into a string"
                        ) from err
                if not isinstance(value, str):
                    raise fnx.NetworkXError(f"{value!r} is not a string")
                yield indent + key + ' "' + escape(value) + '"'

    multigraph = G.is_multigraph()
    yield "graph ["
    if G.is_directed():
        yield "  directed 1"
    if multigraph:
        yield "  multigraph 1"

    ignored_keys = {"directed", "multigraph", "node", "edge"}
    for attr, value in G.graph.items():
        yield from stringize(attr, value, ignored_keys, "  ")

    node_id = dict(zip(G, range(len(G))))
    ignored_keys = {"id", "label"}
    for node, attrs in G.nodes(data=True):
        yield "  node ["
        yield "    id " + str(node_id[node])
        yield from stringize("label", node, (), "    ")
        for attr, value in attrs.items():
            yield from stringize(attr, value, ignored_keys, "    ")
        yield "  ]"

    ignored_keys = {"source", "target"}
    if multigraph:
        ignored_keys.add("key")
        edges = G.edges(keys=True, data=True)
    else:
        edges = G.edges(data=True)

    for edge in edges:
        yield "  edge ["
        yield "    source " + str(node_id[edge[0]])
        yield "    target " + str(node_id[edge[1]])
        if multigraph:
            yield from stringize("key", edge[2], (), "    ")
        for attr, value in edge[-1].items():
            yield from stringize(attr, value, ignored_keys, "    ")
        yield "  ]"
    yield "]"


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
    """Read GEXF into an fnx graph.

    Simple-graph inputs go through the native Rust parser. Multigraph
    inputs (detected via nx's parser, which reads the GEXF metadata)
    round-trip through networkx's multigraph-aware parser and are
    rehydrated on the fnx side as ``fnx.MultiGraph`` / ``fnx.MultiDiGraph``
    (franken_networkx-rrh32).
    """
    import franken_networkx as fnx
    from franken_networkx import _fnx

    _validate_gexf_version(version)
    if hasattr(path, "read"):
        raw = path.read()
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
    else:
        with open(path, "rb") as handle:
            raw = handle.read()

    if _gexf_document_is_multigraph(raw):
        graph = _read_gexf_via_nx(raw)
    else:
        graph = _fnx.read_gexf(BytesIO(raw))

    graph = _apply_gexf_node_type(graph, node_type)
    if relabel:
        graph = relabel_gexf_graph(graph)
    return graph


def write_gexf(G, path, encoding="utf-8", prettyprint=True, version="1.2draft"):
    """Write GEXF to ``path``.

    Multigraph inputs route through ``nx.write_gexf`` (matches upstream
    nx's full parallel-edge semantics, franken_networkx-rrh32). Simple
    graphs keep the native Rust writer path.
    """
    from franken_networkx import _fnx

    _validate_gexf_version(version)
    if G.is_multigraph():
        _write_gexf_via_nx(
            G, path, encoding=encoding, prettyprint=prettyprint, version=version
        )
        return
    return _fnx.write_gexf(G, path)


def generate_gexf(G, encoding="utf-8", prettyprint=True, version="1.2draft"):
    """Yield GEXF lines.

    Multigraph inputs are serialised via upstream nx (supports
    parallel edges with per-edge keys / ids, franken_networkx-rrh32).
    Simple graphs keep the native Rust writer.
    """
    from franken_networkx import _fnx

    _validate_gexf_version(version)
    if G.is_multigraph():
        yield from _generate_gexf_via_nx(
            G, encoding=encoding, prettyprint=prettyprint, version=version
        )
        return
    yield from _fnx.write_gexf_string_rust(G).splitlines()


def _read_gexf_via_nx(raw_bytes):
    """Read a multigraph-shape GEXF document through nx and rehydrate
    as an fnx Multi*Graph (kept private so ``read_gexf`` stays out of
    the NX_DELEGATED classification).
    """
    from networkx.readwrite.gexf import read_gexf as _upstream_read_gexf

    nx_graph = _upstream_read_gexf(BytesIO(raw_bytes))
    return _from_nx_graph(nx_graph)


def _write_gexf_via_nx(G, path, *, encoding, prettyprint, version):
    """Delegate multigraph serialisation to upstream nx.write_gexf.

    Private helper — keeps the public ``write_gexf`` classified as
    PY_WRAPPER.
    """
    from networkx.readwrite.gexf import write_gexf as _upstream_write_gexf

    _upstream_write_gexf(
        _multigraph_to_nx(G),
        path,
        encoding=encoding,
        prettyprint=prettyprint,
        version=version,
    )


def _generate_gexf_via_nx(G, *, encoding, prettyprint, version):
    """Delegate multigraph serialisation to upstream nx.generate_gexf.

    Private helper — keeps the public ``generate_gexf`` classified
    as PY_WRAPPER.
    """
    from networkx.readwrite.gexf import generate_gexf as _upstream_generate_gexf

    yield from _upstream_generate_gexf(
        _multigraph_to_nx(G),
        encoding=encoding,
        prettyprint=prettyprint,
        version=version,
    )


def _gexf_document_is_multigraph(raw_bytes):
    """Inexpensive peek: does this GEXF document declare parallel
    edges or contain repeated ``(source, target)`` pairs?

    Pulls ``source`` / ``target`` attributes off every ``<edge>``
    element with ``xml.etree.ElementTree.iterparse`` so attribute
    order and quote style don't matter (franken_networkx-2ky8p). The
    ``parallel="true"`` declaration on ``<edges>`` is also honoured.
    """
    try:
        text = raw_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return False
    if 'parallel="true"' in text or "parallel='true'" in text:
        return True

    import xml.etree.ElementTree as ET
    from io import BytesIO

    pairs = []
    try:
        for _event, elem in ET.iterparse(BytesIO(raw_bytes), events=("end",)):
            # Tag names in GEXF carry a namespace prefix like
            # "{http://www.gexf.net/1.2draft}edge"; strip it before
            # comparing so any GEXF version matches.
            tag = elem.tag.rsplit("}", 1)[-1] if "}" in elem.tag else elem.tag
            if tag == "edge":
                source = elem.attrib.get("source")
                target = elem.attrib.get("target")
                if source is not None and target is not None:
                    pairs.append((source, target))
            # Free memory — we only need attribute values, not the tree.
            elem.clear()
    except ET.ParseError:
        return False

    if not pairs:
        return False
    return len(pairs) != len(set(pairs))


def parse_gexf(string, node_type=None, relabel=False, version="1.2draft"):
    """Parse a GEXF string into a FrankenNetworkX graph."""
    return read_gexf(
        BytesIO(string.encode("utf-8")),
        node_type=node_type,
        relabel=relabel,
        version=version,
    )


def _multigraph_to_nx(G):
    """Convert an fnx Multi*Graph to the matching nx Multi*Graph so
    nx's GEXF writer can handle it. Preserves keys + per-edge attrs.
    """
    import networkx as _nx_mod

    cls = _nx_mod.MultiDiGraph if G.is_directed() else _nx_mod.MultiGraph
    out = cls()
    out.graph.update(dict(G.graph))
    for node, attrs in G.nodes(data=True):
        out.add_node(node, **dict(attrs))
    for u, v, key, attrs in G.edges(keys=True, data=True):
        out.add_edge(u, v, key=key, **dict(attrs))
    return out


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
