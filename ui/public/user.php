<?php
declare(strict_types=1);

$username = isset($_GET['username']) ? trim($_GET['username']) : '';
$locale = ($_GET['lang'] ?? 'fa') === 'en' ? 'en' : 'fa';
$dir = $locale === 'fa' ? 'rtl' : 'ltr';
if ($username === '') {
    http_response_code(400);
    echo $locale === 'fa' ? 'نام کاربری الزامی است' : 'username is required';
    exit;
}
$labels = $locale === 'fa'
    ? [
        'home'=>'خانه','user'=>'کاربر','group'=>'گروه','report'=>'گزارش','graph'=>'نمودار','admin'=>'مدیر','setting'=>'تنظیمات',
        'user_info'=>'اطلاعات کاربر','search_user'=>'جستجوی کاربر','add_user'=>'افزودن کاربر جدید',
        'username'=>'نام کاربری','password'=>'رمز عبور','status'=>'وضعیت','group_list'=>'لیست گروه','charge'=>'شارژ',
        'ras'=>'RAS','ippool'=>'IPPool','online_users'=>'کاربران آنلاین','connection_logs'=>'لاگ اتصال',
        'connection_usages'=>'مصرف اتصالات','credit_changes'=>'تغییرات اعتبار','user_audit_logs'=>'لاگ حسابرسی کاربر',
        'attributes'=>'ویژگی‌ها','kill_user'=>'قطع کاربر','edit'=>'ویرایش','back'=>'بازگشت','none'=>'موردی وجود ندارد',
        'enabled'=>'فعال','disabled'=>'غیرفعال','configured'=>'تنظیم شده','not_configured'=>'تنظیم نشده',
        'loading'=>'در حال بارگذاری...','not_found'=>'کاربر پیدا نشد','load_error'=>'دریافت اطلاعات کاربر ناموفق بود',
        'name'=>'نام','value'=>'مقدار','scope'=>'محدوده','priority'=>'اولویت','session'=>'نشست','ip'=>'IP',
        'started'=>'شروع','traffic'=>'ترافیک','time'=>'زمان','kind'=>'نوع','amount'=>'مقدار','reference'=>'مرجع'
      ]
    : [
        'home'=>'HOME','user'=>'USER','group'=>'GROUP','report'=>'REPORT','graph'=>'GRAPH','admin'=>'ADMIN','setting'=>'SETTING',
        'user_info'=>'User Information','search_user'=>'Search User','add_user'=>'Add New User',
        'username'=>'Username','password'=>'Password','status'=>'Status','group_list'=>'Group List','charge'=>'Charge',
        'ras'=>'RAS','ippool'=>'IPPool','online_users'=>'Online Users','connection_logs'=>'Connection Logs',
        'connection_usages'=>'Connection Usages','credit_changes'=>'Credit Changes','user_audit_logs'=>'User Audit Logs',
        'attributes'=>'Attributes','kill_user'=>'Kill User','edit'=>'Edit','back'=>'Back','none'=>'No records',
        'enabled'=>'Enabled','disabled'=>'Disabled','configured'=>'Configured','not_configured'=>'Not configured',
        'loading'=>'Loading...','not_found'=>'User not found','load_error'=>'Unable to load user',
        'name'=>'Name','value'=>'Value','scope'=>'Scope','priority'=>'Priority','session'=>'Session','ip'=>'IP',
        'started'=>'Started','traffic'=>'Traffic','time'=>'Time','kind'=>'Kind','amount'=>'Amount','reference'=>'Reference'
      ];
