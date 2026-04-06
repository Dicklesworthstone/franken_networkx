"""Pure-Python graph I/O helpers layered on top of the core bindings."""

import ast
from io import BytesIO

from franken_networkx.drawing.layout import _to_nx


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
    import networkx as nx

    return _from_nx_graph(nx.from_graph6_bytes(bytes_in))


def to_graph6_bytes(G, nodes=None, header=True):
    """Serialize a FrankenNetworkX graph to graph6 bytes through NetworkX."""
    import networkx as nx

    return nx.to_graph6_bytes(_to_nx(G), nodes=nodes, header=header)


def read_graph6(path):
    """Read graph6 files through NetworkX."""
    import networkx as nx

    return _from_nx_graph_or_graphs(nx.read_graph6(path))


def write_graph6(G, path, nodes=None, header=True):
    """Write graph6 files through NetworkX."""
    import networkx as nx

    return nx.write_graph6(_to_nx(G), path, nodes=nodes, header=header)


def parse_graph6(string):
    """Parse a graph6 string into a FrankenNetworkX graph."""
    if isinstance(string, str):
        data = string.encode("ascii")
    else:
        data = bytes(string)
    return from_graph6_bytes(data)


def from_sparse6_bytes(bytes_in):
    """Parse sparse6 bytes into a FrankenNetworkX graph."""
    import networkx as nx

    return _from_nx_graph(nx.from_sparse6_bytes(bytes_in))


def to_sparse6_bytes(G, nodes=None, header=True):
    """Serialize a FrankenNetworkX graph to sparse6 bytes through NetworkX."""
    import networkx as nx

    return nx.to_sparse6_bytes(_to_nx(G), nodes=nodes, header=header)


def read_sparse6(path):
    """Read sparse6 files through NetworkX."""
    import networkx as nx

    return _from_nx_graph_or_graphs(nx.read_sparse6(path))


def write_sparse6(G, path, nodes=None, header=True):
    """Write sparse6 files through NetworkX."""
    import networkx as nx

    return nx.write_sparse6(_to_nx(G), path, nodes=nodes, header=header)


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

    return nx.write_pajek(_to_nx(G), path, encoding=encoding)


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

    yield from nx.generate_gml(_to_nx(G), stringizer=stringizer)


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


def read_gexf(path, node_type=None, relabel=False, version="1.2draft"):
    """Read GEXF through NetworkX and convert the result back to FrankenNetworkX."""
    import networkx as nx

    graph = nx.read_gexf(
        path,
        node_type=node_type,
        relabel=relabel,
        version=version,
    )
    return _from_nx_graph(graph)


def write_gexf(G, path, encoding="utf-8", prettyprint=True, version="1.2draft"):
    """Write GEXF through NetworkX."""
    import networkx as nx

    return nx.write_gexf(
        _to_nx(G),
        path,
        encoding=encoding,
        prettyprint=prettyprint,
        version=version,
    )


def generate_gexf(G, encoding="utf-8", prettyprint=True, version="1.2draft"):
    """Yield GEXF lines through NetworkX."""
    import networkx as nx

    yield from nx.generate_gexf(
        _to_nx(G),
        encoding=encoding,
        prettyprint=prettyprint,
        version=version,
    )


def parse_gexf(string, node_type=None, relabel=False, version="1.2draft"):
    """Parse a GEXF string into a FrankenNetworkX graph."""
    return read_gexf(
        BytesIO(string.encode("utf-8")),
        node_type=node_type,
        relabel=relabel,
        version=version,
    )


def relabel_gexf_graph(G):
    """Relabel a GEXF graph from internal ids to labels via NetworkX."""
    import networkx as nx

    return _from_nx_graph(nx.relabel_gexf_graph(_to_nx(G)))
