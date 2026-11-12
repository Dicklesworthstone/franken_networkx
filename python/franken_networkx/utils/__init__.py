"""Re-export of ``networkx.utils`` for drop-in import-path compatibility.

br-r37-c1-hnv5y: prior to this stub, ``import franken_networkx.utils``
failed with ImportError even though ``franken_networkx.utils.X`` worked
via the package-level ``__getattr__`` fallback (used in
test_random_sequence_parity for ``fnx.utils.discrete_sequence``).

Star-imports the public surface from ``networkx.utils`` and falls
through to the source package for nested submodules
(``decorators``, ``misc``, ``random_sequence``, ``rcm``, ``union_find``,
``mapped_queue``, etc.) that the star-import doesn't auto-pull.
"""

import bz2 as _bz2
import collections as _collections
from collections import defaultdict as _defaultdict, deque as _deque
from collections.abc import Iterable as _Iterable, Iterator as _Iterator, Sized as _Sized
import gzip as _gzip
import inspect as _inspect
from itertools import chain as _chain, tee as _tee, zip_longest as _zip_longest
import math as _math
import numbers as _numbers
from os.path import splitext as _splitext
from pathlib import Path as _Path
import random as _random
import re as _re
import sys as _sys
import uuid as _uuid

import networkx.utils as _nx_utils
from networkx.utils import *  # noqa: F401, F403

__all__ = list(
    getattr(_nx_utils, "__all__", ())
    or [name for name in dir(_nx_utils) if not name.startswith("_")]
)


def _nx_error(msg):
    import franken_networkx as _fnx

    return _fnx.NetworkXError(msg)


def _nx_not_implemented(msg):
    import franken_networkx as _fnx

    return _fnx.NetworkXNotImplemented(msg)


