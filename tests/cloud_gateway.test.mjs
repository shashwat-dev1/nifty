import test from 'node:test';
import assert from 'node:assert/strict';
import {createHmac,scryptSync} from 'node:crypto';
import handler,{validSession} from '../web/api/gateway.mjs';
function response(){return {statusCode:200,headers:{},body:null,setHeader(k,v){this.headers[k]=v},status(v){this.statusCode=v;return this},json(v){this.body=v;return this},send(v){this.body=v;return this},end(){return this}}}
test('signed sessions expire and reject tampering',()=>{const key='x'.repeat(40),body='2000.nonce',sig=createHmac('sha256',key).update(body).digest('hex');assert(validSession(body+'.'+sig,key,1000));assert(!validSession(body+'.'+sig,key,2000));assert(!validSession(body+'.'+sig+'0',key,1000));});
test('login protects API, cookie expires, admin never forwards',async()=>{
 Object.assign(process.env,{BACKEND_ORIGIN:'https://example.onrender.com',BACKEND_API_KEY:'k'.repeat(40),DEMO_PASSWORD_VERIFIER:'salt:'+scryptSync('fixture-password','salt',32).toString('hex'),SESSION_SECRET:'s'.repeat(40)});
 let r=response();await handler({url:'/api/health',method:'GET',headers:{}},r);assert.equal(r.statusCode,401);
 r=response();await handler({url:'/api/cloud/login',method:'POST',headers:{host:'example.vercel.app',origin:'https://example.vercel.app'},body:{password:'wrong'}},r);assert.equal(r.statusCode,401);
 r=response();await handler({url:'/api/cloud/login',method:'POST',headers:{host:'example.vercel.app',origin:'https://example.vercel.app'},body:{password:'fixture-password'}},r);assert.equal(r.statusCode,200);assert(r.headers['Set-Cookie'].includes('Secure; HttpOnly; SameSite=Strict'));
 const cookie=r.headers['Set-Cookie'].split(';')[0];r=response();await handler({url:'/api/admin/jobs',method:'GET',headers:{cookie}},r);assert.equal(r.statusCode,403);
});
