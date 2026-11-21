import React, { useState } from "react";
export function Research({ api, Table }: any) {
  const [mode, setMode] = useState("intraday"),
    [data, setData] = useState<any>(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <section>
      <h2>Chronological backtest</h2>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          setBusy(true);
          try {
            setData(
              await api("backtest", {
                mode,
                start: f.get("start"),
                end: f.get("end"),
                split: f.get("split"),
                horizon: Number(f.get("horizon")),
                minimum: Number(f.get("minimum")),
                cost: 2,
                key: f.get("key"),
              }),
            );
            setError("");
          } catch (x) {
            setError(String(x));
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="controls">
          <label>
            Frequency
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option>intraday</option>
              <option>daily</option>
            </select>
          </label>
          {[
            ["start", "2026-09-01"],
            ["end", "2026-11-19"],
            ["split", "2026-11-01"],
          ].map(([name, value]) => (
            <label key={name}>
              {name}
              <input name={name} type="date" defaultValue={value} />
            </label>
          ))}
          <label>
            Horizon in minutes / daily sessions
            <input
              name="horizon"
              type="number"
              min="1"
              max="60"
              defaultValue="15"
            />
          </label>
          <label>
            Minimum history
            <input name="minimum" type="number" min="1" defaultValue="5" />
          </label>
          <label>
            Rule
            <select name="key">
              {["score", "majority", "moon_star", "moon_sub", "lagna"].map(
                (k) => (
                  <option key={k}>{k}</option>
                ),
              )}
            </select>
          </label>
          <button disabled={busy}>{busy ? "Computing…" : "Run study"}</button>
        </div>
      </form>
      <p>
        Daily uses expanding annual splits. Intraday uses non-overlapping
        windows, a fixed date split and two basis points round-trip cost.
      </p>
      {error && <p className="error">{error}</p>}
      {data && (
        <>
          <p>
            {data.n} held-out cases · Accuracy{" "}
            {(100 * data.accuracy).toFixed(1)}% · Baseline{" "}
            {(100 * data.baseline).toFixed(1)}%
          </p>
          <Table rows={data.rows} />
        </>
      )}
    </section>
  );
}
export function FeedbackForm({ api, moment, page }: any) {
  const [notice, setNotice] = useState("");
  return (
    <section>
      <h2>Research feedback</h2>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          try {
            await api("feedback", {
              page: form.get("page"),
              timestamp: moment,
              result: form.get("result"),
              expected: form.get("expected"),
              actual: form.get("actual"),
              comments: form.get("comments"),
            });
            setNotice("Feedback saved.");
          } catch (x) {
            setNotice(String(x));
          }
        }}
      >
        <label>
          Feature or page
          <input
            name="page"
            defaultValue="Match explorer"
            maxLength={100}
            required
          />
        </label>
        <label>
          Calculation or result reviewed
          <input name="result" maxLength={500} />
        </label>
        {["expected", "actual", "comments"].map((name) => (
          <label key={name}>
            {name}
            <textarea
              name={name}
              maxLength={1800}
              required={name !== "comments"}
            />
          </label>
        ))}
        <button>Submit feedback</button>
        <p>{notice}</p>
      </form>
    </section>
  );
}