class argmap:
    """A decorator to apply a map to arguments before calling the function."""

    def __init__(self, func, *args, try_finally=False):
        self._func = func
        self._args = args
        self._finally = try_finally

    @staticmethod
    def _lazy_compile(func):
        real_func = func.__argmap__.compile(func.__wrapped__)
        func.__code__ = real_func.__code__
        func.__globals__.update(real_func.__globals__)
        func.__dict__.update(real_func.__dict__)
        return func

    def __call__(self, f):
        def func(*args, __wrapper=None, **kwargs):
            return argmap._lazy_compile(__wrapper)(*args, **kwargs)

        func.__name__ = f.__name__
        func.__doc__ = f.__doc__
        func.__defaults__ = f.__defaults__
        func.__kwdefaults__.update(f.__kwdefaults__ or {})
        func.__module__ = f.__module__
        func.__qualname__ = f.__qualname__
        func.__dict__.update(f.__dict__)
        func.__wrapped__ = f

        func.__kwdefaults__["_argmap__wrapper"] = func
        func.__self__ = func
        func.__argmap__ = self

        if hasattr(f, "__argmap__"):
            func.__is_generator = f.__is_generator
        else:
            func.__is_generator = _inspect.isgeneratorfunction(f)

        if self._finally and func.__is_generator:
            raise _nx_error("argmap cannot decorate generators with try_finally")

        return func

    __count = 0

    @classmethod
    def _count(cls):
        cls.__count += 1
        return cls.__count

    _bad_chars = _re.compile("[^a-zA-Z0-9_]")

    @classmethod
    def _name(cls, f):
        f = f.__name__ if hasattr(f, "__name__") else f
        fname = _re.sub(cls._bad_chars, "_", f)
        return f"argmap_{fname}_{cls._count()}"

    def compile(self, f):
        sig, wrapped_name, functions, mapblock, finallys, mutable_args = self.assemble(
            f
        )

        call = f"{sig.call_sig.format(wrapped_name)}#"
        mut_args = f"{sig.args} = list({sig.args})" if mutable_args else ""
        body = argmap._indent(sig.def_sig, mut_args, mapblock, call, finallys)
        code = "\n".join(body)

        locl = {}
        globl = dict(functions.values())
        filename = f"{self.__class__} compilation {self._count()}"
        compiled = compile(code, filename, "exec")
        exec(compiled, globl, locl)
        func = locl[sig.name]
        func._code = code
        return func

    def assemble(self, f):
        if hasattr(f, "__argmap__") and f.__self__ is f:
            (
                sig,
                wrapped_name,
                functions,
                mapblock,
                finallys,
                mutable_args,
            ) = f.__argmap__.assemble(f.__wrapped__)
            functions = dict(functions)
        else:
            sig = self.signature(f)
            wrapped_name = self._name(f)
            mapblock, finallys = [], []
            functions = {id(f): (wrapped_name, f)}
            mutable_args = False

        if id(self._func) in functions:
            fname, _ = functions[id(self._func)]
        else:
            fname, _ = functions[id(self._func)] = self._name(self._func), self._func

        applied = set()

        def get_name(arg, first=True):
            nonlocal mutable_args
            if isinstance(arg, tuple):
                name = ", ".join(get_name(x, False) for x in arg)
                return name if first else f"({name})"
            if arg in applied:
                raise _nx_error(f"argument {arg} is specified multiple times")
            applied.add(arg)
            if arg in sig.names:
                return sig.names[arg]
            elif isinstance(arg, str):
                if sig.kwargs is None:
                    raise _nx_error(
                        f"name {arg} is not a named parameter and this function doesn't have kwargs"
                    )
                return f"{sig.kwargs}[{arg!r}]"
            else:
                if sig.args is None:
                    raise _nx_error(
                        f"index {arg} not a parameter index and this function doesn't have args"
                    )
                mutable_args = True
                return f"{sig.args}[{arg - sig.n_positional}]"

        if self._finally:
            for a in self._args:
                name = get_name(a)
                final = self._name(name)
                mapblock.append(f"{name}, {final} = {fname}({name})")
                mapblock.append("try:")
                finallys = ["finally:", f"{final}()#", "#", finallys]
        else:
            mapblock.extend(
                f"{name} = {fname}({name})" for name in map(get_name, self._args)
            )

        return sig, wrapped_name, functions, mapblock, finallys, mutable_args

    @classmethod
    def signature(cls, f):
        sig = _inspect.signature(f, follow_wrapped=False)
        def_sig = []
        call_sig = []
        names = {}

        kind = None
        args = None
        kwargs = None
        npos = 0
        for i, param in enumerate(sig.parameters.values()):
            prev = kind
            kind = param.kind
            if prev == param.POSITIONAL_ONLY != kind:
                def_sig.append("/")
            if (
                param.VAR_POSITIONAL
                != prev
                != param.KEYWORD_ONLY
                == kind
                != param.VAR_POSITIONAL
            ):
                def_sig.append("*")

            if kind == param.VAR_POSITIONAL:
                name = "*" + param.name
                args = param.name
                count = 0
            elif kind == param.VAR_KEYWORD:
                name = "**" + param.name
                kwargs = param.name
                count = 0
            else:
                names[i] = names[param.name] = param.name
                name = param.name
                count = 1

            if kind == param.KEYWORD_ONLY:
                call_sig.append(f"{name} = {name}")
            else:
                npos += count
                call_sig.append(name)

            def_sig.append(name)

        fname = cls._name(f)
        def_sig = f"def {fname}({', '.join(def_sig)}):"
        call_sig = f"return {{}}({', '.join(call_sig)})"

        return cls.Signature(fname, sig, def_sig, call_sig, names, npos, args, kwargs)

    Signature = _collections.namedtuple(
        "Signature",
        [
            "name",
            "signature",
            "def_sig",
            "call_sig",
            "names",
            "n_positional",
            "args",
            "kwargs",
        ],
    )

    @staticmethod
    def _flatten(nestlist, visited):
        for thing in nestlist:
            if isinstance(thing, list):
                if id(thing) in visited:
                    raise ValueError("A cycle was found in nestlist.  Be a tree.")
                else:
                    visited.add(id(thing))
                yield from argmap._flatten(thing, visited)
            else:
                yield thing

    _tabs = " " * 64

    @staticmethod
    def _indent(*lines):
        depth = 0
        for line in argmap._flatten(lines, set()):
            yield f"{argmap._tabs[:depth]}{line}"
            depth += (line[-1:] == ":") - (line[-1:] == "#")


def not_implemented_for(*graph_types):
    """Decorator to mark algorithms as not implemented."""
    if ("directed" in graph_types) and ("undirected" in graph_types):
        raise ValueError("Function not implemented on directed AND undirected graphs?")
    if ("multigraph" in graph_types) and ("graph" in graph_types):
        raise ValueError("Function not implemented on graph AND multigraphs?")
    if not set(graph_types) < {"directed", "undirected", "multigraph", "graph"}:
        raise KeyError(
            "use one or more of directed, undirected, multigraph, graph.  "
            f"You used {graph_types}"
        )

    dval = ("directed" in graph_types) or "undirected" not in graph_types and None
    mval = ("multigraph" in graph_types) or "graph" not in graph_types and None
    errmsg = f"not implemented for {' '.join(graph_types)} type"

    def _not_implemented_for(g):
        if (mval is None or mval == g.is_multigraph()) and (
            dval is None or dval == g.is_directed()
        ):
            raise _nx_not_implemented(errmsg)

        return g

    return argmap(_not_implemented_for, 0)


