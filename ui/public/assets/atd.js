(() => {
  const root = document.documentElement;
  const saved = localStorage.getItem('atd-theme');
  if (saved === 'dark') root.classList.add('dark');
  document.querySelector('[data-theme-toggle]')?.addEventListener('click', () => {
    root.classList.toggle('dark');
    localStorage.setItem('atd-theme', root.classList.contains('dark') ? 'dark' : 'light');
  });
})();
