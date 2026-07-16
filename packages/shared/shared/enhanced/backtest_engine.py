"""Moduler backtest motoru — look-ahead bias olmadan."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class BacktestTrade:
    symbol: str
    side: str
    entry_price: Decimal
    exit_price: Decimal
    net_pnl_usdt: Decimal
    net_roi_pct: Decimal
    regime: str = "UNKNOWN"


@dataclass
class BacktestResult:
    engine_name: str
    strategy_version: str
    total_trades: int = 0
    win_rate: Decimal = Decimal("0")
    net_pnl: Decimal = Decimal("0")
    profit_factor: Decimal = Decimal("0")
    expectancy: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    sharpe_ratio: Decimal = Decimal("0")
    sortino_ratio: Decimal = Decimal("0")
    average_trade: Decimal = Decimal("0")
    average_win: Decimal = Decimal("0")
    average_loss: Decimal = Decimal("0")
    risk_reward: Decimal = Decimal("0")
    consecutive_losses_max: int = 0
    commission_cost: Decimal = Decimal("0")
    funding_cost: Decimal = Decimal("0")
    slippage_cost: Decimal = Decimal("0")
    by_regime: dict[str, Any] = field(default_factory=dict)
    by_symbol: dict[str, Any] = field(default_factory=dict)
    by_direction: dict[str, Any] = field(default_factory=dict)


def simulate_backtest(
    *,
    engine_name: str,
    strategy_version: str,
    candles_by_symbol: dict[str, list[tuple[float, float, float, float]]],
    decision_fn,
    commission_rate: Decimal = Decimal("0.0004"),
    slippage_pct: Decimal = Decimal("0.05"),
) -> BacktestResult:
    """Her mumda yalnizca gecmis veriyi kullanarak karar verir (look-ahead yok)."""
    trades: list[BacktestTrade] = []
    equity = Decimal("0")
    peak = Decimal("0")
    max_dd = Decimal("0")
    consec = 0
    max_consec = 0

    for symbol, candles in candles_by_symbol.items():
        for i in range(60, len(candles) - 1):
            history = candles[: i + 1]
            decision = decision_fn(symbol, history)
            if decision is None:
                continue
            side, entry_idx = decision
            entry = Decimal(str(candles[entry_idx][3]))
            exit_price = Decimal(str(candles[i + 1][3]))
            qty = Decimal("1")
            if side == "LONG":
                gross = (exit_price - entry) * qty
            else:
                gross = (entry - exit_price) * qty
            slip = entry * slippage_pct / Decimal("100") * qty * 2
            comm = entry * commission_rate * qty + exit_price * commission_rate * qty
            net = gross - slip - comm
            trades.append(
                BacktestTrade(symbol=symbol, side=side, entry_price=entry, exit_price=exit_price,
                              net_pnl_usdt=net, net_roi_pct=net / entry * 100 if entry else Decimal("0"))
            )
            equity += net
            peak = max(peak, equity)
            dd = peak - equity
            max_dd = max(max_dd, dd)
            if net <= 0:
                consec += 1
                max_consec = max(max_consec, consec)
            else:
                consec = 0

    wins = [t for t in trades if t.net_pnl_usdt > 0]
    losses = [t for t in trades if t.net_pnl_usdt <= 0]
    gross_profit = sum((t.net_pnl_usdt for t in wins), Decimal("0"))
    gross_loss = abs(sum((t.net_pnl_usdt for t in losses), Decimal("0")))
    pf = gross_profit / gross_loss if gross_loss > 0 else Decimal("0")

    return BacktestResult(
        engine_name=engine_name,
        strategy_version=strategy_version,
        total_trades=len(trades),
        win_rate=Decimal(str(len(wins) / len(trades) * 100)) if trades else Decimal("0"),
        net_pnl=equity,
        profit_factor=pf,
        expectancy=equity / len(trades) if trades else Decimal("0"),
        max_drawdown=max_dd,
        average_trade=equity / len(trades) if trades else Decimal("0"),
        average_win=sum((t.net_pnl_usdt for t in wins), Decimal("0")) / len(wins) if wins else Decimal("0"),
        average_loss=sum((t.net_pnl_usdt for t in losses), Decimal("0")) / len(losses) if losses else Decimal("0"),
        consecutive_losses_max=max_consec,
        commission_cost=sum((t.entry_price * commission_rate + t.exit_price * commission_rate for t in trades), Decimal("0")),
        slippage_cost=sum((t.entry_price * slippage_pct / Decimal("100") * 2 for t in trades), Decimal("0")),
    )
