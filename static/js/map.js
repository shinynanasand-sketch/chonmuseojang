function popupNode(village) {
  const box = document.createElement('div');
  const name = document.createElement('strong');
  name.textContent = village.village_name || '이름 없음';
  const link = document.createElement('a');
  link.href = `/nearby?village_id=${encodeURIComponent(village.village_id || '')}`;
  link.textContent = '주변정보';
  box.append(name, document.createElement('br'), link);
  return box;
}

async function initMap() {
  const map = L.map('map').setView([35.1, 126.9], 8);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
  const cluster = L.markerClusterGroup ? L.markerClusterGroup() : L.layerGroup();
  cluster.addTo(map);

  const res = await fetch('/api/villages');
  const data = await res.json();
  const villages = data.villages || [];
  const select = document.getElementById('sigungu-filter');
  const names = [...new Set(villages.map((village) => village.sigungu).filter(Boolean))].sort();
  names.forEach((name) => {
    const option = document.createElement('option');
    option.value = name;
    option.textContent = name;
    select.append(option);
  });

  const requested = new URLSearchParams(location.search).get('sigungu') || '';
  if (requested && names.includes(requested)) {
    select.value = requested;
  }

  function draw() {
    cluster.clearLayers();
    const sigungu = select.value;
    const visible = villages.filter((village) => {
      if (!village.latitude || !village.longitude) return false;
      return !sigungu || village.sigungu === sigungu;
    });
    visible.forEach((village) => {
      L.marker([village.latitude, village.longitude]).bindPopup(popupNode(village)).addTo(cluster);
    });
    if (visible.length) {
      const bounds = L.latLngBounds(visible.map((village) => [village.latitude, village.longitude]));
      map.fitBounds(bounds, { padding: [24, 24], maxZoom: sigungu ? 11 : 8 });
    }
  }

  select.addEventListener('change', draw);
  draw();
}

initMap();
