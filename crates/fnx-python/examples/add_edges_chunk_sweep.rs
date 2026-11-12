//! Chunk-size sweep for `G.add_edges_from`, run entirely on the worker in one invocation.
//!
//! br-r37-c1-uta2n recorded a **6.84x cliff at chunk size 8**: feeding the same edges in
//! chunks of 7 cost `1679` ns/edge and chunks of 8 cost `15156`, only working back down as
//! k grew and not beating k=7 again until roughly k>=128. That bead closed with the cause
//! OPEN — "I did NOT locate the threshold in source; a grep of the obvious size guards
//! found nothing".
//!
//! The guards exist and the number is 8: `PLAIN_EDGE_BATCH_MIN` and `ATTR_EDGE_BATCH_MIN`
//! in `try_add_plain_edge_batch` / `try_add_attr_edge_batch`, in both `lib.rs` and
//! `digraph.rs`. A bunch shorter than 8 declines the batch and takes the per-edge path; a
//! bunch of exactly 8 takes the batch. That is the stale-constant shape, so this sweep is
//! the phase-split that either convicts it or clears it.
//!
//! NETWORKX IS THE CONTROL, and it is what makes this decidable. networkx has no such
//! threshold, so its ns/edge curve should be SMOOTH across k=7/8. A discontinuity in fnx
//! at exactly the constant's value, with nx smooth through the same point, convicts the
//! guard rather than "small batches are slow".
//!
//! MUTATION WORKLOAD, so expect fragile nulls: every timed slot builds a fresh graph and
//! the allocator sits in a different state on each repeat. A row whose A/A null strays
//! outside 0.90-1.10 is printed as WITHHELD rather than quietly used.

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

/// The timing loop lives in Python so both arms are called through the identical protocol.
const HARNESS: &str = r#"
import statistics, time, gc
import networkx as nx
import franken_networkx as fnx

import sys as _sys
NX_BUILD = f"{nx.__version__} @ {nx.__file__}"
FNX_EXT = getattr(_sys, "_fnx_ext", "unavailable")
FNX_PROV = getattr(_sys, "_fnx_ext_provenance", "unknown")

N = 2000
M = 4000

def _edges(seed=17):
    import random
    rng = random.Random(seed)
    return [(rng.randrange(N), rng.randrange(N)) for _ in range(M)]

EDGES = _edges()

def build(mod, k):
    """Add every edge, in chunks of k, through add_edges_from."""
    g = mod.Graph()
    for i in range(0, len(EDGES), k):
        g.add_edges_from(EDGES[i:i + k])
    return g

def sweep(ks, rounds=11):
    """INTERLEAVED sweep: every round visits every k, and every k times all three arms.

    The first version of this sweep measured each k in its own sequential block. Arms were
    interleaved within a block, but the k values were not interleaved with each other, so
    any host drift over the run was charged unevenly across the CURVE - and the curve is
    the whole result. The incumbent's own spread across that run was 14% (1637 -> 1436
    ns/edge, monotonically falling), which is exactly the signature of drift rather than a
    property of k, since networkx has no chunk-size behaviour to speak of.

    The fleet rule this now follows: sweeps must interleave arms, and an effect is only
    actionable if it exceeds the INCUMBENT'S WITHIN-RUN SPREAD. So the incumbent spread is
    computed and printed as the yardstick rather than left for a reader to reconstruct.

    Order is reversed on odd rounds at BOTH levels (k order and arm order) so no k and no
    arm sits permanently at a favoured position in the round.
    """
    keys = [(k, a) for k in ks for a in ("fnx", "nx", "null")]
    samples = {key: [] for key in keys}
    for k in ks:
        assert build(fnx, k).number_of_edges() == build(nx, k).number_of_edges()
    was = gc.isenabled()
    gc.disable()
    for r in range(rounds):
        korder = list(ks) if r % 2 == 0 else list(ks)[::-1]
        for k in korder:
            arms = {"fnx": lambda k=k: build(fnx, k),
                    "nx":  lambda k=k: build(nx, k),
                    "null":lambda k=k: build(fnx, k)}
            anames = list(arms) if r % 2 == 0 else list(arms)[::-1]
            for name in anames:
                t = time.perf_counter()
                arms[name]()
                samples[(k, name)].append((time.perf_counter() - t) / M)
    if was:
        gc.enable()
    med = {key: statistics.median(v) for key, v in samples.items()}
    return med

def main():
    ks = (4, 6, 7, 8, 9, 12, 16, 32, 64, 128)
    med = sweep(ks)
    nx_vals = [med[(k, "nx")] for k in ks]
    nx_spread = (max(nx_vals) - min(nx_vals)) / min(nx_vals)
    rows = []
    for k in ks:
        f, n, nul = med[(k, "fnx")], med[(k, "nx")], med[(k, "null")]
        rows.append(("chunk", str(k), n / f, nul / f, f * 1e9, n * 1e9))
    # The actionability yardstick, reported as a row so it cannot be omitted from a paste.
    rows.append(("control", "nx-spread", 1.0 + nx_spread, 1.0, nx_spread * 100.0, 0.0))
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
            "sweep", "k", "nx/fnx", "A/A null", "fnx ns/e", "nx ns/e"
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
            let flag = if (0.97..=1.03).contains(&null) {
                ""
            } else {
                "  <- NULL OUT OF BAND, not quotable"
            };
            println!("{key:<9} {probe:<9} {ratio:10.3}x {null:9.3} {fns:10.1} {nns:10.1}{flag}");
        }
    });
}
