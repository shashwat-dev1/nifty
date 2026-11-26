import React,{useEffect,useState} from 'react';
import {ArrowRight,ChartNoAxesCombined,Eye,EyeOff,LockKeyhole,LoaderCircle} from 'lucide-react';
import './cloud-entry.css';
export function CloudWake({children}:any){
 const cloud=import.meta.env.VITE_CLOUD==='1';
 const [showPassword,setShowPassword]=useState(false),[submitting,setSubmitting]=useState(false);
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
 return <main className="cloud-entry"><div className="cloud-entry-layout">
  <div className="cloud-entry-brand"><span className="cloud-entry-mark"><ChartNoAxesCombined size={22} strokeWidth={1.8}/></span><span>NIFTY <span className="cloud-entry-brand-divider">/</span> KP Research</span></div>
  <div className="cloud-entry-card">
   <div className="cloud-entry-tag"><LockKeyhole size={13}/> Private workspace</div>
   {state==='login'?<>
    <h1>Welcome back</h1><p className="cloud-entry-description">Sign in to explore KP configurations and historical NIFTY movements.</p>
    <form aria-label="Workspace sign in" onSubmit={async e=>{
     e.preventDefault();if(submitting)return;setSubmitting(true);setMessage('');
     try{const r=await fetch('/api/cloud/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password})});
      if(r.ok){setPassword('');setState('checking');setAttempt(v=>v+1)}else setMessage('That password didn’t work. Please try again.');
     }catch{setMessage('Couldn’t sign in. Check your connection and try again.')}finally{setSubmitting(false)}
    }}>
     <label className="cloud-entry-label" htmlFor="workspace-password">Access password</label>
     <div className="cloud-entry-password"><input id="workspace-password" type={showPassword?'text':'password'} required maxLength={128} value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password" placeholder="Enter your access password" aria-invalid={!!message} aria-describedby={message?'cloud-entry-error':undefined}/><button type="button" className="cloud-entry-reveal" aria-label={showPassword?'Hide password':'Show password'} aria-pressed={showPassword} onClick={()=>setShowPassword(v=>!v)}>{showPassword?<EyeOff size={18}/>:<Eye size={18}/>}</button></div>
     {message&&<p id="cloud-entry-error" className="cloud-entry-error" role="alert">{message}</p>}
     <button type="submit" className="cloud-entry-submit" disabled={submitting} aria-busy={submitting}>{submitting?<><LoaderCircle size={17} className="cloud-entry-spin"/>Signing in…</>:<>Open research dashboard<ArrowRight size={17}/></>}</button>
    </form>
    <p className="cloud-entry-help">Use the password shared with you by the workspace owner.</p>
   </>:state==='failed'?<>
    <h1>Unable to connect</h1><p className="cloud-entry-description">The research server is taking longer than expected. Please try connecting again.</p>
    <button className="cloud-entry-submit" onClick={()=>{setState('checking');setAttempt(v=>v+1)}}>Retry connection<ArrowRight size={17}/></button>
   </>:<>
    <h1>{state==='waking'?'Your workspace is starting':'Connecting to your workspace'}</h1><p className="cloud-entry-description">The research server may need a moment to wake up and load historical data. You can leave this tab open.</p>
    <div className="cloud-entry-status" role="status"><LoaderCircle size={20} className="cloud-entry-spin"/><span>{state==='waking'?'Starting research server…':'Checking connection…'}</span></div>
    <p className="cloud-entry-help">This can take a few minutes on the first visit.</p>
   </>}
  </div>
  <p className="cloud-entry-footer">Private access <span aria-hidden="true">·</span> Research use only</p>
 </div></main>
}
