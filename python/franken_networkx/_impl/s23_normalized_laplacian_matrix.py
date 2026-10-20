

def normalized_laplacian_matrix(G, nodelist=None, weight="weight"):
    """Return the normalized Laplacian matrix of *G*.

    ``L_norm = D^{-1/2} L D^{-1/2}`` where L is the Laplacian.

    Returns
    -------
    scipy.sparse array
    """
    import numpy as np
    import scipy.sparse

    if (
        _native_adjacency_index_arrays is not None
        and isinstance(G, (Graph, DiGraph))
        and not G.is_multigraph()
        and weight is None
    ):
        # br-r37-c1-04z53.12: for unit/default-absent weights, build
        # D^{-1/2}(D-A)D^{-1/2} directly from native COO indices. This preserves
        # the to_scipy_sparse_array validation/error contract before bypassing
        # its generic sparse diagonal/matmul route.
        if len(G) == 0:
            raise NetworkXError("Graph has no nodes or edges")
        if nodelist is None:
            native_nodelist = list(G)
        else:
            native_nodelist = list(nodelist)
            if len(native_nodelist) == 0:
                raise NetworkXError("nodelist has no nodes")
            if len(set(native_nodelist)) != len(native_nodelist):
                raise NetworkXError("nodelist contains duplicates.")
            missing = set(native_nodelist) - set(G)
            if missing:
                # br-r37-c1-6cdtz: nx reports the FIRST missing node in nodelist
                # order, singular & str-formatted, not a set of all missing.
                first_missing = next(n for n in native_nodelist if n not in G)
                raise NetworkXError(
                    f"Node {first_missing} in nodelist is not in G"
                )
        absent_weight_attr = weight if isinstance(weight, str) else None
        if (
            nodelist is None
            and type(G) is Graph
            and _native_adjacency_default_order_index_arrays is not None
        ):
            native_index_result = _native_adjacency_default_order_index_arrays(
                G, absent_weight_attr
            )
        else:
            native_index_result = _native_adjacency_index_arrays(
                G,
                native_nodelist,
                absent_weight_attr,
            )
        if native_index_result is not None:
            rows, cols = native_index_result
            n = len(native_nodelist)
            rows = np.asarray(rows, dtype=np.intp)
            cols = np.asarray(cols, dtype=np.intp)
            degree = np.bincount(rows, minlength=n).astype(float)
            self_loop_rows = rows[rows == cols]
            if len(self_loop_rows) == 0:
                self_loop_counts = np.zeros(n, dtype=float)
            else:
                self_loop_counts = np.bincount(self_loop_rows, minlength=n).astype(float)
            scale = np.zeros(n, dtype=float)
            positive_degree = degree > 0
            scale[positive_degree] = 1.0 / np.sqrt(degree[positive_degree])
            off_diagonal = rows != cols
            edge_rows = rows[off_diagonal]
            edge_cols = cols[off_diagonal]
            edge_data = scale[edge_rows] * (-1.0 * scale[edge_cols])
            diag_laplacian = degree - self_loop_counts
            diag = np.flatnonzero(diag_laplacian != 0.0).astype(np.intp)
            diag_data = scale[diag] * (diag_laplacian[diag] * scale[diag])
            return scipy.sparse.coo_array(
                (
                    np.concatenate((diag_data, edge_data)),
                    (
                        np.concatenate((diag, edge_rows)),
                        np.concatenate((diag, edge_cols)),
                    ),
                ),
                shape=(n, n),
            ).tocsr()

    A = to_scipy_sparse_array(G, nodelist=nodelist, weight=weight)
    n = A.shape[0]
    diags = np.asarray(A.sum(axis=1)).flatten().astype(float)
    # br-r37-c1-mxe39: compute N = D^{-1/2} (D - A) D^{-1/2} exactly like nx,
    # NOT I - D^{-1/2} A D^{-1/2}. The two agree for every node with degree > 0,
    # but for an isolated (degree-0) node the D^{-1/2} D D^{-1/2} term is 0
    # (1/sqrt(0) is clamped to 0), so nx's diagonal there is 0 — whereas the
    # constant-identity form leaves a spurious 1. This matters for any graph
    # with an isolated node (e.g. disconnected graphs, where a k-component
    # graph must yield k zero eigenvalues in the spectrum).
    D = scipy.sparse.diags_array(diags)
    L = D - A
    with np.errstate(divide="ignore"):
        diags_sqrt = 1.0 / np.sqrt(diags)
    diags_sqrt[np.isinf(diags_sqrt)] = 0
    D_inv_sqrt = scipy.sparse.diags_array(diags_sqrt)
    return (D_inv_sqrt @ (L @ D_inv_sqrt)).tocsr()


def laplacian_spectrum(G, weight="weight"):
    """Return the eigenvalues of the Laplacian matrix of *G*, sorted.

    Returns
    -------
    numpy.ndarray
    """
    import numpy as np

    complete_values = _complete_laplacian_spectrum_sorted_value_safe(G, weight)
    if complete_values is not None:
        return complete_values

    star_values = _star_laplacian_spectrum_sorted_value_safe(G, weight)
    if star_values is not None:
        return star_values

    if (
        type(G) is Graph
        and (weight is None or isinstance(weight, str))
        and 0 < len(G) <= _LAPLACIAN_SPECTRUM_NATIVE_MAX_N
    ):
        native = getattr(_fnx, "unweighted_laplacian_spectrum_rust", None)
        if native is not None:
            values = native(G, weight, _LAPLACIAN_SPECTRUM_NATIVE_MAX_N)
            if values is not None:
                return np.asarray(values, dtype=np.float64)

    L = laplacian_matrix(G, weight=weight)
    # networkx's scipy.linalg.eigvalsh checks finiteness first: a nan or inf
    # weight raises its ValueError, not LAPACK's non-convergence
    # LinAlgError (br-r37-c1-63v34).
    dense = np.asarray_chkfinite(L.toarray())
    n = dense.shape[0]
    # br-r37-c1-04z53.9109: small dense symmetric Laplacians use the safe-Rust
    # eigensolver after exact matrix construction.
    # br-r37-c1 (cc, laplacian-spectrum-eigsolver): the safe-Rust eigensolver is
    # 2.3-4x SLOWER than LAPACK eigvalsh at EVERY measured n>=30 (profiled
    # crossover) — it has no win on the general dense path, only added cost (it
    # made laplacian_spectrum 2.4x slower than networkx at n=300). Gate it to
    # small n where the absolute cost is negligible; route larger Laplacians to
    # LAPACK eigvalsh (values match to 1e-8, and it is already the fallback, so
    # the tolerance-based spectral tests are unaffected).
    if n <= _LAPLACIAN_DENSE_EIGSOLVER_NATIVE_MAX_N:
        native = getattr(_fnx, "symmetric_eigvals_rust", None)
        if native is not None:
            values = native(np.ascontiguousarray(dense, dtype=np.float64).ravel(), n)
            if values is not None:
                return np.asarray(values, dtype=np.float64)
    return np.sort(np.linalg.eigvalsh(dense))


