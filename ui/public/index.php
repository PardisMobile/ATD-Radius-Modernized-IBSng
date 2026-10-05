<?php
declare(strict_types=1);

$locale = ($_GET['lang'] ?? 'fa') === 'en' ? 'en' : 'fa';
$dir = $locale === 'fa' ? 'rtl' : 'ltr';
$labels = $locale === 'fa'
    ? ['dashboard' => 'داشبورد', 'users' => 'کاربران', 'groups' => 'گروه‌ها', 'services' => 'سرویس‌ها', 'ras' => 'RAS / NAS', 'pools' => 'IP Pool', 'sessions' => 'Sessionها', 'accounting' => 'Accounting', 'billing' => 'Billing', 'reports' => 'گزارش‌ها', 'admin' => 'مدیریت']
    : ['dashboard' => 'Dashboard', 'users' => 'Users', 'groups' => 'Groups', 'services' => 'Services', 'ras' => 'RAS / NAS', 'pools' => 'IP Pools', 'sessions' => 'Sessions', 'accounting' => 'Accounting', 'billing' => 'Billing', 'reports' => 'Reports', 'admin' => 'Administration'];
?><!doctype html>
<html lang="<?= htmlspecialchars($locale, ENT_QUOTES) ?>" dir="<?= $dir ?>">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>ATD Radius — <?= htmlspecialchars($labels['dashboard']) ?></title>
  <link rel="stylesheet" href="/assets/atd.css">
</head>
<body>
<div class="atd-shell">
  <aside class="atd-sidebar">
    <div class="atd-brand"><span class="atd-mark">A</span><div><strong>ATD Radius</strong><small>Modernized IBSng</small></div></div>
    <nav>
      <?php foreach ($labels as $key => $label): ?>
        <?php $href = $key === 'users' ? '/users.php?lang=' . urlencode($locale) : '#' . htmlspecialchars($key); ?>
        <a class="atd-nav-item <?= $key === 'dashboard' ? 'is-active' : '' ?>" href="<?= $href ?>"><span class="atd-nav-dot"></span><?= htmlspecialchars($label) ?></a>
      <?php endforeach; ?>
    </nav>
  </aside>
  <div class="atd-main-shell">
    <header class="atd-header"><div><span class="eyebrow">AAA CONTROL PLANE</span><h1><?= htmlspecialchars($labels['dashboard']) ?></h1></div><div class="atd-header-actions"><a href="?lang=<?= $locale === 'fa' ? 'en' : 'fa' ?>"><?= $locale === 'fa' ? 'EN' : 'FA' ?></a><button type="button" data-theme-toggle>Theme</button></div></header>
    <main class="atd-content">
      <section class="hero"><div><span class="eyebrow">IBSNG MODERNIZATION</span><h2>Operational clarity for AAA infrastructure.</h2><p>IBSng workflows, rebuilt on a modern runtime with RADIUS, EAP and a focused network-operations UI.</p></div></section>
      <section class="stat-grid">
        <?php foreach ([['Users','0'],['Online Sessions','0'],['RAS / NAS','0'],['IP Pools','0']] as $stat): ?>
          <article class="stat-card"><span><?= htmlspecialchars($stat[0]) ?></span><strong><?= htmlspecialchars($stat[1]) ?></strong></article>
        <?php endforeach; ?>
      </section>
      <section class="workspace"><div><span class="eyebrow">NEXT</span><h3>Connect the domain services</h3><p>The dashboard remains intentionally compact; operational detail lives inside each IBSng-style workspace.</p></div><a class="primary" href="/users.php?lang=<?= urlencode($locale) ?>"><?= htmlspecialchars($labels['users']) ?></a></section>
    </main>
  </div>
</div>
<script src="/assets/atd.js"></script>
</body>
</html>
