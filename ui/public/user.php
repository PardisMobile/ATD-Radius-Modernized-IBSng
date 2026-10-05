<?php
$username = isset($_GET['username']) ? trim($_GET['username']) : '';
if ($username === '') {
    http_response_code(400);
    echo 'username is required';
    exit;
}
?><!doctype html>
<html lang="en" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>User · ATD Radius</title>
<style>
:root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#172033;background:#f5f7fb;--surface:#fff;--line:#e6eaf1;--muted:#697386;--accent:#315efb;--danger:#c53b45;--ok:#16855b;--shadow:0 12px 36px rgba(22,31,55,.08)}
@media(prefers-color-scheme:dark){:root{color:#edf1f8;background:#0f131a;--surface:#171c25;--line:#293241;--muted:#a6b0c1;--accent:#6f8cff;--danger:#f0717a;--ok:#55c69a;--shadow:0 16px 40px rgba(0,0,0,.25)}}
*{box-sizing:border-box}body{margin:0}.shell{max-width:1440px;margin:auto;padding:24px}.top{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:22px}.crumb{color:var(--muted);font-size:13px}.title{display:flex;align-items:center;gap:12px}.avatar{width:44px;height:44px;border-radius:14px;background:var(--accent);color:#fff;display:grid;place-items:center;font-weight:800}.title h1{margin:0;font-size:26px}.sub{color:var(--muted);font-size:13px;margin-top:3px}.pill{display:inline-flex;padding:5px 9px;border-radius:999px;font-size:12px;font-weight:700;background:rgba(22,133,91,.12);color:var(--ok)}.toolbar{display:flex;gap:8px;flex-wrap:wrap}.btn{border:1px solid var(--line);background:var(--surface);color:inherit;padding:9px 13px;border-radius:10px;font-weight:700;cursor:pointer}.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}.grid{display:grid;grid-template-columns:1.35fr 1fr;gap:16px}.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);padding:18px}.wide{grid-column:1/-1}.card h2{font-size:15px;margin:0 0 14px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.stat{border:1px solid var(--line);border-radius:12px;padding:13px}.stat b{font-size:20px}.stat span{display:block;color:var(--muted);font-size:12px;margin-top:4px}.list{display:grid;gap:8px}.row{display:flex;justify-content:space-between;gap:12px;padding:11px 0;border-bottom:1px solid var(--line)}.row:last-child{border-bottom:0}.label{color:var(--muted);font-size:12px}.value{font-weight:650;text-align:right}.empty{color:var(--muted);font-size:13px;padding:8px 0}.attr{display:grid;grid-template-columns:1.2fr 1.4fr .5fr .5fr;gap:8px;padding:9px 0;border-bottom:1px solid var(--line);font-size:13px}.table{width:100%;border-collapse:collapse;font-size:13px}.table th,.table td{text-align:left;padding:10px;border-bottom:1px solid var(--line)}.table th{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em}.error{padding:14px;border-radius:12px;background:rgba(197,59,69,.12);color:var(--danger)}
@media(max-width:850px){.shell{padding:14px}.grid{grid-template-columns:1fr}.wide{grid-column:auto}.stats{grid-template-columns:repeat(2,1fr)}.top{align-items:flex-start;flex-direction:column}.toolbar{width:100%}.btn{flex:1}.attr{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
<div class="shell" id="app"><div class="empty">Loading user workspace…</div></div>
<script>
const username = <?php echo json_encode($username, JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES); ?>;
const app=document.getElementById('app');
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const bytes=n=>{n=Number(n||0);if(n<1024)return n+' B';let u=['KB','MB','GB','TB'],i=-1;do{n/=1024;i++}while(n>=1024&&i<u.length-1);return n.toFixed(n>=100?0:1)+' '+u[i]};
const empty=(text='No records')=>`<div class="empty">${esc(text)}</div>`;
async function load(){
 try{
  const r=await fetch('/api/v1/users/'+encodeURIComponent(username)+'/detail',{headers:{Accept:'application/json'}});
  if(!r.ok) throw new Error(r.status===404?'User not found':'Unable to load user');
  const u=await r.json();
  const initial=esc(u.username.slice(0,1).toUpperCase());
  app.innerHTML=`
  <header class="top"><div><div class="crumb">Dashboard / Users / ${esc(u.username)}</div><div class="title"><div class="avatar">${initial}</div><div><h1>${esc(u.username)} <span class="pill">${esc(u.status)}</span></h1><div class="sub">IBSng-compatible user workspace · ${esc(u.id)}</div></div></div></div><div class="toolbar"><button class="btn" onclick="location.href='users.php'">Back to users</button><button class="btn primary" onclick="alert('Edit workspace is the next action surface')">Edit user</button></div></header>
  <main class="grid">
   <section class="card wide"><h2>Overview</h2><div class="stats"><div class="stat"><b>${u.groups.length}</b><span>Groups</span></div><div class="stat"><b>${u.services.length}</b><span>Services</span></div><div class="stat"><b>${u.active_sessions.length}</b><span>Online sessions</span></div><div class="stat"><b>${u.has_password?'Ready':'Missing'}</b><span>Authentication</span></div></div></section>
   <section class="card"><h2>Identity & authentication</h2><div class="list"><div class="row"><span class="label">Username</span><span class="value">${esc(u.username)}</span></div><div class="row"><span class="label">Status</span><span class="value">${esc(u.status)}</span></div><div class="row"><span class="label">Credential</span><span class="value">${u.credential_enabled?'Enabled':'Disabled'}</span></div><div class="row"><span class="label">Password</span><span class="value">${u.has_password?'Configured':'Not configured'}</span></div></div></section>
   <section class="card"><h2>Groups</h2>${u.groups.length?u.groups.map(g=>`<div class="row"><span><b>${esc(g.name)}</b><div class="label">${esc(g.description||'')}</div></span><span class="pill">${g.enabled?'Enabled':'Disabled'}</span></div>`).join(''):empty('No groups assigned')}</section>
   <section class="card wide"><h2>Services</h2>${u.services.length?u.services.map(s=>`<div class="row"><span><b>${esc(s.name)}</b><div class="label">${esc(s.description||'')}</div></span><span>${s.assignment_enabled?'Assigned':'Disabled'}</span></div>`).join(''):empty('No services assigned')}</section>
   <section class="card wide"><h2>Effective policy / attributes</h2>${u.attributes.length?`<div class="attr"><b>Name</b><b>Value</b><b>Scope</b><b>Priority</b></div>`+u.attributes.map(a=>`<div class="attr"><span>${esc(a.name)}</span><span>${esc(a.value)}</span><span>${esc(a.scope_type)}</span><span>${esc(a.precedence)}</span></div>`).join(''):empty('No inherited or user-specific attributes')}</section>
   <section class="card wide"><h2>Active sessions</h2>${u.active_sessions.length?`<table class="table"><thead><tr><th>Session</th><th>RAS</th><th>IP</th><th>Started</th><th>Traffic</th></tr></thead><tbody>${u.active_sessions.map(s=>`<tr><td>${esc(s.session_key)}</td><td>${esc(s.ras_name||'—')}</td><td>${esc(s.framed_ip||'—')}</td><td>${esc(s.started_at||'—')}</td><td>${bytes(s.input_octets)} ↓ / ${bytes(s.output_octets)} ↑</td></tr>`).join('')}</tbody></table>`:empty('No active sessions')}</section>
   <section class="card wide"><h2>Credit activity</h2>${u.credit_ledger.length?`<table class="table"><thead><tr><th>Time</th><th>Kind</th><th>Amount</th><th>Reference</th></tr></thead><tbody>${u.credit_ledger.map(c=>`<tr><td>${esc(c.created_at)}</td><td>${esc(c.kind)}</td><td>${esc(c.amount)} ${esc(c.currency)}</td><td>${esc(c.reference||'—')}</td></tr>`).join('')}</tbody></table>`:empty('No credit ledger entries')}</section>
  </main>`;
 }catch(e){app.innerHTML=`<div class="error">${esc(e.message)}</div>`}
}
load();
</script>
</body></html>
