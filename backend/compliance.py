from __future__ import annotations

import re

from backend.models import DISCLAIMER


TRADING_ADVICE_PATTERNS = (
    r"\bshould\s+i\s+(buy|sell|long|short|hold)\b",
    r"\b(should|can)\s+i\s+enter\b",
    r"\b(buy|sell|long|short)\s+(btc|eth)\s+now\b",
    r"\buse\s+\d+x\s+leverage\b",
    r"现在.*(买|卖|做多|做空)",
    r"(该不该|要不要).*(买|卖|做多|做空|持有)",
    r"(买入|卖出|做多|做空|开仓|平仓).*(btc|eth|比特币|以太坊)",
)


REFUSAL_MARKDOWN = f"""# Research Boundary

I can provide a research summary and risk analysis, but I cannot provide personalized financial advice or trading instructions.

You can ask me to analyze market state, recent drivers, risk factors, funding/open interest, news, or on-chain signals for BTC or ETH.

## Disclaimer
{DISCLAIMER}
"""


def is_trading_advice_request(query: str) -> bool:
    lowered = query.lower()
    return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in TRADING_ADVICE_PATTERNS)
