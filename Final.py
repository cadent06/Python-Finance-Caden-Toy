"""

Features:
  - Add / remove stocks from your portfolio
  - View live prices and daily change
  - See basic technical indicators (RSI, moving averages)
  - Generate a price history chart
  - Save your portfolio to a SQLite database so it persists

Libraries used:
  - yfinance   : download stock price data from Yahoo Finance
  - matplotlib : draw charts
  - sqlite3    : built-in database (no install needed)
  - tabulate   : pretty terminal tables


"""

import sqlite3
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False


## SQL Database
DB_FILE = "portfolio.db"


def db_connect():
    """Open a connection to the database and return it."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row   # lets us use column names like row["ticker"]
    return conn


def db_setup():
    """Create tables if they don't exist yet."""
    conn = db_connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker    TEXT    NOT NULL UNIQUE,
            shares    REAL    NOT NULL,
            buy_price REAL    NOT NULL,
            notes     TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL UNIQUE
        )
    """)
    conn.commit()
    conn.close()


def db_add_stock(ticker, shares, buy_price, notes=""):
    """Add or update a stock in the portfolio."""
    conn = db_connect()
    try:
        conn.execute(
            "INSERT INTO portfolio (ticker, shares, buy_price, notes) VALUES (?,?,?,?)",
            (ticker.upper(), shares, buy_price, notes)
        )
    except sqlite3.IntegrityError:
        # Already exists – update it instead
        conn.execute(
            "UPDATE portfolio SET shares=?, buy_price=?, notes=? WHERE ticker=?",
            (shares, buy_price, notes, ticker.upper())
        )
    conn.commit()
    conn.close()


def db_remove_stock(ticker):
    """Delete a stock from the portfolio."""
    conn = db_connect()
    conn.execute("DELETE FROM portfolio WHERE ticker=?", (ticker.upper(),))
    conn.commit()
    conn.close()


def db_get_portfolio():
    """Return all rows in the portfolio as a list of dicts."""
    conn = db_connect()
    rows = conn.execute("SELECT * FROM portfolio ORDER BY ticker").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_add_watchlist(ticker):
    """Add a ticker to the watchlist."""
    conn = db_connect()
    try:
        conn.execute("INSERT INTO watchlist (ticker) VALUES (?)", (ticker.upper(),))
        conn.commit()
    except sqlite3.IntegrityError:
        pass   # already there
    conn.close()


def db_remove_watchlist(ticker):
    conn = db_connect()
    conn.execute("DELETE FROM watchlist WHERE ticker=?", (ticker.upper(),))
    conn.commit()
    conn.close()


def db_get_watchlist():
    conn = db_connect()
    rows = conn.execute("SELECT ticker FROM watchlist ORDER BY ticker").fetchall()
    conn.close()
    return [r["ticker"] for r in rows]


## Market Data
def get_price_data(ticker, period="6mo"):
    """
    Download historical closing prices for a ticker.
    Returns a pandas Series of closing prices, or None on failure.
    """
    try:
        data = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        if data.empty:
            return None
        close = data["Close"].squeeze()
        return close
    except Exception:
        return None


def get_current_price(ticker):
    """Return just today's closing price as a float."""
    close = get_price_data(ticker, period="5d")
    if close is None:
        return None
    return float(close.iloc[-1])


def get_day_change(ticker):
    """Return (price, dollar change, percent change) vs previous day."""
    close = get_price_data(ticker, period="5d")
    if close is None or len(close) < 2:
        return None, None, None
    price    = float(close.iloc[-1])
    prev     = float(close.iloc[-2])
    change   = price - prev
    pct      = change / prev * 100
    return price, change, pct


# ─────────────────────────────────────────────────────────────────────────────
#  TECHNICAL INDICATORS
# ─────────────────────────────────────────────────────────────────────────────

def calc_sma(prices, window):
    """Simple Moving Average over `window` days."""
    return prices.rolling(window=window).mean()


