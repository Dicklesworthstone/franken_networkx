"""Public-callable delegation reachability and observed runtime routes.

For every public name in ``franken_networkx.__all__``, classify the
execution path the wrapper takes by combining:

- **Static**: transitive calls, imported aliases, callable assignments,
  ``getattr`` and actual exported objects across public package namespaces.
  Private helpers are graph nodes, never additional public rows. Dynamic
  resolution gaps are disclosed; reachability is not an always/never proof.

- **Runtime**: warmed ``sys.monitoring`` events observe real NX frames and
  native calls without monkey-patching helpers. Lazy results are exhausted.
  Every backend entry needs its own registered-callable observation; even a
  complete representative census is not per-shape always/never certification.

Combined output:

- ``docs/delegation_ledger.md`` — Markdown summary table.
- ``docs/delegation_ledger.json`` — full per-function data.

The bead motivation: ``docs/coverage.md`` previously claimed
``NX_DELEGATED=0`` despite many runtime fallbacks via shared parity
helpers; this ledger surfaces the actual mix of Rust-native, Python
wrapper, and NetworkX fallback executions.

Usage::

    python3 scripts/delegation_ledger.py --output-dir /path/to/diagnostics

Exit 2 means INCOMPLETE, not a failed algorithm or a publishable ledger.
Default output cannot overwrite authoritative docs while certification is incomplete.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import inspect
import io
import json
import sys
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import franken_networkx as fnx
import networkx as nx

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
INIT_PATH = REPO_ROOT / "python" / "franken_networkx" / "__init__.py"
_CENSUS_ATTEMPTS = []
_SOURCE_IDENTITIES = []

# ---------------------------------------------------------------------------
# AST classification
# ---------------------------------------------------------------------------


@dataclass
class StaticInfo:
    name: str
    is_rust_reexport: bool = False
    calls_parity_helper: bool = False
    calls_raw_rust: bool = False
    raw_rust_targets: list[str] = field(default_factory=list)
    body_lines: int = 0
    networkx_targets: list[str] = field(default_factory=list)
    reachable_helpers: list[str] = field(default_factory=list)
    analysis_gaps: list[str] = field(default_factory=list)


def _scope_nodes(node):
    """Do not attribute an uncalled nested function's body to its parent."""
    for child in ast.iter_child_nodes(node):
        yield child
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield from _scope_nodes(child)


