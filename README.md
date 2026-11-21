# NIFTY 50 — KP Astro Market Research Terminal

The main application is now React + FastAPI. Double-click **start_app.bat**, then open http://127.0.0.1:8520. The original Streamlit application remains available through **start_dashboard.bat** on port 8517.

Read **CUSTOM_TERMINAL_REPORT.txt** for setup, verified coverage, tests, limitations, and remaining Upstox activation. **PRIVATE_DEMO.md** documents the current read-only sharing workflow. **configure_upstox.bat** stores your token in Windows Credential Manager; never paste it into chat.

The source backup is **migration-baseline.zip**. Historical data remains in archive/research.duckdb; migration does not replace it. The historical research guide remains **HISTORICAL_RESEARCH.md**.

The original v0.1 notes below describe the initial engine release. Statements there about missing data, downloading and evaluation are historical; the custom-terminal report describes the current application.

## Original engine v0.1

Research implementation of **the KP module only**, ported from the uploaded VBA file and Excel macro workbook. This is **not** a trading recommendation and does not establish that astrology predicts prices. No NIFTY historical price data is bundled.

## Verified scope

- Swiss Ephemeris `swe.calc_ut`, Lahiri sidereal mode, **mean** lunar node / derived Ketu, Placidus houses.
- Fixed chart location: Jaipur (26.9124 N, 75.7873 E), matching the uploaded VBA `QUERY_LAT`/`QUERY_LON`.
- Fixed trading timezone: `Asia/Kolkata` (UTC+05:30).
- Same weekday, Moon sign/star/sub lord, and Lagna lord logic; same significator-house union and gain/loss tally.
- Same KP weight cells from `KP_Astrology!B3:B10` and same final `B20` formula.
- **Verified all 26 KP cached score values** against `FullDay_Analysis!U2:U27` in the uploaded workbook on **2026-11-20** (9:15–15:30): 26/26 exact score matches in the current environment.
- Automated unit tests cover lord rules, timezone conversion, day slots, final score formula, one workbook parity reference, forward return computation and split isolation.

**Not implemented:** BNN, Mundane, Parashari engines, macro UI, live feeds, market price downloading, brokerage execution, geopolitical event tagging, parameter optimization. The NIFTY backtester is functional when valid local price CSV data is supplied, but **has not been evaluated on real prices** here.

## Setup

