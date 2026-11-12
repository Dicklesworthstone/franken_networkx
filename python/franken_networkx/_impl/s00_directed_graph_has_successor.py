"""FrankenNetworkX — A high-performance Rust-backed drop-in replacement for NetworkX.

Usage::

    import franken_networkx as fnx

    G = franken_networkx.Graph()
    G.add_edge("a", "b", weight=3.0)
    G.add_edge("b", "c", weight=1.5)
    path = fnx.shortest_path(G, "a", "c", weight="weight")

Or as a NetworkX backend (zero code changes required)::

    import networkx as nx
    nx.config.backend_priority = ["franken_networkx"]
    # Now all supported algorithms dispatch to Rust automatically.
"""

import base64 as _base64
from collections import (
    Counter as _Counter,
    defaultdict as _defaultdict,
    deque as _deque,
)
from collections.abc import (
    Collection as _Collection,
    Generator as _Generator,
    Iterable as _Iterable,
    Iterator as _Iterator,
    Mapping as _Mapping,
    MutableMapping as _MutableMapping,
    Set as _Set,
)
import bisect as _bisect
from copy import deepcopy as _deepcopy
from dataclasses import dataclass as _dataclass, field as _field
from enum import Enum as _Enum
from functools import cached_property as _cached_property, wraps as _wraps
import gc as _gc
import gzip as _gzip
from heapq import heappop as _heappop, heappush as _heappush
import io as _io
import itertools as _itertools
from itertools import combinations as _combinations, count as _count
import math as _math
import numbers as _numbers
import operator as _operator
import sys as _sys
import threading as _threading
import types as _types
import weakref as _weakref

# br-r37-c1-u5tyh: bound once, here, because the nbunch edge guard reads it from
# inside a per-edge loop's trigger branch and a module-attribute lookup there is
# the kind of thing that loop's history says to avoid.
_length_hint = _operator.length_hint

from franken_networkx import _fnx
from franken_networkx._fnx import __version__

# Core graph classes
from franken_networkx._fnx import Graph
from franken_networkx._fnx import DiGraph
from franken_networkx._fnx import MultiGraph
from franken_networkx._fnx import MultiDiGraph

# br-r37-c1-0epvo: nx 3.3+ uses ``__networkx_backend__`` on graph
# instances to route dispatcher-mutated functions (e.g.
# ``minimum_branching``, ``minimum_spanning_arborescence``) to the
# matching registered backend. Without this attribute nx's dispatcher
# refuses to auto-convert fnx graphs for "preserve+mutate" entry
# points and raises ``RuntimeError: ... was called with inputs from
# multiple backends: set()`` (because fnx.Graph is *not* a subclass of
# ``nx.Graph`` and therefore fails nx's `isinstance(g, nx.Graph)` check
# inside the fallback-to-orig branch).
#
# fnx is already registered as a backend via pyproject.toml
# ``[project.entry-points."networkx.backends"]`` so tagging the graph
# classes makes the dispatcher route fnx graphs back through the
# registered backend interface for any function fnx implements.
#
# For functions fnx does *not* implement (~all of nx beyond the ~300
# entries in ``franken_networkx.backend._SUPPORTED_ALGORITHMS``), the
# dispatcher would otherwise raise ``NotImplementedError`` because
# graph_backend_names would be ``{"franken_networkx"}`` with no fall-
# back path. Enabling ``nx.config.fallback_to_nx`` adds ``"networkx"``
# to ``backend_fallback`` so unimplemented functions reach nx's own
# pure-Python kernel — restoring drop-in compatibility for the long
# tail of ``nx.algorithms.X`` that fnx doesn't override.
Graph.__networkx_backend__ = "franken_networkx"
DiGraph.__networkx_backend__ = "franken_networkx"
MultiGraph.__networkx_backend__ = "franken_networkx"
MultiDiGraph.__networkx_backend__ = "franken_networkx"
try:
    import networkx as _nx_for_fallback_cfg

    _nx_for_fallback_cfg.config.fallback_to_nx = True
    _NETWORKX_GRAPH_DEFAULT = _nx_for_fallback_cfg.Graph
    from networkx.exception import HasACycle as _NetworkXHasACycle
except Exception:
    _NETWORKX_GRAPH_DEFAULT = Graph
    _NetworkXHasACycle = Exception


import random as _random


class _InProcPythonRandomViaNumpyBits(_random.Random):
    """Provide the random.Random algorithms using a numpy.random bit generator."""

    def __init__(self, rng=None):
        import numpy as np

        self._rng = np.random.mtrand._rand if rng is None else rng
        self.gauss_next = None

    def random(self):
        return self._rng.random()

    def getrandbits(self, k):
        if k < 0:
            raise ValueError("number of bits must be non-negative")
        numbytes = (k + 7) // 8
        x = int.from_bytes(self._rng.bytes(numbytes), "big")
        return x >> (numbytes * 8 - k)

    def getstate(self):
        return self._rng.__getstate__()

    def setstate(self, state):
        self._rng.__setstate__(state)

    def seed(self, *args, **kwds):
        raise NotImplementedError("seed() not implemented in PythonRandomViaNumpyBits")


class _InProcPythonRandomInterface:
    """Backward-compatible wrapper for pre-seeded numpy RandomState instances."""

    def __init__(self, rng=None):
        import numpy as np

        self._rng = np.random.mtrand._rand if rng is None else rng

    def random(self):
        return self._rng.random()

    def uniform(self, a, b):
        return a + (b - a) * self._rng.random()

    def randrange(self, a, b=None):
        import numpy as np

        if b is None:
            a, b = 0, a
        if b > 9223372036854775807:
            return _InProcPythonRandomViaNumpyBits(self._rng).randrange(a, b)
        if isinstance(self._rng, np.random.Generator):
            return self._rng.integers(a, b)
        return self._rng.randint(a, b)

    def choice(self, seq):
        import numpy as np

        if isinstance(self._rng, np.random.Generator):
            idx = self._rng.integers(0, len(seq))
        else:
            idx = self._rng.randint(0, len(seq))
        return seq[idx]

    def gauss(self, mu, sigma):
        return self._rng.normal(mu, sigma)

    def shuffle(self, seq):
        return self._rng.shuffle(seq)

    def sample(self, seq, k):
        return self._rng.choice(list(seq), size=(k,), replace=False)

    def randint(self, a, b):
        import numpy as np

        if b > 9223372036854775807:
            return _InProcPythonRandomViaNumpyBits(self._rng).randint(a, b)
        if isinstance(self._rng, np.random.Generator):
            return self._rng.integers(a, b + 1)
        return self._rng.randint(a, b + 1)

    def expovariate(self, scale):
        return self._rng.exponential(1 / scale)

    def paretovariate(self, shape):
        return self._rng.pareto(shape)


def _create_py_random_state(random_state=None):
    """Return a stdlib random state matching NetworkX's create_py_random_state."""
    if random_state is None or random_state is _random:
        return _random._inst
    if isinstance(random_state, _random.Random):
        return random_state
    if isinstance(random_state, int):
        return _random.Random(random_state)
    if isinstance(
        random_state, (_InProcPythonRandomInterface, _InProcPythonRandomViaNumpyBits)
    ) or type(random_state).__name__ in (
        "PythonRandomInterface",
        "PythonRandomViaNumpyBits",
    ):
        return random_state

    try:
        import numpy as np
    except ImportError:
        np = None

    if np is not None:
        if isinstance(random_state, np.random.Generator):
            return _InProcPythonRandomViaNumpyBits(random_state)
        if random_state is np.random:
            return _InProcPythonRandomViaNumpyBits(np.random.mtrand._rand)
        if isinstance(random_state, np.random.RandomState):
            if random_state is np.random.mtrand._rand:
                return _InProcPythonRandomViaNumpyBits(random_state)
            return _InProcPythonRandomInterface(random_state)
    raise ValueError(
        f"{random_state} cannot be used to generate a random.Random instance"
    )


try:
    import networkx.lazy_imports as _nx_lazy_imports

    _sys.modules[f"{__name__}.lazy_imports"] = _nx_lazy_imports
except Exception:
    pass


