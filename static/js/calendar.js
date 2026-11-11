const app = document.getElementById("calendar-app");
const token = app.dataset.token;
const mode = app.dataset.mode === "guest" ? "guest" : app.dataset.mode === "change" ? "change" : "operator";
const statusNode = document.getElementById("calendar-status");
const monthLabel = document.getElementById("month-label");
const grid = document.getElementById("month-grid");
const dayTitle = document.getElementById("day-title");
const dayEntries = document.getElementById("day-entries");
const guestForm = document.getElementById("guest-form");
const guestProgram = document.getElementById("guest-program");
const programList = document.getElementById("program-list");
const legend = document.getElementById("calendar-legend");

let snapshot = null;
let shown = new Date();
let selected = "";
let proposing = null;

function pad(value) {
  return String(value).padStart(2, "0");
}

function dateKey(year, month, day) {
  return `${year}-${pad(month)}-${pad(day)}`;
}

function entriesOn(day) {
  return (snapshot.entries || []).filter((row) => row.visit_date === day);
}

function bookingsOn(day) {
  return (snapshot.bookings || []).filter((row) => row.visit_date === day);
}

function inShownMonth(day) {
  if (!day || String(day).length < 7) return false;
  const year = Number(String(day).slice(0, 4));
  const month = Number(String(day).slice(5, 7));
  return year === shown.getFullYear() && month === shown.getMonth() + 1;
}

function setOtherMonthNote(show) {
  const note = document.getElementById("other-month-pending");
  if (note) note.hidden = !show;
}

function proposalsOn(day) {
  return (snapshot.bookings || []).filter((row) => row.proposed_visit_date === day);
}

function bySlot(left, right) {
  const a = `${left.visit_date} ${left.visit_time || ""}`;
  const b = `${right.visit_date} ${right.visit_time || ""}`;
  if (a < b) return -1;
  if (a > b) return 1;
  return (left.booking_id || 0) - (right.booking_id || 0);
}

function won(amount) {
  return `${Number(amount).toLocaleString("ko-KR")}원`;
}

function unitPrice(label) {
  if (!snapshot || !snapshot.prices) return null;
  const value = snapshot.prices[label];
  if (value == null || value === "") return null;
  return Number(value);
}

function bookingTotal(row) {
  if (!row || row.total == null || row.total === "") return "";
  return ` ${won(row.total)}`;
}

function partyText(row) {
  const group = String(row.group_name || "").trim();
  const people = `${row.num_people}명`;
  return group ? `${group} ${people}` : people;
}

function fillGuestPrograms() {
  guestProgram.innerHTML = "";
  (snapshot.experience_names || []).forEach((label) => {
    const option = document.createElement("option");
    option.value = label;
    const price = unitPrice(label);
    option.textContent = price == null ? label : `${label} ${won(price)}`;
    guestProgram.appendChild(option);
  });
  showGuestTotal();
}

function showGuestTotal() {
  const node = document.getElementById("guest-total");
  if (!node) return;
  const price = unitPrice(guestProgram.value);
  const people = Number(document.getElementById("guest-people").value);
  if (price == null) {
    node.textContent = "";
    return;
  }
  if (!people || people < 1) {
    node.textContent = `1인 ${won(price)}`;
    return;
  }
  node.textContent = `${people}명 ${won(price * people)}`;
}

function showPrograms() {
  programList.hidden = false;
  programList.innerHTML = "";
  const names = snapshot.experience_names || [];
  if (!names.length) {
    const item = document.createElement("li");
    item.textContent = "운영 중인 체험이 없습니다.";
    programList.appendChild(item);
    return;
  }
  names.forEach((label) => {
    const item = document.createElement("li");
    const price = unitPrice(label);
    item.textContent = price == null ? label : `${label} ${won(price)}`;
    programList.appendChild(item);
  });
}

function offerText(row) {
  if (!row.proposed_visit_date) return "";
  const clock = row.proposed_visit_time ? ` ${row.proposed_visit_time}` : "";
  return ` 변경 제안 중 ${row.proposed_visit_date}${clock}`;
}

