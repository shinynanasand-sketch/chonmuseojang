const search = document.querySelector("#village-search");
if (search) {
  const empty = document.querySelector("#guide-search-empty");
  const picks = document.querySelector("#village-picks");
  const form = document.querySelector("#dev-reset");
  const chosen = document.querySelector("#dev-chosen");
  const villageId = document.querySelector("#dev-village-id");
  const minLength = Number(search.dataset.minLength || "2");

  function compact(text) {
    return String(text || "").replace(/\s+/g, "");
  }

  const sources = [...document.querySelectorAll(".village-source")].map((element) => ({
    id: element.dataset.villageId || "",
    village: element.dataset.village || "",
    sigungu: element.dataset.sigungu || "",
  }));
  const sigunguByName = new Map();
  sources.forEach((source) => {
    const names = sigunguByName.get(source.village) || new Set();
    names.add(source.sigungu);
    sigunguByName.set(source.village, names);
  });

  function needsSigungu(village) {
    return (sigunguByName.get(village) || new Set()).size > 1;
  }

  function hideActions() {
    form.hidden = true;
    villageId.value = "";
    chosen.textContent = "";
  }

  function render(query) {
    picks.replaceChildren();
    hideActions();
    if (compact(query).length < minLength) {
      picks.hidden = true;
      empty.hidden = true;
      return;
    }
    const matched = sources.filter((source) => compact(source.village).includes(compact(query)));
    if (!matched.length) {
      picks.hidden = true;
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    picks.hidden = false;
    matched.forEach((source) => {
      const button = document.createElement("button");
      button.type = "button";
      const label = needsSigungu(source.village)
        ? `${source.sigungu} ${source.village}`
        : source.village;
      button.textContent = label;
      button.addEventListener("click", () => {
        picks.replaceChildren(button);
        villageId.value = source.id;
        chosen.textContent = label;
        form.hidden = false;
      });
      picks.append(button);
    });
  }

  search.addEventListener("input", () => render(search.value));
}
