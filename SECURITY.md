# Security Policy

## Supported Versions

FrankenNetworkX supports the following versions for security updates.

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it via GitHub Security Advisories or email the maintainers directly. Do not file a public issue for security-related matters.

We aim to acknowledge reports within 48 hours and provide a timeline for remediation.

### Safe by Design
As a Rust-backed project, FrankenNetworkX avoids many memory-safety issues inherent to C/C++ extensions. However, algorithmic complexity attacks (e.g., hash collisions or adversarial graph generation) are within scope for security reports if they bypass the Hardened Mode safeguards.
