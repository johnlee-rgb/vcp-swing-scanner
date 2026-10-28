import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import worker,{trustedClaims,verifyGithubJWT} from '../cloud/worker.mjs';

function environment(){
  const db=new DatabaseSync(':memory:');db.exec(readFileSync(new URL('../cloud/schema.sql',import.meta.url),'utf8'));
  return {READ_TOKEN:'test-read-token',WRITE_TOKEN:'test-write-token',DASHBOARD_PASSWORD:'test-private-password-0001',DB:{prepare(sql){return{bind(...params){return{async first(){return db.prepare(sql).get(...params)},async run(){return db.prepare(sql).run(...params)}}}}}}};
}
function req(path,token,body){return new Request('https://vcp.test'+path,{method:body?'POST':'GET',headers:{...(token?{Authorization:'Bearer '+token}:{}),...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined})}

test('anonymous data denied and login is private',async()=>{
  const env=environment();assert.equal((await worker.fetch(req('/api/object?namespace=scans&key=latest'),env)).status,401);
  const page=await worker.fetch(req('/'),env);const html=await page.text();assert.equal(page.status,200);assert.ok(html.includes('type="password"'));assert.ok(!html.includes(env.READ_TOKEN));
});
test('reader cannot write and writer needs active lease',async()=>{
  const env=environment();const body={namespace:'scans',key:'latest',value:{rows:[]},lease_id:'a'};
  assert.equal((await worker.fetch(req('/api/object',env.READ_TOKEN,body),env)).status,403);
  assert.equal((await worker.fetch(req('/api/object',env.WRITE_TOKEN,body),env)).status,409);
});
test('lease is exclusive; data persists across separate requests',async()=>{
  const env=environment();assert.equal((await worker.fetch(req('/api/lease',env.WRITE_TOKEN,{id:'owner'}),env)).status,200);
  assert.equal((await worker.fetch(req('/api/lease',env.WRITE_TOKEN,{id:'other'}),env)).status,409);
  const body={namespace:'prices',key:'^SOX',value:{rows:[{close:100}]},lease_id:'owner'};
  assert.equal((await worker.fetch(req('/api/object',env.WRITE_TOKEN,body),env)).status,200);
  const r=await worker.fetch(req('/api/object?namespace=prices&key=%5ESOX',env.READ_TOKEN),env);
  assert.equal((await r.json()).value.rows[0].close,100);
});
test('invalid object keys do not become SQL',async()=>{
  const env=environment();const r=await worker.fetch(req('/api/object?namespace=x%27%3BDROP&key=latest',env.READ_TOKEN),env);assert.equal(r.status,400);
});
test('password login sets secure session and never returns API keys',async()=>{
  const env=environment();const f=new FormData();f.set('password',env.DASHBOARD_PASSWORD);
  const r=await worker.fetch(new Request('https://vcp.test/login',{method:'POST',body:f}),env);
  assert.equal(r.status,303);const cookie=r.headers.get('Set-Cookie');assert.ok(cookie.includes('HttpOnly'));assert.ok(cookie.includes('Secure'));assert.ok(cookie.includes('SameSite=Strict'));
  const page=await worker.fetch(new Request('https://vcp.test/',{headers:{Cookie:cookie}}),env);const text=await page.text();assert.ok(text.includes('VCP Cloud Research'));assert.ok(!text.includes(env.WRITE_TOKEN));
});
test('chunked reads require all chunks; partial data never looks successful',async()=>{
  const env=environment();await worker.fetch(req('/api/lease',env.WRITE_TOKEN,{id:'a'}),env);
  await worker.fetch(req('/api/object',env.WRITE_TOKEN,{namespace:'scans',key:'latest',lease_id:'a',value:{rows:[],__chunks:{root:'g',count:1}}}),env);
  assert.equal((await worker.fetch(req('/api/object?namespace=scans&key=latest',env.READ_TOKEN),env)).status,503);
  await worker.fetch(req('/api/object',env.WRITE_TOKEN,{namespace:'chunks',key:'g-0',lease_id:'a',value:[{ticker:'EOG'}]}),env);
  const r=await worker.fetch(req('/api/object?namespace=scans&key=latest',env.READ_TOKEN),env);assert.equal((await r.json()).value.rows[0].ticker,'EOG');
});
function claims(){const now=Math.floor(Date.now()/1000);return{iss:'https://token.actions.githubusercontent.com',aud:'https://vcp.test',repository:'johnlee-rgb/vcp-swing-scanner',repository_id:'1228032780',repository_owner_id:'281393029',ref:'refs/heads/codex/cloud-vnext',workflow_ref:'johnlee-rgb/vcp-swing-scanner/.github/workflows/daily-cloud.yml@refs/heads/codex/cloud-vnext',event_name:'push',runner_environment:'github-hosted',exp:now+300,nbf:now-1,iat:now,run_id:'123',run_attempt:'1'}}
test('OIDC scope rejects fork, wrong workflow, owner, audience and expired token',()=>{
  const c=claims();assert.ok(trustedClaims(c,'https://vcp.test'));
  for(const mutation of [{repository_id:'wrong'},{repository_owner_id:'other'},{ref:'refs/pull/1/merge'},{event_name:'pull_request'},{workflow_ref:'other'},{aud:'elsewhere'},{exp:1}])assert.ok(!trustedClaims({...c,...mutation},'https://vcp.test'));
});
test('OIDC verifies actual RSA signature; forged payload is denied',async()=>{
  const pair=await crypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const jwk=await crypto.subtle.exportKey('jwk',pair.publicKey);jwk.kid='test';jwk.alg='RS256';
  const b64=o=>Buffer.from(JSON.stringify(o)).toString('base64url');
  const h=b64({alg:'RS256',kid:'test'}),p=b64(claims());
  const sig=Buffer.from(await crypto.subtle.sign('RSASSA-PKCS1-v1_5',pair.privateKey,new TextEncoder().encode(h+'.'+p))).toString('base64url');
  const get=async()=>new Response(JSON.stringify({keys:[jwk]}));
  assert.equal((await verifyGithubJWT(h+'.'+p+'.'+sig,'https://vcp.test',get)).run_id,'123');
  const altered=b64({...claims(),run_id:'999'});
  await assert.rejects(verifyGithubJWT(h+'.'+altered+'.'+sig,'https://vcp.test',get));
});
