document.addEventListener('DOMContentLoaded', function () {
  const searchInputs = document.querySelectorAll('.table-search');
  searchInputs.forEach(input => {
    input.addEventListener('input', function (e) {
      const term = e.target.value.toLowerCase();
      const table = e.target.closest('.card')?.querySelector('table');
      if (!table) return;
      const rows = table.querySelectorAll('tbody tr');
      rows.forEach(row => {
        const text = row.innerText.toLowerCase();
        row.style.display = text.includes(term) ? '' : 'none';
      });
    });
  });
});
