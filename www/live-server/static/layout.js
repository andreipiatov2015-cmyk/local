document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.querySelector('.sidebar');
  const collapseButton = document.getElementById('collapseSidebar');

  collapseButton?.addEventListener('click', () => {
    sidebar?.classList.toggle('collapsed');
    document.dispatchEvent(new CustomEvent('layout:sidebar-toggled', {
      detail: { collapsed: !!sidebar?.classList.contains('collapsed') }
    }));
  });
});
