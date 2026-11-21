# Historical research terminal · 20 November 2026

Open http://127.0.0.1:8517 or double-click start_dashboard.bat. The desktop installation includes the research database. Leave Synthetic demo switched off for the historical studies. The Windows launcher reopens a running server on port 8517. On a new installation it requires Python 3.11, the Python launcher and internet for dependencies. Closing the server console stops the application. If another application owns port 8517, close that application before restarting the terminal.

## Start a study

1. Open Historical pattern finder. The initial example uses 20 November 2026 at 10:30 IST. Exact five lords searches earlier saved configurations across all saved intraday times. There are eight such records in the supplied archive. Three have a complete 15-minute price outcome. Inspect the timestamps before interpreting the count. The overview separately restricts its count to the selected clock time.
2. Switch to Partial signature, Score range or Angular similarity to change the question. Require matching components, individual ruling-factor classifications or majority as needed. Select the baseline comparison to calculate the frequency over all eligible saved observations. An unpriced astronomical match still appears.
3. Open Build or resume historical configurations for a different clock time, interval, coordinate pair or calendar-date range. A grid represents observation times. A price requires its own market record. The archive stores snapshots in committed batches of 256. Repeating a request fills missing timestamps.
4. Open Daily research to study midnight configurations against the coming session open and subsequent close. The horizon counts observed sessions. Use Historical backtesting for minute prices, a fixed split or monthly expanding training. Use the sidebar study range to load the period of interest.
5. Open Research lab to compare patterns on chronological holdouts. The daily panel compares both models on the same test dates. The lagged variables include momentum, volatility, opening gaps, trend regime and available India VIX observations. The intraday panel uses earlier market information and the signal-time candle close.
6. Data health shows source coverage, import history, session audits and daily CSV import. NIFTY data manager accepts intraday candles. Optional automatic refresh runs every 30 minutes while the terminal is open once enabled in Data health. Upstox minute requests require an activated account and valid token. Optional credential persistence uses Windows Credential Manager.

## Acquisition and coverage

| Dataset | Coverage in this installation | Count |
|---|---|---:|
| NIFTY 50 daily spot index | 3 November 1995 to 19 November 2026 | 7,706 dates |
| NIFTY 50 minute candles | 3 April 2017 to 19 November 2026 | 604,239 candles in 1,613 accepted sessions |
| India VIX daily | 19 July 2010 to 19 November 2026 | 3,475 observations |
| Jaipur KP snapshots | Selected historical times, including daily midnight snapshots, 09:15, 10:30 and quarter hours on observed minute sessions | 61,790 |

Daily records include 7,679 from the PowerNSE mirror of NSE reports and historical index data, 12 additional dates from the official NSE daily archive and 15 flagged secondary NIFTY spot dates. The web historical form and direct range endpoints did not deliver the full archive during collection. Several individual official reports also returned 404. A secondary archive supplied missing observations where available. On overlapping dates tested before adding secondary records, its largest closing-price difference versus the primary series was below 0.001 index points. Source-level agreements on overlaps cannot certify missing dates independently. Daily quotations before launch on 22 April 1996 are identified as pre-launch history (115 records). The archive begins at the base date. Older retrospective history is outside the installed coverage.

The minute source publishes timestamps as IST minute starts. Import compares local timestamps with Unix epoch seconds, checks prices, OHLC bounds and duplicates, then reconciles each session's maximum high and minimum low with primary daily data. Both differences must be at most 0.10 index points. Start labels move forward one minute for close-aligned research. Constituent volume is excluded. 287,239 candidate candles from 770 sessions remain quarantined. Individual quote accuracy is not independently certified. Filtering by full-session data quality makes the tested sample retrospective and can affect performance. There are no admitted minute records before 3 April 2017. Accepted days within the covered years are discontinuous.

