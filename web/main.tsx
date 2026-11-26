import React, { useState, useEffect, useMemo } from "react";
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
  Calendar,
  Clock,
  MapPin,
  Zap,
  TrendingUp,
  Layers,
  CheckCircle2,
  Download,
  Lightbulb,
  Radio,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import * as Accordion from "@radix-ui/react-accordion";

import "./style.css";
import { TerminalHeader } from "./TerminalHeader";
import { TerminalTabs } from "./TerminalTabs";
import { AstroSidebar } from "./AstroSidebar";
import { ProjectionChart } from "./ProjectionChart";
import { Research, FeedbackForm } from "./Research";
import { Timeline, Import, Lab } from "./Extras";
import {PaperPredictions} from "./PaperPredictions";
import {DailyTerminal} from "./DailyTerminal";
import {ResearchWorkspace} from "./ResearchWorkspace";
import {OutcomeSummary} from "./OutcomeSummary";
import {
  PLANET_META,
  formatDMS,
  formatSpeed,
} from "./astroUtils";

const Chart = React.lazy(() => import("./SessionChart"));

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

// Generic/Custom table component with financial terminal styling
function Table({
  rows,
  onSelect,
  isPlanetaryTable,
  isHistoricalMatchTable,
  selectedTimestamp,
}: {
  rows: any[];
  onSelect?: (r: any) => void;
  isPlanetaryTable?: boolean;
  isHistoricalMatchTable?: boolean;
  selectedTimestamp?: string;
}) {
  const [search, setSearch] = useState("");
  const [sorting, setSorting] = useState<any[]>([]);
  const [visibility, setVisibility] = useState({});

  const columns = React.useMemo(() => {
    if (!rows.length) return [];
    return Object.keys(rows[0] || {}).map((k) => ({
      accessorKey: k,
      header: k.replaceAll("_", " "),
      cell: (info: any) => {
        let v = info.getValue();
        if (k === "timestamp" && v) {
          try {
            v =
              new Date(new Date(v).getTime() + 19800000)
                .toISOString()
                .slice(0, 19)
                .replace("T", " ") + " IST";
          } catch {}
        }
        return v === null
          ? "Unavailable"
          : typeof v === "number"
            ? Number(v.toFixed(4))
            : typeof v === "object"
              ? JSON.stringify(v)
              : String(v);
      },
    }));
  }, [rows]);

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

  const exportCSV = () => {
    if (!rows.length) return;
    const keys = Object.keys(rows[0] || {});
    const cell = (v: any) =>
      '"' + String(v ?? "").replaceAll('"', '""') + '"';
    const csv = [keys, ...data.map((r) => keys.map((k) => r[k]))]
      .map((row) => row.map(cell).join(","))
      .join("\r\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = "local-research.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="terminal-table-container">
      {/* Table tools strip */}
      <div className="tabletools flex items-center justify-between mb-2 text-xs">
        <div className="flex items-center gap-2">
          {!demo && (
            <button
              type="button"
              className="topbar-btn flex items-center gap-1.5"
              onClick={exportCSV}
            >
              <Download size={11} />
              Export local CSV
            </button>
          )}
          <div className="relative">
            <input
              placeholder="Search table…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="terminal-input text-xs py-1 px-2 w-36"
            />
          </div>
        </div>

        <details className="text-[11px] text-slate-400">
          <summary className="cursor-pointer hover:text-cyan-400">
            Columns ({table.getAllLeafColumns().length})
          </summary>
          <div className="absolute z-20 mt-1 bg-slate-900 border border-slate-700 p-2 rounded shadow-xl max-h-48 overflow-y-auto">
            {table.getAllLeafColumns().map((c) => (
              <label key={c.id} className="flex items-center gap-1.5 py-0.5 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={c.getIsVisible()}
                  onChange={c.getToggleVisibilityHandler()}
                  className="rounded"
                />
                {c.id}
              </label>
            ))}
          </div>
        </details>
      </div>

      <div className="table-scroll-wrap">
        <table className="terminal-data-table">
          <thead>
            {table.getHeaderGroups().map((g) => (
              <tr key={g.id}>
                {isHistoricalMatchTable && <th className="w-8">#</th>}
                {g.headers.map((h) => (
                  <th
                    key={h.id}
                    onClick={h.column.getToggleSortingHandler()}
                    className="cursor-pointer select-none"
                  >
                    <div className="flex items-center gap-1">
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {h.column.getIsSorted() ? (
                        h.column.getIsSorted() === "desc" ? " ▾" : " ▴"
                      ) : null}
                    </div>
                  </th>
                ))}
                {onSelect && <th>Chart</th>}
                {rows[0]?.planet && <th>Details</th>}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((r, rowIndex) => {
              const isSelected = selectedTimestamp && r.original.timestamp === selectedTimestamp;
              return (
                <tr
                  key={r.id}
                  className={isSelected ? "selected-row" : ""}
                >
                  {isHistoricalMatchTable && (
                    <td className="text-slate-500 font-mono text-[10px] w-8">
                      <span className={`inline-block w-2 h-2 rounded-full mr-1 ${isSelected ? "bg-cyan-400" : "bg-slate-700"}`} />
                      {rowIndex + 1}
                    </td>
                  )}
                  {r.getVisibleCells().map((c) => {
                    const colId = c.column.id;
                    const val = c.getValue();

                    // Planet styling
                    if (colId === "planet" && typeof val === "string") {
                      const meta = PLANET_META[val] || { glyph: "●", color: "#38bdf8", label: val };
                      return (
                        <td key={c.id}>
                          <div className="planet-cell" style={{ color: meta.color }}>
                            <span className="planet-glyph">{meta.glyph}</span>
                            <span>{meta.label}</span>
                          </div>
                        </td>
                      );
                    }

                    // Longitude formatting
                    if (colId === "longitude" && typeof val === "number") {
                      const dms = formatDMS(val);
                      return (
                        <td key={c.id} className="font-mono text-xs text-slate-300">
                          {dms.full}
                        </td>
                      );
                    }

                    // Sub-lord highlight
                    if ((colId === "sub" || colId === "moon_sub") && typeof val === "string") {
                      return (
                        <td key={c.id}>
                          <span className="sub-lord-tag">{val.toUpperCase()}</span>
                        </td>
                      );
                    }

                    // Speed formatting
                    if (colId === "speed" && typeof val === "number") {
                      const spdStr = formatSpeed(val, r.original.retrograde);
                      return (
                        <td key={c.id}>
                          <span className="speed-tag">{spdStr}</span>
                        </td>
                      );
                    }

                    // Points/Returns positive/negative class
                    const isPositive =
                      val === "Positive" ||
                      (typeof val === "number" && colId.includes("points") && val > 0) ||
                      (typeof val === "number" && colId.includes("percent") && val > 0) ||
                      (typeof val === "number" && colId.includes("return") && val > 0);

                    const isNegative =
                      val === "Negative" ||
                      (typeof val === "number" && colId.includes("points") && val < 0) ||
                      (typeof val === "number" && colId.includes("percent") && val < 0) ||
                      (typeof val === "number" && colId.includes("return") && val < 0);

                    return (
                      <td
                        key={c.id}
                        className={
                          isPositive
                            ? "positive font-mono"
                            : isNegative
                              ? "negative font-mono"
                              : typeof val === "number"
                                ? "font-mono"
                                : ""
                        }
                      >
                        {colId === "market_data" && val === "Available" ? (
                          <span className="tick-ok-pill">
                            <CheckCircle2 size={12} />
                            Available
                          </span>
                        ) : typeof val === "number" ? (
                          (val > 0 && (colId.includes("point") || colId.includes("percent") || colId.includes("return")) ? "+" : "") +
                          val.toFixed(2)
                        ) : (
                          flexRender(c.column.columnDef.cell, c.getContext())
                        )}
                      </td>
                    );
                  })}

                  {onSelect && (
                    <td>
                      <button
                        type="button"
                        className={`inspect-action-btn ${isSelected ? "active-row" : ""}`}
                        onClick={() => onSelect(r.original)}
                      >
                        View movement ↗
                      </button>
                    </td>
                  )}

                  {r.original.planet && (
                    <td>
                      <details className="text-[11px]">
                        <summary className="text-cyan-400 hover:underline">
                          Inspect {r.original.planet}
                        </summary>
                        <pre className="text-[10px] bg-slate-950 p-2 rounded border border-slate-800 text-slate-300 mt-1 max-w-[240px] overflow-x-auto">
                          {JSON.stringify(r.original, null, 2)}
                        </pre>
                      </details>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>

        {!rows.length && (
          <div className="empty p-6 text-center text-slate-500 font-mono text-xs">
            No observations for this selection.
          </div>
        )}
      </div>
    </div>
  );
}

function App() {
  const [page, setPage] = useState("Daily Research");
  const [moment, setMoment] = useState(now());
  const [calculation, setCalculation] = useState<any>();
  const [mode, setMode] = useState("exact");
  const [historyScope,setHistoryScope]=useState("market");
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
  const openMovement=(row:any)=>{setSelected(row);setPage('Chart detail');window.scrollTo({top:0,behavior:'smooth'});};
  const [horizon, setHorizon] = useState(15);
  const [neutral,setNeutral]=useState(0);
  const [similarity,setSimilarity]=useState(80);
  const [weights,setWeights]=useState([1,1,1,1,1]);
  const [notice, setNotice] = useState("");
  const [stats, setStats] = useState<any>();
  const [buildClock, setBuildClock] = useState("10:30");
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [buildStep, setBuildStep] = useState(0);

  // Queries
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

  // Calculate mutation
  const calculate = useMutation({
    mutationFn: () => api("calculate", { timestamp: moment + ":00+05:30" }),
    onSuccess: (v) => {
      setCalculation(v);
      setMatches(null);
      setSelected(null);
    },
  });

  // Find matches mutation
  const find = useMutation({
    mutationFn: (off: number) =>
      api("matches", {
        timestamp: calculation.timestamp,
        start,
        end,
        mode,similarity,weights,history_scope:historyScope,
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

  const summaryQuery=useQuery({queryKey:['outcome-summary',calculation?.timestamp,matches?.total,mode,factors,planets,start,end,tolerance,low,high,similarity,weights,horizon,neutral],enabled:!!matches&&!!calculation,queryFn:()=>api('statistics',{timestamp:calculation.timestamp,start,end,mode,factors,planets,tolerance,minimum:low,maximum:high,similarity,weights,horizon,neutral,history_scope:historyScope})});
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
        mode,similarity,weights,history_scope:historyScope,
        factors,
        planets,
        tolerance,
        minimum: low,
        maximum: high,
        horizon,neutral,
      }),
    onSuccess: setStats,
  });

  useEffect(() => {
    setMatches(null);
    setSelected(null);
    setStats(null);
  }, [mode, start, end, tolerance, low, high, factors, planets,similarity,weights,historyScope]);

  useEffect(() => {
    setStats(null);
  }, [horizon,neutral]);

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

  // Combined Calculate & Find Action
  const handleCalculateAndFind = async () => {
    try {
      const calcResult = await calculate.mutateAsync();
      setNotice("Calculation complete. Choose matching settings, then search.");
    } catch {}
  };

  const synthesisInsight = "Historical observations require a completed query. Frequencies describe the available sample and do not establish predictive performance.";
  const kpiStats = {avg15:stats?.average_points==null?'Unavailable':stats.average_points.toFixed(2)+' pts',avg15Sub:'Selected horizon only',avg60:'Unavailable',avg60Sub:'No separate 60-minute summary requested',maxExcursion:'Unavailable',downside:'Not calculated',profitFactor:'Unavailable',longShort:'No strategy defined'};

  // Presets handlers
  const handlePreset = (timeStr: string) => {
    const d = moment.slice(0, 10);
    setMoment(`${d}T${timeStr}`);
  };

  return (
    <div className="terminal-shell">
      {/* 1. Top Application Header */}
      <TerminalHeader
        demo={demo}
        coverage={coverage.data}
        upstox={upstox.data}
        onEpochClick={() => setMoment(now())}
        onExportClick={() => {
          if (matches?.rows?.length) {
            const keys = Object.keys(matches.rows[0]);
            const csv = [
              keys.join(","),
              ...matches.rows.map((r: any) =>
                keys.map((k) => JSON.stringify(r[k] ?? "")).join(","),
              ),
            ].join("\n");
            const blob = new Blob([csv], { type: "text/csv" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = "nifty_kp_study.csv";
            a.click();
          } else {
            alert("Calculate and find matches first to export terminal study.");
          }
        }}
        onDocsClick={() => setPage("Settings")}
      />

      {/* 2. Top Navigation Tabs */}
      <TerminalTabs
        activeTab={page === "Chart detail" ? "Chart detail" : page}
        onSelectTab={(tabId) => {
          if (tabId === "Chart detail") {
            if (!selected && matches?.rows?.length) {
              setSelected(matches.rows[0]);
            }
            setPage("Chart detail");
          } else {
            setPage(tabId);
          }
        }}
        demo={demo}
      />

      {/* 3. Main Workspace Layout */}
      <div className="terminal-body-layout">
        {/* Left Sidebar */}
        <AstroSidebar
          calculation={calculation}
          activePage={page}
          onNavigate={(targetPage) => {
            setPage(targetPage);
          }}
          demo={demo}
        />

        {/* Main Center Canvas */}
        <main className="terminal-main-canvas">
          {/* Header breadcrumb & page title */}
          {page === "Match explorer" && (
            <div className="terminal-heading-bar flex items-center justify-between pb-1 border-b border-slate-800/80">
              <div>
                <p className="text-[10px] tracking-wider uppercase text-cyan-400 font-semibold">
                  NIFTY 50 / HISTORICAL RESEARCH
                </p>
                <h1 className="text-base font-bold text-white tracking-wide">
                  Historical Planetary Match Explorer
                </h1>
              </div>

              {demo && (
                <span className="text-[10px] font-mono font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30 px-2 py-0.5 rounded">
                  PRIVATE DEMO · READ ONLY
                </span>
              )}
            </div>
          )}

          {page !== "Match explorer" && page !== "Chart detail" && (
            <div className="terminal-heading-bar flex items-center justify-between pb-1 border-b border-slate-800/80">
              <div>
                <p className="text-[10px] tracking-wider uppercase text-cyan-400 font-semibold">
                  NIFTY 50 / HISTORICAL RESEARCH
                </p>
                <div className="text-base font-bold text-white tracking-wide">
                  {page} Workspace
                </div>
              </div>

              {demo && (
                <span className="text-[10px] font-mono font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30 px-2 py-0.5 rounded">
                  PRIVATE DEMO · READ ONLY
                </span>
              )}
            </div>
          )}

          {/* DEDICATED VIEW: HISTORICAL CHART DETAIL TAB */}
          {page === "Chart detail" && (
            <React.Suspense
              fallback={
                <div className="p-8 text-center text-cyan-400 font-mono text-xs">
                  Loading chart workspace...
                </div>
              }
            >
              {selected || matches?.rows?.[0] ? (
                <Chart
                  selected={selected || matches.rows[0]}
                  horizon={horizon}
                  targetTimestamp={calculation?.timestamp}
                  onBack={() => setPage("Match explorer")}
                  allMatches={matches?.rows || []}
                  onSelectMatch={setSelected}
                />
              ) : (
                <div className="p-12 text-center text-slate-400 font-mono text-xs terminal-card">
                  <p className="mb-3">No historical match selected yet.</p>
                  <button
                    type="button"
                    className="terminal-calc-btn mx-auto"
                    onClick={() => setPage("Match explorer")}
                  >
                    Go to Planetary Match Explorer
                  </button>
                </div>
              )}
            </React.Suspense>
          )}

{!demo&&page==='Prospective Predictions'&&<PaperPredictions Table={Table}/>}
{page==='Daily Research'&&<DailyTerminal Table={Table}/>}
{!demo&&page==='Predictions'&&<ResearchWorkspace daily={false} Table={Table}/>}
{!demo&&page==='Model Evaluation'&&<ResearchWorkspace daily={false} Table={Table}/>} 
          {/* ACTIVE VIEW: PLANETARY MATCH EXPLORER */}
          {page === "Match explorer" && (
            <>
              {/* Top Control Bar Card */}
              <div className="terminal-controls-card">
                {/* Row 1: Date & Time, Coordinates, Presets, Calculate Buttons */}
                <div className="controls-row-top">
                  {/* Date & Time Picker */}
                  <div className="control-item-group">
                    <span className="control-label-tag">DATE &amp; TIME</span>
                    <div className="relative flex items-center">
                      <Calendar
                        size={13}
                        className="absolute left-2.5 text-slate-400 pointer-events-none"
                      />
                      <input
                        aria-label="Selected date and time"
                        type="datetime-local"
                        value={moment}
                        onChange={(e) => setMoment(e.target.value)}
                        className="terminal-input pl-8 text-xs font-mono"
                      />
                    </div>
                    <button
                      type="button"
                      className="preset-pill-btn"
                      onClick={() => setMoment(now())}
                      title="Sync with current IST time"
                    >
                      SYNC
                    </button>
                  </div>

                  {/* Ayanamsa */}
                  <div className="control-item-group">
                    <span className="control-label-tag">AYANAMSA</span>
<span>Original Lahiri · Asia/Kolkata</span>
                  </div>

                  {/* Coordinates */}
                  <div className="coordinate-display">
                    <MapPin size={12} className="text-amber-400" />
                    <span>Jaipur (26.9124° N, 75.7873° E)</span>
                  </div>

                  {/* Presets */}
                  <div className="control-item-group">
                    <span className="control-label-tag">PRESETS:</span>
                    <div className="presets-group">
                      <button
                        type="button"
                        className="preset-pill-btn"
                        onClick={() => handlePreset("09:15")}
                      >
                        Open 09:15
                      </button>
                      <button
                        type="button"
                        className="preset-pill-btn"
                        onClick={() => handlePreset("13:00")}
                      >
                        Euro 13:00
                      </button>
                      <button
                        type="button"
                        className="preset-pill-btn"
                        onClick={() => handlePreset("15:00")}
                      >
                        Close 15:00
                      </button>
                    </div>
                  </div>

                  {/* Calculate KP Action Button */}
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="terminal-calc-btn"
                      onClick={() => calculate.mutate()}
                      disabled={calculate.isPending}
                    >
                      <Zap size={14} className="fill-current" />
                      {calculate.isPending ? "Calculating…" : "Calculate KP"}
                    </button>
                  </div>
                </div>


              </div>

              {calculate.error && (
                <p className="error text-xs font-mono text-rose-400 bg-rose-950/40 p-2 rounded border border-rose-800">
                  {String(calculate.error)}
                </p>
              )}

              {/* Main Two-Column Explorer Grid (Left 58% / Right 42%) */}
              <div className="explorer-two-col-grid">
                {/* Left Column: Planetary & KP Cuspal + Historical Configurations */}
                <div className="explorer-col-left">
                  {/* Panel 1: Planetary & KP Cuspal */}
                  <div className="terminal-card">
                    <div className="card-header-strip">
                      <div className="card-title-group">
                        <Radio size={14} className="text-cyan-400" />
                        <h2 className="card-main-title">
                          Selected planetary positions
                        </h2>
                        {calculation && (
                          <span className="timestamp-pill">
                            {new Date(
                              calculation.timestamp,
                            ).toLocaleDateString("en-IN", {
                              day: "2-digit",
                              month: "short",
                              year: "numeric",
                            }).toUpperCase()}{" "}
                            {new Date(
                              calculation.timestamp,
                            ).toLocaleTimeString("en-IN", {
                              hour: "2-digit",
                              minute: "2-digit",
                              second: "2-digit",
                              hour12: false,
                            })}{" "}
                            IST
                          </span>
                        )}
                      </div>

                      <span className="signature-pill">
                        {calculation?.signature??"No calculation"}
                      </span>
                    </div>

                    {calculation ? (
                      <>
                        <Table
                          rows={calculation.rows.map(
                            ({ flags, ...r }: any) => r,
                          )}
                          isPlanetaryTable={true}
                        />

                        {/* Active RP Set Footer Bar */}
                        <div className="rp-footer-bar">
                          <div className="rp-lords-summary">
                            <span className="text-[10px] text-slate-500 uppercase font-bold">
                              ACTIVE RP SET:
                            </span>
                            <span>
                              Lagna Lord:{" "}
                              <strong>
                                {calculation.ruling_planets?.lagna || "Unavailable"}
                              </strong>
                            </span>
                            <span>|</span>
                            <span>
                              Moon Star:{" "}
                              <strong>
                                {calculation.ruling_planets?.moon_star ||
                                  "Unavailable"}
                              </strong>
                            </span>
                            <span>|</span>
                            <span>
                              Moon Sub: <strong>{calculation.ruling_planets?.moon_sub??'Unavailable'}</strong> · Moon Sign:{" "}
                              <strong>
                                {calculation.ruling_planets?.moon_sign || "Unavailable"}
                              </strong>
                            </span>
                            <span>|</span>
                            <span>
                              Day Lord:{" "}
                              <strong>
                                {calculation.ruling_planets?.day || "Unavailable"}{" "}
                                ({calculation.weekday})
                              </strong>
                            </span>
                          </div>

                          <span className="rp-harmony-badge">
                            Original KP profile
                          </span>
                        </div>

                        {/* Accordion for Components */}
                        <Accordion.Root
                          type="single"
                          collapsible
                          className="border-t border-slate-800 text-xs"
                        >
                          <Accordion.Item value="details">
                            <Accordion.Header>
                              <Accordion.Trigger className="w-full text-left p-2.5 bg-slate-900/60 hover:bg-slate-900 text-slate-400 hover:text-cyan-300 flex justify-between items-center text-[11px]">
                                <span>Score components and significators</span>
                                <span className="text-xs">&darr;</span>
                              </Accordion.Trigger>
                            </Accordion.Header>
                            <Accordion.Content className="p-3 bg-slate-950">
                              <p>{calculation.day_lord_rule}</p><pre>{JSON.stringify(calculation.moon_subdivision,null,2)}</pre><Table rows={calculation.ruling_details} />
                              <pre className="text-[10px] text-slate-400 mt-2 bg-slate-900 p-2 rounded overflow-x-auto">
                                {JSON.stringify(
                                  calculation.components,
                                  null,
                                  2,
                                )}
                              </pre>
                            </Accordion.Content>
                          </Accordion.Item>
                        </Accordion.Root>
                      </>
                    ) : (
                      <div className="p-8 text-center text-slate-500 font-mono text-xs">
                        Click &ldquo;Calculate KP&rdquo; to compute planetary
                        positions and ruling lords.
                      </div>
                    )}
                  </div>

                  {/* Panel 2: Historical Configuration Matches */}
                  <div className="terminal-card">
                    <div className="card-header-strip">
                      <div className="card-title-group">
                        <Layers size={14} className="text-amber-400" />
                        <h2 className="card-main-title">
                          {matches
                            ? `${matches.total} earlier saved configurations`
                            : "Matching historical configurations"}
                        </h2>
                      </div>

                      {/* Search trigger button in header */}
                      <button
                        type="button"
                        className="terminal-calc-btn text-xs py-1 px-3"
                        disabled={find.isPending || !calculation}
                        onClick={() => {
                          setOffset(0);
                          find.mutate(0);
                        }}
                      >
                        <Search size={12} className="inline mr-1" />
                        {find.isPending
                          ? "Searching archive…"
                          : "Find historical matches"}
                      </button>
                    </div>

<div className="historical-search-settings" style={{padding:16,borderBottom:"1px solid #253144"}}>
                {/* Row 2: Criteria Locks, Match Threshold Slider, Database Status */}
                <div className="controls-row-bottom">
<div className="controls">
<div style={{display:'flex',gap:8,flexWrap:'wrap',width:'100%'}} aria-label="Quick matching modes"><button type="button" aria-pressed={mode==='exact'} onClick={()=>setMode('exact')}>Exact match · all five lords</button><button type="button" aria-pressed={mode==='partial'} onClick={()=>setMode('partial')}>Partial match · choose lords</button></div>
<label>Historical universe<select value={historyScope} onChange={e=>setHistoryScope(e.target.value)}><option value="market">Market aligned · actual minute candles</option><option value="astronomical">All astronomical timestamps</option></select></label><p>Market-aligned history requires an actual stored minute candle. Missing sessions are excluded; this is not a complete official exchange calendar.</p><label>Matching method<select aria-label="Matching method" value={mode} onChange={e=>setMode(e.target.value)}>{['exact','partial','sign','nakshatra','pada','star','sub','score','longitude','similarity'].map(m=><option key={m}>{m}</option>)}</select></label>
<label>Search from<input type="date" value={start} onChange={e=>setStart(e.target.value)}/></label><label>Search through<input type="date" value={end} onChange={e=>setEnd(e.target.value)}/></label>
{mode==='partial'&&<fieldset style={{padding:12,border:'1px solid #334155'}}><legend>Required ruling lords</legend><p>Select any combination. Only checked lords are required to match.</p>{['day','moon_sign','moon_star','moon_sub','lagna'].map(k=><label key={k} style={{display:'inline-flex',marginRight:16,gap:6}}><input type="checkbox" checked={factors.includes(k)} onChange={e=>setFactors(e.target.checked?[...factors,k]:factors.filter(v=>v!==k))}/>{k.replaceAll('_',' ')}</label>)}</fieldset>}
{['sign','nakshatra','pada','star','sub','longitude'].includes(mode)&&<label>Selected planets<select multiple value={planets} onChange={e=>setPlanets(Array.from(e.target.selectedOptions,o=>o.value))}>{['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu'].map(k=><option key={k}>{k}</option>)}</select></label>}
{mode==='longitude'&&<label>Angular tolerance degrees<input type="number" min="0" max="180" value={tolerance} onChange={e=>setTolerance(+e.target.value)}/></label>}
{mode==='score'&&<><label>Minimum score<input type="number" value={low} onChange={e=>setLow(+e.target.value)}/></label><label>Maximum score<input type="number" value={high} onChange={e=>setHigh(+e.target.value)}/></label></>}
{mode==='similarity'&&<><label>Minimum weighted similarity %<input type="number" min="0" max="100" value={similarity} onChange={e=>setSimilarity(+e.target.value)}/></label><p>100 × sum of matching ruling-lord weights / sum of all five weights. This is categorical similarity, not positional identity.</p>{['day','moon_sign','moon_star','moon_sub','lagna'].map((k,i)=><label key={k}>{k} weight<input type="number" min="0" value={weights[i]} onChange={e=>setWeights(weights.map((w,j)=>j===i?+e.target.value:w))}/></label>)}</>}
<label>Outcome horizon<select value={horizon} onChange={e=>setHorizon(+e.target.value)}>{[5,15,30,60,120,240].map(h=><option key={h} value={h}>{h} minutes</option>)}</select></label>
<label>Neutral threshold ± percent<input aria-label="Neutral threshold" type="number" min="0" step="0.01" value={neutral} onChange={e=>setNeutral(+e.target.value)}/></label>
</div>
                  {/* Database Count Tag */}
                  <div className="database-status-tag">
                    <span className="db-dot" />
                    <span>
                      Database:{" "}
                      {coverage.data?.features?.toLocaleString() || "Unavailable"}{" "}
                      saved configurations
                    </span>
                  </div>
                </div>
</div>
                    {matches ? (
                      <>
                        <Table
                          rows={matches.rows.map((r: any) => ({
                            timestamp: r.timestamp,
                            kp_signature: [r.day,r.moon_sign,r.moon_star,r.moon_sub,r.lagna].join("|"),
                            similarity: r.similarity??"Not applicable",
                            matching_factors: r.matched_factors || "Unavailable",
                            reference: r.reference != null ? r.reference.toFixed(2) : "--",
                            market_data: r.market_data,
                          }))}
                          onSelect={(r) => {
                            const found = matches.rows.find(
                              (v: any) => v.timestamp === r.timestamp,
                            );
                            openMovement(found);
                          }}
                          isHistoricalMatchTable={true}
                          selectedTimestamp={selected?.timestamp}
                        />

                        {/* Pagination Bar */}
                        <div className="flex items-center justify-between p-2.5 bg-slate-900/80 border-t border-slate-800 text-xs">
                          <span className="text-slate-400 text-[11px]">
                            Showing {offset + 1}&ndash;
                            {Math.min(offset + 25, matches.total)} of{" "}
                            {matches.total} matching configurations
                          </span>
                          <div className="flex items-center gap-1.5">
                            <button
                              type="button"
                              className="topbar-btn text-[11px]"
                              disabled={!offset}
                              onClick={() => {
                                setOffset(offset - 25);
                                find.mutate(offset - 25);
                              }}
                            >
                              Previous
                            </button>
                            <button
                              type="button"
                              className="topbar-btn text-[11px]"
                              disabled={offset + 25 >= matches.total}
                              onClick={() => {
                                setOffset(offset + 25);
                                find.mutate(offset + 25);
                              }}
                            >
                              Next
                            </button>
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="p-8 text-center text-slate-500 font-mono text-xs">
                        {calculation
                          ? "Click 'Find historical matches' to query earlier matches."
                          : "Calculate KP first to search historical matches."}
                      </div>
                    )}
                  </div>
                </div>

                {/* Right Column: Forward Price Impact & Win-Rate */}
                <div className="explorer-col-right">
                  <div className="terminal-card">
                    <div className="card-header-strip">
                      <div className="card-title-group">
                        <TrendingUp size={14} className="text-teal-400" />
                        <span className="card-main-title">
                          Observed forward movements
                        </span>
                      </div>
                    </div>

                    <div className="winrate-panel-body"><OutcomeSummary stats={matches?summaryQuery.data:undefined} busy={!!matches&&summaryQuery.isFetching} error={summaryQuery.error} mode={mode} factors={factors} calculation={calculation} horizon={horizon} neutral={neutral}/>
<p>Observed outcomes at {horizon} minutes. Neutral band ±{neutral}%. Missing windows are excluded.</p>
                      {/* Actual Historical Outcomes Table */}
                      <div className="mt-1">
                        <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 flex justify-between items-center">
                          <h2 className="text-xs font-bold text-slate-200 uppercase">
                            Actual historical NIFTY movements
                          </h2>
                          <span className="text-[9.5px] text-slate-500 font-mono">
                            T_0 &rarr; T+60m
                          </span>
                        </div>

                        {matches?.rows?.length ? (
                          <Table
                            rows={matches.rows.map((r: any) => ({
                              timestamp: r.timestamp,
                              t0_ref: r.reference != null ? r.reference.toFixed(2) : "--",
                              t_plus_5m:
                                r.points_5 != null
                                  ? `${r.points_5 >= 0 ? "+" : ""}${r.points_5.toFixed(2)} (${r.return_5 >= 0 ? "+" : ""}${r.return_5.toFixed(2)}%)`
                                  : "--",
                              t_plus_15m:
                                r.points_15 != null
                                  ? `${r.points_15 >= 0 ? "+" : ""}${r.points_15.toFixed(2)} (${r.return_15 >= 0 ? "+" : ""}${r.return_15.toFixed(2)}%)`
                                  : "--",
                              t_plus_30m:
                                r.points_30 != null
                                  ? `${r.points_30 >= 0 ? "+" : ""}${r.points_30.toFixed(2)} (${r.return_30 >= 0 ? "+" : ""}${r.return_30.toFixed(2)}%)`
                                  : "--",
                              t_plus_60m:
                                r.points_60 != null
                                  ? `${r.points_60 >= 0 ? "+" : ""}${r.points_60.toFixed(2)} (${r.return_60 >= 0 ? "+" : ""}${r.return_60.toFixed(2)}%)`
                                  : "--",
                              outcome:
                                r["return_" + horizon] == null
                                  ? r.reference == null
                                    ? "Intraday NIFTY data unavailable for this date."
                                    : "Forward window incomplete"
                                  : r["return_" + horizon] > neutral
                                    ? "Positive"
                                    : r["return_" + horizon] < -neutral
                                      ? "Negative"
                                      : "Neutral",
                            }))}
                            onSelect={(r) => {
                              const found = matches.rows.find(
                                (v: any) => v.timestamp === r.timestamp,
                              );
                              openMovement(found);
                            }}
                          />
                        ) : (
                          <div className="p-4 text-center text-slate-600 font-mono text-xs">
                            Find matches to view historical forward outcomes.
                          </div>
                        )}
                      </div>

                      {/* Summary & Stats Strip */}
                      {/* Summarize button */}
                      <div className="pt-1">
                        <button
                          type="button"
                          className="topbar-btn w-full py-1.5 text-center text-xs"
                          disabled={summarize.isPending || !calculation}
                          onClick={() => summarize.mutate()}
                        >
                          {summarize.isPending
                            ? "Summarizing all matches…"
                            : "Summarize all matching observations"}
                        </button>

                        {stats && (
                          <div className="mt-2 text-xs text-slate-300 bg-slate-900 p-2 rounded border border-slate-800">
                            <p className="mb-1 text-[11px] text-slate-400 font-mono">
                              Historical observations at {horizon} minutes, across
                              all matching records. Frequency is not a calibrated future probability.
                            </p>
                            <Table rows={[stats]} />
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* In-page Candlestick Chart when row selected */}
              {selected && (
                <div className="mt-2">
                  <React.Suspense
                    fallback={
                      <div className="p-8 text-center text-cyan-400 font-mono text-xs">
                        Loading chart...
                      </div>
                    }
                  >
                    <Chart
                      selected={selected}
                      horizon={horizon}
                      targetTimestamp={calculation?.timestamp}
                      onBack={() => setSelected(null)}
                      allMatches={matches?.rows || []}
                      onSelectMatch={setSelected}
                    />
                  </React.Suspense>
                </div>
              )}

              {/* 4. Bottom Research Synthesis Banner */}
              <div className="synthesis-banner-card mt-2">
                <div className="synthesis-text-group">
                  <div className="synthesis-icon-box">
                    <Lightbulb size={20} />
                  </div>
                  <div>
                    <div className="synthesis-title">
                      KP ASTROLOGICAL RESEARCH SYNTHESIS
                    </div>
                    <div className="synthesis-description">
                      {synthesisInsight}
                    </div>
                  </div>
                </div>


              </div>
            </>
          )}

          {/* ACTIVE VIEW: KP CALCULATOR */}
          {page === "KP calculator" && (
            <div className="secondary-page-card">
              <h2>KP calculator</h2>
              <p>
                Geocentric Sidereal calculations with Placidus house cusps and
                Krishnamurti Sub-Lords.
              </p>
              <div className="form-grid">
                <label>
                  Selected date &amp; time &bull; IST
                  <input
                    aria-label="Selected date and time"
                    type="datetime-local"
                    value={moment}
                    onChange={(e) => setMoment(e.target.value)}
                    className="terminal-input"
                  />
                </label>
                <button
                  type="button"
                  className="topbar-btn py-2 px-3"
                  onClick={() => setMoment(now())}
                >
                  Current IST time
                </button>
                <button
                  type="button"
                  className="terminal-calc-btn py-1.5 px-4"
                  onClick={() => calculate.mutate()}
                  disabled={calculate.isPending}
                >
                  {calculate.isPending ? "Calculating…" : "Calculate KP"}
                </button>
              </div>

              {calculation && (
                <div className="mt-4">
                  <Table
                    rows={calculation.rows.map(({ flags, ...r }: any) => r)}
                    isPlanetaryTable={true}
                  />
                </div>
              )}
            </div>
          )}

          {/* ACTIVE VIEW: INTRADAY TIMELINE */}
          {page === "Intraday timeline" && (
            <div className="secondary-page-card">
              <Timeline
                api={api}
                Table={Table}
                moment={moment}
                onSelect={openMovement}
              />
            </div>
          )}

          {/* ACTIVE VIEW: OVERVIEW */}
          {page === "Overview" && (
            <div className="secondary-page-card space-y-4">
              <h2>Overview</h2>
              <p>
                Historical market data coverage and out-of-sample research
                summaries.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="terminal-card p-3">
                  <h3 className="text-xs font-bold text-slate-300 uppercase mb-2">
                    Daily Coverage
                  </h3>
                  <Table rows={coverage.data?.daily || []} />
                </div>
                <div className="terminal-card p-3">
                  <h3 className="text-xs font-bold text-slate-300 uppercase mb-2">
                    Intraday Coverage
                  </h3>
                  <Table rows={coverage.data?.intraday || []} />
                </div>
              </div>
            </div>
          )}

          {/* ACTIVE VIEW: BACKTESTING & RESEARCH LAB */}
          {page === "Backtesting" && (
            <div className="secondary-page-card">
              <h2>Backtesting</h2>
              <Research api={api} Table={Table} />
            </div>
          )}

          {page === "Research lab" && (
            <div className="secondary-page-card">
              <h2>Research lab</h2>
              <Lab api={api} Table={Table} />
            </div>
          )}

          {/* ACTIVE VIEW: DATA MANAGER */}
          {page === "Data manager" && !demo && (
            <div className="secondary-page-card space-y-4">
              <h2>Data manager</h2>
              <p>
                Manage Upstox intraday minute archives and historical data
                synchronization jobs.
              </p>

              <div className="terminal-card p-3">
                <label className="flex items-center gap-2 text-xs text-slate-300 mb-3">
                  <input
                    type="checkbox"
                    checked={autoRefresh}
                    disabled={!upstox.data?.configured}
                    onChange={(e) => setAutoRefresh(e.target.checked)}
                  />
                  <span>
                    Refresh current Upstox session every 30 minutes while this tab
                    stays open
                  </span>
                </label>

                <div className="form-grid">
                  <label>
                    Start
                    <input
                      type="date"
                      value={start}
                      onChange={(e) => setStart(e.target.value)}
                      className="terminal-input"
                    />
                  </label>
                  <label>
                    End
                    <input
                      type="date"
                      value={end}
                      onChange={(e) => setEnd(e.target.value)}
                      className="terminal-input"
                    />
                  </label>
                  <label>
                    Daily clock
                    <input
                      type="time"
                      value={buildClock}
                      onChange={(e) => setBuildClock(e.target.value)}
                      className="terminal-input"
                    />
                  </label>
                  <label>
                    Sampling
                    <select
                      value={buildStep}
                      onChange={(e) => setBuildStep(+e.target.value)}
                      className="terminal-select"
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
                    type="button"
                    className="topbar-btn py-1.5"
                    onClick={() =>
                      invoke("admin/features", {
                        start,
                        end,
                        clock: buildClock,
                        step: buildStep,
                      })
                    }
                  >
                    Build configurations
                  </button>
                  <button
                    type="button"
                    className="topbar-btn py-1.5"
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
                </div>
              </div>

              <Import api={api} />
            </div>
          )}

          {/* ACTIVE VIEW: SETTINGS */}
          {page === "Settings" && (
            <div className="secondary-page-card space-y-4">
              <h2>Settings</h2>
              <div className="terminal-card p-4 space-y-3">
                <h3 className="text-xs font-bold text-slate-300 uppercase">
                  Original calculation profile
                </h3>
                <p className="text-xs text-slate-400">
                  Jaipur 26.9124° N / 75.7873° E &bull; Lahiri sidereal &bull;
                  Placidus houses &bull; Mean lunar nodes
                </p>

                <h3 className="text-xs font-bold text-slate-300 uppercase pt-2">
                  Upstox connection
                </h3>
                <p className="text-xs text-slate-400">
                  Configure your token using configure_upstox.bat on this
                  computer. The token stays in Windows Credential Manager.
                </p>

                <div className="flex gap-2">
                  <button
                    type="button"
                    className="topbar-btn"
                    onClick={() => invoke("admin/upstox/test", {})}
                  >
                    Test connection
                  </button>
                  <button
                    type="button"
                    className="topbar-btn"
                    onClick={() => invoke("admin/diagnostics", undefined)}
                  >
                    Run original engine diagnostics
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ACTIVE VIEW: FEEDBACK */}
          {page === "Feedback" && (
            <div className="secondary-page-card space-y-4">
              <h2>Feedback</h2>
              {!demo && (
                <div className="terminal-card p-3">
                  <h3 className="text-xs font-bold text-slate-300 uppercase mb-2">
                    Review feedback
                  </h3>
                  <Table rows={feedback.data || []} />
                </div>
              )}
              <FeedbackForm api={api} moment={moment} page={page} />
            </div>
          )}

          {notice && (
            <p
              role="status"
              className="text-xs font-mono text-cyan-300 bg-cyan-950/40 p-2 rounded border border-cyan-800"
            >
              {notice}
            </p>
          )}
        </main>
      </div>

      {/* 5. Terminal Status Footer */}
<footer>Swiss Ephemeris · Lahiri sidereal · Mean nodes · Placidus · Jaipur · Asia/Kolkata. Historical observations do not establish future trading probabilities.</footer>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={new QueryClient()}>
    <App />
  </QueryClientProvider>,
);
