import {createHmac,timingSafeEqual,scryptSync,randomBytes} from 'node:crypto';
export const config={maxDuration:30};
const getPaths=new Set(['health','coverage','upstox','market','candles','timeline','daily-research','kp/slot-matches','trajectory-metrics','historical-forecast']);
const postPaths=new Set(['calculate','matches','statistics','feedback']);
function equal(a,b){const x=Buffer.from(a),y=Buffer.from(b);return x.length===y.length&&timingSafeEqual(x,y)}
export function validSession(token,key,now=Date.now()){
 if(!token||!key)return false;
 const [expires,nonce,signature]=token.split('.');
 if(!/^\d+$/.test(expires)||!nonce||!signature||Number(expires)<=now)return false;
 return equal(signature,createHmac('sha256',key).update(expires+'.'+nonce).digest('hex'));
}
export default async function handler(req,res){
 res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');
 const {BACKEND_ORIGIN,BACKEND_API_KEY,DEMO_PASSWORD_VERIFIER,SESSION_SECRET}=process.env;
 if(!BACKEND_ORIGIN||!BACKEND_API_KEY||!DEMO_PASSWORD_VERIFIER||!SESSION_SECRET||SESSION_SECRET.length<32)return res.status(503).json({error:'Cloud connection is not configured'});
 let origin;try{origin=new URL(BACKEND_ORIGIN);if(origin.protocol!=='https:'||origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash)throw Error();}catch{return res.status(503).json({error:'Invalid backend configuration'})}
 const u=new URL(req.url,'https://local.invalid');const route=String(req.query?.route??u.pathname.replace(/^\/api\//,''));
 if(route==='cloud/login'){
  if(req.method!=='POST')return res.status(405).end();
  if(req.headers.origin!==`https://${req.headers.host}`)return res.status(403).end();
  const password=typeof req.body?.password==='string'?req.body.password:'';
  if(!password||password.length>128)return res.status(401).json({error:'Incorrect password'});
  const [salt,hash]=DEMO_PASSWORD_VERIFIER.split(':');
  if(!salt||!hash||!equal(scryptSync(password,salt,32).toString('hex'),hash))return res.status(401).json({error:'Incorrect password'});
  const payload=String(Date.now()+24*3600000)+'.'+randomBytes(24).toString('hex');
  const token=payload+'.'+createHmac('sha256',SESSION_SECRET).update(payload).digest('hex');
  res.setHeader('Set-Cookie',`__Host-research=${token}; Secure; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400`);
  return res.json({authenticated:true});
 }
 const cookie=req.headers.cookie?.split(';').map(x=>x.trim()).find(x=>x.startsWith('__Host-research='))?.slice('__Host-research='.length);
 if(!validSession(cookie,SESSION_SECRET))return res.status(401).json({error:'Sign in required'});
 if(!((req.method==='GET'&&getPaths.has(route))||(req.method==='POST'&&postPaths.has(route))))return res.status(403).json({error:'Route unavailable'});
 if(req.method==='POST'&&req.headers.origin!==`https://${req.headers.host}`)return res.status(403).end();
 u.searchParams.delete('route');const upstream=new URL('/api/'+route,origin);upstream.search=u.search;
 const began=performance.now();
 try{
  const result=await fetch(upstream,{method:req.method,headers:{Authorization:'Bearer '+BACKEND_API_KEY,'Content-Type':'application/json',Origin:origin.origin},body:req.method==='POST'?JSON.stringify(req.body):undefined,signal:AbortSignal.timeout(22000),redirect:'error'});
  if(!result.headers.get('content-type')?.includes('application/json'))return res.status(503).json({error:'Research server is starting'});
  const text=await result.text();res.setHeader('Server-Timing',`upstream;dur=${(performance.now()-began).toFixed(1)}`+(result.headers.get('server-timing')?`, ${result.headers.get('server-timing')}`:''));res.setHeader('Content-Type','application/json');return res.status(result.status).send(text);
 }catch{return res.status(503).json({error:'Research server is starting or unavailable'});}
}