# br-r37-c1-04z53.9109: direct unweighted Laplacian construction plus the
# safe-Rust eigensolver wins on small exact Graph inputs by avoiding SciPy sparse
# materialization and C LAPACK dispatch. Weighted, directed, multigraph,
# subclass, and larger cases continue through the exact matrix builder before
# the native dense eigensolver.
_LAPLACIAN_SPECTRUM_NATIVE_MAX_N = 32
_LAPLACIAN_DENSE_EIGSOLVER_NATIVE_MAX_N = 64


def _complete_laplacian_spectrum_sorted_value_safe(G, weight):
    if type(G) is not Graph or not (weight is None or isinstance(weight, str)):
        return None
    n = len(G)
    if n == 0:
        return None
    native = getattr(G, "_native_is_complete_unweighted_graph", None)
    if native is not None:
        if not native(weight):
            return None
    else:
        if G.number_of_edges() != n * (n - 1) // 2:
            return None
        for _, degree in G.degree():
            if degree != n - 1:
                return None
        if isinstance(weight, str):
            for _, _, attrs in G.edges(data=True):
                if weight in attrs:
                    return None

    import numpy as np

    values = np.empty(n, dtype=np.float64)
    values[0] = 0.0
    if n > 1:
        values[1:] = float(n)
    return values


def _star_laplacian_spectrum_sorted_value_safe(G, weight):
    if type(G) is not Graph or not (weight is None or isinstance(weight, str)):
        return None
    n = len(G)
    certified_n = _star_shape_certificate_size(G, weight)
    if certified_n is not None:
        n = certified_n
    elif n < 2 or G.number_of_edges() != n - 1:
        return None
    elif isinstance(weight, str):
        for _, _, attrs in G.edges(data=True):
            if weight in attrs:
                return None

    if certified_n is None:
        if n == 2:
            for _, degree in G.degree():
                if degree != 1:
                    return None
        else:
            center_count = 0
            leaf_count = 0
            for _, degree in G.degree():
                if degree == n - 1:
                    center_count += 1
                elif degree == 1:
                    leaf_count += 1
                else:
                    return None
            if center_count != 1 or leaf_count != n - 1:
                return None

    import numpy as np

    values = np.ones(n, dtype=np.float64)
    values[0] = 0.0
    values[-1] = float(n)
    return values


def _star_shape_certificate_size(G, weight):
    certificate = vars(G).get("_fnx_star_shape")
    if certificate is None:
        return None
    try:
        nodes_seq, edges_seq, n = certificate
    except (TypeError, ValueError):
        return None
    try:
        if G.nodes_seq != nodes_seq or G.edges_seq != edges_seq:
            return None
    except AttributeError:
        return None
    if n < 2 or G.number_of_edges() != n - 1:
        return None
    if weight is None:
        return n
    if not isinstance(weight, str) or _native_dijkstra_weight_cache_token is None:
        return None
    try:
        token = _native_dijkstra_weight_cache_token(G)
    except Exception:
        return None
    if token is None:
        return None
    token_nodes_seq, token_edges_seq, edge_attrs_dirty, _attr_rewrites = token
    # br-r37-c1-starcertattr (cc): the clean-token (not edge_attrs_dirty) path
    # certified the star as UNWEIGHTED, but edges_dirty is cleared by a sync while
    # the weights remain in the native store -- so a *synced weighted* star (e.g.
    # after one laplacian_spectrum call, which syncs) was wrongly certified
    # unweighted, making a SECOND laplacian_spectrum return the unweighted spectrum
    # (USER-FACING: call1 correct, call2 wrong). edges_dirty alone cannot witness
    # "no weights". Require the O(1) native graph_has_any_attrs to be False: only an
    # attr-free star is genuinely unweighted. Attr-bearing stars fall through to the
    # explicit per-edge weight check in _star_laplacian_spectrum_sorted_value_safe.
    try:
        _has_attrs = _fnx.graph_has_any_attrs(G)
    except Exception:
        _has_attrs = True
    if (
        token_nodes_seq == nodes_seq
        and token_edges_seq == edges_seq
        and not edge_attrs_dirty
        and _has_attrs is False
    ):
        return n
    return None


def _star_adjacency_spectrum_raw_order_safe(G, weight):
    if type(G) is not Graph or not (weight is None or isinstance(weight, str)):
        return None
    n = len(G)
    if n < 2 or G.number_of_edges() != n - 1:
        return None
    if isinstance(weight, str):
        for _, _, attrs in G.edges(data=True):
            if weight in attrs:
                return None
    degrees = list(G.degree())
    if n == 2:
        if degrees[0][1] != 1 or degrees[1][1] != 1:
            return None
        import numpy as np

        return np.asarray([1.0, -1.0], dtype=np.float64).astype(np.complex128)
    if degrees[0][1] != n - 1:
        return None
    for _, degree in degrees[1:]:
        if degree != 1:
            return None

    import numpy as np

    values = np.zeros(n, dtype=np.complex128)
    root = float(n - 1) ** 0.5
    values[0] = complex(root, 0.0)
    values[1] = complex(-root, 0.0)
    return values


def _complete_adjacency_spectrum_sorted_value_safe(G, weight):
    if type(G) is not Graph or not (weight is None or isinstance(weight, str)):
        return None
    n = len(G)
    if n == 0:
        return None
    native = getattr(G, "_native_is_complete_unweighted_graph", None)
    if native is not None:
        if not native(weight):
            return None
    else:
        if G.number_of_edges() != n * (n - 1) // 2:
            return None
        for _, degree in G.degree():
            if degree != n - 1:
                return None
        if isinstance(weight, str):
            for _, _, attrs in G.edges(data=True):
                if weight in attrs:
                    return None

    import numpy as np

    values = np.empty(n, dtype=np.complex128)
    if n == 1:
        values[0] = complex(0.0, 0.0)
    else:
        values[:-1] = complex(-1.0, 0.0)
        values[-1] = complex(float(n - 1), 0.0)
    return values


def _edgeless_adjacency_spectrum_sorted_value_safe(G, weight):
    if type(G) is not Graph or not (weight is None or isinstance(weight, str)):
        return None
    n = len(G)
    if n == 0 or G.number_of_edges() != 0:
        return None

    import numpy as np

    return np.zeros(n, dtype=np.complex128)


def _cycle_adjacency_spectrum_sorted_value_safe(G, weight):
    if type(G) is not Graph or not (weight is None or isinstance(weight, str)):
        return None
    n = len(G)
    if n < 3 or G.number_of_edges() != n:
        return None
    if isinstance(weight, str):
        for _, _, attrs in G.edges(data=True):
            if weight in attrs:
                return None

    degrees = list(G.degree())
    for _, degree in degrees:
        if degree != 2:
            return None

    start = degrees[0][0]
    seen = {start}
    stack = [start]
    while stack:
        node = stack.pop()
        for neighbor in G.neighbors(node):
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    if len(seen) != n:
        return None

    import numpy as np

    k = np.arange(n, dtype=np.float64)
    values = 2.0 * np.cos((2.0 * np.pi / float(n)) * k)
    return np.sort(values).astype(np.complex128)