function describeProposal(row) {
  const clock = row.visit_time ? ` ${row.visit_time}` : "";
  return `${row.label} · ${row.booking_id}번 · 현재 ${row.visit_date}${clock}. 바꿀 날짜를 누르고 시간을 입력합니다.`;
}

function addStatusButtons(item, row) {
  if (!snapshot.can_write || row.status !== "pending") return;
  const actions = document.createElement("div");
  actions.className = "card-actions";
  ["confirmed", "rejected"].forEach((status) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = status === "confirmed" ? "승인" : "거절";
    button.addEventListener("click", () => decideBooking(row, status));
    actions.appendChild(button);
  });
  const change = document.createElement("button");
  change.type = "button";
  change.textContent = "일정 변경";
  change.addEventListener("click", () => startPropose(row));
  actions.appendChild(change);
  item.appendChild(actions);
}

function addAnswerButtons(item) {
  const actions = document.createElement("div");
  actions.className = "card-actions";
  ["accept", "decline"].forEach((decision) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = decision === "accept" ? "변경 승인" : "변경 거부";
    button.addEventListener("click", () => answerChange(decision));
    actions.appendChild(button);
  });
  item.appendChild(actions);
}

function appendSlot(card, row) {
  const clock = row.visit_time ? ` ${row.visit_time}` : "";
  if (row.proposed_visit_date) {
    const pair = document.createElement("div");
    pair.className = "slot-pair";
    const original = document.createElement("p");
    original.textContent = `원래 ${row.visit_date}${clock}`;
    const offered = document.createElement("p");
    const offerClock = row.proposed_visit_time ? ` ${row.proposed_visit_time}` : "";
    offered.textContent = `제안 ${row.proposed_visit_date}${offerClock}`;
    pair.appendChild(original);
    pair.appendChild(offered);
    card.appendChild(pair);
    return;
  }
  const when = document.createElement("p");
  when.textContent = `${row.visit_date}${clock}`;
  card.appendChild(when);
}

function fillBoard(slot, title, rows, emptyText, withActions) {
  slot.innerHTML = "";
  slot.hidden = false;
  const heading = document.createElement("h2");
  heading.textContent = title;
  slot.appendChild(heading);
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = emptyText;
    slot.appendChild(empty);
    return;
  }
  rows.forEach((row) => {
    const card = document.createElement("article");
    card.className = row.status === "confirmed" ? "booking-card booking-confirmed" : "booking-card booking-pending";
    const name = document.createElement("p");
    name.className = "booking-name";
    const place = row.village_name ? `${row.village_name} ` : "";
    name.textContent = `${place}${row.label}`;
    const meta = document.createElement("p");
    meta.textContent = `${partyText(row)}${bookingTotal(row)} · ${row.booking_id}번`;
    card.appendChild(name);
    appendSlot(card, row);
    card.appendChild(meta);
    if (withActions) addStatusButtons(card, row);
    slot.appendChild(card);
  });
}

function showBoards() {
  const pendingSlot = document.getElementById("pending-list");
  const approvedSlot = document.getElementById("approved-list");
  const rejectedSlot = document.getElementById("rejected-list");
  const guest = mode === "guest";
  const operator = mode === "operator";
  if (!guest && !operator) {
    pendingSlot.hidden = true;
    approvedSlot.hidden = true;
    if (rejectedSlot) rejectedSlot.hidden = true;
    setOtherMonthNote(false);
    return;
  }
  if (operator) {
    programList.hidden = true;
    programList.innerHTML = "";
  }
  const bookings = (snapshot.bookings || []).filter((row) => inShownMonth(row.visit_date));
  const otherPending = (snapshot.bookings || []).some(
    (row) => row.status === "pending" && row.visit_date && !inShownMonth(row.visit_date),
  );
  setOtherMonthNote(operator && snapshot.can_write && otherPending);
  const withActions = operator;
  fillBoard(
    pendingSlot,
    "대기 예약",
    bookings.filter((row) => row.status === "pending").sort(bySlot),
    "대기 예약이 없습니다.",
    withActions,
  );
  fillBoard(
    approvedSlot,
    "승인된 체험",
    bookings.filter((row) => row.status === "confirmed").sort(bySlot),
    "승인된 체험이 없습니다.",
    false,
  );
  if (rejectedSlot) {
    fillBoard(
      rejectedSlot,
      "거절된 예약",
      bookings.filter((row) => row.status === "rejected").sort(bySlot),
      "거절된 예약이 없습니다.",
      false,
    );
  }
}

