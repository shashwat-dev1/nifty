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

export function calculateAspectMatrix(positions:Record<string,any>={}){return [['Rahu','Sun'],['Saturn','Mars']].flatMap(([a,b])=>{if(positions[a]?.longitude==null||positions[b]?.longitude==null)return [];const angle=Math.abs((positions[a].longitude-positions[b].longitude+540)%360-180);return [{symbol:'',label:a+' / '+b,value:angle.toFixed(4)+' degrees separation',highlight:false,color:''}]})}
export function calculateSimilarity(match:any,base:any){return {overall:null,longitude:null,subLordSync:null,cuspResonance:null}}
