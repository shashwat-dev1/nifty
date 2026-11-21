import React, { useEffect } from "react";

interface TerminalTabsProps {
  activeTab: string;
  onSelectTab: (tab: string) => void;
  demo?: boolean;
}

export function TerminalTabs({ activeTab, onSelectTab, demo }: TerminalTabsProps) {
  const tabs = [
    { id: "Match explorer", label: "Planetary Match Explorer", shortcut: "ALT+1" },
    { id: "Chart detail", label: "Historical Chart Detail", shortcut: "ALT+2" },
    { id: "Intraday timeline", label: "Intraday Timeline", shortcut: "ALT+3" },
    { id: "Backtesting", label: "Backtesting & Research Lab", shortcut: "ALT+4" },
    ...(!demo ? [{ id: "Data manager", label: "NIFTY Data Manager", shortcut: "" }] : []),
  ];

  // Keyboard shortcut support
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.altKey) {
        if (e.key === "1") {
          e.preventDefault();
          onSelectTab("Match explorer");
        } else if (e.key === "2") {
          e.preventDefault();
          onSelectTab("Chart detail");
        } else if (e.key === "3") {
          e.preventDefault();
          onSelectTab("Intraday timeline");
        } else if (e.key === "4") {
          e.preventDefault();
          onSelectTab("Backtesting");
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onSelectTab]);

  return (
    <div className="terminal-nav-strip">
      <div className="terminal-tabs-list">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              className={`nav-tab-btn ${isActive ? "active" : ""}`}
              onClick={() => onSelectTab(tab.id)}
            >
              {tab.label}
              {isActive && <span className="tab-indicator" />}
            </button>
          );
        })}
      </div>

      <div className="terminal-shortcuts-list">
        <span className="shortcut-pill"><kbd>ALT+1</kbd> MATCH</span>
        <span className="shortcut-pill"><kbd>ALT+2</kbd> CHART</span>
        <span className="shortcut-pill"><kbd>ALT+3</kbd> TIME</span>
        <span className="shortcut-pill"><kbd>ALT+4</kbd> LAB</span>
      </div>
    </div>
  );
}