function syncGuestForm() {
  const names = (snapshot && snapshot.experience_names) || [];
  const open = mode === "guest" && names.length > 0 && Boolean(selected);
  guestForm.hidden = !open;
  const dateLine = document.getElementById("guest-date");
  if (dateLine) dateLine.textContent = open ? `${selected}에 예약합니다.` : "";
  showGuestTotal();
}

function guestNote(text) {
  const note = document.getElementById("guest-result");
  if (note) note.textContent = text;
  if (text) statusNode.textContent = text;
}

function revealGuestBooking() {
  if (mode !== "guest" || guestForm.hidden) return;
  const block = document.getElementById("guest-action");
  if (block) block.scrollIntoView({block: "start"});
}

function snapshotPath() {
  if (mode === "guest") return `/api/book/${token}`;
  if (mode === "change") return `/api/change/${token}`;
  const programView = app.dataset.view === "program";
  return programView ? `/api/calendar/${token}?view=program` : `/api/calendar/${token}`;
}

async function load(keepStatus) {
  const response = await fetch(snapshotPath());
  if (!response.ok) {
    statusNode.textContent = "달력을 열 수 없습니다.";
    return;
  }
  snapshot = await response.json();
  if (proposing) {
    const still = (snapshot.bookings || []).find(
      (row) => row.booking_id === proposing.booking_id && row.status === "pending",
    );
    proposing = still || null;
  }
  if (mode === "guest") {
    document.getElementById("calendar-title").textContent = `${snapshot.village_name} 예약 상태`;
    showPrograms();
    showBoards();
  } else if (mode === "change") {
    document.getElementById("calendar-title").textContent = snapshot.village_name
      ? `${snapshot.village_name} 일정 변경`
      : "일정 변경";
    programList.hidden = true;
    showBoards();
    if (snapshot.open && snapshot.focus_date) {
      const parts = snapshot.focus_date.split("-");
      shown = new Date(Number(parts[0]), Number(parts[1]) - 1, 1);
      selected = snapshot.focus_date;
    }
  } else {
    const heading = snapshot.can_write ? "예약 승인" : "체험 일정";
    document.getElementById("calendar-title").textContent = `${snapshot.village_name} ${heading}`;
    showBoards();
  }
  if (legend) legend.hidden = mode === "change";
  if (!keepStatus) {
    if (mode === "guest") {
      statusNode.textContent = (snapshot.experience_names || []).length
        ? "대기, 승인, 거절은 위 목록에 있습니다. 새 예약은 날짜를 누릅니다."
        : "운영 중인 체험이 없습니다.";
    } else if (mode === "change") {
      statusNode.textContent = snapshot.open
        ? "제안한 날짜를 보고 변경을 승인하거나 거부합니다."
        : "이 일정 변경은 이미 끝났습니다.";
    } else {
      statusNode.textContent = snapshot.can_write
        ? "대기인 날짜를 눌러 승인하거나 거절합니다."
        : "자기 체험 일정만 봅니다.";
    }
  }
  fillGuestPrograms();
  const proposeForm = document.getElementById("propose-form");
  proposeForm.hidden = !proposing;
  if (proposing) {
    document.getElementById("propose-target").textContent = describeProposal(proposing);
  }
  draw();
  if (selected) showDay(selected);
  else syncGuestForm();
}

