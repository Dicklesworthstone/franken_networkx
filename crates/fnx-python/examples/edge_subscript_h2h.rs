//! Head-to-head for edge-attribute lookup - `G.edges[u, v]` and `G[u][v]` - on the worker.
//!
//! br-r37-c1-tjp0g records the worst ratio left in the ready set:
//!
//!     fnx G.edges[u,v] (DiGraph, full)   546.5 ns
//!     nx  G.edges[u,v] (WHOLE CALL)      115.2 ns      -> 0.211x
//!     native get_edge_data ALONE         214.7 ns
//!
//! and names the mechanism: networkx does two dict lookups on strings whose hash is CACHED IN
//! THE OBJECT, while fnx canonicalises the key ("str:{len}:{s}") and probes a
//! `HashMap<String, _>`, SipHashing those bytes on every call. Those numbers are from
//! 2026-08-16 on a different ELF, and the last bead taken from this queue turned out to have
//! been fixed four days earlier, so this re-measures on HEAD before anything is attempted.
//!
//! AXES. Two spellings (`G.edges[u,v]`, the EdgeView subscript, and `G[u][v]`, the adjacency
//! double-subscript) because a spread between sibling spellings on one class means one of them
//! reaches a fast path the other misses. Two classes (Graph, DiGraph) because the bead reports
//! Graph at 0.6793x against DiGraph's 0.211x - a 3x class asymmetry on the same operation is
//! itself a lead. Two key types (str, int) because the named mechanism is STRING
//! canonicalisation, so an int-keyed graph is the control that says whether the cost is really
//! the rehash.
//!
//! Protocol: arms interleaved inside one loop with the order reversed on odd rounds (ABBA),
//! median over rounds, and DUAL A/A nulls - a separately built fnx fixture against the fnx arm
//! and a separately built networkx fixture against the networkx arm. A single-arm null is
//! blind to the failure that matters: 4cbb18f78 null-failed on its networkx arm with a clean
//! fnx arm, and the predecessors run null-failed on its fnx arm with a clean networkx arm.
//! Either way round, the arm being distorted is the one that moves the ratio, so a row is
//! withheld unless BOTH nulls land in band.
//!
//! Results go to STDERR so the remote runner returns them.

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

/// Repo root from CARGO_MANIFEST_DIR so paths resolve on a remote worker where CWD is not
/// the repo, plus the extension this same invocation imports.
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
# The workers have networkx 3.6.1 installed, which is the release users actually have; the
# vendored legacy_networkx_code copy is 3.7rc0.dev0, a DEV PRERELEASE. Default to installed.
_vendored = os.environ.get('FNX_INCUMBENT', 'installed') != 'installed'
_rel = ('python',)
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
        break
"
    )
}

/// The timing loop lives in Python so every arm goes through the identical protocol - the same
/// subscript, the same loop, the same interpreter.
const HARNESS: &str = r#"
import statistics, time
import networkx as nx
import franken_networkx as fnx

import sys as _sys
NX_BUILD = f"{nx.__version__} @ {nx.__file__}"
FNX_EXT = getattr(_sys, "_fnx_ext", "unavailable")

N = 1000
N_LONG = 300      # 2000-char keys: fewer nodes so the fixture build stays bounded

def build_all(cls, keytype):
    """Build ALL FOUR fixtures INTERLEAVED, edge by edge.

    Circulant: every node has out-degree 3, so every probe hits an EXISTING edge and no arm
    measures an exception path (an absent key would time nx raising KeyError, not fnx being
    slow - the absent-key trap from has_node).

    THE INTERLEAVING IS THE POINT AT LONG KEYS. Building the four graphs one after another
    made the previous run in this series read an fnx-arm A/A null of 1.174-1.190 at
    2000-character keys - two content-identical fixtures differing ~18% purely by
    construction order, which withheld every long-key row. Adding each edge to all four
    graphs in turn spreads any allocator or cache drift across the arms instead of
    concentrating it in whichever was built last.
    """
    n = N if keytype == "str3" else N_LONG
    if keytype == "str3":
        names = [f"{i:03d}" for i in range(n)]
    else:
        names = [f"{i:04d}".ljust(2000, "x") for i in range(n)]
    graphs = [getattr(m, cls)() for m in (fnx, nx, fnx, nx)]
    for g in graphs:
        g.add_nodes_from(names)
    pairs = []
    for i in range(n):
        for d in (1, 2, 3):
            u, v = names[i], names[(i + d) % n]
            for g in graphs:
                g.add_edge(u, v, weight=1.0)
            if i % 5 == 0 and d == 1:
                pairs.append((u, v))
    return graphs, pairs

