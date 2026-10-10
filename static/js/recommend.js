function programText(item) {
  const name = String(item.program_name || '').trim();
  const type = String(item.program_type || '').split('+')[0].trim();
  if (name && type && !name.includes(type)) return `${name} · ${type}`;
  return name || type;
}

function detailLine(value) {
  const raw = String(value || '').trim();
  if (!raw) return null;
  const p = document.createElement('p');
  p.textContent = raw.length > 120 ? `${raw.slice(0, 120)}…` : raw;
  return p;
}

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
    if (item.grade) {
      const badge = document.createElement('span');
      badge.className = 'badge';
      badge.textContent = item.grade;
      title.append(badge);
    }
    const place = document.createElement('p');
    place.textContent = item.sigungu || '시군구 미상';
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
    card.append(title, place, reason);
    [item.address, programText(item), item.facilities].forEach((value) => {
      const line = detailLine(value);
      if (line) card.append(line);
    });
    card.append(links);
    container.appendChild(card);
  });
  if (!results.length) {
    container.textContent = data.message || '결과가 없습니다.';
  }
});