def _complete_bipartite_adjacency_spectrum_sorted_value_safe(G, weight):
    if type(G) is not Graph or not (weight is None or isinstance(weight, str)):
        return None
    n = len(G)
    parts = _complete_bipartite_shape_certificate_parts(G, weight)
    if parts is None:
        native = getattr(G, "_native_complete_bipartite_unweighted_parts", None)
        if native is not None:
            parts = native(weight)
    if parts is None:
        edge_count = G.number_of_edges()
        if n < 2 or edge_count == 0:
            return None
        if isinstance(weight, str):
            for _, _, attrs in G.edges(data=True):
                if weight in attrs:
                    return None

        degrees = list(G.degree())
        start = degrees[0][0]
        colors = {start: 0}
        stack = [start]
        while stack:
            node = stack.pop()
            next_color = 1 - colors[node]
            for neighbor in G.neighbors(node):
                color = colors.get(neighbor)
                if color is None:
                    colors[neighbor] = next_color
                    stack.append(neighbor)
                elif color != next_color:
                    return None
        if len(colors) != n:
            return None

        left_size = 0
        for color in colors.values():
            if color == 0:
                left_size += 1
        right_size = n - left_size
        if left_size == 0 or right_size == 0 or edge_count != left_size * right_size:
            return None

        for node, degree in degrees:
            expected = right_size if colors[node] == 0 else left_size
            if degree != expected:
                return None
    else:
        left_size, right_size = parts

    import numpy as np

    values = np.zeros(n, dtype=np.complex128)
    root = float(left_size * right_size) ** 0.5
    values[0] = complex(-root, 0.0)
    values[-1] = complex(root, 0.0)
    return values


def _path_adjacency_spectrum_sorted_value_safe(G, weight):
    if type(G) is not Graph or not (weight is None or isinstance(weight, str)):
        return None
    n = len(G)
    if n == 0:
        return None
    if G.number_of_edges() != n - 1:
        return None
    if isinstance(weight, str):
        for _, _, attrs in G.edges(data=True):
            if weight in attrs:
                return None

    import numpy as np

    if n == 1:
        return np.asarray([0.0], dtype=np.float64).astype(np.complex128)

    degrees = list(G.degree())
    leaves = []
    for node, degree in degrees:
        if degree == 1:
            leaves.append(node)
        elif degree != 2:
            return None
    if len(leaves) != 2:
        return None

    seen = {leaves[0]}
    stack = [leaves[0]]
    while stack:
        node = stack.pop()
        for neighbor in G.neighbors(node):
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    if len(seen) != n:
        return None

    k = np.arange(n, 0, -1, dtype=np.float64)
    values = 2.0 * np.cos(k * np.pi / float(n + 1))
    return values.astype(np.complex128)


def adjacency_spectrum(G, weight="weight"):
    """Return the eigenvalues of the adjacency matrix of *G*.

    Returns
    -------
    numpy.ndarray
        Complex eigenvalues, dtype ``complex128``.  Solver order is
        unstable (LAPACK/QR Schur deflation order is not portable), so
        the contract is dtype + sorted-value parity with
        ``networkx.adjacency_spectrum`` (``scipy.linalg.eigvals``).

    br-r37-c1-aspec-cmplx: previously used ``np.linalg.eigvalsh``
    + ``np.sort`` which returned ``float64`` and pre-sorted.  nx
    uses the general (non-Hermitian) ``scipy.linalg.eigvals`` so
    its dtype is ``complex128``.  Match the dtype — the real-coercion
    to ``float64`` broke parity for callers using ``.dtype``.
    """
    import numpy as np

    edgeless_values = _edgeless_adjacency_spectrum_sorted_value_safe(G, weight)
    if edgeless_values is not None:
        return edgeless_values

    cycle_values = _cycle_adjacency_spectrum_sorted_value_safe(G, weight)
    if cycle_values is not None:
        return cycle_values

    # Exact unweighted stars have spectrum {+sqrt(n-1), -sqrt(n-1), 0...}.
    # Bypass dense matrix construction and the generic symmetric eigensolver
    # while preserving the public dtype + sorted-value contract.
    star_values = _star_adjacency_spectrum_raw_order_safe(G, weight)
    if star_values is not None:
        return star_values

    complete_bipartite_values = _complete_bipartite_adjacency_spectrum_sorted_value_safe(
        G, weight
    )
    if complete_bipartite_values is not None:
        return complete_bipartite_values

    complete_values = _complete_adjacency_spectrum_sorted_value_safe(G, weight)
    if complete_values is not None:
        return complete_values

    path_values = _path_adjacency_spectrum_sorted_value_safe(G, weight)
    if path_values is not None:
        return path_values

    # br-r37-c1-04z53.9112 (orchestrator-ruled sorted-value contract):
    # undirected adjacency is symmetric, so its eigenvalues are real.
    # nx/scipy.linalg.eigvals runs the GENERAL (non-Hermitian) dgeev path
    # which ignores symmetry and is ~10-16x slower than a symmetric
    # tridiagonal QL. Route undirected Graph through the safe-Rust
    # symmetric eigensolver (no C LAPACK), presented as complex128 to
    # match nx's dtype. Raw LAPACK Schur order is unreproducible in safe
    # Rust and irrelevant (eigenvalues-only, no eigenvector pairing); the
    # contract is dtype + sorted-value parity (test sorts both sides).
    if (
        type(G) is Graph
        and (weight is None or isinstance(weight, str))
        and len(G) > 0
    ):
        native = getattr(_fnx, "symmetric_eigvals_rust", None)
        if native is not None:
            dense = np.ascontiguousarray(
                np.asarray(adjacency_matrix(G, weight=weight).todense()),
                dtype=np.float64,
            )
            # nan/inf edge weights make scipy.linalg.eigvals raise ValueError;
            # fall through to SciPy so the native route preserves that contract.
            if np.isfinite(dense).all():
                # br-r37-c1 (cc, dense-eigsolver-gate): safe-Rust eig is 2.3-4x
                # slower than LAPACK eigvalsh at every n (same ascending order +
                # values to 1e-7), so gate it to small n and route larger dense
                # symmetric spectra to eigvalsh.
                an = dense.shape[0]
                if an <= _LAPLACIAN_DENSE_EIGSOLVER_NATIVE_MAX_N:
                    values = native(dense.ravel(), an)
                    if values is not None:
                        return np.asarray(values, dtype=np.float64).astype(np.complex128)
                else:
                    return np.linalg.eigvalsh(dense).astype(np.complex128)

    import scipy as sp

    # br-r37-c1-tssa-empty: route through adjacency_matrix so the
    # nx-matching `Graph has no nodes or edges` raise on empty G is
    # visible here too (the previous to_numpy_array path silently
    # returned an empty 0-d array).
    return sp.linalg.eigvals(adjacency_matrix(G, weight=weight).todense())


_FIEDLER_METHODS = frozenset(
    ("tracemin", "tracemin_pcg", "tracemin_lu", "lanczos", "lobpcg")
)


def _validate_fiedler_method(method):
    if method not in _FIEDLER_METHODS:
        raise NetworkXError(f"unknown method {method!r}.")


