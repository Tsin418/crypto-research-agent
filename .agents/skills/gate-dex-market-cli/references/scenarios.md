# Scenarios — gate-dex-market-cli

Scenario-style examples for review, testing, and publication completeness. All scenarios are read-only and do not move funds.

## Scenario 1: Inspect token price and market cap

**Context**: User has a token contract address on Ethereum and wants the current price, market cap, and 24h volume before deciding whether to track or trade it.

**Prompt Examples**:
- "What is the price and market cap of token 0xdAC17F958D2ee523a2206206994597C13D831ec7 on Ethereum?"
- "Show me USDT info on ETH."

**Expected Behavior**:
1. Run `gate-dex token-info --chain eth --address 0xdAC17F958D2ee523a2206206994597C13D831ec7`.
2. Return a concise table with price, market cap, 24h volume, 24h price change, total supply.
3. Suggest follow-ups: K-line for the same token, token risk audit, or token ranking on the chain.

## Scenario 2: Security audit before swapping an unfamiliar token

**Context**: User mentions a token they discovered on-chain but have never traded. They want to know whether it is safe before swapping.

**Prompt Examples**:
- "Is 0x123...abc on Arbitrum safe to swap?"
- "Run a honeypot check on this token."

**Expected Behavior**:
1. Run `gate-dex token-risk --chain arb --address 0x123...abc`.
2. Surface the audit result faithfully: honeypot check, contract ownership, trading restrictions, liquidity lock status.
3. If any risk flag is set, warn the user explicitly before suggesting a swap; recommend routing the actual swap through `gate-dex-trade-cli`.
4. If the token is too new and audit data is unavailable, clearly state the gap and advise caution rather than fabricating an "all clear" response.

## Scenario 3: Resolve a token address by symbol

**Context**: User knows the token symbol (e.g. "ARB") but not the contract address, and needs the address to query market data.

**Prompt Examples**:
- "What's the contract address for ARB on Arbitrum?"
- "Find USDC on Solana."

**Expected Behavior**:
1. Run `gate-dex swap-tokens --chain arb --search ARB`.
2. Return matching tokens with chain, symbol, and contract address.
3. Offer to chain into `token-info`, `token-risk`, or `kline` using the resolved address.

## Scenario 4: Raw RPC parameter validation (edge case)

**Context**: User asks for an `eth_call` or `eth_getBalance` RPC query but provides parameters that are not a valid JSON array string.

**Prompt Examples**:
- "Run eth_getBalance for 0xMyAddress."
- "Call eth_call with `to=0x...` and `data=0x70a08231...`."

**Expected Behavior**:
1. Construct `--params` as a strict JSON array string before invoking `gate-dex rpc`.
2. If the user-supplied parameters are ambiguous, ask for the missing pieces (address, block tag) rather than guessing.
3. On invalid JSON, surface the CLI error verbatim and re-prompt with a corrected example.
4. Never fabricate balance values; only return what the RPC response provides.

## Scenario 5: New token discovery within a time window

**Context**: User wants to scan recently listed tokens on a specific chain after a given timestamp.

**Prompt Examples**:
- "Show new tokens on Solana after 2026-04-01."
- "What launched on ETH this week?"

**Expected Behavior**:
1. Run `gate-dex new-tokens --chain sol --start 2026-04-01T00:00:00Z` (use RFC3339).
2. Return a list with token symbol, address, creation time.
3. Remind the user that newly listed tokens often lack risk-audit coverage and recommend `token-risk` before any swap.
