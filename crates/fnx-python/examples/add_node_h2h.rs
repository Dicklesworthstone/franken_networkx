//! Head-to-head for `G.add_node`, run entirely on the worker in one invocation.
//!
//! br-r37-c1-jc9e4. The bead records `add_node`/`add_edge` at 0.46-0.50x vs networkx and a
//! `914.4` ns no-op `add_node` control, and its retry predicate asked for a Rust self-time
//! profile of the per-mutation call entry first. That profile is
//! `add_node_entry_self_time_ladder`; it closes at 1.0000x and priced the eager node
//! attribute-dict materialisation at `+37.4` ns of a `242.7` ns no-op call. Removing it is a
//! SELF-SPEEDUP and therefore maintenance, not a win — this file is what turns it into a
//! claim, by running the LIVE incumbent in the same invocation.
//!
//! THREE CELLS, because the lever only touches one of them and saying so requires measuring
//! all three: a NO-OP add (the node is already present, which is the control the bead
//! anchors on), a FRESH add (new nodes, the case users actually pay for), and an
//! ATTRIBUTED add (which still materialises a dict and must therefore NOT move).
//!
//! Both arms run in ONE process on ONE worker CPU in ONE invocation. Protocol: arms
//! interleaved with the order reversed on odd rounds (ABBA), median over rounds, and an A/A
//! NULL arm built as a SEPARATELY BUILT fnx graph timed through the identical call protocol.
//! A row whose null strays from 1.0 is reported as not quotable rather than quietly used.
//!
//! The extension's provenance is printed as a field: a run that reports
//! STALE-TREE-FALLBACK loaded a peer's `maturin` output rather than a cdylib this
//! invocation built, and its numbers must not be quoted.

use pyo3::prelude::*;
use pyo3::types::PyDict;
use sha2::{Digest, Sha256};
use std::ffi::CString;

fn self_identity() -> String {
    let Ok(path) = std::env::current_exe() else {
        return "unavailable".to_owned();
    };
    let Ok(bytes) = std::fs::read(&path) else {
        return "unavailable".to_owned();
    };
    let mut hasher = Sha256::new();
    hasher.update(&bytes);
    format!("{:x} ({} bytes)", hasher.finalize(), bytes.len())
}

fn cstring(source: &str) -> CString {
    CString::new(source).expect("Python snippets must not contain NUL bytes")
}

/// Bootstrap identical to `public_api_gauntlet`: repo root from CARGO_MANIFEST_DIR so the
/// paths resolve on a remote worker where CWD is not the repo, plus the freshly built
/// extension from this same cargo invocation.
fn preload_source() -> String {
    let repo_root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(std::path::Path::parent)
        .expect("fnx-python crate must live under crates/")
        .to_str()
        .expect("repo path must be UTF-8");
    format!(
        "import importlib.util, os, sys
cwd = {repo_root:?}
# FNX_INCUMBENT=installed drops the vendored oracle from sys.path so `import networkx`
# resolves to whatever is installed on the worker. The vendored copy is 3.7rc0.dev0, a
# DEV PRERELEASE; the README's published claims and the released library users actually
# have are 3.6.1, so the incumbent version is a variable worth isolating rather than
# assuming away.
_vendored = os.environ.get('FNX_INCUMBENT', 'vendored') != 'installed'
_rel = ('crates/fnx-python/examples', 'python')
if _vendored:
    _rel = _rel + ('legacy_networkx_code/networkx', 'legacy_networkx_code')
for rel_path in _rel:
    path = os.path.join(cwd, rel_path)
    if path not in sys.path:
        sys.path.insert(0, path)
available_cpus = sorted(os.sched_getaffinity(0))
if available_cpus:
    os.sched_setaffinity(0, set((available_cpus[-1],)))
    print(f'bench cpu: {{available_cpus[-1]}}', file=sys.stderr)
target_dir = os.environ.get('CARGO_TARGET_DIR') or os.path.join(cwd, 'target')
candidates = [
    os.path.join(target_dir, 'release', 'lib_fnx.so'),
    os.path.join(target_dir, 'release', 'libfnx_python.so'),
    os.path.join(cwd, 'python', 'franken_networkx', '_fnx.abi3.so'),
]
# br-r37-c1-qan46: the third candidate is a TRAP and it used to be silent. The first
# two are cdylibs this cargo invocation built; the third is a checked-in artifact that
# whatever peer last ran `maturin develop` left in the tree, and on a shared checkout
# it is rebuilt under a running measurement (observed: sha 8ff908fc -> 486a2fb4 inside
# nine minutes). Falling through to it means the run measured SOMEBODY ELSE'S BUILD
# while printing a perfectly respectable sha, which is exactly the failure named as
# 'a printed sha is not a checked sha'. The provenance is now reported as a field,
# so a row pasted from this output carries it and cannot be quoted as a
# same-invocation build by accident.
for path in candidates[:2]:
    if os.path.exists(path):
        sys._fnx_ext_provenance = 'built-by-this-invocation'
        break
else:
    sys._fnx_ext_provenance = 'STALE-TREE-FALLBACK (not built by this invocation)'
for path in candidates:
    if os.path.exists(path):
        spec = importlib.util.spec_from_file_location('franken_networkx._fnx', path)
        module = importlib.util.module_from_spec(spec)
        sys.modules['franken_networkx._fnx'] = module
        spec.loader.exec_module(module)
        import hashlib
        with open(path, 'rb') as fh:
            _sha = hashlib.sha256(fh.read()).hexdigest()
        sys._fnx_ext = f'{{path}} sha256={{_sha}}'
        print(f'fnx extension: {{sys._fnx_ext}}', file=sys.stderr)
        print(f'fnx extension provenance: {{sys._fnx_ext_provenance}}', file=sys.stderr)
        break
"
    )
}