def calc_rsi(prices, window=14):
    """
    Relative Strength Index (RSI).
    RSI < 30  → oversold  (potential buy signal)
    RSI > 70  → overbought (potential sell signal)
    """
    delta     = prices.diff()
    gains     = delta.clip(lower=0)
    losses    = -delta.clip(upper=0)
    avg_gain  = gains.ewm(com=window - 1, min_periods=window).mean()
    avg_loss  = losses.ewm(com=window - 1, min_periods=window).mean()
    rs        = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def rsi_label(rsi_value):
    """readable interpretation of an RSI value."""
    if rsi_value < 30:
        return "Oversold – possible buy opportunity"
    elif rsi_value > 70:
        return "Overbought – consider taking profits"
    else:
        return "Neutral zone"


## Chart
def draw_chart(ticker, period="6mo"):
    """
    Draw a 2-panel chart:
      Top    – price history with 20-day and 50-day moving averages
      Bottom – RSI with overbought / oversold zones highlighted
    Saves the chart as <TICKER>_chart.png
    """
    close = get_price_data(ticker, period=period)
    if close is None:
        print(f"  Could not fetch data for {ticker}.")
        return

    sma20 = calc_sma(close, 20)
    sma50 = calc_sma(close, 50)
    rsi   = calc_rsi(close)

## colors
    BG     = "#0d1117"
    PANEL  = "#161b22"
    BLUE   = "#58a6ff"
    GREEN  = "#3fb950"
    ORANGE = "#ffa657"
    RED    = "#f85149"
    YELLOW = "#d29922"
    GREY   = "#8b949e"
    WHITE  = "#e6edf3"

    plt.rcParams.update({
        "figure.facecolor": BG, "axes.facecolor": PANEL,
        "axes.edgecolor": GREY, "axes.labelcolor": WHITE,
        "xtick.color": GREY, "ytick.color": WHITE,
        "text.color": WHITE, "grid.color": "#21262d",
        "grid.linestyle": "--", "grid.alpha": 0.5,
        "font.family": "monospace",
    })

    fig = plt.figure(figsize=(14, 8))
    gs  = gridspec.GridSpec(2, 1, height_ratios=[3, 1], hspace=0.08)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)

    # Top panel – price + moving averages
    ax1.plot(close.index, close,  color=WHITE,  lw=1.5, label="Price")
    ax1.plot(close.index, sma20, color=ORANGE, lw=1.2, linestyle="--", label="SMA 20")
    ax1.plot(close.index, sma50, color=BLUE,   lw=1.2, linestyle="--", label="SMA 50")
    ax1.fill_between(close.index, close, alpha=0.05, color=BLUE)
    ax1.set_title(f"  {ticker.upper()}  ·  Price & Moving Averages  ·  {period}",
                  fontsize=13, color=WHITE, fontweight="bold", loc="left", pad=8)
    ax1.set_ylabel("Price ($)")
    ax1.legend(fontsize=9, facecolor=PANEL, edgecolor=GREY, labelcolor=WHITE, loc="upper left")
    ax1.grid(True)
    plt.setp(ax1.get_xticklabels(), visible=False)

    # Bottom panel – RSI
    ax2.plot(rsi.index, rsi, color=YELLOW, lw=1.3, label="RSI (14)")
    ax2.axhline(70, color=RED,   lw=0.8, linestyle=":")
    ax2.axhline(30, color=GREEN, lw=0.8, linestyle=":")
    ax2.axhline(50, color=GREY,  lw=0.5)
    ax2.fill_between(rsi.index, 70, 100, alpha=0.07, color=RED)
    ax2.fill_between(rsi.index, 0,  30,  alpha=0.07, color=GREEN)
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("RSI")
    ax2.legend(fontsize=9, facecolor=PANEL, edgecolor=GREY, labelcolor=WHITE, loc="upper left")
    ax2.grid(True)

    filename = f"{ticker.upper()}_chart.png"
    fig.savefig(filename, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(f"  Chart saved as  {filename}")


# ─────────────────────────────────────────────────────────────────────────────
#  DISPLAY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def print_table(rows, headers):
    """Print a table – uses tabulate if available, otherwise plain text."""
    if HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="simple", numalign="right"))
    else:
        widths = [max(len(str(h)), max((len(str(r[i])) for r in rows), default=0))
                  for i, h in enumerate(headers)]
        fmt = "  ".join(f"{{:<{w}}}" for w in widths)
        print(fmt.format(*headers))
        print("  ".join("-" * w for w in widths))
        for row in rows:
            print(fmt.format(*[str(v) for v in row]))


def color_pnl(value):
    """Return a string with + or – and a simple label."""
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}"