def algebraic_connectivity(G, weight="weight", normalized=False, tol=1e-8, method="tracemin_pcg", seed=None):
    """Return the algebraic connectivity of *G*.

    The algebraic connectivity is the second-smallest eigenvalue of the
    Laplacian matrix (Fiedler value).

    br-algconnkwargs: accept ``tol``, ``method``, ``seed`` kwargs for
    nx signature parity. fnx's bespoke implementation uses a direct
    eigenvalue solver (``np.linalg.eigvalsh`` on the dense
    Laplacian), so these iterative-solver knobs are accepted for
    API parity but don't alter the numerics. A native iterative
    port is future work.

    Parameters
    ----------
    G : Graph
        Must be connected.
    weight : str or None, optional
    normalized : bool, optional
        Use normalized Laplacian if True.
    tol, method, seed : accepted for nx parity; unused here.

    Returns
    -------
    float
    """
    import numpy as np

    # br-r37-c1-cdf1v: the dense solver draws nothing, but networkx's
    # @np_random_state(5) rejects a seed numpy cannot take (a random.Random, a
    # float, an int outside [0, 2**32)) - first: networkx's flattened argmap
    # resolves the seed before @not_implemented_for's directed check.
    _numpy_random_state(seed)
    del seed
    # br-r37-c1-d8qdy: nx is @not_implemented_for('directed') — fnx
    # would otherwise compute a meaningless Fiedler value on the
    # directed Laplacian. Add the type guard up front so drop-in
    # code that does ``except NetworkXNotImplemented`` triggers.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    # br-r37-c1-pb97z: nx raises NetworkXError on null/single-node
    # graphs; fnx silently returned 0.0. Match the documented contract.
    if len(G) < 2:
        raise NetworkXError("graph has less than two nodes.")

    if not is_connected(G):
        return 0.0

    if len(G) > 2:
        _validate_fiedler_method(method)
    del tol, method  # accepted for nx parity but not used here

    # br-algconnsparse: the old solver formed the DENSE Laplacian and ran
    # np.linalg.eigvalsh (O(n^3)) — ~7x slower than nx (1.85s vs 0.26s on a
    # 400-node sparse graph), which uses a sparse iterative solver. Match nx's
    # algorithm CLASS: build the sparse Laplacian and pull the few smallest
    # eigenvalues with shift-invert ARPACK (sigma=0 targets the eigenvalues
    # nearest 0). For a connected graph the smallest is 0 and the second is the
    # algebraic connectivity. k=4 (not 2) and a "smallest ~= 0, all finite"
    # sanity check guard against a missed/degenerate eigenvalue; any failure or
    # tiny graph falls back to the exact dense eigvalsh, so correctness is never
    # at risk. 1.85s -> ~13ms (faster than nx); value matches nx within 1e-7.
    L = (
        normalized_laplacian_matrix(G, weight=weight)
        if normalized
        else laplacian_matrix(G, weight=weight)
    )
    n = L.shape[0]
    # Shift-invert ARPACK is a large, reliable win on SPARSE Laplacians but can
    # converge slowly (or hang) on denser ones, where the dense O(n^3) solver is
    # comparable to nx anyway. Gate on sparsity (avg degree < ~16) and bound the
    # ARPACK iterations so any non-convergence raises into the dense fallback
    # rather than spinning.
    nnz = L.nnz if hasattr(L, "nnz") else None
    if n >= 12 and nnz is not None and nnz < 16 * n:
        try:
            import scipy.sparse as _sp
            import scipy.sparse.linalg as _sla

            Lc = _sp.csc_matrix(L, dtype=float)
            k = min(4, n - 2)
            vals = np.sort(
                _sla.eigsh(
                    Lc,
                    k=k,
                    sigma=0,
                    which="LM",
                    return_eigenvectors=False,
                    maxiter=200,
                )
            )
            if abs(vals[0]) < 1e-6 and np.all(np.isfinite(vals)):
                return float(vals[1])
        except Exception:
            pass
    spectrum = np.sort(np.linalg.eigvalsh(L.toarray()))
    if len(spectrum) < 2:
        return 0.0
    return float(spectrum[1])


def _fiedler_vector_impl(
    G,
    weight="weight",
    normalized=False,
    tol=1e-08,
    method="tracemin_pcg",
    seed=None,
    *,
    _use_dense_native=True,
):
    """Return the Fiedler vector of *G*.

    The Fiedler vector is the eigenvector corresponding to the
    algebraic connectivity (second-smallest Laplacian eigenvalue).

    Parameters
    ----------
    G : Graph
    weight : str, optional
    normalized : bool, optional
    tol : float, optional
        Tolerance — accepted for nx parity; unused by the dense solver.
    method : str, optional
        Accepted for nx parity; the dense ``numpy.linalg.eigh`` solver
        ignores it.
    seed : int or Random, optional
        Accepted for nx parity; the dense solver is deterministic so
        ``seed`` has no effect.

    Returns
    -------
    numpy.ndarray
    """
    import numpy as np

    # br-r37-c1-cdf1v: networkx's @np_random_state(5) rejects a seed numpy
    # cannot take - before the directed check, as its flattened argmap
    # resolves the seed first; the dense solver itself draws nothing.
    _numpy_random_state(seed)
    del seed
    # br-r37-c1-96xkv: directed guard runs before any graph-shape
    # checks so the @not_implemented_for ordering matches nx (a
    # directed empty/single-node graph raises NetworkXNotImplemented
    # rather than NetworkXError "graph has less than two nodes").
    # MultiGraph is *not* rejected: nx's fiedler_vector accepts it.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    # br-r37-c1-s22qo: nx raises NetworkXError on disconnected graphs
    # ('graph is not connected.'); fnx's dense eigh solver silently
    # produced a numerically-meaningless eigenvector for the
    # second-smallest eigenvalue (which equals 0 for disconnected
    # inputs and yields a degenerate basis). Match nx's contract.
    # Sister functions algebraic_connectivity and spectral_ordering
    # already raise correctly — fiedler_vector was the outlier.
    if len(G) < 2:
        raise NetworkXError("graph has less than two nodes.")
    if not is_connected(G):
        raise NetworkXError("graph is not connected.")
    if len(G) == 2:
        # br-r37-c1-atjs9: networkx's answer for two nodes, unnormalized.
        return np.array([1.0, -1.0])
    _validate_fiedler_method(method)
    # br-r37-c1-atjs9: networkx's tracemin methods return the vector with its
    # FIRST component negative (every converged case of ~190 graphs, weighted
    # or not, normalized or not; when that component is ~0 the sign is its
    # random start's). lobpcg's sign follows its random start - left as the
    # solver gives it. The dense / Lanczos / ARPACK solvers below return
    # either sign, so ~46% of fnx's vectors (and spectral_bisection's two
    # sets) came out flipped against networkx's.
    orient_first_negative = method in ("tracemin_pcg", "tracemin_lu")

    def _oriented(vector):
        if orient_first_negative and vector[0] > 0:
            return -vector
        return vector

    del tol, method  # accepted for nx parity but not used by the dense solver

    # br-r37-c1-ucvfx: for medium dense, unweighted, simple native graphs the
    # old fallback spends essentially all time in dense np.linalg.eigh. A
    # native Lanczos/Ritz solve works in the Laplacian matvec subspace and
    # proves its residual before returning; any unsupported or ill-conditioned
    # case falls through to the established SciPy/dense paths below.
    native_node_count = len(G)
    native_edge_count = G.number_of_edges()
    if (
        _use_dense_native
        and not normalized
        and not G.is_multigraph()
        and 32 <= native_node_count <= 128
        and native_edge_count * 2 >= 16 * native_node_count
    ):
        try:
            unweighted = weight is None
            if not unweighted and isinstance(weight, str):
                unweighted = not any(
                    weight in attrs for _, _, attrs in G.edges(data=True)
                )
            if unweighted:
                native_vector = _fnx.fiedler_vector_unweighted_lanczos_rust(
                    G, 96, 1e-8
                )
                if native_vector is not None:
                    return _oriented(np.asarray(native_vector, dtype=float))
        except Exception:
            pass

    # br-fiedlersparse: same dense O(n^3) np.linalg.eigh tax as
    # algebraic_connectivity (~6.5x slower than nx, 1.56s @ watts(400,6)). For
    # a SPARSE graph with a SIMPLE second-smallest eigenvalue, get the Fiedler
    # eigenpair with shift-invert ARPACK (scipy eigsh, sigma=0) -- ~90x faster.
    # The Fiedler vector is sign-ambiguous (nx and the dense solver already
    # disagree on sign), so the sparse vector is canonicalized to a
    # largest-magnitude-component-positive sign; it then matches nx up to sign
    # for non-degenerate lambda2. A DEGENERATE eigenspace has no canonical basis
    # vector, so when lambda2 is not strictly separated from lambda3 -- and on
    # dense/tiny graphs or any failure -- fall back to the exact dense eigh,
    # byte-identical to the previous implementation.
    L_sparse = (
        normalized_laplacian_matrix(G, weight=weight)
        if normalized
        else laplacian_matrix(G, weight=weight)
    )
    n = L_sparse.shape[0]
    nnz = L_sparse.nnz if hasattr(L_sparse, "nnz") else None
    if n >= 12 and nnz is not None and nnz < 16 * n:
        try:
            import scipy.sparse as _sp
            import scipy.sparse.linalg as _sla

            Lc = _sp.csc_matrix(L_sparse, dtype=float)
            k = min(5, n - 2)
            vals, vecs = _sla.eigsh(
                Lc, k=k, sigma=0, which="LM", return_eigenvectors=True, maxiter=200
            )
            order = np.argsort(vals)
            vals = vals[order]
            vecs = vecs[:, order]
            if (
                abs(vals[0]) < 1e-6
                and np.all(np.isfinite(vals))
                and vals[2] - vals[1] > 1e-7 * max(1.0, abs(vals[2]))
            ):
                v = np.asarray(vecs[:, 1], dtype=float)
                j = int(np.argmax(np.abs(v)))
                return _oriented(-v if v[j] < 0 else v)
        except Exception:
            pass

    L = L_sparse.toarray() if hasattr(L_sparse, "toarray") else np.asarray(L_sparse)
    eigenvalues, eigenvectors = np.linalg.eigh(L)
    return _oriented(eigenvectors[:, 1])


