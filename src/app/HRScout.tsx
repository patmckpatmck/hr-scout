"use client";

import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";

// ═══════════════════════════════════════════════════════════════════════════════
// STATIC DATA (for matchups tab rendering)
// ═══════════════════════════════════════════════════════════════════════════════
const PARK_FACTORS = {
  LAD: { L: 10, R: 9,  name: "Dodger Stadium" },
  BAL: { L: 9,  R: 9,  name: "Camden Yards" },
  NYY: { L: 10, R: 6,  name: "Yankee Stadium" },
  LAA: { L: 8,  R: 8,  name: "Angel Stadium" },
  ATH: { L: 8,  R: 8,  name: "Sutter Health Park" },
  OAK: { L: 8,  R: 8,  name: "Sutter Health Park" },
  TOR: { L: 7,  R: 7,  name: "Rogers Centre" },
  DET: { L: 7,  R: 7,  name: "Comerica Park" },
  TB:  { L: 7,  R: 7,  name: "Tropicana Field" },
  COL: { L: 9,  R: 10, name: "Coors Field" },
  HOU: { L: 6,  R: 6,  name: "Minute Maid Park" },
  SEA: { L: 6,  R: 6,  name: "T-Mobile Park" },
  PHI: { L: 7,  R: 6,  name: "Citizens Bank Park" },
  AZ:  { L: 6,  R: 6,  name: "Chase Field" },
  CHC: { L: 6,  R: 6,  name: "Wrigley Field" },
  NYM: { L: 5,  R: 5,  name: "Citi Field" },
  ATL: { L: 5,  R: 5,  name: "Truist Park" },
  CWS: { L: 5,  R: 5,  name: "Guaranteed Rate Field" },
  CIN: { L: 5,  R: 5,  name: "Great American Ball Park" },
  MIL: { L: 5,  R: 5,  name: "American Family Field" },
  CLE: { L: 4,  R: 4,  name: "Progressive Field" },
  WSH: { L: 4,  R: 4,  name: "Nationals Park" },
  MIN: { L: 4,  R: 4,  name: "Target Field" },
  BOS: { L: 6,  R: 3,  name: "Fenway Park" },
  STL: { L: 3,  R: 3,  name: "Busch Stadium" },
  MIA: { L: 3,  R: 3,  name: "loanDepot Park" },
  TEX: { L: 3,  R: 3,  name: "Globe Life Field" },
  SD:  { L: 2,  R: 2,  name: "Petco Park" },
  KC:  { L: 2,  R: 2,  name: "Kauffman Stadium" },
  SF:  { L: 3,  R: 1,  name: "Oracle Park" },
  PIT: { L: 1,  R: 1,  name: "PNC Park" },
};

const DOMES = new Set(["TB","TOR","HOU","SEA","AZ","MIL","MIA","TEX","MIN"]);

const BULLPEN = {
  COL:10, LAA:9.47, OAK:9.47, WSH:8.40, LAD:8.30, BAL:8.09, MIA:8.09,
  HOU:7.98, NYY:7.87, DET:7.87, TB:7.87, ATH:7.77, CIN:7.77, ATL:7.66,
  CWS:7.55, PHI:7.34, AZ:7.02, CHC:7.02, TOR:6.91, TEX:6.70, MIN:6.49,
  NYM:6.38, SEA:6.28, KC:6.17, MIL:5.96, PIT:5.85, SD:5.43, SF:5.11,
  CLE:5.00, STL:4.79, BOS:4.79,
};

const scoreColor = (s: number) => s>=7.5?"#e8e020":s>=6.5?"#86efac":s>=5.5?"#93c5fd":"#94a3b8";
const factorBg   = (s: number) => `rgba(232,224,32,${0.15+(s/10)*0.6})`;


interface Data {
  date: string;
  generatedAt: string;
  games: Array<{
    homeTeam: string;
    awayTeam: string;
    homePitcher: string;
    awayPitcher: string;
    homePitcherHand: string;
    awayPitcherHand: string;
  }>;
  players: Array<{
    name: string;
    team: string;
    hand: string;
    score: number;
    factors: Record<string, number>;
    matchup: string;
    pitcher: string;
    pitcherHand: string;
    parkName: string;
    windInfo: { speed: number; deg: number; score: number; isDome: boolean };
    xhrScore: number;
    evScore: number;
    bvpScore: number;
    bvpAb: number;
    adjScore: number;
    fdOdds: string | null;
    recent: { r5: number; r10: number };
    flags?: string[];
  }>;
  windData: Record<string, { speed: number; deg: number }>;
}

interface HistoryPlayer {
  name: string;
  team: string;
  rank: number;
  score: number;
  hitHR: boolean;
  autoResulted?: boolean;
}

interface HistoryDay {
  date: string;
  generatedAt: string;
  players: HistoryPlayer[];
}

function vegasModifier(odds: number): number {
  if (odds <= 200) return 0.5;
  if (odds <= 400) return 0;
  if (odds <= 600) return -0.3;
  return -0.5;
}