def ask(prompt_text, default=None):
    """Simple input prompt."""
    suffix = f" [{default}]" if default else ""
    return input(f"  > {prompt_text}{suffix}: ").strip()


def separator():
    print("-" * 60)


# ─────────────────────────────────────────────────────────────────────────────
#  MENU ACTIONS
# ─────────────────────────────────────────────────────────────────────────────

def show_portfolio():
    """Fetch live prices for every position and display a P&L table."""
    positions = db_get_portfolio()
    if not positions:
        print("  Your portfolio is empty. Add a stock first (option 1).")
        return

    print("\n  Fetching live prices...\n")
    rows = []
    total_invested = 0
    total_value    = 0

    for p in positions:
        price, change, pct = get_day_change(p["ticker"])
        if price is None:
            price, change, pct = 0, 0, 0

        market_value = price * p["shares"]
        invested     = p["buy_price"] * p["shares"]
        pnl          = market_value - invested
        pnl_pct      = (pnl / invested * 100) if invested else 0

        total_invested += invested
        total_value    += market_value

        rows.append([
            p["ticker"],
            f"{p['shares']}",
            f"${p['buy_price']:.2f}",
            f"${price:.2f}",
            f"{change:+.2f} ({pct:+.1f}%)",
            f"${market_value:,.2f}",
            f"${color_pnl(pnl)} ({color_pnl(pnl_pct)}%)",
        ])

    print_table(rows, ["TICKER", "SHARES", "BUY PRICE", "CURRENT", "DAY CHANGE", "MKT VALUE", "TOTAL P&L"])

    separator()
    total_pnl = total_value - total_invested
    total_pct = (total_pnl / total_invested * 100) if total_invested else 0
    print(f"  Total Invested : ${total_invested:,.2f}")
    print(f"  Portfolio Value: ${total_value:,.2f}")
    print(f"  Total P&L      : ${total_pnl:+,.2f}  ({total_pct:+.2f}%)")
    separator()


def add_stock():
    """Prompt user and add a stock to the portfolio."""
    ticker    = ask("Ticker symbol (e.g. AAPL)").upper()
    if not ticker:
        return
    try:
        shares    = float(ask("Number of shares"))
        buy_price = float(ask("Your purchase price per share ($)"))
    except ValueError:
        print("  Invalid number. Try again.")
        return
    notes = ask("Notes (optional, press Enter to skip)", default="")
    db_add_stock(ticker, shares, buy_price, notes)
    print(f"  Added {shares} shares of {ticker} at ${buy_price:.2f}.")


def remove_stock():
    """Remove a stock from the portfolio."""
    positions = db_get_portfolio()
    if not positions:
        print("  Portfolio is empty.")
        return
    for p in positions:
        print(f"    {p['ticker']}")
    ticker = ask("Ticker to remove").upper()
    db_remove_stock(ticker)
    print(f"  {ticker} removed.")


def analyze_stock():
    """Show technical indicators and optionally draw a chart."""
    ticker = ask("Ticker symbol to analyze").upper()
    period = ask("Time period (1mo / 3mo / 6mo / 1y)", default="6mo")

    print(f"\n  Fetching data for {ticker}...\n")
    close = get_price_data(ticker, period)
    if close is None:
        print("  Could not find data. Check the ticker symbol.")
        return

    price      = float(close.iloc[-1])
    prev_price = float(close.iloc[-2])
    day_chg    = price - prev_price
    day_pct    = day_chg / prev_price * 100

    sma20_val  = float(calc_sma(close, 20).iloc[-1])
    sma50_val  = float(calc_sma(close, 50).iloc[-1])
    rsi_val    = float(calc_rsi(close).iloc[-1])

    separator()
    print(f"  {ticker}  –  Analysis")
    separator()
    print(f"  Current Price :  ${price:.2f}  ({day_chg:+.2f}, {day_pct:+.1f}% today)")
    print(f"  SMA 20-day    :  ${sma20_val:.2f}  {'↑ Price above SMA' if price > sma20_val else '↓ Price below SMA'}")
    print(f"  SMA 50-day    :  ${sma50_val:.2f}  {'↑ Price above SMA' if price > sma50_val else '↓ Price below SMA'}")
    print(f"  RSI (14-day)  :  {rsi_val:.1f}  –  {rsi_label(rsi_val)}")

    # Simple overall signal
    signals = 0
    if price > sma20_val: signals += 1
    if price > sma50_val: signals += 1
    if rsi_val < 50:      signals += 1

    signal_text = ["Bearish lean", "Slightly bearish", "Neutral", "Bullish lean"][min(signals, 3)]
    print(f"\n  Overall signal:  {signal_text}  ({signals}/3 indicators positive)")
    separator()

    chart = ask("Generate chart? (y/n)", default="y")
    if chart.lower() == "y":
        draw_chart(ticker, period)


