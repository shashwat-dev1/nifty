import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useMutation,
} from "@tanstack/react-query";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
} from "@tanstack/react-table";
import {
  Activity,
  Search,
  Database,
  Settings,
  MessageSquare,
  ChartNoAxesCombined,
} from "lucide-react";
const Chart = React.lazy(() => import("./SessionChart"));
import "./style.css";
import { Research, FeedbackForm } from "./Research";
import { Timeline, Import, Lab } from "./Extras";
import * as Accordion from "@radix-ui/react-accordion";
async function api(path: string, body?: any) {
  const r = await fetch(
    "/api/" + path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {},
  );
  const value = await r.json();
  if (!r.ok)
    throw Error(
      typeof value.detail === "string"
        ? value.detail
        : JSON.stringify(value.detail),
    );
  return value;
}
const demo =
  location.pathname.startsWith("/demo") ||
  location.hostname.endsWith(".trycloudflare.com");
const now = () => new Date(Date.now() + 19800000).toISOString().slice(0, 16);
function Table({
  rows,
  onSelect,
}: {
  rows: any[];
  onSelect?: (r: any) => void;
}) {
  const [search, setSearch] = useState("");
  const [sorting, setSorting] = useState<any[]>([]);
  const [visibility, setVisibility] = useState({});
  const columns = React.useMemo(
    () =>
      Object.keys(rows[0] || {}).map((k) => ({
        accessorKey: k,
        header: k.replaceAll("_", " "),
        cell: (info: any) => {
          let v = info.getValue();
          if (k === "timestamp" && v)
            v =
              new Date(new Date(v).getTime() + 19800000)
                .toISOString()
                .slice(0, 19)
                .replace("T", " ") + " IST";
          return v === null
            ? "Unavailable"
            : typeof v === "number"
              ? Number(v.toFixed(5))
              : typeof v === "object"
                ? JSON.stringify(v)
                : String(v);
        },
      })),
    [rows],
  );
  const data = React.useMemo(
    () =>
      rows.filter((r) =>
        JSON.stringify(r).toLowerCase().includes(search.toLowerCase()),
      ),
    [rows, search],
  );
  const table = useReactTable({
    data,
    columns,
    state: { sorting, columnVisibility: visibility },
    onSortingChange: setSorting,
    onColumnVisibilityChange: setVisibility,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });
  return (
    <>
      <div className="tabletools">
        {!demo && (
          <button
            onClick={() => {
              const keys = Object.keys(rows[0] || {});
              const cell = (v: any) =>
                '"' + String(v ?? "").replaceAll('"', '""') + '"';
              const csv = [keys, ...data.map((r) => keys.map((k) => r[k]))]
                .map((row) => row.map(cell).join(","))
                .join("\r\n");
              const a = document.createElement("a");
              a.href = URL.createObjectURL(
                new Blob([csv], { type: "text/csv" }),
              );
              a.download = "local-research.csv";
              a.click();
              URL.revokeObjectURL(a.href);
            }}
          >
            Export local CSV
          </button>
        )}
        <input
          placeholder="Search table…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <details>
          <summary>Columns</summary>
          {table.getAllLeafColumns().map((c) => (
            <label key={c.id}>
              <input
                type="checkbox"
                checked={c.getIsVisible()}
                onChange={c.getToggleVisibilityHandler()}
              />
              {c.id}
            </label>
          ))}
        </details>
      </div>
      <div className="tablewrap">
        <table>
          <thead>
            {table.getHeaderGroups().map((g) => (
              <tr key={g.id}>
                {g.headers.map((h) => (
                  <th key={h.id} onClick={h.column.getToggleSortingHandler()}>
                    {flexRender(h.column.columnDef.header, h.getContext())}
                  </th>
                ))}
                {onSelect && <th>Chart</th>}
                {rows[0]?.planet && <th>Details</th>}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((r) => (
              <tr key={r.id}>
                {r.getVisibleCells().map((c) => (
                  <td
                    className={
                      c.getValue() === "Positive"
                        ? "positive"
                        : c.getValue() === "Negative"
                          ? "negative"
                          : ""
                    }
                    key={c.id}
                  >
                    {flexRender(c.column.columnDef.cell, c.getContext())}
                  </td>
                ))}
                {onSelect && (
                  <td>
                    <button onClick={() => onSelect(r.original)}>
                      View movement ↗
                    </button>
                  </td>
                )}
                {r.original.planet && (
                  <td>
                    <details>
                      <summary>Inspect {r.original.planet}</summary>
                      <pre>{JSON.stringify(r.original, null, 2)}</pre>
                    </details>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <p className="empty">No observations for this selection.</p>
        )}
      </div>
    </>
  );
}
function App() {
  const [page, setPage] = useState("Match explorer");
  const [moment, setMoment] = useState(now());
  const [calculation, setCalculation] = useState<any>();
  const [mode, setMode] = useState("exact");
  const [factors, setFactors] = useState(["moon_star", "moon_sub"]);
  const [planets, setPlanets] = useState(["Moon"]);
  const [start, setStart] = useState("1995-11-03");
  const [end, setEnd] = useState(now().slice(0, 10));
  const [tolerance, setTolerance] = useState(5);
  const [low, setLow] = useState(-30);
  const [high, setHigh] = useState(30);
  const [offset, setOffset] = useState(0);
  const [matches, setMatches] = useState<any>();
  const [selected, setSelected] = useState<any>();
  const [horizon, setHorizon] = useState(15);
  const [notice, setNotice] = useState("");
  const [stats, setStats] = useState<any>();
  const [buildClock, setBuildClock] = useState("10:30");
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [buildStep, setBuildStep] = useState(0);
  const coverage = useQuery({
    queryKey: ["coverage"],
    queryFn: () => api("coverage"),
  });
  const upstox = useQuery({
    queryKey: ["upstox"],
    queryFn: () => api("upstox"),
  });
  const studies = useQuery({
    queryKey: ["studies"],
    queryFn: () => api("studies"),
  });
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api("admin/jobs"),
    enabled: !demo,
    refetchInterval: page === "Data manager" ? 2000 : false,
  });
  const feedback = useQuery({
    queryKey: ["feedback"],
    queryFn: () => api("admin/feedback"),
    enabled: page === "Feedback" && !demo,
  });
  const calculate = useMutation({
    mutationFn: () => api("calculate", { timestamp: moment + ":00+05:30" }),
    onSuccess: (v) => {
      setCalculation(v);
      setMatches(null);
      setSelected(null);
    },
  });
  const find = useMutation({
    mutationFn: (off: number) =>
      api("matches", {
        timestamp: calculation.timestamp,
        start,
        end,
        mode,
        factors,
        planets,
        tolerance,
        minimum: low,
        maximum: high,
        offset: off,
        limit: 25,
      }),
    onSuccess: (v) => {
      setMatches(v);
      setStats(null);
    },
  });
  const invoke = async (path: string, body: any) => {
    try {
      setNotice(JSON.stringify(await api(path, body)));
    } catch (e) {
      setNotice(String(e));
    }
  };
  const summarize = useMutation({
    mutationFn: () =>
      api("statistics", {
        timestamp: calculation.timestamp,
        start,
        end,
        mode,
        factors,
        planets,
        tolerance,
        minimum: low,
        maximum: high,
        horizon,
      }),
    onSuccess: setStats,
  });
  useEffect(() => {
    setMatches(null);
    setSelected(null);
    setStats(null);
  }, [mode, start, end, tolerance, low, high, factors, planets]);
  useEffect(() => {
    setStats(null);
  }, [horizon]);
  useEffect(() => {
    if (demo || !autoRefresh) return;
    const handle = window.setInterval(
      async () => {
        try {
          const active = await api("admin/jobs");
          if (
            Object.values(active).some((v: any) =>
              ["queued", "running"].includes(v.status),
            )
          )
            return;
          await api("admin/sync", {
            start: now().slice(0, 10),
            end: now().slice(0, 10),
          });
          coverage.refetch();
        } catch (e) {
          setNotice(String(e));
        }
      },
      30 * 60 * 1000,
    );
    return () => window.clearInterval(handle);
  }, [autoRefresh]);
  const pages = demo
    ? ["Match explorer", "KP calculator", "Intraday timeline", "Feedback"]
    : [
        "Match explorer",
        "KP calculator",
        "Intraday timeline",
        "Overview",
        "Backtesting",
        "Data manager",
        "Research lab",
        "Settings",
        "Feedback",
      ];
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <Activity /> NIFTY <span>RESEARCH</span>
        </div>
        <p className="small">KP Astro Market Terminal</p>
        <nav>
          {pages.map((p, i) => (
            <button
              className={page === p ? "active" : ""}
              onClick={() => setPage(p)}
              key={p}
            >
              {React.createElement(
                [
                  Search,
                  Activity,
                  ChartNoAxesCombined,
                  Activity,
                  ChartNoAxesCombined,
                  Database,
                  ChartNoAxesCombined,
                  Settings,
                  MessageSquare,
                ][i],
                { size: 17 },
              )}
              {p}
            </button>
          ))}
        </nav>
        <div className="asidefoot">
          Original KP profile
          <br />
          Jaipur · Lahiri · Placidus
          <br />
          Mean nodes · Asia/Kolkata
        </div>
      </aside>
      <main>
        <header>
          <span>
            {demo ? "PRIVATE DEMO · READ ONLY" : "LOCAL RESEARCH WORKSPACE"}
          </span>
          <div>
            <b className="dot" />{" "}
            {coverage.data?.features?.toLocaleString() || "…"} saved
            configurations{" "}
            <span className="badge">
              Upstox {upstox.data?.configured ? "configured" : "disconnected"}
            </span>
          </div>
        </header>
        <div className="content">
          <div className="heading">
            <p className="eyebrow">NIFTY 50 / HISTORICAL RESEARCH</p>
            <h1>
              {page === "Match explorer"
                ? "Historical Planetary Match Explorer"
                : page}
            </h1>
            <p>
              Explore calculated configurations and observed market outcomes.
            </p>
          </div>
          {["Match explorer", "KP calculator", "Intraday timeline"].includes(
            page,
          ) && (
            <>
              <section>
                <div className="controls">
                  <label>
                    Selected date & time · IST
                    <input
                      aria-label="Selected date and time"
                      type="datetime-local"
                      value={moment}
                      onChange={(e) => setMoment(e.target.value)}
                    />
                  </label>
                  <button onClick={() => setMoment(now())}>
                    Current IST time
                  </button>
                  <button
                    className="primary"
                    onClick={() => calculate.mutate()}
                    disabled={calculate.isPending}
                  >
                    {calculate.isPending ? "Calculating…" : "Calculate KP"}
                  </button>
                </div>
                {calculate.error && (
                  <p className="error">{String(calculate.error)}</p>
                )}
              </section>
              {calculation && (
                <>
                  <section>
                    <div className="sectionhead">
                      <h2>Selected planetary positions</h2>
                      <div className="score">
                        {new Date(calculation.timestamp).toLocaleString(
                          "en-IN",
                          { timeZone: "Asia/Kolkata" },
                        )}{" "}
                        IST · KP score <strong>{calculation.kp_score}</strong>
                      </div>
                    </div>
                    <div className="lords">
                      {Object.entries(calculation.ruling_planets).map(
                        ([k, v]) => (
                          <div key={k}>
                            <small>{k.replaceAll("_", " ")}</small>
                            <b>{String(v)}</b>
                          </div>
                        ),
                      )}
                    </div>
                    <Table
                      rows={calculation.rows.map(({ flags, ...r }) => r)}
                    />
                    <Accordion.Root type="single" collapsible>
                      <Accordion.Item value="details">
                        <Accordion.Header>
                          <Accordion.Trigger>
                            Score components and significators
                          </Accordion.Trigger>
                        </Accordion.Header>
                        <Accordion.Content>
                          <Table rows={calculation.ruling_details} />
                          <pre>
                            {JSON.stringify(calculation.components, null, 2)}
                          </pre>
                        </Accordion.Content>
                      </Accordion.Item>
                    </Accordion.Root>
                  </section>
                  {page === "Match explorer" && (
                    <section>
                      <h2>Matching historical configurations</h2>
                      <div className="controls">
                        <label>
                          From
                          <input
                            type="date"
                            value={start}
                            onChange={(e) => setStart(e.target.value)}
                          />
                        </label>
                        <label>
                          Through
                          <input
                            type="date"
                            value={end}
                            onChange={(e) => setEnd(e.target.value)}
                          />
                        </label>
                        <label>
                          Matching method
                          <select
                            value={mode}
                            onChange={(e) => setMode(e.target.value)}
                          >
                            {[
                              "exact",
                              "partial",
                              "sign",
                              "nakshatra",
                              "sub",
                              "score",
                              "longitude",
                            ].map((m) => (
                              <option key={m}>{m}</option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Primary horizon
                          <select
                            value={horizon}
                            onChange={(e) => setHorizon(+e.target.value)}
                          >
                            {[5, 15, 30, 60].map((h) => (
                              <option key={h} value={h}>
                                {h} minutes
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                      {mode === "partial" && (
                        <label>
                          Required lords
                          <select
                            multiple
                            value={factors}
                            onChange={(e) =>
                              setFactors(
                                [...e.target.selectedOptions].map(
                                  (o) => o.value,
                                ),
                              )
                            }
                          >
                            {[
                              "day",
                              "moon_sign",
                              "moon_star",
                              "moon_sub",
                              "lagna",
                            ].map((f) => (
                              <option key={f}>{f}</option>
                            ))}
                          </select>
                        </label>
                      )}
                      {["sign", "nakshatra", "sub", "longitude"].includes(
                        mode,
                      ) && (
                        <label>
                          Planets
                          <select
                            multiple
                            value={planets}
                            onChange={(e) =>
                              setPlanets(
                                [...e.target.selectedOptions].map(
                                  (o) => o.value,
                                ),
                              )
                            }
                          >
                            {calculation.rows.map((p) => (
                              <option key={p.planet}>{p.planet}</option>
                            ))}
                          </select>
                        </label>
                      )}
                      {mode === "longitude" && (
                        <label>
                          Angular tolerance · experimental
                          <input
                            type="number"
                            min="0"
                            max="180"
                            value={tolerance}
                            onChange={(e) => setTolerance(+e.target.value)}
                          />
                        </label>
                      )}
                      {mode === "score" && (
                        <div className="controls">
                          <input
                            aria-label="Minimum score"
                            type="number"
                            value={low}
                            onChange={(e) => setLow(+e.target.value)}
                          />
                          <input
                            aria-label="Maximum score"
                            type="number"
                            value={high}
                            onChange={(e) => setHigh(+e.target.value)}
                          />
                        </div>
                      )}
                      <button
                        className="primary"
                        disabled={find.isPending}
                        onClick={() => {
                          setOffset(0);
                          find.mutate(0);
                        }}
                      >
                        {find.isPending
                          ? "Searching archive…"
                          : "Find historical matches"}
                      </button>
                      {find.error && (
                        <p className="error">{String(find.error)}</p>
                      )}
                    </section>
                  )}
                  {matches && (
                    <>
                      <section>
                        <div className="sectionhead">
                          <h2>
                            {matches.total.toLocaleString()} earlier saved
                            configurations
                          </h2>
                          <span>
                            Showing {offset + 1}–
                            {Math.min(offset + 25, matches.total)}
                          </span>
                        </div>
                        <Table
                          rows={matches.rows.map((r) =>
                            Object.fromEntries(
                              Object.entries(r).filter(([k]) =>
                                [
                                  "timestamp",
                                  "score",
                                  "day",
                                  "moon_sign",
                                  "moon_star",
                                  "moon_sub",
                                  "lagna",
                                  "matched",
                                  "differences",
                                  "category",
                                  "matched_factors",
                                  "market_data",
                                ].includes(k),
                              ),
                            ),
                          )}
                          onSelect={(r) =>
                            setSelected(
                              matches.rows.find(
                                (v) => v.timestamp === r.timestamp,
                              ),
                            )
                          }
                        />
                        <div className="controls">
                          <button
                            disabled={!offset}
                            onClick={() => {
                              setOffset(offset - 25);
                              find.mutate(offset - 25);
                            }}
                          >
                            Previous
                          </button>
                          <button
                            disabled={offset + 25 >= matches.total}
                            onClick={() => {
                              setOffset(offset + 25);
                              find.mutate(offset + 25);
                            }}
                          >
                            Next
                          </button>
                        </div>
                      </section>
                      <section>
                        <h2>Actual historical NIFTY movements</h2>
                        {selected && (
                          <p>
                            Selected occurrence:{" "}
                            {new Date(selected.timestamp).toLocaleString(
                              "en-IN",
                              { timeZone: "Asia/Kolkata" },
                            )}{" "}
                            IST · chart below{" "}
                            <button onClick={() => setSelected(null)}>
                              Clear chart selection
                            </button>
                          </p>
                        )}
                        <p>
                          Observed index close at the signal timestamp. Every
                          forward minute must be available within the same date.
                        </p>
                        <Table
                          rows={matches.rows.map((r) => ({
                            timestamp: r.timestamp,
                            reference: r.reference,
                            price_5: r.price_5,
                            price_15: r.price_15,
                            price_30: r.price_30,
                            price_60: r.price_60,
                            points_5: r.points_5,
                            percent_5: r.return_5,
                            points_15: r.points_15,
                            percent_15: r.return_15,
                            points_30: r.points_30,
                            percent_30: r.return_30,
                            points_60: r.points_60,
                            percent_60: r.return_60,
                            outcome:
                              r["return_" + horizon] == null
                                ? r.reference == null
                                  ? "Intraday NIFTY data unavailable for this date."
                                  : "Forward window incomplete: missing candles or session boundary."
                                : r["return_" + horizon] > 0
                                  ? "Positive"
                                  : r["return_" + horizon] < 0
                                    ? "Negative"
                                    : "Flat",
                            source: r.source,
                            interval_minutes: r.interval_minutes,
                            quality: r.quality,
                          }))}
                          onSelect={(r) =>
                            setSelected(
                              matches.rows.find(
                                (v) => v.timestamp === r.timestamp,
                              ),
                            )
                          }
                        />
                        <button
                          disabled={summarize.isPending}
                          onClick={() => summarize.mutate()}
                        >
                          {summarize.isPending
                            ? "Summarizing all matches…"
                            : "Summarize all matching observations"}
                        </button>
                        {summarize.error && (
                          <p className="error">{String(summarize.error)}</p>
                        )}
                        {stats && (
                          <>
                            <p>
                              Historical observations at {horizon} minutes,
                              across all matching records. Frequency is not a
                              calibrated future probability.
                            </p>
                            <Table rows={[stats]} />
                          </>
                        )}
                      </section>
                    </>
                  )}
                  {page === "Intraday timeline" && (
                    <Timeline
                      api={api}
                      Table={Table}
                      moment={moment}
                      onSelect={setSelected}
                    />
                  )}
                  {selected && (
                    <React.Suspense fallback={<p>Loading chart…</p>}>
                      <Chart selected={selected} horizon={horizon} />
                    </React.Suspense>
                  )}
                </>
              )}
            </>
          )}
          {["Overview", "Data manager", "Settings"].includes(page) && (
            <section>
              <h2>Data coverage</h2>
              <Table rows={coverage.data?.daily || []} />
              <Table rows={coverage.data?.intraday || []} />
              <Table rows={coverage.data?.sources || []} />
              <Table rows={coverage.data?.audit || []} />
              <p>
                Missing sessions within minute coverage:{" "}
                {coverage.data?.missing_sessions} · Dates below 375 bars:{" "}
                {coverage.data?.incomplete_dates} (special sessions may be
                shorter). Last import: {coverage.data?.last_sync}
              </p>
            </section>
          )}
          {["Backtesting", "Research lab", "Overview"].includes(page) && (
            <section>
              <h2>Saved out-of-sample research</h2>
              <p>
                Daily and intraday studies use separate training periods and
                outcomes. These observations require further validation.
              </p>
              <Table
                rows={Object.entries(studies.data || {}).map(([study, v]) => ({
                  study,
                  ...(v as any),
                }))}
              />
            </section>
          )}
          {page === "Data manager" && (
            <section>
              <h2>Archive jobs</h2>
              <label>
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  disabled={!upstox.data?.configured}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                />{" "}
                Refresh current Upstox session every 30 minutes while this tab
                stays open
              </label>
              <div className="controls">
                <label>
                  Start
                  <input
                    type="date"
                    value={start}
                    onChange={(e) => setStart(e.target.value)}
                  />
                </label>
                <label>
                  End
                  <input
                    type="date"
                    value={end}
                    onChange={(e) => setEnd(e.target.value)}
                  />
                </label>
                <label>
                  Daily clock
                  <input
                    type="time"
                    value={buildClock}
                    onChange={(e) => setBuildClock(e.target.value)}
                  />
                </label>
                <label>
                  Sampling
                  <select
                    value={buildStep}
                    onChange={(e) => setBuildStep(+e.target.value)}
                  >
                    {[0, 1, 5, 15, 30].map((n) => (
                      <option key={n} value={n}>
                        {n === 0
                          ? "One time daily"
                          : n + " minute session grid"}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  onClick={() =>
                    invoke("admin/features", {
                      start,
                      end,
                      clock: buildClock,
                      step: buildStep,
                    })
                  }
                >
                  Build or resume configurations
                </button>
                <button
                  onClick={() =>
                    invoke("admin/sync", {
                      start,
                      end,
                      clock: buildClock,
                      step: buildStep,
                    })
                  }
                >
                  Resume Upstox minute download
                </button>
                <button
                  onClick={() => invoke("admin/sync-daily", { start, end })}
                >
                  Resume Upstox daily download
                </button>
                <button
                  onClick={() =>
                    invoke("admin/sync", {
                      start: now().slice(0, 10),
                      end: now().slice(0, 10),
                    })
                  }
                >
                  Refresh current session
                </button>
              </div>
              {Object.entries(jobs.data || {}).map(([id, v]: any) => (
                <p key={id}>
                  {v.status} · {v.done}{" "}
                  <button
                    onClick={() => invoke("admin/jobs/" + id + "/cancel", {})}
                  >
                    Cancel
                  </button>
                </p>
              ))}
            </section>
          )}
          {page === "Data manager" && <Import api={api} />}
          {page === "Research lab" && <Lab api={api} Table={Table} />}
          {page === "Settings" && (
            <section>
              <h2>Original calculation profile</h2>
              <p>
                Jaipur 26.9124° N / 75.7873° E · Lahiri sidereal · Placidus
                houses · Mean lunar nodes
              </p>
              <h2>Upstox connection</h2>
              <p>
                Configure your token using configure_upstox.bat on this
                computer. The token stays in Windows Credential Manager.
              </p>
              <button onClick={() => invoke("admin/upstox/test", {})}>
                Test connection
              </button>
              <button onClick={() => invoke("admin/diagnostics", undefined)}>
                Run original engine diagnostics
              </button>
              <label>
                Accent color
                <input
                  type="color"
                  defaultValue="#62d8b2"
                  onChange={(e) =>
                    document.documentElement.style.setProperty(
                      "--accent",
                      e.target.value,
                    )
                  }
                />
              </label>
            </section>
          )}
          {!demo && page === "Feedback" && (
            <section>
              <h2>Review feedback</h2>
              <Table rows={feedback.data || []} />
            </section>
          )}
          {!demo && page === "Backtesting" && (
            <Research api={api} Table={Table} />
          )}
          {page === "Feedback" && (
            <FeedbackForm api={api} moment={moment} page={page} />
          )}
          {notice && <p role="status">{notice}</p>}
          <footer>
            Research outputs describe rules and historical samples. Future
            market probabilities require independent validation.
          </footer>
        </div>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={new QueryClient()}>
    <App />
  </QueryClientProvider>,
);
