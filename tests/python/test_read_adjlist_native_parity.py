"""br-r37-c1-770mm: read_adjlist native fast-path parity vs networkx.

The default-kwargs path (comments="#", delimiter=None, nodetype=None,
encoding="utf-8", create_using=None/Graph) routes through the Rust
``read_adjlist_simple`` single-pass parser. These tests pin its contract
against upstream networkx: node order, edge order, adjacency order, attrs,
error surfaces, and the delegation gates for non-default kwargs.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _canon(g):
    return (
        [(n, dict(a)) for n, a in g.nodes(data=True)],
        [(u, v, dict(d)) for u, v, d in g.edges(data=True)],
        {n: list(g[n]) for n in g},
        dict(g.graph),
    )


def _write(tmp_path, content, name="g.adjlist"):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def test_fast_path_engaged(tmp_path):
    p = _write(tmp_path, "a b c\nb c\n")
    native = fnx._fnx.read_adjlist_simple(p)
    assert native is not None
    assert _canon(fnx.read_adjlist(p)) == _canon(native)


def test_random_corpus_matches_nx(tmp_path):
    rnd = random.Random(20260605)
    for trial in range(25):
        n = rnd.choice([0, 1, 2, 5, 40, 150])
        g = nx.Graph()
        labels = [
            rnd.choice([str(i), f"node_{i}", f"ü{i}"]) for i in range(n)
        ]
        g.add_nodes_from(labels)
        for _ in range(int(n * rnd.uniform(0, 3))):
            g.add_edge(rnd.choice(labels), rnd.choice(labels))
        p = _write(tmp_path, "", name=f"c{trial}.adjlist")
        nx.write_adjlist(g, p)
        assert _canon(fnx.read_adjlist(p)) == _canon(nx.read_adjlist(p)), trial


@pytest.mark.parametrize(
    "content",
    [
        "a\tb\tc\nb\td\n",  # tab separators (delimiter=None whitespace split)
        "a b b c\nb a\nc a\n",  # duplicate edges both directions
        "a a b\nb b\n",  # self-loops
        "a b # rest ignored\nb c#tight\n",  # inline comments
        "# header\n#another\na b\n# mid\nb c\n",  # comment-only lines
        "a\nb\nc a\n",  # isolated nodes
        "a b\nb c",  # no trailing newline
        "a b\r\nb c\r\n",  # CRLF
        "a b c d\nb c d\nc d\nd\n",  # shared targets
        "1 2 3\n2 4\n10 1\n",  # numeric-lookalike string keys
    ],
)
def test_handcrafted_files_match_nx(tmp_path, content):
    p = _write(tmp_path, content)
    assert _canon(fnx.read_adjlist(p)) == _canon(nx.read_adjlist(p))


@pytest.mark.parametrize(
    "content",
    ["a b\n\nc d\n", "a b\n   \nc d\n", "a b\n  # x\nc d\n"],
)
def test_blank_line_error_parity(tmp_path, content):
    """nx raises IndexError('pop from empty list') on blank/ws-only lines;
    the fast path must bail to the delegated parser so the error matches."""
    p = _write(tmp_path, content)
    with pytest.raises(IndexError) as nx_err:
        nx.read_adjlist(p)
    with pytest.raises(IndexError) as fnx_err:
        fnx.read_adjlist(p)
    assert str(fnx_err.value) == str(nx_err.value)


def test_non_default_kwargs_still_delegate(tmp_path):
    p = _write(tmp_path, "1 2 3\n2 4\n")
    assert list(fnx.read_adjlist(p, nodetype=int)) == [1, 2, 3, 4]
    g_di = fnx.read_adjlist(p, create_using=fnx.DiGraph)
    assert g_di.is_directed()
    assert list(g_di.edges()) == [("1", "2"), ("1", "3"), ("2", "4")]
    g_cu = fnx.read_adjlist(p, create_using=fnx.Graph)
    assert type(g_cu) is fnx.Graph
    assert _canon(g_cu) == _canon(fnx.read_adjlist(p))
    assert list(fnx.read_adjlist(p, delimiter=" ")) == list(
        nx.read_adjlist(p, delimiter=" ")
    )


def test_fast_path_graph_is_mutable_and_copyable(tmp_path):
    p = _write(tmp_path, "a b c\nb c\n")
    g = fnx.read_adjlist(p)
    g["a"]["b"]["w"] = 3
    assert g["b"]["a"]["w"] == 3
    g.add_edge("c", "zz")
    g.add_node("solo", color="red")
    assert g.number_of_edges() == 4
    assert "zz" in g
    assert g.nodes["solo"]["color"] == "red"
    cp = g.copy()
    assert list(cp.edges()) == list(g.edges())


def test_missing_file_error_parity(tmp_path):
    missing = str(tmp_path / "nope.adjlist")
    with pytest.raises(Exception) as nx_err:
        nx.read_adjlist(missing)
    with pytest.raises(Exception) as fnx_err:
        fnx.read_adjlist(missing)
    assert type(fnx_err.value) is type(nx_err.value)