class _CallGraph:
    """Conservative source reachability, independent of helper spellings.

    Imports and simple callable aliases are followed without executing source.
    Unresolved dynamic calls remain explicit gaps, not proof of never delegating.
    """

    def __init__(self, sources: dict[str, str], runtime_bindings=None, closures=None, packages=None):
        self.packages = packages or {"franken_networkx"}
        self.functions = {}
        self.parents = {}
        self.function_environments = {}
        self.environments = {}
        self.edges = {}
        self.gaps = {}
        trees = {name: ast.parse(source) for name, source in sources.items()}
        for module, tree in trees.items():
            env = {}
            self._definitions(module, module, tree, env)
            self.environments[module] = env
        for module, tree in trees.items():
            self._bindings(list(_scope_nodes(tree)), self.environments[module], module)
            self.environments[module].update((runtime_bindings or {}).get(module, {}))
        for target, (module, node, inherited) in self.functions.items():
            parent = self.parents.get(target)
            lexical = self.function_environments[parent] if parent is not None else self.environments[module]
            env = {**lexical, **inherited}
            env.update((closures or {}).get(target, {}))
            nodes = list(_scope_nodes(node))
            for statement in nodes:
                if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                    for assigned in targets:
                        for part in ast.walk(assigned):
                            if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Store):
                                env[part.id] = set()
            # Parameters shadow globals, even when named like an imported alias.
            for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                env[arg.arg] = {"dynamic:" + arg.arg}
            for arg in (node.args.vararg, node.args.kwarg):
                if arg is not None:
                    env[arg.arg] = {"dynamic:" + arg.arg}
            self._bindings(nodes, env, module)
            self.function_environments[target] = env
            reached = set()
            gaps = set()
            for call in nodes:
                if not isinstance(call, ast.Call):
                    continue
                refs = self._resolve(call.func, env)
                reached.update(refs)
                if not refs or any(ref.startswith("dynamic:") for ref in refs):
                    gaps.add(ast.unparse(call.func))
                # Passing a callable to an orchestrator is reachability,
                # too; it need not occur syntactically in call.func.
                for arg in (*call.args, *(kw.value for kw in call.keywords)):
                    reached.update(
                        r for r in self._resolve(arg, env)
                        if r in self.functions or r.startswith((
                            "networkx.", "franken_networkx._fnx.", "_fnx."
                        ))
                    )
            self.edges[target] = reached
            self.gaps[target] = gaps

    def _definitions(self, module, prefix, node, env, parent=None):
        for child in _scope_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                target = prefix + "." + child.name
                env[child.name] = {target}
                nested = {}
                self.functions[target] = (module, child, nested)
                self.parents[target] = parent
                self._definitions(module, target + ".<locals>", child, nested, target)
            elif isinstance(child, ast.ClassDef):
                self._definitions(module, prefix + "." + child.name, child, {}, parent)

    @staticmethod
    def _resolve(node, env):
        if isinstance(node, ast.Name):
            return env.get(node.id, set())
        if isinstance(node, ast.Attribute):
            return {root + "." + node.attr for root in _CallGraph._resolve(node.value, env)}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2:
            roots = _CallGraph._resolve(node.args[0], env)
            attr = node.args[1]
            if isinstance(attr, ast.Constant) and isinstance(attr.value, str):
                return {root + "." + attr.value for root in roots}
            return {root + ".*" for root in roots}
        return set()

    def _bindings(self, nodes, env, module):
        # Alias chains need a fixed point; union across branches is conservative.
        for _ in range(len(nodes) + 1):
            changed = False
            for node in nodes:
                bindings = {}
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.asname or alias.name.split(".")[0]
                        bindings[name] = {alias.name if alias.asname else name}
                elif isinstance(node, ast.ImportFrom):
                    origin = node.module or ""
                    if node.level:
                        package = module if module in self.packages else module.rpartition(".")[0]
                        origin = importlib.util.resolve_name("." * node.level + origin, package)
                    for alias in node.names:
                        bindings[alias.asname or alias.name] = {origin + "." + alias.name}
                elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name):
                            if isinstance(node.value, ast.Attribute) and any(
                                isinstance(part, ast.Name) and part.id == target.id
                                for part in ast.walk(node.value)
                            ):
                                bindings[target.id] = {"dynamic:rebound:" + target.id}
                            else:
                                bindings[target.id] = self._resolve(node.value, env)
                for name, refs in bindings.items():
                    before = env.setdefault(name, set())
                    new = refs - before
                    if new:
                        before.update(new)
                        changed = True
            if not changed:
                return

    def analyze(self, public: dict[str, set[str]]) -> dict[str, StaticInfo]:
        result = {}
        for name, roots in public.items():
            si = StaticInfo(name=name)
            pending = list(roots)
            seen = set()
            while pending:
                target = pending.pop()
                if target in seen:
                    continue
                seen.add(target)
                if target in self.functions:
                    pending.extend(self.edges[target])
                    si.reachable_helpers.append(target)
                    si.analysis_gaps.extend(self.gaps[target])
                    node = self.functions[target][1]
                    si.body_lines += getattr(node, "end_lineno", node.lineno) - node.lineno
                elif target == "networkx" or target.startswith("networkx."):
                    # Constructors/configuration/exceptions are not algorithm delegation.
                    leaf = target.rsplit(".", 1)[-1]
                    if leaf not in {"Graph", "DiGraph", "MultiGraph", "MultiDiGraph", "config"} and not leaf.startswith("NetworkX") and not target.startswith(("networkx.exception.", "networkx.utils.configs.")):
                        si.networkx_targets.append(target)
                elif target.startswith(("franken_networkx._fnx.", "_fnx.")):
                    si.raw_rust_targets.append(target)
                elif target.startswith("franken_networkx.") or target.startswith("dynamic:"):
                    si.analysis_gaps.append(target)
            si.networkx_targets = sorted(set(si.networkx_targets))
            si.raw_rust_targets = sorted(set(si.raw_rust_targets))
            si.reachable_helpers = sorted(set(si.reachable_helpers))
            si.analysis_gaps = sorted(set(si.analysis_gaps))
            si.calls_parity_helper = bool(si.networkx_targets)
            si.calls_raw_rust = bool(si.raw_rust_targets)
            si.is_rust_reexport = bool(roots) and all(
                target.startswith(("franken_networkx._fnx.", "_fnx.")) for target in roots
            )
            result[name] = si
        return result


def _analyze_source(source: str, public_names: list[str]) -> dict[str, StaticInfo]:
    graph = _CallGraph({"franken_networkx": source})
    env = graph.environments["franken_networkx"]
    return graph.analyze({name: env.get(name, set()) for name in public_names})


