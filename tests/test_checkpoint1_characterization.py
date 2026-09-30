import math

import numpy as np
import pandas as pd

import app


def make_price_frame(
    closes=None,
    volumes=None,
    high_spread=1.01,
    low_spread=0.99,
):
    if closes is None:
        closes = np.linspace(80, 120, 260)
    closes = np.asarray(closes, dtype=float)
    if volumes is None:
        volumes = np.full(len(closes), 1_000_000.0)
    volumes = np.asarray(volumes, dtype=float)
    frame = pd.DataFrame(
        {
            "Open": closes * 0.995,
            "High": closes * high_spread,
            "Low": closes * low_spread,
            "Close": closes,
            "Adj Close": closes,
            "Volume": volumes,
        },
        index=pd.bdate_range("2025-01-01", periods=len(closes)),
    )
    return app.add_indicators(frame, None)


def test_score_ranges_match_reachable_momentum_thresholds():
    data = make_price_frame()
    trend_score, _ = app.score_trend(data)
    technical_score, _ = app.score_technical(data, app.detect_pivot(data))

    assert trend_score <= app.SCORE_RANGES["trend"].maximum
    assert technical_score <= app.SCORE_RANGES["technical"].maximum
    assert app.threshold_is_reachable("trend", app.MOMENTUM_TREND_MIN)
    assert app.MOMENTUM_TREND_MIN == app.SCORE_RANGES["trend"].maximum


def test_momentum_breakout_route_is_reachable_at_max_trend_score():
    assert app.is_momentum_breakout_confirmed(
        action="READY",
        trend_score=7,
        technical_score=8,
        rs_score=8,
        breakout_alert="CONFIRMED BREAKOUT",
        risk_pct=8,
        volume_confirmation="YES",
        extended=False,
        earnings_label="LOW RISK",
    )


def test_rr_score_uses_structural_target_not_planned_two_r():
    entry = 100
    stop = 95

    assert app.calculate_rr_score(entry, stop, 110) == (2.0, "A")
    assert app.calculate_rr_score(entry, stop, None) == (None, "NOT_AVAILABLE")
    assert app.calculate_rr_score(entry, stop, 99) == (None, "NOT_AVAILABLE")


def test_structural_target_can_come_from_measured_move():
    closes = np.linspace(80, 100, 120)
    data = make_price_frame(closes=closes)
    pivot = app.PivotInfo(pivot=100, distance_pct=0, trigger=100.1, label="Near pivot", tests=3)

    target = app.estimate_structural_reward_target(data, 100.1, pivot)

    assert target is not None
    assert target > 100.1


def test_ready_to_trigger_rewards_dry_up_not_breakout_volume():
    closes = np.linspace(90, 100, 80)
    volumes = np.concatenate([np.full(60, 2_000_000.0), np.full(10, 1_200_000.0), np.full(10, 700_000.0)])
    data = make_price_frame(closes=closes, volumes=volumes)
    pivot = app.PivotInfo(pivot=102, distance_pct=2, trigger=102.1, label="Near pivot", tests=3)

    confirmation, note = app.calculate_volume_confirmation(data, "READY", pivot)

    assert confirmation == "YES"
    assert "dry-up" in note.lower()


def test_breakout_confirmed_still_requires_expansion():
    closes = np.linspace(90, 104, 80)
    volumes = np.full(80, 800_000.0)
    data = make_price_frame(closes=closes, volumes=volumes)
    pivot = app.PivotInfo(pivot=102, distance_pct=-2, trigger=102.1, label="Breakout in progress", tests=3)

    confirmation, note = app.calculate_volume_confirmation(data, "READY", pivot)

    assert confirmation == "NO"
    assert "breakout volume" in note.lower()


def test_stale_pivot_guard_blocks_trade_yes():
    closes = np.linspace(80, 120, 260)
    data = make_price_frame(closes=closes)

    assert app.is_stale_pivot_entry(data, "READY", 110)
    assert not app.is_stale_pivot_entry(data, "PULLBACK ENTRY", 110)


def test_missing_data_helpers_are_defensive():
    empty = pd.DataFrame()
    pivot = app.PivotInfo(pivot=np.nan, distance_pct=np.nan, trigger=np.nan, label="Insufficient data", tests=0)

    assert app.classify_setup_state(empty, "READY", pivot) == app.SETUP_FAILED
    assert app.estimate_structural_reward_target(empty, 100, pivot) is None


