//! Fuzz target for the GEXF parser boundary.
#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let Ok(input) = std::str::from_utf8(data) else {
        return;
    };

    let mut strict = fnx_readwrite::EdgeListEngine::strict();
    let _ = strict.read_gexf(input);

    let mut hardened = fnx_readwrite::EdgeListEngine::hardened();
    let _ = hardened.read_gexf(input);

    let mut strict_di = fnx_readwrite::EdgeListEngine::strict();
    let _ = strict_di.read_digraph_gexf(input);

    let mut hardened_di = fnx_readwrite::EdgeListEngine::hardened();
    let _ = hardened_di.read_digraph_gexf(input);

    let mut directed_detector = fnx_readwrite::EdgeListEngine::strict();
    let _ = directed_detector.gexf_declares_directed(input);
});
