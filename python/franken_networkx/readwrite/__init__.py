"""Pure-Python graph I/O helpers layered on top of the core bindings."""

from io import BytesIO

from franken_networkx.drawing.layout import _to_nx


def _normalize_lines(lines):
    """Normalize a string or iterable into a list of text lines."""
    if isinstance(lines, str):
        return lines.splitlines()
    return list(lines)


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
        for left, right, _, attrs in graph.edges(keys=True, data=True):
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


def parse_adjlist(lines, comments="#", delimiter=None, create_using=None, nodetype=None):
    """Parse an adjacency-list line stream into a FrankenNetworkX graph."""
    import networkx as nx

    graph = nx.parse_adjlist(
        _normalize_lines(lines),
        comments=comments,
        delimiter=delimiter,
        create_using=None,
        nodetype=nodetype,
    )
    return _from_nx_graph(graph, create_using=create_using)


def parse_edgelist(
    lines,
    comments="#",
    delimiter=None,
    create_using=None,
    nodetype=None,
    data=True,
):
    """Parse an edge-list line stream into a FrankenNetworkX graph."""
    import networkx as nx

    graph = nx.parse_edgelist(
        _normalize_lines(lines),
        comments=comments,
        delimiter=delimiter,
        create_using=None,
        nodetype=nodetype,
        data=data,
    )
    return _from_nx_graph(graph, create_using=create_using)


def parse_gml(lines, label="label", destringizer=None):
    """Parse GML text or lines into a FrankenNetworkX graph."""
    import networkx as nx

    graph = nx.parse_gml(_normalize_lines(lines), label=label, destringizer=destringizer)
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
    """Read multiline adjacency lists through NetworkX."""
    import networkx as nx

    graph = nx.read_multiline_adjlist(
        path,
        comments=comments,
        delimiter=delimiter,
        create_using=None,
        nodetype=nodetype,
        edgetype=edgetype,
        encoding=encoding,
    )
    return _from_nx_graph(graph, create_using=create_using)


def write_multiline_adjlist(G, path, delimiter=" ", comments="#", encoding="utf-8"):
    """Write multiline adjacency lists through NetworkX."""
    import networkx as nx

    return nx.write_multiline_adjlist(
        _to_nx(G),
        path,
        delimiter=delimiter,
        comments=comments,
        encoding=encoding,
    )


def parse_multiline_adjlist(
    lines,
    comments="#",
    delimiter=None,
    create_using=None,
    nodetype=None,
    edgetype=None,
):
    """Parse multiline adjacency-list text or lines into a FrankenNetworkX graph."""
    import networkx as nx

    graph = nx.parse_multiline_adjlist(
        iter(_normalize_lines(lines)),
        comments=comments,
        delimiter=delimiter,
        create_using=None,
        nodetype=nodetype,
        edgetype=edgetype,
    )
    return _from_nx_graph(graph, create_using=create_using)


def read_weighted_edgelist(
    path,
    comments="#",
    delimiter=None,
    create_using=None,
    nodetype=None,
    encoding="utf-8",
):
    """Read weighted edge lists through NetworkX."""
    import networkx as nx

    graph = nx.read_weighted_edgelist(
        path,
        comments=comments,
        delimiter=delimiter,
        create_using=None,
        nodetype=nodetype,
        encoding=encoding,
    )
    return _from_nx_graph(graph, create_using=create_using)


def write_weighted_edgelist(G, path, comments="#", delimiter=" ", encoding="utf-8"):
    """Write weighted edge lists through NetworkX."""
    import networkx as nx

    return nx.write_weighted_edgelist(
        _to_nx(G),
        path,
        comments=comments,
        delimiter=delimiter,
        encoding=encoding,
    )


def generate_multiline_adjlist(G, delimiter=" "):
    """Yield multiline adjacency-list lines through NetworkX."""
    import networkx as nx

    yield from nx.generate_multiline_adjlist(_to_nx(G), delimiter=delimiter)


def generate_adjlist(G, delimiter=" "):
    """Yield adjacency-list lines using NetworkX's generator."""
    import networkx as nx

    yield from nx.generate_adjlist(_to_nx(G), delimiter=delimiter)


def generate_edgelist(G, delimiter=" ", data=True):
    """Yield edge-list lines using NetworkX's generator."""
    import networkx as nx

    yield from nx.generate_edgelist(_to_nx(G), delimiter=delimiter, data=data)


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
