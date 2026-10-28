// Private D1 gateway and lightweight read-only cloud view of the SAME scan outputs.
const keyOK = s => typeof s === 'string' && /^[A-Za-z0-9_.:\^-]{1,100}$/.test(s);
const enc = new TextEncoder();
const repo='johnlee-rgb/vcp-swing-scanner';
function decode64(s){return Uint8Array.from(atob(s.replaceAll('-','+').replaceAll('_','/')+'='.repeat((4-s.length%4)%4)),c=>c.charCodeAt(0))}
export function trustedClaims(c,audience,now=Math.floor(Date.now()/1000)){
  return c.iss==='https://token.actions.githubusercontent.com' && c.aud===audience &&
    c.repository===repo && String(c.repository_id)==='1228032780' && String(c.repository_owner_id)==='281393029' &&
    ['refs/heads/main','refs/heads/codex/cloud-vnext'].includes(c.ref) &&
    c.workflow_ref===repo+'/.github/workflows/daily-cloud.yml@'+c.ref &&
    ['push','schedule','workflow_dispatch'].includes(c.event_name) && c.runner_environment==='github-hosted' &&
    Number.isFinite(c.exp) && c.exp>now && c.exp<=now+900 && Number.isFinite(c.nbf) && c.nbf<=now+30 &&
    Number.isFinite(c.iat) && c.iat<=now+30 && /^\d{1,30}$/.test(String(c.run_id)) && /^\d{1,10}$/.test(String(c.run_attempt));
}
export async function verifyGithubJWT(token,audience,get=fetch){
  if(typeof token!=='string'||token.length>16000)throw new Error('Invalid identity token');
  const parts=token.split('.');if(parts.length!==3)throw new Error('Invalid identity token');
  const h=JSON.parse(new TextDecoder().decode(decode64(parts[0]))),c=JSON.parse(new TextDecoder().decode(decode64(parts[1])));
  if(h.alg!=='RS256'||typeof h.kid!=='string'||!trustedClaims(c,audience))throw new Error('Identity not authorized');
  const response=await get('https://token.actions.githubusercontent.com/.well-known/jwks');
  if(!response.ok)throw new Error('Identity provider unavailable');
  const keys=(await response.json()).keys;
  const jwk=keys.find(k=>k.kid===h.kid&&k.kty==='RSA'&&k.alg==='RS256');
  if(!jwk)throw new Error('Signing key unavailable');
  const key=await crypto.subtle.importKey('jwk',jwk,{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['verify']);
  if(!await crypto.subtle.verify('RSASSA-PKCS1-v1_5',key,decode64(parts[2]),enc.encode(parts[0]+'.'+parts[1])))throw new Error('Invalid signature');
  return c;
}
async function same(a,b) {
  if (!a || !b) return false;
  const x = new Uint8Array(await crypto.subtle.digest('SHA-256', enc.encode(a)));
  const y = new Uint8Array(await crypto.subtle.digest('SHA-256', enc.encode(b)));
  return x.reduce((v,n,i) => v | (n ^ y[i]), 0) === 0;
}
async function signature(text,secret) {
  const k=await crypto.subtle.importKey('raw',enc.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);
  return Array.from(new Uint8Array(await crypto.subtle.sign('HMAC',k,enc.encode(text))),x=>x.toString(16).padStart(2,'0')).join('');
}
const headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
  'Content-Security-Policy':"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'; form-action 'self'"};