def _install_nx_interop_patches():
    # br-r37-c1-u3umv: patch nx.drawing.layout._process_params so fnx graphs
    # convert with edges preserved rather than falling into the duck-typed
    # node-only branch.
    try:
        import networkx.drawing.layout as _nx_layout_module

        _orig_process_params = _nx_layout_module._process_params

        def _fnx_aware_process_params(G, center, dim):
            if isinstance(G, (Graph, DiGraph, MultiGraph, MultiDiGraph)):
                from franken_networkx.backend import _fnx_to_nx

                G = _fnx_to_nx(G)
            return _orig_process_params(G, center, dim)

        _fnx_aware_process_params.__wrapped__ = _orig_process_params
        _nx_layout_module._process_params = _fnx_aware_process_params
    except Exception:
        pass

    # br-r37-c1-sg4dw: patch nx.scale_free_graph so initial_graph accepts fnx
    # MultiDiGraph instances.
    try:
        import functools as _functools_for_sfg
        import networkx as _nx_for_sfg_patch
        import networkx.generators as _nx_generators_for_sfg
        import networkx.generators.directed as _nx_directed_for_sfg

        _orig_sfg = _nx_directed_for_sfg.scale_free_graph

        @_functools_for_sfg.wraps(_orig_sfg)
        def _fnx_aware_scale_free_graph(n, *args, initial_graph=None, **kwargs):
            if initial_graph is not None and isinstance(
                initial_graph, (Graph, DiGraph, MultiGraph, MultiDiGraph)
            ):
                from franken_networkx.backend import _fnx_to_nx

                initial_graph = _fnx_to_nx(initial_graph)
                if not isinstance(initial_graph, _nx_for_sfg_patch.MultiDiGraph):
                    converted = _nx_for_sfg_patch.MultiDiGraph()
                    for node, attrs in initial_graph.nodes(data=True):
                        converted.add_node(node, **attrs)
                    for u, v, *rest in initial_graph.edges(data=True):
                        data = rest[0] if rest else {}
                        converted.add_edge(u, v, **data)
                    initial_graph = converted
            return _orig_sfg(n, *args, initial_graph=initial_graph, **kwargs)

        _nx_directed_for_sfg.scale_free_graph = _fnx_aware_scale_free_graph
        _nx_generators_for_sfg.scale_free_graph = _fnx_aware_scale_free_graph
        _nx_for_sfg_patch.scale_free_graph = _fnx_aware_scale_free_graph
    except Exception:
        pass


_install_nx_interop_patches()


# br-r37-c1-rc0923-epic-honest-measurement-vbneu.1: NetworkX's own enum, by
# identity. The previous look-alike enum with ``__module__`` rewritten to
# "networkx.algorithms.tree.mst" satisfied the coverage classifier's spelling
# check while staying a different class (``is``/``==``/``isinstance`` all False
# against nx) and made ``pickle.dumps(EdgePartition.OPEN)`` raise.
from networkx.algorithms.tree.mst import EdgePartition


def _directed_graph_has_successor(self, u, v):
    # br-r37-c1-s8dj1: on a plain directed graph this IS `has_edge(u, v)` --
    # networkx defines both as `u in self._succ and v in self._succ[u]` -- and
    # `has_edge` is the NATIVE method, now answering from node positions. The
    # form below materialises a successor ROW to answer a membership question,
    # which cost 464.0 ns against `has_edge`'s 123.3 ns for the same answer on
    # the same graph. The equivalence is asserted against networkx itself in
    # tests/python/test_has_successor_uses_the_native_edge_path.py rather than
    # taken on faith.
    #
    # THE ROW FORM IS KEPT FOR ASSIGNED PRIVATE STORAGE, and that is the whole
    # reason it is written this way: br-r37-c1-ppiei found that the MAPPING
    # decides whether `u` exists, not the node view, so under an assigned
    # `_succ` carrying a node the native store does not, asking the store
    # returns False where networkx returns True -- a SILENT wrong answer.
    if type(self) in _NATIVE_DIRECTED_EDGE_CLASSES and not _has_networkx_private_storage(
        self
    ):
        return self.has_edge(u, v)
    succ = self.succ
    return u in succ and v in succ[u]


def _directed_graph_has_predecessor(self, u, v):
    # The `_pred` twin of the above; same authority, same reasoning. Note the
    # ARGUMENT ORDER: `has_predecessor(u, v)` asks whether v -> u exists, so the
    # native call is `has_edge(v, u)`.
    if type(self) in _NATIVE_DIRECTED_EDGE_CLASSES and not _has_networkx_private_storage(
        self
    ):
        return self.has_edge(v, u)
    pred = self.pred
    return u in pred and v in pred[u]


def _digraph_out_edges(self, nbunch=None, data=False, default=None):
    owner = _shared_unsplit_owner(self)
    if owner is not None:
        return _digraph_out_edges(owner, nbunch=nbunch, data=data, default=default)
    is_native_digraph = type(self) is DiGraph and not _has_networkx_private_storage(self)
    # br-r37-c1-outedges: out_edges == edges() for a DiGraph, but this delegated
    # to ``self.edges(...)`` (the EdgeDataView Python machinery) instead of the
    # node-major native builder that _digraph_in_edges already uses — so
    # out_edges(data=True) was ~4x nx. Route the all-edges path through the
    # native ``_native_edges_*`` kernels (byte-identical to nx out_edges order +
    # data). Same exact-DiGraph gate as in_edges (conversion / subgraph views
    # keep the Python edges() path: their inner is not the source of truth).
    if nbunch is None and is_native_digraph:
        if data is False:
            native = getattr(self, "_native_edges_no_data", None)
            if native is not None:
                return native()
        elif data is True:
            native = getattr(self, "_native_edges_with_data", None)
            if native is not None:
                return native()
        else:
            native = getattr(self, "_native_edges_data_key", None)
            if native is not None:
                return native(data, default)
    # br-r37-c1-edgenbnative (cc): out_edges(nbunch, data=False) — one native pass
    # (canonical filter + succ-row tuples) replaces the EdgeDataView machinery.
    if (
        data is False
        and is_native_digraph
        and (
            _nbunch_is_iterable_bunch(self, nbunch)
        )
    ):
        # iterable nbunch only — a single in-graph node must return its edges via
        # the view path (nbunch_iter), not be try_iter'd by the native kernel.
        native = getattr(self, "_native_out_edges_nbunch_no_data", None)
        if native is not None:
            try:
                result = _nbunch_data_cache(
                        self, "_fnx_out_edges_nb_nodata_cache", nbunch, native
                    )
            except TypeError as exc:
                raise NetworkXError(str(exc))
            if result is not None:
                return result
    # br-r37-c1-edgenbnative (cc): out_edges(nbunch, data=True) — native succ rows +
    # live attr dicts (~0.21x via the EdgeDataView path). iterable nbunch only.
    if (
        data is True
        and is_native_digraph
        and (
            _nbunch_is_iterable_bunch(self, nbunch)
        )
    ):
        native = getattr(self, "_native_out_edges_nbunch_data", None)
        if native is not None:
            try:
                result = _digraph_out_edges_data_cache(self, nbunch, native)
            except TypeError as exc:
                raise NetworkXError(str(exc))
            if result is not None:
                return result
    if (
        data is not False
        and data is not True
        and is_native_digraph
        and (
            _nbunch_is_iterable_bunch(self, nbunch)
        )
    ):
        native = getattr(self, "_native_out_edges_nbunch_data_key", None)
        if native is not None:
            try:
                # br-r37-c1-p1tyz: VALUES are not memoized - an attribute
                # write moves neither seq, so a remembered value goes stale.
                result = native(nbunch, data, default)
            except TypeError as exc:
                raise NetworkXError(str(exc))
            if result is not None:
                return result
    return list(self.edges(nbunch=nbunch, data=data, default=default))


def _digraph_in_edges(self, nbunch=None, data=False, default=None):
    owner = _shared_unsplit_owner(self)
    if owner is not None:
        return _digraph_in_edges(owner, nbunch=nbunch, data=data, default=default)
    is_native_digraph = type(self) is DiGraph and not _has_networkx_private_storage(self)
    # br-r37-c1-inedges: all-edges path routes to the native node-major
    # predecessor builder instead of walking pred[target].items() via the
    # DiAdjacencyView lambda chain (~176x no-data / ~50x data). data=True
    # reuses the live attr dict (marks dirty for weight re-sync); data=<key>
    # yields the value. Gated on exact DiGraph type: conversion views
    # (_DirectedGraphConversionView, a DiGraph subclass with an empty inner that
    # computes edges from a wrapped graph) and SubgraphViews inherit this method
    # but must keep the Python pred-walk; their inner is not the source of truth.
    if nbunch is None and is_native_digraph:
        if data is False:
            native = getattr(self, "_native_in_edges_no_data", None)
            if native is not None:
                return native()
        elif data is True:
            native = getattr(self, "_native_in_edges_with_data", None)
            if native is not None:
                return native()
        else:
            native = getattr(self, "_native_in_edges_data_key", None)
            if native is not None:
                return native(data, default)
    elif is_native_digraph and (
        _nbunch_is_iterable_bunch(self, nbunch)
    ):
        # iterable nbunch -> native pred-major pass. br-r37-c1-inedges (cc).
        # br-r37-c1-inedgesnbdatakey (cc): data=<attr> now routes to a native too
        # (index-native store read), previously fell to the Python pred-walk (0.32x).
        native = None
        if data is False:
            native = getattr(self, "_native_in_edges_nbunch_no_data", None)
        elif data is True:
            native = getattr(self, "_native_in_edges_nbunch_data", None)
        else:
            native = getattr(self, "_native_in_edges_nbunch_data_key", None)
        if native is not None:
            try:
                if data is True:
                    # br in_edges nbunch-data cache: mirror the out_edges cache so
                    # the directed pair matches (was 0.68x on the repeated view).
                    result = _digraph_in_edges_data_cache(self, nbunch, native)
                elif data is False:
                    result = _nbunch_data_cache(
                        self, "_fnx_in_edges_nb_nodata_cache", nbunch, native
                    )
                else:
                    # br-r37-c1-p1tyz: values are not memoized (they go stale).
                    result = native(nbunch, data, default)
            except TypeError as exc:
                raise NetworkXError(str(exc))
            if result is not None:
                return result
    result = []
    for target in self.nbunch_iter(nbunch):
        for source, attrs in self.pred[target].items():
            if data is True:
                result.append((source, target, attrs))
            elif data is False:
                result.append((source, target))
            else:
                result.append((source, target, attrs.get(data, default)))
    return result


