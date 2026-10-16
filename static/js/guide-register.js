const search = document.querySelector("#village-search");
const empty = document.querySelector("#guide-search-empty");
const picks = document.querySelector("#village-picks");
const lines = document.querySelector("#registration-lines");
const locked = document.querySelector("#registration-locked");
const minLength = Number(search.dataset.minLength || "2");

function compact(text) {
  return String(text || "").replace(/\s+/g, "");
}

function readSources() {
  return [...document.querySelectorAll(".village-source")].map((element) => ({
    village: element.dataset.village || "",
    sigungu: element.dataset.sigungu || "",
    code: element.dataset.code || "",
    programs: [...element.querySelectorAll("[data-program]")].map(
      (item) => item.dataset.program || ""
    ),
  }));
}

const sources = readSources();
const sigunguByName = new Map();
sources.forEach((source) => {
  const names = sigunguByName.get(source.village) || new Set();
  names.add(source.sigungu);
  sigunguByName.set(source.village, names);
});

function needsSigungu(village) {
  return (sigunguByName.get(village) || new Set()).size > 1;
}

function matchingGroups(query) {
  const groups = new Map();
  sources.forEach((source) => {
    if (!compact(source.village).includes(query)) return;
    const key = `${source.sigungu}\0${source.village}`;
    const group = groups.get(key);
    if (!group) {
      groups.set(key, {
        village: source.village,
        sigungu: source.sigungu,
        code: source.code,
        programs: source.programs.filter(Boolean),
      });
      return;
    }
    if (!group.code && source.code) group.code = source.code;
    source.programs.forEach((program) => {
      if (program && !group.programs.includes(program)) group.programs.push(program);
    });
  });
  return [...groups.values()].sort((left, right) =>
    `${left.sigungu}${left.village}`.localeCompare(`${right.sigungu}${right.village}`, "ko")
  );
}

function hideResult() {
  empty.hidden = true;
  picks.hidden = true;
  picks.replaceChildren();
  lines.hidden = true;
  lines.replaceChildren();
  locked.hidden = true;
}

function showLines(group) {
  lines.replaceChildren();
  if (!group.code) {
    lines.hidden = true;
    locked.hidden = false;
    return;
  }
  const prefix = needsSigungu(group.village)
    ? `${group.sigungu} ${group.village}`.trim()
    : group.village;
  const add = (text) => {
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    lines.appendChild(paragraph);
  };
  add(`${prefix} ${group.code}`);
  group.programs.forEach((program) => add(`${prefix} ${group.code} ${program}`));
  lines.hidden = false;
  locked.hidden = true;
}

function renderPicks(groups) {
  picks.replaceChildren();
  groups.forEach((group) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = needsSigungu(group.village)
      ? `${group.sigungu} ${group.village}`.trim()
      : group.village;
    button.addEventListener("click", () => {
      [...picks.children].forEach((item) => {
        item.hidden = item !== button;
      });
      showLines(group);
    });
    picks.appendChild(button);
  });
  picks.hidden = groups.length === 0;
}

function applyVillageSearch() {
  const query = compact(search.value);
  hideResult();
  if (query.length < minLength) return;
  const groups = matchingGroups(query);
  empty.hidden = groups.length > 0;
  renderPicks(groups);
}

search.addEventListener("input", applyVillageSearch);
applyVillageSearch();
