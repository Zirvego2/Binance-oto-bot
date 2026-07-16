"""Market AI research tests."""

from shared.ai_market_research import validate_market_research_response


def test_market_research_json_schema():
    data = {
        "executive_summary": "BTC yatay seyirde.",
        "market_outlook": "NEUTRAL",
        "confidence_pct": 55,
        "btc_analysis": "RSI notr bolgede.",
        "altcoin_implications": "Altcoinler BTC ile birlikte hareket edebilir.",
        "key_observations": ["Dusuk volatilite"],
        "risk_factors": ["Ani haber akisi"],
        "opportunities": ["Range islemleri"],
        "time_horizon": "INTRADAY",
        "analyst_note": "Dikkatli olun.",
        "disclaimer": "Yatirim tavsiyesi degildir.",
    }
    result = validate_market_research_response(data)
    assert result is not None
    assert result.market_outlook == "NEUTRAL"
    assert result.confidence_pct == 55


def test_market_research_no_trade_language_in_schema():
    from shared.ai_market_research import MARKET_RESEARCH_SYSTEM_PROMPT

    assert "ASLA" in MARKET_RESEARCH_SYSTEM_PROMPT
    assert "emri" in MARKET_RESEARCH_SYSTEM_PROMPT.lower()
