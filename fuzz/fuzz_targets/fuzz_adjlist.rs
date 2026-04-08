#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let Ok(input) = std::str::from_utf8(data) else {
        return;
    };

    // Strict mode: must return Err or Ok, never panic.
    let mut strict = fnx_readwrite::EdgeListEngine::strict();
    let _ = strict.read_adjlist(input);

    // Hardened mode: must return Ok with warnings or Ok empty, never panic.
    let mut hardened = fnx_readwrite::EdgeListEngine::hardened();
    let _ = hardened.read_adjlist(input);

    // DiGraph variants.
    let mut strict_di = fnx_readwrite::EdgeListEngine::strict();
    let _ = strict_di.read_digraph_adjlist(input);

    let mut hardened_di = fnx_readwrite::EdgeListEngine::hardened();
    let _ = hardened_di.read_digraph_adjlist(input);
});