Requires Python 3.10+ (for `zoneinfo`). From this folder:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python cli.py point 2026-11-20T09:15:00+05:30
python cli.py day 2026-11-20 --output kp_day.csv
```

For production-grade ephemeris accuracy/parity, install compatible Swiss Ephemeris data files and configure `KPChart(..., ephe_path='/path/to/ephe')`. Without the full Swiss ephemeris dataset, the library may silently use its built-in Moshier calculation fallback. Record both the code version and ephemeris data version when storing features. Check licensing before commercial use.

## NIFTY historical data requirements

Bring your own **real historical NIFTY 50 index close candles** in a UTF-8 CSV:

```csv
timestamp,close
2026-11-19T09:15:00+05:30,100.00
2026-11-19T09:30:00+05:30,100.10
2026-11-19T09:45:00+05:30,100.05
```

Those numbers illustrate the **format only**; they are invented, not NIFTY prices. Timestamps **must** indicate the *close/end* time of the candle, not its start. Input close values must be positive, numeric, and each timestamp unique. This prototype requires bars exactly at signal and forward-horizon timestamps; it does not interpolate. The 09:15 candle must mean the price **known at 09:15**, not the price at 09:16/09:30. Verify your provider's semantics before use. A common data provider's '09:15' 1-minute candle denotes the **start** of the minute: shift such timestamps forward to the actual bar close or use a documented as-of convention before importing.

To run (e.g. training up to Dec 2023, testing 2024 onward):

```bash
python cli.py backtest --prices path/to/nifty_1minute_CLOSE_TIMESTAMPS.csv --split 2024-01-01 --horizon 15 --step 15 --minimum 10 --output nifty_events.csv --report backtest_report.json
```

The script records the KP signature and score at **each eligible historical bar-close**, then looks for the close **15 minutes later** *on the same session*. It calculates realized forward percentage returns, partitions train/test chronologically and compares each test signature only with training-period records. A strict date split avoids selecting patterns from the test period. Historical matches must meet the minimum frequency to be reported.

## What the model matches

Five lords, serialized as `day|moon_sign|moon_star|moon_sub|lagna`. Example: `Venus|Jupiter|Saturn|Venus|Moon`. This is **categorical KP matching, not an exact whole-solar-system angular recurrence**. Changes to chart location, ayanamsa, house method or node type change the signature/score. The script stores a minimal engine output; for a research database, persist the full `KPChart.calculate()` record, ephemeris version and computed components.

The train/test summary separately shows baseline up frequency, matched-pattern prior up fraction, and observed returns. The 95% Wilson interval is descriptive and **understates uncertainty when overlapping events are correlated**. Never treat observed 8/10 as a calibrated 80% forecast. To estimate net profitability, add spread, slippage, commissions and realistic instrument execution. The NIFTY index itself is not a directly tradable share.

## Next engineering steps

1. Obtain licensed NIFTY 50 1-minute historical index candles with accurate timestamps and corporate/session metadata.
2. Validate the complete *KP components* on more dates and historical chart configurations, not only B20 scores; preserve a versioned fixture table.
3. Introduce independent-event grouping / embargoed walk-forward splits; compute confidence intervals clustered by trading day.
4. Compare to unconditional positive-return rate, intraday seasonal baseline, and straightforward price-only models.
5. Add alternate KP feature matching and angular similarity in an explicitly separate experimental module; avoid choosing hyperparameters by test-set performance.
6. Fix or explicitly version the existing VBA's sign-asymmetry in majority confirmations **only after** verifying the original model; the faithful implementation intentionally preserves it.

## Source traceability

- Uploaded `KP file.txt`: `JulianDay`, `SwePlanetSiderealLong`, `GetSignLord`, `GetNakLord`, `GetSubLord`, `DayLordOf`, `GetCuspsAt`, `PlanetBasicHousesAtJD`, `PlanetKPSignificatorHouses`, `UpdateKPAstrology`.
- Uploaded `.xlsm`: `KP_Astrology!B3:B10` weights; `KP_Astrology!B20` formula; `FullDay_Analysis!U2:U27` parity fixture.
- Parity is for **scores**, not yet full numerical astronomy/house-by-house parity for all dates. No Excel VBA macros were executed.

## Windows dashboard

Install 64-bit Python 3.11 with the Windows Python launcher, then double-click `start_dashboard.bat`. First setup needs internet access. Keep the launcher window open during use. Choose the theme in the Streamlit app menu under Settings.

For a walkthrough, enable **Synthetic demo** in the sidebar and select November 20, 2026 at 09:15 IST. Demo prices live in a separate database. Open KP calculator, select Calculate KP, then Find historical matches. In backtesting, start with a single factor to see how many historical sessions support it. A rare five-factor pattern may have no eligible test observations.

For your own data, switch Synthetic demo off. Open **NIFTY data manager**, upload a licensed historical index CSV, identify the timestamp and close columns and optionally map open, high and low. Set the source timezone and interval. Select the start-label option only when the vendor timestamps candle beginnings. Inspect the preview and gaps, then import. Re-imports skip identical candles and reject conflicting prices atomically. Default validation uses weekday session hours; verify holidays and special sessions against the data provider. Keep distinct special sessions in separate trading dates; the analysis treats an IST date as one session.

The finder searches earlier dates. Backtesting freezes the training sample at the split date, requires distinct training sessions per pattern and skips overlapping positions. Forward returns are percentages. Predictions +1, 0 and −1 mean long, cash and short. Net results deduct a round-trip cost for each position. The research lab uses the sign of the previous bar return, five-bar trailing volatility in 10-basis-point bins, IST hour and opening gap direction. Gap analysis needs a recorded prior session close and opening OHLC. Compare coverage as well as accuracy across rules. The day bootstrap assumes independent sessions. Demo statistics have no financial interpretation.

Use Download CSV beneath a results table. Diagnostics runs the local tests. Historical results depend on your price feed, session labels, ephemeris backend and research choices.
