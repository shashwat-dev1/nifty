import React, { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Plotly from "plotly.js-dist-min";
const ist = (t: any) =>
  new Date(new Date(t).getTime() + 19800000).toISOString().slice(0, 19);
export default function SessionChart({ selected, horizon, transitions=[], predictions=[], model="market", completeDay=false, showForecast=true }: any) {
  const node = useRef<HTMLDivElement>(null),
    [interval, setInterval] = useState(1);
  const [view,setView]=useState(completeDay?"day":"window");
  const { data, error, isPending } = useQuery({
    queryKey: ["candles", selected.timestamp, interval],
    queryFn: async () => {
      const r = await fetch(
        "/api/candles?timestamp=" +
          encodeURIComponent(selected.timestamp) +
          "&interval=" +
          interval,
      );
      if (!r.ok) throw Error("Could not load session candles");
      return r.json();
    },
  });
  const forecast=useQuery({queryKey:['historical-overlay',selected.timestamp,horizon,model],enabled:showForecast,queryFn:async()=>{const r=await fetch('/api/historical-forecast?timestamp='+encodeURIComponent(selected.timestamp)+'&model='+model+'&horizon='+horizon);if(!r.ok)return {status:'unavailable',reason:'Forecast unavailable for this horizon'};return r.json()}});
  useEffect(() => {
    if (!node.current || !data?.rows.length) return;
    const el = node.current,
      rows = data.rows,
      stamp = ist(selected.timestamp),
      end = ist(
        new Date(new Date(selected.timestamp).getTime() + horizon * 60000),
      );
    const ref = selected.reference,
      exit = selected["price_" + horizon];
    const shapes: any[] = [
      {
        type: "rect",
        xref: "x",
        yref: "paper",
        x0: stamp,
        x1: end,
        y0: 0,
        y1: 1,
        fillcolor: "#75b6ff",
        opacity: 0.12,
        line: { width: 0 },
      },
      {
        type: "line",
        xref: "x",
        yref: "paper",
        x0: stamp,
        x1: stamp,
        y0: 0,
        y1: 1,
        line: { color: "#75b6ff", dash: "dot" },
      },
    ];
    if (ref != null)
      shapes.push({
        type: "line",
        xref: "paper",
        yref: "y",
        x0: 0,
        x1: 1,
        y0: ref,
        y1: ref,
        line: { color: "#e0be7b", dash: "dash" },
      });
    const traces: any[] = [
      {
        type: "candlestick",
        name: "NIFTY 50",
        x: rows.map((r) => ist(r.timestamp)),
        open: rows.map((r) => r.open),
        high: rows.map((r) => r.high),
        low: rows.map((r) => r.low),
        close: rows.map((r) => r.close),
        increasing: { line: { color: "#62d8b2" } },
        decreasing: { line: { color: "#f28b82" } },
      },
    ];
    if (exit != null)
      traces.push({
        type: "scatter",
        mode: "markers",
        name: "Forward endpoint",
        x: [end],
        y: [exit],
        marker: { color: "#e0be7b", size: 10 },
      });
    if(transitions.length){traces.push({type:'scatter',mode:'lines+markers',name:'KP score',x:transitions.map((r:any)=>ist(r.timestamp)),y:transitions.map((r:any)=>r.score),yaxis:'y2',text:transitions.map((r:any)=>'Moon sub: '+r.moon_sub),line:{color:'#c8af75',width:1,shape:'hv'}});}
    if(predictions.length)traces.push({type:'scatter',mode:'markers',name:'Prospective paper forecasts',x:predictions.map((r:any)=>ist(r.timestamp)),y:predictions.map((r:any)=>r.reference),text:predictions.map((r:any)=>r.model_version+' · '+r.horizon+'m · expected '+r.expected_points+' pts · interval '+r.lower_points+' to '+r.upper_points),marker:{symbol:'diamond',size:10,color:'#e0be7b'}});
    const f=showForecast?forecast.data:undefined;
    if(f?.path?.points?.length){
      const pts=f.path.points;const x=[ist(f.timestamp),...pts.map((p:any)=>ist(p.timestamp))];
      traces.push({type:'scatter',mode:'lines',name:'Path lower bound',x,y:[f.reference,...pts.map((p:any)=>p.lower)],line:{width:0},showlegend:false,hoverinfo:'skip'});
      traces.push({type:'scatter',mode:'lines',name:'90% pointwise interval',x,y:[f.reference,...pts.map((p:any)=>p.upper)],fill:'tonexty',fillcolor:'rgba(100,160,235,.16)',line:{width:0},hoverinfo:'skip'});
      traces.push({type:'scatter',mode:'lines',name:'Forecast path',x,y:[f.reference,...pts.map((p:any)=>p.predicted)],line:{color:'#77b4ff',width:2.5,dash:'dash'},customdata:[[f.reference,0,f.reference,f.reference],...pts.map((p:any)=>[p.actual,p.difference,p.lower,p.upper])],hovertemplate:'%{x}<br>Predicted %{y:.2f}<br>Actual %{customdata[0]:.2f}<br>Difference %{customdata[1]:.2f}<br>Lower %{customdata[2]:.2f} · Upper %{customdata[3]:.2f}<extra>Held-out trajectory forecast</extra>'});
    }
    if(f?.status==='available'){
      traces.push({type:'scatter',mode:'markers',name:f.path?'Predicted endpoint':'Predicted endpoint · endpoint model',x:[ist(f.endpoint_timestamp)],y:[f.predicted_endpoint],marker:{color:'#79aef0',size:13,symbol:'diamond'},error_y:{type:'data',symmetric:false,array:[f.upper_endpoint-f.predicted_endpoint],arrayminus:[f.predicted_endpoint-f.lower_endpoint],color:'#79aef0'},text:['Predicted '+f.predicted_endpoint.toFixed(2)+' · Actual '+(f.actual_endpoint??'Unavailable')+' · Absolute error '+(f.absolute_error??'Unavailable')],hovertemplate:'%{x}<br>%{text}<extra>Historical endpoint forecast</extra>'});
      if(f.actual_endpoint!=null)traces.push({type:'scatter',mode:'markers',name:'Actual endpoint',x:[ist(f.endpoint_timestamp)],y:[f.actual_endpoint],marker:{color:'#e7c384',size:10,symbol:'circle-open'}});
    }
    const begin=new Date(selected.timestamp).getTime()-30*60000;
    const finish=new Date(selected.timestamp).getTime()+horizon*60000;
    const visible=rows.filter((r:any)=>view==='day'||(new Date(r.timestamp).getTime()>=begin&&new Date(r.timestamp).getTime()<=finish));
    const values=visible.flatMap((r:any)=>[r.low,r.high]);
    if(f?.path?.points)values.push(...f.path.points.flatMap((p:any)=>[p.lower,p.upper]));
    const bottom=Math.min(...values),top=Math.max(...values),pad=(top-bottom)*.06||1;
    Plotly.newPlot(
      el,
      traces,
      {
        paper_bgcolor: "#121c28",
        plot_bgcolor: "#121c28",
        font: { color: "#b8c6d7" },
        height: transitions.length?540:430,
        margin: { l: 65, r: 25, t: 20, b: 100 },
        showlegend:true,legend:{orientation:"h",x:0,y:-.16},yaxis2:{domain:[0,.16],title:{text:"KP score"},showgrid:false},
        hovermode: "closest",
        xaxis: {
          range:view==='window'?[ist(new Date(Math.max(begin,new Date(rows[0].timestamp).getTime()))),ist(new Date(Math.min(finish,new Date(rows[rows.length-1].timestamp).getTime())))]:undefined,
          showspikes: true,
          spikemode: "across",
          rangeslider: { visible: false },
          title: { text: "Asia/Kolkata · candle close" },
        },
        yaxis: {domain:transitions.length?[.28,1]:[0,1],range:[bottom-pad,top+pad],tickformat:".2f",showspikes:true,spikemode:"across"},
        shapes,
      },
      { responsive: true, displaylogo: false },
    );
    return () => Plotly.purge(el);
  }, [data, selected, horizon,transitions,predictions,forecast.data,view,showForecast]);
  return (
    <section aria-label="Historical chart">
      <div className="sectionhead">
        <h2>{showForecast?'Actual versus predicted NIFTY':'Historical NIFTY slot movement'}</h2><label>Chart view<select aria-label="Chart view" value={view} onChange={e=>setView(e.target.value)}><option value="window">{showForecast?'Prediction Window':'Matched Slot'}</option><option value="day">Full Trading Day</option></select></label>
        <label>
          Candle interval
          <select
            value={interval}
            onChange={(e) => setInterval(+e.target.value)}
          >
            {[1, 5, 15].map((n) => (
              <option key={n} value={n}>
                {n} minute candles
              </option>
            ))}
          </select>
        </label>
      </div>
      <p>
        {ist(selected.timestamp).replace("T", " ")} IST · {horizon}-minute
        window highlighted
      </p>
      {selected["points_" + horizon] != null && (
        <p>
          Observed movement: {selected["points_" + horizon].toFixed(2)} points (
          {selected["return_" + horizon].toFixed(3)}%)
        </p>
      )}
      {isPending ? (
        <p>Loading actual session candles…</p>
      ) : error ? (
        <p className="error">{String(error)}</p>
      ) : !data?.rows.length ? (
        <p className="empty">Intraday NIFTY data unavailable for this date.</p>
      ) : (
        <div ref={node} />
      )}
{showForecast&&<details className="chart-method"><summary>Forecast method and numerical comparison</summary>      {forecast.isFetching?<p>Loading eligible historical forecast…</p>:forecast.data?.status==='available'?<div aria-label="Forecast comparison"><p>{forecast.data.forecast_type} · {forecast.data.model} · {forecast.data.version}</p><p>{forecast.data.path_note}</p><p>Predicted direction: {forecast.data.direction} · Actual direction: {forecast.data.actual_direction??'Unavailable'} · Correct: {String(forecast.data.direction_correct??'Unavailable')}</p><p>Predicted endpoint: {forecast.data.predicted_endpoint.toFixed(2)} · Actual endpoint: {forecast.data.actual_endpoint?.toFixed(2)??'Unavailable'} · Absolute error: {forecast.data.absolute_error?.toFixed(2)??'Unavailable'}</p><p>Predicted movement: {forecast.data.expected_points.toFixed(2)} points · Actual movement: {forecast.data.actual_points?.toFixed(2)??'Unavailable'} points · Interval covered: {String(forecast.data.interval_covered??'Unavailable')} · Path MAE: {forecast.data.path_error?.toFixed(2)??"Unavailable: endpoint model only"}</p></div>:<p>{forecast.data?.reason??'Prediction unavailable'}</p>}
</details>}
      <p>
        Close timestamps; reference and forward changes are descriptive index
        observations, not executable fills.
      </p>
    </section>
  );
}