def _multidigraph_out_edges(self, nbunch=None, data=False, keys=False, default=None):
    owner = _shared_unsplit_owner(self)
    if owner is not None:
        return _multidigraph_out_edges(
            owner, nbunch=nbunch, data=data, keys=keys, default=default
        )
    is_native_mdg = type(self) is MultiDiGraph and not _has_networkx_private_storage(self)
    # br-r37-c1-mdgoutedge (cc): out_edges(nbunch, data=False) — one native pass
    # (succ x edge_keys in rust; nx iterates succ[u] keydicts in Python). iterable
    # nbunch only (a single in-graph node returns its edges via the view path).
    if (
        data is False
        and is_native_mdg
        and (
            _nbunch_is_iterable_bunch(self, nbunch)
        )
    ):
        native = getattr(self, "_native_mdg_out_edges_nbunch_no_data", None)
        if native is not None:
            try:
                result = _nbunch_data_cache(
                        self, "_fnx_mdg_out_edges_nb_nodata_cache", nbunch, native, keys
                    )
            except TypeError as exc:
                raise NetworkXError(str(exc))
            if result is not None:
                return result
    # br-r37-c1-mdgoutedge (cc): out_edges(nbunch, data=True) — native succ rows +
    # live attr dicts. iterable nbunch only.
    if (
        data is True
        and is_native_mdg
        and (
            _nbunch_is_iterable_bunch(self, nbunch)
        )
    ):
        native = getattr(self, "_native_mdg_out_edges_nbunch_data", None)
        if native is not None:
            try:
                result = _digraph_out_edges_data_cache(self, nbunch, native, keys)
            except TypeError as exc:
                raise NetworkXError(str(exc))
            if result is not None:
                return result
    if (
        data is not False
        and data is not True
        and is_native_mdg
        and (
            _nbunch_is_iterable_bunch(self, nbunch)
        )
    ):
        # br-r37-c1-outedgesnbattr (cc): keys=True now routes here too (the native
        # builds the 4-tuple); previously keys=True fell to the slow Python view (0.34x).
        native = getattr(self, "_native_mdg_out_edges_nbunch_data_key", None)
        if native is not None:
            try:
                # br-r37-c1-p1tyz: values are not memoized (they go stale).
                result = native(nbunch, data, default, keys)
            except TypeError as exc:
                raise NetworkXError(str(exc))
            if result is not None:
                return result
    return list(self.edges(nbunch=nbunch, data=data, keys=keys, default=default))


def _multidigraph_in_edges(self, nbunch=None, data=False, keys=False, default=None):
    owner = _shared_unsplit_owner(self)
    if owner is not None:
        return _multidigraph_in_edges(
            owner, nbunch=nbunch, data=data, keys=keys, default=default
        )
    is_native_mdg = type(self) is MultiDiGraph and not _has_networkx_private_storage(self)
    # br-r37-c1-mdginedges (cc): full-graph in_edges(data=True) was a pure-Python
    # self.pred[target].items() loop (~11x slower than nx). Route it to a native
    # target-major pass (byte-identical order, live attr dicts). Other shapes
    # (nbunch / keys / data=key / data=False) keep the Python path below.
    if nbunch is None and is_native_mdg:
        if data is True:
            native = getattr(self, "_native_mdg_in_edges_with_data", None)
            if native is not None:
                result = native(keys)
                if result is not None:
                    return result
        elif data is False:
            native = getattr(self, "_native_mdg_in_edges_no_data", None)
            if native is not None:
                result = native(keys)
                if result is not None:
                    return result
        else:  # data is an attribute key -> (s, t[, key], attrs.get(data, default))
            native = getattr(self, "_native_mdg_in_edges_data_key", None)
            if native is not None:
                result = native(data, default, keys)
                if result is not None:
                    return result
    elif is_native_mdg and (
        _nbunch_is_iterable_bunch(self, nbunch)
    ):
        # iterable nbunch -> native pred-major pass (a single in-graph node returns
        # its in-edges via the Python path below). br-r37-c1-mdginedges (cc).
        if data is True:
            native = getattr(self, "_native_mdg_in_edges_nbunch_data", None)
        elif data is False:
            native = getattr(self, "_native_mdg_in_edges_nbunch_no_data", None)
        else:
            native = getattr(self, "_native_mdg_in_edges_nbunch_data_key", None)
        if native is not None:
            try:
                # br-r37-c1-mdginb: route through the SAME memo the other three
                # members of this family already use. `_digraph_in_edges_data_cache`
                # existed and was wired at exactly ONE call site (DiGraph.in_edges)
                # while `_digraph_out_edges_data_cache` was wired at four, so this
                # was the one nbunch edge-view in the family paying the native
                # kernel on every repeated call.
                # br-r37-c1-dinbfam: data=True and data=False call DIFFERENT
                # natives but with IDENTICAL native_args (just `keys`), so a
                # shared slot made their cache keys equal and data=False was
                # served data=True's rows. Separate slots, one per spelling.
                if data is True:
                    result = _nbunch_data_cache(
                        self, "_fnx_mdg_in_edges_nb_data_cache", nbunch, native, keys
                    )
                elif data is False:
                    result = _nbunch_data_cache(
                        self, "_fnx_mdg_in_edges_nb_nodata_cache", nbunch, native, keys
                    )
                else:
                    # br-r37-c1-p1tyz: values are not memoized (they go stale).
                    result = native(nbunch, data, default, keys)
            except TypeError as exc:
                raise NetworkXError(str(exc))
            if result is not None:
                return result
    result = []
    for target in self.nbunch_iter(nbunch):
        for source, keyed_attrs in self.pred[target].items():
            for key, attrs in keyed_attrs.items():
                if data is True and keys:
                    result.append((source, target, key, attrs))
                elif data is True:
                    result.append((source, target, attrs))
                elif data is False and keys:
                    result.append((source, target, key))
                elif data is False:
                    result.append((source, target))
                elif keys:
                    result.append((source, target, key, attrs.get(data, default)))
                else:
                    result.append((source, target, attrs.get(data, default)))
    return result


def _nbunch_membership_container(graph):
    """The ADJACENCY when this graph carries assigned private storage, else None.

    br-r37-c1-vbe1o: nx's `nbunch_iter` reads `self._adj` — both to iterate when
    `nbunch is None` and to filter a sequence. fnx used the node view for both,
    which gives the same answer on an ordinary graph and the WRONG one on a graph
    carrying assigned storage, where the node set and the adjacency differ. It
    was wrong in both directions at once: a node carried only by an assigned
    `_adj` was filtered out, and one carried only by an assigned `_node` was let
    through.

    Returning None rather than the node view lets each caller keep its own cheap
    default — `iter(self)` for the None branch, `self.nodes` for the filter —
    which is what preserves the containers br-r37-c1-oaamq measured and chose.
    The private lookup happens once per CALL, not once per node.
    """
    storage = vars(graph)
    if _shared_unsplit_owner(graph, storage) is not None:
        return None
    if (
        _PRIVATE_NODE_OVERRIDE in storage
        or _PRIVATE_ADJ_OVERRIDE in storage
        or _PRIVATE_SUCC_OVERRIDE in storage
        or _PRIVATE_PRED_OVERRIDE in storage
        or _SHARED_STORAGE_SOURCE in storage
    ):
        return graph.adj
    return None


def _nbunch_filter_container(graph):
    """The container `nbunch_iter` should test membership against.

    br-r37-c1-vbe1o: networkx filters with `n in self._adj`, a plain dict, so its
    per-node test is a C hash lookup. fnx used `self.nodes`, whose
    `__contains__` crosses into PyO3 every time -- measured 0.70x against
    networkx over a 1000-node nbunch, about 15 ns per node. CERTIFIED 1.4159x
    self-speedup, taking the cell from 0.70x to 1.006x against networkx.

    The graph already maintains a real dict of node keys (the mirror the native
    node iterator walks), reachable as `_fnx_node_key_dict`. READ-ONLY: it is the
    live mirror, not a copy, and nbunch_iter only tests membership against it.

    Dict membership raises TypeError on an unhashable key exactly as networkx's
    does, which is the property br-r37-c1-oaamq relied on when it dropped the
    per-node `hash()`. That is why this is a safe swap and `Graph.__contains__`
    was not -- that one answers False instead of raising.

    CONCRETE graphs only. A filtered / conversion / reverse view SUBCLASSES the
    native class so the accessor exists on it, but its Rust base is EMPTY: the
    mirror would come back empty and filter every node out. That is the failure
    br-r37-c1-kum9v records for the other native fast paths, and
    test_to_directed_view_nbunch_argument catches it.
    """
    private = _nbunch_membership_container(graph)
    if private is not None:
        return private
    target = _shared_unsplit_owner(graph) or graph
    if type(target) in (Graph, DiGraph, MultiGraph, MultiDiGraph):
        node_dict = getattr(target, "_fnx_node_key_dict", None)
        if node_dict is not None:
            return node_dict()
    return graph.nodes