const json=(v,status=200)=>new Response(JSON.stringify(v),{status,headers:{...headers,'Content-Type':'application/json'}});
const html=(v,status=200)=>new Response(v,{status,headers:{...headers,'Content-Type':'text/html; charset=utf-8'}});
const login=`<!doctype html><html lang="zh-HK"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VCP 私人研究</title><style>body{font:16px system-ui;background:#101820;color:#f0f3f5;max-width:420px;margin:12vh auto;padding:24px}input,button{box-sizing:border-box;width:100%;padding:14px;margin:12px 0;font:inherit}button{background:#59c3a7;border:0}p{line-height:1.7}</style><h1>VCP 私人研究</h1><p>私人雲端掃描與歷史研究。登入後查看已保存結果。</p><form method="post" action="/login"><label>私人存取密碼<input type="password" name="password" required autocomplete="current-password" maxlength="256"></label><button>登入</button></form></html>`;
const dashboard=`<!doctype html><html lang="zh-HK"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VCP Cloud Research</title><style>body{font:15px system-ui;margin:0;background:#f4f6f8;color:#18242d}header{background:#132d32;color:white;padding:20px 4%}main{padding:24px 4%}nav{display:flex;gap:8px;flex-wrap:wrap}button,input{padding:10px;border:1px solid #a7b9bd;background:white;font:inherit;border-radius:4px}button.active{background:#157968;color:white}#status{padding:16px 0;line-height:1.6}.scroll{overflow:auto;max-height:65vh}table{border-collapse:collapse;background:white;white-space:nowrap;font-size:13px}th,td{padding:10px 12px;border-bottom:1px solid #ddd;text-align:left;max-width:420px;white-space:normal;min-width:80px}th{position:sticky;top:0;background:#d9e9e8}pre{white-space:pre-wrap;overflow-wrap:anywhere}footer{padding:20px 0;color:#566b73}</style><header><h1>VCP Cloud Research</h1><span>私人研究平台 · WATCH ≠ BUY · 無經紀交易連線</span></header><main><nav id="nav"></nav><p><input id="filter" placeholder="搜尋股票／機構" aria-label="搜尋"><button id="refresh">重新讀取</button><button id="csv">下載 CSV</button><a href="/logout">登出</a></p><div id="status"></div><div class="scroll"><table id="table"></table></div><details><summary>資料來源及完整診斷</summary><pre id="detail"></pre></details><footer>13F 為延遲季度申報，唔代表今日買入；內幕研究及 MET-A 未證明有盈利優勢。回測、模擬交易與實盤表現不可混為一談。</footer></main><script>
const views=[['市場與 VCP','scans'],['MET-A 研究','meta'],['機構持倉','holdings'],['內幕交易','insiders'],['回測與勝率','research'],['訊號歷史','signals']];
let active='scans',payload={},rows=[];
function draw(){const q=document.getElementById('filter').value.toLowerCase(),r=rows.filter(x=>JSON.stringify(x).toLowerCase().includes(q));const t=document.getElementById('table');t.replaceChildren();const preferred=['ticker','Final Action','Setup Stage','Trade','Legacy VCP Score','Enhanced VCP Score','Entry Trigger','Stop Loss','Risk %','manager','status','insider','code','available_at'];const all=[...new Set(r.flatMap(Object.keys))];const cols=[...preferred.filter(c=>all.includes(c)),...all.filter(c=>!preferred.includes(c))].slice(0,24);const tr=document.createElement('tr');cols.forEach(c=>{const e=document.createElement('th');e.textContent=c;tr.append(e)});t.append(tr);r.forEach(x=>{const tr=document.createElement('tr');cols.forEach(c=>{const e=document.createElement('td');e.textContent=typeof x[c]==='object'?JSON.stringify(x[c]):x[c]??'N/A';tr.append(e)});t.append(tr)})}
async function load(){document.getElementById('status').textContent='讀取已保存資料…';const r=await fetch('/api/object?namespace='+active+'&key=latest');if(r.status===401){location='/';return}if(!r.ok){document.getElementById('status').textContent='暫時未能讀取，請稍後再試。';return}payload=(await r.json()).value||{};rows=Array.isArray(payload)?payload:(payload.rows||[]);document.getElementById('status').textContent=(payload.saved_at?'更新：'+payload.saved_at+' · ':'')+(payload.status||'尚未有已保存資料；排程啟用後先會更新。');document.getElementById('detail').textContent=JSON.stringify(payload,null,2);draw()}
views.forEach(([label,ns])=>{const b=document.createElement('button');b.textContent=label;b.onclick=()=>{active=ns;document.querySelectorAll('nav button').forEach(x=>x.className='');b.className='active';load()};document.getElementById('nav').append(b)});document.getElementById('filter').oninput=draw;document.getElementById('refresh').onclick=load;
document.getElementById('csv').onclick=()=>{const cols=[...new Set(rows.flatMap(Object.keys))];const quote=x=>'"'+String(typeof x==='object'?JSON.stringify(x):x??'').replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"';const csv=[cols,...rows.map(r=>cols.map(c=>r[c]))].map(r=>r.map(quote).join(',')).join('\\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\\uFEFF'+csv],{type:'text/csv'}));a.download=active+'.csv';a.click();URL.revokeObjectURL(a.href)};load();</script></html>`;

