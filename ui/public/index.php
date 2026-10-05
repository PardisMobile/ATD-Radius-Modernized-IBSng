<?php
declare(strict_types=1);

$locale = ($_GET['lang'] ?? 'fa') === 'en' ? 'en' : 'fa';
$dir = $locale === 'fa' ? 'rtl' : 'ltr';
$labels = $locale === 'fa'
    ? ['home' => 'خانه', 'user' => 'کاربر', 'group' => 'گروه', 'report' => 'گزارش', 'graph' => 'نمودار', 'admin' => 'مدیر', 'setting' => 'تنظیمات']
    : ['home' => 'HOME', 'user' => 'USER', 'group' => 'GROUP', 'report' => 'REPORT', 'graph' => 'GRAPH', 'admin' => 'ADMIN', 'setting' => 'SETTING'];
?><!doctype html>
<html lang="<?= htmlspecialchars($locale, ENT_QUOTES) ?>" dir="<?= $dir ?>">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>ATD Radius — <?= htmlspecialchars($labels['home']) ?></title>
  <link rel="stylesheet" href="/assets/atd.css">
</head>
<body>
<div class="atd-shell">
  <aside class="atd-sidebar">
    <div class="atd-brand"><span class="atd-mark">A</span><div><strong>ATD Radius</strong><small>Modernized IBSng</small></div></div>
    <nav>
      <?php foreach ($labels as $key => $label): ?>
        <?php $href = $key === 'user' ? '/users.php?lang=' . urlencode($locale) : '#' . htmlspecialchars($key); ?>
        <a class="atd-nav-item <?= $key === 'home' ? 'is-active' : '' ?>" href="<?= $href ?>"><span class="atd-nav-dot"></span><?= htmlspecialchars($label) ?></a>
      <?php endforeach; ?>
    </nav>
  </aside>
  <div class="atd-main-shell">
    <header class="atd-header"><div><span class="eyebrow">AAA CONTROL PLANE</span><h1><?= htmlspecialchars($labels['home']) ?></h1></div><div class="atd-header-actions"><a href="?lang=<?= $locale === 'fa' ? 'en' : 'fa' ?>"><?= $locale === 'fa' ? 'EN' : 'FA' ?></a><button type="button" data-theme-toggle>Theme</button></div></header>
    <main class="atd-content">
      <section class="hero"><div><span class="eyebrow">IBSNG MODERNIZATION</span><h2>Operational clarity for AAA infrastructure.</h2><p>IBSng workflows, rebuilt on a modern runtime with RADIUS and IBSng-compatible operator workflows.</p></div></section>
      <section class="stat-grid">
        <?php foreach ([['User Information','0'],['Online Users','0'],['RAS','0'],['IPPool','0']] as $stat): ?>
          <article class="stat-card"><span><?= htmlspecialchars($stat[0]) ?></span><strong><?= htmlspecialchars($stat[1]) ?></strong></article>
        <?php endforeach; ?>
      </section>
      <section class="workspace"><div><span class="eyebrow">NEXT</span><h3>Connect the domain services</h3><p>The dashboard remains intentionally compact; operational detail lives inside each IBSng-style workspace.</p></div><a class="primary" href="/users.php?lang=<?= urlencode($locale) ?>"><?= htmlspecialchars($labels['user']) ?></a></section>
    </main>
  </div>
</div>
<script src="/assets/atd.js"></script>
</body>
</html>