?><!doctype html>
<html lang="<?= htmlspecialchars($locale, ENT_QUOTES) ?>" dir="<?= $dir ?>">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title><?= htmlspecialchars($labels['user_info']) ?> · ATD Radius</title>
<style>
:root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#172033;background:#f5f7fb;--surface:#fff;--line:#e6eaf1;--muted:#697386;--accent:#315efb;--danger:#c53b45;--ok:#16855b;--shadow:0 12px 36px rgba(22,31,55,.08)}
@media(prefers-color-scheme:dark){:root{color:#edf1f8;background:#0f131a;--surface:#171c25;--line:#293241;--muted:#a6b0c1;--accent:#6f8cff;--danger:#f0717a;--ok:#55c69a;--shadow:0 16px 40px rgba(0,0,0,.25)}}
*{box-sizing:border-box}body{margin:0}.shell{max-width:1440px;margin:auto;padding:24px}.top{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:22px}.crumb{color:var(--muted);font-size:13px}.title{display:flex;align-items:center;gap:12px}.avatar{width:44px;height:44px;border-radius:14px;background:var(--accent);color:#fff;display:grid;place-items:center;font-weight:800}.title h1{margin:0;font-size:26px}.sub{color:var(--muted);font-size:13px;margin-top:3px}.pill{display:inline-flex;padding:5px 9px;border-radius:999px;font-size:12px;font-weight:700;background:rgba(22,133,91,.12);color:var(--ok)}.toolbar{display:flex;gap:8px;flex-wrap:wrap}.btn{border:1px solid var(--line);background:var(--surface);color:inherit;padding:9px 13px;border-radius:10px;font-weight:700;cursor:pointer}.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}.grid{display:grid;grid-template-columns:1.35fr 1fr;gap:16px}.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);padding:18px}.wide{grid-column:1/-1}.card h2{font-size:15px;margin:0 0 14px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.stat{border:1px solid var(--line);border-radius:12px;padding:13px}.stat b{font-size:20px}.stat span{display:block;color:var(--muted);font-size:12px;margin-top:4px}.list{display:grid;gap:8px}.row{display:flex;justify-content:space-between;gap:12px;padding:11px 0;border-bottom:1px solid var(--line)}.row:last-child{border-bottom:0}.label{color:var(--muted);font-size:12px}.value{font-weight:650;text-align:right}.empty{color:var(--muted);font-size:13px;padding:8px 0}.attr{display:grid;grid-template-columns:1.2fr 1.4fr .5fr .5fr;gap:8px;padding:9px 0;border-bottom:1px solid var(--line);font-size:13px}.table{width:100%;border-collapse:collapse;font-size:13px}.table th,.table td{text-align:start;padding:10px;border-bottom:1px solid var(--line)}.table th{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em}.error{padding:14px;border-radius:12px;background:rgba(197,59,69,.12);color:var(--danger)}
@media(max-width:850px){.shell{padding:14px}.grid{grid-template-columns:1fr}.wide{grid-column:auto}.stats{grid-template-columns:repeat(2,1fr)}.top{align-items:flex-start;flex-direction:column}.toolbar{width:100%}.btn{flex:1}.attr{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
<div class="shell" id="app"><div class="empty"><?= htmlspecialchars($labels['loading']) ?></div></div>
<script>
const username=<?= json_encode($username,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES) ?>;
const labels=<?= json_encode($labels,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES) ?>;
const app=document.getElementById('app');
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const bytes=n=>{n=Number(n||0);if(n<1024)return n+' B';let u=['KB','MB','GB','TB'],i=-1;do{n/=1024;i++}while(n>=1024&&i<u.length-1);return n.toFixed(n>=100?0:1)+' '+u[i]};
const empty=text=>'<div class="empty">'+esc(text||labels.none)+'</div>';
async function load(){
 try{
  const r=await fetch('/api/v1/users/'+encodeURIComponent(username)+'/detail',{headers:{Accept:'application/json'}});
  if(!r.ok)throw new Error(r.status===404?labels.not_found:labels.load_error);
  const u=await r.json();
  const initial=esc((u.username||username).slice(0,1).toUpperCase());
  app.innerHTML=`
  <header class="top"><div><div class="crumb">${esc(labels.user_info)} / ${esc(u.username)}</div><div class="title"><div class="avatar">${initial}</div><div><h1>${esc(u.username)} <span class="pill">${esc(u.status)}</span></h1><div class="sub">${esc(labels.user_info)} · ${esc(u.id)}</div></div></div></div><div class="toolbar"><button class="btn" onclick="location.href='users.php?lang=<?= $locale ?>'">${esc(labels.back)}</button><button class="btn primary" onclick="alert('Edit User Information')">${esc(labels.edit)}</button></div></header>
  <main class="grid">
   <section class="card wide"><h2>${esc(labels.user_info)}</h2><div class="stats"><div class="stat"><b>${u.groups.length}</b><span>${esc(labels.group_list)}</span></div><div class="stat"><b>${u.active_sessions.length}</b><span>${esc(labels.online_users)}</span></div><div class="stat"><b>${u.has_password?esc(labels.configured):esc(labels.not_configured)}</b><span>${esc(labels.password)}</span></div><div class="stat"><b>${u.credential_enabled?esc(labels.enabled):esc(labels.disabled)}</b><span>${esc(labels.status)}</span></div></div></section>
   <section class="card"><h2>${esc(labels.user_info)}</h2><div class="list"><div class="row"><span class="label">${esc(labels.username)}</span><span class="value">${esc(u.username)}</span></div><div class="row"><span class="label">${esc(labels.status)}</span><span class="value">${esc(u.status)}</span></div><div class="row"><span class="label">${esc(labels.password)}</span><span class="value">${u.has_password?esc(labels.configured):esc(labels.not_configured)}</span></div></div></section>
   <section class="card"><h2>${esc(labels.group_list)}</h2>${u.groups.length?u.groups.map(g=>`<div class="row"><span><b>${esc(g.name)}</b><div class="label">${esc(g.description||'')}</div></span><span class="pill">${g.enabled?esc(labels.enabled):esc(labels.disabled)}</span></div>`).join(''):empty(labels.none)}</section>
   <section class="card wide"><h2>${esc(labels.attributes)}</h2>${u.attributes.length?`<div class="attr"><b>${esc(labels.name)}</b><b>${esc(labels.value)}</b><b>${esc(labels.scope)}</b><b>${esc(labels.priority)}</b></div>`+u.attributes.map(a=>`<div class="attr"><span>${esc(a.name)}</span><span>${esc(a.value)}</span><span>${esc(a.scope_type)}</span><span>${esc(a.precedence)}</span></div>`).join(''):empty(labels.none)}</section>
   <section class="card wide"><h2>${esc(labels.online_users)}</h2>${u.active_sessions.length?`<table class="table"><thead><tr><th>${esc(labels.session)}</th><th>${esc(labels.ras)}</th><th>${esc(labels.ip)}</th><th>${esc(labels.started)}</th><th>${esc(labels.traffic)}</th></tr></thead><tbody>${u.active_sessions.map(s=>`<tr><td>${esc(s.session_key)}</td><td>${esc(s.ras_name||'—')}</td><td>${esc(s.framed_ip||'—')}</td><td>${esc(s.started_at||'—')}</td><td>${bytes(s.input_octets)} ↓ / ${bytes(s.output_octets)} ↑</td></tr>`).join('')}</tbody></table>`:empty(labels.none)}</section>
   <section class="card wide"><h2>${esc(labels.credit_changes)}</h2>${u.credit_ledger.length?`<table class="table"><thead><tr><th>${esc(labels.time)}</th><th>${esc(labels.kind)}</th><th>${esc(labels.amount)}</th><th>${esc(labels.reference)}</th></tr></thead><tbody>${u.credit_ledger.map(c=>`<tr><td>${esc(c.created_at)}</td><td>${esc(c.kind)}</td><td>${esc(c.amount)} ${esc(c.currency)}</td><td>${esc(c.reference||'—')}</td></tr>`).join('')}</tbody></table>`:empty(labels.none)}</section>
  </main>`;
 }catch(e){app.innerHTML='<div class="error">'+esc(e.message)+'</div>'}
}
load();
</script>
</body></html>