def _nbunch_names_one_node(graph, nbunch):
    """br-r37-c1-jl8x1: ``nbunch_iter``'s FIRST rule, kept in one place.

    ``nbunch_iter`` opens with ``elif nbunch in self: return iter([nbunch])``, so
    a container that is ITSELF a node names that ONE node rather than a sequence
    of its elements. A TUPLE and a FROZENSET are both hashable and both perfectly
    ordinary networkx node keys — ``grid_graph`` and the cartesian products give
    every node a ``(row, col)`` tuple — so this is not a corner case.

    The three list-backed edge views classified their own nbunch with
    ``isinstance(nbunch, (list, tuple, set, frozenset))`` and therefore re-derived
    that rule WITHOUT its first clause: a tuple node was try_iter'd for the nodes
    ``1`` and ``2``, neither of which existed, and the view answered with an empty
    list instead of raising. 30 cells of a 68-cell differential sweep diverged
    that way. Their own comments already said a single in-graph node had to reach
    the view path; the predicate simply did not say it.

    ``list`` and ``set`` short-circuit because they are UNHASHABLE and so can
    never be a node — that keeps the hot ``edges([n])`` spelling free of the
    membership probe. Everything else is asked, because everything else can be:
    a namedtuple is a tuple subclass, and a user class with ``__iter__`` can be
    hashable too. The probe is ``nbunch in graph``, character for character what
    ``nbunch_iter`` asks, rather than a second opinion about it.
    """
    if nbunch is None or type(nbunch) is list or type(nbunch) is set:
        return False
    try:
        return nbunch in graph
    except TypeError:
        return False


def _nbunch_is_iterable_bunch(graph, nbunch):
    """br-r37-c1-jl8x1: is this nbunch a SEQUENCE of nodes, or one node?

    The three list-backed edge views each carried their own copy of this
    predicate — eleven copies of ``isinstance(nbunch, (list, tuple, set,
    frozenset)) or (hasattr(nbunch, "__iter__") and not isinstance(nbunch, (str,
    bytes)))`` — and every copy was missing ``nbunch_iter``'s first clause. Their
    comments already said a single in-graph node had to reach the view path; the
    code did not. One copy is the fix and the point.

    ORDER IS DELIBERATE AND MEASURED. ``list`` and ``set`` answer first, on two
    ``type()`` compares and nothing else: both are UNHASHABLE, so neither can
    ever BE a node, and ``list`` is the spelling every hot caller uses. Putting
    the four-way ``isinstance`` and the ``hasattr`` ahead of them cost 1.5-2.6
    percent on the ``edges(nbunch)`` rows in a balanced-square A/B, which is the
    whole budget this predicate has. Only a tuple, a frozenset or another
    hashable iterable reaches ``nbunch in graph`` — the one case where the answer
    can change.
    """
    if type(nbunch) is list or type(nbunch) is set:
        return True
    if not (
        isinstance(nbunch, (list, tuple, set, frozenset))
        or (hasattr(nbunch, "__iter__") and not isinstance(nbunch, (str, bytes)))
    ):
        return False
    return not _nbunch_names_one_node(graph, nbunch)


def _resolved_nbunch_rows(graph, nbunch):
    """br-r37-c1-cnwof: what ``graph.nbunch_iter(nbunch)`` yields, cheaply.

    Every ``edges(nbunch)`` return on the three list-backed views hands
    ``_guarded_edge_list`` a ``graph.nbunch_iter(nbunch)`` generator purely so
    the fail-fast row guard has the RESOLVED node list, and
    ``_guarded_edge_list`` immediately materialises it with ``tuple(...)``.
    Measured on a 200-node MultiGraph with a one-node nbunch, that round trip
    costs ~780 ns of the ~3920 ns the view CONSTRUCTION takes: a generator
    frame, an exception translator that never fires, and ``nbunch_iter``'s
    ``if nbunch in self`` single-node probe that a list can never satisfy, on
    top of ~75 ns of actual filtering.

    A ``list`` nbunch is the only form this shortcut serves, and the exclusion
    of ``tuple`` is load-bearing rather than conservatism: a TUPLE CAN BE A
    NODE, and ``nbunch_iter``'s ``if nbunch in self`` branch resolves such a
    tuple to that ONE node rather than to its elements. A list is unhashable,
    so it can never reach that branch and the two spellings cannot diverge.

    The membership container is ``nbunch_iter``'s own — private storage and the
    node-key mirror included — so the filtered answer is identical, and an
    unhashable ELEMENT still raises out of dict membership. That case falls
    back to the generator rather than translating the error here, because the
    NetworkXError text is ``nbunch_iter``'s contract and there is no reason for
    two copies of it.
    """
    if nbunch is None:
        return None
    if type(nbunch) is list:
        container = _nbunch_filter_container(graph)
        try:
            return [node for node in nbunch if node in container]
        except TypeError:
            pass
    return graph.nbunch_iter(nbunch)


def _graph_nbunch_iter(self, nbunch=None):
    # br-r37-c1-nbunchnone (cc): nbunch=None is iteration over ALL nodes; route it
    # to the cheap cached node iterator (iter(self)) BEFORE building self.adj — the
    # old `adjacency = self.adj` ran unconditionally and cost ~12x for the None case
    # (0.09x vs nx) just to iterate the view's keys. self.adj is still built for the
    # membership-filter path below (its __contains__ is the fast container there).
    if nbunch is None:
        # br-r37-c1-vbe1o: nx is `iter(self._adj)`. On an ordinary graph that is
        # the node set and `iter(self)` is the cheap way to say it; under
        # assigned private storage the two differ and the ADJACENCY is the one
        # nx iterates. The private branch is the rare one and pays for itself.
        container = _nbunch_membership_container(self)
        return iter(self) if container is None else iter(container)
    if nbunch in self:
        # nx tests the NODE view here (`elif nbunch in self`), not the adjacency
        # -- the same two-rule split the degree view needed. Left as-is on
        # purpose.
        return iter([nbunch])
    # br-r37-c1-oaamq: the br-cc-nbunchbulk native bulk path used to sit here. It
    # filtered a re-iterable nbunch in ONE native call to avoid the per-node
    # `n in self.adj` crossing below, and against THAT baseline it was a real
    # improvement. But `self.adj` was never the cheapest container, and the
    # comparison was never made against the others. Measured, N=4000, filtering
    # 2000 nodes, so each row is the same work:
    #
    #     networkx list(nbunch_iter)      88.3 us
    #     native _nbunch_present         167.0 us   <- what was here
    #     py `n in self.adj`             433.6 us   <- what it replaced
    #     py `n in self.nodes`            93.3 us
    #     py `n in self`                  78.5 us   <- cheapest, and beats nx
    #
    # so the bulk call was twice networkx's cost while a one-word change to the
    # container is below it. nbunch_iter was the worst row in the whole sweep at
    # 0.453x-0.515x across all four classes; it is the container, not the loop.
    #
    # REMOVING IT ALSO RESTORES TWO CONTRACTS, which is the better reason. nx's
    # nbunch_iter returns a lazy GENERATOR over the live graph. The bulk call was
    # eager, so a node added between the call and the iteration was invisible:
    #
    #     it = G.nbunch_iter(['a', 'b', 'later']); G.add_node('later'); list(it)
    #     networkx -> ['a', 'b', 'later']      fnx -> ['a', 'b']
    #
    # on all four classes, and the returned type was list_iterator where nx's is
    # generator. Both are back with the eager path gone.

    def bunch_iter(nlist, adj):
        try:
            for n in nlist:
                if n in adj:
                    yield n
        except TypeError as err:
            exc, message = err, err.args[0]
            if "iter" in message:
                exc = NetworkXError("nbunch is not a node or a sequence of nodes.")
            if "object is not iterable" in message:
                exc = NetworkXError(f"Node {nbunch} is not in the graph.")
            if "hashable" in message:
                exc = NetworkXError(f"Node {n} in sequence nbunch is not a valid node.")
            raise exc

    # `self.nodes`, not `self.adj`: same membership answer (adjacency keys ARE
    # the nodes) and 3.3x cheaper. It also RAISES TypeError on an unhashable
    # element the way nx's plain-dict membership does, which is what lets the
    # explicit per-node ``hash(n)`` go — that call alone was 71.4us of the
    # 181.2us total, i.e. more than networkx spends on the whole operation.
    # ``Graph.__contains__`` cannot be used instead: it is marginally cheaper
    # still (109.8us vs 129.7us) but ANSWERS FALSE for an unhashable node
    # rather than raising, so it would need the hash back and end up dearer.
    # Both keep working for the proxy views the old bulk path had to exclude.
    #
    # br-r37-c1-vbe1o: "same membership answer" holds for an ORDINARY graph and
    # not for one carrying assigned private storage, where the node view and the
    # adjacency are different sets. nx filters this branch on `self._adj`, so a
    # node carried only by an assigned `_adj` must survive the filter and one
    # carried only by an assigned `_node` must not — fnx had both backwards.
    #
    # The check is per CALL, not per node, so it amortises over the whole
    # nbunch and the ordinary path keeps the cheap container the note above
    # earned.
    return bunch_iter(nbunch, _nbunch_filter_container(self))