_fopeners = {
    ".gz": _gzip.open,
    ".gzip": _gzip.open,
    ".bz2": _bz2.BZ2File,
}
_dispatch_dict = _defaultdict(lambda: open, **_fopeners)


def open_file(path_arg, mode="r"):
    """Decorator to ensure clean opening and closing of files."""

    def _open_file(path):
        if isinstance(path, str):
            ext = _splitext(path)[1]
        elif isinstance(path, _Path):
            ext = path.suffix
            path = str(path)
        else:
            return path, lambda: None

        fobj = _dispatch_dict[ext](path, mode=mode)
        return fobj, lambda: fobj.close()

    return argmap(_open_file, path_arg, try_finally=True)


def nodes_or_number(which_args):
    """Decorator to allow number of nodes or container of nodes."""

    def _nodes_or_number(n):
        try:
            nodes = list(range(n))
        except TypeError:
            nodes = tuple(n)
        else:
            if n < 0:
                raise _nx_error(f"Negative number of nodes not valid: {n}")
        return (n, nodes)

    try:
        iter_wa = iter(which_args)
    except TypeError:
        iter_wa = (which_args,)

    return argmap(_nodes_or_number, *iter_wa)


def flatten(obj, result=None):
    """Return flattened version of (possibly nested) iterable object."""
    if not isinstance(obj, _Iterable | _Sized) or isinstance(obj, str | bytes):
        return obj
    if result is None:
        result = []
    for item in obj:
        if not isinstance(item, _Iterable | _Sized) or isinstance(item, str | bytes):
            result.append(item)
        else:
            flatten(item, result)
    return tuple(result)


def make_list_of_ints(sequence):
    """Return list of ints from sequence of integral numbers."""
    if not isinstance(sequence, _Iterable):
        raise _nx_error(f"sequence is not an iterable : {type(sequence)}")
    result = []
    for i in sequence:
        if not isinstance(i, _numbers.Number):
            raise _nx_error(f"sequence contains non-number: {i}")
        try:
            if int(i) != i:
                raise _nx_error(f"sequence contains non-integral number: {i}")
        except (ValueError, TypeError, OverflowError) as err:
            raise _nx_error(f"sequence contains non-integral number: {i}") from err
        result.append(int(i))
    return result


def dict_to_numpy_array(d, mapping=None):
    """Convert a dictionary of dictionaries to a numpy array."""
    try:
        return _dict_to_numpy_array2(d, mapping)
    except (AttributeError, TypeError):
        return _dict_to_numpy_array1(d, mapping)


def _dict_to_numpy_array2(d, mapping=None):
    import numpy as np

    if mapping is None:
        s = set(d.keys())
        for k, v in d.items():
            s.update(v.keys())
        mapping = dict(zip(s, range(len(s))))
    n = len(mapping)
    a = np.zeros((n, n))
    for k1, i in mapping.items():
        for k2, j in mapping.items():
            try:
                a[i, j] = d[k1][k2]
            except KeyError:
                pass
    return a


def _dict_to_numpy_array1(d, mapping=None):
    import numpy as np

    if mapping is None:
        s = set(d.keys())
        mapping = dict(zip(s, range(len(s))))
    n = len(mapping)
    a = np.zeros(n)
    for k1, i in mapping.items():
        i = mapping[k1]
        a[i] = d[k1]
    return a


def arbitrary_element(iterable):
    """Returns an arbitrary element of `iterable` without removing it."""
    if isinstance(iterable, _Iterator):
        raise ValueError("cannot return an arbitrary item from an iterator")
    return next(iter(iterable))


def pairwise(iterable, cyclic=False):
    """s -> (s0, s1), (s1, s2), (s2, s3), ..."""
    a, b = _tee(iterable)
    first = next(b, None)
    if cyclic is True:
        return zip(a, _chain(b, (first,)))
    return zip(a, b)


