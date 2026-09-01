"""DEMO DATA — a representative subset of NIFTY 50 constituents plus two
indices, with approximate mid-2026 price levels as the random-walk starting
point. This is illustrative seed data for local development, never a live
feed. See MockMarketDataProvider for how prices evolve from here."""

# symbol, name, sector, approx starting price (INR), is_index
SEED_SECURITIES: list[tuple[str, str, str, float, bool]] = [
    ("NIFTY50", "Nifty 50 Index", "Index", 25000.0, True),
    ("BANKNIFTY", "Nifty Bank Index", "Index", 54000.0, True),
    ("RELIANCE", "Reliance Industries", "Energy", 2950.0, False),
    ("TCS", "Tata Consultancy Services", "Information Technology", 4150.0, False),
    ("INFY", "Infosys", "Information Technology", 1850.0, False),
    ("HDFCBANK", "HDFC Bank", "Financials", 1720.0, False),
    ("ICICIBANK", "ICICI Bank", "Financials", 1280.0, False),
    ("AXISBANK", "Axis Bank", "Financials", 1150.0, False),
    ("KOTAKBANK", "Kotak Mahindra Bank", "Financials", 1820.0, False),
    ("SBIN", "State Bank of India", "Financials", 830.0, False),
    ("ITC", "ITC Limited", "Consumer Staples", 460.0, False),
    ("HINDUNILVR", "Hindustan Unilever", "Consumer Staples", 2450.0, False),
    ("TATAMOTORS", "Tata Motors", "Automobiles", 980.0, False),
    ("MARUTI", "Maruti Suzuki", "Automobiles", 12500.0, False),
    ("LT", "Larsen & Toubro", "Industrials", 3600.0, False),
    ("BHARTIARTL", "Bharti Airtel", "Telecommunications", 1650.0, False),
    ("SUNPHARMA", "Sun Pharmaceutical", "Healthcare", 1780.0, False),
    ("ASIANPAINT", "Asian Paints", "Consumer Discretionary", 2900.0, False),
    ("NTPC", "NTPC Limited", "Energy", 380.0, False),
    ("ONGC", "Oil & Natural Gas Corp", "Energy", 265.0, False),
    ("ADANIENT", "Adani Enterprises", "Industrials", 2750.0, False),
    ("WIPRO", "Wipro", "Information Technology", 310.0, False),
]