def _size_with_unweighted_int(size_impl):
    def size(self, weight=None):
        if weight is None:
            return self.number_of_edges()
        # br-r37-c1-sizedeg: the native ``size_impl`` reads the live edge attr dict
        # per edge (PyO3 get_item + extract f64 -> ~637us / 2000 edges = 0.45x vs nx).
        # nx's own formula ``sum(d for _, d in self.degree(weight=...)) / 2`` routes
        # through the faster degree(weight) path (~2x: 0.45x -> 0.87x) and is what nx
        # uses for EVERY weight type (str / callable / arbitrary key). Byte-identical
        # to size_impl 2000/2000 across Graph/DiGraph/MultiGraph/MultiDiGraph incl
        # self-loops + negative/float weights (degree counts each edge once per
        # endpoint — self-loops twice — so /2 recovers the per-edge weight sum). The
        # old str-only branch through size_impl is the slow path; drop it. (size_impl
        # kept in the signature for call-site compatibility.)
        # br-r37-c1-sizeweight: this also fixes the prior TypeError on callable/
        # non-str weight, since the Rust size_impl's PyO3 signature was ``weight: str``.
        #
        # br-r37-c1-wsize (cc): the degree route still materialises N
        # ``(node, PyFloat)`` degree pairs just to reduce them to one scalar
        # (~all of size(weight)'s cost). When ``weight`` is a string key, try the
        # native store scalar first: on a clean graph with all-integer weights it
        # sums the CgseValue store in one walk (no per-node PyObject) and returns
        # the size directly — byte-identical to ``sum(int degrees)/2``. It returns
        # None (→ the exact degree path below) on a dirty mirror, any non-integer
        # weight, or a non-string/callable weight, so float/mixed parity is
        # unchanged.
        target = _shared_unsplit_owner(self)
        if type(weight) is str and (
            target is not None or not _has_networkx_private_storage(self)
        ):
            target = target or self
            fast = target._weighted_size_fast(weight)
            if fast is not None:
                return fast
            # br-r37-c1-7pzs9: the scalar above is INT-only (it sums each edge
            # once, which is exact for ints and wrong for floats), so every
            # float/mixed graph fell to the degree route below and materialised N
            # (node, PyFloat) pairs to produce ONE number — 2 Python frames for an
            # int graph against ~2N for a float one. This sibling reproduces nx's
            # TWO-LEVEL sum natively (compensated per node, compensated fold over
            # the node totals, then the halving), which a one-pass edge sum does
            # NOT: it diverges from nx on 7% of uniform(0,1) graphs and 30% of
            # wide-range ones. Returns None on a dirty store, a non-numeric
            # weight, overflow, or an integer total past 2**53, which keeps those
            # on the byte-identical formula below.
            fast = getattr(target, "_weighted_size_fast_float", None)
            if fast is not None:
                fast = fast(weight)
                if fast is not None:
                    return fast
        s = sum(d for _, d in self.degree(weight=weight))
        return s / 2

    return size


def _number_of_edges_with_endpoints(number_of_edges_impl):
    def number_of_edges(self, u=None, v=None):
        if u is None and v is None:
            # br-r37-c1-vbe1o: the private-storage case is NOT handled here. This
            # factory is one of two same-named definitions; the live one for a
            # graph carrying assigned storage is the instance-level wrapper
            # further down (freevar `raw_number_of_edges`), which is where the
            # derivation belongs. Editing this one changed nothing — the third
            # dead-twin in this campaign, caught by the sweep count not moving.
            return number_of_edges_impl(self)
        if v is None:
            if u not in self:
                raise KeyError(u)
            return 0
        if u is None:
            raise TypeError("number_of_edges() missing 1 required positional argument: 'u'")
        return 1 if self.has_edge(u, v) else 0

    return number_of_edges


def _neighbors_with_networkx_missing_node_error(neighbors_impl, *, graph_kind="graph"):
    def neighbors(self, node):
        # br-r37-c1-i9whv: nx raises TypeError on unhashable nodes
        # (the underlying ``adj[n]`` dict access calls hash(n) first).
        # fnx fell through to ``not in self`` membership which silently
        # returned False on unhashable, then raised NetworkXError.
        _HASH_PROBE.get(node)
        try:
            result = neighbors_impl(self, node)
        except NodeNotFound as exc:
            raise NetworkXError(f"The node {node} is not in the {graph_kind}.") from exc
        # br-nbriter: nx.Graph.neighbors returns a dict_keyiterator
        # (iterator). fnx's Rust impl returns a list. Code like
        # ``for x in G.neighbors(u): break`` + ``for x in same_list``
        # accidentally restarts iteration because list iteration is not
        # stateful across re-entries — e.g. nx.dfs_labeled_edges broke
        # on fnx when it pushed ``(start, G.neighbors(start))`` onto a
        # stack and the outer ``for child in children`` re-ran from the
        # beginning after break, producing spurious nontree edges.
        # Always return a proper iterator so algorithms that rely on
        # iterator state work.
        # br-r37-c1-nbritype (cycle 218): nx returns ``iter(self._adj[n])``,
        # whose runtime type is ``dict_keyiterator``.  fnx previously
        # returned ``list_iterator`` (from ``iter(list)``), diverging
        # on ``type(G.neighbors(u)).__name__``.  Drop-in code that
        # does ``isinstance(it, type({}.__iter__()))`` saw the wrong
        # type.  Emit a proper ``dict_keyiterator`` by going through
        # ``dict.fromkeys`` (the result is unique-keyed anyway in nx,
        # so no semantic loss).
        if isinstance(result, list):
            return iter(dict.fromkeys(result))
        return result

    return neighbors


def _remove_edge_with_networkx_missing_edge_error(
    remove_edge_impl, *, missing_edge_message, supports_key=False
):
    if supports_key:

        def remove_edge(self, u, v, key=None):
            # br-r37-c1-i9whv: hash check before membership for nx parity.
            _HASH_PROBE.get(u)
            _HASH_PROBE.get(v)
            if key is None:
                if not self.has_edge(u, v):
                    raise NetworkXError(missing_edge_message.format(u=u, v=v))
            elif not self.has_edge(u, v, key):
                # mutation-matrix r3: nx's `self._adj[u][v]` KeyError fires
                # BEFORE key handling — a missing PAIR reports without the
                # key; only a present pair with a missing KEY mentions it.
                if not self.has_edge(u, v):
                    raise NetworkXError(missing_edge_message.format(u=u, v=v))
                raise NetworkXError(f"The edge {u}-{v} with key {key} is not in the graph.")
            result = remove_edge_impl(self, u, v, key)
            _invalidate_adjacency_row_caches(self)
            return result

    else:

        def remove_edge(self, u, v):
            # br-r37-c1-i9whv: hash check before membership for nx parity.
            _HASH_PROBE.get(u)
            _HASH_PROBE.get(v)
            if not self.has_edge(u, v):
                raise NetworkXError(missing_edge_message.format(u=u, v=v))
            result = remove_edge_impl(self, u, v)
            _invalidate_adjacency_row_caches(self)
            return result

    return remove_edge


def _remove_node_with_networkx_missing_node_error(remove_node_impl, *, graph_kind="graph"):
    def remove_node(self, n):
        # br-r37-c1-g438p: nx raises TypeError('unhashable type: ...')
        # before the membership check. fnx's ``n not in self`` ran the
        # __contains__ path which silently returned False on unhashable
        # nodes, causing remove_node to raise NetworkXError("not in
        # graph") instead. hash() up front for nx parity.
        _HASH_PROBE.get(n)
        if n not in self:
            raise NetworkXError(f"The node {n} is not in the {graph_kind}.")
        _detach_rows_before_node_removal(self, n)
        result = remove_node_impl(self, n)
        _invalidate_adjacency_row_caches(self)
        return result

    return remove_node