def fiedler_vector(
    G,
    weight="weight",
    normalized=False,
    tol=1e-08,
    method="tracemin_pcg",
    seed=None,
):
    """Return the Fiedler vector of *G*."""
    return _fiedler_vector_impl(
        G, weight=weight, normalized=normalized, tol=tol, method=method, seed=seed
    )


# ---------------------------------------------------------------------------
# Additional matrix representations
# ---------------------------------------------------------------------------


def incidence_matrix(
    G, nodelist=None, edgelist=None, oriented=False, weight=None, *, dtype=None
):
    """Return the incidence matrix of *G* as a SciPy sparse array.

    Parameters
    ----------
    G : Graph
    nodelist : list, optional
    edgelist : list, optional
    oriented : bool, optional
        If True, use +1/-1 for edge endpoints. Default False (uses 1).
    weight : str or None, optional
    dtype : numpy dtype, optional
        The desired data-type for the array. Matches nx's keyword-only
        ``dtype`` argument.

    Returns
    -------
    scipy.sparse array
        Shape (n_nodes, n_edges).
    """
    import numpy as np
    import scipy.sparse

    if nodelist is None:
        nodelist = list(G.nodes())
    if edgelist is None:
        if G.is_multigraph():
            edgelist = list(G.edges(keys=True))
        else:
            edgelist = list(G.edges())

    node_index = {n: i for i, n in enumerate(nodelist)}
    n_nodes = len(nodelist)
    n_edges = len(edgelist)
    is_multi = G.is_multigraph()

    row, col, data = [], [], []
    for ei, e in enumerate(edgelist):
        u, v = e[:2]
        if u == v:
            continue  # self loops give zero column (match nx)
        try:
            ui = node_index[u]
            vi = node_index[v]
        except KeyError as err:
            raise NetworkXError(
                f"node {u} or {v} in edgelist but not in nodelist"
            ) from err
        if weight is None:
            wt = 1
        elif is_multi:
            wt = G[u][v][e[2]].get(weight, 1)
        else:
            wt = G[u][v].get(weight, 1)
        # oriented: u is tail (-wt), v is head (+wt); unoriented: +wt both
        row.append(ui)
        col.append(ei)
        data.append(-wt if oriented else wt)
        row.append(vi)
        col.append(ei)
        data.append(wt)

    arr_dtype = float if dtype is None else dtype
    return scipy.sparse.coo_array(
        (
            np.array(data, dtype=arr_dtype),
            (np.array(row, dtype=int), np.array(col, dtype=int)),
        ),
        shape=(n_nodes, n_edges),
    ).tocsc()


# ---------------------------------------------------------------------------
# Social network datasets (hardcoded classic graphs)
# ---------------------------------------------------------------------------


_KARATE_CLUB_MATRIX = """\
0 4 5 3 3 3 3 2 2 0 2 3 2 3 0 0 0 2 0 2 0 2 0 0 0 0 0 0 0 0 0 2 0 0
4 0 6 3 0 0 0 4 0 0 0 0 0 5 0 0 0 1 0 2 0 2 0 0 0 0 0 0 0 0 2 0 0 0
5 6 0 3 0 0 0 4 5 1 0 0 0 3 0 0 0 0 0 0 0 0 0 0 0 0 0 2 2 0 0 0 3 0
3 3 3 0 0 0 0 3 0 0 0 0 3 3 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
3 0 0 0 0 0 2 0 0 0 3 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
3 0 0 0 0 0 5 0 0 0 3 0 0 0 0 0 3 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
3 0 0 0 2 5 0 0 0 0 0 0 0 0 0 0 3 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
2 4 4 3 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
2 0 5 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 3 0 4 3
0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 2
2 0 0 0 3 3 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
3 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
1 0 0 3 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
3 5 3 3 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 3
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 3 2
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 3 4
0 0 0 0 0 3 3 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
2 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 2
2 2 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 3 1
2 2 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 2 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 5 0 4 0 2 0 0 5 4
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 2 0 3 0 0 0 2 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 5 2 0 0 0 0 0 0 7 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 4 0 0 0 2
0 0 2 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 4 3 0 0 0 0 0 0 0 0 4
0 0 2 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 2 0 2
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 3 0 0 4 0 0 0 0 0 3 2
0 2 0 0 0 0 0 0 3 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 3 3
2 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 2 7 0 0 2 0 0 0 4 4
0 0 2 0 0 0 0 0 3 0 0 0 0 0 3 3 0 0 1 0 3 0 2 5 0 0 0 0 0 4 3 4 0 5
0 0 0 0 0 0 0 0 4 2 0 0 0 3 2 4 0 0 2 1 1 0 3 4 0 0 2 4 2 2 3 4 5 0"""
_KARATE_CLUB1 = frozenset({0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 16, 17, 19, 21})


