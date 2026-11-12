import networkx.classes.coreviews as _nx_dict_import_views


_SIMPLE_DICT_IMPORT_ADD_EDGES_FROM = {
    cls: cls.add_edges_from for cls in (Graph, DiGraph)
}
_SIMPLE_DICT_IMPORT_GRAPH_METHODS = {
    cls: (cls.__contains__, cls.add_node, cls.get_edge_data)
    for cls in (Graph, DiGraph)
}
_SIMPLE_DICT_IMPORT_VIEW_METHODS = {
    cls: tuple(
        (name, getattr(cls, name))
        for name in ("__getattribute__", "__iter__", "__getitem__", "items", "_atlas")
    )
    for cls in (_nx_dict_import_views.AdjacencyView, _nx_dict_import_views.AtlasView)
}


def _simple_dict_import_plain_rows(data):
    """Return plain backing rows only when inspection cannot run user code."""
    plain_attrs = _plain_read_attr_dict_types()
    if type(data) is dict:
        rows = data
    else:
        # Standard NetworkX adjacency views wrap a dict without transforming
        # it. Capture their protocols so a class patch cannot silently become
        # permission to inspect custom rows before their public traversal.
        if type(data) is not _nx_dict_import_views.AdjacencyView:
            return None
        for cls, methods in _SIMPLE_DICT_IMPORT_VIEW_METHODS.items():
            if getattr(_nx_dict_import_views, cls.__name__, None) is not cls or any(
                getattr(cls, name) is not original for name, original in methods
            ):
                return None
        rows = data._atlas
        if type(rows) is not dict:
            return None
    for node, neighbors in rows.items():
        if not _multigraph_import_plain_key(node) or type(neighbors) is not dict:
            return None
        for neighbor, attrs in neighbors.items():
            if (
                not _multigraph_import_plain_key(neighbor)
                or type(attrs) not in plain_attrs
                or not _multigraph_import_plain_attrs(attrs)
            ):
                return None
    return rows


def _add_dict_simple_edge(graph, add_edges, source, target, attrs):
    """Run attribute providers outside the native graph's mutable borrow."""
    contains, add_node, get_edge_data = _SIMPLE_DICT_IMPORT_GRAPH_METHODS[type(graph)]
    # add_edges_from does not dispatch through overridable add_node or
    # get_edge_data methods. Internal setup must retain that same boundary.
    if not contains(graph, source):
        add_node(graph, source)
    if not contains(graph, target):
        add_node(graph, target)
    existing = get_edge_data(graph, source, target)
    if existing is None:
        # A failing provider leaves the endpoint nodes, but no new edge.
        # Its callbacks can inspect the graph while this dict is unlinked.
        prepared = {}
        prepared.update(attrs)
        add_edges([(source, target, prepared)])
    else:
        # Updating an existing edge is visible incrementally, including fields
        # written before a provider raises. Preserve the native write-watch
        # notification which dict.update cannot reach after such an error.
        try:
            existing.update(attrs)
        except BaseException:
            if type(existing) in (_EdgeAttrDict, _SlottedEdgeAttrDict):
                watch = existing._fnx_watch
                if watch is not None:
                    watch.note(existing)
            raise


_MULTIGRAPH_IMPORT_METHODS = {
    cls: tuple(
        (name, getattr(cls, name))
        for name in (
            "add_edge", "add_nodes_from", "get_edge_data", "clear",
            "is_directed", "is_multigraph",
        )
    )
    for cls in (MultiGraph, MultiDiGraph)
}


def _multigraph_import_can_batch(graph):
    """Keep custom graph storage and mutation hooks on the incremental route."""
    graph_type = type(graph)
    return (
        graph_type in (MultiGraph, MultiDiGraph)
        and not _has_networkx_private_storage(graph)
        and all(
            getattr(graph_type, name) is original
            for name, original in _MULTIGRAPH_IMPORT_METHODS[graph_type]
        )
        and graph.__dict__.keys().isdisjoint(
            (
                "add_edge", "add_nodes_from", "get_edge_data", "clear",
                "is_directed", "is_multigraph", "_try_add_attr_edges_from_batch",
            )
        )
    )


def _multigraph_import_plain_key(value):
    """Keys which can be inspected without invoking user hash/equality hooks."""
    value_type = type(value)
    return (
        value_type is str or value_type is int
        or value_type is float or value_type is bool
    ) or (
        value_type is tuple
        and all(type(item) in (str, int, float, bool) for item in value)
    )


def _multigraph_import_plain_attrs(attrs):
    """Decline non-native attribute values before buffering the whole input."""
    for key, value in attrs.items():
        if type(key) is not str:
            return False
        value_type = type(value)
        if value_type is str or value_type is bool:
            continue
        if value_type is int and -(2**63) <= value < 2**63:
            continue
        if value_type is float and value == value:
            continue
        return False
    return True


def _try_from_pandas_multigraph_batch(
    graph, df, source, target, attr_columns, edge_key
):
    """Try one atomic native insertion for ordinary, eagerly readable columns.

    Custom tables, extension arrays and keys must keep their iteration interleaved
    with graph mutations. A declined native batch leaves the graph untouched, so
    the caller can use its original iterators and preserve partial errors too.
    """
    if (
        not _multigraph_import_can_batch(graph)
        or type(attr_columns) not in (list, tuple)
    ):
        return False
    try:
        import pandas as pd
    except ImportError:
        return False

    if type(df) is not pd.DataFrame or len(df) < 8:
        return False
    columns = [source, target, *attr_columns]
    if edge_key is not None:
        columns.append(edge_key)
    if not all(_multigraph_import_plain_key(column) for column in columns):
        return False
    # These pandas-owned arrays only yield stored values. In particular, do not
    # eagerly iterate a third-party ExtensionArray, whose iterator may observe G.
    numpy_array_types = tuple(
        getattr(pd.arrays, name, None)
        for name in ("NumpyExtensionArray", "PandasArray")
    )
    array_types = numpy_array_types + tuple(
        getattr(pd.arrays, name, None)
        for name in ("StringArray", "ArrowStringArray", "IntegerArray", "FloatingArray", "BooleanArray")
    )
    series = []
    for position, column in enumerate(columns):
        values = df[column]
        if type(values) is not pd.Series:
            return False
        array_type = type(values.array)
        if array_type not in array_types:
            return False
        # Object columns can hide a non-native value at the very last row.
        # Decline from their dtype before buffering; dedicated pandas string
        # arrays remain eligible even though their dtype kind can also be "O".
        if (
            2 <= position < 2 + len(attr_columns)
            and array_type in numpy_array_types
            and values.dtype.kind == "O"
        ):
            return False
        series.append(values)
    batch = []
    for row in zip(*series):
        u, v = row[:2]
        if not (_multigraph_import_plain_key(u) and _multigraph_import_plain_key(v)):
            return False
        attrs = dict(zip(attr_columns, row[2:]))
        # Reject common non-scalar columns cheaply; the native collector checks
        # every remaining record without repeating that scan in Python.
        if not batch and not _multigraph_import_plain_attrs(attrs):
            return False
        if edge_key is None:
            batch.append((u, v, attrs))
        else:
            key = row[-1]
            # The existing explicit-key collectors accept integer endpoints
            # and integer keys. Decline other shapes before buffering the table.
            if type(u) is not int or type(v) is not int or type(key) is not int:
                return False
            batch.append((u, v, key, attrs))
    # The collector also checks lossless attributes, duplicate explicit keys,
    # label aliases and key allocation before making any graph mutation.
    return graph._try_add_attr_edges_from_batch(batch) is not None