# br-r37-c1-q32e6: THE HASHABILITY PROBE, and it is a dict on purpose.
#
# Every one of these call sites is asserting networkx's hashability contract on a
# node or edge key. networkx asserts it by REACHING A DICT, and CPython 3.14 gives
# a dict subscript a longer TypeError than a bare hash does:
#
#     d[k]      cannot use 'X' as a dict key (unhashable type: 'X')
#     hash(k)   unhashable type: 'X'
#
# So `hash(k)` was answering the right question with the wrong words. A 76-cell
# sweep of the public spellings that can meet an unhashable key found 43 divergent
# against live networkx, ALL of them on the message alone - same exception type,
# same ordering, same partial graph state.
#
# THE WORDING IS NOT SPELLED OUT ANYWHERE. Hard-coding it pins fnx to one CPython
# version and it has already changed once; probing a real dict means fnx says
# whatever the running interpreter says, for free, on every version.
#
# It is also CHEAPER than the call it replaces: 13.5 ns for `.get` against 16.6 ns
# for `hash()` on a str key (repeat-min of 7 over 2e6 iterations), because a dict
# lookup that misses is less work than the builtin call around the same hash.
#
# It must stay EMPTY. Nothing writes to it; a `.get` that found something would
# still be discarded, so an accident here is harmless rather than a correctness
# hazard.
_HASH_PROBE: dict = {}


def _FailFastEdgeIterator(
    graph,
    iterable,
    *,
    guard_edge_count=False,
    nbunch_rows=None,
    ignore_removed_nbunch_row=False,
    refresh_rows=None,
    initial_rows=None,
):
    # br-r37-c1-edgesdataperf: O(1) per-element staleness check against
    # snapshotted counts/revisions (was an O(N) tuple-build + compare per
    # __next__, i.e. O(E*N)). nx's contract: mutating the graph SIZE during
    # iteration raises; key-permutation does not.
    #
    # br-r37-c1-2a00r: a generator FUNCTION (was a class with __next__). The
    # baseline is still captured eagerly here (call time == the old __init__),
    # so `it = iter(view); G.add_node(); list(it)` still raises exactly as
    # before. But consumers drain the returned generator via the C-level
    # generator protocol with the guard values as cell-locals — no per-element
    # bound-method dispatch + LOAD_ATTR chain. This was the dominant cost of
    # list(DiGraph.edges()) (~6.8ms of the 12ms for 40k edges) and helps every
    # _FailFastEdgeIterator consumer (EdgeDataView, OutEdgeView, etc.).
    use_seq_guard = (
        hasattr(graph, "nodes_seq")
        and (not guard_edge_count or hasattr(graph, "edges_seq"))
        and not _has_networkx_private_storage(graph)
    )
    it = iter(iterable)
    _err = "dictionary changed size during iteration"

    # br-r37-c1-hihrf: an NBUNCH iteration is not iterating the node dict, so
    # networkx cannot see a node added elsewhere. Its `MultiEdgeDataView.__iter__`
    # walks `self._nbunch` and then each node's adjacency dict, so the only
    # mutation it can notice is one that resizes the row it is standing in.
    # The guard above answers a coarser question - "did ANYTHING change" - and
    # so raised on five mutations networkx completes through.
    #
    # The sequence compare stays the only per-item work. It becomes a TRIGGER:
    # the expensive row question is asked only once a mutation has actually been
    # observed, and the snapshot is then refreshed so an irrelevant mutation
    # does not re-arm it for every remaining item.
    if nbunch_rows is not None and use_seq_guard:
        try:
            if graph.is_directed():
                degree_of = graph.out_degree
                pairs = getattr(graph, "_native_out_degree_pairs_subset", None)
            else:
                degree_of = graph.degree
                pairs = getattr(graph, "_native_degree_pairs_subset", None)
            if pairs is not None:
                row_sizes = dict(pairs(list(nbunch_rows)))
            else:
                row_sizes = {node: degree_of(node) for node in nbunch_rows}
        except Exception:  # noqa: BLE001 - an odd graph keeps the coarse guard
            row_sizes = None
        if row_sizes is not None:

            # br-r37-c1-u5tyh: EAGERLY, at call time, which is what the
            # non-nbunch `_gen` beside this one already does and what this
            # function's own header comment promises ("the baseline is still
            # captured eagerly here"). Inside the generator body it was captured
            # at the FIRST `next()` instead, so `it = iter(view); G.add_edge(...);
            # list(it)` compared the graph against itself and reported the
            # pre-mutation list — the one shape where nothing had been yielded
            # yet, and so the one the row rule could not catch later either.
            base_nodes = graph.nodes_seq
            base_edges = graph.edges_seq if guard_edge_count else None
            current_rows = initial_rows

            def _row_move(previous, emitted, at_end):
                """What networkx does once the graph has moved mid-walk.

                ``previous`` is the item handed out last, whose row networkx
                is standing in; ``emitted`` counts the items handed out, or is
                None when the splice point is unknown. Raises where networkx's
                row dict reports a resize; otherwise returns the rows still
                owed after ``emitted``, rebuilt from the graph as it now is,
                or None to carry on with the list as built.
                """
                nonlocal current_rows
                try:
                    owner = previous[0]
                    nbr = previous[1]
                except (TypeError, IndexError, KeyError):
                    owner = None
                    nbr = None
                prev_rows = (
                    list(list.__iter__(current_rows))
                    if isinstance(current_rows, list)
                    else current_rows
                )
                fresh = None
                if owner in row_sizes:
                    # MultiEdgeDataView holds the source row it already
                    # entered.  Removing that source (including clear())
                    # detaches the native row but does not resize the captured
                    # dict in NetworkX, so the remaining materialised rows must
                    # still drain.  A present owner keeps the normal live-row
                    # size check.
                    if not (ignore_removed_nbunch_row and owner not in graph):
                        if degree_of(owner) != row_sizes[owner]:
                            if (
                                graph.is_multigraph()
                                and prev_rows is not None
                                and refresh_rows is not None
                                and nbr is not None
                            ):
                                fresh = refresh_rows()
                                if fresh is not None:
                                    old_cell = sum(
                                        1
                                        for e in prev_rows
                                        if e[0] == owner and e[1] == nbr
                                    )
                                    new_cell = sum(
                                        1
                                        for e in fresh
                                        if e[0] == owner and e[1] == nbr
                                    )
                                    if graph.is_directed():
                                        old_nbrs = {
                                            e[1]
                                            for e in prev_rows
                                            if e[0] == owner
                                        }
                                        new_nbrs = {
                                            e[1] for e in fresh if e[0] == owner
                                        }
                                    else:
                                        old_nbrs = {
                                            e[1]
                                            for e in prev_rows
                                            if e[0] == owner
                                        } | {
                                            e[0]
                                            for e in prev_rows
                                            if e[1] == owner
                                        }
                                        new_nbrs = {
                                            e[1] for e in fresh if e[0] == owner
                                        } | {
                                            e[0] for e in fresh if e[1] == owner
                                        }
                                    if old_cell != new_cell or len(old_nbrs) != len(
                                        new_nbrs
                                    ):
                                        raise RuntimeError(_err)
                                    row_sizes[owner] = degree_of(owner)
                                else:
                                    raise RuntimeError(_err)
                            else:
                                raise RuntimeError(_err)
                # br-r37-c1-u5tyh: NO RAISE MEANS NETWORKX CARRIES ON — and it
                # carries on out of the row dicts it captured, which are the
                # graph's OWN dicts, so everything it has not reached yet
                # reflects the mutation.
                if emitted is None or refresh_rows is None:
                    return None
                if not (owner is None or owner in graph):
                    return None
                if fresh is None:
                    fresh = refresh_rows()
                if fresh is None:
                    return None
                resume_at = emitted
                if (
                    prev_rows is not None
                    and owner is not None
                    and nbr is not None
                ):
                    first_idx = next(
                        (
                            i
                            for i, e in enumerate(fresh)
                            if e[0] == owner and e[1] == nbr
                        ),
                        None,
                    )
                    if first_idx is not None:
                        k_done = sum(
                            1
                            for e in prev_rows[:emitted]
                            if e[0] == owner and e[1] == nbr
                        )
                        resume_at = first_idx + k_done
                current_rows = fresh
                if at_end and resume_at >= len(fresh):
                    return None
                return fresh[resume_at:]

            # br-r37-c1-ounhu: an exact graph class reads its revisions
            # natively; its per-item check is two integer compares instead of
            # two PyO3 getters.
            native = _fnx._guarded_edge_iter(graph, it, base_nodes, base_edges, _row_move)
            if native is not None:
                return native

            def _gen_rows():
                exp_nodes = base_nodes
                exp_edges = base_edges
                # The row networkx is standing in is the one owning the item it
                # JUST yielded, not the next one - a mutation lands between two
                # `next()` calls, and CPython's dict iterator reports it on the
                # following step even when that step is the one that would end
                # the row. Checking the NEXT item's owner therefore misses a
                # change to a row whose last item has already been handed out,
                # which is exactly the MultiDiGraph case: out-edges only, so
                # nbunch[0] contributes one item and the next belongs to
                # nbunch[1].
                previous = None
                # br-r37-c1-u5tyh: the position is NOT tracked per item. An
                # `emitted += 1` in this loop measured 5% on every nbunch
                # edges() row — the loop runs once per edge, and the header
                # comment above already records that adding one `item[0]` here
                # cost 2x. A list iterator knows how many items it has left, so
                # the count is reconstructed at TRIGGER time from the length
                # hint and costs nothing until a mutation lands. `_length_hint`
                # returns -1 for an iterator that cannot say, and that
                # disables the rebuild rather than guessing a splice point.
                source = it
                source_len = _length_hint(source, -1)
                offset = 0
                while source is not None:
                    restart = None
                    for item in source:
                        if graph.nodes_seq != exp_nodes or (
                            exp_edges is not None and graph.edges_seq != exp_edges
                        ):
                            # Only now is it worth asking WHICH row we are in.
                            # Doing `item[0]` per element instead cost 2x on this
                            # loop - the guard runs once per edge, so the
                            # untriggered path must stay two integer compares and
                            # one store.
                            exp_nodes = graph.nodes_seq
                            if exp_edges is not None:
                                exp_edges = graph.edges_seq
                            # `item` has been taken from `source` and NOT yet
                            # yielded, so the hint counts one fewer than the
                            # items still owed.
                            left = _length_hint(source, -1) if source_len >= 0 else -1
                            emitted = offset + source_len - left - 1 if left >= 0 else None
                            tail = _row_move(previous, emitted, False)
                            if tail is not None:
                                restart = iter(tail)
                                source_len = len(tail)
                                offset = emitted
                                break
                        previous = item
                        yield item
                    if restart is None and (
                        graph.nodes_seq != exp_nodes
                        or (exp_edges is not None and graph.edges_seq != exp_edges)
                    ):
                        exp_nodes = graph.nodes_seq
                        if exp_edges is not None:
                            exp_edges = graph.edges_seq
                        emitted = offset + (source_len if source_len >= 0 else 0)
                        tail = _row_move(previous, emitted, True)
                        if tail is not None:
                            restart = iter(tail)
                            source_len = len(tail)
                            offset = emitted
                    source = restart

            return _gen_rows()

    if use_seq_guard:
        exp_nodes_seq = graph.nodes_seq
        exp_edges_seq = graph.edges_seq if guard_edge_count else None
        native = _fnx._guarded_edge_iter(graph, it, exp_nodes_seq, exp_edges_seq)
        if native is not None:
            return native

        def _gen():
            if exp_edges_seq is None:
                for item in it:
                    if graph.nodes_seq != exp_nodes_seq:
                        raise RuntimeError(_err)
                    yield item
            else:
                for item in it:
                    if (
                        graph.nodes_seq != exp_nodes_seq
                        or graph.edges_seq != exp_edges_seq
                    ):
                        raise RuntimeError(_err)
                    yield item
    else:
        exp_node_count = len(graph)
        exp_edge_count = graph.number_of_edges() if guard_edge_count else None

        def _gen():
            if exp_edge_count is None:
                for item in it:
                    if len(graph) != exp_node_count:
                        raise RuntimeError(_err)
                    yield item
            else:
                for item in it:
                    if (
                        len(graph) != exp_node_count
                        or graph.number_of_edges() != exp_edge_count
                    ):
                        raise RuntimeError(_err)
                    yield item

    return _gen()