Raw files, provider attributions, source conventions, quality and import times are retained. NIFTY 50 uses its historical spot series, including the S&P CNX NIFTY and CNX NIFTY aliases. Recorded exchange dates and observed candles drive market studies. The app does not infer that every missing weekday was a trading day. A complete independently certified historical holiday and special-session calendar remains unavailable. The minute finder requires all minutes across the window. Daily horizons refer to successive available sessions and should be checked against gaps for sensitive studies.

Source snapshots and documentation:

- [PowerNSE archive at the imported revision](https://github.com/inquilabee/powernse/tree/6d3211c7d456c6aa141dff949a5d61289a7d95b4/nse-data)
- [NSE daily report example](https://archives.nseindia.com/content/indices/ind_close_all_19112026.csv)
- [NSE Indices historical reports](https://www.niftyindices.com/reports/historical-data)
- [Secondary daily spot archive](https://github.com/aswinv90/indian-market-historical-data)
- [Minute archive, timestamp specification and licence](https://github.com/technovusin/nifty50-historical-data/tree/bd3248ff0c20dd010f4ad115c1432bfeeda50fc6)
- [Upstox historical candle documentation](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/)

## Verification and results

The previous dashboard provided eight workspaces, a SQLite importer, synthetic demonstrations and chronological intraday evaluation. The original 13 tests passed before the changes. The project backup is baseline-20261120-124619.zip. Production market and astronomy data now use archive/research.duckdb with Parquet snapshots. The original KP engine and original SQLite files are preserved. The CLI remains available.

The original VBA text and Updated_2.xlsm workbook were found in Downloads. All five ruling lords, all seven score components and the final score agreed at every one of the 26 saved workbook times. Workbook SHA-256 is 4eef0205076e8383eb712ff10ac2828dbba5e3572d85421f343a12903acacd98. This checks the saved Excel values on one day. The macros were not executed. The original positive confirmation weights for either majority remain in force. Version identifiers include the engine source hash and Swiss Ephemeris version. Per-body returned calculation flags are stored with each snapshot. Initial daily and 09:15 feature generation for 7,624 dates took 9.3 seconds on this installation. Larger requests depend on the interval and date range.

The daily default study used a score-only pattern, a minimum of 20 prior observations and an expanding annual split beginning in 2016. Across 2,680 held-out sessions through 19 November 2026, it classified 1,371 outcomes correctly (51.2%). The training-mode market baseline classified 1,336 correctly (49.9%). The 95% month-cluster bootstrap interval for the equal-month accuracy advantage was −0.6 to +3.6 percentage points. These data do not establish a reliable edge.

The saved intraday study used 15-minute non-overlapping windows, September–October 2026 training, a 1 November split, score matching, five distinct prior sessions and a two-basis-point round-trip cost. There were 301 matched windows across 14 test sessions. Accuracy was 50.8% versus 43.2% for the training-mode baseline. The hypothetical long/short index-level simulation returned −6.81% net. An index level is not a directly executable security. The short test period and retrospective coverage filter limit interpretation. Both studies are historical held-out exercises. Repeated interactive experiments reuse the holdout and cannot establish independent replication.

All 11 workspaces were exercised with the production archive. Browser interaction verified the daily held-out report. The automated suite includes an offline navigation test, workbook parity when the original file is installed, batch-resume, provider parsing, conflict handling, exact window alignment and purged chronological isolation.

## Evidence and remaining limits

- archive/reports/coverage_by_year.csv and daily_inventory.csv identify the dates and providers used. minute_coverage_by_day.csv and minute_session_audit.csv identify admitted and quarantined sessions. sync_history.csv includes failed attempts.
- archive/reports/daily_walk_forward.csv and intraday_holdout.csv contain individual predictions and outcomes. example_signature_matches.csv preserves the November 20 query.
- Live Upstox access, account entitlements and earliest minute coverage await activation. The official instrument master confirmed NSE_INDEX|Nifty 50, NSE_INDEX segment, INDEX type and exchange token 26000. Production token use and historical repair against an authenticated account remain untested.
- Research on excluded dates needs additional reliable source data. No paid vendor subscription was purchased. Other astrological systems, international indexes and economic/news-event datasets were outside this implementation.

