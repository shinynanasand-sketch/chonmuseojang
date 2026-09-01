document.getElementById('recommend-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const query = document.getElementById('query').value;
  const res = await fetch('/api/recommend', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  const data = await res.json();
  const container = document.getElementById('results');
  container.innerHTML = '';
  (data.results || []).forEach((item) => {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `<strong>${item.village_name}</strong><p>${item.reason || ''}</p>`;
    container.appendChild(card);
  });
  if (!data.results?.length) {
    container.textContent = data.message || '결과가 없습니다.';
  }
});