/// The timing loop lives in Python so both arms are called through the identical
/// protocol - the same bound-method call, the same loop, the same interpreter.
const HARNESS: &str = r#"
import statistics, time, gc
import networkx as nx
import franken_networkx as fnx

import sys as _sys
NX_BUILD = f"{nx.__version__} @ {nx.__file__}"
FNX_EXT = getattr(_sys, "_fnx_ext", "unavailable")
FNX_PROV = getattr(_sys, "_fnx_ext_provenance", "unknown")

N = 2000

def _prebuilt(mod):
    g = mod.Graph()
    g.add_nodes_from(range(N))
    return g

def run_cell(mod_pair, cell, rounds=21):
    """One cell, both arms plus a separately built A/A null fixture.

    NO-OP re-adds nodes that are already there, so nothing mutates and the call can be
    timed repeatedly - this is the bead's own 914.4 ns control. FRESH builds a new graph
    per timed slot, so it is a MUTATION arm and its allocator state differs every repeat;
    its null is the fragile one and is reported rather than assumed.
    """
    fnx_mod, nx_mod = mod_pair
    probe = list(range(N))
    if cell == "noop":
        fg, ng, fg2 = _prebuilt(fnx_mod), _prebuilt(nx_mod), _prebuilt(fnx_mod)
        arms = {"fnx": lambda: [fg.add_node(k) for k in probe],
                "nx":  lambda: [ng.add_node(k) for k in probe],
                "null":lambda: [fg2.add_node(k) for k in probe]}
    elif cell == "fresh":
        arms = {"fnx": lambda: _fill(fnx_mod, probe),
                "nx":  lambda: _fill(nx_mod, probe),
                "null":lambda: _fill(fnx_mod, probe)}
    else:
        attrs = {"w": 1.0}
        fg, ng, fg2 = _prebuilt(fnx_mod), _prebuilt(nx_mod), _prebuilt(fnx_mod)
        arms = {"fnx": lambda: [fg.add_node(k, **attrs) for k in probe],
                "nx":  lambda: [ng.add_node(k, **attrs) for k in probe],
                "null":lambda: [fg2.add_node(k, **attrs) for k in probe]}

    was = gc.isenabled()
    gc.disable()
    samples = {k: [] for k in arms}
    for r in range(rounds):
        order = list(arms) if r % 2 == 0 else list(arms)[::-1]
        for name in order:
            fn = arms[name]
            t = time.perf_counter()
            fn()
            samples[name].append((time.perf_counter() - t) / len(probe))
    if was:
        gc.enable()
    med = {k: statistics.median(v) for k, v in samples.items()}
    return med["nx"] / med["fnx"], med["null"] / med["fnx"], med["fnx"] * 1e9, med["nx"] * 1e9

def _fill(mod, probe):
    g = mod.Graph()
    for k in probe:
        g.add_node(k)
    return g

