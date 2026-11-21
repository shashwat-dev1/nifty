import React from "react";

interface ProjectionChartProps {
  referencePrice?: number;
  points15?: number;
  points30?: number;
  points60?: number;
  isBullish?: boolean;
}

export function ProjectionChart({
  referencePrice = 17369.25,
  points15 = 48.6,
  points30 = 79.4,
  points60 = 112.4,
  isBullish = true,
}: ProjectionChartProps) {
  // Chart dimensions in viewBox coordinates
  const width = 500;
  const height = 110;
  const padLeft = 45;
  const padRight = 30;
  const padTop = 20;
  const padBottom = 26;

  const chartW = width - padLeft - padRight;
  const chartH = height - padTop - padBottom;

  // Normalized points: T0 (0), +15m (0.25), +30m (0.5), +45m (0.75), +60m (1.0)
  const p0 = 0;
  const p15 = points15;
  const p30 = points30;
  const p45 = points30 + (points60 - points30) * 0.45;
  const p60 = points60;

  const allVals = [p0, p15, p30, p45, p60];
  const maxVal = Math.max(...allVals, 20);
  const minVal = Math.min(...allVals, -10);
  const valRange = maxVal - minVal || 1;

  // Coordinate mapping
  const getX = (tPct: number) => padLeft + tPct * chartW;
  const getY = (val: number) => padTop + chartH - ((val - minVal) / valRange) * chartH;

  const x0 = getX(0);
  const y0 = getY(p0);

  const x15 = getX(0.25);
  const y15 = getY(p15);

  const x30 = getX(0.5);
  const y30 = getY(p30);

  const x45 = getX(0.75);
  const y45 = getY(p45);

  const x60 = getX(1.0);
  const y60 = getY(p60);

  // Smooth bezier curve path
  const pathD = `M ${x0} ${y0} C ${x0 + (x15 - x0) * 0.5} ${y0}, ${x15 - (x15 - x0) * 0.4} ${y15}, ${x15} ${y15} ` +
                `C ${x15 + (x30 - x15) * 0.5} ${y15}, ${x30 - (x30 - x15) * 0.4} ${y30}, ${x30} ${y30} ` +
                `C ${x30 + (x45 - x30) * 0.5} ${y30}, ${x45 - (x45 - x30) * 0.4} ${y45}, ${x45} ${y45} ` +
                `C ${x45 + (x60 - x45) * 0.5} ${y45}, ${x60 - (x60 - x45) * 0.4} ${y60}, ${x60} ${y60}`;

  const areaD = `${pathD} L ${x60} ${padTop + chartH} L ${x0} ${padTop + chartH} Z`;

  const lineColor = isBullish ? "#2dd4bf" : "#f43f5e";
  const gradId = isBullish ? "bullGrad" : "bearGrad";

  return (
    <div className="projection-curve-container">
      <div className="projection-header flex justify-between items-center text-xs mb-1">
        <span className="text-slate-300 font-medium tracking-wide">
          Composite Forward Projection Curve (T0 &rarr; T+60m)
        </span>
        <span className="text-teal-400 font-mono text-[11px]">
          Std Error: &plusmn;14.2 pts
        </span>
      </div>

      <div className="svg-wrapper relative">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto overflow-visible select-none"
        >
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={lineColor} stopOpacity="0.28" />
              <stop offset="80%" stopColor={lineColor} stopOpacity="0.04" />
              <stop offset="100%" stopColor={lineColor} stopOpacity="0.0" />
            </linearGradient>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Reference Zero/T0 Line */}
          <line
            x1={padLeft}
            y1={y0}
            x2={width - padRight}
            y2={y0}
            stroke="#1e293b"
            strokeWidth="1"
            strokeDasharray="3 3"
          />

          {/* Shaded Area Under Curve */}
          <path d={areaD} fill={`url(#${gradId})`} />

          {/* Projection Line */}
          <path
            d={pathD}
            fill="none"
            stroke={lineColor}
            strokeWidth="2.5"
            filter="url(#glow)"
          />

          {/* T0 Label */}
          <text
            x={padLeft - 6}
            y={y0 + 3}
            fill="#64748b"
            fontSize="9"
            fontFamily="monospace"
            textAnchor="end"
          >
            T0 {referencePrice.toLocaleString()}
          </text>

          {/* Timeline markers */}
          <g fontSize="9" fontFamily="monospace" fill="#64748b" textAnchor="middle">
            <line x1={x15} y1={padTop + chartH} x2={x15} y2={padTop + chartH + 4} stroke="#334155" />
            <text x={x15} y={padTop + chartH + 14}>+15m</text>

            <line x1={x30} y1={padTop + chartH} x2={x30} y2={padTop + chartH + 4} stroke="#334155" />
            <text x={x30} y={padTop + chartH + 14}>+30m</text>

            <line x1={x45} y1={padTop + chartH} x2={x45} y2={padTop + chartH + 4} stroke="#334155" />
            <text x={x45} y={padTop + chartH + 14}>+45m</text>

            <line x1={x60} y1={padTop + chartH} x2={x60} y2={padTop + chartH + 4} stroke="#334155" />
            <text x={x60} y={padTop + chartH + 14}>+60m</text>
          </g>

          {/* Dots on key horizons */}
          <circle cx={x15} cy={y15} r="3" fill={lineColor} />
          <circle cx={x30} cy={y30} r="3" fill={lineColor} />
          <circle cx={x60} cy={y60} r="3.5" fill="#ffffff" stroke={lineColor} strokeWidth="2" />
        </svg>
      </div>
    </div>
  );
}