_KARATE_CLUB_EDGE_STREAM = None


def _karate_club_edge_stream():
    """The exact ``(row, col, weight)`` stream Zachary's matrix emits.

    br-r37-c1-p4qjj: parsed once and memoised, because the matrix is a
    compile-time constant and re-``int()``-ing all 1156 cells on every call
    was pure repeat work.

    BOTH triangles stay in the stream, in row-major order. Zachary's matrix
    is NOT symmetric: seven pairs disagree across the diagonal — (0,12),
    (2,32), (8,32), (8,33), (22,33), (23,29), (29,32) — and (22,33) is zero
    above the diagonal, so the edge exists only because row 33 emits (33,22).
    The duplicate lower-triangle entries are therefore load-bearing twice
    over: they are what makes the final weight last-write-wins, and they are
    what makes that one edge exist at all. An upper-triangle shortcut would
    silently drop one edge and mis-weight seven.
    """
    global _KARATE_CLUB_EDGE_STREAM
    stream = _KARATE_CLUB_EDGE_STREAM
    if stream is None:
        stream = tuple(
            (row, col, entry)
            for row, line in enumerate(_KARATE_CLUB_MATRIX.split("\n"))
            for col, entry in enumerate(int(b) for b in line.split())
            if entry >= 1
        )
        _KARATE_CLUB_EDGE_STREAM = stream
    return stream


def karate_club_graph():
    """Return Zachary's Karate Club graph (34 nodes, 78 edges).

    br-karateattrs: carries per-node ``club`` attribute ('Mr. Hi' /
    'Officer') and per-edge ``weight`` integers from Zachary's
    interaction matrix. Previous builder omitted both — weighted
    HITS diverged by ~1.6% and ``G.nodes[v]['club']`` crashed with
    KeyError. Inlining Zachary's matrix directly (no nx dispatch so
    the coverage classifier stays PY_WRAPPER).

    br-r37-c1-p4qjj: the per-cell ``add_edge`` accept loop paid 155 PyO3
    crossings plus 34 more for the node-attribute pass, which measured
    0.3762x vs live NetworkX. Replay the memoised stream through one batched
    ``add_edges_from`` and fold the ``club`` attribute into the single
    ``add_nodes_from`` instead. Observable output is unchanged: nodes still
    arrive 0..33 before any edge, and the edge stream is replayed in the
    identical row-major order with the identical last-write-wins duplicate
    semantics, so node order, edge order, weights and attributes are all
    byte-identical (locked by tests/python/test_karate_club_graph_parity.py).

    The attribute dicts are rebuilt per call rather than memoised alongside
    the stream: a shared dict would be a mutation channel between two graphs
    handed to two different callers.
    """
    G = Graph()
    G.add_nodes_from(
        (v, {"club": "Mr. Hi" if v in _KARATE_CLUB1 else "Officer"})
        for v in range(34)
    )
    G.add_edges_from(
        (row, col, {"weight": entry})
        for row, col, entry in _karate_club_edge_stream()
    )
    G.graph["name"] = "Zachary's Karate Club"
    return G




# ---------------------------------------------------------------------------
# Community graph generators
# ---------------------------------------------------------------------------


def caveman_graph(l, k):
    """Return a caveman graph of *l* cliques of size *k*.

    Parameters
    ----------
    l : int
        Number of cliques.
    k : int
        Size of each clique.

    Returns
    -------
    Graph

    br-r37-c1-cave-neg: nx raises ``NetworkXError("Negative number
    of nodes not valid: -X")`` when ``l*k`` is negative (i.e. either
    ``l`` or ``k`` is negative). Previously fnx silently returned
    an empty graph, breaking drop-in parity with nx's
    structural-error contract.
    """
    if isinstance(l, int) and isinstance(k, int):
        total = l * k
        if total < 0:
            raise NetworkXError(f"Negative number of nodes not valid: {total}")
        if type(l) is int and type(k) is int and l >= 0 and k >= 0:
            return _rust_caveman_graph(l, k)
    G = Graph()
    # Always materialise every node, even when a clique has size 1 and
    # thus contributes no edges. Previously the k=1 case collapsed to an
    # empty graph because the edge loop only added endpoints — nx adds
    # the `l` singletons.
    G.add_nodes_from(range(l * k))
    # br-r37-c1-caveman-bulk: the previous triple-nested loop added each clique
    # edge with a per-edge add_edge (~l*C(k,2) PyO3 calls = ~61k for caveman(50,50),
    # 4.4x slower than nx). Emit every clique's combinations through ONE bulk
    # add_edges_from on the fresh graph (hits the native batch path). Byte-exact:
    # clique 0 edges then clique 1 ... in combinations order — the identical
    # stream to nx's per-clique combinations(range(start,start+k),2), and edges()
    # is node-iteration-determined.
    if k > 1:
        G.add_edges_from(
            (start + u, start + v)
            for start in range(0, l * k, k)
            for u, v in _combinations(range(k), 2)
        )
    return G


def connected_caveman_graph(l, k):
    """Return a connected caveman graph.

    Like ``caveman_graph`` but with one edge rewired per clique to
    connect adjacent cliques in a ring. br-caveman: matches nx's
    ``G.remove_edge(start, start+1); G.add_edge(start, start-1 mod lk)``
    rewiring — previously only added the bridge without removing the
    within-clique edge, producing 3 extra edges per (l, k).
    """
    if k < 2:
        raise NetworkXError(
            "The size of cliques in a connected caveman graph must be at least 2."
        )

    G = caveman_graph(l, k)
    for start in range(0, l * k, k):
        G.remove_edge(start, start + 1)
        G.add_edge(start, (start - 1) % (l * k))
    return G


def _random_tree_internal(n, seed=None):
    """Internal Prüfer-sequence tree generator retained for backward
    compatibility — kept private after nx 3.4 removed the public
    ``nx.random_tree`` symbol (replaced by ``random_labeled_tree``).
    Use ``random_labeled_tree`` going forward.
    """
    if n <= 0:
        return Graph()
    if n == 1:
        G = Graph()
        G.add_node(0)
        return G
    if n == 2:
        G = Graph()
        G.add_edge(0, 1)
        return G

    # br-r37-c1-cdf1v: networkx's seed handling (a random.Random, numpy RNG or
    # None -> the global random module state are all accepted, as nx's
    # py_random_state does), and networkx's own draw, seed.choice(range(n)) -
    # its numpy-backed wrappers implement choice, not only randint.
    rng = _generator_random_state(seed)
    prufer = [rng.choice(range(n)) for _ in range(n - 2)]

    # br-r37-c1-prufer-on2: the previous decode scanned ``range(n)`` for the
    # smallest degree-1 node on every Prüfer element — O(n^2) (~4M iters at
    # n=2000, the whole 12.6x gap vs nx). Replace with networkx's exact O(n)
    # ``from_prufer_sequence`` decode: a forward-only ``index`` pointer means
    # the ``next(... range(index+1, n) ...)`` scans never revisit earlier nodes,
    # so the total work is O(n). Byte-identical to nx (same edge set, and edges
    # are emitted in node-iteration order since all nodes 0..n-1 are added up
    # front).
    degree = [1] * n
    for i in prufer:
        degree[i] += 1

    # Collect the decoded edges, then add them in one bulk ``add_edges_from``
    # (native batch path) rather than n-1 per-edge ``add_edge`` PyO3 calls —
    # the edge SET and emission order are unchanged (all nodes 0..n-1 are added
    # up front, so edges() is node-order-determined), so this stays byte-exact.
    tree_edges = []
    not_orphaned = set()
    index = u = next(k for k in range(n) if degree[k] == 1)
    for v in prufer:
        tree_edges.append((u, v))
        not_orphaned.add(u)
        degree[v] -= 1
        if v < index and degree[v] == 1:
            u = v
        else:
            index = u = next(k for k in range(index + 1, n) if degree[k] == 1)

    # Exactly two nodes remain un-parented; join them (matches nx).
    u, v = set(range(n)) - not_orphaned
    tree_edges.append((u, v))

    G = Graph()
    G.add_nodes_from(range(n))
    G.add_edges_from(tree_edges)

    return G