def _try_from_dict_multigraph_batch(graph, data, multigraph_input):
    """Batch plain dictionary inputs without consuming custom mappings early."""
    if (
        not _multigraph_import_can_batch(graph)
        or type(data) is not dict
        or type(multigraph_input) is not bool
    ):
        return False
    directed = type(graph) is MultiDiGraph
    seen = set()
    batch = []
    keys = []
    auto_keys = True
    integer_endpoints = True
    for u, neighbors in data.items():
        if not _multigraph_import_plain_key(u) or type(neighbors) is not dict:
            return False
        for v, edge_data in neighbors.items():
            if not _multigraph_import_plain_key(v):
                return False
            if not directed and (u, v) in seen:
                continue
            if multigraph_input:
                if type(edge_data) is not dict:
                    return False
                keyed_data = edge_data.items()
            else:
                keyed_data = ((0, edge_data),)
            for offset, (key, attrs) in enumerate(keyed_data):
                if (
                    (key is not None and not _multigraph_import_plain_key(key))
                    or type(attrs) is not dict
                    or (not batch and not _multigraph_import_plain_attrs(attrs))
                ):
                    return False
                integer_endpoints = integer_endpoints and type(u) is int and type(v) is int
                batch.append((u, v, attrs))
                if multigraph_input:
                    keys.append(key)
                    auto_keys = auto_keys and type(key) is int and key == offset
                    if type(key) is not int or (not auto_keys and not integer_endpoints):
                        return False
            if not directed:
                seen.add((v, u))
    # Keep integer endpoints keyed: the existing-node collector avoids rebuilding
    # the node index. A fresh graph gives each pair keys 0, 1, ... , so triples
    # admit equivalent string/tuple-labelled inputs to the auto-key collector.
    if not multigraph_input and integer_endpoints:
        batch = [(u, v, 0, attrs) for u, v, attrs in batch]
    elif multigraph_input and (not auto_keys or integer_endpoints):
        batch = [(u, v, key, attrs) for (u, v, attrs), key in zip(batch, keys)]
    return graph._try_add_attr_edges_from_batch(batch) is not None


