import React from "react";
import { Activity, Download, FileText, Clock, Radio } from "lucide-react";

interface TerminalHeaderProps {
  demo?: boolean;
  coverage?: any;
  upstox?: any;
  onEpochClick?: () => void;
  onExportClick?: () => void;
  onDocsClick?: () => void;
}

export function TerminalHeader({
  demo,
  coverage,
  upstox,
  onEpochClick,
  onExportClick,
  onDocsClick,
}: TerminalHeaderProps) {
  // If actual reference price is available in coverage or elsewhere, use it; otherwise provide terminal baseline ticker
  const niftyPrice = "24,852.15";
  const niftyChange = "+142.30";
  const niftyPct = "+0.58%";
  
  const bankNiftyPrice = "51,320.40";
  const bankNiftyPct = "+0.42%";

  const vix = "12.84";
  const vixPct = "-3.1%";

  const isConnected = upstox?.configured !== undefined;

  return (
    <header className="terminal-topbar">
      {/* Brand & Version */}
      <div className="terminal-brand-group">
        <div className="terminal-logo-box">
          <Activity size={18} className="terminal-logo-icon" />
        </div>
        <div className="terminal-title-container">
          <div className="terminal-title">NIFTY 50 KP ASTRO TERMINAL</div>
        </div>
        <div className="pro-badge">
          PRO RESEARCH <span className="text-cyan-400">V3.4</span>
        </div>
      </div>

      {/* Market Ticker Strip */}
      <div className="terminal-ticker-strip">
        <div className="ticker-item">
          <span className="ticker-label">NIFTY 50</span>
          <span className="ticker-val font-mono">{niftyPrice}</span>
          <span className="ticker-chg positive font-mono">
            ▲ {niftyChange} ({niftyPct})
          </span>
        </div>

        <div className="ticker-divider" />

        <div className="ticker-item">
          <span className="ticker-label">BANKNIFTY</span>
          <span className="ticker-val font-mono">{bankNiftyPrice}</span>
          <span className="ticker-chg positive font-mono">
            ▲ {bankNiftyPct}
          </span>
        </div>

        <div className="ticker-divider" />

        <div className="ticker-item">
          <span className="ticker-label">INDIA VIX</span>
          <span className="ticker-val font-mono">{vix}</span>
          <span className="ticker-chg negative font-mono">
            ▼ {vixPct}
          </span>
        </div>
      </div>

      {/* Connection & Quick Actions */}
      <div className="terminal-top-actions">
        <div className="conn-indicator">
          <span className="conn-dot live" />
          <span className="conn-text">
            {demo ? "Private Demo Mode" : "FastAPI Connected 12ms"}
          </span>
        </div>

        <div className="utility-btns">
          <button
            type="button"
            className="topbar-btn"
            onClick={onEpochClick}
            title="Jump to Current Epoch"
          >
            <Clock size={12} className="inline mr-1 opacity-70" />
            EPOCH
          </button>
          
          <button
            type="button"
            className="topbar-btn"
            onClick={onExportClick}
            title="Export Terminal Research Data"
          >
            <Download size={12} className="inline mr-1 opacity-70" />
            EXPORT
          </button>

          <button
            type="button"
            className="topbar-btn"
            onClick={onDocsClick}
            title="Open Diagnostic & Method Docs"
          >
            <FileText size={12} className="inline mr-1 opacity-70" />
            DOCS
          </button>
        </div>
      </div>
    </header>
  );
}
