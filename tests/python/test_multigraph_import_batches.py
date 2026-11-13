"""Table/dictionary imports preserve the public construction contract."""

from collections.abc import Mapping

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.fixture
def pandas():
    return pytest.importorskip("pandas")


def _classes(directed, multigraph=True):
    name = ("Multi" if multigraph else "") + ("DiGraph" if directed else "Graph")
    return getattr(fnx, name), getattr(nx, name)


def _snapshot(graph):
    edges = (
        graph.edges(keys=True, data=True)
        if graph.is_multigraph()
        else ((u, v, None, attrs) for u, v, attrs in graph.edges(data=True))
    )
    return (
        list(graph.nodes(data=True)),
        [(u, v, k, list(attrs.items())) for u, v, k, attrs in edges],
        dict(graph.graph),
    )


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("multigraph", [False, True])
@pytest.mark.parametrize("labels", ["int", "str"])
@pytest.mark.parametrize("key_mode", ["auto", "unique", "gaps", "str", "duplicates", "none"])
@pytest.mark.parametrize("edge_attr", [None, True, "weight", ["weight", "kind"]])
def test_pandas_multigraph_import_matches_networkx(
    pandas, directed, multigraph, labels, key_mode, edge_attr
):
    fnx_cls, nx_cls = _classes(directed, multigraph)
    pairs = [(3, 1), (3, 1), (1, 3), (2, 2)] + [(i, i + 1) for i in range(12)]
    label = str if labels == "str" else int
    frame = pandas.DataFrame(
        {
            "source": [label(u) for u, _ in pairs],
            "target": [label(v) for _, v in pairs],
            "weight": [i + 1 for i in range(len(pairs))],
            "kind": [f"kind-{i % 3}" for i in range(len(pairs))],
        }
    )
    edge_key = None
    if key_mode != "auto":
        edge_key = "edge_id"
        keys = {
            "unique": list(range(len(pairs))),
            "gaps": [2 * i + 7 for i in range(len(pairs))],
            "str": [f"key-{i}" for i in range(len(pairs))],
            "duplicates": [0] * len(pairs),
            "none": [None if i % 2 else i for i in range(len(pairs))],
        }[key_mode]
        frame[edge_key] = pandas.Series(keys, dtype=object)
    options = dict(edge_attr=edge_attr, edge_key=edge_key)
    actual = fnx.from_pandas_edgelist(frame, create_using=fnx_cls, **options)
    expected = nx.from_pandas_edgelist(frame, create_using=nx_cls, **options)
    assert _snapshot(actual) == _snapshot(expected)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("multigraph_input", [False, True])
