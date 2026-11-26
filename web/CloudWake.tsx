import React,{useEffect,useState} from 'react';
export function CloudWake({children}:any){
 const cloud=import.meta.env.VITE_CLOUD==='1';
 const [state,setState]=useState(cloud?'checking':'ready'),[attempt,setAttempt]=useState(0),[password,setPassword]=useState(''),[message,setMessage]=useState('');
 useEffect(()=>{
  if(!cloud)return;
  let stopped=false;const controller=new AbortController();
  (async()=>{
   const deadline=Date.now()+300000;
   while(!stopped&&Date.now()<deadline){
    try{
     const r=await fetch('/api/health',{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(25000)]),cache:'no-store'});
     if(stopped)return;
     if(r.status===401){setState('login');return;}
     if(r.ok){const data=await r.json();if(data.status==='ok'){setState('ready');return;}}
    }catch{if(stopped)return;}
    if(!stopped)setState('waking');
    await new Promise<void>(resolve=>{const timer=setTimeout(resolve,5000);controller.signal.addEventListener('abort',()=>{clearTimeout(timer);resolve()},{once:true})});
   }
   if(!stopped)setState('failed');
  })();
  return()=>{stopped=true;controller.abort()};
 },[cloud,attempt]);
 if(state==='ready')return children;
 return <main style={{maxWidth:500,margin:'15vh auto',padding:24,fontFamily:'system-ui'}}><h1>NIFTY KP Research</h1>{state==='login'?<form onSubmit={async e=>{e.preventDefault();setMessage('');try{const r=await fetch('/api/cloud/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password})});setPassword('');if(r.ok){setState('checking');setAttempt(v=>v+1)}else setMessage('Sign-in failed. Check the access password.')}catch{setMessage('Sign-in unavailable. Please retry.')}}}><label>Access password<input type="password" required maxLength={128} value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password"/></label><button>Open research dashboard</button><p role="alert">{message}</p></form>:state==='failed'?<><p>The research server did not become ready. No market data has been substituted.</p><button onClick={()=>{setState('checking');setAttempt(v=>v+1)}}>Retry connection</button></>:<><p role="status">Starting research server…</p><p>Render may be asleep. Please wait while it starts and restores the historical data. This can take several minutes.</p></>}</main>
}
