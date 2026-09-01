"""DEMO DATA — illustrative mid-2020s India macro snapshot. Not fetched from
RBI/MOSPI/any live source. code, name, value, unit."""

SEED_INDICATORS: list[tuple[str, str, float, str]] = [
    ("gsec_10y", "10Y G-Sec Yield", 6.5, "%"),
    ("repo_rate", "RBI Repo Rate", 6.0, "%"),
    ("cpi_inflation", "CPI Inflation (YoY)", 4.2, "%"),
    ("gdp_growth", "Real GDP Growth (YoY)", 6.8, "%"),
    ("inr_usd", "INR / USD", 84.5, "INR"),
    ("crude_brent", "Brent Crude", 82.0, "USD/bbl"),
    ("gold", "Gold", 2650.0, "USD/oz"),
]