// Team concentration cap.
//   - max 2 players per team in display positions 1-10
//   - max 2 players per team in display positions 11-20
//   - so a team appears at most 4 times in the top 20
// Pure function: no React, no side effects. Returns a new array.
// Defensive: normalizes team strings via .trim().toUpperCase() before bucketing.
function applyTeamCap<T extends { team: string }>(
  players: T[]
): (T & { _capped?: boolean })[] {
  type R = T & { _capped?: boolean };
  const normalize = (t: string | undefined | null) => (t || "").trim().toUpperCase();
  const result: R[] = [];
  const teamCount: Record<string, { top10: number; top20: number }> = {};
  const counts = (team: string) => {
    const key = normalize(team);
    if (!teamCount[key]) teamCount[key] = { top10: 0, top20: 0 };
    return teamCount[key];
  };

  // Single-pass sequential placement: walk all players in score order.
  // Try to place each one; if their team's cap for the current zone is full,
  // add them to deferred. After each successful placement, drain deferred
  // into any newly-opened zone slots.
  const deferred: T[] = [];

  const tryPlace = (p: T, capped: boolean): boolean => {
    const slot = result.length + 1;
    if (slot > 20) return false;
    const c = counts(p.team);
    const zone = slot <= 10 ? "top10" : "top20";
    if (c[zone] >= 2) return false;
    result.push(capped ? { ...p, _capped: true } as R : p as R);
    c[zone] += 1;
    return true;
  };

  const drainDeferred = () => {
    let placed = true;
    while (placed && deferred.length > 0 && result.length < 20) {
      placed = false;
      for (let i = 0; i < deferred.length; i++) {
        if (tryPlace(deferred[i], true)) {
          deferred.splice(i, 1);
          placed = true;
          break;
        }
      }
    }
  };

  for (const p of players) {
    if (result.length >= 20) {
      deferred.push(p);
      continue;
    }
    if (!tryPlace(p, false)) {
      deferred.push(p);
    }
    drainDeferred();
  }

  return [...result, ...deferred as R[]];
}

const HR_STORAGE_KEY = "hrScout:hitHR";
const hrKey = (date: string, name: string) => `${date}|${name}`;

// Static styles for memoized HistoryRow (defined outside component to preserve identity)
const HR_TD: React.CSSProperties = { padding:"9px 10px", fontSize:"12px", borderBottom:"1px solid #070d0f" };
const HR_TD_DATE: React.CSSProperties = { ...HR_TD, fontSize:"11px", color:"#64748b" };
const HR_TD_RANK: React.CSSProperties = { ...HR_TD, fontFamily:"'Bebas Neue',monospace", fontSize:"20px", color:"#1e3a2a", textAlign:"center", width:"30px" };
const HR_TD_CENTER: React.CSSProperties = { ...HR_TD, textAlign:"center" };
const HR_NAME: React.CSSProperties = { fontWeight:"600", fontSize:"13px" };
const HR_BADGE: React.CSSProperties = { display:"inline-block", padding:"1px 5px", borderRadius:"3px", background:"#0f2518", fontSize:"9px", fontWeight:"700", color:"#86efac", marginLeft:"5px" };
const HR_CHECK: React.CSSProperties = { width:"16px", height:"16px", accentColor:"#e8e020", cursor:"pointer" };
const scoreCellColor = (s: number) => s>=7.5?"#e8e020":s>=6.5?"#86efac":s>=5.5?"#93c5fd":"#94a3b8";

interface HistoryRowProps {
  date: string;
  name: string;
  team: string;
  rank: number;
  score: number;
  hitHR: boolean;
  autoResulted: boolean;
  zebra: boolean;
}
const HistoryRow = memo(function HistoryRow({
  date, name, team, rank, score, hitHR, autoResulted, zebra,
}: HistoryRowProps) {
  const resultIcon = !autoResulted ? "⏳" : hitHR ? "✅" : "❌";
  const resultTitle = !autoResulted ? "Pending — not yet auto-resulted" : hitHR ? "Hit a HR" : "Did not hit a HR";
  return (
    <tr style={{background: zebra ? "#060d09" : "transparent"}}>
      <td style={HR_TD_RANK}>{rank}</td>
      <td style={HR_TD}><span style={HR_NAME}>{name}</span></td>
      <td style={HR_TD}><span style={HR_BADGE}>{team}</span></td>
      <td style={{...HR_TD, fontFamily:"'Bebas Neue',monospace", fontSize:"24px", fontWeight:"700", color:scoreCellColor(score), textAlign:"right"}}>{score.toFixed(2)}</td>
      <td style={HR_TD_CENTER}>
        <span title={resultTitle} style={{fontSize:"16px",cursor:"default"}}>{resultIcon}</span>
      </td>
    </tr>
  );
});