@pytest.mark.parametrize("labels", ["int", "str", "tuple"])
@pytest.mark.parametrize("key_mode", ["consecutive", "gaps", "str", "none"])
def test_dictionary_multigraph_import_matches_networkx(
    directed, multigraph_input, labels, key_mode
):
    fnx_cls, nx_cls = _classes(directed)
    label = {"int": int, "str": str, "tuple": lambda n: ("node", n)}[labels]
    data = {label(i): {} for i in [5, 0, 3, 1, 2, 4]}
    keys = {
        "consecutive": [0, 1, 2],
        "gaps": [9, 2, 7],
        "str": ["first", "second", "third"],
        "none": [None, 3, 1],
    }[key_mode]
    for i in range(6):
        u, v = label(i), label((i + 1) % 6)
        attrs = {"weight": i + 1, "kind": "forward"}
        data[u][v] = (
            {key: dict(attrs, order=j) for j, key in enumerate(keys)}
            if multigraph_input else attrs
        )
        reverse = {"weight": 100 + i, "kind": "reverse"}
        data[v][u] = (
            {key: dict(reverse, order=j) for j, key in enumerate(keys)}
            if multigraph_input else reverse
        )
    data[label(2)][label(2)] = (
        {0: {"weight": 50}, 1: {"weight": 51}}
        if multigraph_input else {"weight": 50}
    )
    options = dict(multigraph_input=multigraph_input)
    actual = fnx.from_dict_of_dicts(data, create_using=fnx_cls, **options)
    expected = nx.from_dict_of_dicts(data, create_using=nx_cls, **options)
    assert _snapshot(actual) == _snapshot(expected)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize(
    "route",
    ["pandas_auto", "pandas_keyed", "pandas_keyed_no_attrs", "dict_simple", "dict_auto", "dict_keyed"],
)
def test_ordinary_multigraph_import_uses_one_native_batch(pandas, monkeypatch, directed, route):
    fnx_cls, nx_cls = _classes(directed)
    original = fnx_cls._try_add_attr_edges_from_batch
    calls = []

    def track(graph, rows, *args):
        result = original(graph, rows, *args)
        calls.append((len(rows), result is not None))
        return result

    monkeypatch.setattr(fnx_cls, "_try_add_attr_edges_from_batch", track)
    if route.startswith("pandas"):
        frame = pandas.DataFrame(
            {
                "source": [0] * 16, "target": list(range(1, 17)),
                "weight": list(range(16)), "id": [7] * 16,
                "kind": pandas.Series(["road"] * 16, dtype="string"),
            }
        )
        options = {
            "edge_attr": None if route.endswith("no_attrs") else ["weight", "kind"],
            "edge_key": None if route == "pandas_auto" else "id",
        }
        actual = fnx.from_pandas_edgelist(frame, create_using=fnx_cls, **options)
        expected = nx.from_pandas_edgelist(frame, create_using=nx_cls, **options)
    else:
        label = int if route == "dict_keyed" else str
        data = {label(i): {} for i in range(17)}
        for i in range(1, 17):
            attrs = {"weight": i}
            data[label(0)][label(i)] = (
                attrs if route == "dict_simple" else {7 if route == "dict_keyed" else 0: attrs}
            )
        options = {"multigraph_input": route != "dict_simple"}
        actual = fnx.from_dict_of_dicts(data, create_using=fnx_cls, **options)
        expected = nx.from_dict_of_dicts(data, create_using=nx_cls, **options)
    assert _snapshot(actual) == _snapshot(expected)
    assert calls == [(16, True)]


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("route", ["pandas", "dict"])
def test_multigraph_import_keeps_shallow_attribute_references(pandas, directed, route):
    fnx_cls, nx_cls = _classes(directed)
    shared = {"items": []}
    attrs = {"weight": 3, "payload": shared}
    if route == "pandas":
        data = pandas.DataFrame(
            {"source": [0] * 16, "target": list(range(1, 17)), "weight": [3] * 16, "payload": [shared] * 16}
        )
        converter = "from_pandas_edgelist"
        options = {"edge_attr": True}
    else:
        data = {i: {} for i in range(17)}
        data[0] = {i: {0: attrs} for i in range(1, 17)}
        converter = "from_dict_of_dicts"
        options = {"multigraph_input": True}
    actual = getattr(fnx, converter)(data, create_using=fnx_cls, **options)
    expected = getattr(nx, converter)(data, create_using=nx_cls, **options)
    assert _snapshot(actual) == _snapshot(expected)
    for _, _, _, edge_attrs in actual.edges(keys=True, data=True):
        assert edge_attrs is not attrs
        assert edge_attrs["payload"] is shared
    actual.get_edge_data(0, 1, 0)["weight"] = 99
    assert attrs["weight"] == 3
    assert actual.get_edge_data(0, 2, 0)["weight"] == 3
    shared["items"].append("visible")
    assert actual.get_edge_data(0, 16, 0)["payload"]["items"] == ["visible"]


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("route", ["pandas", "dict"])
def test_multigraph_import_reuses_and_clears_existing_graph(pandas, directed, route):
    fnx_cls, nx_cls = _classes(directed)
    outputs = []
    for library, cls in [(fnx, fnx_cls), (nx, nx_cls)]:
        graph = cls()
        graph.add_edge("old", "edge", key="old-key", old=True)
        graph.graph["old"] = True
        if route == "pandas":
            data = pandas.DataFrame({"source": range(16), "target": range(1, 17), "weight": range(16)})
            result = library.from_pandas_edgelist(data, edge_attr=True, create_using=graph)
        else:
            data = {i: {i + 1: {"weight": i}} for i in range(16)}
            result = library.from_dict_of_dicts(data, create_using=graph)
        assert result is graph
        outputs.append(_snapshot(result))
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("multigraph", [False, True])
@pytest.mark.parametrize("edge_key", [None, "id"])
def test_custom_table_iteration_observes_inserted_prefix(directed, multigraph, edge_key):
    fnx_cls, nx_cls = _classes(directed, multigraph)
    outputs = []
    for library, cls in [(fnx, fnx_cls), (nx, nx_cls)]:
        graph = cls()
        observed = []

        def sources():
            for node in range(3):
                observed.append(graph.number_of_edges())
                if node == 2:
                    raise RuntimeError("table stopped")
                yield node

        table = {"source": sources(), "target": [1, 2, 3], "weight": [4, 5, 6], "id": [7, 8, 9]}
        with pytest.raises(RuntimeError, match="table stopped"):
            library.from_pandas_edgelist(table, edge_attr="weight", edge_key=edge_key, create_using=graph)
        assert observed == [0, 1, 2]
        outputs.append(_snapshot(graph))
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("multigraph", [False, True])
def test_custom_pandas_extension_array_observes_inserted_prefix(pandas, directed, multigraph):
    np = pytest.importorskip("numpy")
    fnx_cls, nx_cls = _classes(directed, multigraph)
    outputs = []
    for library, cls in [(fnx, fnx_cls), (nx, nx_cls)]:
        graph = cls()
        observed = []

        class ObservedDtype(pandas.api.extensions.ExtensionDtype):
            name = "fnx-observed-integer"
            type = int
            kind = "O"
            na_value = None

            @classmethod
            def construct_array_type(cls):
                return ObservedArray

        class ObservedArray(pandas.api.extensions.ExtensionArray):
            def __init__(self, values):
                self._values = np.asarray(values, dtype=object)

            @classmethod
            def _from_sequence(cls, values, dtype=None, copy=False):
                return cls(values)

            @property
            def dtype(self):
                return ObservedDtype()

            @property
            def nbytes(self):
                return self._values.nbytes

            def __len__(self):
                return len(self._values)

            def __getitem__(self, index):
                values = self._values[index]
                return type(self)(values) if isinstance(values, np.ndarray) else values

            def isna(self):
                return np.array([value is None for value in self._values])

            def copy(self):
                return type(self)(self._values.copy())

            def take(self, indices, allow_fill=False, fill_value=None):
                return type(self)([
                    fill_value if allow_fill and index == -1 else self._values[index]
                    for index in indices
                ])

            def __iter__(self):
                for value in self._values:
                    observed.append(graph.number_of_edges())
                    yield value

        frame = pandas.DataFrame(
            {"source": ObservedArray(np.array(range(16), dtype=object)), "target": range(1, 17), "weight": range(16)}
        )
        assert type(frame["source"].array) is ObservedArray
        observed.clear()
        result = library.from_pandas_edgelist(frame, edge_attr="weight", create_using=graph)
        assert observed == list(range(16))
        outputs.append(_snapshot(result))
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("custom_field", ["target", "id"])
def test_custom_pandas_keys_are_not_hashed_before_prefix(pandas, monkeypatch, directed, custom_field):
    fnx_cls, _ = _classes(directed)
    graph = fnx_cls()
    observed = []
    inserted = []
    original = fnx_cls.add_edge

    def add_edge(self, *args, **kwargs):
        key = original(self, *args, **kwargs)
        inserted.append(args[:2])
        return key

    monkeypatch.setattr(fnx_cls, "add_edge", add_edge)

    class Key(str):
        def __hash__(self):
            # A callback must observe the completed prefix. Use the public
            # add_edge log, avoiding a reentrant native borrow in __hash__.
            observed.append(len(inserted))
            return super().__hash__()

    frame = pandas.DataFrame({"source": range(16), "target": range(1, 17), "id": range(16), "weight": range(16)})
    values = list(frame[custom_field])
    values[7] = Key("custom-key")
    frame[custom_field] = pandas.Series(values, dtype=object)
    observed.clear()
    result = fnx.from_pandas_edgelist(frame, edge_attr="weight", edge_key="id", create_using=graph)
    assert result.number_of_edges() == 16
    assert observed and min(observed) >= 7


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("multigraph_input", [False, True])
def test_dictionary_mapping_failure_keeps_inserted_prefix(directed, multigraph_input):
    fnx_cls, nx_cls = _classes(directed)
    outputs = []
    for library, cls in [(fnx, fnx_cls), (nx, nx_cls)]:
        graph = cls()
        observed = []

        class Neighbors(dict):
            def items(self):
                observed.append(graph.number_of_edges())
                attrs = {"weight": 2}
                yield 2, {0: attrs} if multigraph_input else attrs
                observed.append(graph.number_of_edges())
                raise RuntimeError("mapping stopped")

        first = {"weight": 1}
        data = {0: {1: {0: first} if multigraph_input else first}, 1: Neighbors(), 2: {}}
        with pytest.raises(RuntimeError, match="mapping stopped"):
            library.from_dict_of_dicts(data, create_using=graph, multigraph_input=multigraph_input)
        assert observed == [1, 2]
        outputs.append(_snapshot(graph))
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize("directed", [False, True])
def test_dictionary_custom_attributes_observe_inserted_prefix(directed):
    fnx_cls, nx_cls = _classes(directed)
    outputs = []
    for library, cls in [(fnx, fnx_cls), (nx, nx_cls)]:
        graph = cls()

        class Attributes(Mapping):
            def __iter__(self):
                yield "prefix_edges"

            def __len__(self):
                return 1

            def __getitem__(self, key):
                return graph.number_of_edges()

        data = {0: {1: {0: {"weight": 1}}}, 1: {2: {0: Attributes()}}, 2: {}}
        result = library.from_dict_of_dicts(data, create_using=graph, multigraph_input=True)
        assert result.get_edge_data(1, 2, 0)["prefix_edges"] == 1
        outputs.append(_snapshot(result))
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize("directed", [False, True])
def test_pandas_graph_subclass_keeps_add_edge_hooks(pandas, directed):
    fnx_cls, nx_cls = _classes(directed)
    outputs = []
    for library, cls in [(fnx, fnx_cls), (nx, nx_cls)]:
        calls = []

        class CustomGraph(cls):
            def add_edge(self, u, v, key=None, **attrs):
                calls.append((u, v, self.number_of_edges()))
                return super().add_edge(u, v, key=key, **attrs)

        frame = pandas.DataFrame({"source": [0] * 16, "target": range(1, 17), "weight": range(16)})
        result = library.from_pandas_edgelist(frame, edge_attr=True, create_using=CustomGraph)
        assert calls == [(0, i + 1, i) for i in range(16)]
        outputs.append(_snapshot(result))
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("multigraph", [False, True])
def test_pandas_invalid_node_keeps_prior_edges(pandas, directed, multigraph):
    fnx_cls, nx_cls = _classes(directed, multigraph)
    outcomes = []
    for library, cls in [(fnx, fnx_cls), (nx, nx_cls)]:
        graph = cls()
        targets = list(range(1, 32, 2))
        targets[12] = None
        frame = pandas.DataFrame({"source": range(0, 32, 2), "target": pandas.Series(targets, dtype=object), "weight": range(16)})
        with pytest.raises(ValueError) as error:
            library.from_pandas_edgelist(frame, edge_attr="weight", create_using=graph)
        outcomes.append((str(error.value), _snapshot(graph)))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("route", ["pandas", "dict"])