def groups(many_to_one):
    """Converts a many-to-one mapping into a one-to-many mapping."""
    one_to_many = _defaultdict(set)
    for v, k in many_to_one.items():
        one_to_many[k].add(v)
    return dict(one_to_many)


def create_random_state(random_state=None):
    """Returns a numpy.random.RandomState or numpy.random.Generator instance."""
    import numpy as np

    if random_state is None or random_state is np.random:
        return np.random.mtrand._rand
    if isinstance(random_state, np.random.RandomState):
        return random_state
    if isinstance(random_state, _numbers.Integral):
        return np.random.RandomState(random_state)
    if isinstance(random_state, np.random.Generator):
        return random_state
    msg = (
        f"{random_state} cannot be used to create a numpy.random.RandomState or\n"
        "numpy.random.Generator instance"
    )
    raise ValueError(msg)


class PythonRandomViaNumpyBits(_random.Random):
    """Provide the random.random algorithms using a numpy.random bit generator."""

    def __init__(self, rng=None):
        import numpy as np

        if rng is None:
            self._rng = np.random.mtrand._rand
        else:
            self._rng = rng
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


class MinHeap:
    """Base class for min-heaps."""

    class _Item:
        __slots__ = ("key", "value")

        def __init__(self, key, value):
            self.key = key
            self.value = value

        def __repr__(self):
            return repr((self.key, self.value))

    def __init__(self):
        self._dict = {}

    def min(self):
        raise NotImplementedError

    def pop(self):
        raise NotImplementedError

    def get(self, key, default=None):
        raise NotImplementedError

    def insert(self, key, value, allow_increase=False):
        raise NotImplementedError

    def __nonzero__(self):
        return bool(self._dict)

    def __bool__(self):
        return bool(self._dict)

    def __len__(self):
        return len(self._dict)

    def __contains__(self, key):
        return key in self._dict


class PairingHeap(MinHeap):
    """A pairing heap."""

    class _Node(MinHeap._Item):
        __slots__ = ("left", "next", "prev", "parent")

        def __init__(self, key, value):
            super().__init__(key, value)
            self.left = None
            self.next = None
            self.prev = None
            self.parent = None

    def __init__(self):
        super().__init__()
        self._root = None

    def min(self):
        if self._root is None:
            raise _nx_error("heap is empty.")
        return (self._root.key, self._root.value)

    def pop(self):
        if self._root is None:
            raise _nx_error("heap is empty.")
        min_node = self._root
        self._root = self._merge_children(self._root)
        del self._dict[min_node.key]
        return (min_node.key, min_node.value)

    def get(self, key, default=None):
        node = self._dict.get(key)
        return node.value if node is not None else default

    def insert(self, key, value, allow_increase=False):
        node = self._dict.get(key)
        root = self._root
        if node is not None:
            if value < node.value:
                node.value = value
                if node is not root and value < node.parent.value:
                    self._cut(node)
                    self._root = self._link(root, node)
                return True
            elif allow_increase and value > node.value:
                node.value = value
                child = self._merge_children(node)
                if child is not None:
                    self._root = self._link(self._root, child)
            return False
        else:
            node = self._Node(key, value)
            self._dict[key] = node
            self._root = self._link(root, node) if root is not None else node
            return True

    def _link(self, root, other):
        if other.value < root.value:
            root, other = other, root
        nxt = root.left
        other.next = nxt
        if nxt is not None:
            nxt.prev = other
        other.prev = None
        root.left = other
        other.parent = root
        return root

    def _merge_children(self, root):
        node = root.left
        root.left = None
        if node is not None:
            link = self._link
            prev = None
            while True:
                nxt = node.next
                if nxt is None:
                    node.prev = prev
                    break
                next_next = nxt.next
                node = link(node, nxt)
                node.prev = prev
                prev = node
                if next_next is None:
                    break
                node = next_next
            prev = node.prev
            while prev is not None:
                prev_prev = prev.prev
                node = link(prev, node)
                prev = prev_prev
            node.prev = None
            node.next = None
            node.parent = None
        return node

    def _cut(self, node):
        prev = node.prev
        nxt = node.next
        if prev is not None:
            prev.next = nxt
        else:
            node.parent.left = nxt
        node.prev = None
        if nxt is not None:
            nxt.prev = prev
            node.next = None
        node.parent = None


