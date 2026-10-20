

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

    # br-r37-c1-rc0923-epic-silent-wrong-answers-nro4w.6: networkx assigns the
    # attribute values through numpy, so numpy decides every conversion and
    # error. The native builders return float64 values (and fail closed on a
    # weight that is not a real number), which is only equivalent when the
    # requested dtype is a float or complex one — an int/bool dtype must see
    # the exact Python ints, object and structured dtypes the values themselves.
    requested_dtype = np.dtype(dtype)
    native_dtype_ok = requested_dtype.names is None and requested_dtype.kind in "fc"

    if nodelist is None:
        if (
            native_dtype_ok
            and _native_adjacency_arrays_multigraph_default_order_live_checked is not None
            and multigraph_weight is sum
            and nonedge == 0
            and isinstance(G, MultiDiGraph)
            and G.is_multigraph()
            and isinstance(weight, str)
        ):
            _mg_default = _native_adjacency_arrays_multigraph_default_order_live_checked(
                G, weight, 1.0
            )
            if _mg_default is not None:
                rows, cols, data = _mg_default
                matrix = np.full(
                    (len(G), len(G)),
                    nonedge,
                    dtype=dtype,
                    order=order,
                )
                if rows:
                    np.add.at(
                        matrix,
                        (np.asarray(rows), np.asarray(cols)),
                        np.asarray(data, dtype=matrix.dtype),
                    )
                return matrix
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

    # br-r37-c1-lqlx2: native Rust COO builder, same fast path as
    # to_scipy_sparse_array.  Scatter (rows, cols, data) into the
    # pre-allocated dense matrix.
    if (
        native_dtype_ok
        and _native_adjacency_arrays is not None
        and not G.is_multigraph()
        and isinstance(G, (Graph, DiGraph))
        and (weight is None or isinstance(weight, str))
    ):
        # br-r37-c1-hits-bipartite-svds-degenerate-xjar9: use the native
        # helper only when no edge attrs are read. Python-visible mutations
        # like ``G[u][v]["weight"] = 7`` can otherwise be stale in Rust
        # storage, while the fallback reads the live Python attr dicts.
        #
        # br-tnaweighted: extend the native COO builder to the weighted case
        # (string ``weight`` key). Unlike ``to_scipy_sparse_array`` we never
        # need native int-vs-float dtype inference here: the matrix dtype is
        # already fixed by ``np.full(..., nonedge, dtype=...)`` above (float64
        # for the default ``nonedge=0.0``), so the f64-returning native helper
        # scatters into it exactly as the Python ``G._adj`` loop would assign
        # ``edge_attrs.get(weight, 1)``. Direct ``G[u][v][k]=v`` mutations can
        # be stale in Rust storage, so push them into ``inner`` before reading.
        if weight is not None:
            _sync_rust_edge_attrs(G, edge_only=True)
        native_result = _native_adjacency_arrays(
            G, nodelist, weight if weight is not None else None, 1.0
        )
        if native_result is not None:
            rows, cols, data = native_result
            if rows:
                rows_arr = np.asarray(rows)
                cols_arr = np.asarray(cols)
                data_arr = np.asarray(data, dtype=matrix.dtype)
                matrix[rows_arr, cols_arr] = data_arr
            return matrix

    if G.is_multigraph():
        # br-r37-c1-iyu0a: native multigraph COO fast path for the default
        # ``multigraph_weight=sum`` aggregation. The native helper emits one
        # entry per parallel edge (symmetric for undirected non-self-loops);
        # ``np.add.at`` accumulates duplicates into the matrix exactly like
        # ``sum(parallel weights)``. Gated to ``nonedge == 0`` (add.at sums onto
        # the matrix base) and a finite-numeric weight scan (the f64 helper
        # coerces non-numeric/non-finite weights to the default). ~2x over the
        # Python parallel-edge dict-of-lists loop; byte-identical to nx.
        if (
            native_dtype_ok
            and multigraph_weight is sum
            and nonedge == 0
            and isinstance(G, (MultiGraph, MultiDiGraph))
            and (weight is None or isinstance(weight, str))
        ):
            # br-r37-c1-iyu0a: weight=None uses unit weights (no finiteness
            # concern); weight=str uses the fused COO+finiteness kernel — ONE
            # edge pass instead of a separate non-finite scan + COO. The checked
            # kernel returns None on a non-numeric/non-finite weight, falling
            # through to the exact Python loop.
            _mg = None
            if weight is None and _native_adjacency_arrays_multigraph is not None:
                _mg = _native_adjacency_arrays_multigraph(G, nodelist, None, 1.0)
            elif (
                isinstance(weight, str)
                and _native_adjacency_arrays_multigraph_checked is not None
            ):
                if (
                    isinstance(G, MultiDiGraph)
                    and _native_adjacency_arrays_multigraph_live_checked is not None
                ):
                    _mg = _native_adjacency_arrays_multigraph_live_checked(
                        G, nodelist, weight, 1.0
                    )
                if _mg is None:
                    _sync_rust_edge_attrs(G, edge_only=True)
                    _mg = _native_adjacency_arrays_multigraph_checked(
                        G, nodelist, weight, 1.0
                    )
            if _mg is not None:
                rows, cols, data = _mg
                if rows:
                    np.add.at(
                        matrix,
                        (np.asarray(rows), np.asarray(cols)),
                        np.asarray(data, dtype=matrix.dtype),
                    )
                return matrix
        # networkx's reference path, step for step: the missing-attribute
        # default is 1.0 (``G.edges(data=weight, default=1.0)``; with
        # weight=None that is every edge), parallel weights are reduced per
        # (row, col), and the reduced values go into the array in ONE
        # advanced-index assignment, so numpy converts them as a group.
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
    if (
        default_nodelist
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
        default_nodelist
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

    if (
        default_nodelist
        and _native_adjacency_csr_multidigraph_default_order_live_checked is not None
        and G.is_multigraph()
        and isinstance(G, MultiDiGraph)
        and isinstance(weight, str)
        and dtype is None
        and format == "csr"
    ):
        _mdg_csr = _native_adjacency_csr_multidigraph_default_order_live_checked(
            G, weight, 1.0
        )
        if _mdg_csr is not None:
            import numpy as _np

            indptr, indices, data = _mdg_csr
            n = len(G)
            if data:
                data_arr = _np.asarray(data)
                if _np.array_equal(data_arr, data_arr.astype(_np.int64)):
                    data_arr = data_arr.astype(_np.int64)
            else:
                data_arr = _np.asarray(data, dtype=_np.float64)
            matrix = scipy.sparse.csr_array(
                (
                    data_arr,
                    _np.asarray(indices, dtype=_np.intp),
                    _np.asarray(indptr, dtype=_np.intp),
                ),
                shape=(n, n),
            )
            return matrix

    if (
        default_nodelist
        and _native_adjacency_arrays_multigraph_default_order_live_checked is not None
        and G.is_multigraph()
        and isinstance(G, MultiDiGraph)
        and isinstance(weight, str)
        and dtype is None
    ):
        _mg_default = _native_adjacency_arrays_multigraph_default_order_live_checked(
            G, weight, 1.0
        )
        if _mg_default is not None:
            import numpy as _np

            rows, cols, data = _mg_default
            n = len(G)
            if data:
                data_arr = _np.asarray(data)
                if _np.array_equal(data_arr, data_arr.astype(_np.int64)):
                    matrix = scipy.sparse.coo_array(
                        (data_arr.astype(_np.int64), (rows, cols)),
                        shape=(n, n),
                    )
                else:
                    matrix = scipy.sparse.coo_array(
                        (data_arr, (rows, cols)),
                        shape=(n, n),
                    )
            else:
                matrix = scipy.sparse.coo_array(
                    (data, (rows, cols)),
                    shape=(n, n),
                )
            return _sparse_asformat(matrix, format)

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
    weight_is_none = weight is None
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
    _use_native_weighted = isinstance(weight, str) and dtype is not None
    _probe_native_missing_default_weight = (
        isinstance(weight, str)
        and dtype is None
        and _native_adjacency_index_arrays is not None
        and not G.is_multigraph()
        and isinstance(G, (Graph, DiGraph))
    )
    if (
        _native_adjacency_arrays is not None
        and not G.is_multigraph()
        and isinstance(G, (Graph, DiGraph))
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

    # br-r37-c1-mexh6: native COO builder for MultiGraph / MultiDiGraph.
    # Emits one COO entry per parallel edge (symmetric for undirected
    # non-self-loops); scipy sums duplicate coordinates at format conversion,
    # producing a matrix identical to the pre-accumulated Python path below
    # (and to nx, which likewise emits per-edge duplicates). Gated like the
    # simple weighted path: weight=None (unit weights) or a string weight key
    # with a pinned dtype — a pinned dtype removes nx's int/float inference
    # ambiguity that the f64-returning native helper cannot reproduce. The
    # native helper reads the Rust inner AttrMap, stale after G[u][v][k]=v
    # mutations, so sync edge attrs first when a weight key is used.
    # br-r37-c1-iyu0a: the default weighted call ``weight='weight', dtype=None``
    # used to skip the native multigraph COO builder (gated on a pinned dtype to
    # dodge nx's int/float inference), falling to the ~2x-slower Python
    # parallel-edge-sum loop. The body below ALREADY reproduces nx's inference
    # (``array_equal(data, data.astype(int64))``), and the f64-returning native
    # helper silently coerces non-numeric/non-finite weights to the default — so
    # admit ``dtype=None`` only when the native non-finite/non-numeric scan
    # confirms every present weight is finite-numeric (absent => default 1,
    # matching nx). Byte-identical to nx across int/float/missing/self-loop.
    # br-r37-c1-iyu0a: native multigraph COO for the default weighted call.
    #   weight=None              -> unit weights, plain kernel
    #   weight=str, dtype set    -> plain kernel (pinned dtype removes nx's
    #                               int/float inference ambiguity)
    #   weight=str, dtype=None   -> FUSED COO + finiteness kernel: ONE edge pass
    #                               instead of a separate non-finite scan + COO;
    #                               returns None on a non-numeric/non-finite
    #                               weight so we fall through to the exact Python
    #                               loop. The body reproduces nx's int/float
    #                               inference (array_equal(data, data.astype int)).
    # COO exposes duplicate coordinates, so it must retain NetworkX's exact
    # per-edge ordering rather than taking the native multigraph builder.  For
    # an undirected multigraph NetworkX emits all stored edges first, then the
    # reverse entries, and finally a negative self-loop correction.  Other
    # sparse formats canonicalize duplicates, so their native path remains
    # equivalent and faster.
    if G.is_multigraph() and format == "coo":
        rows = []
        cols = []
        data = []
        self_loops = []
        for u, v, _, edge_attrs in G.edges(keys=True, data=True):
            ui = index.get(u)
            vi = index.get(v)
            if ui is None or vi is None:
                continue
            edge_value = 1 if weight_is_none else edge_attrs.get(weight, 1)
            rows.append(ui)
            cols.append(vi)
            data.append(edge_value)
            if not is_directed and u == v:
                self_loops.append((ui, edge_value))
        if not is_directed:
            rows.extend(cols)
            cols.extend(rows[: len(cols)])
            data.extend(data)
            for ui, edge_value in self_loops:
                rows.append(ui)
                cols.append(ui)
                data.append(-edge_value)
        matrix = scipy.sparse.coo_array(
            (data, (rows, cols)),
            shape=(len(nodelist), len(nodelist)),
            dtype=dtype,
        )
        return matrix

    _mg_native = None
    if G.is_multigraph() and isinstance(G, (MultiGraph, MultiDiGraph)):
        if weight is None and _native_adjacency_arrays_multigraph is not None:
            _mg_native = _native_adjacency_arrays_multigraph(G, nodelist, None, 1.0)
        elif (
            isinstance(weight, str)
            and dtype is not None
            and _native_adjacency_arrays_multigraph is not None
        ):
            _sync_rust_edge_attrs(G, edge_only=True)
            _mg_native = _native_adjacency_arrays_multigraph(G, nodelist, weight, 1.0)
        elif (
            isinstance(weight, str)
            and dtype is None
            and _native_adjacency_arrays_multigraph_checked is not None
        ):
            if (
                isinstance(G, MultiDiGraph)
                and _native_adjacency_arrays_multigraph_live_checked is not None
            ):
                _mg_native = _native_adjacency_arrays_multigraph_live_checked(
                    G, nodelist, weight, 1.0
                )
            if _mg_native is None:
                _sync_rust_edge_attrs(G, edge_only=True)
                _mg_native = _native_adjacency_arrays_multigraph_checked(
                    G, nodelist, weight, 1.0
                )
    if _mg_native is not None:
        import numpy as _np
        rows, cols, data = _mg_native
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
            if dtype is not None:
                rows = _np.asarray(rows, dtype=_np.intp)
                cols = _np.asarray(cols, dtype=_np.intp)
                data = _np.asarray(data, dtype=dtype)
            matrix = scipy.sparse.coo_array(
                (data, (rows, cols)),
                shape=(len(nodelist), len(nodelist)),
                dtype=dtype,
            )
        return _sparse_asformat(matrix, format)

    # br-r37-c1-tssaperf: Python fallback path — multigraph (which
    # needs parallel-edge sum dedup), non-string weight key, or
    # non-fnx graph input (subclass).  Iterate G._adj.items()
    # directly instead of G.edges(data=True) — yields (u, {v: attrs})
    # without per-edge tuple alloc across PyO3.
    index = {node: i for i, node in enumerate(nodelist)}
    rows = []
    cols = []
    data = []
    if G.is_multigraph():
        accum = {}
        for u, v, _, edge_attrs in G.edges(keys=True, data=True):
            ui = index.get(u)
            vi = index.get(v)
            if ui is None or vi is None:
                continue
            edge_value = 1 if weight_is_none else edge_attrs.get(weight, 1)
            accum[(ui, vi)] = accum.get((ui, vi), 0) + edge_value
            if not is_directed and u != v:
                accum[(vi, ui)] = accum.get((vi, ui), 0) + edge_value
        for (ui, vi), val in accum.items():
            rows.append(ui)
            cols.append(vi)
            data.append(val)
    else:
        # For undirected graphs, every edge appears twice in _adj
        # (once from each endpoint), so the natural iteration already
        # emits both (u, v) and (v, u) without an explicit symmetric
        # write.  Just emit one entry per visit.
        for u, nbrs in G._adj.items():
            ui = index.get(u)
            if ui is None:
                continue
            for v, edge_attrs in nbrs.items():
                vi = index.get(v)
                if vi is None:
                    continue
                edge_value = 1 if weight_is_none else edge_attrs.get(weight, 1)
                rows.append(ui)
                cols.append(vi)
                data.append(edge_value)

    matrix = scipy.sparse.coo_array(
        (data, (rows, cols)),
        shape=(len(nodelist), len(nodelist)),
        dtype=dtype,
    )
    return _sparse_asformat(matrix, format)


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
    kind_to_python_type = {
        "f": float,
        "i": int,
        "u": int,
        "b": bool,
        "c": complex,
    }
    graph = _empty_graph_from_create_using(create_using)
    n, m = A.shape
    if n != m:
        raise NetworkXError(f"Adjacency matrix not square: nx,ny={A.shape}")

    coo = A.tocoo()
    python_type = kind_to_python_type.get(A.dtype.kind)
    if (
        type(graph) in (Graph, DiGraph)
        and isinstance(edge_attribute, str)
        and not edge_attribute.startswith("__fnx_incompatible")
        and A.dtype.kind in ("f", "i", "u", "b")
    ):
        if graph._native_fill_weighted_int_edges(
            n, coo.row.tolist(), coo.col.tolist(), coo.data.tolist(), edge_attribute
        ):
            return graph

    graph.add_nodes_from(range(n))
    triples = (
        (
            int(u),
            int(v),
            python_type(weight) if python_type is not None else weight,
        )
        for u, v, weight in zip(coo.row, coo.col, coo.data)
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
    elif type(graph) is Graph:
        # br-r37-c1-nlanb: batch the whole edge set through add_edges_from
        # (nx does exactly this with a generator of (u, v, data) triples) so
        # the attributed batch path (br-r37-c1-pr8q6) commits it in one bulk
        # insertion instead of per-edge Python add_edge + two adjacency-view
        # __getitem__ + dict.update (~7.8x nx). Semantics are identical for
        # well-formed input; for a NON-dict attrs value this also corrects a
        # divergence: the old loop added the edge BEFORE update() raised,
        # while nx's add_edges_from leaves nodes-but-no-edge (datadict is
        # only linked into _adj after a successful update).
        #
        # br-r37-c1-dodsymdedup: an UNDIRECTED dict-of-dicts lists every edge
        # twice (u->v and v->u). nx feeds both to add_edges_from (the reverse is
        # a redundant no-op update). Skip the reverse when it is the SAME attrs
        # object (the symmetric case produced by to_dict_of_dicts), halving the
        # batch. An asymmetric reverse (different dict) is still emitted so the
        # later one wins exactly as nx's add_edges_from does — byte-identical
        # result, ~2x less batch work. (The existing-nodes attr index batch,
        # br-r37-c1-dodattrbatch, only fires when node labels equal their indices;
        # a graph from to_dict_of_dicts of a non-0..n-ordered source falls back to
        # the String-keyed batch, where halving the work still helps.)
        seen = set()
        batch = []
        for u, nbrs in d.items():
            for v, edge_attrs in nbrs.items():
                if (
                    u != v
                    and (v, u) in seen
                    and v in d
                    and d[v].get(u) is edge_attrs
                ):
                    continue
                batch.append((u, v, edge_attrs))
                seen.add((u, v))
        graph.add_edges_from(batch)
    elif type(graph) is DiGraph:
        # br-r37-c1-doddir (cc): the directed simple-graph case had NO batch
        # branch and fell to the per-edge ``add_edge`` + ``graph[u][v].update``
        # loop below. That per-edge adjacency-view __getitem__ is O(N), making
        # the whole build O(N^2) — 963ms @ n=800 (0.003x vs nx, ~430x slower).
        # Directed dict-of-dicts edges are UNIQUE (no symmetric (v,u) dedup like
        # the undirected branch), so emit (u, v, attrs) triples through ONE
        # add_edges_from — byte-identical (nx does exactly this) and O(E).
        graph.add_edges_from(
            (u, v, edge_attrs)
            for u, nbrs in d.items()
            for v, edge_attrs in nbrs.items()
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
