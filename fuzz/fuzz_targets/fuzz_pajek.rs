//! Fuzz target for Pajek (.net) format parser.
//!
//! Tests the native Rust Pajek parser with arbitrary input to find
//! crashes, hangs, and memory safety issues.

#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let Ok(input) = std::str::from_utf8(data) else {
        return;
    };

    // Strict mode: must return Err, never panic.
    let mut strict = fnx_readwrite::EdgeListEngine::strict();
    let _ = strict.read_pajek(input);

    // Hardened mode: must return Ok with warnings or Ok empty, never panic.
    let mut hardened = fnx_readwrite::EdgeListEngine::hardened();
    let _ = hardened.read_pajek(input);

    // DiGraph variants.
    let mut strict_di = fnx_readwrite::EdgeListEngine::strict();
    let _ = strict_di.read_digraph_pajek(input);

    let mut hardened_di = fnx_readwrite::EdgeListEngine::hardened();
    let _ = hardened_di.read_digraph_pajek(input);
});
