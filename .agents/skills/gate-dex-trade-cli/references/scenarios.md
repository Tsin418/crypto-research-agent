# Scenarios — gate-dex-trade-cli

Scenario-style examples for review, testing, and publication completeness. All swap-execution scenarios require explicit user confirmation in chat before the `swap` command runs.

## Scenario 1: Same-chain swap of native ETH for USDT

**Context**: User wants to swap a small amount of native ETH for USDT on Ethereum. Token addresses are well-known.

**Prompt Examples**:
- "Swap 0.01 ETH for USDT on Ethereum."
- "Trade ETH to USDT, 0.01."

**Expected Behavior**:
1. Run `gate-dex quote --from-chain 1 --to-chain 1 --from - --to 0xdAC17F958D2ee523a2206206994597C13D831ec7 --amount 0.01`.
2. Display quote (estimated output, price impact, route, fee, slippage default 3%) using the Swap Confirmation template.
3. Wait for explicit "confirm" reply. On "cancel", abort. On "modify", return to parameter collection.
4. After confirmation, run `gate-dex swap --from-chain 1 --to-chain 1 --from - --to 0xdAC17... --amount 0.01`.
5. Display tx hash, etherscan link, order id; surface mandatory trading risk disclosure.

## Scenario 2: Resolve unknown token symbol before quoting

**Context**: User asks to swap into a token by symbol on Arbitrum, but the contract address is not provided.

**Prompt Examples**:
- "Swap 10 USDT for ARB on Arbitrum."
- "Buy ARB with USDT on Arb."

**Expected Behavior**:
1. Run `gate-dex swap-tokens --chain arb --search ARB` to resolve the token address.
2. Confirm the resolved address with the user (avoid acting on the wrong contract).
3. Continue with `quote` and the standard confirmation flow.
4. Recommend `gate-dex token-risk` (via `gate-dex-market-cli`) for unfamiliar tokens before confirmation.

## Scenario 3: Cross-chain bridge ETH (Ethereum) → USDT (Arbitrum)

**Context**: User wants to bridge native ETH from Ethereum to USDT on Arbitrum, sending the proceeds to their existing Arbitrum wallet.

**Prompt Examples**:
- "Bridge 0.1 ETH from Ethereum to USDT on Arbitrum."
- "Cross-chain swap ETH to USDT, target Arbitrum."

**Expected Behavior**:
1. Run `gate-dex bridge-tokens --src-chain eth --dest-chain arb` to confirm the pair is supported.
2. Run `gate-dex quote --from-chain 1 --to-chain 42161 --from - --to 0xFd086bC7... --amount 0.1 --to-wallet 0xUserArbAddress`.
3. Display quote and remind the user that destination arrival is asynchronous.
4. After explicit confirmation, run the corresponding `gate-dex swap` command.
5. Display source-chain tx hash + order id; instruct the user to track destination arrival via `gate-dex swap-detail <order_id>`.
6. Surface mandatory trading risk disclosure including bridge-specific settlement-time and counterparty risk.

## Scenario 4: User cancels at confirmation step

**Context**: After receiving a quote, the user decides not to proceed.

**Prompt Examples**:
- "Cancel" (after seeing the Swap Confirmation block).
- "Don't execute, the price impact is too high."

**Expected Behavior**:
1. Do not run `gate-dex swap`.
2. Echo the cancellation back to the user.
3. Offer alternatives (e.g. higher slippage, different amount, route check) and wait for the next instruction.

## Scenario 5: Slippage adjustment for low-liquidity token

**Context**: User wants to swap into a meme/low-liquidity token and the default 3% slippage is rejected by the quote.

**Prompt Examples**:
- "Swap 50 USDT for $XYZ on BSC, slippage 5%."
- "Increase slippage to 0.1 and try again."

**Expected Behavior**:
1. Re-run `gate-dex quote ... --slippage 0.05` (or the user-specified ratio).
2. Surface higher slippage as a risk and reconfirm with the user before executing.
3. Do not silently raise slippage above what the user explicitly approved.
4. Recommend a `token-risk` audit for the destination token before swapping.
