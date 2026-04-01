"use client";

import { useEffect, useRef, useState } from "react";

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

const IMPS = [
  { icon:"🌬️", tag:"ADDED", tagColor:"#86efac", title:"Wind & Weather (replaces Days w/o HR)",
    body:"Real-time wind speed and direction from Open-Meteo pulled for every outdoor park. Scored per batter handedness — a 20mph tailwind to right field scores a LHH much higher than a RHH at the same park." },
  { icon:"📋", tag:"ADDED", tagColor:"#86efac", title:"Confirmed Lineup Filter",
    body:"Pulls confirmed starting lineups each day. Players not in the lineup return null and are excluded from scoring entirely — eliminating the ~15–20% of daily scores that were wasted on DNP players." },
  { icon:"🎯", tag:"REPLACED", tagColor:"#93c5fd", title:"xHR Rate (replaces Barrel%)",
    body:"Expected home runs per 600 PA from Baseball Savant now drives the contact quality score. More directly predictive than barrel%, especially for gap hitters who occasionally go deep." },
  { icon:"🏟️", tag:"IMPROVED", tagColor:"#c084fc", title:"Park Factor by Handedness",
    body:"Yankee Stadium now scores 10 for LHH, 6 for RHH. Oracle Park scores 3 for LHH, 1 for RHH. Fenway Park scores 6 for LHH, 3 for RHH. Every park now reflects actual directional dimensions." },
  { icon:"🃏", tag:"REMOVED", tagColor:"#f87171", title:"Days Without HR (gambler's fallacy)",
    body:"Removed entirely. Zero autocorrelation in daily HR events — a player 8 days cold is not statistically more likely to go deep. Replaced by Exit Velocity Trend: actual quality-of-contact data showing whether a hitter is making harder contact recently." },
];

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

