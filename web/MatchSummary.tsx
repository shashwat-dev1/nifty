import React from 'react';
const value=(n:any,suffix='')=>n==null||!Number.isFinite(Number(n))?'Unavailable':Number(n).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})+suffix;
export function MatchSummary({stats,busy,error,horizon,enabled,supported}:any){
 const n=stats?.complete_forward_windows??0;
 return <section className="match-summary" aria-label="Match outcome summary"><div className="match-summary-heading"><h2>Historical match summary</h2>{supported&&<span>{horizon}-minute movement</span>}</div>
 {!enabled?<p>{supported?'Enable matching and choose at least one factor to see the summary.':'Select an intraday horizon to summarize market movements.'}</p>:busy?<p role="status">Calculating outcomes across all matching records…</p>:error?<p role="alert">The outcome summary could not load. Please retry.</p>:!stats?<p>Waiting for historical matches…</p>:<>
 <p>All <strong>{stats.matches}</strong> matches under the selected criteria · {stats.with_data} with a reference price · <strong>{n} valid outcomes</strong> · {stats.matches-n} unavailable outcomes. Not limited to the first ten table rows.</p>
 <div className="match-direction-cards">{[['Up',stats.positive,stats.positive_percent,'up'],['Down',stats.negative,stats.negative_percent,'down'],['Neutral',stats.flat,stats.neutral_percent,'flat']].map(([label,count,pct,tone])=><div className={'match-direction-card '+tone} key={String(label)}><span>{label}</span><strong>{count??0}</strong><small>{value(pct,'%')} of {n} valid outcomes</small></div>)}</div>
 {n>0&&<div className="match-direction-bar" aria-label="Observed direction frequencies">{[['Up',stats.positive_percent,'up'],['Down',stats.negative_percent,'down'],['Neutral',stats.neutral_percent,'flat']].map(([label,pct,tone])=><div className={String(tone)} key={String(label)} style={{width:Number(pct)+'%'}} title={label+': '+value(pct,'%')}/>)}</div>}
 <div className="match-movement-cards">{[['Average up move',stats.average_positive_points],['Median up move',stats.median_positive_points],['Average down move',stats.average_negative_points],['Median down move',stats.median_negative_points],['Overall average',stats.average_points],['Overall median',stats.median_points]].map(([label,v])=><div key={String(label)}><span>{label}</span><strong>{value(v,' pts')}</strong></div>)}</div>
 <p className="match-summary-note">Movements use genuine candle-close prices over the selected horizon. Neutral means exactly zero movement (±0%). Missing or incomplete windows are excluded from percentages and averages. Frequencies describe this historical sample, not future probabilities; nearby or overlapping matches may be dependent.</p>
 </>}
 </section>
}