# br-r37-c1-degtok: local sentinel. `_PRIVATE_MISSING` is defined far below
# this function, and a default argument is evaluated at DEF time, not call
# time -- using it here is an import-time NameError.
_FRESHNESS_SEQ_UNSET = object()


def _edge_list_freshness_token(graph, nodes_seq=_FRESHNESS_SEQ_UNSET):
    """br-r37-c1-af0ig: O(1) token that changes on any STRUCTURAL mutation.

    ``nodes_seq`` / ``edges_seq`` are monotonic revision counters, so they
    catch a mutation that leaves both counts unchanged — removing an edge and
    adding another one is exactly the case a count-only check would miss, and
    it is the case in this bead's repro. Counts are only the fallback, for
    graphs that do not carry the counters (nx private storage / foreign
    graph objects).

    Returns None when no token can be computed, which callers treat as
    "cannot tell" and therefore never refresh — the pre-existing snapshot
    behaviour, rather than a wrong guess.
    """
    # br-r37-c1-degtok: `nodes_seq` may be passed in by a caller that has just
    # read it -- each read is a PyO3 crossing, and `_FilteredDegreeView.__init__`
    # reads it for `_fnx_nodes_seq` immediately before asking for a token.
    # A dedicated sentinel distinguishes "not
    # supplied" from a genuine None, which means "this graph has no counter".
    storage = graph.__dict__
    if not (
        _PRIVATE_NODE_OVERRIDE in storage
        or _PRIVATE_ADJ_OVERRIDE in storage
        or _PRIVATE_SUCC_OVERRIDE in storage
        or _PRIVATE_PRED_OVERRIDE in storage
    ):
        if nodes_seq is _FRESHNESS_SEQ_UNSET:
            nodes_seq = getattr(graph, "nodes_seq", None)
        if nodes_seq is not None:
            edges_seq = getattr(graph, "edges_seq", None)
            if edges_seq is not None:
                return (nodes_seq, edges_seq)
    try:
        return (len(graph), graph.number_of_edges())
    except Exception:  # noqa: BLE001 - a graph-like without either is not our problem
        return None


def _edge_attr_freshness_token(graph):
    storage = getattr(graph, "__dict__", None)
    if (
        storage is not None
        and type(graph) in (Graph, DiGraph, MultiGraph, MultiDiGraph)
        and not (
            _PRIVATE_NODE_OVERRIDE in storage
            or _PRIVATE_ADJ_OVERRIDE in storage
            or _PRIVATE_SUCC_OVERRIDE in storage
            or _PRIVATE_PRED_OVERRIDE in storage
        )
    ):
        try:
            return _fnx.edge_attr_epoch(graph)
        except Exception:  # noqa: BLE001
            return None
    return None


# br-r37-c1-aq6jv: nbunch sizes at or below this walk the cached rows in
# Python instead of calling the native kernel. MEASURED crossover, not a guess
# — py-walk/native was 0.693x at nbunch=1, 0.981x at 8 and 1.105x at 16, so the
# Python walk stopped paying at 8. (The first guess of 32 was 1.219x, i.e. 22%
# SLOWER than the kernel it replaced.)
#
# br-r37-c1-yjy9i: DO NOT set this to 0 for performance. The kernel is now
# faster at EVERY nbunch size (py-walk/kernel 1.422x at 1 up to 2.222x at 128,
# measured after br-r37-c1-y603y made the kernel O(rows)), so on pure timing
# this threshold looks backwards — but it is also what makes small-nbunch
# iteration LAZY, and that is what keeps fnx from over-raising during mutation.
# Setting it to 0 was tried and resurrected the br-r37-c1-u5tyh over-raise on
# BOTH Graph and DiGraph: `for e in G.edges(['a','b']): G.add_edge(...)` went
# from completing (matching networkx) to RuntimeError. The kernel returns a
# materialised list that the fail-fast guard then polices; the Python walk
# iterates cached rows lazily, which reproduces networkx's semantics for free.
# Raising the threshold is therefore a CORRECTNESS lever before it is a
# performance one — see br-r37-c1-u5tyh.
_EDGES_NBUNCH_PY_WALK_MAX = 8

# br-r37-c1-aq6jv: the threshold above is a FLOOR, not the whole rule, because
# the native kernel it guards is O(graph order) while the Python walk is
# O(nbunch). Measured, list(G.edges(nbunch)) in us, walk/kernel below 1.0 meaning
# the Python walk is faster:
#
#     N        k=4     k=8     k=16    k=32
#     2000     1.149   1.564   1.846   2.046     kernel wins everywhere
#     8000     0.603   0.865   1.209   1.489     walk wins to k=8
#     32000    0.256   0.358   0.688   0.900     walk wins everywhere tested
#
# So the crossover MOVES WITH N, and a fixed 8 is only right near N=2000 — which
# is where it was tuned. networkx is flat at ~8us for a 10-node nbunch at every
# N; fnx went 8.5us at N=500 to 36.6us at N=32000 on the same call, i.e. 0.935x
# down to 0.217x. Scaling the limit with the graph's order tracks the crossover.
#
# ONE PER 1000 NODES fits the three measured crossings (N=2000 -> 3, N=8000 -> 9,
# N=32000 -> 33) and stays under them, so the walk is taken only where it was
# measured to win.
#
# THE DIRECTION IS CORRECTNESS-SAFE, which is why it is expressed as max(). The
# note above records that LOWERING this to 0 resurrects the br-r37-c1-u5tyh
# over-raise on Graph and DiGraph, because the Python walk is what reproduces
# networkx's mutate-during-iteration semantics. Raising it can only route MORE
# calls onto the walk, i.e. onto the more nx-faithful path.
# br-r37-c1-8qxi9 RETUNED this from 1000 to 250. Batching the per-node row
# resolution (one graph-level preamble for the whole nbunch instead of one per
# node) made the walk ~1.7x cheaper, which moved the crossover a long way out.
# Re-measured walk/kernel, below 1.0 meaning the walk is faster:
#
#     N         k=4     k=8    k=16    k=32    k=64   k=128
#     2000    0.767   1.002   1.283   1.111   1.152   1.292   crossover ~8
#     8000    0.446   0.560   0.756   0.814   1.009   1.073   crossover ~64
#     32000   0.192   0.252   0.348   0.468   0.721   0.818   walk wins to 128
#     128000  0.055   0.082   0.115   0.188   0.301   0.447   walk wins to 128
#
# One per 250 nodes gives 8 / 32 / 128 / 512 at those sizes, which stays at or
# under every measured crossing (the 512 at N=128000 extrapolates past the
# largest nbunch measured, k=128, where the walk was still winning by 2.2x).
_EDGES_NBUNCH_PY_WALK_NODES_PER_EXTRA = 250