# ---------------------------------------------------------------------------
# Structural hole / brokerage metrics
# ---------------------------------------------------------------------------


def _structural_holes_constraint_matrix(G, weight):
    """br-r37-c1-qurfc: nx's ``constraint(nodes=None)`` MATRIX path, verbatim,
    over the native ``adjacency_matrix`` (byte-identical sparse to nx's)."""
    import numpy as _np

    G = _coerce_arg_to_fnx_graph(G)
    P = adjacency_matrix(G, weight=weight).astype(float)
    mutual_weights = P + P.T
    sum_mutual_weights = mutual_weights.sum(axis=1)
    with _np.errstate(divide="ignore", invalid="ignore"):
        mutual_weights /= sum_mutual_weights[:, _np.newaxis]
    local_constraints = (mutual_weights + mutual_weights @ mutual_weights) ** 2
    constraints = ((mutual_weights > 0) * local_constraints).sum(axis=1)
    isolated_nodes = sum_mutual_weights - 2 * mutual_weights.diagonal() == 0
    constraints = _np.asarray(constraints).flatten()
    constraints[_np.asarray(isolated_nodes).flatten()] = float("nan")
    return dict(zip(G, constraints.tolist()))


def _structural_holes_effective_size_matrix(G, weight):
    """br-r37-c1-qurfc: nx's ``effective_size(nodes=None)`` MATRIX path, verbatim,
    over the native ``adjacency_matrix``."""
    import numpy as _np

    G = _coerce_arg_to_fnx_graph(G)
    P = adjacency_matrix(G, weight=weight).astype(float)
    mutual_weights1 = P + P.T
    mutual_weights2 = mutual_weights1.copy()
    with _np.errstate(divide="ignore", invalid="ignore"):
        mutual_weights1 /= mutual_weights1.sum(axis=1)[:, _np.newaxis]
        mutual_weights2 /= mutual_weights2.max(axis=1).toarray()
    r = 1 - (mutual_weights1 @ mutual_weights2.T).toarray()
    effective_size = _np.asarray(((mutual_weights1 > 0) * r).sum(axis=1)).flatten()
    sum_mutual_weights = (
        _np.asarray(mutual_weights1.sum(axis=1)).flatten() - mutual_weights1.diagonal()
    )
    isolated_nodes = sum_mutual_weights == 0
    effective_size[_np.asarray(isolated_nodes).flatten()] = float("nan")
    return dict(zip(G, effective_size.tolist()))


def constraint(G, nodes=None, weight=None, *, backend=None, **backend_kwargs):
    """Return Burt's constraint for nodes in *G*."""
    _validate_backend_dispatch_keywords("constraint", backend, backend_kwargs)
    # br-r37-c1-shdir: the Rust constraint_rust kernel is undirected-only; on
    # DiGraphs it ignored edge direction and returned uniform values, whereas
    # nx uses the directed mutual-weight convention (neighbors = successors |
    # predecessors, mutual_weight = w(u->v) + w(v->u)). Delegate directed
    # graphs to nx, like the weighted path already does.
    # br-r37-c1-1boe3: the Rust kernel also effectively ignores self-loops,
    # but nx's matrix path folds a self-loop into the mutual-weight row-sum /
    # row-max normalization (while still excluding the node from its own
    # neighbor sum), so the two diverge whenever a non-isolated node carries a
    # self-loop. Delegate self-loop graphs to nx rather than re-deriving nx's
    # subtle matrix semantics in Rust.
    # br-r37-c1-14vcl: a multigraph too - constraint_rust reads it as a simple
    # graph, while networkx's matrix path sums parallel edges and its loop path
    # counts each edge once (see _mutual_weight).
    if (
        weight is not None
        or G.is_directed()
        or G.is_multigraph()
        or number_of_selfloops(G) > 0
    ):
        # br-r37-c1-qurfc: nx's constraint(nodes=None) uses a deterministic
        # MATRIX path (P + P.T row-normalized), not the set-order summation —
        # so it is byte-reproducible in-process over the native adjacency_matrix
        # (proven 0/320 exact across weighted/directed/self-loop), dropping the
        # per-call fnx->nx conversion (~4x). The set-order ULP wall only affects
        # the nodes!=None set path, which stays delegated.
        if nodes is None:
            return _structural_holes_constraint_matrix(G, weight)
        # br-r37-c1-qbj9u (constraint): networkx serves this function TWO ways and they
        # DISAGREE on directed graphs - `nodes is None and has_scipy` takes a sparse-matrix
        # path (P + P.T, row-normalised), anything else takes the set-order summation over
        # local_constraint. Measured, they differ on 19 of 40 random digraphs, specifically in
        # NaN PLACEMENT rather than values: a node with predecessors but NO successors gets a
        # number from the matrix path and NaN from the loop. (The sibling effective_size
        # differs in the VALUES themselves; do not carry that across.) So the branch above must
        # keep the matrix answer, and only THIS branch may use a kernel reproducing the LOOP.
        #
        # constraint_rust is undirected-only and does NOT reproduce the directed loop (548
        # mismatches in 807 node values), which is why this delegated wholesale at 0.964x
        # and 2.59e9 Ir/call. constraint_directed_rust does: validated against
        # nx.constraint(G, nodes=list(G)) over 150 random digraphs, 0 divergences.
        if (
            weight is None
            and G.is_directed()
            and not G.is_multigraph()
            and number_of_selfloops(G) == 0
        ):
            try:
                from franken_networkx._fnx import (
                    constraint_directed_rust as _rust_constraint_directed,
                )
            except ImportError:
                _rust_constraint_directed = None
            if _rust_constraint_directed is not None:
                requested_directed = list(nodes)
                for node in requested_directed:
                    if node not in G:
                        raise KeyError(node)
                raw_directed = _rust_constraint_directed(G)
                directed_constraint = {}
                for node in requested_directed:
                    # networkx marks a node NaN when `len(G[v]) == 0`, and G[v] on a
                    # DiGraph is SUCCESSORS ONLY - a node with predecessors but no
                    # successors is NaN. The kernel applies the same rule; this mirrors
                    # the sibling native paths, which also post-pass in Python.
                    directed_constraint[node] = raw_directed[node]
                return directed_constraint
        return _call_networkx_submodule_for_parity(
            "algorithms.structuralholes", "constraint", G,
            nodes=nodes, weight=weight,
        )

    from franken_networkx._fnx import constraint_rust as _rust_constraint

    if len(G) == 0:
        raise NetworkXError("Graph has no nodes or edges")

    if nodes is None:
        # br-r37-c1-vbjbk: when nodes is None and SciPy is available, NetworkX
        # always executes its sparse matrix path (even for unweighted simple
        # undirected graphs), whose CSR minor-axis reduction differs by 1 ULP
        # from the per-node scalar formulas in constraint_rust.
        try:
            import scipy as _scipy
        except ImportError:
            pass
        else:
            return _structural_holes_constraint_matrix(G, weight)
        requested_nodes = list(G)
    else:
        requested_nodes = list(nodes)
        for node in requested_nodes:
            if node not in G:
                raise KeyError(node)

    result = _rust_constraint(G)
    constrained = {}
    for node in requested_nodes:
        if all(neighbor == node for neighbor in G[node]):
            constrained[node] = float("nan")
        else:
            constrained[node] = result[node]
    return constrained


