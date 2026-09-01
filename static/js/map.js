async function initMap() {
  const map = L.map('map').setView([35.1, 126.9], 8);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
  const res = await fetch('/api/villages');
  const data = await res.json();
  (data.villages || []).forEach((v) => {
    if (v.latitude && v.longitude) {
      L.marker([v.latitude, v.longitude]).addTo(map).bindPopup(v.village_name);
    }
  });
}
initMap();
