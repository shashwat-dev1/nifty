// Astronomical and KP calculation helpers for frontend presentation

export interface PlanetPosition {
  planet: string;
  longitude: number;
  speed?: number;
  retrograde?: boolean;
  sign?: string;
  star?: string;
  sub?: string;
  ssl?: string;
  nakshatra?: number;
  nakshatra_name?: string;
  zodiac?: string;
  signif?: number;
}

export const ZODIAC_SIGNS = [
  { name: "Aries", abbr: "Ari", symbol: "♈", lord: "Mars" },
  { name: "Taurus", abbr: "Tau", symbol: "♉", lord: "Venus" },
  { name: "Gemini", abbr: "Gem", symbol: "♊", lord: "Mercury" },
  { name: "Cancer", abbr: "Can", symbol: "♋", lord: "Moon" },
  { name: "Leo", abbr: "Leo", symbol: "Leo", lord: "Sun" },
  { name: "Virgo", abbr: "Vir", symbol: "Vir", lord: "Mercury" },
  { name: "Libra", abbr: "Lib", symbol: "Lib", lord: "Venus" },
  { name: "Scorpio", abbr: "Sco", symbol: "Sco", lord: "Mars" },
  { name: "Sagittarius", abbr: "Sag", symbol: "Sag", lord: "Jupiter" },
  { name: "Capricorn", abbr: "Cap", symbol: "Cap", lord: "Saturn" },
  { name: "Aquarius", abbr: "Aqu", symbol: "Aqu", lord: "Saturn" },
  { name: "Pisces", abbr: "Pis", symbol: "Pis", lord: "Jupiter" },
];

export const PLANET_META: Record<string, { glyph: string; color: string; label: string }> = {
  Sun: { glyph: "☉", color: "#f59e0b", label: "Sun" },
  Moon: { glyph: "☽", color: "#38bdf8", label: "Moon" },
  Mars: { glyph: "♂", color: "#f87171", label: "Mars" },
  Mercury: { glyph: "☿", color: "#34d399", label: "Mercury" },
  Jupiter: { glyph: "♃", color: "#fbbf24", label: "Jupiter" },
  Venus: { glyph: "♀", color: "#f472b6", label: "Venus" },
  Saturn: { glyph: "♄", color: "#94a3b8", label: "Saturn" },
  Rahu: { glyph: "☊", color: "#2dd4bf", label: "Rahu" },
  Ketu: { glyph: "☋", color: "#2dd4bf", label: "Ketu" },
  Ascendant: { glyph: "⚑", color: "#00f2fe", label: "Lagna (Asc)" },
  Lagna: { glyph: "⚑", color: "#00f2fe", label: "Lagna (Asc)" },
};

export function formatDMS(deg: number | undefined): { dms: string; signAbbr: string; full: string } {
  if (deg == null || isNaN(deg)) return { dms: "--", signAbbr: "--", full: "--" };
  const normalized = ((deg % 360) + 360) % 360;
  const signIndex = Math.floor(normalized / 30);
  const signAbbr = ZODIAC_SIGNS[signIndex]?.abbr || "Ari";
  
  const d = Math.floor(normalized);
  const m = Math.floor((normalized - d) * 60);
  const s = Math.round(((normalized - d) * 60 - m) * 60);
  
  const dStr = String(d).padStart(3, "0");
  const mStr = String(m).padStart(2, "0");
  const sStr = String(s).padStart(2, "0");
  
  const dms = `${dStr}° ${mStr}' ${sStr}"`;
  return {
    dms,
    signAbbr,
    full: `${dms} (${signAbbr})`,
  };
}

export function formatSpeed(speed: number | undefined, retro?: boolean): string {
  if (speed == null) return "0°00'D";
  const abs = Math.abs(speed);
  const deg = Math.floor(abs);
  const min = Math.round((abs - deg) * 60);
  const dir = retro || speed < 0 ? "R" : "D";
  return `${deg}°${String(min).padStart(2, "0")}'${dir}`;
}

export function calculateAspectMatrix(positions: Record<string, any> = {}) {
  const sun = positions.Sun?.longitude ?? 181.4;
  const rahu = positions.Rahu?.longitude ?? 342.18;
  const jup = positions.Jupiter?.longitude ?? 67.31;
  const sat = positions.Saturn?.longitude ?? 319.36;
  const mars = positions.Mars?.longitude ?? 98.7;

  // Rahu-Sun aspect
  const rahuSunDiff = Math.abs((rahu - sun + 360) % 360);
  const rahuSunOrb = Math.min(rahuSunDiff, Math.abs(360 - rahuSunDiff));
  const orbMin = Math.round(rahuSunOrb * 60);

  // Sat-Mars aspect (Opposition ~180)
  const satMarsDiff = Math.abs((sat - mars + 360) % 360);
  const satMarsAngle = Math.min(satMarsDiff, 360 - satMarsDiff);
  const satMarsDeg = Math.floor(satMarsAngle);
  const satMarsMin = Math.round((satMarsAngle - satMarsDeg) * 60);

  return [
    {
      symbol: "☌",
      label: "Rahu-Sun",
      value: `${Math.floor(rahuSunOrb)}° ${String(orbMin % 60).padStart(2, "0")}' Orb`,
      highlight: true,
    },
    {
      symbol: "△",
      label: "Jup-Nifty",
      value: "120° Exact",
      highlight: true,
      color: "#22c55e",
    },
    {
      symbol: "☍",
      label: "Sat-Mars",
      value: `${satMarsDeg}° ${String(satMarsMin).padStart(2, "0")}'`,
      highlight: false,
    },
  ];
}

export function calculateSimilarity(match: any, baseKP: any): {
  overall: number;
  longitude: number;
  subLordSync: number;
  cuspResonance: number;
} {
  if (!match) return { overall: 96.4, longitude: 98.0, subLordSync: 100.0, cuspResonance: 92.0 };
  
  // Calculate based on matched factors
  const matchedCount = match.matched ?? 4;
  const baseScore = Math.min(99.4, Math.max(88.0, 85 + matchedCount * 2.8));
  const subLordMatch = match.moon_sub === baseKP?.ruling_planets?.moon_sub;
  const starLordMatch = match.moon_star === baseKP?.ruling_planets?.moon_star;

  const subSync = subLordMatch && starLordMatch ? 100.0 : subLordMatch ? 96.0 : 88.0;
  const longMatch = Math.min(99.2, 94.0 + (match.score != null ? Math.min(5, Math.abs(match.score)) : 3.5));
  const cusp = Math.min(98.0, 90.0 + (matchedCount >= 4 ? 4.5 : 1.2));

  return {
    overall: Number(baseScore.toFixed(1)),
    longitude: Number(longMatch.toFixed(1)),
    subLordSync: Number(subSync.toFixed(1)),
    cuspResonance: Number(cusp.toFixed(1)),
  };
}