export default function HRScout({ data, history: initialHistory }: { data: Data | null; history: HistoryDay[] | null }) {
  const [tab, setTab] = useState("top20");
  const [odds, setOdds] = useState<Record<string, string>>({});
  const [history] = useState<HistoryDay[]>(initialHistory || []);
  const [minScore, setMinScore] = useState("");
  // Lightweight hitHR state: {`${date}|${name}`: true} — cheap to update
  const [hrOverrides, setHrOverrides] = useState<Record<string, boolean>>({});
  const prevGenRef = useRef(data?.generatedAt);
  useEffect(() => {
    if (data?.generatedAt && data.generatedAt !== prevGenRef.current) {
      setOdds({});
      prevGenRef.current = data.generatedAt;
    }
  }, [data?.generatedAt]);

  // Load hitHR state from localStorage on mount (falls back to server history)
  useEffect(() => {
    if (typeof window === "undefined") return;
    const seed: Record<string, boolean> = {};
    for (const day of initialHistory || []) {
      for (const p of day.players) {
        if (p.hitHR) seed[hrKey(day.date, p.name)] = true;
      }
    }
    try {
      const stored = localStorage.getItem(HR_STORAGE_KEY);
      if (stored) Object.assign(seed, JSON.parse(stored));
    } catch {}
    setHrOverrides(seed);
  }, [initialHistory]);

  const toggleHR = useCallback((date: string, playerName: string, hitHR: boolean) => {
    const key = hrKey(date, playerName);
    setHrOverrides(prev => {
      const next = hitHR ? { ...prev, [key]: true } : (() => {
        const n = { ...prev };
        delete n[key];
        return n;
      })();
      try { localStorage.setItem(HR_STORAGE_KEY, JSON.stringify(next)); } catch {}
      return next;
    });
    // Fire-and-forget — don't block UI on network
    fetch("/api/history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date, playerName, hitHR }),
    }).catch(() => {});
  }, []);

  const games = data?.games || [];
  const date = data?.date || null;
  const windData = data?.windData || {};
  const generatedAt = data?.generatedAt || null;

  // ── Rankings pipeline ──
  // 1. raw players → 2. sort by score desc → 3. applyTeamCap → 4. render
  // The output of this pipeline (cappedPlayers) is the ONLY array used in the
  // Rankings table JSX. No further sort/filter happens after it.
  const cappedPlayers = useMemo(() => {
    const raw = data?.players || [];
    const noIL = raw.filter(p => !p.flags?.includes("IL"));
    const sorted = [...noIL].sort((a, b) => b.score - a.score);
    // STEP 1 — diagnostic: log raw team strings before the cap runs
    if (typeof window !== "undefined" && sorted.length > 0) {
      console.log("[applyTeamCap] RAW top 10 (BEFORE cap) — exact team strings:");
      sorted.slice(0, 10).forEach((p, i) => {
        console.log(
          `  ${String(i + 1).padStart(2, " ")}. ${p.name} | team=${JSON.stringify(p.team)} | len=${(p.team || "").length} | score=${p.score}`
        );
      });
    }
    return applyTeamCap(sorted);
  }, [data?.players]);

  // STEP 3 — verification: log capped output with team strings + counts
  useEffect(() => {
    if (typeof window === "undefined" || cappedPlayers.length === 0) return;
    console.log("[applyTeamCap] cappedPlayers — top 20 (this is what the table renders):");
    cappedPlayers.slice(0, 20).forEach((p, i) => {
      console.log(
        `  ${String(i + 1).padStart(2, " ")}. ${p.name.padEnd(25)} team=${JSON.stringify(p.team)}${(p as { _capped?: boolean })._capped ? " [capped]" : ""}`
      );
    });
    // Sanity check: count per team in each tier (using normalized keys)
    const norm = (t: string) => (t || "").trim().toUpperCase();
    const top10Counts: Record<string, number> = {};
    const top20Counts: Record<string, number> = {};
    cappedPlayers.slice(0, 10).forEach(p => { const k = norm(p.team); top10Counts[k] = (top10Counts[k] || 0) + 1; });
    cappedPlayers.slice(10, 20).forEach(p => { const k = norm(p.team); top20Counts[k] = (top20Counts[k] || 0) + 1; });
    console.log("[applyTeamCap] Top 10 team counts:", top10Counts);
    console.log("[applyTeamCap] Ranks 11-20 team counts:", top20Counts);
    const violations10 = Object.entries(top10Counts).filter(([, n]) => n > 2);
    const violations20 = Object.entries(top20Counts).filter(([, n]) => n > 2);
    if (violations10.length || violations20.length) {
      console.error("[applyTeamCap] CAP VIOLATED:", { top10: violations10, top11_20: violations20 });
    } else {
      console.log("[applyTeamCap] ✓ Cap enforced correctly (max 2/team per tier)");
    }
  }, [cappedPlayers]);

  // ── History tab: memoized derived data (only recomputes when inputs change) ──
  const threshold = parseFloat(minScore) || 0;
  const historyRows = useMemo(() => {
    const sortedDays = [...history].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
    return sortedDays.flatMap(day =>
      day.players
        .filter(p => p.score >= threshold)
        .map(p => ({
          name: p.name, team: p.team, rank: p.rank, score: p.score, date: day.date,
          hitHR: p.hitHR, autoResulted: p.autoResulted ?? false,
        }))
    );
  }, [history, threshold]);

  // Group history rows by date for accordion display
  const historyGroups = useMemo(() => {
    const sortedDays = [...history].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
    return sortedDays.map(day => {
      const players = day.players
        .filter(p => p.score >= threshold)
        .map(p => ({
          name: p.name, team: p.team, rank: p.rank, score: p.score, date: day.date,
          hitHR: p.hitHR, autoResulted: p.autoResulted ?? false,
        }));
      const resulted = players.filter(p => p.autoResulted);
      const hrCount = resulted.filter(p => p.hitHR).length;
      return { date: day.date, players, totalPlayers: players.length, hrCount };
    });
  }, [history, threshold]);

  // Track which date groups are expanded — today open by default
  const todayStr = data?.date || "";
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  const isGroupOpen = useCallback((date: string, state: Record<string, boolean>) => {
    if (date in state) return state[date];
    return date === todayStr;
  }, [todayStr]);
  const toggleGroup = useCallback((date: string) => {
    setOpenGroups(prev => ({ ...prev, [date]: !isGroupOpen(date, prev) }));
  }, [isGroupOpen]);

  const historyStats = useMemo(() => {
    // Only count rows that have been auto-resulted
    const resulted = historyRows.filter(r => r.autoResulted);
    const hitRate = (arr: typeof resulted) => {
      const t = arr.length;
      const h = arr.filter(r => r.hitHR).length;
      return t > 0 ? `${h}/${t} (${(h/t*100).toFixed(1)}%)` : "—";
    };
    const r1_5 = resulted.filter(r => r.rank >= 1 && r.rank <= 5);
    const r6_10 = resulted.filter(r => r.rank >= 6 && r.rank <= 10);
    const r11_20 = resulted.filter(r => r.rank >= 11 && r.rank <= 20);
    const hit = resulted.filter(r => r.hitHR);
    const miss = resulted.filter(r => !r.hitHR);
    return {
      overall: hitRate(resulted),
      r1_5: hitRate(r1_5),
      r6_10: hitRate(r6_10),
      r11_20: hitRate(r11_20),
      avgHit: hit.length > 0 ? (hit.reduce((s, r) => s + r.score, 0) / hit.length).toFixed(2) : "—",
      avgMiss: miss.length > 0 ? (miss.reduce((s, r) => s + r.score, 0) / miss.length).toFixed(2) : "—",
    };
  }, [historyRows]);

  const S = {
    app:   { minHeight:"100dvh", minWidth:"100vw", background:"#060a0c", color:"#e2e8f0", fontFamily:"'DM Sans','Segoe UI',sans-serif" } as React.CSSProperties,
    hdr:   { background:"linear-gradient(135deg,#07110a,#0d1b2a)", borderBottom:"1px solid #0f2518", padding:"18px 28px", display:"flex" as const, alignItems:"center" as const, justifyContent:"space-between" as const },
    logo:  { fontFamily:"'Bebas Neue','Impact',monospace", fontSize:"32px", letterSpacing:"3px", color:"#e8e020" },
    sub:   { fontSize:"10px", color:"#475569", letterSpacing:"1px", textTransform:"uppercase" as const, marginTop:"2px" },
    tabs:  { display:"flex" as const, background:"#070d0f", borderBottom:"1px solid #0f1f18", padding:"0 28px" },
    tab:   (a: boolean) => ({ padding:"12px 18px", fontSize:"11px", fontWeight:"700" as const, letterSpacing:"0.8px", textTransform:"uppercase" as const, border:"none", borderBottom:a?"2px solid #e8e020":"2px solid transparent", background:"transparent", color:a?"#e8e020":"#475569", cursor:"pointer" as const }),
    body:  { padding:"22px 28px", maxWidth:"1140px" },
    tbl:   { width:"100%", borderCollapse:"collapse" as const },
    th:    { padding:"8px 10px", fontSize:"9px", fontWeight:"800" as const, letterSpacing:"1.2px", textTransform:"uppercase" as const, color:"#334155", textAlign:"left" as const, borderBottom:"1px solid #0f2518" },
    td:    { padding:"9px 10px", fontSize:"12px", borderBottom:"1px solid #070d0f" },
    rank:  { fontFamily:"'Bebas Neue',monospace", fontSize:"20px", color:"#1e3a2a", textAlign:"center" as const, width:"30px" },
    sc:    (s: number) => ({ fontFamily:"'Bebas Neue',monospace", fontSize:"24px", fontWeight:"700" as const, color:scoreColor(s), textAlign:"right" as const }),
    pip:   (v: number) => ({ display:"inline-block" as const, width:`${Math.max(4,(v/10)*52)}px`, height:"3px", background:factorBg(v), borderRadius:"2px", verticalAlign:"middle" as const, marginRight:"4px" }),
    badge: { display:"inline-block" as const, padding:"1px 5px", borderRadius:"3px", background:"#0f2518", fontSize:"9px", fontWeight:"700" as const, color:"#86efac", marginLeft:"5px" },
    wind:  (ws: number, isDome: boolean) => ({ color: isDome?"#475569":ws>=7?"#e8e020":ws>=5?"#86efac":"#94a3b8", fontSize:"11px" }),
  };

  return (
    <div style={S.app}>
      <div style={S.hdr}>
        <div>
          <div style={{display:"flex",alignItems:"center",gap:"10px"}}>
            <span style={{fontSize:"26px"}}>⚾</span>
            <span style={S.logo}>HR SCOUT</span>
          </div>
          <div style={S.sub}>
            Daily MLB Home Run Prediction
            {generatedAt && <span style={{marginLeft:"12px",color:"#334155"}}>· Updated {new Date(generatedAt).toLocaleTimeString()}</span>}
          </div>
        </div>
        <div style={{textAlign:"right",lineHeight:"1.6",fontSize:"11px",color:"rgba(255,255,255,0.55)",fontWeight:400,letterSpacing:"0.3px"}}>
          <div>@hrmagicball</div>
          <div>homerunscout@gmail.com</div>
          <div>homerunscout.com</div>
        </div>
      </div>

      <div style={S.tabs}>
        {([["top20","🏆 Today's Top 20"],["scout","⚾ Rankings"],["history","📊 Previous HRs"],["matchups","🏟 Matchups"]] as const).map(([id,label])=>(
          <button key={id} style={S.tab(tab===id)} onClick={()=>setTab(id)}>{label}</button>
        ))}
      </div>

      <div style={S.body}>

        {/* ── TOP 20 TAB ── */}
        {tab==="top20" && (
          <div>
            {cappedPlayers.length > 0 ? (
              <>
                <div style={{marginBottom:"16px"}}>
                  <div style={{fontFamily:"'Bebas Neue',monospace",fontSize:"22px",color:"#e8e020",letterSpacing:"1px"}}>TODAY'S TOP 20 — {date}</div>
                  <div style={{fontSize:"11px",color:"#334155",marginTop:"2px"}}>Sorted by Adjusted Score · lineup-filtered · wind-adjusted</div>
                </div>
                <div style={{overflowX:"auto",background:"#060a0c",WebkitOverflowScrolling:"touch"} as React.CSSProperties}>
                <table style={{...S.tbl,minWidth:"560px"}}>
                  <thead>
                    <tr>
                      <th style={{...S.th,textAlign:"center",width:"40px"}}>#</th>
                      <th style={S.th}>Player</th>
                      <th style={S.th}>Matchup</th>
                      <th style={{...S.th,textAlign:"right"}}>Adj Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(() => {
                      const sorted = [...cappedPlayers].sort((a, b) => b.adjScore - a.adjScore);
                      const top20 = applyTeamCap(sorted).slice(0, 20);
                      return top20.map((p, i) => (
                        <tr key={p.name+i} style={{background:i%2===0?"transparent":"#060d09"}}
                          onMouseEnter={e=>e.currentTarget.style.background="#0a1810"}
                          onMouseLeave={e=>e.currentTarget.style.background=i%2===0?"transparent":"#060d09"}>
                          <td style={{...S.td,...S.rank}}>{i+1}</td>
                          <td style={S.td}>
                            <span style={{fontWeight:"600",fontSize:"13px"}}>{p.name}</span>
                            <span style={S.badge}>{p.team}</span>
                            {p.flags?.includes("IL") && <span title="On Injured List" style={{marginLeft:"4px",cursor:"default"}}>⚠️</span>}
                            <span style={{marginLeft:"6px",fontSize:"10px",color:"#475569"}}>{p.hand==="L"?"LHH":p.hand==="R"?"RHH":"SWI"}</span>
                          </td>
                          <td style={{...S.td,fontSize:"11px",color:"#64748b"}}>
                            <span style={{color:"#94a3b8"}}>{p.matchup}</span>
                            <div style={{color:"#475569",fontSize:"10px"}}>{p.pitcher} ({p.pitcherHand}HP)</div>
                          </td>
                          <td style={S.td}>
                            <div style={{textAlign:"right"}}>
                              <span style={{fontFamily:"'Bebas Neue',monospace",fontSize:"24px",fontWeight:"700",color:scoreColor(p.adjScore)}}>{p.adjScore.toFixed(2)}</span>
                              {!p.fdOdds && <span style={{marginLeft:"4px",fontSize:"10px",color:"#475569"}} title="No odds entered — showing base score">*</span>}
                            </div>
                          </td>
                        </tr>
                      ));
                    })()}
                  </tbody>
                </table>
                </div>
              </>
            ) : (
              <div style={{textAlign:"center",padding:"72px 20px"}}>
                <div style={{fontSize:"48px",marginBottom:"12px"}}>⏳</div>
                <div style={{fontFamily:"'Bebas Neue',monospace",fontSize:"20px",color:"#e8e020",marginBottom:"8px"}}>WAITING FOR TODAY'S DATA</div>
                <div style={{fontSize:"12px",color:"#475569"}}>Scores will appear once lineups are confirmed.</div>
              </div>
            )}
          </div>
        )}

        {/* ── SCOUT TAB ── */}
        {tab==="scout" && (
          <div>
            {!data && (
              <div style={{textAlign:"center",padding:"72px 20px"}}>
                <div style={{fontSize:"52px",marginBottom:"16px",filter:"grayscale(0.3)"}}>⚾</div>
                <div style={{fontFamily:"'Bebas Neue',monospace",fontSize:"30px",color:"#0f2518",letterSpacing:"2px",marginBottom:"8px"}}>NO DATA YET</div>
                <div style={{fontSize:"12px",color:"#334155",lineHeight:"1.8"}}>
                  Run <code style={{color:"#86efac"}}>python3 scripts/generate.py</code> to generate today's predictions.
                </div>
              </div>
            )}

            {cappedPlayers.length > 0 && (
              <>
                <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-end",marginBottom:"16px"}}>
                  <div>
                    <div style={{fontFamily:"'Bebas Neue',monospace",fontSize:"22px",color:"#e8e020",letterSpacing:"1px"}}>TODAY'S HR LEADERS — {date}</div>
                    <div style={{fontSize:"11px",color:"#334155",marginTop:"2px"}}>{cappedPlayers.length} confirmed starters scored · lineup-filtered · wind-adjusted</div>
                  </div>
                </div>
                <div style={{overflowX:"auto",background:"#060a0c",WebkitOverflowScrolling:"touch"} as React.CSSProperties}>
                <table style={{...S.tbl,minWidth:"960px"}}>
                  <thead>
                    <tr>
                      <th style={{...S.th,textAlign:"center"}}>#</th>
                      <th style={S.th}>Player</th>
                      <th style={S.th}>Matchup</th>
                      <th style={S.th}>Park ✦ Hand</th>
                      <th style={S.th}>xHR</th>
                      <th style={S.th}>Pitcher HR/9</th>
                      <th style={S.th}>Wind 🌬️</th>
                      <th style={S.th}>BvP</th>
                      <th style={S.th}>EV Trend</th>
                      <th style={S.th}>Recent 5/10</th>
                      <th style={{...S.th,textAlign:"right"}}>Score</th>
                      <th style={{...S.th,textAlign:"center"}}>FD Odds</th>
                      <th style={{...S.th,textAlign:"right"}}>Adj Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cappedPlayers.slice(0,40).map((p,i)=>(
                      <tr key={p.name+i} style={{background:i%2===0?"transparent":"#060d09"}}
                        onMouseEnter={e=>e.currentTarget.style.background="#0a1810"}
                        onMouseLeave={e=>e.currentTarget.style.background=i%2===0?"transparent":"#060d09"}>
                        <td style={{...S.td,...S.rank}}>{i+1}</td>
                        <td style={S.td}>
                          <span style={{fontWeight:"600",fontSize:"13px"}}>{p.name}</span>
                          <span style={S.badge}>{p.team}</span>
                          {p.flags?.includes("IL") && <span title="On Injured List" style={{marginLeft:"4px",cursor:"default"}}>⚠️</span>}
                          {p.flags?.includes("NEW") && <span title="Not in database — using league avg defaults" style={{marginLeft:"4px",cursor:"default"}}>🆕</span>}
                          {(p as typeof p & {_capped?: boolean})._capped && <span title="Displaced by team concentration cap" style={{marginLeft:"4px",fontSize:"9px",color:"#475569",cursor:"default"}}>📊 Capped</span>}
                        </td>
                        <td style={{...S.td,fontSize:"11px",color:"#64748b"}}>
                          <span style={{color:"#94a3b8"}}>{p.matchup}</span>
                          <div style={{color:"#475569",fontSize:"10px"}}>{p.pitcher} ({p.pitcherHand}HP)</div>
                        </td>
                        <td style={S.td} title={p.parkName}>
                          <div style={{color:scoreColor(p.factors.ballpark),fontSize:"12px",fontWeight:"600",cursor:"default"}}>{p.factors.ballpark}/10</div>
                          <div style={{fontSize:"10px",color:"#475569"}}>{p.hand==="L"?"LHH":p.hand==="R"?"RHH":"SWI"}</div>
                        </td>
                        <td style={S.td}>
                          <span style={S.pip(p.xhrScore)}/>
                          <span style={{color:scoreColor(p.xhrScore),fontSize:"12px"}}>{p.xhrScore}/10</span>
                        </td>
                        <td style={S.td}>
                          <span style={{color:scoreColor(p.factors.pitcherHR9),fontSize:"12px"}}>{p.factors.pitcherHR9}/10</span>
                        </td>
                        <td style={S.td}>
                          {p.windInfo.isDome
                            ? <span style={{color:"#334155",fontSize:"11px"}}>dome</span>
                            : <span style={S.wind(p.windInfo.score, p.windInfo.isDome)}>
                                {p.windInfo.speed.toFixed(0)}mph · {p.windInfo.score}/10
                              </span>
                          }
                        </td>
                        <td style={S.td}>
                          <div style={{color:scoreColor(p.bvpScore),fontSize:"12px",fontWeight:"600"}}>{p.bvpScore}/10</div>
                          <div style={{fontSize:"10px",color:"#475569"}}>{p.bvpAb > 0 ? `(${p.bvpAb} AB)` : "(n/a)"}</div>
                        </td>
                        <td style={S.td}>
                          <span style={{color:p.evScore>=6?"#86efac":p.evScore<=4?"#f87171":"#94a3b8",fontSize:"12px"}}>
                            {p.evScore>=6?"▲":p.evScore<=4?"▼":"—"} {p.evScore}/10
                          </span>
                        </td>
                        <td style={{...S.td,color:"#64748b",fontSize:"12px"}}>
                          {p.recent.r5}HR / {p.recent.r10}HR
                        </td>
                        <td style={{...S.td,...S.sc(p.score)}}>{p.score.toFixed(2)}</td>
                        <td style={{...S.td,textAlign:"center"}}>
                          {i < 30 ? (
                            <input
                              type="text"
                              placeholder="+350"
                              value={odds[p.name] || ""}
                              onChange={e => setOdds(prev => ({...prev, [p.name]: e.target.value}))}
                              style={{
                                width:"62px", padding:"4px 6px", fontSize:"11px", fontWeight:"600",
                                background:"#0a1810", border:"1px solid #0f2518", borderRadius:"4px",
                                color:"#e8e020", textAlign:"center", outline:"none",
                              }}
                              onFocus={e => e.currentTarget.style.borderColor="#e8e020"}
                              onBlur={e => e.currentTarget.style.borderColor="#0f2518"}
                            />
                          ) : <span style={{color:"#1e3a2a"}}>—</span>}
                        </td>
                        <td style={S.td}>
                          {(() => {
                            const raw = odds[p.name]?.replace(/[+\s]/g, "");
                            const parsed = raw ? parseInt(raw, 10) : NaN;
                            if (isNaN(parsed)) return <span style={{color:"#1e3a2a",fontFamily:"'Bebas Neue',monospace",fontSize:"24px",textAlign:"right",display:"block"}}>—</span>;
                            const adj = p.score + vegasModifier(parsed);
                            const mod = vegasModifier(parsed);
                            return (
                              <div style={{textAlign:"right"}}>
                                <span style={{fontFamily:"'Bebas Neue',monospace",fontSize:"24px",fontWeight:"700",color:scoreColor(adj)}}>{adj.toFixed(2)}</span>
                                <div style={{fontSize:"9px",color:mod>0?"#86efac":mod<0?"#f87171":"#475569"}}>
                                  {mod>0?`+${mod}`:mod<0?`${mod}`:"±0"}
                                </div>
                              </div>
                            );
                          })()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
              </>
            )}
          </div>
        )}

        {/* ── HISTORY TAB ── */}
        {tab==="history" && (
          <div>
            {history.length === 0 ? (
              <div style={{textAlign:"center",padding:"60px",color:"#1e3a2a",fontSize:"13px"}}>
                No history yet. Run the generate script at least once, then check back after marking HR results.
              </div>
            ) : (
              <>
                <div style={{fontFamily:"'Bebas Neue',monospace",fontSize:"22px",color:"#e8e020",letterSpacing:"1px",marginBottom:"16px"}}>
                  PREVIOUS HRS — TRACKING
                </div>

                {/* Stats bar */}
                <div style={{display:"flex",gap:"12px",flexWrap:"wrap",marginBottom:"18px"}}>
                  {[
                    ["Overall", historyStats.overall],
                    ["Rank 1-5", historyStats.r1_5],
                    ["Rank 6-10", historyStats.r6_10],
                    ["Rank 11-20", historyStats.r11_20],
                    ["Avg Score (Hit)", historyStats.avgHit],
                    ["Avg Score (Miss)", historyStats.avgMiss],
                  ].map(([label, val]) => (
                    <div key={label} style={{background:"#060d09",border:"1px solid #0f2518",borderRadius:"8px",padding:"10px 16px",minWidth:"120px"}}>
                      <div style={{fontSize:"9px",color:"#475569",fontWeight:"700",letterSpacing:"1px",textTransform:"uppercase",marginBottom:"4px"}}>{label}</div>
                      <div style={{fontSize:"16px",fontWeight:"700",fontFamily:"'Bebas Neue',monospace",color:"#e8e020",letterSpacing:"0.5px"}}>{val}</div>
                    </div>
                  ))}
                </div>

                {/* Filter */}
                <div style={{marginBottom:"14px",display:"flex",alignItems:"center",gap:"8px"}}>
                  <span style={{fontSize:"11px",color:"#475569",fontWeight:"700"}}>Min Score:</span>
                  <input
                    type="text"
                    placeholder="0"
                    value={minScore}
                    onChange={e => setMinScore(e.target.value)}
                    style={{width:"60px",padding:"4px 8px",fontSize:"12px",background:"#0a1810",border:"1px solid #0f2518",borderRadius:"4px",color:"#e8e020",textAlign:"center",outline:"none"}}
                  />
                  {threshold > 0 && <span style={{fontSize:"11px",color:"#334155"}}>{historyRows.length} players shown</span>}
                </div>

                {/* Accordion by date */}
                {historyGroups.map(group => {
                  const open = isGroupOpen(group.date, openGroups);
                  const hrLabel = group.hrCount > 0 ? `${group.hrCount} HR${group.hrCount !== 1 ? "s" : ""} ✅` : "0 HRs";
                  // Format date for display — strip year, show short form
                  const shortDate = group.date.replace(/, \d{4}$/, "");
                  return (
                    <div key={group.date} style={{marginBottom:"6px"}}>
                      <button
                        onClick={() => toggleGroup(group.date)}
                        style={{
                          width:"100%", display:"flex", alignItems:"center", justifyContent:"space-between",
                          padding:"10px 14px", background: open ? "#0a1810" : "#060d09",
                          border:"1px solid #0f2518", borderRadius: open ? "8px 8px 0 0" : "8px",
                          cursor:"pointer", color:"#e2e8f0", outline:"none",
                        }}
                      >
                        <div style={{display:"flex",alignItems:"center",gap:"10px"}}>
                          <span style={{fontSize:"12px",color:"#475569",transition:"transform 0.15s",transform:open?"rotate(90deg)":"rotate(0deg)"}}>▶</span>
                          <span style={{fontFamily:"'Bebas Neue',monospace",fontSize:"16px",color:"#e8e020",letterSpacing:"0.5px"}}>{shortDate}</span>
                        </div>
                        <span style={{fontSize:"11px",color:"#64748b"}}>
                          {group.totalPlayers} player{group.totalPlayers !== 1 ? "s" : ""} · {hrLabel}
                        </span>
                      </button>
                      {open && (
                        <div style={{border:"1px solid #0f2518",borderTop:"none",borderRadius:"0 0 8px 8px",overflow:"hidden"}}>
                          <table style={S.tbl}>
                            <thead>
                              <tr>
                                <th style={{...S.th,textAlign:"center"}}>Rank</th>
                                <th style={S.th}>Player</th>
                                <th style={S.th}>Team</th>
                                <th style={{...S.th,textAlign:"right"}}>Score</th>
                                <th style={{...S.th,textAlign:"center"}}>Hit HR</th>
                              </tr>
                            </thead>
                            <tbody>
                              {group.players.map((r, i) => (
                                <HistoryRow
                                  key={`${r.date}-${r.name}`}
                                  date={r.date}
                                  name={r.name}
                                  team={r.team}
                                  rank={r.rank}
                                  score={r.score}
                                  hitHR={r.hitHR}
                                  autoResulted={r.autoResulted}
                                  zebra={i % 2 === 1}
                                />
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  );
                })}
              </>
            )}
          </div>
        )}

        {/* ── MATCHUPS TAB ── */}
        {tab==="matchups" && (
          <div>
            {games.length===0
              ? <div style={{textAlign:"center",padding:"60px",color:"#1e3a2a",fontSize:"13px"}}>No game data. Run the generate script first.</div>
              : <>
                  <div style={{fontFamily:"'Bebas Neue',monospace",fontSize:"22px",color:"#e8e020",letterSpacing:"1px",marginBottom:"18px"}}>GAME ENVIRONMENTS — {date}</div>
                  {games.map((g,i)=>{
                    const isDome = DOMES.has(g.homeTeam);
                    const wind = windData[g.homeTeam] || { speed:0, deg:0 };
                    const parkL = PARK_FACTORS[g.homeTeam as keyof typeof PARK_FACTORS]?.L || 5;
                    const parkR = PARK_FACTORS[g.homeTeam as keyof typeof PARK_FACTORS]?.R || 5;
                    const awayBp = BULLPEN[g.awayTeam as keyof typeof BULLPEN]||5;
                    const homeBp = BULLPEN[g.homeTeam as keyof typeof BULLPEN]||5;
                    const rawScore = ((parkL+parkR)/2 + awayBp/2 + homeBp/2) / 3;
                    return (
                      <div key={i} style={{background:"#060d09",border:"1px solid #0f2518",borderRadius:"10px",padding:"16px 20px",marginBottom:"10px",display:"flex",alignItems:"center",gap:"24px"}}>
                        <div style={{flex:"0 0 180px"}}>
                          <div style={{fontSize:"15px",fontWeight:"700"}}>
                            <span style={{color:"#64748b"}}>{g.awayTeam}</span>
                            <span style={{color:"#1e3a2a",margin:"0 8px"}}>@</span>
                            <span style={{color:"#e8e020"}}>{g.homeTeam}</span>
                          </div>
                          <div style={{fontSize:"10px",color:"#334155",marginTop:"3px"}}>{PARK_FACTORS[g.homeTeam as keyof typeof PARK_FACTORS]?.name}</div>
                        </div>
                        <div style={{flex:1,fontSize:"11px",color:"#64748b",lineHeight:"1.8"}}>
                          <div>{g.awayPitcher}({g.awayPitcherHand}) vs {g.homePitcher}({g.homePitcherHand})</div>
                          <div>Park LHH: <span style={{color:scoreColor(parkL)}}>{parkL}</span> · RHH: <span style={{color:scoreColor(parkR)}}>{parkR}</span> · Away BP: <span style={{color:scoreColor(awayBp)}}>{awayBp?.toFixed(1)}</span></div>
                        </div>
                        <div style={{fontSize:"11px",color:isDome?"#334155":"#94a3b8",textAlign:"right"}}>
                          {isDome ? "🏠 dome" : `💨 ${wind.speed.toFixed(0)}mph`}
                        </div>
                        <div style={{fontFamily:"'Bebas Neue',monospace",fontSize:"28px",color:scoreColor(rawScore),minWidth:"52px",textAlign:"right"}}>
                          {rawScore.toFixed(1)}
                        </div>
                      </div>
                    );
                  })}
                </>
            }
          </div>
        )}


      </div>
    </div>
  );
}
