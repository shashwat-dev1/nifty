import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
export function Timeline({ api, Table, moment, onSelect }: any) {
  const [step, setStep] = useState(15);
  const q = useQuery({
    queryKey: ["timeline", moment.slice(0, 10), step],
    queryFn: () => api("timeline?day=" + moment.slice(0, 10) + "&step=" + step),
  });
  return (
    <section>
      <h2>Intraday KP timeline · IST</h2>
      <label>
        Sampling interval
        <select value={step} onChange={(e) => setStep(+e.target.value)}>
          {[1, 5, 15, 30].map((v) => (
            <option key={v} value={v}>
              {v} minutes
            </option>
          ))}
        </select>
      </label>
      {q.isPending && <p>Calculating session…</p>}
      {q.error && <p className="error">{String(q.error)}</p>}
      <Table rows={q.data || []} onSelect={onSelect} />
    </section>
  );
}
export function Import({ api }: any) {
  const [notice, setNotice] = useState("");
  return (
    <section>
      <h2>Import genuine NIFTY spot candles</h2>
      <p>
        CSV columns: timestamp, close and optional open, high, low. Conflicting
        records are rejected. Confirm this is NIFTY 50 spot-index data.
      </p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          try {
            const csv = await (f.get("file") as File).text();
            setNotice(
              JSON.stringify(
                await api("admin/import", {
                  csv,
                  source: f.get("source"),
                  timezone: f.get("timezone"),
                  interval: Number(f.get("interval")),
                  start_labels: f.get("label") === "start",
                }),
              ),
            );
          } catch (x) {
            setNotice(String(x));
          }
        }}
      >
        <div className="controls">
          <label>
            CSV
            <input type="file" name="file" accept=".csv" required />
          </label>
          <label>
            Source
            <input name="source" required maxLength={120} />
          </label>
          <label>
            Timezone
            <input name="timezone" defaultValue="Asia/Kolkata" />
          </label>
          <label>
            Interval minutes
            <input
              name="interval"
              type="number"
              defaultValue={1}
              min={1}
              max={60}
            />
          </label>
          <label>
            Timestamp labels
            <select name="label">
              <option value="start">Interval opening</option>
              <option value="close">Interval closing</option>
            </select>
          </label>
          <label>
            <input type="checkbox" required /> Verified NIFTY 50 spot index
          </label>
          <button>Validate and import</button>
        </div>
      </form>
      <p role="status">{notice}</p>
    </section>
  );
}
export function Lab({ api, Table }: any) {
  const [rows, setRows] = useState([]),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <section>
      <h2>Daily factor research lab</h2>
      <p>
        Annual expanding training windows. Lagged market context; same held-out
        dates for combined and baseline rules. Monthly sign tests adjusted
        across 11 comparisons. Daily research does not validate minute signals.
      </p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          setBusy(true);
          try {
            setRows(
              await api("admin/lab", {
                first: Number(f.get("first")),
                minimum: Number(f.get("minimum")),
              }),
            );
            setNotice("Study complete");
          } catch (x) {
            setNotice(String(x));
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="controls">
          <label>
            First held-out year
            <input
              name="first"
              type="number"
              defaultValue={2016}
              min={1997}
              max={2100}
            />
          </label>
          <label>
            Minimum training cases
            <input name="minimum" type="number" defaultValue={20} min={1} />
          </label>
          <button disabled={busy}>
            {busy ? "Comparing factors…" : "Compare factors"}
          </button>
        </div>
      </form>
      <p>{notice}</p>
      <Table rows={rows} />
    </section>
  );
}
