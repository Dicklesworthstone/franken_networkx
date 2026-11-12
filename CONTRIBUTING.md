# Contributing to FrankenNetworkX

First off, thank you for considering contributing to FrankenNetworkX! It's people like you that make FrankenNetworkX such a great tool.

## Where do I go from here?

If you've noticed a bug or have a feature request, make sure to check our [issue tracker](https://github.com/doodlestein/franken_networkx/issues) to see if someone else in the community has already created a ticket. If not, go ahead and [make one](https://github.com/doodlestein/franken_networkx/issues/new/choose)!

## Development Setup

1. Clone the repository
2. Install Rust (nightly) via rustup
3. Install Python 3.12+ and `uv`
4. Run `maturin develop` to build the Python bindings

Please read `AGENTS.md` to understand our workflow. We use `br` and `bv` for task triage, and `rch` for remote compilation. All new algorithms MUST implement our Canonical Graph Semantics Engine (CGSE) for strict upstream parity.

## Code Review

All submissions, including submissions by project members, require review. We use GitHub pull requests for this purpose. Consult [GitHub Help](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/about-pull-requests) for more information on using pull requests.

## License

By contributing, you agree that your contributions will be licensed under the project's chosen license.
