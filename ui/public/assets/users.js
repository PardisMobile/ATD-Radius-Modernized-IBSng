(() => {
  const cfg = window.ATD_USERS || {};
  const search = document.querySelector('#user-search');
  const status = document.querySelector('#user-status');
  const rows = document.querySelector('#user-rows');
  const loading = document.querySelector('#user-loading');
  const empty = document.querySelector('#user-empty');
  const error = document.querySelector('#user-error');
  const table = document.querySelector('#user-table-wrap');
  const count = document.querySelector('#user-count');
  const pageLabel = document.querySelector('#user-page');
  const prev = document.querySelector('#user-prev');
  const next = document.querySelector('#user-next');
  const pageSize = 25;
  let offset = 0;

  const escapeHTML = value => String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#039;','"':'&quot;'}[c]));
  const statusLabel = value => cfg.labels?.[value] || value;

  async function load() {
    loading.hidden = false;
    error.hidden = true;
    empty.hidden = true;
    table.hidden = true;
    rows.innerHTML = '';
    const params = new URLSearchParams({limit: String(pageSize), offset: String(offset)});
    if (search.value.trim()) params.set('search', search.value.trim());
    if (status.value) params.set('status', status.value);
    try {
      const response = await fetch(`${cfg.api}?${params.toString()}`, {headers: {'Accept': 'application/json'}});
      if (!response.ok) throw new Error('request failed');
      const payload = await response.json();
      loading.hidden = true;
      count.textContent = `${payload.total} ${payload.total === 1 ? (cfg.locale === 'fa' ? 'کاربر' : 'user') : (cfg.locale === 'fa' ? 'کاربر' : 'users')}`;
      pageLabel.textContent = String(Math.floor(payload.offset / payload.limit) + 1);
      prev.disabled = payload.offset === 0;
      next.disabled = payload.offset + payload.items.length >= payload.total;
      if (!payload.items.length) { empty.hidden = false; return; }
      table.hidden = false;
      rows.innerHTML = payload.items.map(user => `
        <tr>
          <td><div class="user-cell"><span class="avatar">${escapeHTML(user.username.slice(0,1).toUpperCase())}</span><div><strong>${escapeHTML(user.username)}</strong><small>${escapeHTML(user.id)}</small></div></div></td>
          <td><span class="status-pill status-${escapeHTML(user.status)}"><i></i>${escapeHTML(statusLabel(user.status))}</span></td>
          <td><a class="row-action" href="#user/${encodeURIComponent(user.username)}">${escapeHTML(cfg.labels?.open || 'Open')}</a></td>
        </tr>`).join('');
    } catch (_) {
      loading.hidden = true;
      error.hidden = false;
      prev.disabled = true;
      next.disabled = true;
    }
  }

  let timer;
  search.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => { offset = 0; load(); }, 220); });
  status.addEventListener('change', () => { offset = 0; load(); });
  prev.addEventListener('click', () => { offset = Math.max(0, offset - pageSize); load(); });
  next.addEventListener('click', () => { offset += pageSize; load(); });
  load();
})();
