<?php
declare(strict_types=1);

$locale = ($_GET['lang'] ?? 'fa') === 'en' ? 'en' : 'fa';
$dir = $locale === 'fa' ? 'rtl' : 'ltr';
$fa = ['home'=>'خانه','user'=>'کاربر','group'=>'گروه','report'=>'گزارش','graph'=>'نمودار','admin'=>'مدیر','setting'=>'تنظیمات','user_info'=>'اطلاعات کاربر','search'=>'جستجوی کاربر...','status'=>'وضعیت','all'=>'همه','active'=>'فعال','disabled'=>'غیرفعال','expired'=>'منقضی','locked'=>'قفل‌شده','new_user'=>'افزودن کاربر جدید','username'=>'نام کاربری','actions'=>'عملیات','open'=>'باز کردن','total'=>'کاربر','loading'=>'در حال بارگذاری...','empty'=>'کاربری مطابق فیلتر پیدا نشد.','error'=>'دریافت اطلاعات کاربران ناموفق بود.','previous'=>'قبلی','next'=>'بعدی'];
$en = ['home'=>'HOME','user'=>'USER','group'=>'GROUP','report'=>'REPORT','graph'=>'GRAPH','admin'=>'ADMIN','setting'=>'SETTING','user_info'=>'User Information','search'=>'Search User...','status'=>'Status','all'=>'All','active'=>'Active','disabled'=>'Disabled','expired'=>'Expired','locked'=>'Locked','new_user'=>'Add New User','username'=>'Username','actions'=>'Actions','open'=>'Open','total'=>'users','loading'=>'Loading...','empty'=>'No users match the current filters.','error'=>'Unable to load users.','previous'=>'Previous','next'=>'Next'];
$labels = $locale === 'fa' ? $fa : $en;
?>
<!doctype html>
<html lang="<?= htmlspecialchars($locale, ENT_QUOTES) ?>" dir="<?= $dir ?>">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>ATD Radius — <?= htmlspecialchars($labels['user']) ?></title>
  <link rel="stylesheet" href="/assets/atd.css">
</head>
<body>
<div class="atd-shell">
  <aside class="atd-sidebar">
    <div class="atd-brand"><span class="atd-mark">A</span><div><strong>ATD Radius</strong><small>Modernized IBSng</small></div></div>
    <nav>
      <?php foreach ($labels as $key => $label): if (!in_array($key, ['user_info','search','status','all','active','disabled','expired','locked','new_user','username','actions','open','total','loading','empty','error','previous','next'], true)): ?>
        <a class="atd-nav-item <?= $key === 'user' ? 'is-active' : '' ?>" href="<?= $key === 'user' ? '/users.php' : '/?lang=' . urlencode($locale) . '#' . htmlspecialchars($key) ?>"><span class="atd-nav-dot"></span><?= htmlspecialchars($label) ?></a>
      <?php endif; endforeach; ?>
    </nav>
  </aside>
  <div class="atd-main-shell">
    <header class="atd-header">
      <div><span class="eyebrow">IBSNG WORKSPACE</span><h1><?= htmlspecialchars($labels['user_info']) ?></h1></div>
      <div class="atd-header-actions">
        <a href="?lang=<?= $locale === 'fa' ? 'en' : 'fa' ?>"><?= $locale === 'fa' ? 'EN' : 'FA' ?></a>
        <button type="button" data-theme-toggle>Theme</button>
      </div>
    </header>
    <main class="atd-content">
      <section class="page-head">
        <div><span class="eyebrow">IDENTITY &amp; ACCESS</span><h2><?= htmlspecialchars($labels['user']) ?></h2><p id="user-count">—</p></div>
        <a class="primary" href="#new-user"><?= htmlspecialchars($labels['new_user']) ?></a>
      </section>

      <section class="toolbar">
        <label class="search-box"><span>⌕</span><input id="user-search" type="search" placeholder="<?= htmlspecialchars($labels['search']) ?>" autocomplete="off"></label>
        <label class="select-box"><span><?= htmlspecialchars($labels['status']) ?></span><select id="user-status"><option value=""><?= htmlspecialchars($labels['all']) ?></option><option value="active"><?= htmlspecialchars($labels['active']) ?></option><option value="disabled"><?= htmlspecialchars($labels['disabled']) ?></option><option value="expired"><?= htmlspecialchars($labels['expired']) ?></option><option value="locked"><?= htmlspecialchars($labels['locked']) ?></option></select></label>
      </section>

      <section class="table-card">
        <div id="user-loading" class="table-state"><?= htmlspecialchars($labels['loading']) ?></div>
        <div id="user-error" class="table-state is-error" hidden><?= htmlspecialchars($labels['error']) ?></div>
        <div id="user-empty" class="table-state" hidden><?= htmlspecialchars($labels['empty']) ?></div>
        <div class="table-scroll" id="user-table-wrap" hidden>
          <table class="data-table">
            <thead><tr><th><?= htmlspecialchars($labels['username']) ?></th><th><?= htmlspecialchars($labels['status']) ?></th><th><?= htmlspecialchars($labels['actions']) ?></th></tr></thead>
            <tbody id="user-rows"></tbody>
          </table>
        </div>
        <div class="table-footer">
          <button type="button" class="ghost" id="user-prev" disabled><?= htmlspecialchars($labels['previous']) ?></button>
          <span id="user-page">1</span>
          <button type="button" class="ghost" id="user-next" disabled><?= htmlspecialchars($labels['next']) ?></button>
        </div>
      </section>
    </main>
  </div>
</div>
<script>
window.ATD_USERS = { locale: <?= json_encode($locale) ?>, api: '/api/v1/users', labels: <?= json_encode(['open' => $labels['open'], 'active' => $labels['active'], 'disabled' => $labels['disabled'], 'expired' => $labels['expired'], 'locked' => $labels['locked']], JSON_UNESCAPED_UNICODE) ?> };
</script>
<script src="/assets/atd.js"></script>
<script src="/assets/users.js"></script>
</body>
</html>