def show_watchlist():
    """Display the watchlist with live prices."""
    tickers = db_get_watchlist()
    if not tickers:
        print("  Watchlist is empty. Add tickers with option 4.")
        return

    print("\n  Fetching watchlist prices...\n")
    rows = []
    for ticker in tickers:
        price, change, pct = get_day_change(ticker)
        if price:
            rows.append([ticker, f"${price:.2f}", f"{change:+.2f}", f"{pct:+.1f}%"])
        else:
            rows.append([ticker, "N/A", "N/A", "N/A"])

    print_table(rows, ["TICKER", "PRICE", "CHANGE $", "CHANGE %"])


def manage_watchlist():
    """Add or remove tickers from the watchlist."""
    print("\n  1  Add ticker")
    print("  2  Remove ticker")
    choice = ask("Choose")
    if choice == "1":
        ticker = ask("Ticker to add").upper()
        db_add_watchlist(ticker)
        print(f"  {ticker} added to watchlist.")
    elif choice == "2":
        tickers = db_get_watchlist()
        for t in tickers:
            print(f"    {t}")
        ticker = ask("Ticker to remove").upper()
        db_remove_watchlist(ticker)
        print(f"  {ticker} removed.")


def quick_scan():
    """Scan several tickers at once and compare their RSI."""
    raw     = ask("Enter tickers separated by spaces (e.g. AAPL MSFT TSLA)")
    tickers = [t.strip().upper() for t in raw.split() if t.strip()]
    if not tickers:
        return

    print("\n  Scanning...\n")
    rows = []
    for ticker in tickers:
        close = get_price_data(ticker, "1mo")
        if close is None:
            rows.append([ticker, "N/A", "N/A", "N/A", "N/A"])
            continue
        price   = float(close.iloc[-1])
        prev    = float(close.iloc[-2])
        pct     = (price - prev) / prev * 100
        rsi_val = float(calc_rsi(close).iloc[-1])
        sma20v  = float(calc_sma(close, 20).iloc[-1])
        signal  = "BUY?" if rsi_val < 35 else ("SELL?" if rsi_val > 65 else "Neutral")
        rows.append([ticker, f"${price:.2f}", f"{pct:+.1f}%", f"{rsi_val:.0f}", signal])

    print_table(rows, ["TICKER", "PRICE", "DAY %", "RSI", "SIGNAL"])
    separator()

## main loop
def print_banner():
    print()
    print("=" * 60)
    print("   INVESTMENT TRACKER  –  Final Project")
    print("   Data: Yahoo Finance  |  Storage: SQLite")
    print("=" * 60)
    print()


def main():
    db_setup()   # create tables on first run
    print_banner()

    menu = {
        "1": ("View portfolio (live prices + P&L)",  show_portfolio),
        "2": ("Add / update a stock",                add_stock),
        "3": ("Remove a stock",                      remove_stock),
        "4": ("Analyze a stock (RSI, SMA, chart)",   analyze_stock),
        "5": ("View watchlist",                      show_watchlist),
        "6": ("Manage watchlist (add / remove)",     manage_watchlist),
        "7": ("Quick scan – compare multiple stocks",quick_scan),
        "0": ("Exit",                                None),
    }

    while True:
        print("\n  MENU")
        separator()
        for key, (label, _) in menu.items():
            print(f"  {key}  {label}")
        separator()

        choice = ask("Select option")

        if choice not in menu:
            print("  Invalid choice. Enter a number from the menu.")
            continue

        label, action = menu[choice]
        if action is None:
            print("\n  Goodbye!\n")
            break

        print(f"\n  [{label}]")
        separator()
        action()
        input("\n  Press Enter to return to menu...")

if __name__ == "__main__":
    main()