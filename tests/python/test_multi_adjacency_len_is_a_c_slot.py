"""br-r37-c1-m1k0q: len(MultiGraph.adj) must resolve to a native C slot.

`len(G.adj)` was 0.77x networkx on the multigraph classes and 1.36x on the simple
ones -- same operation, same number. The whole difference was that br-r37-c1-5gam7
gave only Graph/DiGraph a `__len__` that is a C slot, by subclassing the native
view so the MRO puts the native slot ahead of the Python function. This is the
multigraph twin.

THIS FILE IS A WIRING GUARD, not a value test. The values are covered elsewhere;
what is fragile here is the ROUTING. A previous `native_len` wiring on these same
four factories was silently dropped when a peer rebuilt them from an older
revision -- nothing failed to import, the binding just stopped arriving and the
fix went inert. A test that asserts where `__len__` comes from catches that; a
test that only checks the number does not.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def _len_owner(view):
    """The class in the MRO that actually supplies __len__."""
    return next(b.__name__ for b in type(view).__mro__ if "__len__" in vars(b))


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_adj_len_comes_from_a_native_class(cls):
    g = getattr(fnx, cls)()
    g.add_edge("a", "b")
    owner = _len_owner(g.adj)
    assert owner.endswith("LenView"), (
        f"len({cls}.adj) resolves to {owner}, not the native C-slot class — the "
        "routing has been dropped and the fix is inert"
    )


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_adj_len_agrees_with_iteration_and_networkx(cls):
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        for i in range(6):
            g.add_edge(f"n{i}", f"n{(i + 1) % 6}")
        g.add_node("iso")
    assert len(gfx.adj) == len(gnx.adj)
    assert len(gfx.adj) == len(list(gfx.adj))
    assert bool(gfx.adj) == bool(gnx.adj)


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_empty_graph_len_and_bool(cls):
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    assert len(gfx.adj) == len(gnx.adj) == 0
    assert bool(gfx.adj) == bool(gnx.adj) is False


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_everything_else_still_comes_from_the_python_class(cls):
    """Only __len__/__bool__ are taken from the native base.

    Inheriting the rest would drop the row cache, the private-storage-aware
    membership and the nx-shaped repr, so this pins that they did not move.
    """
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edge("a", "b")
    assert sorted(map(str, gfx.adj)) == sorted(map(str, gnx.adj))
    assert ("a" in gfx.adj) == ("a" in gnx.adj)
    assert ("nope" in gfx.adj) == ("nope" in gnx.adj)
    assert sorted(map(str, gfx.adj["a"])) == sorted(map(str, gnx.adj["a"]))
    with pytest.raises(KeyError):
        gfx.adj["nope"]
    # the row view is the parity one, not a bare native object
    assert type(gfx.adj["a"]).__name__ == type(gnx.adj["a"]).__name__


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_len_survives_mutation(cls):
    """The handle is live, not a snapshot taken at view construction."""
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edge("a", "b")
    vnx, vfx = gnx.adj, gfx.adj
    for g in (gnx, gfx):
        g.add_edge("c", "d")
        g.add_node("solo")
    assert len(vfx) == len(vnx)
    for g in (gnx, gfx):
        g.remove_node("solo")
    assert len(vfx) == len(vnx)
