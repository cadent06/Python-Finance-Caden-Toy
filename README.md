
A terminal-based stock portfolio tracker. Enter your stocks, and the program pulls live price data from Yahoo Finance to show your gains or losses, analyze indicators, and generate charts.

How It Works
When you run the program, a numbered menu appears. Type a number and press Enter to navigate.
1 – View Portfolio — shows every stock you've added with the current price, today's change, and your total profit or loss since purchase.
2 / 3 – Add or Remove a Stock — enter a ticker symbol (e.g. AAPL), how many shares you own, and what you paid. That information is saved to a local database (portfolio.db) so it's still there next time you run the program.
4 – Analyze a Stock — pulls up to a year of price history and calculates two indicators: moving averages (SMA 20 and SMA 50) to show the trend, and RSI to flag whether a stock looks overbought or oversold. It then saves a chart as a PNG file in the same folder.
5 / 6 – Watchlist — track stocks you don't own yet with live prices.
7 – Quick Scan — type several tickers at once and see their prices and RSI scores side by side in one table.

