# Changelog

## [2026.4.24-1] - 2026-04-24

### Added
- General Rules block referencing `gate-runtime-rules.md`.
- README.md with Overview, Core Capabilities, Architecture, Safety, and Risk sections.
- `references/scenarios.md` with scenario-style examples covering same-chain swap, cross-chain bridge, unknown-symbol resolution, and slippage handling.
- Risk Disclosure section in SKILL.md (mandatory trading risk + transaction irreversibility statements).
- Explicit "no execution without confirmation" guard in Security Rules.

### Changed
- Frontmatter `description` now includes "Use this skill whenever" and "Trigger phrases include" for routing clarity.

## [2026.4.23-1] - 2026-04-23

### Added
- Initial skill scaffold for one-shot DEX swaps via the `gate-dex` CLI.
- Commands: `quote`, `swap`, `swap-history`, `swap-detail`, `swap-tokens`, `bridge-tokens`.
- Built-in GV security check-in inside the `swap` command (no external `tx-checkin` binary required).
- EVM multi-chain and Solana support; cross-chain bridge via `--to-wallet`.