class BinaryHeap(MinHeap):
    """A binary heap."""

    def __init__(self):
        from heapq import heappop as _heappop, heappush as _heappush
        from itertools import count as _count

        super().__init__()
        self._heap = []
        self._count = _count()
        self._heappop = _heappop
        self._heappush = _heappush

    def min(self):
        d = self._dict
        if not d:
            raise _nx_error("heap is empty")
        heap = self._heap
        while True:
            value, _, key = heap[0]
            if key in d and value == d[key]:
                break
            self._heappop(heap)
        return (key, value)

    def pop(self):
        d = self._dict
        if not d:
            raise _nx_error("heap is empty")
        heap = self._heap
        while True:
            value, _, key = heap[0]
            self._heappop(heap)
            if key in d and value == d[key]:
                break
        del d[key]
        return (key, value)

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def insert(self, key, value, allow_increase=False):
        d = self._dict
        if key in d:
            old_value = d[key]
            if value < old_value or (allow_increase and value > old_value):
                d[key] = value
                self._heappush(self._heap, (value, next(self._count), key))
                return value < old_value
            return False
        else:
            d[key] = value
            self._heappush(self._heap, (value, next(self._count), key))
            return True


def create_py_random_state(random_state=None):
    """Returns a random.Random instance depending on input."""
    if random_state is None or random_state is _random:
        return _random._inst
    if isinstance(random_state, _random.Random):
        return random_state
    if isinstance(random_state, int):
        return _random.Random(random_state)

    try:
        import numpy as np
    except ImportError:
        pass
    else:
        py_rand_iface = globals()["PythonRandomInterface"]
        if isinstance(random_state, py_rand_iface | PythonRandomViaNumpyBits):
            return random_state
        if isinstance(random_state, np.random.Generator):
            return PythonRandomViaNumpyBits(random_state)
        if random_state is np.random:
            return PythonRandomViaNumpyBits(np.random.mtrand._rand)

        if isinstance(random_state, np.random.RandomState):
            if random_state is np.random.mtrand._rand:
                return PythonRandomViaNumpyBits(random_state)
            return py_rand_iface(random_state)

    msg = f"{random_state} cannot be used to generate a random.Random instance"
    raise ValueError(msg)


def np_random_state(random_state_argument):
    """Decorator to generate a numpy RandomState or Generator instance."""
    return argmap(create_random_state, random_state_argument)


def py_random_state(random_state_argument):
    """Decorator to generate a random.Random instance (or equiv)."""
    return argmap(create_py_random_state, random_state_argument)


def nodes_equal(nodes1, nodes2):
    """Check if nodes are equal."""
    nlist1 = list(nodes1)
    nlist2 = list(nodes2)
    try:
        d1 = dict(nlist1)
        d2 = dict(nlist2)
    except (ValueError, TypeError):
        d1 = dict.fromkeys(nlist1)
        d2 = dict.fromkeys(nlist2)
    return d1 == d2


def edges_equal(edges1, edges2, *, directed=False):
    """Return whether edgelists are equal."""
    d1 = _defaultdict(list)
    d2 = _defaultdict(list)

    for e1, e2 in _zip_longest(edges1, edges2, fillvalue=None):
        if e1 is None or e2 is None:
            return False
        for e, d in [(e1, d1), (e2, d2)]:
            u, v, *data = e
            d[u, v].append(data)
            if not directed:
                d[v, u].append(data)

    return all(d1[e].count(data) == d2[e].count(data) for e in d1 for data in d1[e])


def graphs_equal(graph1, graph2):
    """Check if graphs are equal."""
    return (
        graph1.adj == graph2.adj
        and graph1.nodes == graph2.nodes
        and graph1.graph == graph2.graph
    )


def cuthill_mckee_ordering(G, heuristic=None):
    """Generate an ordering (permutation) of the graph nodes to make a sparse matrix."""
    import franken_networkx as _fnx

    for c in _fnx.connected_components(G):
        yield from _connected_cuthill_mckee_ordering(G.subgraph(c), heuristic)


def reverse_cuthill_mckee_ordering(G, heuristic=None):
    """Generate an ordering (permutation) of the graph nodes to make a sparse matrix."""
    return reversed(list(cuthill_mckee_ordering(G, heuristic=heuristic)))


def _connected_cuthill_mckee_ordering(G, heuristic=None):
    if heuristic is None:

        def heuristic(G):
            return _pseudo_peripheral_node(G)

    visited = set()
    queue = _deque()
    for i in range(len(G)):
        if len(visited) == len(G):
            break
        start = heuristic(G.subgraph(set(G) - visited))
        visited.add(start)
        queue.append(start)
        while queue:
            parent = queue.popleft()
            yield parent
            nd = sorted(
                [(v, d) for v, d in G.degree(set(G[parent]) - visited)],
                key=lambda x: x[1],
            )
            children = [n for n, d in nd]
            visited.update(children)
            queue.extend(children)


