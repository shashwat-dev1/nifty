import React from 'react';
export function OutcomeSummary({stats,busy,error,mode,factors,calculation,horizon,neutral}:any){
 const names:any={day:'Day lord',moon_sign:'Moon sign lord',moon_star:'Moon star lord',moon_sub:'Moon sub lord',lagna:'Lagna lord'};
 const rules=mode==='exact'?Object.keys(names):mode==='partial'?factors:[];
 const n=stats?.complete_forward_windows??0;
 const fmt=(v:any,suffix='')=>v==null?'Unavailable':Number(v).toFixed(2)+suffix;
 return <section className="outcome-summary" aria-label="Historical outcome summary">
 <h3>Historical outcome summary · {horizon} minutes</h3>
 <p>{mode==='partial'?'Partial match: only the following ruling lords were required to match. Other lords may differ.':mode==='exact'?'Exact match: all five ruling lords were required to match.':'Matching method: '+mode+'. These observations use your selected search settings.'}</p>
 {rules.length>0&&<p className="summary-rules">{rules.map((k:string)=>names[k]+': '+(calculation?.ruling_planets?.[k]??'Unavailable')).join(' · ')}</p>}
 {busy?<p role="status">Summarizing all matching records…</p>:error?<p role="alert">Summary could not load: {String(error)}</p>:!stats?<p>Run a historical search to see the summary.</p>:<>
 <div className="summary-cards">{[['Astronomical matches',stats.matches],['With reference price',stats.with_data],['Valid forward outcomes',n],['Unavailable outcomes',stats.matches-n]].map(([label,v])=><div className="summary-card" key={String(label)}><span>{label}</span><strong>{v}</strong></div>)}</div>
 <div className="summary-cards">{[['Positive',stats.positive,stats.positive_percent,'positive'],['Negative',stats.negative,stats.negative_percent,'negative'],['Neutral',stats.flat,stats.neutral_percent,'']].map(([label,count,pct,color])=><div className={'summary-card '+color} key={String(label)}><span>{label}</span><strong>{count??0}</strong><span>{fmt(pct,'%')} of {n} valid outcomes</span></div>)}</div>
 {n>0&&<><div className="outcome-distribution" aria-label="Outcome distribution">{[['Positive',stats.positive_percent,'#50b494'],['Negative',stats.negative_percent,'#d68080'],['Neutral',stats.neutral_percent,'#8b9aaf']].map(([label,pct,color])=><div key={String(label)} title={label+': '+fmt(pct,'%')} style={{width:Number(pct)+'%',background:String(color)}}/>)}</div><p>In this historical sample, {stats.positive} of {n} valid outcomes were positive ({fmt(stats.positive_percent,'%')}), {stats.negative} negative ({fmt(stats.negative_percent,'%')}) and {stats.flat} neutral ({fmt(stats.neutral_percent,'%')}).</p></>}
 <div className="summary-cards">{[['Average movement',fmt(stats.average_points,' pts')],['Median movement',fmt(stats.median_points,' pts')],['Average return',fmt(stats.average_percent,'%')],['Median return',fmt(stats.median_percent,'%')]].map(([label,v])=><div className="summary-card" key={label}><span>{label}</span><strong>{v}</strong></div>)}</div>
 <p>{stats.without_data} matches have no reference price; {stats.incomplete_forward_windows??0} have a reference but an incomplete forward window. Missing data is excluded from outcome percentages.</p>
 <p>Neutral means a return within ±{neutral}%, including the boundaries. These are observed historical frequencies, not validated future probabilities. Repeated or overlapping occurrences may be dependent.{n<30?' Small sample: fewer than 30 valid outcomes; interpret cautiously.':''}</p>
 </>}
 </section>
}
