import React from "react";
import { calculateAspectMatrix } from "./astroUtils";
import {
  Compass,
  Activity,
  Layers,
  Database,
  Settings as SettingsIcon,
  MessageSquare,
  Search,
  TrendingUp,
} from "lucide-react";

interface AstroSidebarProps {
  calculation?: any;
  activePage: string;
  onNavigate: (page: string) => void;
  demo?: boolean;
}

export function AstroSidebar({
  calculation,
  activePage,
  onNavigate,
  demo,
}: AstroSidebarProps) {
  // Derive ruling lords from calculation
  const rp = calculation?.ruling_planets || {};
  const ascLord = rp.lagna || "Unavailable";
  const ascSub = calculation?.positions?.Lagna?.sub || "Unavailable";

  const moonStar = rp.moon_star || "Unavailable";
  const moonSub = rp.moon_sub || "Unavailable";

  const sunLong = calculation?.positions?.Sun?.longitude;
  const sunSign = calculation?.positions?.Sun?.sign || "Unavailable";
  const sunDegFormatted =
    sunLong != null
      ? `${Math.floor(sunLong % 30)}Â°${String(
          Math.floor(((sunLong % 30) - Math.floor(sunLong % 30)) * 60),
        ).padStart(2, "0")}'`
      : "Unavailable";

  const aspects = calculateAspectMatrix(calculation?.positions);

  const pages = demo
    ? ["Match explorer", "KP calculator", "Intraday timeline", "Feedback"]
    : [
        "Match explorer",
        "KP calculator",
        "Intraday timeline",
        "Daily Research",
        "Model Evaluation",
        "Prospective Predictions",
        "Overview",
        "Backtesting",
        "Data manager",
        "Research lab",
        "Settings",
        "Feedback",
      ];

  const getIcon = (name: string) => {
    switch (name) {
      case "Match explorer":
        return Search;
      case "KP calculator":
        return Compass;
      case "Intraday timeline":
        return TrendingUp;
      case "Overview":
        return Layers;
      case "Backtesting":
        return Activity;
      case "Data manager":
        return Database;
      case "Research lab":
        return Activity;
      case "Settings":
        return SettingsIcon;
      case "Feedback":
        return MessageSquare;
      default:
        return Activity;
    }
  };

  return (
    <aside className="terminal-sidebar">
      {/* KP ASTRO SUB-LORDS Box */}
      <div className="sidebar-panel-card">
        <div className="panel-card-title">KP ASTRO SUB-LORDS</div>

        <div className="astro-metric-row">
          <span className="metric-label">Ascendant</span>
          <span className="metric-val text-cyan-400 font-mono font-semibold">
            {ascLord.slice(0, 3).toUpperCase()} / {ascSub.slice(0, 3).toUpperCase()}
          </span>
        </div>

        <div className="astro-metric-row">
          <span className="metric-label">Moon Star Lord</span>
          <span className="metric-val text-cyan-400 font-mono font-semibold">
            {moonStar.slice(0, 3).toUpperCase()} / {moonSub.slice(0, 3).toUpperCase()}
          </span>
        </div>

        <div className="astro-metric-row">
          <span className="metric-label">Sun Transits</span>
          <span className="metric-val text-emerald-400 font-mono font-semibold">
            {sunSign.toUpperCase()} {sunDegFormatted}
          </span>
        </div>
      </div>

      {/* HARMONIC ASPECT MATRIX Box */}
      <div className="sidebar-panel-card">
        <div className="panel-card-title">HARMONIC ASPECT MATRIX</div>

        {aspects.map((asp, idx) => (
          <div key={idx} className="astro-metric-row">
            <span className="metric-label flex items-center gap-1.5">
              <span className="text-cyan-300 opacity-90">{asp.symbol}</span>
              <span>{asp.label}</span>
            </span>
            <span
              className={`metric-val font-mono font-medium ${
                asp.color ? "" : asp.highlight ? "text-cyan-400" : "text-slate-300"
              }`}
              style={asp.color ? { color: asp.color } : {}}
            >
              {asp.value}
            </span>
          </div>
        ))}
      </div>

      {/* Workspace Navigation Links */}
      <div className="sidebar-nav-card">
        <div className="panel-card-title">RESEARCH WORKSPACES</div>
        <div className="sidebar-nav-links">
          {pages.map((p) => {
            const Icon = getIcon(p);
            const isActive = activePage === p;
            return (
              <button
                key={p}
                type="button"
                className={`sidebar-nav-btn ${isActive ? "active" : ""}`}
                onClick={() => onNavigate(p)}
              >
                <Icon size={14} className="opacity-70" />
                <span>{p}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Bottom Ephemeris Details */}
      <div className="sidebar-footer-card">
        <div className="ephemeris-title">SWISS EPHEMERIS V2.10</div>
        <div className="ephemeris-sub">Ayanamsa: Lahiri</div>
        <div className="ephemeris-sub">Calculation: Geocentric</div>
      </div>
    </aside>
  );
}