@pytest.mark.parametrize("hook", ["add_edge", "clear"])
def test_multigraph_class_mutation_hooks_keep_incremental_route(pandas, monkeypatch, directed, route, hook):
    fnx_cls, nx_cls = _classes(directed)
    outcomes = []
    for library, cls in [(fnx, fnx_cls), (nx, nx_cls)]:
        graph = cls()
        calls = []
        original = getattr(cls, hook)

        def tracked(self, *args, **kwargs):
            calls.append(self.number_of_edges())
            return original(self, *args, **kwargs)

        monkeypatch.setattr(cls, hook, tracked)
        if library is fnx:
            def forbidden(*args, **kwargs):
                raise AssertionError("a graph mutation hook was bypassed")

            monkeypatch.setattr(cls, "_try_add_attr_edges_from_batch", forbidden)
        if route == "pandas":
            data = pandas.DataFrame({"source": [0] * 16, "target": range(1, 17), "weight": range(16)})
            result = library.from_pandas_edgelist(data, edge_attr=True, create_using=graph)
        else:
            data = {i: {} for i in range(17)}
            data[0] = {i: {0: {"weight": i}} for i in range(1, 17)}
            result = library.from_dict_of_dicts(data, create_using=graph, multigraph_input=True)
        assert calls == ([0] if hook == "clear" else list(range(16)))
        outcomes.append(_snapshot(result))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("directed", [False, True])