def _edges_nbunch_py_walk_limit(graph):
    """Largest nbunch that should take the Python walk on this graph.

    br-r37-c1-hihrf: I RETIRED THE ORDER-SCALED TERM HERE AND PUT IT BACK. The
    perf half of my reasoning holds and the correctness half did not, so the
    finding is recorded rather than the change kept.

    What is true: the note above justifies the scaling with "the native kernel it
    guards is O(graph order) while the Python walk is O(nbunch)", and that premise
    is STALE. Re-measured on ELF 85f4c2bd with both paths FORCED at the same size,
    list(G.edges(nbunch)) in microseconds:

        N       nbunch    python    native    py/native
        2000        50     32.34     15.56       2.08x
        8000        50     33.39     15.69       2.13x
        16000       50     32.77     15.71       2.09x
        32000       50     32.91     16.00       2.06x
        32000      200    116.79     49.18       2.37x

    The native column is FLAT across a 16x range in N, where the old table's
    kernel column grew with N. So on perf grounds alone the scaling now routes
    work to the slower path, and a 50-node nbunch steps from 1.83x of networkx at
    N=8000 to 0.87x at N=16000 as order // 250 crosses 50.

    Why it stays anyway: the walk is not merely a faster path for small nbunch,
    it is the NX-FAITHFUL one. Returning the fixed floor failed
    test_mutation_during_iteration_still_matches_networkx at nbunch 9 and 16 -
    the br-r37-c1-u5tyh semantics the note above warns about. Parity outranks a
    2x, so the gate keeps buying it.

    The real fix is to make the NATIVE kernel reproduce networkx's
    mutate-during-iteration behaviour; then this gate can drop to the floor and
    take the 2x everywhere. Until then the scaling is load-bearing for
    correctness, not tuning. See br-r37-c1-hihrf.
    """
    try:
        order = graph.number_of_nodes()
    except Exception:  # noqa: BLE001 - any odd graph keeps the fixed floor
        return _EDGES_NBUNCH_PY_WALK_MAX
    return max(
        _EDGES_NBUNCH_PY_WALK_MAX, order // _EDGES_NBUNCH_PY_WALK_NODES_PER_EXTRA
    )


def _guarded_edge_list(result, graph, *, guard_edge_count=False, nbunch_rows=None):
    if not isinstance(result, _EdgeListWithSetAlgebra):
        result = _EdgeListWithSetAlgebra(result)
    result._fnx_guard_graph = graph
    result._fnx_guard_edge_count = guard_edge_count
    # br-r37-c1-hihrf: the nbunch this view was called with, so iteration can
    # apply networkx's row rule instead of the coarse "anything changed" one.
    #
    # MATERIALISED, because callers pass `graph.nbunch_iter(...)`, which is a
    # one-shot generator. Stored as-is it was consumed by the FIRST iteration and
    # every later one saw an empty snapshot and silently stopped guarding - the
    # view kept its rule for one pass and lost it thereafter. A view is iterated
    # more than once by design, so that is a real hole rather than a slow path.
    result._fnx_nbunch_rows = None if nbunch_rows is None else tuple(nbunch_rows)
    # br-r37-c1-af0ig: stamp the graph revision this snapshot was taken at, so
    # a later read can tell whether it is still current. The rebuild thunk is
    # attached separately by _live_called_edge_view, which is the only place
    # that knows the arguments the view was called with.
    result._fnx_token = _edge_list_freshness_token(graph)
    return result


def _primitive_nbunch_cache_key(graph, nbunch):
    if not isinstance(nbunch, (list, tuple)):
        return None
    nbunch_key = tuple(nbunch)
    if not all(type(node) in (int, str) for node in nbunch_key):
        return None
    return (graph.nodes_seq, graph.edges_seq, nbunch_key)


def _nbunch_data_cache(graph, slot, nbunch, native, *native_args):
    """Slot-parameterised form of the two helpers below (br-r37-c1-mgednb).

    The directed pair each own one hard-coded attribute because each class has
    exactly one nbunch edge-view; other views get their own slot, so two
    spellings on one graph do not evict each other on every alternation.

    The cached tuple holds the SAME live attr-dict objects the native returned,
    and a fresh ``list`` is handed out per call, so nx's live-view semantics are
    preserved and no caller can mutate another caller's result. Only rows of
    live dicts or no data may be memoized here: a ``data=<key>`` row holds a
    VALUE, and an attribute write moves neither seq, so a remembered value goes
    stale (br-r37-c1-p1tyz - every data=<key> view here answered the old weight).
    """
    key = _primitive_nbunch_cache_key(graph, nbunch)
    if key is not None and native_args:
        key = (*key, *native_args)
    if key is not None:
        cached = getattr(graph, slot, None)
        if cached is not None and cached[0] == key:
            return list(cached[1])
    result = native(nbunch, *native_args)
    if result is not None and key is not None:
        setattr(graph, slot, (key, tuple(result)))
    return result


def _digraph_out_edges_data_cache(graph, nbunch, native, *native_args):
    key = _primitive_nbunch_cache_key(graph, nbunch)
    if key is not None and native_args:
        key = (*key, *native_args)
    if key is not None:
        cached = getattr(graph, "_fnx_out_edges_nbunch_data_cache", None)
        if cached is not None and cached[0] == key:
            return list(cached[1])
    result = native(nbunch, *native_args)
    if result is not None and key is not None:
        graph._fnx_out_edges_nbunch_data_cache = (key, tuple(result))
    return result


def _digraph_in_edges_data_cache(graph, nbunch, native, *native_args):
    # br in_edges nbunch-data cache: pred-major mirror of
    # _digraph_out_edges_data_cache. in_edges(nbunch, data=True) had NO cache while
    # out_edges did, so the directed pair diverged (in 0.68x vs out ~7x on the
    # repeated-view pattern). Same last-(nbunch, result) memo keyed on
    # (nodes_seq, edges_seq, nbunch) — any structural mutation invalidates it, and
    # the cached tuple holds the SAME live attr-dict objects the native returns, so
    # post-capture attr mutations stay reflected (nx EdgeDataView live semantics).
    key = _primitive_nbunch_cache_key(graph, nbunch)
    if key is not None and native_args:
        key = (*key, *native_args)
    if key is not None:
        cached = getattr(graph, "_fnx_in_edges_nbunch_data_cache", None)
        if cached is not None and cached[0] == key:
            return list(cached[1])
    result = native(nbunch, *native_args)
    if result is not None and key is not None:
        graph._fnx_in_edges_nbunch_data_cache = (key, tuple(result))
    return result


# br-r37-c1-ex1s6: networkx's edge-view membership (reportviews.py), one row
# lookup each. fnx's views answered from a materialised list or a scan of
# one: a malformed probe - (0,), 5, (0, [1]), (u, v, {}) - was False where
# networkx's unpacking or dict lookup raises, a multigraph pair without a key
# meant "any key" where networkx means key 0, and in_edges membership walked
# every edge. Only a KeyError (a node or neighbour that is not there) answers
# False; anything else raises what networkx raises. `kind` is "out" (the row
# is succ[u]), "in" (pred[v], the edge still reported as (u, v)) or
# "undirected" (adj).
def _nx_edge_view_contains(adj, e, kind, multi):
    """OutEdgeView / InEdgeView / EdgeView and the multigraph edge views."""
    if multi:
        n = len(e)
        if n == 3:
            u, v, k = e
        elif n == 2:
            u, v = e
            k = 0
        else:
            raise ValueError("MultiEdge must have length 2 or 3")
        try:
            return k in (adj[v][u] if kind == "in" else adj[u][v])
        except KeyError:
            return False
    if kind == "undirected":
        try:
            u, v = e[:2]
            return v in adj[u] or u in adj[v]
        except (KeyError, ValueError):
            return False
    try:
        u, v = e
        return u in adj[v] if kind == "in" else v in adj[u]
    except KeyError:
        return False