def run_cell(cls, spelling, keytype, rounds=15):
    (fg, ng, fg2, ng2), pairs = build_all(cls, keytype)

    def probe_edges(g):
        ev = g.edges
        def run():
            for u, v in pairs:
                ev[u, v]
        return run

    def probe_adj(g):
        def run():
            for u, v in pairs:
                g[u][v]
        return run

    def probe_ged(g):
        # DECOMPOSITION ARM. `get_edge_data` is the native lookup reached directly, with no
        # EdgeView subscript in front of it. Subtracting it from `edges[u,v]` on the SAME
        # class in the SAME invocation separates the Python wrapper's cost from the native
        # lookup's, which is what decides whether the lever is the class asymmetry (Python
        # body on the directed view) or the lookup itself.
        ged = g.get_edge_data
        def run():
            for u, v in pairs:
                ged(u, v)
        return run

    make = {"edges[u,v]": probe_edges, "G[u][v]": probe_adj}.get(spelling, probe_ged)
    arms = {"fnx": make(fg), "nx": make(ng), "null_f": make(fg2), "null_n": make(ng2)}
    for fn in arms.values():      # warm every arm over the full probe list
        fn()

    samples = {k: [] for k in arms}
    for r in range(rounds):
        order = list(arms) if r % 2 == 0 else list(arms)[::-1]
        for name in order:
            fn = arms[name]
            t = time.perf_counter()
            fn()
            samples[name].append((time.perf_counter() - t) / len(pairs))
    med = {k: statistics.median(v) for k, v in samples.items()}
    return (med["nx"] / med["fnx"], med["null_f"] / med["fnx"], med["null_n"] / med["nx"],
            med["fnx"] * 1e9, med["nx"] * 1e9)

def main():
    rows = []
    for keytype in ("str3", "str2000"):
        for cls in ("Graph", "DiGraph"):
            for spelling in ("edges[u,v]", "G[u][v]", "get_edge_data"):
                ratio, null_f, null_n, fns, nns = run_cell(cls, spelling, keytype)
                rows.append((keytype, cls, spelling, ratio, null_f, null_n, fns, nns))
    return rows
"#;

fn main() {
    Python::initialize();
    Python::attach(|py| {
        py.run(cstring(&preload_source()).as_c_str(), None, None)
            .expect("bootstrap failed");
        let globals = PyDict::new(py);
        py.run(cstring(HARNESS).as_c_str(), Some(&globals), None)
            .expect("harness failed to define");

        let fetch = |name: &str| -> String {
            globals
                .get_item(name)
                .expect("lookup")
                .expect("missing")
                .extract()
                .expect("is a str")
        };
        eprintln!("bench_elf_sha256 {}", self_identity());
        eprintln!("fnx_extension {}", fetch("FNX_EXT"));
        eprintln!("incumbent {}", fetch("NX_BUILD"));
        eprintln!(
            "{:<5} {:<8} {:<14} {:>10} {:>9} {:>9} {:>10} {:>10}",
            "key", "class", "spelling", "nx/fnx", "null fnx", "null nx", "fnx ns", "nx ns"
        );

        let rows = globals
            .get_item("main")
            .expect("main lookup")
            .expect("main missing")
            .call0()
            .expect("harness main() raised");
        for row in rows.try_iter().expect("rows iterable") {
            let row = row.expect("row");
            let get_s = |i: usize| -> String { row.get_item(i).unwrap().extract().unwrap() };
            let get_f = |i: usize| -> f64 { row.get_item(i).unwrap().extract().unwrap() };
            let (key, cls, spelling) = (get_s(0), get_s(1), get_s(2));
            let (ratio, null_f, null_n) = (get_f(3), get_f(4), get_f(5));
            let (fns, nns) = (get_f(6), get_f(7));
            // Both nulls gate the row: whichever arm is distorted is the one that moves the
            // ratio, so a strayed null on EITHER side withholds the number.
            let band = 0.90..=1.10;
            let flag = match (band.contains(&null_f), band.contains(&null_n)) {
                (true, true) => "",
                (true, false) => "  <- NX-ARM NULL OUT OF BAND, withheld",
                (false, true) => "  <- FNX-ARM NULL OUT OF BAND, withheld",
                (false, false) => "  <- BOTH NULLS OUT OF BAND, withheld",
            };
            eprintln!(
                "{key:<5} {cls:<8} {spelling:<14} {ratio:9.3}x {null_f:9.3} {null_n:9.3} {fns:10.1} {nns:10.1}{flag}"
            );
        }
    });
}
