# Changelog

## [2026.4.24-1] - 2026-04-24

### Added
- General Rules block referencing `gate-runtime-rules.md`.
- README.md with Overview, Core Capabilities, Architecture, Safety, and Risk sections.
- Risk Disclosure section in SKILL.md (transaction irreversibility + AI output disclaimer + minor protection statement).
- Explicit "no execution without confirmation" guard in Security Rules.

### Fixed
- Description typo: `wallet addresses,Account Address` → `wallet/account addresses` (added missing space and normalized casing).
- Description now includes "Use this skill whenever" and "Trigger phrases include" for routing clarity.
- Capability Boundaries table no longer routes "DApp interactions", "x402 payments", and "MCP tool calls" back to this skill — they now correctly point to the MCP-based `gate-dex-wallet` skill.
- Key Design Differences table no longer compares this skill against itself; the right column now correctly references `gate-dex-wallet` (MCP-based).
- "NOT This Skill" misroute rows no longer point to this skill; they now correctly route DApp, x402, on-chain withdraw, and direct MCP tool calls to `gate-dex-wallet`.
- Module Routing and Follow-up Routing tables: relative Markdown links (e.g. `[./references/auth.md](./references/auth.md)`) replaced with inline-code form (`` `references/auth.md` ``) to avoid 404 on the Skills Hub page.

### Changed
- Full Command Reference: Swap commands and Market/Token-data commands removed from this skill's command table and replaced with explicit "out of scope — route to gate-dex-trade-cli / gate-dex-market-cli" notices, matching the existing Module Routing rules.

## [2026.4.23-1] - 2026-04-23

### Added
- Initial skill scaffold for the Gate DEX wallet CLI (pure REST, no MCP).
- Auth: `login` (Gate / Google OAuth Device Flow), `logout`, `status`, `web3-domain`.
- Wallet queries: `balance`, `address`, `tokens` (with chain filter and pagination).
- Transfer & signing: `transfer` (preview), `send` (one-shot), `send-tx`, `sol-tx`, `gas`, `sign-msg`, `sign-tx`.
- Routing references: `references/auth.md`, `references/asset-query.md`, `references/transfer.md`.
- Built-in GV security check-in inside signing commands (no external `tx-checkin` binary).
