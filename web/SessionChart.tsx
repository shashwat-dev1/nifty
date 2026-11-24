import React, { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Plotly from "plotly.js-dist-min";
const ist = (t: any) =>
  new Date(new Date(t).getTime() + 19800000).toISOString().slice(0, 19);
export default function SessionChart({ selected, horizon }: any) {
  const node = useRef<HTMLDivElement>(null),
    [interval, setInterval] = useState(1);
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
  useEffect(() => {
    if (!node.current || !data?.rows.length) return;
    const el = node.current,
      rows = data.rows,
      stamp = ist(selected.timestamp),
      end = ist(
        new Date(new Date(selected.timestamp).getTime() + horizon * 60000),
      );
    const ref = selected.reference,
      exit = selected["price_" + horizon];
    const shapes: any[] = [
      {
        type: "rect",
        xref: "x",
        yref: "paper",
        x0: stamp,
        x1: end,
        y0: 0,
        y1: 1,
        fillcolor: "#75b6ff",
        opacity: 0.12,
        line: { width: 0 },
      },
      {
        type: "line",
        xref: "x",
        yref: "paper",
        x0: stamp,
        x1: stamp,
        y0: 0,
        y1: 1,
        line: { color: "#75b6ff", dash: "dot" },
      },
    ];
    if (ref != null)
      shapes.push({
        type: "line",
        xref: "paper",
        yref: "y",
        x0: 0,
        x1: 1,
        y0: ref,
        y1: ref,
        line: { color: "#e0be7b", dash: "dash" },
      });
    const traces: any[] = [
      {
        type: "candlestick",
        name: "NIFTY 50",
        x: rows.map((r) => ist(r.timestamp)),
        open: rows.map((r) => r.open),
        high: rows.map((r) => r.high),
        low: rows.map((r) => r.low),
        close: rows.map((r) => r.close),
        increasing: { line: { color: "#62d8b2" } },
        decreasing: { line: { color: "#f28b82" } },
      },
    ];
    if (exit != null)
      traces.push({
        type: "scatter",
        mode: "markers",
        name: "Forward endpoint",
        x: [end],
        y: [exit],
        marker: { color: "#e0be7b", size: 10 },
      });
    Plotly.newPlot(
      el,
      traces,
      {
        paper_bgcolor: "#121c28",
        plot_bgcolor: "#121c28",
        font: { color: "#b8c6d7" },
        height: 460,
        margin: { l: 65, r: 25, t: 30, b: 45 },
        showlegend: false,
        hovermode: "closest",
        xaxis: {
          showspikes: true,
          spikemode: "across",
          rangeslider: { visible: false },
          title: { text: "Asia/Kolkata · candle close" },
        },
        yaxis: { showspikes: true, spikemode: "across" },
        shapes,
      },
      { responsive: true, displaylogo: false },
    );
    return () => Plotly.purge(el);
  }, [data, selected, horizon]);
  return (
    <section aria-label="Historical chart">
      <div className="sectionhead">
        <h2>Historical NIFTY session</h2>
        <label>
          Candle interval
          <select
            value={interval}
            onChange={(e) => setInterval(+e.target.value)}
          >
            {[1, 5, 15].map((n) => (
              <option key={n} value={n}>
                {n} minute candles
              </option>
            ))}
          </select>
        </label>
      </div>
      <p>
        {ist(selected.timestamp).replace("T", " ")} IST · {horizon}-minute
        window highlighted
      </p>
      {selected["points_" + horizon] != null && (
        <p>
          Observed movement: {selected["points_" + horizon].toFixed(2)} points (
          {selected["return_" + horizon].toFixed(3)}%)
        </p>
      )}
      {isPending ? (
        <p>Loading actual session candles…</p>
      ) : error ? (
        <p className="error">{String(error)}</p>
      ) : !data?.rows.length ? (
        <p className="empty">Intraday NIFTY data unavailable for this date.</p>
      ) : (
        <div ref={node} />
      )}
      <p>
        Close timestamps; reference and forward changes are descriptive index
        observations, not executable fills.
      </p>
    </section>
  );
}
