"""Public functions honour the ``backend=`` keyword they declare, like networkx.

br-r37-c1-rc0923-epic-honest-measurement-vbneu.1. 629 public fnx callables
declare networkx's dispatchable surface ``(..., *, backend=None,
**backend_kwargs)`` — most of them through a synthesised ``__signature__``. The
behaviour behind that declaration rejected this library's OWN backend name:
``fnx.pagerank(G, backend="franken_networkx")`` raised "'franken_networkx'
backend is not installed", while ``nx.pagerank(G, backend="franken_networkx")``
runs fnx. Portable code written against networkx's dispatch API broke on fnx.

The sweep below is argument-free, so it only pins what is decidable without
valid inputs: neither backend name that can run here may produce ImportError.
The parametrized cases then pin full behaviour against networkx with real
arguments.
"""

from __future__ import annotations

import inspect

import networkx as nx
import pytest

import franken_networkx as fnx


def _declares_backend(obj):
    try:
        return "backend" in inspect.signature(obj).parameters
    except (TypeError, ValueError):
        return False


DECLARING = sorted(
    name
    for name in fnx.__all__
    if callable(getattr(fnx, name, None))
    and not inspect.isclass(getattr(fnx, name))
    and _declares_backend(getattr(fnx, name))
)


def test_sweep_covers_the_dispatchable_surface():
    # Guard the sweep itself: if discovery breaks it must not pass vacuously.
    assert len(DECLARING) > 500


@pytest.mark.parametrize("backend", ["networkx", "franken_networkx"])
def test_runnable_backend_names_never_raise_import_error(backend):
    offenders = []
    for name in DECLARING:
        try:
            getattr(fnx, name)(backend=backend)
        except ImportError as exc:
            offenders.append(f"{name}: {exc}")
        except Exception:  # missing required arguments etc. are fine here
            pass
    assert not offenders, f"{len(offenders)} functions reject backend={backend!r}: {offenders[:10]}"


def _path():
    return (nx.path_graph(6), fnx.path_graph(6))


CASES = {
    "pagerank": lambda m, G, **kw: m.pagerank(G, **kw),
    "adamic_adar_index": lambda m, G, **kw: list(m.adamic_adar_index(G, [(0, 2), (1, 4)], **kw)),
    "all_pairs_dijkstra_path_length": lambda m, G, **kw: dict(m.all_pairs_dijkstra_path_length(G, **kw)),
    "diameter": lambda m, G, **kw: m.diameter(G, **kw),
    "has_path": lambda m, G, **kw: m.has_path(G, 0, 5, **kw),
    "shortest_path_length": lambda m, G, **kw: m.shortest_path_length(G, 0, 5, **kw),
    "gnp_random_graph": lambda m, G, **kw: sorted(m.gnp_random_graph(12, 0.3, seed=4, **kw).edges()),
    "binomial_graph": lambda m, G, **kw: sorted(m.binomial_graph(12, 0.3, seed=4, **kw).edges()),
}


def _outcome(fn):
    try:
        return ("ok", fn())
    except Exception as exc:
        return ("raised", type(exc).__name__, str(exc))


@pytest.mark.parametrize("name", sorted(CASES))
@pytest.mark.parametrize("backend", [None, "networkx", "franken_networkx"])
def test_runnable_backend_gives_networkx_result(name, backend):
    gnx, gfx = _path()
    call = CASES[name]
    kw = {} if backend is None else {"backend": backend}
    want = call(nx, gnx)  # networkx's own result, no dispatch
    assert _outcome(lambda: call(fnx, gfx, **kw)) == ("ok", want)


@pytest.mark.parametrize("name", sorted(CASES))
def test_unknown_backend_and_unknown_keyword_raise_like_networkx(name):
    gnx, gfx = _path()
    call = CASES[name]
    for kw in ({"backend": "__no_such_backend__"}, {"no_such_keyword": 1}):
        want = _outcome(lambda: call(nx, gnx, **kw))
        got = _outcome(lambda: call(fnx, gfx, **kw))
        assert got[:2] == want[:2], (kw, got, want)
