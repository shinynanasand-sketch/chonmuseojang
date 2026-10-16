const search = document.querySelector("#village-search");
const table = document.querySelector(".guide-table");
const empty = document.querySelector("#guide-search-empty");
const rows = document.querySelectorAll("[data-village]");

function compact(text) {
  return String(text || "").replace(/\s+/g, "");
}

function applyVillageSearch() {
  const query = compact(search.value);
  let shown = 0;
  rows.forEach((row) => {
    const hit = query.length > 0 && compact(row.dataset.village).includes(query);
    row.hidden = !hit;
    if (hit) shown += 1;
  });
  table.hidden = query.length === 0 || shown === 0;
  empty.hidden = query.length === 0 || shown > 0;
}

search.addEventListener("input", applyVillageSearch);
applyVillageSearch();
