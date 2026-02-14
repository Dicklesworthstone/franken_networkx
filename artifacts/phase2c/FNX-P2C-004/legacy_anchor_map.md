# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-004
- subsystem: Conversion and relabel contracts
- legacy module paths: networkx/convert.py

## Anchor Map
- path: networkx/convert.py
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for conversion and relabel contracts

## Behavior Notes
- deterministic constraints: Conversion precedence is deterministic across input forms; Attribute coercion behavior is deterministic by mode
- compatibility-sensitive edge cases: input precedence drift; relabel contract divergence

## Compatibility Risk
- risk level: critical
- rationale: conversion matrix gate is required to guard compatibility-sensitive behavior.