export default function HRScout({ data, history: initialHistory }: { data: Data | null; history: HistoryDay[] | null }) {
  const [tab, setTab] = useState("scout");
  const [odds, setOdds] = useState<Record<string, string>>({});
  const [history, setHistory] = useState<HistoryDay[]>(initialHistory || []);
  const [minScore, setMinScore] = useState("");
  const prevGenRef = useRef(data?.generatedAt);
  useEffect(() => {
    if (data?.generatedAt && data.generatedAt !== prevGenRef.current) {
      setOdds({});
      prevGenRef.current = data.generatedAt;
    }
  }, [data?.generatedAt]);

  const toggleHR = async (date: string, playerName: string, hitHR: boolean) => {
    setHistory(prev => prev.map(day =>
      day.date === date
        ? { ...day, players: day.players.map(p => p.name === playerName ? { ...p, hitHR } : p) }
        : day
    ));
    await fetch("/api/history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date, playerName, hitHR }),
    });
  };

  const games = data?.games || [];
  const players = data?.players || [];
  const date = data?.date || null;
  const windData = data?.windData || {};
  const generatedAt = data?.generatedAt || null;

  const S = {
    app:   { minHeight:"100vh" as const, background:"#060a0c", color:"#e2e8f0", fontFamily:"'DM Sans','Segoe UI',sans-serif" },
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
    impCard: { background:"linear-gradient(135deg,#07110a,#091520)", border:"1px solid #0f2518", borderRadius:"12px", padding:"20px 22px", marginBottom:"14px" },
    tag:   (col: string) => ({ display:"inline-block" as const, padding:"2px 7px", borderRadius:"3px", border:`1px solid ${col}30`, color:col, fontSize:"10px", fontWeight:"700" as const, marginTop:"8px" }),
  };

  return (
    <div style={S.app}>
      <div style={S.hdr}>
        <div>
          <div style={{display:"flex",alignItems:"center",gap:"10px"}}>
            <span style={{fontSize:"26px"}}>⚾</span>
            <span style={S.logo}>HR SCOUT</span>
            <span style={{background:"#e8e020",color:"#000",fontSize:"9px",fontWeight:"800",padding:"2px 6px",borderRadius:"3px",letterSpacing:"0.5px"}}>v2.0</span>
          </div>
          <div style={S.sub}>
            Daily MLB Home Run Prediction · 5 Model Upgrades Active
            {generatedAt && <span style={{marginLeft:"12px",color:"#334155"}}>· Updated {new Date(generatedAt).toLocaleTimeString()}</span>}
          </div>
        </div>
      </div>

      <div style={S.tabs}>
        {([["scout","⚾ Rankings"],["history","📊 Previous HRs"],["matchups","🏟 Matchups"],["improvements","⚡ What Changed"]] as const).map(([id,label])=>(
          <button key={id} style={S.tab(tab===id)} onClick={()=>setTab(id)}>{label}</button>
        ))}
      </div>

      <div style={S.body}>

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

            {players.length > 0 && (
              <>
                <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-end",marginBottom:"16px"}}>
                  <div>
                    <div style={{fontFamily:"'Bebas Neue',monospace",fontSize:"22px",color:"#e8e020",letterSpacing:"1px"}}>TODAY'S HR LEADERS — {date}</div>
                    <div style={{fontSize:"11px",color:"#334155",marginTop:"2px"}}>{players.length} confirmed starters scored · lineup-filtered · wind-adjusted</div>
                  </div>
                </div>
                <table style={S.tbl}>
                  <thead>
                    <tr>
                      <th style={{...S.th,textAlign:"center"}}>#</th>
                      <th style={S.th}>Player</th>
                      <th style={S.th}>Matchup</th>
                      <th style={S.th}>Park ✦ Hand</th>
                      <th style={S.th}>xHR</th>
                      <th style={S.th}>Pitcher HR/9</th>
                      <th style={S.th}>Wind 🌬️</th>
                      <th style={S.th}>EV Trend</th>
                      <th style={S.th}>Recent 5/10</th>
                      <th style={{...S.th,textAlign:"right"}}>Score</th>
                      <th style={{...S.th,textAlign:"center"}}>FD Odds</th>
                      <th style={{...S.th,textAlign:"right"}}>Adj Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {players.slice(0,40).map((p,i)=>(
                      <tr key={p.name+i} style={{background:i%2===0?"transparent":"#060d09"}}
                        onMouseEnter={e=>e.currentTarget.style.background="#0a1810"}
                        onMouseLeave={e=>e.currentTarget.style.background=i%2===0?"transparent":"#060d09"}>
                        <td style={{...S.td,...S.rank}}>{i+1}</td>
                        <td style={S.td}>
                          <span style={{fontWeight:"600",fontSize:"13px"}}>{p.name}</span>
                          <span style={S.badge}>{p.team}</span>
                          {p.flags?.includes("IL") && <span title="On Injured List" style={{marginLeft:"4px",cursor:"default"}}>⚠️</span>}
                          {p.flags?.includes("NEW") && <span title="Not in database — using league avg defaults" style={{marginLeft:"4px",cursor:"default"}}>🆕</span>}
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
                          <span style={{color:p.evScore>=6?"#86efac":p.evScore<=4?"#f87171":"#94a3b8",fontSize:"12px"}}>
                            {p.evScore>=6?"▲":p.evScore<=4?"▼":"—"} {p.evScore}/10
                          </span>
                        </td>
                        <td style={{...S.td,color:"#64748b",fontSize:"12px"}}>
                          {p.recent.r5}HR / {p.recent.r10}HR
                        </td>
                        <td style={{...S.td,...S.sc(p.score)}}>{p.score.toFixed(2)}</td>
                        <td style={{...S.td,textAlign:"center"}}>
                          {i < 20 ? (
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
            ) : (() => {
              const threshold = parseFloat(minScore) || 0;
              const sortedDays = [...history].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
              const allRows = sortedDays.flatMap(day =>
                day.players
                  .filter(p => p.score >= threshold)
                  .map(p => ({ ...p, date: day.date }))
              );
              const checked = allRows.filter(r => r.hitHR);
              const total = allRows.length;
              const hitRate = (arr: typeof allRows) => {
                const t = arr.length;
                const h = arr.filter(r => r.hitHR).length;
                return t > 0 ? `${h}/${t} (${(h/t*100).toFixed(1)}%)` : "—";
              };
              const r1_5 = allRows.filter(r => r.rank >= 1 && r.rank <= 5);
              const r6_10 = allRows.filter(r => r.rank >= 6 && r.rank <= 10);
              const r11_20 = allRows.filter(r => r.rank >= 11 && r.rank <= 20);
              const avgHit = checked.length > 0
                ? (checked.reduce((s, r) => s + r.score, 0) / checked.length).toFixed(2)
                : "—";
              const misses = allRows.filter(r => !r.hitHR);
              const avgMiss = misses.length > 0
                ? (misses.reduce((s, r) => s + r.score, 0) / misses.length).toFixed(2)
                : "—";

              return (
                <>
                  <div style={{fontFamily:"'Bebas Neue',monospace",fontSize:"22px",color:"#e8e020",letterSpacing:"1px",marginBottom:"16px"}}>
                    PREVIOUS HRS — TRACKING
                  </div>

                  {/* Stats bar */}
                  <div style={{display:"flex",gap:"12px",flexWrap:"wrap",marginBottom:"18px"}}>
                    {[
                      ["Overall", hitRate(allRows)],
                      ["Rank 1-5", hitRate(r1_5)],
                      ["Rank 6-10", hitRate(r6_10)],
                      ["Rank 11-20", hitRate(r11_20)],
                      ["Avg Score (Hit)", avgHit],
                      ["Avg Score (Miss)", avgMiss],
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
                    {threshold > 0 && <span style={{fontSize:"11px",color:"#334155"}}>{allRows.length} players shown</span>}
                  </div>

                  {/* Table */}
                  <table style={S.tbl}>
                    <thead>
                      <tr>
                        <th style={S.th}>Date</th>
                        <th style={{...S.th,textAlign:"center"}}>Rank</th>
                        <th style={S.th}>Player</th>
                        <th style={S.th}>Team</th>
                        <th style={{...S.th,textAlign:"right"}}>Score</th>
                        <th style={{...S.th,textAlign:"center"}}>Hit HR</th>
                      </tr>
                    </thead>
                    <tbody>
                      {allRows.map((r, i) => (
                        <tr key={`${r.date}-${r.name}`} style={{background:i%2===0?"transparent":"#060d09"}}>
                          <td style={{...S.td,fontSize:"11px",color:"#64748b"}}>{r.date}</td>
                          <td style={{...S.td,...S.rank}}>{r.rank}</td>
                          <td style={S.td}>
                            <span style={{fontWeight:"600",fontSize:"13px"}}>{r.name}</span>
                          </td>
                          <td style={S.td}>
                            <span style={S.badge}>{r.team}</span>
                          </td>
                          <td style={{...S.td,...S.sc(r.score)}}>{r.score.toFixed(2)}</td>
                          <td style={{...S.td,textAlign:"center"}}>
                            <input
                              type="checkbox"
                              checked={r.hitHR}
                              onChange={e => toggleHR(r.date, r.name, e.target.checked)}
                              style={{width:"16px",height:"16px",accentColor:"#e8e020",cursor:"pointer"}}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              );
            })()}
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

        {/* ── IMPROVEMENTS TAB ── */}
        {tab==="improvements" && (
          <div>
            <div style={{fontFamily:"'Bebas Neue',monospace",fontSize:"22px",color:"#e8e020",letterSpacing:"1px",marginBottom:"6px"}}>WHAT CHANGED IN v2.0</div>
            <div style={{fontSize:"12px",color:"#475569",marginBottom:"20px",lineHeight:"1.7",maxWidth:"700px"}}>
              All five model upgrades are live. Formula preserved: <code style={{color:"#86efac"}}>SUM(11 factors) / 9</code> —
              Days w/o HR removed, Wind and EV Trend replace it. Park score now handedness-specific.
            </div>
            {IMPS.map((imp,i)=>(
              <div key={i} style={S.impCard}>
                <div style={{display:"flex",gap:"14px",alignItems:"flex-start"}}>
                  <span style={{fontSize:"22px",lineHeight:"1"}}>{imp.icon}</span>
                  <div>
                    <div style={{display:"flex",alignItems:"center",gap:"8px",marginBottom:"6px"}}>
                      <span style={{fontSize:"14px",fontWeight:"700",color:"#e2e8f0"}}>{imp.title}</span>
                      <span style={S.tag(imp.tagColor)}>{imp.tag}</span>
                    </div>
                    <div style={{fontSize:"12px",color:"#64748b",lineHeight:"1.7"}}>{imp.body}</div>
                  </div>
                </div>
              </div>
            ))}
            <div style={{background:"#060d09",border:"1px solid #0f2518",borderRadius:"10px",padding:"16px 20px",fontSize:"11px",color:"#334155",lineHeight:"1.9"}}>
              <strong style={{color:"#e8e020",display:"block",marginBottom:"6px"}}>📐 Updated formula</strong>
              <code style={{color:"#86efac"}}>
                SCORE = (Home/Away + Park[hand] + LHPvRHP + PitcherHR9 + BullpenHR9 + xHR + 2025HRs + Wind + Recent5 + Recent10 + SeasonGap) / 9
              </code>
              <div style={{marginTop:"8px"}}>Wind replaces Days w/o HR · xHR replaces Barrel% · Park is now handedness-specific</div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
