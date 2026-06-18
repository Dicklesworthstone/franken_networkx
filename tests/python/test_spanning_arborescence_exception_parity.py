"""Parity for spanning-arborescence no-result exception type.

When no spanning arborescence exists, networkx raises the *base*
``NetworkXException`` (not the ``NetworkXError`` subclass). The native
fnx binding raised ``NetworkXError``; the wrappers now re-raise the base
class so the exact exception type matches nx. br-r37-c1-6f4uj
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx


@pytest.mark.parametrize(
    "fn", ["minimum_spanning_arborescence", "maximum_spanning_arborescence"]
)
def test_no_arborescence_raises_base_networkx_exception(fn):
    # Disconnected digraph: no spanning arborescence exists.
    fg = fnx.DiGraph([(0, 1), (2, 3)])
    ng = nx.DiGraph([(0, 1), (2, 3)])

    with pytest.raises(nx.NetworkXException) as fnx_exc:
        getattr(fnx, fn)(fg)
    with pytest.raises(nx.NetworkXException) as nx_exc:
        getattr(nx, fn)(ng)

    assert str(fnx_exc.value) == str(nx_exc.value)
    # Exact type parity: nx raises the BASE class, not the NetworkXError subclass.
    assert type(fnx_exc.value) is type(nx_exc.value) is nx.NetworkXException


@pytest.mark.parametrize(
    "fn", ["minimum_spanning_arborescence", "maximum_spanning_arborescence"]
)
def test_valid_arborescence_unaffected(fn):
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for g in (fg, ng):
        g.add_edge(0, 1, weight=1)
        g.add_edge(0, 2, weight=5)
        g.add_edge(1, 2, weight=2)
    fr = getattr(fnx, fn)(fg)
    nr = getattr(nx, fn)(ng)
    fw = sum(d["weight"] for _, _, d in fr.edges(data=True))
    nw = sum(d["weight"] for _, _, d in nr.edges(data=True))
    assert fw == nw