def first_touch(mod, built_by):
    """add N nodes, then write ONE attribute on each - the FIRST touch of every node.

    br-r37-c1-jc9e4 made add_node stop materialising an attribute dict, which MOVES that
    allocation from add time to first-read time. br-r37-c1-node-attr-first-touch-
    materialisation-j1o70 measures exactly that first touch at 0.4081x on Graph, so the
    honest question is whether the lever created a new cost class or merely made add_node
    agree with paths that were already lazy.

    built_by is the control axis and it is the whole point. "add_node" graphs are the ones
    the lever changed; "add_edge" graphs reached the lazy mirror BEFORE it, via
    br-r37-c1-89kxg. If the two agree, the lever moved add_node onto an existing path and
    invented nothing; if add_node is worse, it did.
    """
    g = mod.Graph()
    if built_by == "add_node":
        for k in range(N):
            g.add_node(k)
    else:
        for k in range(0, N - 1, 2):
            g.add_edge(k, k + 1)
    t = time.perf_counter()
    for k in range(N):
        g.nodes[k]["w"] = 1
    return (time.perf_counter() - t) / N

def run_first_touch(built_by, rounds=21):
    arms = {"fnx": lambda: first_touch(fnx, built_by),
            "nx":  lambda: first_touch(nx, built_by),
            "null":lambda: first_touch(fnx, built_by)}
    was = gc.isenabled()
    gc.disable()
    samples = {k: [] for k in arms}
    for r in range(rounds):
        order = list(arms) if r % 2 == 0 else list(arms)[::-1]
        for name in order:
            samples[name].append(arms[name]())
    if was:
        gc.enable()
    med = {k: statistics.median(v) for k, v in samples.items()}
    return med["nx"] / med["fnx"], med["null"] / med["fnx"], med["fnx"] * 1e9, med["nx"] * 1e9

def main():
    rows = []
    for cell in ("noop", "fresh", "attr"):
        ratio, null, fns, nns = run_cell((fnx, nx), cell)
        rows.append(("add_node", cell, ratio, null, fns, nns))
    for built_by in ("add_node", "add_edge"):
        ratio, null, fns, nns = run_first_touch(built_by)
        rows.append(("1st-touch", built_by, ratio, null, fns, nns))
    return rows
"#;

fn main() {
    Python::initialize();
    Python::attach(|py| {
        py.run(cstring(&preload_source()).as_c_str(), None, None)
            .expect(
                "bootstrap failed. With FNX_INCUMBENT=installed this is EXPECTED on an \
                 rch worker: the workers have no networkx installed, so the vendored \
                 legacy_networkx_code oracle is the only incumbent available there.",
            );
        let globals = PyDict::new(py);
        py.run(cstring(HARNESS).as_c_str(), Some(&globals), None)
            .expect("harness failed to define");
        let nx_build: String = globals
            .get_item("NX_BUILD")
            .expect("NX_BUILD lookup")
            .expect("NX_BUILD missing")
            .extract()
            .expect("NX_BUILD is a str");

        println!("bench_elf_sha256 {}", self_identity());
        let fnx_ext: String = globals
            .get_item("FNX_EXT")
            .expect("FNX_EXT lookup")
            .expect("FNX_EXT missing")
            .extract()
            .expect("FNX_EXT is a str");
        println!("fnx_extension {fnx_ext}");
        let fnx_prov: String = globals
            .get_item("FNX_PROV")
            .expect("FNX_PROV lookup")
            .expect("FNX_PROV missing")
            .extract()
            .expect("FNX_PROV is a str");
        println!("fnx_extension_provenance {fnx_prov}");
        println!("incumbent {nx_build}");
        println!(
            "{:<9} {:<9} {:>11} {:>9} {:>11} {:>11}",
            "op", "cell", "nx/fnx", "A/A null", "fnx ns", "nx ns"
        );

        let rows = globals
            .get_item("main")
            .expect("main lookup")
            .expect("main missing")
            .call0()
            .expect("harness main() raised");
        for row in rows.try_iter().expect("rows iterable") {
            let row = row.expect("row");
            let key: String = row.get_item(0).unwrap().extract().unwrap();
            let probe: String = row.get_item(1).unwrap().extract().unwrap();
            let ratio: f64 = row.get_item(2).unwrap().extract().unwrap();
            let null: f64 = row.get_item(3).unwrap().extract().unwrap();
            let fns: f64 = row.get_item(4).unwrap().extract().unwrap();
            let nns: f64 = row.get_item(5).unwrap().extract().unwrap();
            let flag = if (0.90..=1.10).contains(&null) {
                ""
            } else {
                "  <- NULL OUT OF BAND, not quotable"
            };
            println!("{key:<9} {probe:<9} {ratio:10.3}x {null:9.3} {fns:10.1} {nns:10.1}{flag}");
        }
    });
}