def test_pandas_numeric_label_aliases_match_networkx(pandas, directed):
    fnx_cls, nx_cls = _classes(directed)
    nan = float("nan")
    labels = [1, True, 1.0, False, 0, 0.0, nan, nan] + list(range(2, 10))
    frame = pandas.DataFrame({
        "source": pandas.Series(labels, dtype=object),
        "target": range(20, 36),
        "weight": range(16),
    })
    actual = fnx.from_pandas_edgelist(frame, edge_attr=True, create_using=fnx_cls)
    expected = nx.from_pandas_edgelist(frame, edge_attr=True, create_using=nx_cls)
    assert _snapshot(actual) == _snapshot(expected)
    assert [type(node) for node in actual] == [type(node) for node in expected]


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("columns", ["nan", "bool-int-alias"])
def test_pandas_nonstring_and_duplicate_columns_match_networkx(pandas, directed, columns):
    fnx_cls, nx_cls = _classes(directed)
    names = [float("nan")] if columns == "nan" else [True, 1]
    frame = pandas.DataFrame(
        [[node, node + 1, *([node + 2] * len(names))] for node in range(16)],
        columns=["source", "target", *names],
    )
    actual = fnx.from_pandas_edgelist(frame, edge_attr=names, create_using=fnx_cls)
    expected = nx.from_pandas_edgelist(frame, edge_attr=names, create_using=nx_cls)
    assert _snapshot(actual) == _snapshot(expected)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("objects", ["late_nested", "integers", "strings"])