function draw() {
  const year = shown.getFullYear();
  const month = shown.getMonth();
  monthLabel.textContent = `${year}년 ${month + 1}월`;
  grid.innerHTML = "";
  const first = new Date(year, month, 1).getDay();
  const last = new Date(year, month + 1, 0).getDate();
  for (let blank = 0; blank < first; blank += 1) {
    const empty = document.createElement("span");
    grid.appendChild(empty);
  }
  for (let day = 1; day <= last; day += 1) {
    const key = dateKey(year, month + 1, day);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "day-cell";
    const dayBookings = bookingsOn(key);
    const hasPending = dayBookings.some((row) => row.status === "pending");
    const hasConfirmed = dayBookings.some((row) => row.status === "confirmed");
    if (hasPending) button.classList.add("pending");
    if (hasConfirmed) button.classList.add("confirmed");
    if (!hasPending && !hasConfirmed && (entriesOn(key).length || dayBookings.length)) {
      button.classList.add("has");
    }
    if (proposalsOn(key).length) button.classList.add("proposed");
    if (key === selected) button.classList.add("selected");
    button.textContent = String(day);
    button.addEventListener("click", () => showDay(key));
    grid.appendChild(button);
  }
}

function showDay(key) {
  const changed = selected !== key;
  selected = key;
  if (changed) guestNote("");
  dayTitle.textContent = key;
  dayEntries.innerHTML = "";
  const rows = entriesOn(key);
  const bookings = bookingsOn(key);
  if (!rows.length && !bookings.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "이 날짜의 일정이 없습니다.";
    dayEntries.appendChild(empty);
  }
  bookings.forEach((row) => {
    const item = document.createElement("div");
    item.className = "day-line";
    if (row.status === "pending") item.classList.add("booking-pending");
    if (row.status === "confirmed") item.classList.add("booking-confirmed");
    const clock = row.visit_time ? ` ${row.visit_time}` : "";
    if (mode === "change") {
      const originalClock = row.original_visit_time ? ` ${row.original_visit_time}` : "";
      const original = row.original_visit_date ? ` 원래 ${row.original_visit_date}${originalClock}` : "";
      item.textContent = `${row.booking_id}번 ${row.label}${clock} ${partyText(row)}${bookingTotal(row)}${original}`;
      if (snapshot.open) addAnswerButtons(item);
    } else {
      const place = row.village_name ? `${row.village_name} ` : "";
      item.textContent = `${row.booking_id}번 ${row.status_label} ${place}${row.label}${clock} ${partyText(row)}${bookingTotal(row)}${offerText(row)}`;
      addStatusButtons(item, row);
    }
    dayEntries.appendChild(item);
  });
  rows.forEach((row) => {
    const item = document.createElement("p");
    item.textContent = `${row.label} ${row.group_name} ${row.num_people}명`;
    if (snapshot.can_write) {
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "삭제";
      remove.addEventListener("click", () => removeEntry(row));
      item.appendChild(remove);
    }
    dayEntries.appendChild(item);
  });
  syncGuestForm();
  draw();
  revealGuestBooking();
}

function startPropose(row) {
  proposing = row;
  const proposeForm = document.getElementById("propose-form");
  proposeForm.hidden = false;
  document.getElementById("propose-target").textContent = describeProposal(row);
  const timeInput = document.getElementById("propose-time");
  if (row.visit_time) timeInput.value = String(row.visit_time).slice(0, 5);
  statusNode.textContent = "바꿀 날짜를 누른 뒤 시간을 입력하고 제안을 보냅니다.";
}

async function answerChange(decision) {
  const response = await fetch(`/api/change/${token}`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({decision}),
  });
  statusNode.textContent = response.ok
    ? (decision === "accept" ? "변경을 승인했습니다. 예약은 대기입니다." : "변경을 거부했습니다.")
    : "이 일정 변경은 이미 끝났습니다.";
  if (response.ok) await load(true);
}

