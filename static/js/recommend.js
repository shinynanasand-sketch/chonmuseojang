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
  container.replaceChildren();
  const results = data.results || [];
  results.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'card';
    const title = document.createElement('strong');
    title.textContent = item.village_name || '이름 없음';
    const place = document.createElement('p');
    const program = item.program_type ? item.program_type.split('+')[0].trim() : '';
    place.textContent = program
      ? `${item.sigungu || '시군구 미상'} · ${program}`
      : (item.sigungu || '시군구 미상');
    const reason = document.createElement('p');
    reason.textContent = item.reason || '';
    const links = document.createElement('p');
    links.className = 'card-links';
    if (item.village_id) {
      const nearby = document.createElement('a');
      nearby.href = `/nearby?village_id=${encodeURIComponent(item.village_id)}`;
      nearby.textContent = '주변정보';
      links.append(nearby);
    }
    card.append(title, place, reason, links);
    container.appendChild(card);
  });
  if (!results.length) {
    container.textContent = data.message || '결과가 없습니다.';
  }
});
