#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let Ok(input) = std::str::from_utf8(data) else {
        return;
    };

    // Strict mode: must return Err, never panic.
    let mut strict = fnx_readwrite::EdgeListEngine::strict();
    let _ = strict.read_gml(input);

    // Hardened mode: must return Ok with warnings or Ok empty, never panic.
    let mut hardened = fnx_readwrite::EdgeListEngine::hardened();
    let _ = hardened.read_gml(input);

    // DiGraph variants.
    let mut strict_di = fnx_readwrite::EdgeListEngine::strict();
    let _ = strict_di.read_digraph_gml(input);

    let mut hardened_di = fnx_readwrite::EdgeListEngine::hardened();
    let _ = hardened_di.read_digraph_gml(input);

    // Directed detection helper.
    let mut detect = fnx_readwrite::EdgeListEngine::strict();
    let _ = detect.gml_declares_directed(input);
});