async function decideBooking(row, status) {
  const response = await fetch(`/api/calendar/${token}/bookings/${row.booking_id}`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({status}),
  });
  statusNode.textContent = response.ok ? "예약 상태를 바꿨습니다." : "예약 상태를 바꾸지 못했습니다.";
  if (response.ok) await load(true);
}

async function removeEntry(row) {
  const response = await fetch(`/api/calendar/${token}`, {
    method: "DELETE",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      label: row.label,
      visit_date: row.visit_date,
      group_name: row.group_name,
    }),
  });
  statusNode.textContent = response.ok ? "일정을 지웠습니다." : "지우지 못했습니다.";
  if (response.ok) await load(true);
}

guestProgram.addEventListener("change", showGuestTotal);
document.getElementById("guest-people").addEventListener("input", showGuestTotal);

guestForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selected) {
    guestNote("날짜를 먼저 눌러 주세요.");
    return;
  }
  const groupName = document.getElementById("group-name").value.trim();
  if (!groupName) {
    guestNote("단체 이름이 없으면 없음을 입력해 주세요.");
    return;
  }
  const visitTime = document.getElementById("visit-time").value;
  if (!visitTime) {
    guestNote("시간을 입력해 주세요.");
    return;
  }
  const people = Number(document.getElementById("guest-people").value);
  if (!people || people < 1) {
    guestNote("인원을 1명 이상으로 입력해 주세요.");
    return;
  }
  const response = await fetch(`/api/book/${token}`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      label: guestProgram.value,
      visit_date: selected,
      visit_time: visitTime,
      num_people: people,
      group_name: groupName,
    }),
  });
  if (!response.ok) {
    const failed = await response.json().catch(() => ({}));
    guestNote(failed.detail || "예약하지 못했습니다.");
    return;
  }
  const saved = await response.json();
  if (!saved.booking_id) {
    guestNote("예약을 접수하지 못했습니다. 다시 눌러 주세요.");
    return;
  }
  const total = saved.total == null || saved.total === "" ? "" : ` ${saved.num_people}명 ${won(saved.total)}.`;
  const party = saved.group_name ? `${saved.group_name} ` : "";
  if (saved.headcount_updated || saved.group_updated) {
    guestNote(`예약번호 ${saved.booking_id}번 ${party}${saved.num_people}명으로 고쳤습니다.${total}`);
  } else if (saved.already_open) {
    guestNote(`예약번호 ${saved.booking_id}번은 이미 ${saved.status_label} 상태입니다.${total}`);
  } else {
    guestNote(`예약번호 ${saved.booking_id}번 ${party}${saved.label} ${saved.visit_date} ${saved.visit_time} 예약을 대기로 접수했습니다.${total} 위 목록에서 볼 수 있습니다.`);
  }
  await load(true);
  const note = document.getElementById("guest-result");
  if (note) note.scrollIntoView({block: "center"});
});

document.getElementById("propose-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!proposing) return;
  if (!selected) {
    statusNode.textContent = "날짜를 먼저 눌러 주세요.";
    return;
  }
  const response = await fetch(`/api/calendar/${token}/bookings/${proposing.booking_id}/proposal`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      visit_date: selected,
      visit_time: document.getElementById("propose-time").value,
    }),
  });
  statusNode.textContent = response.ok ? "일정 변경을 제안했습니다." : "일정을 제안하지 못했습니다.";
  if (response.ok) {
    proposing = null;
    document.getElementById("propose-form").hidden = true;
    await load(true);
  }
});

function moveMonth(offset) {
  shown = new Date(shown.getFullYear(), shown.getMonth() + offset, 1);
  if (selected && !inShownMonth(selected)) {
    selected = "";
    dayTitle.textContent = "날짜를 눌러 주세요";
    dayEntries.innerHTML = "";
    syncGuestForm();
  }
  showBoards();
  draw();
}

document.getElementById("prev-month").addEventListener("click", () => moveMonth(-1));
document.getElementById("next-month").addEventListener("click", () => moveMonth(1));

load();