def _gather_static(*, include_backend=True) -> dict[str, StaticInfo]:
    """Actual public callables across the package, not every private AST def."""
    sources = {}
    modules = {}
    packages = set()
    public_modules = set()
    _SOURCE_IDENTITIES.clear()
    for path in sorted(INIT_PATH.parent.rglob("*.py")):
        parts = list(path.relative_to(INIT_PATH.parent).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        module = ".".join(["franken_networkx", *parts])
        if not any(part.startswith("_") for part in parts):
            public_modules.add(module)
        if path.name == "__init__.py":
            packages.add(module)
        sources[module] = path.read_text(encoding="utf-8")
        modules[module] = importlib.import_module(module)
        loaded_path = Path(modules[module].__file__)
        _SOURCE_IDENTITIES.append({
            "module": module,
            "checkout_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "loaded_sha256": hashlib.sha256(loaded_path.read_bytes()).hexdigest(),
        })

    runtime_bindings = {}
    closures = {}
    public = {}
    for module_name, module in modules.items():
        runtime_bindings[module_name] = {}
        names = fnx.__all__ if module is fnx else getattr(module, "__all__", None)
        if names is None:
            names = [name for name in dir(module) if not name.startswith("_")]
        # Resolve actual imported/rebound objects; __module__ is often copied by
        # functools.wraps and is not evidence of the code being executed.
        for name, obj in vars(module).items():
            refs = _object_targets(obj)
            if refs:
                runtime_bindings[module_name][name] = refs
            function = getattr(obj, "__func__", obj)
            if inspect.isfunction(function):
                refs = _object_targets(function)
                if refs:
                    captured = inspect.getclosurevars(function).nonlocals
                    for ref in refs:
                        env = closures.setdefault(ref, {})
                        for key, value in captured.items():
                            env.setdefault(key, set()).update(_object_targets(value))
        if module_name not in public_modules:
            continue
        for name in names:
            try:
                obj = getattr(module, name)
            except AttributeError:
                # A declared-but-missing export remains an unresolved row.
                obj = None
            if obj is None and module is fnx:
                public[name] = {module_name + "." + name}
            elif callable(obj):
                label = name if module is fnx else module_name.removeprefix("franken_networkx.") + "." + name
                public[label] = _object_targets(obj) or {"dynamic:export:" + label}
        if module is fnx:
            # Namespace objects (approximation is not a ModuleType) also expose
            # concrete methods; dir alone misses names supplied by __getattr__.
            for name in fnx.__all__:
                obj = getattr(fnx, name, None)
                reference = getattr(nx, name, None)
                if callable(obj) or obj is None or not inspect.ismodule(reference):
                    continue
                for attr in dir(reference):
                    if attr.startswith("_"):
                        continue
                    value = getattr(obj, attr, None)
                    if callable(value):
                        public[name + "." + attr] = _object_targets(value) or {"dynamic:export:" + name + "." + attr}
    from franken_networkx.backend import _SUPPORTED_ALGORITHMS

    if include_backend:
        for name, obj in _SUPPORTED_ALGORITHMS.items():
            public["backend.BackendInterface." + name] = _object_targets(obj) or {"dynamic:backend:" + name}
    graph = _CallGraph(sources, runtime_bindings, closures, packages)
    return graph.analyze(public)


def _object_targets(obj) -> set[str]:
    function = getattr(obj, "__func__", obj)
    code = getattr(function, "__code__", None)
    if code is not None:
        path = Path(code.co_filename).resolve()
        for package in (fnx, nx):
            root = Path(package.__file__).resolve().parent
            if path.is_relative_to(root):
                parts = list(path.relative_to(root).with_suffix("").parts)
                if parts[-1] == "__init__":
                    parts.pop()
                return {".".join([package.__name__, *parts, code.co_qualname])}
        return set()
    if inspect.ismodule(obj):
        return {obj.__name__}
    native_name = getattr(obj, "__name__", None)
    if native_name is not None and (inspect.isbuiltin(obj) or isinstance(obj, type)) and vars(fnx._fnx).get(native_name) is obj:
        return {"franken_networkx._fnx." + native_name}
    module = getattr(obj, "__module__", "")
    if not isinstance(module, str):
        return set()
    if (inspect.isbuiltin(obj) or isinstance(obj, type)) and (module.startswith("franken_networkx._fnx") or module == "_fnx"):
        return {"franken_networkx._fnx." + obj.__name__}
    if module.startswith("networkx."):
        return {module + "." + getattr(obj, "__name__", type(obj).__name__)}
    return set()


def _classify_static(si: StaticInfo) -> str:
    if si.is_rust_reexport:
        return "rust-reexport"
    if si.calls_raw_rust and not si.calls_parity_helper:
        return "rust-native"
    if si.calls_raw_rust and si.calls_parity_helper:
        return "mixed-route"
    if si.calls_parity_helper:
        return "nx-fallback"
    return "py-wrapper"


# ---------------------------------------------------------------------------
# Runtime instrumentation
# ---------------------------------------------------------------------------


@dataclass
class RuntimeProbe:
    name: str
    shape_id: str
    raw_called: list[str] = field(default_factory=list)
    parity_called_with_target: list[str] = field(default_factory=list)
    error: str | None = None
    classification: str = "uninstrumented"
    networkx_frames: int = 0
    networkx_algorithm_frames: int = 0
    networkx_frame_targets: dict[str, int] = field(default_factory=dict)


def _make_unweighted_path_5():
    return fnx.path_graph(5), 0, 4


def _make_weighted_path_5_kwargs():
    g = fnx.Graph()
    for i in range(4):
        g.add_edge(i, i + 1, weight=i + 1.5)
    return g, 0, 4


def _make_weighted_path_5_postmut():
    g = fnx.path_graph(5)
    for i, (u, v) in enumerate(g.edges):
        g[u][v]["weight"] = i + 1.5
    return g, 0, 4


def _make_cycle_6():
    return fnx.cycle_graph(6), 0, 3


def _make_directed_cycle_6():
    return fnx.DiGraph([(i, (i + 1) % 6) for i in range(6)]), 0, 3


# Shape-sensitive wrappers we want to profile. Each entry is
# (wrapper-name, list of (shape-id, builder, args, kwargs)).
RUNTIME_SPECS: list[tuple[str, list[tuple[str, Callable, tuple, dict]]]] = [
    (
        "single_source_dijkstra_path_length",
        [
            ("path-5-unweighted", _make_unweighted_path_5, ("source",), {}),
            ("path-5-weighted-kwargs", _make_weighted_path_5_kwargs, ("source",), {}),
            ("path-5-weighted-postmut", _make_weighted_path_5_postmut, ("source",), {}),
        ],
    ),
    (
        "single_source_bellman_ford_path_length",
        [
            ("path-5-unweighted", _make_unweighted_path_5, ("source",), {}),
            ("path-5-weighted-kwargs", _make_weighted_path_5_kwargs, ("source",), {}),
            ("path-5-weighted-postmut", _make_weighted_path_5_postmut, ("source",), {}),
        ],
    ),
    (
        "astar_path_length",
        [
            ("path-5-unweighted", _make_unweighted_path_5, ("source", "target"), {}),
            ("path-5-weighted-kwargs", _make_weighted_path_5_kwargs, ("source", "target"), {}),
            ("path-5-weighted-postmut", _make_weighted_path_5_postmut, ("source", "target"), {}),
        ],
    ),
    (
        "shortest_path_length",
        [
            ("path-5-unweighted", _make_unweighted_path_5, ("source", "target"), {}),
            ("path-5-weighted-kwargs", _make_weighted_path_5_kwargs, ("source", "target"), {"weight": "weight"}),
            ("path-5-weighted-postmut", _make_weighted_path_5_postmut, ("source", "target"), {"weight": "weight"}),
        ],
    ),
    (
        "floyd_warshall",
        [
            ("path-5-unweighted", _make_unweighted_path_5, (), {}),
            ("path-5-weighted-kwargs", _make_weighted_path_5_kwargs, (), {}),
            ("path-5-weighted-postmut", _make_weighted_path_5_postmut, (), {}),
        ],
    ),
]
RUNTIME_SPECS += [
    (name, [("cycle-6", _make_cycle_6, (), kwargs)])
    for name, kwargs in [
        ("max_weight_matching", {}),
        ("min_weight_matching", {}),
        ("community.louvain_communities", {"seed": 7}),
        ("community.greedy_modularity_communities", {}),
        ("k_components", {}),
    ]
]
RUNTIME_SPECS += [
    (name, [("directed-cycle-6", _make_directed_cycle_6, (), {})])
    for name in ["maximum_branching", "simple_cycles"]
]


class _Tracer:
    """Observe actual Python starts and native calls, without patching fnx."""

    def __init__(self):
        self.parity_targets: list[str] = []
        self.raw_targets: list[str] = []
        self.networkx_frames = 0
        self.networkx_algorithm_frames = 0
        self.frame_targets = Counter()
        self._tool_id = None
        self._nx_root = str(Path(nx.__file__).resolve().parent) + "/"
        self._raw_ids = {
            id(target): name for name, target in vars(fnx).items()
            if name.startswith("_raw_") and callable(target)
        }
        for name, target in vars(fnx._fnx).items():
            if callable(target):
                self._raw_ids.setdefault(id(target), "_fnx." + name)

    def install(self):
        if not hasattr(sys, "monitoring"):
            raise RuntimeError("runtime census requires Python 3.12+ sys.monitoring")
        monitoring = sys.monitoring
        for tool_id in (3, 4):
            try:
                monitoring.use_tool_id(tool_id, "fnx-delegation-ledger")
            except ValueError:
                continue
            self._tool_id = tool_id
            break
        if self._tool_id is None:
            raise RuntimeError("no free monitoring tool ID; census not observed")
        try:
            monitoring.register_callback(self._tool_id, monitoring.events.PY_START, self._python_start)
            monitoring.register_callback(self._tool_id, monitoring.events.CALL, self._call)
            monitoring.set_events(self._tool_id, monitoring.events.PY_START | monitoring.events.CALL)
        except BaseException:
            self.restore()
            raise

    def _python_start(self, code, instruction_offset):
        if not code.co_filename.startswith(self._nx_root) or code.co_name == "<module>":
            return
        relative = code.co_filename[len(self._nx_root):]
        if relative in {"exception.py", "utils/configs.py"}:
            return
        self.networkx_frames += 1
        target = relative + ":" + code.co_qualname
        self.frame_targets[target] += 1
        # Keep all eligible NX frames, but distinguish graph constructors and
        # backend/decorator plumbing from algorithm execution in the verdict.
        if relative.startswith(("algorithms/", "generators/", "readwrite/", "linalg/", "drawing/")) or relative in {
            "convert.py", "convert_matrix.py", "relabel.py"
        }:
            self.networkx_algorithm_frames += 1
            self.parity_targets.append(target)

    def _call(self, code, instruction_offset, target, arg0):
        name = self._raw_ids.get(id(target))
        if name is not None:
            self.raw_targets.append(name)

    def restore(self):
        if self._tool_id is not None:
            monitoring = sys.monitoring
            monitoring.set_events(self._tool_id, 0)
            monitoring.register_callback(self._tool_id, monitoring.events.PY_START, None)
            monitoring.register_callback(self._tool_id, monitoring.events.CALL, None)
            monitoring.free_tool_id(self._tool_id)
            self._tool_id = None


def _consume_result(value, budget=None):
    """Exhaust lazy results (including iterators nested in APSP result rows)."""
    if budget is None:
        budget = [10000]
    if isinstance(value, (Iterator, list, tuple, dict)):
        values = value.values() if isinstance(value, dict) else value
        for item in values:
            budget[0] -= 1
            if budget[0] < 0:
                raise RuntimeError("runtime probe result exceeded 10000 items")
            _consume_result(item, budget)


def _observe_callable(wrapper, *args, _warm_args=None, **kwargs) -> RuntimeProbe:
    probe = RuntimeProbe(name=getattr(wrapper, "__name__", type(wrapper).__name__), shape_id="call")
    tracer = _Tracer()
    try:
        _consume_result(wrapper(*(_warm_args if _warm_args is not None else args), **kwargs))
        tracer.install()
        _consume_result(wrapper(*args, **kwargs))
    except Exception as exc:
        probe.error = f"{type(exc).__name__}: {exc}"
    finally:
        tracer.restore()
    probe.raw_called = sorted(set(tracer.raw_targets))
    probe.parity_called_with_target = sorted(set(tracer.parity_targets))
    probe.networkx_frames = tracer.networkx_frames
    probe.networkx_algorithm_frames = tracer.networkx_algorithm_frames
    probe.networkx_frame_targets = dict(sorted(tracer.frame_targets.items()))
    if probe.error is not None:
        probe.classification = "error"
    elif probe.networkx_algorithm_frames and probe.raw_called:
        probe.classification = "mixed (native and nx observed)"
    elif probe.networkx_algorithm_frames:
        probe.classification = "nx-fallback"
    elif probe.raw_called:
        probe.classification = "rust-native"
    else:
        probe.classification = "py-wrapper-only"
    return probe


def _run_runtime_probes() -> list[RuntimeProbe]:
    probes: list[RuntimeProbe] = []
    for fname, shapes in RUNTIME_SPECS:
        wrapper = fnx
        for part in fname.split("."):
            wrapper = getattr(wrapper, part, None)
            if wrapper is None:
                break
        if wrapper is None:
            probes.append(RuntimeProbe(name=fname, shape_id="missing-export", error="declared probe export is absent", classification="error"))
            continue
        for shape_id, builder, arg_keys, kwargs in shapes:
            try:
                graph, *extras = builder()
            except Exception as exc:
                probes.append(
                    RuntimeProbe(
                        name=fname,
                        shape_id=shape_id,
                        error=f"build: {type(exc).__name__}: {exc}",
                    )
                )
                continue

            arg_map = {"source": extras[0] if extras else None,
                       "target": extras[1] if len(extras) > 1 else None}
            try:
                args = [arg_map[key] for key in arg_keys]
            except KeyError:
                args = []

            probe = _observe_callable(wrapper, graph, *args, **kwargs)
            probe.name = fname
            probe.shape_id = shape_id
            probes.append(probe)
    probes.extend(_run_default_dispatchable_census())
    probes.extend(_run_explicit_dispatchable_census())
    return probes


def _run_default_dispatchable_census() -> list[RuntimeProbe]:
    """Bounded default-call fixtures; errors are retained and earn no coverage.

    Both shapes and the required registry are selected before execution.
    Non-default arities need explicit fixtures, not guessed argument values.
    """
    from franken_networkx.backend import _SUPPORTED_ALGORITHMS

    _CENSUS_ATTEMPTS.clear()
    shapes = [
        ("default-undirected-cycle-6", lambda: fnx.Graph([(i, (i + 1) % 6) for i in range(6)])),
        ("default-directed-path-6", lambda: fnx.DiGraph([(i, i + 1) for i in range(5)])),
    ]
    probes = []
    for name, function in sorted(_SUPPORTED_ALGORITHMS.items()):
        try:
            parameters = list(inspect.signature(function).parameters.values())
        except (ValueError, TypeError) as exc:
            _CENSUS_ATTEMPTS.append({"name": name, "status": "missing-signature", "error": str(exc)})
            continue
        if not parameters or parameters[0].name not in {"G", "g", "graph", "flowG"} or parameters[0].kind not in {
            inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD
        } or any(
            p.default is inspect.Parameter.empty and p.kind in {
                inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY
            } for p in parameters[1:]
        ):
            _CENSUS_ATTEMPTS.append({"name": name, "status": "needs-explicit-fixture"})
            continue
        kwargs = {"seed": 7} if any(p.name == "seed" and p.kind != inspect.Parameter.POSITIONAL_ONLY for p in parameters) else {}
        for shape_id, build in shapes:
            # Setup stays outside the observed window. Fresh graphs prevent a
            # mutating warm call from consuming or invalidating the live input.
            graph, warm_graph = build(), build()
            with nx.config(backend_priority={}):
                probe = _observe_callable(function, graph, _warm_args=(warm_graph,), **kwargs)
            _CENSUS_ATTEMPTS.append({
                "name": name, "shape": shape_id,
                "status": "observed" if probe.error is None else "fixture-error",
                "error": probe.error,
            })
            if probe.error is None:
                probe.name = "backend.BackendInterface." + name
                probe.shape_id = shape_id
                probes.append(probe)
    return probes


_SOURCE_CASES = {
    "ancestors", "descendants", "dominance_frontiers", "immediate_dominators",
    "bfs_edges", "bfs_predecessors", "bfs_successors", "bfs_tree", "predecessor",
    "single_source_bellman_ford", "single_source_bellman_ford_path", "single_source_bellman_ford_path_length",
    "single_source_dijkstra", "single_source_dijkstra_path", "single_source_dijkstra_path_length",
    "single_source_shortest_path", "single_source_shortest_path_length",
    "single_target_shortest_path", "single_target_shortest_path_length",
    "node_connected_component", "non_neighbors", "is_isolate", "local_reaching_centrality",
}
_ENDPOINT_CASES = {
    "all_shortest_paths", "all_simple_paths", "astar_path", "astar_path_length", "bellman_ford_path",
    "bellman_ford_path_length", "bidirectional_shortest_path", "common_neighbors",
    "dijkstra_path", "dijkstra_path_length", "efficiency", "has_path",
    "shortest_simple_paths", "maximum_flow", "maximum_flow_value", "minimum_cut",
    "minimum_cut_value", "contracted_nodes", "identified_nodes",
}
_NO_ARG_GENERATORS = {
    "bull_graph", "chvatal_graph", "cubical_graph", "desargues_graph", "diamond_graph",
    "dodecahedral_graph", "frucht_graph", "heawood_graph", "hoffman_singleton_graph",
    "house_graph", "house_x_graph", "icosahedral_graph", "krackhardt_kite_graph",
    "moebius_kantor_graph", "null_graph", "octahedral_graph", "pappus_graph",
    "petersen_graph", "sedgewick_maze_graph", "tetrahedral_graph", "trivial_graph",
    "truncated_cube_graph", "truncated_tetrahedron_graph", "tutte_graph",
}
_GENERATOR_ARGS = {
    "balanced_tree": (2, 2), "barabasi_albert_graph": (6, 2), "barbell_graph": (3, 1),
    "binomial_tree": (3,), "chordal_cycle_graph": (5,), "circulant_graph": (6, [1, 2]),
    "circular_ladder_graph": (3,), "complete_bipartite_graph": (3, 3), "complete_graph": (6,),
    "complete_multipartite_graph": (2, 2, 2), "cycle_graph": (6,), "empty_graph": (6,),
    "full_rary_tree": (2, 6), "generalized_petersen_graph": (5, 2), "gnp_random_graph": (6, 0.2),
    "grid_2d_graph": (2, 3), "hypercube_graph": (3,), "kneser_graph": (5, 2),
    "ladder_graph": (3,), "lollipop_graph": (3, 3), "paley_graph": (5,), "path_graph": (6,),
    "ring_of_cliques": (3, 3), "star_graph": (5,), "tadpole_graph": (3, 3),
    "turan_graph": (6, 3), "watts_strogatz_graph": (6, 2, 0.2),
    "wheel_graph": (6,), "windmill_graph": (3, 3),
}
_SPECIAL_CASES = {
    "bfs_layers", "descendants_at_distance", "multi_source_dijkstra", "find_negative_cycle",
    "chordal_graph_treewidth", "is_aperiodic", "max_weight_clique", "tree_broadcast_center",
    "tree_broadcast_time", "is_digraphical", "is_graphical", "is_multigraphical", "is_pseudographical",
    "compose", "difference", "intersection", "symmetric_difference", "union",
    "could_be_isomorphic", "fast_could_be_isomorphic", "faster_could_be_isomorphic", "is_isomorphic",
    "contracted_edge", "cut_size", "normalized_cut_size", "edge_boundary", "node_boundary",
    "group_degree_centrality", "group_in_degree_centrality", "group_out_degree_centrality",
    "get_edge_attributes", "get_node_attributes", "set_edge_attributes", "set_node_attributes",
    "incremental_closeness_centrality", "is_dominating_set", "is_edge_cover", "is_k_regular",
    "is_matching", "is_maximal_matching", "is_perfect_matching", "is_path", "is_simple_path",
    "modularity", "path_weight", "relabel_nodes", "spanner", "from_dict_of_dicts",
    "from_dict_of_lists", "from_edgelist", "from_numpy_array", "from_scipy_sparse_array",
    "from_pandas_edgelist", "node_link_graph", "read_adjlist", "read_edgelist", "read_graphml",
}


def _explicit_census_input(name):
    if name in _NO_ARG_GENERATORS:
        return (), {}
    if name in _GENERATOR_ARGS:
        kwargs = {"seed": 7} if name in {"barabasi_albert_graph", "gnp_random_graph", "watts_strogatz_graph"} else {}
        return _GENERATOR_ARGS[name], kwargs
    directed = name in {
        "ancestors", "descendants", "dominance_frontiers", "immediate_dominators",
        "descendants_at_distance", "maximum_flow", "maximum_flow_value", "minimum_cut", "minimum_cut_value",
        "group_in_degree_centrality", "group_out_degree_centrality", "is_aperiodic",
    }
    graph = (fnx.DiGraph if directed else fnx.Graph)(
        [(i, i + 1, {"weight": 1.5, "capacity": 2.0}) for i in range(5)]
    )
    if name in _SOURCE_CASES:
        return (graph, 0), {}
    if name in _ENDPOINT_CASES:
        return (graph, 0, 3), {}
    if name == "bfs_layers":
        return (graph, [0]), {}
    if name == "descendants_at_distance":
        return (graph, 0, 2), {}
    if name == "multi_source_dijkstra":
        return (graph, [0]), {}
    if name == "find_negative_cycle":
        graph.add_edge(0, 1, weight=-1)
        return (graph, 0), {}
    if name in {"chordal_graph_treewidth", "tree_broadcast_center", "tree_broadcast_time"}:
        return (graph,), {}
    if name == "is_aperiodic":
        graph.add_edge(5, 0)
        return (graph,), {}
    if name == "max_weight_clique":
        for node in graph:
            graph.nodes[node]["weight"] = 1
        return (graph,), {}
    if name == "is_digraphical":
        return ([1] * 6, [1] * 6), {}
    if name in {"is_graphical", "is_multigraphical", "is_pseudographical"}:
        return ([2] * 6,), {}
    if name in {"compose", "difference", "intersection", "symmetric_difference", "could_be_isomorphic", "fast_could_be_isomorphic", "faster_could_be_isomorphic", "is_isomorphic", "union"}:
        other = graph.copy()
        return (graph, other), ({"rename": ("G", "H")} if name == "union" else {})
    if name in {"cut_size", "normalized_cut_size"}:
        return (graph, {0, 1, 2}, {3, 4, 5}), {}
    if name in {"edge_boundary", "node_boundary", "group_degree_centrality", "group_in_degree_centrality", "group_out_degree_centrality", "is_dominating_set"}:
        return (graph, {0, 2, 4}), {}
    if name in {"get_edge_attributes", "get_node_attributes"}:
        return (graph, "weight"), {}
    if name in {"set_edge_attributes", "set_node_attributes"}:
        return (graph, 2.0, "weight"), {}
    if name in {"contracted_edge", "incremental_closeness_centrality"}:
        return (graph, (0, 1)), {}
    if name == "is_edge_cover":
        return (graph, list(graph.edges)), {}
    if name == "is_k_regular":
        return (graph, 2), {}
    if name in {"is_matching", "is_maximal_matching", "is_perfect_matching"}:
        return (graph, {(0, 1), (2, 3), (4, 5)}), {}
    if name in {"is_path", "is_simple_path", "path_weight"}:
        return (graph, [0, 1, 2]), ({"weight": "weight"} if name == "path_weight" else {})
    if name == "modularity":
        return (graph, [{0, 1, 2}, {3, 4, 5}]), {}
    if name == "relabel_nodes":
        return (graph, {node: str(node) for node in graph}), {}
    if name == "spanner":
        return (graph, 3), {"seed": 7}
    if name == "from_dict_of_dicts":
        return ({0: {1: {}}, 1: {0: {}}},), {}
    if name == "from_dict_of_lists":
        return ({0: [1], 1: [0]},), {}
    if name == "from_edgelist":
        return ([(0, 1), (1, 2)],), {}
    if name == "from_numpy_array":
        import numpy as np
        return (np.array([[0, 1], [1, 0]]),), {}
    if name == "from_scipy_sparse_array":
        import scipy.sparse
        return (scipy.sparse.csr_array([[0, 1], [1, 0]]),), {}
    if name == "from_pandas_edgelist":
        import pandas as pd
        return (pd.DataFrame({"source": [0, 1], "target": [1, 2]}),), {}
    if name == "node_link_graph":
        return (nx.node_link_data(nx.path_graph(3)),), {}
    if name in {"read_adjlist", "read_edgelist"}:
        return (io.BytesIO(b"0 1\n1 2\n"),), {}
    if name == "read_graphml":
        data = "\n".join(nx.generate_graphml(nx.path_graph(3))).encode()
        return (io.BytesIO(data),), {}
    raise ValueError("no explicit fixture: " + name)


def _run_explicit_dispatchable_census():
    from franken_networkx.backend import _SUPPORTED_ALGORITHMS

    probes = []
    names = _SOURCE_CASES | _ENDPOINT_CASES | _NO_ARG_GENERATORS | set(_GENERATOR_ARGS) | _SPECIAL_CASES
    for name in sorted(names):
        function = _SUPPORTED_ALGORITHMS[name]
        try:
            args, kwargs = _explicit_census_input(name)
            warm_args, _ = _explicit_census_input(name)
        except Exception as exc:
            _CENSUS_ATTEMPTS.append({"name": name, "shape": "explicit", "status": "fixture-error", "error": f"{type(exc).__name__}: {exc}"})
            continue
        with nx.config(backend_priority={}):
            probe = _observe_callable(function, *args, _warm_args=warm_args, **kwargs)
        _CENSUS_ATTEMPTS.append({"name": name, "shape": "explicit", "status": "observed" if probe.error is None else "fixture-error", "error": probe.error})
        if probe.error is None:
            probe.name = "backend.BackendInterface." + name
            probe.shape_id = "explicit"
            probes.append(probe)
    return probes


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_markdown(
    static: dict[str, StaticInfo],
    runtime: list[RuntimeProbe],
    path: Path,
) -> None:
    counts = Counter(_classify_static(si) for si in static.values())
    public = sorted(static)
    coverage = _census_coverage(runtime)

    lines = [
        "# FrankenNetworkX Delegation Ledger",
        "",
        "*Auto-generated by `scripts/delegation_ledger.py` (br-r37-c1-256q5).*",
        "",
        "## Static AST classification",
        "",
        "Public callable rows from `__all__` and public package namespaces. "
        "Transitive AST reachability includes private helpers but does not count them as exports. "
        "Unresolved dynamic calls are retained in JSON; no category proves always/never delegation. Categories:",
        "",
        "- `rust-reexport`: the exported callable is a native binding.",
        "- `rust-native`: resolved call graph reaches native bindings but no NX algorithm call.",
        "- `mixed-route`: resolved call graph reaches both native and NX calls; not a per-shape proof.",
        "- `nx-fallback`: resolved call graph reaches NX calls but no native binding.",
        "- `py-wrapper`: no resolved native/NX call; consult `analysis_gaps` before interpreting this row.",
        "",
        "| classification | count |",
        "|----------------|-------|",
    ]
    for cls, n in sorted(counts.items()):
        lines.append(f"| `{cls}` | {n} |")
    lines.append("")

    lines.append("## Runtime probe results")
    lines.append("")
    lines.append(
        "Warmed `sys.monitoring` PY_START/CALL events; lazy results are exhausted. "
        "Eligible NX frames exclude imports, exceptions and config; algorithm-frame counts "
        "separately exclude constructors/backend plumbing. No FNX helper is patched. "
        "A native-call observation is not proof that the entire algorithm runs in Rust. "
        f"Representative-input census: {len(coverage['observed'])}/{len(coverage['required'])} "
        "dispatchables observed successfully; the full missing set is in JSON. "
        "Overall analysis remains INCOMPLETE: per-shape always/never certification is not implemented."
    )
    lines.append("")
    lines.append(
        "| function | shape | classification | raw bindings used | nx fallbacks |"
    )
    lines.append("|----------|-------|----------------|-------------------|--------------|")
    for probe in runtime:
        raw_str = ", ".join(f"`{x}`" for x in probe.raw_called) or "—"
        nx_str = ", ".join(f"`{x}`" for x in probe.parity_called_with_target) or "—"
        lines.append(
            f"| `{probe.name}` | `{probe.shape_id}` | `{probe.classification}` | "
            f"{raw_str} | {nx_str} |"
        )
    lines.append("")

    # Per-function static breakdown table
    lines.append("## Per-function static classification")
    lines.append("")
    lines.append("| name | classification | calls_parity_helper | raw_targets |")
    lines.append("|------|----------------|--------------------|-------------|")
    for name in public:
        si = static.get(name)
        if si is None:
            cls = "untracked"
            parity = ""
            raw = ""
        else:
            cls = _classify_static(si)
            parity = "yes" if si.calls_parity_helper else "no"
            raw = ", ".join(f"`{t}`" for t in sorted(set(si.raw_rust_targets))) or "—"
        lines.append(f"| `{name}` | `{cls}` | {parity} | {raw} |")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_json(
    static: dict[str, StaticInfo],
    runtime: list[RuntimeProbe],
    path: Path,
) -> None:
    out = {
        "status": "INCOMPLETE",
        "unimplemented_checks": ["per-shape always/mixed/never certification", "independent verification"],
        "scope": "public callable access paths and BackendInterface dispatch entries, not unique implementations",
        "census": _census_coverage(runtime),
        "census_attempts": _CENSUS_ATTEMPTS,
        "provenance": {
            "fnx_version": fnx.__version__,
            "nx_version": nx.__version__,
            "loaded_shim_sha256": hashlib.sha256(Path(fnx.__file__).read_bytes()).hexdigest(),
            "checkout_shim_sha256": hashlib.sha256(INIT_PATH.read_bytes()).hexdigest(),
            "so_sha256": hashlib.sha256(Path(fnx._fnx.__file__).read_bytes()).hexdigest(),
            "python": sys.version,
            "package_sources": _SOURCE_IDENTITIES,
        },
        "static": [
            {
                "name": si.name,
                "classification": _classify_static(si),
                "is_rust_reexport": si.is_rust_reexport,
                "calls_parity_helper": si.calls_parity_helper,
                "calls_raw_rust": si.calls_raw_rust,
                "raw_rust_targets": sorted(set(si.raw_rust_targets)),
                "body_lines": si.body_lines,
                "networkx_targets": si.networkx_targets,
                "reachable_helpers": si.reachable_helpers,
                "analysis_gaps": si.analysis_gaps,
            }
            for name, si in sorted(static.items())
        ],
        "runtime": [
            {
                "name": probe.name,
                "shape": probe.shape_id,
                "classification": probe.classification,
                "raw_called": probe.raw_called,
                "parity_called_with_target": probe.parity_called_with_target,
                "error": probe.error,
                "networkx_frames": probe.networkx_frames,
                "networkx_algorithm_frames": probe.networkx_algorithm_frames,
                "networkx_frame_targets": probe.networkx_frame_targets,
            }
            for probe in runtime
        ],
    }
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")


def _census_coverage(runtime):
    from franken_networkx.backend import _SUPPORTED_ALGORITHMS

    required = sorted(_SUPPORTED_ALGORITHMS)
    prefix = "backend.BackendInterface."
    observed = sorted({
        p.name.removeprefix(prefix) for p in runtime
        if p.error is None and p.name.startswith(prefix)
    } & set(required))
    return {"required": required, "observed": observed, "missing": sorted(set(required) - set(observed))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=DOCS_DIR, help="output directory"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="suppress stdout summary"
    )
    args = parser.parse_args(argv)

    static = _gather_static()
    stale_sources = [row["module"] for row in _SOURCE_IDENTITIES if row["checkout_sha256"] != row["loaded_sha256"]]
    if stale_sources:
        print(f"FAIL: loaded package sources differ from checkout: {stale_sources}", file=sys.stderr)
        return 1
    runtime = _run_runtime_probes()
    out_dir = args.output_dir
    mismatches = [p.name for p in runtime if p.networkx_algorithm_frames and not static.get(p.name, StaticInfo(p.name)).calls_parity_helper]
    errors = [p.name for p in runtime if p.error is not None]
    if mismatches or errors:
        print(f"FAIL: static misses={mismatches}; runtime errors={errors}", file=sys.stderr)
        return 1
    if out_dir.resolve() == DOCS_DIR.resolve():
        print("INCOMPLETE: refusing to replace authoritative docs with a partial census; use --output-dir for diagnostics", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    write_markdown(static, runtime, out_dir / "delegation_ledger.md")
    write_json(static, runtime, out_dir / "delegation_ledger.json")

    if not args.quiet:
        counts = Counter(_classify_static(si) for si in static.values())
        print(f"Static: {sum(counts.values())} public callable access paths")
        for cls, n in sorted(counts.items()):
            print(f"  {cls:20s} {n:>5}")
        rt_counts = Counter(p.classification for p in runtime)
        print(f"\nRuntime: {len(runtime)} (function, shape) probes")
        for cls, n in sorted(rt_counts.items()):
            print(f"  {cls:35s} {n:>4}")
        print(f"\nWrote {out_dir / 'delegation_ledger.md'}")
        print(f"Wrote {out_dir / 'delegation_ledger.json'}")
    coverage = _census_coverage(runtime)
    print(
        f"INCOMPLETE: {len(coverage['observed'])}/{len(coverage['required'])} dispatchables observed; "
        "per-shape always/never proof and independent verification remain pending", file=sys.stderr
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