export default {async fetch(request,env) {
  const url=new URL(request.url);
  if(!env.READ_TOKEN || !env.WRITE_TOKEN || !env.DASHBOARD_PASSWORD) return json({error:'Service not configured'},503);
  if(url.pathname==='/health') return json({status:'ok',private:true});
  if(url.pathname==='/api/oidc' && request.method==='POST'){
    try{
      if(Number(request.headers.get('Content-Length')||0)>20000)return json({error:'Too large'},413);
      const c=await verifyGithubJWT((await request.json()).token,url.origin);
      const expiry=Math.floor(Date.now()/1000)+1200;
      const content=[expiry,c.run_id,c.run_attempt].join('.');
      const token='vcpjob.'+content+'.'+await signature('job:'+content,env.WRITE_TOKEN);
      return json({token,expires_at:expiry,sec_user_agent:env.SEC_USER_AGENT||''});
    }catch{return json({error:'GitHub workflow identity denied'},401)}
  }
  if(url.pathname==='/login' && request.method==='POST') {
    if(Number(request.headers.get('Content-Length')||0)>2000) return json({error:'Too large'},413);
    const f=await request.formData();
    // Shared-IP bounded login attempts persisted in D1, never log passwords.
    const ip=request.headers.get('CF-Connecting-IP')||'unknown';
    const bucket=Math.floor(Date.now()/600000),id=await signature(ip+bucket,env.READ_TOKEN);
    const count=await env.DB.prepare('INSERT INTO login_attempts(id,n) VALUES(?,1) ON CONFLICT(id) DO UPDATE SET n=n+1 RETURNING n').bind(id).first();
    if(count.n>10) return html('登入嘗試過多，請十分鐘後再試。',429);
    if(!await same(String(f.get('password')||''),env.DASHBOARD_PASSWORD)) return html(login,401);
    const expiry=String(Math.floor(Date.now()/1000)+3600);
    const cookie=expiry+'.'+await signature(expiry,env.READ_TOKEN);
    return new Response(null,{status:303,headers:{...headers,Location:'/', 'Set-Cookie':`vcp_session=${cookie}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=3600`}});
  }
  if(url.pathname==='/logout') return new Response(null,{status:303,headers:{Location:'/', 'Set-Cookie':'vcp_session=; Max-Age=0; Secure; HttpOnly; SameSite=Strict; Path=/'}});
  const bearer=(request.headers.get('Authorization')||'').replace(/^Bearer /,'');
  const job=bearer.match(/^vcpjob\.(\d+)\.(\d+)\.(\d+)\.([a-f0-9]+)$/);
  const jobValid=!!job && Number(job[1])>Date.now()/1000 && Number(job[1])<=Date.now()/1000+1200 && await same(job[4],await signature('job:'+job.slice(1,4).join('.'),env.WRITE_TOKEN));
  const writer=jobValid||await same(bearer,env.WRITE_TOKEN);
  const reader=writer||await same(bearer,env.READ_TOKEN);
  const cookie=(request.headers.get('Cookie')||'').match(/(?:^|; )vcp_session=(\d+)\.([a-f0-9]+)/);
  const session=!!cookie && Number(cookie[1])>Date.now()/1000 && await same(cookie[2],await signature(cookie[1],env.READ_TOKEN));
  if(url.pathname==='/') return html(session?dashboard:login);
  if(!reader&&!session) return json({error:'Unauthorized'},401);
  if(url.pathname==='/api/object' && request.method==='GET') {
    const ns=url.searchParams.get('namespace'),key=url.searchParams.get('key');
    if(!keyOK(ns)||!keyOK(key)) return json({error:'Invalid key'},400);
    const r=await env.DB.prepare('SELECT payload,updated_at FROM objects WHERE namespace=? AND key=?').bind(ns,key).first();
    const value=r?JSON.parse(r.payload):null;
    if(value?.__chunks){
      if(value.__chunks.count>100) return json({error:'Chunk limit'},413);
      const rows=[];
      for(let i=0;i<value.__chunks.count;i++){
        const part=await env.DB.prepare('SELECT payload FROM objects WHERE namespace=? AND key=?').bind('chunks',value.__chunks.root+'-'+i).first();
        if(!part) return json({error:'Incomplete durable object'},503);
        rows.push(...JSON.parse(part.payload));
      }
      value.rows=rows;delete value.__chunks;
    }
    return json({value,updated_at:r?.updated_at});
  }
  if(!writer) return json({error:'Read only'},403);
  if(request.method!=='POST') return json({error:'Not found'},404);
  if(Number(request.headers.get('Content-Length')||0)>1500000) return json({error:'Too large'},413);
  let body;try{body=await request.json()}catch{return json({error:'Invalid JSON'},400)}
  if(url.pathname==='/api/lease') {
    if(!keyOK(body.id)) return json({error:'Invalid lease'},400);
    const now=Math.floor(Date.now()/1000);
    if(body.release){await env.DB.prepare('DELETE FROM lease WHERE name=? AND owner=?').bind('job',body.id).run();return json({released:true})}
    const r=await env.DB.prepare('INSERT INTO lease(name,owner,expires) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET owner=excluded.owner,expires=excluded.expires WHERE lease.expires<? OR lease.owner=? RETURNING owner').bind('job',body.id,now+1200,now,body.id).first();
    return json({acquired:r?.owner===body.id},r?200:409);
  }
  if(url.pathname==='/api/object') {
    if(!keyOK(body.namespace)||!keyOK(body.key)||JSON.stringify(body.value).length>1400000) return json({error:'Invalid object'},400);
    // INSERT SELECT enforces current lease atomically with each write.
    const r=await env.DB.prepare('INSERT INTO objects(namespace,key,payload,updated_at) SELECT ?,?,?,? WHERE EXISTS(SELECT 1 FROM lease WHERE name=? AND owner=? AND expires>?) ON CONFLICT(namespace,key) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at RETURNING key').bind(body.namespace,body.key,JSON.stringify(body.value),new Date().toISOString(),'job',body.lease_id,Math.floor(Date.now()/1000)).first();
    return json({saved:!!r},r?200:409);
  }
  return json({error:'Not found'},404);
}};
