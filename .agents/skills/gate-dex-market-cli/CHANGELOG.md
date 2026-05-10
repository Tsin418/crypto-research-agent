# Changelog

## [2026.4.23-2] - 2026-04-23

### Added
- General Rules block referencing `gate-runtime-rules.md`.
- README.md with Overview, Core Capabilities, and Architecture sections.
- `references/scenarios.md` with scenario-style examples covering K-line, token info, token risk, and raw RPC usage.
- Risk Disclosure section in SKILL.md.

### Changed
- Frontmatter `description` now includes "Use this skill whenever" and "Trigger phrases include" for routing clarity.

## [2026.4.23-1] - 2026-04-23

### Added
- Initial skill scaffold for read-only Gate DEX market and token data via the `gate-dex` CLI.
- Commands: `kline`, `liquidity`, `tx-stats`, `token-info`, `token-risk`, `token-rank`, `new-tokens`, `swap-tokens`, `bridge-tokens`, `chain-config`, `rpc`.