def test_pandas_object_attributes_decline_before_buffering(pandas, monkeypatch, directed, objects):
    fnx_cls, nx_cls = _classes(directed)
    graph = fnx_cls()
    payload = [f"label-{i}" for i in range(16)] if objects == "strings" else list(range(16))
    if objects == "late_nested":
        payload[-1] = {"items": [15]}
    frame = pandas.DataFrame({
        "source": range(16), "target": range(1, 17), "weight": range(16),
        "payload": pandas.Series(payload, dtype=object),
    })
    observed = []
    original_iter = pandas.Series.__iter__

    def observe_rows(series):
        for value in original_iter(series):
            if series.name == "source":
                observed.append(graph.number_of_edges())
            yield value

    def forbidden(*args, **kwargs):
        raise AssertionError("an object attribute column reached the native collector")

    with monkeypatch.context() as patch:
        patch.setattr(pandas.Series, "__iter__", observe_rows)
        patch.setattr(fnx_cls, "_try_add_attr_edges_from_batch", forbidden)
        actual = fnx.from_pandas_edgelist(frame, edge_attr=True, create_using=graph)
    expected = nx.from_pandas_edgelist(frame, edge_attr=True, create_using=nx_cls)
    assert observed == list(range(16))
    assert _snapshot(actual) == _snapshot(expected)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("hook_scope", ["instance", "class"])
