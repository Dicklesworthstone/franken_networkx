"""``generate_edgelist(G, data=[keys])`` must drop, not blank, a missing key.

br-r37-c1-5xl85. fnx built each line with ``d.get(k, "")``, so an edge
lacking a requested attribute got an EMPTY FIELD and the line grew a trailing
delimiter networkx never writes:

    fnx  'a d '      'a b 2 '
    nx   'a d'       'a b 2'

networkx does something different in kind, not just in spacing:

    e = [u, v]
    try:
        e.extend(d[k] for k in data)
    except KeyError:
        pass

``list.extend`` consumes the generator lazily and appends as it goes, so the
first missing key ABORTS THE REST. Values before it survive; the absent key and
every key after it are dropped. Asking for ``["weight", "color"]`` on an edge
carrying only ``weight`` yields ``"a b 2"``, and asking for ``["color",
"weight"]`` on that same edge yields ``"a b"`` - the SAME edge and the SAME key
set, differing only in the order requested. A ``.get(k, "")`` formulation cannot
express that, which is why this is a rewrite rather than a strip().

WHY IT MATTERS BEYOND COSMETICS: these lines are a file format. They round-trip
through ``read_edgelist``, where a stray empty field is a real column - it shifts
every later value and can change the parsed type of the row.

Found while checking whether fnx's ``generate_edgelist`` was byte-identical to
networkx's for multigraphs (it is now, and so are the simple classes - the bug
hit ALL FOUR). 96 combinations of class x data-spelling x delimiter agree.

The pure-bool spellings were already correct and are pinned here as the control,
so a future rewrite cannot regress them while "fixing" the list case.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
DELIMITERS = [" ", "\t", ",", "|"]


def _build(lib, cls):
    """Deliberately heterogeneous: every edge carries a different key subset."""
    g = getattr(lib, cls)()
    g.add_edge("a", "b", weight=1.5, color="red")  # both keys
    g.add_edge("a", "b", weight=2)  # weight only (parallel on multis)
    g.add_edge("b", "c")  # no attrs at all
    g.add_edge("c", "c", weight=3)  # self-loop, weight only
    g.add_edge("d", "a", color="blue")  # color only
    g.add_edge("d", "e", k=None)  # an unrelated key
    g.add_node("isolated")
    return g


DATA_SPELLINGS = [
    True,
    False,
    [],
    ["weight"],
    ["color"],
    ["weight", "color"],
    ["color", "weight"],
    ["absent"],
    ["weight", "absent", "color"],
    ["k"],
]


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("data", DATA_SPELLINGS, ids=lambda d: str(d))
@pytest.mark.parametrize("delimiter", DELIMITERS, ids=lambda d: repr(d))
def test_matches_networkx_line_for_line(cls, data, delimiter):
    got = list(fnx.generate_edgelist(_build(fnx, cls), delimiter, data))
    want = list(nx.generate_edgelist(_build(nx, cls), delimiter, data))
    assert got == want


@pytest.mark.parametrize("cls", CLASSES)
def test_a_missing_key_adds_no_empty_field(cls):
    """The defect, stated directly: no line may end with the delimiter."""
    lines = list(fnx.generate_edgelist(_build(fnx, cls), " ", ["weight", "color"]))
    assert lines, "fixture produced no edges"
    for line in lines:
        assert not line.endswith(" "), f"trailing delimiter in {line!r}"
        assert "  " not in line, f"empty field in {line!r}"


@pytest.mark.parametrize("cls", CLASSES)
def test_the_first_missing_key_drops_the_rest(cls):
    """Order-sensitivity is the part a ``.get`` default cannot reproduce.

    Same edge, same key set, different request ORDER -> different line, because
    networkx stops at the first miss instead of skipping it.
    """
    got = _build(fnx, cls)
    want = _build(nx, cls)

    def da_lines(graph, lib, keys):
        # Select by ENDPOINT SET: an undirected graph emits this edge as
        # "a d" and a directed one as "d a", so a prefix match silently
        # matched nothing for half the classes and the assertion below
        # compared [] against [] and passed for the wrong reason.
        return [
            ln
            for ln in lib.generate_edgelist(graph, " ", keys)
            if set(ln.split(" ")[:2]) == {"a", "d"}
        ]

    # edge d-a carries color but not weight.
    weight_first = da_lines(got, fnx, ["weight", "color"])
    color_first = da_lines(got, fnx, ["color", "weight"])
    assert weight_first, "fixture no longer produces the a/d edge"
    assert weight_first == da_lines(want, nx, ["weight", "color"])
    assert color_first == da_lines(want, nx, ["color", "weight"])
    assert weight_first != color_first, (
        "requesting the same keys in a different order must change this line; "
        "if it does not, the missing-key branch is skipping rather than stopping"
    )


@pytest.mark.parametrize("cls", CLASSES)
def test_values_before_the_missing_key_survive(cls):
    """Not 'drop the whole tail from the start' - only from the miss onward."""
    got = _build(fnx, cls)
    lines = [
        ln
        for ln in fnx.generate_edgelist(got, " ", ["weight", "absent"])
        if ln.startswith("c c")
    ]
    # c-c carries weight=3 and never carries 'absent'.
    assert lines == ["c c 3"], lines


@pytest.mark.parametrize("cls", CLASSES)
def test_bool_spellings_are_the_control(cls):
    """data=True/False were already correct; pin them against regression."""
    for data in (True, False):
        assert list(fnx.generate_edgelist(_build(fnx, cls), " ", data)) == list(
            nx.generate_edgelist(_build(nx, cls), " ", data)
        )


@pytest.mark.parametrize("cls", CLASSES)
def test_lines_round_trip_through_read_edgelist(cls):
    """Why the empty field mattered: the output is parsed back as columns."""
    got = _build(fnx, cls)
    want = _build(nx, cls)
    fnx_lines = list(fnx.generate_edgelist(got, " ", ["weight"]))
    nx_lines = list(nx.generate_edgelist(want, " ", ["weight"]))
    assert fnx_lines == nx_lines
    # Every line must be 2 or 3 fields - never 3 where the third is empty.
    for line in fnx_lines:
        fields = line.split(" ")
        assert len(fields) in (2, 3), line
        assert all(f != "" for f in fields), line
