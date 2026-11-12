"""``G.copy()`` starts with a CLEAN weighted store, and stays correct when written to.

br-r37-c1-igdzi. ``edges(data=True)`` hands out the live edge attr dicts, exactly as
networkx does, so the store conservatively marks itself dirty and every later weighted
read (``size(weight=...)``, ``degree(weight=...)``) takes a slow path -- permanently.
That part is correct and is NOT what this module tests.

What was wrong is that ``copy()`` PROPAGATED that flag. A copy deep-copies every attr
dict, so the dicts it holds were created by the copy and no caller can hold a reference
to one; the flag is a fact about the source's dicts, not the copy's. Propagating it cost
5.4x on every weighted read of every copy, forever. Measured on a 4000-edge graph:
``copy()`` of a contaminated graph went 2352 us (0.801x vs networkx) to 385 us (4.976x),
landing on top of ``subgraph(all).copy()``, which already started clean and is the
control proving a clean start is safe and sufficient.

THE NEGATIVE CASE a naive "just start clean" fails is
``test_copy_redirties_when_it_hands_out_its_own_dict``. Starting clean is only sound
while nobody holds one of the COPY's dicts. The moment the copy hands one out it must
mark itself dirty again, or a write through that dict is invisible and every later
weighted read serves a STALE weight -- trading a perf bug for a silent wrong answer,
which is precisely the objection that sank the earlier "re-sync" proposal on this bead.

``__copy__`` is deliberately NOT included. It is the shallow-copy protocol, networkx
SHARES attr dicts there, and it must keep propagating the flag.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(module, cls_name, n=40):
    graph = getattr(module, cls_name)()
    for i in range(n):
        graph.add_edge(f"n{i}", f"n{i + 1}", weight=float(i))
    return graph


def _attrs(graph, cls_name, u="n0", v="n1"):
    """The live attr dict for one edge, whatever the class's spelling."""
    if cls_name.startswith("Multi"):
        return graph[u][v][0]
    return graph[u][v]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_copy_weighted_reads_match_networkx_after_contamination(cls_name):
    """The whole point: a copy taken after reading edge data still reads correctly."""
    outcomes = {}
    for name, module in (("nx", nx), ("fnx", fnx)):
        graph = _build(module, cls_name)
        list(graph.edges(data=True))  # hands out live dicts; marks fnx's store dirty
        duplicate = graph.copy()
        outcomes[name] = (
            duplicate.size(weight="weight"),
            sorted(dict(duplicate.degree(weight="weight")).items()),
        )
    assert outcomes["fnx"] == outcomes["nx"], (
        f"{cls_name}: weighted reads on a copy taken after edges(data=True) must match "
        f"networkx. networkx gave {outcomes['nx'][0]}, fnx gave {outcomes['fnx'][0]}."
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_write_through_the_source_does_not_reach_the_copy(cls_name):
    """A clean start is only sound because the copy's dicts are its own.

    If ``copy()`` ever shares attr dict objects with its source, starting clean would
    let a write through the source go unseen by the copy's store. This pins the premise
    the fix rests on, against networkx, which makes the same guarantee.
    """
    outcomes = {}
    for name, module in (("nx", nx), ("fnx", fnx)):
        graph = _build(module, cls_name)
        duplicate = graph.copy()
        _attrs(graph, cls_name)["weight"] = 10_000.0
        outcomes[name] = duplicate.size(weight="weight")
    assert outcomes["fnx"] == outcomes["nx"], (
        f"{cls_name}: writing through the SOURCE's attr dict must not change the copy. "
        f"networkx gave {outcomes['nx']}, fnx gave {outcomes['fnx']}."
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_copy_redirties_when_it_hands_out_its_own_dict(cls_name):
    """NEGATIVE CASE. Start clean, then write through a dict the COPY handed out.

    An implementation that starts clean and forgets to re-dirty on handing a dict out
    serves the pre-write weight here. That is a silent wrong answer, strictly worse than
    the slow path this change removes, so it is asserted for every class.
    """
    outcomes = {}
    for name, module in (("nx", nx), ("fnx", fnx)):
        graph = _build(module, cls_name)
        list(graph.edges(data=True))
        duplicate = graph.copy()
        duplicate.size(weight="weight")  # populate/settle any store fast path first
        _attrs(duplicate, cls_name)["weight"] = 10_000.0
        outcomes[name] = duplicate.size(weight="weight")
    assert outcomes["fnx"] == outcomes["nx"], (
        f"{cls_name}: a write through a dict the COPY handed out must be visible to the "
        f"copy's own weighted reads. networkx gave {outcomes['nx']}, fnx gave "
        f"{outcomes['fnx']} -- a stale weight served from a store that started clean and "
        f"did not re-dirty."
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_write_through_edges_data_on_the_copy_is_visible(cls_name):
    """The same negative case via the bulk spelling that causes the contamination."""
    outcomes = {}
    for name, module in (("nx", nx), ("fnx", fnx)):
        graph = _build(module, cls_name)
        duplicate = graph.copy()
        duplicate.size(weight="weight")
        for _u, _v, data in duplicate.edges(data=True):
            data["weight"] = 2.0
        outcomes[name] = duplicate.size(weight="weight")
    assert outcomes["fnx"] == outcomes["nx"], (
        f"{cls_name}: writes made through the copy's own edges(data=True) dicts must be "
        f"visible. networkx gave {outcomes['nx']}, fnx gave {outcomes['fnx']}."
    )
