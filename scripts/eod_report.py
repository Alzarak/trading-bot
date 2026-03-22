"""End-of-day report generator for autonomous trading bot.

Produces a daily summary dict with P&L, trade counts, win rate, and
biggest winner/loser from the StateStore trade_log and PortfolioTracker.

This module is stateless — EODReportGenerator requires no dependencies
at construction time and can be instantiated before trading begins.
"""
from datetime import date as _date_class

from loguru import logger


class EODReportGenerator:
    """Generates end-of-day trading summaries.

    Stateless — no dependencies at construction. Call generate() with
    live objects at report time.
    """

    def __init__(self) -> None:
        """No-op constructor — class is stateless."""
        pass

    def generate(
        self,
        tracker,
        state_store,
        date: str | None = None,  # noqa: A002 — shadows stdlib, but the param name is correct per spec
    ) -> dict:
        """Generate a complete end-of-day summary.

        Args:
            tracker: PortfolioTracker instance — provides get_daily_pnl().
            state_store: StateStore instance — provides get_trade_history().
            date: ISO date string 'YYYY-MM-DD' to filter trades. Defaults to today.

        Returns:
            Dict with keys:
                date (str), daily_pnl (float), daily_pnl_pct (float),
                total_trades (int), buy_count (int), sell_count (int),
                win_count (int), loss_count (int), win_rate (float),
                biggest_winner (dict|None), biggest_loser (dict|None)
        """
        if date is None:
            date = _today()

        # Fetch P&L from tracker
        pnl_data = tracker.get_daily_pnl()
        daily_pnl = pnl_data["daily_pnl"]
        daily_pnl_pct = pnl_data["daily_pnl_pct"]

        # Fetch trade history and filter to the target date
        all_trades = state_store.get_trade_history(limit=500)
        today_trades = [
            t for t in all_trades
            if str(t.get("logged_at", ""))[:10] == date
        ]

        logger.info(
            "EOD report for {}: {} trades out of {} total",
            date, len(today_trades), len(all_trades),
        )

        # Count buys and sells
        buy_count = sum(1 for t in today_trades if t.get("action") == "BUY")
        sell_count = sum(1 for t in today_trades if t.get("action") == "SELL")
        total_trades = buy_count + sell_count

        # Evaluate wins and losses from SELL trades with P&L
        sell_trades_with_pnl = [
            t for t in today_trades
            if t.get("action") == "SELL" and t.get("pnl") is not None
        ]

        win_count = sum(1 for t in sell_trades_with_pnl if t["pnl"] > 0)
        loss_count = sum(1 for t in sell_trades_with_pnl if t["pnl"] < 0)
        win_rate = win_count / sell_count if sell_count > 0 else 0.0

        # Biggest winner and loser
        biggest_winner: dict | None = None
        biggest_loser: dict | None = None

        if sell_trades_with_pnl:
            winner_trade = max(sell_trades_with_pnl, key=lambda t: t["pnl"])
            loser_trade = min(sell_trades_with_pnl, key=lambda t: t["pnl"])
            biggest_winner = {
                "symbol": winner_trade["symbol"],
                "pnl": winner_trade["pnl"],
            }
            biggest_loser = {
                "symbol": loser_trade["symbol"],
                "pnl": loser_trade["pnl"],
            }

        report = {
            "date": date,
            "daily_pnl": daily_pnl,
            "daily_pnl_pct": daily_pnl_pct,
            "total_trades": total_trades,
            "buy_count": buy_count,
            "sell_count": sell_count,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": win_rate,
            "biggest_winner": biggest_winner,
            "biggest_loser": biggest_loser,
        }

        logger.info(
            "EOD summary: pnl=${:.2f} ({:.2f}%), trades={}, win_rate={:.1f}%",
            daily_pnl, daily_pnl_pct, total_trades, win_rate * 100,
        )

        return report

    def format_text(self, report: dict) -> str:
        """Format a report dict into a human-readable multi-line string.

        Suitable for Slack, email, and log output.

        Args:
            report: Dict returned by generate().

        Returns:
            Multi-line formatted string.
        """
        lines = [
            f"=== End-of-Day Report: {report['date']} ===",
            f"P&L: ${report['daily_pnl']:+.2f} ({report['daily_pnl_pct']:+.2f}%)",
            f"Trades: {report['total_trades']} total | {report['buy_count']} buys | {report['sell_count']} sells",
            f"Win/Loss: {report['win_count']} wins | {report['loss_count']} losses | Win rate: {report['win_rate'] * 100:.1f}%",
        ]

        if report["biggest_winner"] is not None:
            w = report["biggest_winner"]
            lines.append(f"Biggest Winner: {w['symbol']} +${w['pnl']:.2f}")
        else:
            lines.append("Biggest Winner: N/A")

        if report["biggest_loser"] is not None:
            lo = report["biggest_loser"]
            lines.append(f"Biggest Loser: {lo['symbol']} ${lo['pnl']:.2f}")
        else:
            lines.append("Biggest Loser: N/A")

        return "\n".join(lines)


def _today() -> str:
    """Return today's date as ISO string 'YYYY-MM-DD'."""
    return _date_class.today().isoformat()
