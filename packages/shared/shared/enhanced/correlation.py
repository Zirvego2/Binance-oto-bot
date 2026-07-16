"""Portfoy korelasyon hesabi."""

from __future__ import annotations


def pearson_correlation(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 5:
        return 0.0
    xs = a[-n:]
    ys = b[-n:]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = sum((x - mean_x) ** 2 for x in xs) ** 0.5
    den_y = sum((y - mean_y) ** 2 for y in ys) ** 0.5
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def max_portfolio_correlation(
    candidate_closes: list[float],
    open_positions_closes: dict[str, list[float]],
) -> float:
    if not open_positions_closes:
        return 0.0
    return max(abs(pearson_correlation(candidate_closes, closes)) for closes in open_positions_closes.values())


def correlation_penalty(corr: float, max_corr: float, weight: float) -> float:
    if corr <= max_corr:
        return 0.0
    excess = (corr - max_corr) / max(1 - max_corr, 0.01)
    return min(100.0, excess * 100 * weight)