def effective_size(G, nodes=None, weight=None, *, backend=None, **backend_kwargs):
    """Return the effective size of each node's ego network.

    Effective size is the number of alters minus the average degree of
    alters within the ego network (not counting ties to ego).

    Parameters
    ----------
    G : Graph
    nodes : iterable, optional
    weight : str or None, optional

    Returns
    -------
    dict
        ``{node: effective_size}``
    """
    _validate_backend_dispatch_keywords("effective_size", backend, backend_kwargs)
    # br-r37-c1-qbj9u: simple unweighted DiGraphs now use a native kernel with
    # NetworkX's directed mutual-neighbor semantics (successors ∪ predecessors,
    # mutual weight I(u->v)+I(v->u)), removing the matrix/delegation path for
    # the realistic directed common case. Weighted, multigraph, and self-loop
    # graphs keep the existing matrix/parity route below.
    has_selfloops = number_of_selfloops(G) > 0
    # br-r37-c1-qbj9u REVERTED (cc, verify phase): the native
    # effective_size_directed_rust kernel diverged from networkx by ~0.2/node on
    # simple DiGraphs (e.g. fnx 2.6 vs nx 2.8) — caught by
    # test_effective_size_directed_conformance_guard.py (the scaffold filed with the
    # lever). Route directed graphs back through the nx-correct matrix/parity
    # fallback below until the kernel matches nx. CrimsonRiver flagged to fix the
    # kernel; the guard will validate re-enabling it.

    # br-r37-c1-shdir: see constraint — the Rust effective_size_rust kernel was
    # undirected-only and mishandled DiGraphs. Non-simple directed cases still
    # use the matrix/delegated parity path.
    # br-r37-c1-1boe3: the Rust kernel also ignores self-loops, but nx folds a
    # self-loop into the mutual-weight normalization, so delegate self-loop
    # graphs to nx (same reasoning as constraint).
    # br-r37-c1-14vcl: a multigraph too, as in constraint.
    if weight is not None or G.is_directed() or G.is_multigraph() or has_selfloops:
        # br-r37-c1-qurfc: nx's effective_size(nodes=None) uses a deterministic
        # MATRIX path, byte-reproducible in-process over the native
        # adjacency_matrix (proven 0/320 exact), dropping the fnx->nx conversion.
        # nodes!=None (set-order path) stays delegated.
        if nodes is None:
            # NetworkX only takes its sparse matrix path when SciPy imports
            # successfully.  The Python package does not require SciPy, so
            # keep its no-SciPy loop fallback instead of unconditionally
            # calling our SciPy-backed adjacency_matrix implementation.
            try:
                import scipy as _scipy
            except ImportError:
                return _call_networkx_submodule_for_parity(
                    "algorithms.structuralholes", "effective_size", G,
                    nodes=nodes, weight=weight,
                )
            return _structural_holes_effective_size_matrix(G, weight)
        # br-r37-c1-qbj9u: networkx serves this function TWO ways and they DISAGREE on
        # directed graphs. nodes=None takes a scipy MATRIX path; nodes=<iterable> takes
        # the redundancy LOOP in structuralholes.py. Measured, the two differ on 50 of 60
        # random digraphs (31 of them nan-vs-value) and on 0 of 60 undirected. So the
        # kernel that is correct here is NOT the one that is correct above, and the branch
        # above must keep the matrix path.
        #
        # The revert note further up is right that effective_size_directed_rust does not
        # reproduce nx's DEFAULT answer - but it reproduces nx's LOOP exactly, which is
        # what nx itself runs once `nodes` is given: 0 mismatches over 1494 node values
        # once the successors-only nan rule below is applied, and 0 divergences over 1500
        # (graph, subset) cases for this branch as a whole, including string node keys,
        # empty and reordered subsets, and the missing-node KeyError.
        #
        # Worth having because the delegated path is pathologically slow: networkx's loop
        # costs ~207 ms per call on a 200-node digraph where its own matrix path costs
        # 1.6 ms marginal, so asking for a SUBSET of nodes is ~130x dearer than asking for
        # all of them. fnx was paying that plus a conversion tax (0.964x vs networkx).
        if (
            weight is None
            and G.is_directed()
            and not G.is_multigraph()
            and not has_selfloops
        ):
            from franken_networkx._fnx import (
                effective_size_directed_rust as _rust_eff_size_directed,
            )

            requested_directed = list(nodes)
            for node in requested_directed:
                if node not in G:
                    raise KeyError(node)
            raw_directed = _rust_eff_size_directed(G)
            directed_effective = {}
            for node in requested_directed:
                # nx's isolated-node rule is `all(u == v for u in G[v])`, and G[v] on a
                # DiGraph is SUCCESSORS ONLY - so a node with predecessors but no
                # successors is nan. The kernel's own rule tests successors UNION
                # predecessors, which is what made it look wrong; applied here instead,
                # exactly as the undirected native path below already does.
                if all(neighbor == node for neighbor in G[node]):
                    directed_effective[node] = float("nan")
                else:
                    directed_effective[node] = raw_directed[node]
            return directed_effective
        return _call_networkx_submodule_for_parity(
            "algorithms.structuralholes", "effective_size", G,
            nodes=nodes, weight=weight,
        )

    if len(G) == 0:
        raise NetworkXError("Graph has no nodes or edges")

    if nodes is None:
        # br-r37-c1-vbjbk: match NetworkX's default SciPy matrix path bit-for-bit
        # when nodes is None and SciPy is available.
        try:
            import scipy as _scipy
        except ImportError:
            pass
        else:
            return _structural_holes_effective_size_matrix(G, weight)
        requested_nodes = list(G.nodes())
    else:
        requested_nodes = list(nodes)
        for node in requested_nodes:
            if node not in G:
                raise KeyError(node)

    from franken_networkx._fnx import effective_size_rust as _rust_eff_size

    result = _rust_eff_size(G)
    effective = {}
    for node in requested_nodes:
        if all(neighbor == node for neighbor in G[node]):
            effective[node] = float("nan")
        else:
            effective[node] = result[node]
    return effective