def from_pandas_edgelist(
    df,
    source="source",
    target="target",
    edge_attr=None,
    create_using=None,
    edge_key=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Return a graph from a Pandas DataFrame of edges.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame with at least two columns for source and target nodes.
    source : str, optional
        Column name for source nodes. Default ``'source'``.
    target : str, optional
        Column name for target nodes. Default ``'target'``.
    edge_attr : str, list of str, True, or None, optional
        Edge attributes to include. ``True`` means all columns except source
        and target. ``None`` means no attributes.
    create_using : Graph constructor, optional
        Graph type to create. Default ``Graph()``.

    Returns
    -------
    G : Graph or DiGraph
    """
    _validate_backend_dispatch_keywords("from_pandas_edgelist", backend, backend_kwargs)
    graph = _empty_graph_from_create_using(create_using)

    if edge_attr is None:
        if graph.is_multigraph() and edge_key is not None:
            if _try_from_pandas_multigraph_batch(
                graph, df, source, target, (), edge_key
            ):
                return graph
            for u, v, edge_key_value in zip(df[source], df[target], df[edge_key]):
                _add_json_multiedge(graph, u, v, edge_key_value, {})
        else:
            graph.add_edges_from(zip(df[source], df[target]))
        return graph

    reserved_columns = [source, target]
    if graph.is_multigraph() and edge_key is not None:
        reserved_columns.append(edge_key)

    if isinstance(edge_attr, bool) and edge_attr:
        attr_col_headings = [column for column in df.columns if column not in reserved_columns]
    elif isinstance(edge_attr, list | tuple):
        attr_col_headings = edge_attr
    else:
        attr_col_headings = [edge_attr]
    if len(attr_col_headings) == 0:
        raise NetworkXError(
            f"Invalid edge_attr argument: No columns found with name: {attr_col_headings}"
        )

    try:
        attribute_data = zip(*[df[column] for column in attr_col_headings])
    except (KeyError, TypeError) as err:
        msg = f"Invalid edge_attr argument: {edge_attr}"
        raise NetworkXError(msg) from err

    if graph.is_multigraph():
        if edge_key is not None:
            try:
                attribute_data = zip(attribute_data, df[edge_key])
            except (KeyError, TypeError) as err:
                msg = f"Invalid edge_key argument: {edge_key}"
                raise NetworkXError(msg) from err

        if _try_from_pandas_multigraph_batch(
            graph, df, source, target, attr_col_headings, edge_key
        ):
            return graph
        for source_node, target_node, attrs in zip(df[source], df[target], attribute_data):
            if edge_key is not None:
                attrs, edge_key_value = attrs
                _add_json_multiedge(
                    graph,
                    source_node,
                    target_node,
                    edge_key_value,
                    dict(zip(attr_col_headings, attrs)),
                )
            else:
                actual_key = graph.add_edge(source_node, target_node)
                graph[source_node][target_node][actual_key].update(zip(attr_col_headings, attrs))
    elif type(graph) in (Graph, DiGraph):
        # br-r37-c1-nodebatch/pandas: batch the whole attributed edge set
        # through add_edges_from (the attr edge batch, br-r37-c1-pr8q6) in one
        # bulk insertion instead of per-edge add_edge + adjacency-view
        # __getitem__ + dict.update (~2.6x nx). br-r37-c1-pandasdir (cc): DiGraph
        # added to the gate — it previously fell to the per-row else loop, whose
        # directed adjacency-view __getitem__ per row is O(N^2) (962ms @ n=800,
        # 0.004x vs nx). The batch is identical for directed (no symmetric dedup;
        # directed rows are unique, duplicate (u,v) rows merge later-wins exactly
        # like the repeated update). Identical semantics: each edge's
        # data dict is dict(zip(headings, attrs)); duplicate (u, v) rows merge
        # per-key later-wins, exactly as the repeated ``update`` did. Any
        # batch-incompatible attr value (e.g. an exotic numpy scalar) makes
        # add_edges_from fall back to its per-edge path transparently.
        graph.add_edges_from(
            [
                (source_node, target_node, dict(zip(attr_col_headings, attrs)))
                for source_node, target_node, attrs in zip(
                    df[source], df[target], attribute_data
                )
            ]
        )
    else:
        for source_node, target_node, attrs in zip(df[source], df[target], attribute_data):
            graph.add_edge(source_node, target_node)
            graph[source_node][target_node].update(zip(attr_col_headings, attrs))

    return graph


def to_numpy_array(
    G,
    nodelist=None,
    dtype=None,
    order=None,
    multigraph_weight=sum,
    weight="weight",
    nonedge=0.0,
):
    """Return the adjacency matrix of G as a NumPy array.

    Parameters
    ----------
    G : Graph or DiGraph
        The input graph.
    nodelist : list, optional
        Rows and columns are ordered according to the nodes in *nodelist*.
        If ``None``, the ordering is produced by ``G.nodes()``.
    dtype : NumPy dtype, optional
        The NumPy data type of the array. Default ``numpy.float64``.
    order : {'C', 'F'}, optional
        Memory layout passed to ``numpy.full``.
    multigraph_weight : callable, optional
        Aggregation function used to combine parallel edge weights for
        multigraph inputs.
    weight : str or None, optional
        Edge attribute key used as weight. If ``None``, every edge has
        weight 1. Default ``'weight'``.
    nonedge : float, optional
        Value used for non-edges. Default ``0.0``.

    Returns
    -------
    A : numpy.ndarray
        Adjacency matrix as a 2-D NumPy array.
    """
    import numpy as np

    if nodelist is None:
        nodelist = list(G)
    else:
        nodelist = list(nodelist)
        missing = set(nodelist) - set(G)
        if missing:
            # br-r37-c1-6cdtz: the DENSE exporters (to_numpy_array,
            # to_pandas_adjacency) keep nx's plural set wording, unlike the
            # sparse/laplacian exporters which report the first missing node.
            # networkx checks membership before duplicates.
            raise NetworkXError(f"Nodes {missing} in nodelist is not in G")
        if len(set(nodelist)) != len(nodelist):
            raise NetworkXError("nodelist contains duplicates.")

    matrix = np.full(
        (len(nodelist), len(nodelist)),
        nonedge,
        dtype=dtype,
        order=order,
    )
    # networkx's corner cases come before any dtype/weight validation.
    if not nodelist or G.number_of_edges() == 0:
        return matrix
    index = {node: i for i, node in enumerate(nodelist)}
    if matrix.dtype.names:
        # networkx's structured-dtype branch: weight=None, one field per edge
        # attribute (default 1.0), simple graphs only.
        if weight is not None:
            raise ValueError(
                "Specifying `weight` not supported for structured dtypes\n."
                "To create adjacency matrices from structured dtypes, use `weight=None`."
            )
        if G.is_multigraph():
            raise NetworkXError("Structured arrays are not supported for MultiGraphs")
        rows, cols, datas = [], [], []
        for u, v, data in G.edges(data=True):
            if u in index and v in index:
                rows.append(index[u])
                cols.append(index[v])
                datas.append(data)
        for attr in matrix.dtype.names:
            attr_data = [data.get(attr, 1.0) for data in datas]
            matrix[attr][rows, cols] = attr_data
            if not G.is_directed():
                matrix[attr][cols, rows] = attr_data
        return matrix

    # Native COO values are f64. Inspect the actual array dtype: with
    # dtype=None, an integer ``nonedge`` can make np.full infer int64.
    # Narrower and extended floating dtypes must see the original values
    # to avoid a second rounding step. Parallel edges must also be reduced
    # in their original numeric domain before any array conversion.
    native_dtype_ok = matrix.dtype.names is None and (
        (matrix.dtype.kind == "f" and matrix.dtype.itemsize == 8)
        or (matrix.dtype.kind == "c" and matrix.dtype.itemsize == 16)
    )
    if (
        native_dtype_ok
        and _native_adjacency_arrays is not None
        and type(G) in (Graph, DiGraph)
        and not _has_networkx_private_storage(G)
        and isinstance(weight, str)
    ):
        # Keep the common float64 weighted path native while reading live
        # Python-visible mutations. A None weight key uses the Python path:
        # an attribute actually keyed by None is observable in NetworkX.
        _sync_rust_edge_attrs(G, edge_only=True)
        native_result = _native_adjacency_arrays(G, nodelist, weight, 1.0)
        if native_result is not None:
            rows, cols, data = native_result
            if rows:
                rows_arr = np.asarray(rows)
                cols_arr = np.asarray(cols)
                data_arr = np.asarray(data, dtype=matrix.dtype)
                matrix[rows_arr, cols_arr] = data_arr
            return matrix

    if G.is_multigraph():
        # Reduce live values before casting, just as NetworkX does. Casting
        # each parallel edge first can erase exact integer cancellation,
        # Python's compensated float sum, or even unit-edge counts in float16.
        # Assign all reduced values together so NumPy owns dtype conversion.
        reduced = {}
        for u, v, _, edge_attrs in G.edges(keys=True, data=True):
            if u in index and v in index:
                reduced.setdefault((index[u], index[v]), []).append(
                    edge_attrs.get(weight, 1.0)
                )
        rows, cols = np.array(list(reduced.keys())).T
        weights = [multigraph_weight(values) for values in reduced.values()]
        matrix[rows, cols] = weights
        if not G.is_directed():
            matrix[cols, rows] = weights
        return matrix

    # networkx's reference path for simple graphs (see the multigraph branch
    # above): collect every edge's value, default 1.0, then assign as a group.
    rows, cols, weights = [], [], []
    for u, v, edge_attrs in G.edges(data=True):
        if u in index and v in index:
            rows.append(index[u])
            cols.append(index[v])
            weights.append(edge_attrs.get(weight, 1.0))
    matrix[rows, cols] = weights
    if not G.is_directed():
        matrix[cols, rows] = weights
    return matrix


def from_numpy_array(
    A,
    parallel_edges=False,
    create_using=None,
    edge_attr="weight",
    *,
    nodelist=None,
):
    """Return a graph from a 2-D NumPy adjacency matrix.

    Parameters
    ----------
    A : numpy.ndarray
        A 2-D NumPy array interpreted as an adjacency matrix.
    parallel_edges : bool, optional
        If ``True`` and ``create_using`` is a multigraph, integer array
        entries create that many parallel edges.
    create_using : Graph constructor, optional
        Graph type to create. Default ``Graph()``.

    Returns
    -------
    G : Graph or DiGraph
        The constructed graph.
    """
    kind_to_python_type = {
        "f": float,
        "i": int,
        "u": int,
        "b": bool,
        "c": complex,
        "S": str,
        "U": str,
        "V": "void",
    }
    graph = _empty_graph_from_create_using(create_using)
    if A.ndim != 2:
        raise NetworkXError(f"Input array must be 2D, not {A.ndim}")
    n, m = A.shape
    if n != m:
        raise NetworkXError(f"Adjacency matrix not square: nx,ny={A.shape}")
    dtype = A.dtype
    try:
        python_type = kind_to_python_type[dtype.kind]
    except Exception as err:
        raise TypeError(f"Unknown numpy data type: {dtype}") from err

    default_nodes = nodelist is None
    if default_nodes:
        nodelist = range(n)
    else:
        if len(nodelist) != n:
            raise ValueError("nodelist must have the same length as A.shape[0]")

    if (
        default_nodes
        and type(graph) in (Graph, DiGraph)
        and isinstance(edge_attr, str)
        and not edge_attr.startswith("__fnx_incompatible")
        and dtype.kind in ("f", "i", "u", "b")
    ):
        rows, cols = A.nonzero()
        if graph._native_fill_weighted_int_edges(
            n, rows.tolist(), cols.tolist(), A[rows, cols].tolist(), edge_attr
        ):
            return graph

    graph.add_nodes_from(nodelist)
    edges = ((int(u), int(v)) for u, v in zip(*A.nonzero()))
    if python_type == "void":
        fields = sorted((offset, field_dtype, name) for name, (field_dtype, offset) in dtype.fields.items())
        triples = (
            (
                u,
                v,
                {}
                if edge_attr in [False, None]
                else {
                    name: kind_to_python_type[field_dtype.kind](value)
                    for (_, field_dtype, name), value in zip(fields, A[u, v])
                },
            )
            for u, v in edges
        )
    elif python_type is int and graph.is_multigraph() and parallel_edges:
        chain = _itertools.chain.from_iterable
        if edge_attr in [False, None]:
            triples = chain(((u, v, {}) for _ in range(A[u, v])) for (u, v) in edges)
        else:
            triples = chain(
                ((u, v, {edge_attr: 1}) for _ in range(A[u, v])) for (u, v) in edges
            )
    else:
        if edge_attr in [False, None]:
            triples = ((u, v, {}) for u, v in edges)
        else:
            triples = ((u, v, {edge_attr: python_type(A[u, v])}) for u, v in edges)

    if graph.is_multigraph() and not graph.is_directed():
        triples = ((u, v, attrs) for u, v, attrs in triples if u <= v)
    if not default_nodes:
        idx_to_node = dict(enumerate(nodelist))
        triples = ((idx_to_node[u], idx_to_node[v], attrs) for u, v, attrs in triples)

    graph.add_edges_from(triples)
    return graph


def _sparse_asformat(matrix, format):
    """networkx's final step of to_scipy_sparse_array: an unknown format is a
    NetworkXError, raised after every other validation
    (br-r37-c1-rc0923-epic-silent-wrong-answers-nro4w.7)."""
    try:
        return matrix.asformat(format)
    except ValueError as err:
        raise NetworkXError(f"Unknown sparse matrix format: {format}") from err


def _sparse_multigraph_sums_are_exact(G, weight):
    """Prove that the native f64 CSR accumulator cannot round any partial sum.

    Binary floats have power-of-two denominators. Expressing every weight in
    the finest input unit lets us bound every possible intermediate sum by
    the sum of absolute integer coefficients. Undirected self-loop correction
    can use three copies of a weight, so reserve that factor as well. Wider
    integers, non-builtin numerics, and rounding-sensitive sums use SciPy's
    original-value construction instead.
    """
    import math

    limit = (1 << 53) // (1 if G.is_directed() else 3)
    denominator = 1
    magnitude = 0
    nonempty = False
    for _, _, value in G.edges(data=weight, default=1):
        if type(value) is int:
            numerator, divisor = value, 1
        elif type(value) is float:
            if not math.isfinite(value) or (
                value == 0.0 and math.copysign(1.0, value) < 0
            ):
                return False
            numerator, divisor = value.as_integer_ratio()
        else:
            return False
        if divisor > denominator:
            magnitude *= divisor // denominator
            denominator = divisor
        magnitude += abs(numerator) * (denominator // divisor)
        if magnitude > limit:
            return False
        nonempty = True
    # An empty source infers float64, which the integral native buffer does
    # not distinguish from a nonempty graph containing integer zero weights.
    return nonempty


def _sparse_array_from_edge_values(G, index, dtype, weight, format):
    """Let SciPy infer/cast each original value before reducing duplicates."""
    import networkx as nx
    import scipy.sparse

    rows, cols, values, loops = [], [], [], []
    directed = G.is_directed()
    native_storage = (
        type(G) in (Graph, DiGraph, MultiGraph, MultiDiGraph)
        and not _has_networkx_private_storage(G)
        and G.edge_attr_dict_factory is dict
    )
    if (
        not isinstance(G, nx.Graph)
        and (weight is None or not native_storage)
        and weight is not True
        and weight is not False
    ):
        # Resolve selectors against the actual dictionaries on logical views
        # and custom storage. Their edge-data adapters may only project string
        # keys. NetworkX's edge view uses containment and subscription here,
        # rather than get(), whose behavior can differ on custom mappings.
        # Literal None keys need this path even on concrete native graphs.
        # True/False retain the public edge view's tuple-shape semantics.
        # Foreign graph providers already implement selector projection and
        # must observe the original data/default arguments instead.
        edges = (
            (u, v, attrs[weight] if weight in attrs else 1)
            for u, v, attrs in G.edges(data=True)
        )
    else:
        edges = G.edges(data=weight, default=1)
    for u, v, value in edges:
        if u not in index or v not in index:
            continue
        row, col = index[u], index[v]
        rows.append(row)
        cols.append(col)
        values.append(value)
        if not directed and u == v:
            loops.append((row, value))
    if not directed:
        edge_count = len(rows)
        rows.extend(cols)
        cols.extend(rows[:edge_count])
        values.extend(values)
        if not native_storage:
            # NetworkX reads self-loop data again after the main edge pass.
            # This pass uses get(), unlike the edge view's membership and
            # subscription protocol. Capture all corrections before applying
            # unary minus, since either read or arithmetic can have effects.
            if G.is_multigraph():
                loop_data = (
                    (node, node, attrs)
                    for node, neighbors in G._adj.items()
                    if node in neighbors
                    for attrs in neighbors[node].values()
                )
            else:
                loop_data = (
                    (node, node, neighbors[node])
                    for node, neighbors in G._adj.items()
                    if node in neighbors
                )
            if weight is True:
                correction_edges = loop_data
            elif weight is False:
                correction_edges = ((u, v) for u, v, _ in loop_data)
            else:
                correction_edges = (
                    (u, v, attrs.get(weight, 1)) for u, v, attrs in loop_data
                )
            loops = [
                (index[u], value)
                for u, v, value in correction_edges
                if u in index and v in index
            ]
        # Keep the correction entries themselves: their dtype, overflow,
        # non-finite behavior, and public COO representation are observable.
        for row, value in loops:
            rows.append(row)
            cols.append(row)
            values.append(-value)
    matrix = scipy.sparse.coo_array(
        (values, (rows, cols)), shape=(len(index), len(index)), dtype=dtype
    )
    return _sparse_asformat(matrix, format)


def to_scipy_sparse_array(G, nodelist=None, dtype=None, weight="weight", format="csr"):
    """Return the adjacency matrix of G as a SciPy sparse array.

    Parameters
    ----------
    G : Graph or DiGraph
        The input graph.
    nodelist : list, optional
        Rows and columns are ordered according to *nodelist*.
        If ``None``, the ordering is produced by ``G.nodes()``.
    dtype : NumPy dtype, optional
        Data type of the matrix entries. Default ``numpy.float64``.
    weight : str or None, optional
        Edge attribute key used as weight. ``None`` means weight 1.
        Default ``'weight'``.
    format : {'csr', 'csc', 'coo', 'lil', 'dok', 'bsr'}, optional
        Sparse matrix format. Default ``'csr'``.

    Returns
    -------
    A : scipy.sparse array
        Adjacency matrix in the requested sparse format.
    """
    import scipy.sparse

    # br-r37-c1-tssa-empty: nx.to_scipy_sparse_array raises NetworkXError
    # on len(G)==0 BEFORE consulting nodelist. Previously fnx returned
    # an empty 0×0 sparse array, which then cascaded into adjacency_matrix,
    # laplacian_matrix, normalized_laplacian_matrix, and the three
    # *_spectrum wrappers all silently returning [] on empty graphs
    # (nx raises on every one of those entry points).
    if len(G) == 0:
        raise NetworkXError("Graph has no nodes or edges")

    default_nodelist = nodelist is None
    native_multigraph_csr = (
        default_nodelist
        and dtype is None
        and format == "csr"
        and type(G) in (MultiGraph, MultiDiGraph)
        and not _has_networkx_private_storage(G)
        and isinstance(weight, str)
        and _sparse_multigraph_sums_are_exact(G, weight)
    )
    if (
        native_multigraph_csr
        and _native_adjacency_csr_bytes_multigraph_default_order_live_checked is not None
        and G.is_multigraph()
        and isinstance(G, MultiGraph)
        and not isinstance(G, MultiDiGraph)
        and isinstance(weight, str)
        and dtype is None
        and format == "csr"
    ):
        _mg_csr = _native_adjacency_csr_bytes_multigraph_default_order_live_checked(
            G, weight, 1.0
        )
        if _mg_csr is not None:
            import numpy as _np

            indptr_bytes, indices_bytes, data_bytes, data_is_int = _mg_csr
            n = len(G)
            data_dtype = _np.int64 if data_is_int else _np.float64
            data_arr = _np.frombuffer(data_bytes, dtype=data_dtype)
            matrix = scipy.sparse.csr_array(
                (
                    data_arr,
                    _np.frombuffer(indices_bytes, dtype=_np.intp),
                    _np.frombuffer(indptr_bytes, dtype=_np.intp),
                ),
                shape=(n, n),
            )
            return matrix

    if (
        native_multigraph_csr
        and _native_adjacency_csr_bytes_multidigraph_default_order_live_checked is not None
        and G.is_multigraph()
        and isinstance(G, MultiDiGraph)
        and isinstance(weight, str)
        and dtype is None
        and format == "csr"
    ):
        _mdg_csr = _native_adjacency_csr_bytes_multidigraph_default_order_live_checked(
            G, weight, 1.0
        )
        if _mdg_csr is not None:
            import numpy as _np

            indptr_bytes, indices_bytes, data_bytes, data_is_int = _mdg_csr
            n = len(G)
            data_dtype = _np.int64 if data_is_int else _np.float64
            data_arr = _np.frombuffer(data_bytes, dtype=data_dtype)
            matrix = scipy.sparse.csr_array(
                (
                    data_arr,
                    _np.frombuffer(indices_bytes, dtype=_np.intp),
                    _np.frombuffer(indptr_bytes, dtype=_np.intp),
                ),
                shape=(n, n),
            )
            return matrix

    if default_nodelist:
        nodelist = list(G)
    else:
        nodelist = list(nodelist)
        # br-r37-c1-tssa-nlist0: empty user-supplied nodelist on a
        # non-empty graph silently returned a 0×0 sparse matrix;
        # nx raises NetworkXError("nodelist has no nodes"). Order
        # the check BEFORE the duplicate / missing checks so the
        # message matches nx exactly when nlen == 0.
        if len(nodelist) == 0:
            raise NetworkXError("nodelist has no nodes")
        if len(set(nodelist)) != len(nodelist):
            raise NetworkXError("nodelist contains duplicates.")
        missing = set(nodelist) - set(G)
        if missing:
            # br-r37-c1-6cdtz: nx reports the FIRST missing node in nodelist
            # order, singular & str-formatted, not a set of all missing.
            first_missing = next(n for n in nodelist if n not in G)
            raise NetworkXError(f"Node {first_missing} in nodelist is not in G")

    index = {node: i for i, node in enumerate(nodelist)}
    is_directed = G.is_directed()
    if (
        G.is_multigraph()
        or weight is None
        or format in ("coo", None)
        or (not is_directed and number_of_selfloops(G))
    ):
        return _sparse_array_from_edge_values(G, index, dtype, weight, format)
    # br-r37-c1-lqlx2: native Rust COO builder for non-multigraph.
    # Iterates the IndexMap directly (~0.1ms for 1000 edges) instead
    # of Python's G._adj.items() loop (~3ms).  Returns None for
    # multigraph; we keep the dedup-by-sum Python path for those.
    # Requires sync because mutations via G[u][v][k]=v live in the
    # Python attrs view until pushed back to Rust storage.  Skip the
    # native path when caller passes an explicit ``dtype`` we'd have
    # to coerce in Python anyway (the dtype arg is preserved by the
    # scipy COO constructor when given to ``coo_array(..., dtype=)``).
    # br-r37-c1-wqtfe: also take the native COO builder for a string weight
    # key when the caller pins ``dtype`` (hits, kemeny, laplacian/spectral all
    # pass ``dtype=float``). The native helper reads the Rust ``inner`` AttrMap,
    # which can be stale after ``G[u][v][k]=v`` mutations, so sync first. We
    # only enable this when ``dtype`` is given because for ``dtype=None`` nx
    # infers int-vs-float from the original Python value types, which the
    # f64-returning native helper cannot reproduce; a pinned dtype removes that
    # ambiguity. The matrix is byte-identical to the Python path (COO -> CSR
    # canonicalises duplicate/ordering, and the (row, col, data) set matches).
    import numpy as _np

    requested_dtype = _np.dtype(dtype)
    # An explicit dtype does not make an f64 intermediate lossless: integer
    # and extended-precision exports must retain their original values, while
    # float32/complex64 conversions can be changed by double rounding.
    native_float_dtype = (
        requested_dtype.kind == "f" and requested_dtype.itemsize == 8
    ) or (requested_dtype.kind == "c" and requested_dtype.itemsize == 16)
    native_simple = type(G) in (Graph, DiGraph) and not _has_networkx_private_storage(G)
    _use_native_weighted = (
        isinstance(weight, str) and dtype is not None and native_float_dtype
    )
    _probe_native_missing_default_weight = (
        isinstance(weight, str)
        and dtype is None
        and _native_adjacency_index_arrays is not None
        and native_simple
    )
    if _probe_native_missing_default_weight and any(
        type(value) not in (int, float)
        or (type(value) is int and abs(value) > (1 << 53))
        for _, _, value in G.edges(data=weight, default=1)
    ):
        # The native store normalizes NumPy scalars to Python numeric kinds.
        # Default sparse dtype inference must instead see the original scalar
        # types, including uint64/longdouble values an f64 cannot represent.
        return _sparse_array_from_edge_values(G, index, dtype, weight, format)
    if (
        _native_adjacency_arrays is not None
        and native_simple
        and (weight is None or _use_native_weighted or _probe_native_missing_default_weight)
    ):
        # br-r37-c1-hits-bipartite-svds-degenerate-xjar9: weighted
        # matrix exports must read Python-visible attr dicts because
        # direct adjacency mutations can be stale in Rust storage —
        # push them into ``inner`` before the native read.
        if _use_native_weighted:
            _sync_rust_edge_attrs(G, edge_only=True)
        native_weight = weight if _use_native_weighted else None
        native_index_result = None
        if native_weight is None and _native_adjacency_index_arrays is not None:
            if not _probe_native_missing_default_weight:
                absent_weight_attr = weight if _probe_native_missing_default_weight else None
                if (
                    default_nodelist
                    and format == "csr"
                    and type(G) is Graph
                    and _native_adjacency_default_order_index_arrays is not None
                ):
                    native_index_result = _native_adjacency_default_order_index_arrays(
                        G, absent_weight_attr
                    )
                else:
                    native_index_result = _native_adjacency_index_arrays(
                        G, nodelist, absent_weight_attr
                    )
            if native_index_result is not None:
                rows, cols = native_index_result
                import numpy as _np
                # br-r37-c1-pmqhz-nl: nx infers float64 for an EMPTY edge set
                # (empty data list), int64 for unit weights otherwise.
                if dtype is None:
                    unit_dtype = _np.float64 if len(rows) == 0 else _np.int64
                else:
                    unit_dtype = dtype
                data = _np.ones(len(rows), dtype=unit_dtype)
                matrix = scipy.sparse.coo_array(
                    (data, (rows, cols)),
                    shape=(len(nodelist), len(nodelist)),
                    dtype=dtype,
                )
                return _sparse_asformat(matrix, format)
            if _probe_native_missing_default_weight:
                native_weight = None
            else:
                native_weight = weight if _use_native_weighted else None
        if (
            _probe_native_missing_default_weight
            and native_index_result is None
            and default_nodelist
            and type(G) in (Graph, DiGraph)
            and _native_adjacency_default_order_typed_arrays is not None
        ):
            # br-r37-c1-pmqhz: extended from Graph+csr-only to DiGraph and any
            # output format. The typed helper now handles directed default-order
            # graphs (out-edges); the result is COO-format-agnostic (the final
            # matrix.asformat(format) applies the requested format), so dropping
            # the format=="csr" gate is safe and closes the DiGraph (~3.3x) +
            # non-csr (~4.2x) weighted dtype=None gaps.
            # br-r37-c1-04z53.20: dtype=None with present string weights used
            # to fall back to Python edge iteration solely to preserve nx dtype
            # inference. The typed native helper returns conservative dtype
            # metadata; unsupported value kinds still return None and use the
            # exact Python fallback below.
            _sync_rust_edge_attrs(G, edge_only=True)
            typed_native_result = _native_adjacency_default_order_typed_arrays(
                G, weight, 1.0
            )
            if typed_native_result is not None:
                rows, cols, data, needs_float_dtype = typed_native_result
                import numpy as _np
                # br-r37-c1-pmqhz-nl: an empty edge set (e.g. a subset nodelist
                # with no internal edges) must be float64 — nx infers float64
                # from the empty data list, not int64.
                data_dtype = (
                    _np.float64 if (needs_float_dtype or len(data) == 0) else _np.int64
                )
                matrix = scipy.sparse.coo_array(
                    (
                        _np.asarray(data, dtype=data_dtype),
                        (
                            _np.asarray(rows, dtype=_np.intp),
                            _np.asarray(cols, dtype=_np.intp),
                        ),
                    ),
                    shape=(len(nodelist), len(nodelist)),
                )
                return _sparse_asformat(matrix, format)

        if (
            _probe_native_missing_default_weight
            and native_index_result is None
            and not default_nodelist
            and type(G) in (Graph, DiGraph)
            and _native_adjacency_nodelist_typed_arrays is not None
        ):
            # br-r37-c1-pmqhz-nl: explicit (non-default) nodelist with present
            # string weights and dtype=None used to fall back to per-edge
            # G[u][v] Python reads (~3.5-4.2x slower). The nodelist typed helper
            # remaps endpoints (storage order -> key -> nodelist position),
            # skipping edges outside a subset nodelist, with the same type-based
            # dtype metadata as the default-order helper.
            _sync_rust_edge_attrs(G, edge_only=True)
            typed_native_result = _native_adjacency_nodelist_typed_arrays(
                G, nodelist, weight, 1.0
            )
            if typed_native_result is not None:
                rows, cols, data, needs_float_dtype = typed_native_result
                import numpy as _np
                # br-r37-c1-pmqhz-nl: an empty edge set (e.g. a subset nodelist
                # with no internal edges) must be float64 — nx infers float64
                # from the empty data list, not int64.
                data_dtype = (
                    _np.float64 if (needs_float_dtype or len(data) == 0) else _np.int64
                )
                matrix = scipy.sparse.coo_array(
                    (
                        _np.asarray(data, dtype=data_dtype),
                        (
                            _np.asarray(rows, dtype=_np.intp),
                            _np.asarray(cols, dtype=_np.intp),
                        ),
                    ),
                    shape=(len(nodelist), len(nodelist)),
                )
                return _sparse_asformat(matrix, format)

        if _probe_native_missing_default_weight and native_index_result is None:
            native_result = None
        elif (
            _use_native_weighted
            and default_nodelist
            and format == "csr"
            and type(G) is Graph
            and _native_adjacency_default_order_arrays is not None
        ):
            native_result = _native_adjacency_default_order_arrays(
                G, native_weight, 1.0
            )
        else:
            native_result = _native_adjacency_arrays(G, nodelist, native_weight, 1.0)
        if native_result is not None:
            rows, cols, data = native_result
            # br-r37-c1-tssadtype: nx preserves int dtype when every
            # edge weight is an integer (literal int 1 for weight=None;
            # or integer-valued ``weight=`` attrs).  Native helper
            # returns Vec<f64> uniformly; vectorize the integer-check
            # via numpy (~5× faster than the Python ``all()`` loop on
            # a 50k-edge graph).  Float values get a short-circuit
            # early-exit when ``all()`` discovers the first non-int.
            import numpy as _np
            if dtype is None and data:
                data_arr = _np.asarray(data)
                if _np.array_equal(data_arr, data_arr.astype(_np.int64)):
                    matrix = scipy.sparse.coo_array(
                        (data_arr.astype(_np.int64), (rows, cols)),
                        shape=(len(nodelist), len(nodelist)),
                    )
                else:
                    matrix = scipy.sparse.coo_array(
                        (data_arr, (rows, cols)),
                        shape=(len(nodelist), len(nodelist)),
                    )
            else:
                if _use_native_weighted:
                    rows = _np.asarray(rows, dtype=_np.intp)
                    cols = _np.asarray(cols, dtype=_np.intp)
                    data = _np.asarray(data, dtype=dtype)
                matrix = scipy.sparse.coo_array(
                    (data, (rows, cols)),
                    shape=(len(nodelist), len(nodelist)),
                    dtype=dtype,
                )
            return _sparse_asformat(matrix, format)

    return _sparse_array_from_edge_values(G, index, dtype, weight, format)


def from_scipy_sparse_array(
    A, parallel_edges=False, create_using=None, edge_attribute="weight"
):
    """Return a graph from a SciPy sparse array.

    Parameters
    ----------
    A : scipy.sparse array or matrix
        An adjacency matrix representation of a graph.
    parallel_edges : bool, optional
        If ``True`` and ``create_using`` is a multigraph, integer sparse
        entries create that many parallel edges.
    create_using : Graph constructor, optional
        Graph type to create. Default ``Graph()``.
    edge_attribute : str, optional
        Name of the edge attribute to set from matrix values.
        Default ``'weight'``.

    Returns
    -------
    G : Graph or DiGraph
        The constructed graph.
    """
    graph = _empty_graph_from_create_using(create_using)
    n, m = A.shape
    if n != m:
        raise NetworkXError(f"Adjacency matrix not square: nx,ny={A.shape}")

    coo = A.tocoo()
    # NumPy retains longdouble/clongdouble scalars when no Python numeric
    # type can represent them losslessly. Match NetworkX's tolist conversion
    # instead of narrowing those values to float or complex in the fallback.
    edge_values = coo.data.tolist()
    if (
        type(graph) in (Graph, DiGraph)
        and isinstance(edge_attribute, str)
        and not edge_attribute.startswith("__fnx_incompatible")
        and A.dtype.kind in ("f", "i", "u", "b")
    ):
        if graph._native_fill_weighted_int_edges(
            n, coo.row.tolist(), coo.col.tolist(), edge_values, edge_attribute
        ):
            return graph

    graph.add_nodes_from(range(n))
    triples = (
        (int(u), int(v), weight)
        for u, v, weight in zip(coo.row, coo.col, edge_values)
    )
    if A.dtype.kind in ("i", "u") and graph.is_multigraph() and parallel_edges:
        chain = _itertools.chain.from_iterable
        triples = chain(((u, v, 1) for _ in range(int(weight))) for (u, v, weight) in triples)
    if graph.is_multigraph() and not graph.is_directed():
        triples = ((u, v, weight) for u, v, weight in triples if u <= v)

    if edge_attribute is None:
        # br-r37-c1-oa0fs: nx accepts ``edge_attribute=None`` and uses
        # the literal ``None`` as the edge-attribute dict key. fnx's
        # ``add_weighted_edges_from`` *and* ``add_edges_from`` both
        # validate attr keys against ``str``, rejecting ``None``. Add
        # each edge first (no attrs), then set ``G[u][v][None] = w``
        # directly — the per-edge dict accepts arbitrary hashable keys.
        if graph.is_multigraph():
            for u, v, w in triples:
                key = graph.add_edge(u, v)
                graph[u][v][key][None] = w
        else:
            for u, v, w in triples:
                graph.add_edge(u, v)
                graph[u][v][None] = w
    elif graph.is_multigraph():
        graph.add_weighted_edges_from(triples, weight=edge_attribute)
    else:
        # br-r37-c1-scipybulk: simple-graph path routes through the bulk
        # attributed add_edges_from (one native edge batch) instead of
        # add_weighted_edges_from's per-edge streaming add_edge — ~2.3x
        # faster on dense COO. The COO triples are clean int endpoints +
        # numeric weights, so the streaming error-contract is moot here;
        # result (edges + weight attr) is byte-identical.
        graph.add_edges_from((u, v, {edge_attribute: w}) for u, v, w in triples)
    return graph


def _install_convert_matrix_native_aliases():
    import importlib as _importlib

    module = _importlib.import_module(f"{__name__}.convert_matrix")
    for name in (
        "from_numpy_array",
        "from_pandas_adjacency",
        "from_pandas_edgelist",
        "from_scipy_sparse_array",
        "to_numpy_array",
        "to_pandas_adjacency",
        "to_pandas_edgelist",
        "to_scipy_sparse_array",
    ):
        setattr(module, name, globals()[name])
    globals()["convert_matrix"] = module


_install_convert_matrix_native_aliases()


def from_dict_of_dicts(d, create_using=None, multigraph_input=False):
    """Return a graph from a dictionary of dictionaries."""
    graph = _empty_graph_from_create_using(create_using)
    graph.add_nodes_from(d)

    if _try_from_dict_multigraph_batch(graph, d, multigraph_input):
        return graph

    if multigraph_input:
        if graph.is_directed():
            if graph.is_multigraph():
                for u, nbrs in d.items():
                    for v, edge_map in nbrs.items():
                        for edge_key, edge_attrs in edge_map.items():
                            _add_json_multiedge(graph, u, v, edge_key, dict(edge_attrs))
            else:
                for u, nbrs in d.items():
                    for v, edge_map in nbrs.items():
                        for _, edge_attrs in edge_map.items():
                            graph.add_edge(u, v)
                            graph[u][v].update(edge_attrs)
        else:
            seen = set()
            if graph.is_multigraph():
                for u, nbrs in d.items():
                    for v, edge_map in nbrs.items():
                        if (u, v) in seen:
                            continue
                        for edge_key, edge_attrs in edge_map.items():
                            _add_json_multiedge(graph, u, v, edge_key, dict(edge_attrs))
                        seen.add((v, u))
            else:
                for u, nbrs in d.items():
                    for v, edge_map in nbrs.items():
                        if (u, v) in seen:
                            continue
                        for _, edge_attrs in edge_map.items():
                            graph.add_edge(u, v)
                            graph[u][v].update(edge_attrs)
                        seen.add((v, u))
        return graph

    if graph.is_multigraph():
        if graph.is_directed():
            for u, nbrs in d.items():
                for v, edge_attrs in nbrs.items():
                    _add_json_multiedge(graph, u, v, 0, dict(edge_attrs))
        else:
            seen = set()
            for u, nbrs in d.items():
                for v, edge_attrs in nbrs.items():
                    if (u, v) in seen:
                        continue
                    _add_json_multiedge(graph, u, v, 0, dict(edge_attrs))
                    seen.add((v, u))
    elif type(graph) in (Graph, DiGraph):
        add_edges = graph.add_edges_from
        if getattr(add_edges, "__func__", None) is not _SIMPLE_DICT_IMPORT_ADD_EDGES_FROM[type(graph)]:
            # Assigned storage and overridden graph methods retain their own
            # incremental implementation and one public add_edges_from call.
            add_edges(
                (u, v, attrs) for u, neighbors in d.items()
                for v, attrs in neighbors.items()
            )
            return graph
        rows = None
        if (
            not _has_networkx_private_storage(graph)
            and graph.node_attr_dict_factory is dict
            and graph.edge_attr_dict_factory is dict
        ):
            rows = _simple_dict_import_plain_rows(d)
        if rows is None:
            # A row or attribute provider may observe the target, change a
            # later source row, or fail after a valid prefix. The general
            # add_edges_from wrapper buffers iterators; commit each edge
            # before advancing the caller's traversal.
            for u, neighbors in d.items():
                for v, attrs in neighbors.items():
                    _add_dict_simple_edge(graph, add_edges, u, v, attrs)
        elif type(graph) is Graph:
            # Identical symmetric plain dictionaries have no observable
            # second update. Keep the existing deduplicated native batch for
            # this common case; distinct reciprocal attrs still merge in order.
            seen = set()
            batch = []
            for u, neighbors in rows.items():
                for v, attrs in neighbors.items():
                    if (
                        u != v and (v, u) in seen
                        and v in rows and rows[v].get(u) is attrs
                    ):
                        continue
                    batch.append((u, v, attrs))
                    seen.add((u, v))
            add_edges(batch)
        else:
            add_edges(
                (u, v, attrs) for u, neighbors in rows.items()
                for v, attrs in neighbors.items()
            )
    else:
        # Subclasses and networkx graphs given as create_using: networkx's own
        # statement, one add_edges_from over the triples. The former
        # add_edge + graph[u][v].update loop read the edge back through
        # __getitem__, which is not the adjacency on every class (networkx's
        # AntiGraph returns the complement: KeyError, nro4w.7).
        graph.add_edges_from(
            (u, v, edge_attrs) for u, nbrs in d.items() for v, edge_attrs in nbrs.items()
        )

    return graph


def from_edgelist(edgelist, create_using=None):
    """Return a graph from a list of edges.

    Parameters
    ----------
    edgelist : iterable
        Each element is a tuple (u, v) or (u, v, d) where d is a dict of
        edge attributes.
    create_using : Graph constructor, optional
        Graph type to create. Default ``Graph()``.

    Returns
    -------
    G : Graph or DiGraph
    """
    G = _empty_graph_from_create_using(create_using)

    G.add_edges_from(edgelist)
    return G


def to_dict_of_dicts(G, nodelist=None, edge_data=None):
    """Return adjacency representation as a dictionary of dictionaries.

    Parameters
    ----------
    G : Graph or DiGraph
        The input graph.
    nodelist : list, optional
        Use only nodes in *nodelist*. Default: all nodes.
    edge_data : object, optional
        If provided, use this as the edge data instead of the edge
        attribute dict.

    Returns
    -------
    d : dict
        ``d[u][v]`` is the edge data for (u, v).
    """
    # br-r37-c1-yl59j/br-r37-c1-nocb2: native fast path for exact simple
    # Graph/DiGraph with no nodelist/edge_data override. Builds the nested dict
    # in Rust reusing live edge-attr dict objects (same refs as G[u][v]) in
    # adjacency/successor order.
    if (
        nodelist is None
        and edge_data is None
        and type(G) in (Graph, DiGraph)
        and not _has_networkx_private_storage(G)
    ):
        _fast = _fnx.to_dict_of_dicts_undirected(G)
        if _fast is not None:
            return _fast
    d = {}
    # br-r37-c1-5cqna: with no nodelist, networkx hands out a multigraph's own
    # keydicts (dod[u] = nbrdict.copy()), so d[u][v] is a real dict whose
    # storage holds {key: datadict}: live, writes through it reach the graph,
    # and d[u][v] is d[v][u] on an undirected graph. fnx's keydict is
    # _MultiEdgeKeydict, which get_edge_data(u, v) returns and the graph keeps
    # in step. A lazy view with empty storage (br-r37-c1-mexh6) read as {} to
    # json and every other reader of the dict storage. With a nodelist,
    # networkx's d[u][v] is the G[u][v] view instead - the loop at the end.
    # The native walk registers a keydict for every pair once, then only looks
    # them up, and ``_multi_keydict_todod_rows`` reuses the rows until the
    # graph's shape changes.
    if nodelist is None:
        if edge_data is not None:
            for u, nbrdict in G.adjacency():
                d[u] = dict.fromkeys(nbrdict, edge_data)
            return d
        if (
            type(G) in (MultiGraph, MultiDiGraph)
            and not _has_networkx_private_storage(G)
        ):
            return _multi_keydict_todod_rows(G, G._native_to_dict_of_dicts_live)
        if (
            isinstance(G, (MultiGraph, MultiDiGraph))
            and _PRIVATE_ADJ_OVERRIDE not in G.__dict__
            and _PRIVATE_SUCC_OVERRIDE not in G.__dict__
            and getattr(G.adjacency, "__func__", None) is _multigraph_adjacency
        ):
            # Native-backed subclasses also need real, registered keydicts:
            # adjacency() exposes snapshot keydicts, unlike NetworkX's rows.
            keydict = (MultiDiGraph if G.is_directed() else MultiGraph).get_edge_data
            for u, nbrdict in G.adjacency():
                d[u] = {v: keydict(G, u, v) for v in nbrdict}
            return d
        # A synthetic view's native base is empty. Its public row wrapper also
        # need not have the raw row's copy semantics: a directed conversion
        # shares rows, whereas UnionAtlas.copy merges and copies attributes.
        if isinstance(G, _ConversionGraphViewBase):
            source = G._graph
            if G.is_directed() or not source.is_directed():
                return to_dict_of_dicts(source)
            succ, pred = source._succ, source._pred
            for u in succ:
                outgoing, incoming = succ[u], pred[u]
                if G.is_multigraph():
                    row = {}
                    for v in set(outgoing) | set(incoming):
                        keys = {
                            key: attrs.copy()
                            for key, attrs in outgoing.get(v, {}).items()
                        }
                        for key, attrs in incoming.get(v, {}).items():
                            if key in keys:
                                keys[key].update(attrs)
                            else:
                                keys[key] = attrs.copy()
                        row[v] = keys
                else:
                    row = {v: attrs.copy() for v, attrs in outgoing.items()}
                    for v, attrs in incoming.items():
                        if v in row:
                            row[v].update(attrs)
                        else:
                            row[v] = attrs.copy()
                d[u] = row
            return d
        if isinstance(G, _ReverseDirectedViewBase):
            for u, nbrdict in G._graph._pred.items():
                if _atlas_is_filtered(nbrdict):
                    name = "FilterMultiInner" if G.is_multigraph() else "FilterAtlas"
                    raise AttributeError(f"'{name}' object has no attribute 'copy'")
                d[u] = dict(nbrdict.items())
            return d
        simple_native_rows = (
            isinstance(G, (Graph, DiGraph))
            and _PRIVATE_ADJ_OVERRIDE not in G.__dict__
            and _PRIVATE_SUCC_OVERRIDE not in G.__dict__
            and getattr(G.adjacency, "__func__", None) is _simple_graph_adjacency
        )
        for u, nbrdict in G.adjacency():
            if isinstance(G, _FilteredGraphView):
                name = "FilterMultiInner" if G.is_multigraph() else "FilterAtlas"
                raise AttributeError(f"'{name}' object has no attribute 'copy'")
            d[u] = dict(nbrdict.items()) if simple_native_rows else nbrdict.copy()
        return d
    for u in nodelist:
        d[u] = {}
        if edge_data is None:
            for v, data in G[u].items():
                if v in nodelist:
                    # Reverse multigraph rows can expose raw keydicts here;
                    # NetworkX's explicit-nodelist export keeps an AtlasView.
                    if (
                        isinstance(G, _ReverseDirectedViewBase)
                        and G.is_multigraph()
                        and isinstance(data, dict)
                    ):
                        data = AtlasView(lambda data=data: data)
                    d[u][v] = data
        else:
            for v in G[u]:
                if v in nodelist:
                    d[u][v] = edge_data
    return d


def _materialized_view(view):
    """cc-nldmaterialize: return a view's RAW materialized list when it exposes the
    private ``_materialize()`` (every NodeDataView + the simple-Graph EdgeDataView),
    else the view itself. Skips the per-element ``_FailFastEdgeIterator``/``_gen``
    mutation-during-iteration guard for INTERNAL read-only consumers (serializers)
    that never mutate G mid-build — same tuples, same order (byte-identical). The
    guarded generator is ~1.85x slower on a 3000-edge walk (0.73->0.39ms)."""
    materialize = getattr(view, "_materialize", None)
    return materialize() if materialize is not None else view


def cytoscape_data(G, name="name", ident="id"):
    """Export graph to Cytoscape.js JSON format."""
    if name == ident:
        raise NetworkXError("name and ident must be different.")

    payload = {
        "data": list(G.graph.items()),
        "directed": G.is_directed(),
        "multigraph": G.is_multigraph(),
        "elements": {"nodes": [], "edges": []},
    }
    for node, node_attrs in _materialized_view(G.nodes(data=True)):
        node_payload = {"data": dict(node_attrs)}
        node_payload["data"]["id"] = node_attrs.get(ident) or str(node)
        node_payload["data"]["value"] = node
        node_payload["data"]["name"] = node_attrs.get(name) or str(node)
        payload["elements"]["nodes"].append(node_payload)

    if G.is_multigraph():
        for u, v, edge_key, edge_attrs in _materialized_view(
            G.edges(keys=True, data=True)
        ):
            edge_payload = {"data": dict(edge_attrs)}
            edge_payload["data"]["source"] = u
            edge_payload["data"]["target"] = v
            edge_payload["data"]["key"] = edge_key
            payload["elements"]["edges"].append(edge_payload)
    else:
        for u, v, edge_attrs in _materialized_view(G.edges(data=True)):
            edge_payload = {"data": dict(edge_attrs)}
            edge_payload["data"]["source"] = u
            edge_payload["data"]["target"] = v
            payload["elements"]["edges"].append(edge_payload)
    return payload


def cytoscape_graph(data, name="name", ident="id"):
    """Build graph from Cytoscape.js JSON format."""
    if name == ident:
        raise NetworkXError("name and ident must be different.")

    multigraph = data.get("multigraph")
    directed = data.get("directed")
    graph = _json_graph_from_flags(
        directed=bool(directed),
        multigraph=bool(multigraph),
    )
    graph.graph.update(dict(data.get("data")))

    # br-r37-c1-cytobatch: collect the (node, data) and (source, target, data)
    # tuples and BUILD via add_nodes_from / add_edges_from in one batch instead of
    # a per-node ``add_node`` + ``nodes[node].update`` AND per-edge ``add_edge`` +
    # ``edges[s, t].update`` PyO3 round-trip (4 view crossings per element, the
    # dominant cost vs nx). 0.27x -> 1.55x (7.8x self). Simple Graph/DiGraph only;
    # the multigraph path keeps ``_add_json_multiedge`` (keyed parallel edges).
    if not multigraph:
        nodes_batch = []
        for node_entry in data["elements"]["nodes"]:
            node_data = node_entry["data"].copy()
            node = node_entry["data"]["value"]
            if node_entry["data"].get(name):
                node_data[name] = node_entry["data"].get(name)
            if node_entry["data"].get(ident):
                node_data[ident] = node_entry["data"].get(ident)
            nodes_batch.append((node, node_data))
        edges_batch = [
            (
                edge_entry["data"]["source"],
                edge_entry["data"]["target"],
                edge_entry["data"].copy(),
            )
            for edge_entry in data["elements"]["edges"]
        ]
        graph.add_nodes_from(nodes_batch)
        graph.add_edges_from(edges_batch)
        return graph

    for node_entry in data["elements"]["nodes"]:
        node_data = node_entry["data"].copy()
        node = node_entry["data"]["value"]

        if node_entry["data"].get(name):
            node_data[name] = node_entry["data"].get(name)
        if node_entry["data"].get(ident):
            node_data[ident] = node_entry["data"].get(ident)

        graph.add_node(node)
        graph.nodes[node].update(node_data)

    for edge_entry in data["elements"]["edges"]:
        edge_data = edge_entry["data"].copy()
        source = edge_entry["data"]["source"]
        target = edge_entry["data"]["target"]
        edge_key = edge_entry["data"].get("key", 0)
        _add_json_multiedge(graph, source, target, edge_key, edge_data)
    return graph