def _pseudo_peripheral_node(G):
    u = arbitrary_element(G)
    lp = 0
    v = u
    while True:
        spl = dict(_rcm_breadth_first_search(G, v))
        l = max(spl.values())
        if l <= lp:
            break
        lp = l
        farthest = (n for n, dist in spl.items() if dist == l)
        v, deg = min(G.degree(farthest), key=lambda x: x[1])
    return v


def _rcm_breadth_first_search(G, source):
    G_adj = G.adj
    seen = set()
    nextlevel = {source}
    level = 0
    while nextlevel:
        thislevel = nextlevel
        nextlevel = set()
        for v in thislevel:
            if v not in seen:
                seen.add(v)
                nextlevel.update(G_adj[v])
                yield v, level
        level += 1


@py_random_state(2)
def powerlaw_sequence(n, exponent=2.0, seed=None):
    """Return sample sequence of length n from a power law distribution."""
    return [seed.paretovariate(exponent - 1) for i in range(n)]


def is_valid_tree_degree_sequence(degree_sequence):
    """Check if a degree sequence is valid for a tree."""
    seq = list(degree_sequence)
    number_of_nodes = len(seq)
    twice_number_of_edges = sum(seq)

    if 2 * number_of_nodes - twice_number_of_edges != 2:
        return False, "tree must have one more node than number of edges"
    elif seq != [0] and any(d <= 0 for d in seq):
        return False, "nontrivial tree must have strictly positive node degrees"
    return True, ""


@py_random_state(2)
def zipf_rv(alpha, xmin=1, seed=None):
    """Returns a random value chosen from the Zipf distribution."""
    if xmin < 1:
        raise ValueError("xmin < 1")
    if alpha <= 1:
        raise ValueError("a <= 1.0")
    a1 = alpha - 1.0
    b = 2**a1
    while True:
        u = 1.0 - seed.random()
        v = seed.random()
        x = int(xmin * u ** -(1.0 / a1))
        t = (1.0 + (1.0 / x)) ** a1
        if v * x * (t - 1.0) / (b - 1.0) <= t / b:
            break
    return x


def cumulative_distribution(distribution):
    """Returns normalized cumulative distribution from discrete distribution."""
    cdf = [0.0]
    cumulative = 0.0
    for element in distribution:
        cumulative += element
        cdf.append(cumulative)
    return [element / cumulative for element in cdf]


@py_random_state(3)
def discrete_sequence(n, distribution=None, cdistribution=None, seed=None):
    """Return sample sequence of length n from a given discrete distribution."""
    import bisect

    if cdistribution is not None:
        cdf = cdistribution
    elif distribution is not None:
        cdf = cumulative_distribution(distribution)
    else:
        raise _nx_error(
            "discrete_sequence: distribution or cdistribution missing"
        )

    inputseq = [seed.random() for i in range(n)]
    seq = [bisect.bisect_left(cdf, s) - 1 for s in inputseq]
    return seq


@py_random_state(2)
def random_weighted_sample(mapping, k, seed=None):
    """Returns k items without replacement from a weighted sample."""
    if k > len(mapping):
        raise ValueError("sample larger than population")
    sample = set()
    while len(sample) < k:
        sample.add(weighted_choice(mapping, seed))
    return list(sample)


@py_random_state(1)
def weighted_choice(mapping, seed=None):
    """Returns a single element from a weighted sample."""
    rnd = seed.random() * sum(mapping.values())
    for k, w in mapping.items():
        rnd -= w
        if rnd < 0:
            return k


def _install_utils_child_aliases():
    import importlib
    import pkgutil
    import sys
    import networkx.utils as _src

    for info in pkgutil.iter_modules(_src.__path__):
        name = info.name
        if name == "tests" or name.startswith("_"):
            continue
        alias = f"{__name__}.{name}"
        if alias in sys.modules:
            continue
        module = importlib.import_module(f"networkx.utils.{name}")
        sys.modules[alias] = module
        globals()[name] = module


def __getattr__(name):
    import networkx.utils as _src

    try:
        return getattr(_src, name)
    except AttributeError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc


def __dir__():
    import networkx.utils as _src

    return sorted(set(globals()) | set(dir(_src)))


_install_utils_child_aliases()