def test_core_indicator_and_decision_characterization():
    data = make_price_frame()
    pivot = app.detect_pivot(data)
    vcp = app.detect_vcp(data, pivot)
    trend_score, _ = app.score_trend(data)
    technical_score, _ = app.score_technical(data, pivot)
    extended, *_ = app.detect_extension(data)
    action = app.choose_action_label(data, trend_score, technical_score, pivot, vcp, extended)
    entry, stop, risk_pct, target_2r, target_3r, _ = app.build_trade_plan(data, action, pivot)
    tightness_score, _ = app.calculate_tightness(data, vcp)
    market_score, _, _ = app.calculate_market_score({"SPY": data, "QQQ": data, "IWM": data, "SMH": data})
    sector_score, _ = app.calculate_sector_score("AI / Semiconductor", {"SMH": data, "XLK": data})

    assert trend_score >= 0
    assert technical_score >= 0
    assert tightness_score >= 0
    assert market_score >= 0
    assert sector_score >= 0
    assert entry > stop
    assert target_2r > entry
    assert target_3r > target_2r
    assert isinstance(action, str)
    assert isinstance(risk_pct, float)


def test_watchlist_vcp_near_breakout_rule_without_changing_trade_rules():
    pivot = app.PivotInfo(pivot=100, distance_pct=2, trigger=100.1, label="Near pivot", tests=3)

    flag, reason = app.decide_watchlist_flag(
        trade="NO",
        vcp_status="VALID VCP",
        trend_score=7,
        technical_score=7,
        tightness_score=4,
        extended=False,
        risk_pct=11,
        rr_score="B",
        volume_contraction=True,
        pivot=pivot,
        volume_confirmation="NO",
        market_score=3,
        sector_score=2,
        earnings_risk_label="LOW RISK",
    )

    assert flag == "YES"
    assert "risk" in reason.lower() or "volume" in reason.lower()


def test_earnings_risk_blocks_trade_but_can_watch():
    trade, reason = app.decide_trade(
        action="READY",
        technical_score=7,
        trend_score=7,
        final_score=90,
        risk_pct=8,
        rr_score="A",
        extended=False,
        earnings_risk=True,
        volume_confirmation="YES",
    )

    assert trade == "NO"
    assert "earnings" in reason.lower()


def test_hk_market_path_scores_without_network():
    data = make_price_frame()
    score, status, details = app.calculate_hk_market_score({"^HSI": data, "2800.HK": data})

    assert score >= 0
    assert isinstance(status, str)
    assert details


def test_ipo_path_scores_minimal_table():
    row = pd.Series(
        {
            "company": "Example AI Semiconductor",
            "industry": "Technology",
            "offer price": 10,
            "listing date": "2026-01-01",
        }
    )

    scored = app.score_live_ipo(row.to_dict())

    assert "IPO score" in scored
    assert not math.isnan(scored["IPO score"])


class DummyProgress:
    def progress(self, *args, **kwargs):
        return None

    def empty(self):
        return None


def test_us_scan_path_uses_mocked_data_without_live_yfinance(monkeypatch):
    closes = np.linspace(80, 120, 260) + np.sin(np.arange(260)) * 1.5
    data = make_price_frame(closes=closes, volumes=np.full(260, 2_000_000.0))
    raw = data[["Open", "High", "Low", "Close", "Adj Close", "Volume"]].copy()

    def fake_download(tickers, period="18mo"):
        return {ticker: raw.copy() for ticker in tickers}

    monkeypatch.setattr(app, "download_daily_data", fake_download)
    monkeypatch.setattr(app, "download_market_caps", lambda tickers: {ticker: 5_000_000_000 for ticker in tickers})
    monkeypatch.setattr(app, "download_earnings_data", lambda tickers: {ticker: {} for ticker in tickers})
    monkeypatch.setattr(app.st, "progress", lambda *args, **kwargs: DummyProgress())

    results, indicator_data, summary = app.scan_universe(["AAPL"], "Custom Input", 1, 0, 0)

    assert not results.empty
    assert "Trade" in results.columns
    assert "AAPL" in indicator_data
    assert summary["scanned"] == 1


def test_hk_scan_path_uses_mocked_data_without_live_yfinance(monkeypatch):
    closes = np.linspace(80, 120, 260) + np.sin(np.arange(260)) * 1.5
    data = make_price_frame(closes=closes, volumes=np.full(260, 2_000_000.0))
    raw = data[["Open", "High", "Low", "Close", "Adj Close", "Volume"]].copy()

    def fake_download(tickers, period="18mo"):
        return {ticker: raw.copy() for ticker in tickers}

    monkeypatch.setattr(app, "download_daily_data", fake_download)
    monkeypatch.setattr(app, "download_market_caps", lambda tickers: {ticker: 5_000_000_000 for ticker in tickers})
    monkeypatch.setattr(app, "download_earnings_data", lambda tickers: {ticker: {} for ticker in tickers})
    monkeypatch.setattr(app.st, "progress", lambda *args, **kwargs: DummyProgress())

    results, indicator_data, summary = app.scan_universe(["0700.HK"], "HK Pro Market Scan", 1, 0, 0)

    assert not results.empty
    assert "Trade" in results.columns
    assert "0700.HK" in indicator_data
    assert summary["scanned"] == 1
