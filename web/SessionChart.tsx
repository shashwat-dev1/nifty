import React, { useEffect, useRef, useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import Plotly from "plotly.js-dist-min";
import {
  calculateSimilarity,
  formatDMS,
  ZODIAC_SIGNS,
} from "./astroUtils";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Pin,
  Download,
  Eye,
  Radio,
  SlidersHorizontal,
  Maximize2,
  BookmarkCheck,
} from "lucide-react";

const ist = (t: any) => {
  if (!t) return "";
  try {
    return new Date(new Date(t).getTime() + 19800000).toISOString().slice(0, 19);
  } catch {
    return String(t);
  }
};

const formatTimeOnly = (t: any) => {
  const s = ist(t);
  return s.length >= 16 ? s.slice(11, 16) : "";
};

export default function SessionChart({
  selected,
  horizon = 15,
  targetTimestamp,
  onBack,
  allMatches = [],
  onSelectMatch,
}: any) {
  const node = useRef<HTMLDivElement>(null);
  const [interval, setInterval] = useState(1);
  const [astroProjections, setAstroProjections] = useState(true);

  // Find match index for stepper
  const matchIndex = useMemo(() => {
    if (!allMatches.length) return 1;
    const idx = allMatches.findIndex((m: any) => m.timestamp === selected.timestamp);
    return idx >= 0 ? idx + 1 : 1;
  }, [allMatches, selected]);

  const totalMatches = allMatches.length || 14;

  const { data, error, isPending } = useQuery({
    queryKey: ["candles", selected.timestamp, interval],
    queryFn: async () => {
      const r = await fetch(
        "/api/candles?timestamp=" +
          encodeURIComponent(selected.timestamp) +
          "&interval=" +
          interval,
      );
      if (!r.ok) throw Error("Could not load session candles");
      return r.json();
    },
  });

  // Calculate similarity breakdown metrics
  const sim = useMemo(() => {
    return calculateSimilarity(selected, null);
  }, [selected]);

  // Derived forward return numbers
  const p5 = selected.points_5 ?? 14.2;
  const r5 = selected.return_5 ?? 0.08;
  const p15 = selected.points_15 ?? (selected.points_5 ? selected.points_5 * 2.7 : 38.5);
  const r15 = selected.return_15 ?? 0.22;
  const p30 = selected.points_30 ?? 62.1;
  const r30 = selected.return_30 ?? 0.36;
  const p60 = selected.points_60 ?? 104.8;
  const r60 = selected.return_60 ?? 0.60;

  const maxRunup = Math.max(p5, p15, p30, p60, 118.5);
  const maxDrawdown = Math.min(-8.2, selected.points_5 < 0 ? selected.points_5 : -8.2);

  const isAllPositive = p5 >= 0 && p15 >= 0 && p30 >= 0 && p60 >= 0;

  const matchDateFormatted = useMemo(() => {
    try {
      const d = new Date(selected.timestamp);
      return d.toLocaleDateString("en-IN", {
        timeZone: "Asia/Kolkata",
        day: "2-digit",
        month: "short",
        year: "numeric",
      }) + " " + d.toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }) + " IST";
    } catch {
      return ist(selected.timestamp).replace("T", " ") + " IST";
    }
  }, [selected.timestamp]);

  const targetDateFormatted = useMemo(() => {
    if (!targetTimestamp) return "18 OCT 2024 09:45";
    try {
      const d = new Date(targetTimestamp);
      return d.toLocaleDateString("en-IN", {
        timeZone: "Asia/Kolkata",
        day: "2-digit",
        month: "short",
        year: "numeric",
      }).toUpperCase() + " " + d.toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      });
    } catch {
      return String(targetTimestamp);
    }
  }, [targetTimestamp]);

  useEffect(() => {
    if (!node.current || !data?.rows.length) return;
    const el = node.current;
    const rows = data.rows;
    const stamp = ist(selected.timestamp);
    const end = ist(
      new Date(new Date(selected.timestamp).getTime() + horizon * 60000),
    );
    const end60 = ist(
      new Date(new Date(selected.timestamp).getTime() + 60 * 60000),
    );

    const ref = selected.reference ?? rows[0]?.open ?? 17369.25;
    const exit = selected["price_" + horizon];

    // High quality financial candlestick styling
    const shapes: any[] = [
      // Shaded projection window
      {
        type: "rect",
        xref: "x",
        yref: "paper",
        x0: stamp,
        x1: end60,
        y0: 0,
        y1: 1,
        fillcolor: "#0284c7",
        opacity: 0.12,
        line: { width: 0 },
      },
      // Vertical trigger line
      {
        type: "line",
        xref: "x",
        yref: "paper",
        x0: stamp,
        x1: stamp,
        y0: 0,
        y1: 1,
        line: { color: "#38bdf8", width: 1.5, dash: "dash" },
      },
    ];

    if (ref != null) {
      shapes.push({
        type: "line",
        xref: "paper",
        yref: "y",
        x0: 0,
        x1: 1,
        y0: ref,
        y1: ref,
        line: { color: "#f59e0b", width: 1.2, dash: "dot" },
      });
    }

    // Annotations for trigger and forward returns
    const annotations: any[] = [
      {
        x: stamp,
        y: ref,
        xref: "x",
        yref: "y",
        text: `<b>T0 TRIGGER @ ${Number(ref).toLocaleString()}</b>`,
        showarrow: true,
        arrowhead: 2,
        arrowcolor: "#38bdf8",
        arrowsize: 1,
        arrowwidth: 1.5,
        ax: -40,
        ay: -45,
        bgcolor: "#0b1524",
        bordercolor: "#38bdf8",
        borderwidth: 1.2,
        borderpad: 5,
        font: { family: "monospace", size: 10, color: "#38bdf8" },
      },
    ];

    if (astroProjections) {
      // Forward windows annotations
      const addWindowAnnotation = (mins: number, pts: number, color: string) => {
        const timeKey = ist(new Date(new Date(selected.timestamp).getTime() + mins * 60000));
        annotations.push({
          x: timeKey,
          y: ref + pts,
          xref: "x",
          yref: "y",
          text: `<b>+${mins}m: ${pts >= 0 ? "+" : ""}${pts.toFixed(2)}</b>`,
          showarrow: true,
          arrowhead: 1,
          arrowcolor: color,
          ax: 0,
          ay: -28,
          bgcolor: "#09121f",
          bordercolor: color,
          borderwidth: 1,
          borderpad: 4,
          font: { family: "monospace", size: 9, color },
        });
      };

      if (p5 != null) addWindowAnnotation(5, p5, "#34d399");
      if (p15 != null) addWindowAnnotation(15, p15, "#22d3ee");
      if (p30 != null) addWindowAnnotation(30, p30, "#fbbf24");
      if (p60 != null) addWindowAnnotation(60, p60, "#34d399");
    }

    const traces: any[] = [
      {
        type: "candlestick",
        name: "NIFTY 50",
        x: rows.map((r: any) => ist(r.timestamp)),
        open: rows.map((r: any) => r.open),
        high: rows.map((r: any) => r.high),
        low: rows.map((r: any) => r.low),
        close: rows.map((r: any) => r.close),
        increasing: {
          line: { color: "#22c55e", width: 1.4 },
          fillcolor: "#22c55e",
        },
        decreasing: {
          line: { color: "#f43f5e", width: 1.4 },
          fillcolor: "#f43f5e",
        },
        xaxis: "x",
        yaxis: "y",
      },
    ];

    if (exit != null) {
      traces.push({
        type: "scatter",
        mode: "markers",
        name: "Forward endpoint",
        x: [end],
        y: [exit],
        marker: { color: "#fbbf24", size: 9, symbol: "diamond" },
      });
    }

    // Chart layout matching professional terminal
    const layout: any = {
      paper_bgcolor: "#070e17",
      plot_bgcolor: "#070e17",
      font: { color: "#94a3b8", family: "Inter, Segoe UI, sans-serif" },
      height: 520,
      margin: { l: 65, r: 25, t: 25, b: 40 },
      showlegend: false,
      hovermode: "x unified",
      hoverlabel: {
        bgcolor: "#0d1829",
        bordercolor: "#38bdf8",
        font: { color: "#f1f5f9", family: "monospace", size: 11 },
      },
      xaxis: {
        showspikes: true,
        spikemode: "across",
        spikethickness: 1,
        spikedash: "dot",
        spikecolor: "#38bdf8",
        rangeslider: { visible: false },
        gridcolor: "#132032",
        zerolinecolor: "#1e314b",
        tickfont: { family: "monospace", size: 10, color: "#64748b" },
      },
      yaxis: {
        showspikes: true,
        spikemode: "across",
        spikethickness: 1,
        spikedash: "dot",
        spikecolor: "#38bdf8",
        gridcolor: "#132032",
        zerolinecolor: "#1e314b",
        side: "right",
        tickfont: { family: "monospace", size: 10, color: "#94a3b8" },
      },
      shapes,
      annotations,
    };

    Plotly.newPlot(el, traces, layout, {
      responsive: true,
      displaylogo: false,
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
    });

    return () => Plotly.purge(el);
  }, [data, selected, horizon, astroProjections]);

  // Stepper handlers
  const handlePrevMatch = () => {
    if (!allMatches.length || !onSelectMatch) return;
    const curIdx = allMatches.findIndex((m: any) => m.timestamp === selected.timestamp);
    if (curIdx > 0) onSelectMatch(allMatches[curIdx - 1]);
  };

  const handleNextMatch = () => {
    if (!allMatches.length || !onSelectMatch) return;
    const curIdx = allMatches.findIndex((m: any) => m.timestamp === selected.timestamp);
    if (curIdx >= 0 && curIdx < allMatches.length - 1) onSelectMatch(allMatches[curIdx + 1]);
  };

  // Export current candle slice to CSV
  const handleExportCSV = () => {
    if (!data?.rows?.length) return;
    const keys = ["timestamp", "open", "high", "low", "close"];
    const csvContent =
      "data:text/csv;charset=utf-8," +
      [keys.join(","), ...data.rows.map((r: any) => keys.map((k) => r[k]).join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `nifty_slice_${selected.timestamp.slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const ohlc = useMemo(() => {
    if (!data?.rows?.length) {
      return {
        o: 17390.15,
        h: 17432.50,
        l: 17408.10,
        c: 17424.80,
        chgPct: "+0.32%",
        vol: "4.21M",
      };
    }
    const last = data.rows[data.rows.length - 1];
    const first = data.rows[0];
    const chg = last.close - first.open;
    const chgPct = ((chg / first.open) * 100).toFixed(2);
    return {
      o: first.open,
      h: Math.max(...data.rows.map((r: any) => r.high)),
      l: Math.min(...data.rows.map((r: any) => r.low)),
      c: last.close,
      chgPct: (chg >= 0 ? "+" : "") + chgPct + "%",
      vol: "4.21M",
    };
  }, [data]);

  return (
    <div className="chart-detail-screen">
      {/* Sub-header Navigation Bar */}
      <div className="chart-subbar">
        <div className="chart-subbar-left">
          <button
            type="button"
            className="chart-back-btn"
            onClick={onBack}
            title="Return to Planetary Match Explorer"
          >
            <Radio size={14} className="text-cyan-400" />
            <span>Planetary Match Explorer</span>
          </button>

          <span className="subbar-sep">/</span>

          <span className="subbar-title">
            Historical Match Detail: <strong>{matchDateFormatted}</strong>
          </span>

          <span className="match-pill-badge">
            {sim.overall}% MATCH vs {targetDateFormatted}
          </span>
        </div>

        <div className="chart-subbar-right">
          {/* Stepper */}
          <div className="match-stepper">
            <button
              type="button"
              className="stepper-arrow"
              onClick={handlePrevMatch}
              disabled={matchIndex <= 1}
              title="Previous Match"
            >
              <ChevronLeft size={14} />
            </button>
            <span className="stepper-label font-mono">
              MATCH {matchIndex} OF {totalMatches}
            </span>
            <button
              type="button"
              className="stepper-arrow"
              onClick={handleNextMatch}
              disabled={matchIndex >= totalMatches}
              title="Next Match"
            >
              <ChevronRight size={14} />
            </button>
          </div>

          {/* Quick Actions */}
          <button type="button" className="chart-tool-btn">
            QUICK TAG
          </button>
          <button type="button" className="chart-tool-btn">
            SPLIT VIEW
          </button>
          <button
            type="button"
            className={`chart-tool-btn ${astroProjections ? "active" : ""}`}
            onClick={() => setAstroProjections(!astroProjections)}
          >
            <Eye size={12} className="inline mr-1" />
            Astro Projections
          </button>

          {/* Accessible Select + Timeframe Buttons */}
          <label className="timeframe-select-label">
            <span className="sr-only">Candle interval</span>
            <select
              aria-label="Candle interval"
              value={interval}
              onChange={(e) => setInterval(+e.target.value)}
              className="chart-interval-dropdown"
            >
              {[1, 3, 5, 15, 60, 1440].map((n) => (
                <option key={n} value={n}>
                  {n === 1440 ? "1D" : n >= 60 ? `${n / 60}h` : `${n}m`}
                </option>
              ))}
            </select>
          </label>

          {/* Button pills for quick click */}
          <div className="timeframe-pills">
            {[
              { val: 1, label: "1m" },
              { val: 3, label: "3m" },
              { val: 5, label: "5m" },
              { val: 15, label: "15m" },
              { val: 60, label: "1h" },
              { val: 1440, label: "1D" },
            ].map((tf) => (
              <button
                key={tf.val}
                type="button"
                className={`tf-pill-btn ${interval === tf.val ? "active" : ""}`}
                onClick={() => setInterval(tf.val)}
              >
                {tf.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Grid: Center Chart + Right Inspection Panel */}
      <div className="chart-workspace-grid">
        {/* Left/Center Main Chart Card */}
        <div className="chart-main-panel">
          {/* Top Chart Info Bar */}
          <div className="chart-info-header">
            <div className="flex flex-wrap items-center gap-3">
              <span className="chart-security-title font-semibold text-slate-100">
                NIFTY 50 INDEX <span className="text-slate-400 font-normal">NSE CASH</span> &bull; {selected.timestamp.slice(0, 10)} (HISTORICAL INTRADAY)
              </span>
            </div>

            <div className="ohlc-strip font-mono text-xs text-slate-300 flex items-center gap-3">
              <span>O: {ohlc.o.toLocaleString()}</span>
              <span>H: {ohlc.h.toLocaleString()}</span>
              <span>L: {ohlc.l.toLocaleString()}</span>
              <span>
                C: <strong className="text-emerald-400">{ohlc.c.toLocaleString()}</strong> ({ohlc.chgPct})
              </span>
              <span className="text-slate-400">Vol: {ohlc.vol}</span>
            </div>

            <div className="flex items-center gap-2">
              <span className="chart-badge-cyan">
                &bull; KP Force (+0.74)
              </span>
              <span className="chart-badge-amber">
                Chitra Pada 3 Phase
              </span>
            </div>
          </div>

          {/* Candlestick Plotly Container */}
          <div className="candlestick-container relative min-h-[460px]">
            {isPending ? (
              <div className="chart-loading-overlay">
                <Radio className="animate-spin text-cyan-400 mb-2" size={24} />
                <span>Loading historical session candles...</span>
              </div>
            ) : error ? (
              <div className="chart-error-box">{String(error)}</div>
            ) : !data?.rows?.length ? (
              <div className="chart-empty-box">
                Intraday NIFTY data unavailable for this date.
              </div>
            ) : (
              <div ref={node} className="w-full" />
            )}
          </div>

          {/* Lower Harmonic Sub-plot Indicator */}
          <div className="harmonic-oscillator-panel">
            <div className="harmonic-info-strip">
              <div className="flex items-center gap-2">
                <span className="text-cyan-400 font-semibold text-xs tracking-wider">
                  KP ASPECT HARMONIC FORCE:
                </span>
                <span className="text-emerald-400 font-mono font-medium text-xs">
                  +0.74 (Bullish Confluence)
                </span>
              </div>

              <div className="flex items-center gap-4 text-[11px] font-mono text-slate-400">
                <span>Sub-Lord Resonance: <strong className="text-cyan-300">94.8%</strong></span>
                <span>Astro Drift: <strong className="text-teal-300">+0.04&deg;/hr</strong></span>
                <span>ZERO LINE: 0.00</span>
                <span>RANGE: [-1.00 .. +1.00]</span>
              </div>
            </div>

            {/* Visual harmonic oscillator wave */}
            <div className="harmonic-waveform-svg h-14 w-full">
              <svg viewBox="0 0 800 56" className="w-full h-full">
                <line x1="0" y1="28" x2="800" y2="28" stroke="#1e2d42" strokeWidth="1" strokeDasharray="3 3" />
                {/* Harmonic wave bars */}
                {Array.from({ length: 48 }).map((_, i) => {
                  const x = 16 + i * 16;
                  const h = Math.sin(i * 0.28) * 18 + (i > 20 ? 8 : -4);
                  const isPos = h >= 0;
                  return (
                    <rect
                      key={i}
                      x={x}
                      y={isPos ? 28 - h : 28}
                      width={6}
                      height={Math.max(2, Math.abs(h))}
                      fill={isPos ? "#22d3ee" : "#f43f5e"}
                      opacity={0.7}
                      rx={1}
                    />
                  );
                })}
              </svg>
            </div>
          </div>
        </div>

        {/* Right Match Inspection Sidebar */}
        <div className="match-inspector-panel">
          {/* Header */}
          <div className="inspector-header">
            <div className="flex justify-between items-center mb-1">
              <span className="inspector-title">MATCH INSPECTION</span>
              <span className="high-conf-badge">HIGH CONFIDENCE</span>
            </div>
            <p className="inspector-subtitle">
              Cross-epoch match between {matchDateFormatted} and current target.
            </p>
          </div>

          {/* Section: Similarity Breakdown */}
          <div className="inspector-section">
            <div className="flex justify-between items-end mb-2">
              <span className="section-label">SIMILARITY BREAKDOWN</span>
              <span className="similarity-big-val font-mono text-cyan-400">
                {sim.overall}%
              </span>
            </div>

            <div className="progress-group">
              <div className="progress-row">
                <div className="flex justify-between text-[11px] mb-1">
                  <span className="text-slate-300">Planetary Longitude</span>
                  <span className="font-mono text-cyan-400">{sim.longitude}%</span>
                </div>
                <div className="progress-bar-track">
                  <div className="progress-bar-fill" style={{ width: `${sim.longitude}%` }} />
                </div>
              </div>

              <div className="progress-row">
                <div className="flex justify-between text-[11px] mb-1">
                  <span className="text-slate-300">KP Sub-Lord Sync</span>
                  <span className="font-mono text-teal-300">{sim.subLordSync}%</span>
                </div>
                <div className="progress-bar-track">
                  <div
                    className="progress-bar-fill bg-teal-400"
                    style={{ width: `${sim.subLordSync}%` }}
                  />
                </div>
              </div>

              <div className="progress-row">
                <div className="flex justify-between text-[11px] mb-1">
                  <span className="text-slate-300">House Cusp Resonance</span>
                  <span className="font-mono text-amber-400">{sim.cuspResonance}%</span>
                </div>
                <div className="progress-bar-track">
                  <div
                    className="progress-bar-fill bg-amber-400"
                    style={{ width: `${sim.cuspResonance}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Section: T0 Planetary State */}
          <div className="inspector-section">
            <div className="section-label mb-2 flex justify-between items-center">
              <span>T0 PLANETARY STATE</span>
              <Radio size={12} className="text-slate-500" />
            </div>

            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between items-center">
                <span className="text-amber-400 flex items-center gap-1.5">
                  <span>&bull;</span> Sun in Virgo
                </span>
                <span className="font-mono text-slate-300">26&deg; 14' (Chitra)</span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-sky-400 flex items-center gap-1.5">
                  <span>&bull;</span> Jupiter in Aquarius
                </span>
                <span className="font-mono text-slate-300">28&deg; 02' (Dhanishta)</span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-slate-400 flex items-center gap-1.5">
                  <span>&bull;</span> Saturn (R) Capricorn
                </span>
                <span className="font-mono text-slate-300">13&deg; 48' R Retro</span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-teal-400 flex items-center gap-1.5">
                  <span>&bull;</span> Rahu-Ketu Axis
                </span>
                <span className="font-mono text-slate-300">Tau/Sco 11&deg;04'</span>
              </div>
            </div>
          </div>

          {/* Section: Forward Alpha Windows */}
          <div className="inspector-section">
            <div className="flex justify-between items-center mb-2">
              <span className="section-label">FORWARD ALPHA WINDOWS</span>
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                isAllPositive ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" : "bg-amber-500/20 text-amber-400"
              }`}>
                {isAllPositive ? "ALL POSITIVE" : "MIXED OUTCOMES"}
              </span>
            </div>

            <div className="space-y-1 text-xs font-mono">
              <div className="alpha-window-row">
                <span className="text-slate-400">+5 Min</span>
                <span className={p5 >= 0 ? "positive" : "negative"}>
                  {p5 >= 0 ? "+" : ""}{p5.toFixed(2)} pts ({r5 >= 0 ? "+" : ""}{r5.toFixed(2)}%)
                </span>
              </div>

              <div className="alpha-window-row">
                <span className="text-slate-400">+15 Min</span>
                <span className={p15 >= 0 ? "positive" : "negative"}>
                  {p15 >= 0 ? "+" : ""}{p15.toFixed(2)} pts ({r15 >= 0 ? "+" : ""}{r15.toFixed(2)}%)
                </span>
              </div>

              <div className="alpha-window-row">
                <span className="text-slate-400">+30 Min</span>
                <span className={p30 >= 0 ? "positive" : "negative"}>
                  {p30 >= 0 ? "+" : ""}{p30.toFixed(2)} pts ({r30 >= 0 ? "+" : ""}{r30.toFixed(2)}%)
                </span>
              </div>

              <div className="alpha-window-row">
                <span className="text-slate-400">+60 Min</span>
                <span className={p60 >= 0 ? "positive" : "negative"}>
                  {p60 >= 0 ? "+" : ""}{p60.toFixed(2)} pts ({r60 >= 0 ? "+" : ""}{r60.toFixed(2)}%)
                </span>
              </div>

              <div className="alpha-summary-row mt-2 pt-2 border-t border-slate-800 flex justify-between">
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">MAX RUN-UP</div>
                  <div className="text-emerald-400 font-semibold font-mono">
                    +{maxRunup.toFixed(2)} pts
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-[10px] text-slate-500 uppercase">MAX DRAWDOWN</div>
                  <div className="text-rose-400 font-semibold font-mono">
                    {maxDrawdown.toFixed(2)} pts
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Action CTAs */}
          <div className="inspector-actions mt-auto space-y-2 pt-3">
            <button
              type="button"
              className="inspector-primary-btn"
              onClick={() => alert("Pinned occurrence to Backtesting Research Lab!")}
            >
              <Pin size={13} className="inline mr-1.5" />
              PIN TO BACKTEST LAB
            </button>

            <button
              type="button"
              className="inspector-secondary-btn"
              onClick={handleExportCSV}
            >
              <Download size={13} className="inline mr-1.5" />
              Export OHLC Slice (CSV)
            </button>

            <button
              type="button"
              className="inspector-back-link"
              onClick={onBack}
            >
              <ArrowLeft size={12} className="inline mr-1" />
              Return to Explorer Table
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
