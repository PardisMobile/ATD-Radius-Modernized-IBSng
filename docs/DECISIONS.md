# Architecture Decisions

## ADR-001: Modernize IBSng instead of continuing the Go implementation
Status: accepted.

The project's primary purpose is to modernize IBSng A1.24 while preserving proven behavior. Go is not the core implementation language for this repository.

## ADR-002: IBSng A1.24 is the behavioral reference
Status: accepted.

The reference source is analyzed separately. We preserve domain behavior where it is intentional, while replacing obsolete implementation and deployment details.

## ADR-003: Python 3 core
Status: accepted.

Python is the closest practical modernization path for the existing IBSng core/domain concepts and keeps the implementation maintainable for this project.

## ADR-004: PHP 8+ web panel
Status: accepted.

The web panel remains a separate presentation layer, but its legacy PHP/Smarty implementation is rewritten around a modern ATD design system.

## ADR-005: EAP is first-class
Status: accepted.

EAP support is part of the AAA architecture from the beginning rather than an afterthought.

## ADR-006: No old ATD repository code is imported
Status: accepted.

The previous ATD-Radius repository is historical/reference only. This repository starts clean.