def test_simple_pandas_mutation_hooks_can_change_later_rows(pandas, monkeypatch, directed, hook_scope):
    fnx_cls, nx_cls = _classes(directed, multigraph=False)
    outcomes = []
    for library, cls in [(fnx, fnx_cls), (nx, nx_cls)]:
        graph = cls()
        frame = pandas.DataFrame({"source": [0, 1, 2], "target": [1, 2, 3], "weight": [1, 2, 3]})
        weights = frame["weight"].array
        calls = []
        original = cls.add_edge

        def tracked(self, u, v, **attrs):
            calls.append((u, v, self.number_of_edges()))
            result = original(self, u, v, **attrs)
            if u == 0:
                weights[2] = 99
            return result

        with monkeypatch.context() as patch:
            if hook_scope == "class":
                patch.setattr(cls, "add_edge", tracked)
            else:
                patch.setattr(graph, "add_edge", tracked.__get__(graph, cls))
            result = library.from_pandas_edgelist(frame, edge_attr="weight", create_using=graph)
        assert result is graph
        assert calls == [(0, 1, 0), (1, 2, 1), (2, 3, 2)]
        assert graph[2][3]["weight"] == 99
        outcomes.append(_snapshot(graph))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("directed", [False, True])
def test_simple_pandas_object_labels_can_change_later_rows(pandas, directed):
    fnx_cls, nx_cls = _classes(directed, multigraph=False)
    outcomes = []
    for library, cls in [(fnx, fnx_cls), (nx, nx_cls)]:
        armed = [False]
        weights = None

        class Node:
            def __hash__(self):
                if armed[0]:
                    armed[0] = False
                    weights[2] = 99
                return 41

        node = Node()
        frame = pandas.DataFrame({
            "source": pandas.Series([0, node, 2], dtype=object),
            "target": [1, 2, 3], "weight": [1, 2, 3],
        })
        weights = frame["weight"].array
        armed[0] = True
        graph = library.from_pandas_edgelist(frame, edge_attr="weight", create_using=cls)
        outcomes.append((
            graph.number_of_edges(),
            [graph[u][v]["weight"] for u, v in [(0, 1), (node, 2), (2, 3)]],
        ))
    assert outcomes == [(3, [1, 2, 99]), (3, [1, 2, 99])]


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("objects", [False, True])
def test_simple_scalar_pandas_import_keeps_bulk_insertion(pandas, monkeypatch, directed, objects):
    fnx_cls, nx_cls = _classes(directed, multigraph=False)
    frame = pandas.DataFrame({
        "source": [0] * 16, "target": range(1, 17),
        "weight": range(16), "kind": ["road"] * 16,
    })
    if objects:
        frame["weight"] = frame["weight"].astype(object)
    batches = []
    original = fnx._pandas_simple_import_batch

    def track(*args):
        batch = original(*args)
        batches.append(None if batch is None else len(batch))
        return batch

    monkeypatch.setattr(fnx, "_pandas_simple_import_batch", track)
    actual = fnx.from_pandas_edgelist(frame, edge_attr=True, create_using=fnx_cls)
    expected = nx.from_pandas_edgelist(frame, edge_attr=True, create_using=nx_cls)
    assert _snapshot(actual) == _snapshot(expected)
    assert batches == [16]
