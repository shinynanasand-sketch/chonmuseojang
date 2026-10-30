const app = document.getElementById("calendar-app");
const token = app.dataset.token;
const mode = app.dataset.mode === "guest" ? "guest" : app.dataset.mode === "change" ? "change" : "operator";
const statusNode = document.getElementById("calendar-status");
const monthLabel = document.getElementById("month-label");
const grid = document.getElementById("month-grid");
const dayTitle = document.getElementById("day-title");
const dayEntries = document.getElementById("day-entries");
const form = document.getElementById("entry-form");
const guestForm = document.getElementById("guest-form");
const programSelect = document.getElementById("program-label");
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

function fillSelect(select, labels) {
  select.innerHTML = "";
  labels.forEach((label) => {
    const option = document.createElement("option");
    option.value = label;
    option.textContent = label;
    select.appendChild(option);
  });
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
    item.textContent = label;
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
    name.textContent = row.label;
    const meta = document.createElement("p");
    meta.textContent = `${row.num_people}명 · ${row.booking_id}번`;
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
  if (mode !== "operator") {
    pendingSlot.hidden = true;
    approvedSlot.hidden = true;
    return;
  }
  programList.hidden = true;
  programList.innerHTML = "";
  const bookings = snapshot.bookings || [];
  fillBoard(
    pendingSlot,
    "대기 예약",
    bookings.filter((row) => row.status === "pending").sort(bySlot),
    "대기 예약이 없습니다.",
    true,
  );
  fillBoard(
    approvedSlot,
    "승인된 체험",
    bookings.filter((row) => row.status === "confirmed").sort(bySlot),
    "승인된 체험이 없습니다.",
    false,
  );
}

function syncGuestForm() {
  const names = (snapshot && snapshot.experience_names) || [];
  const open = mode === "guest" && names.length > 0 && Boolean(selected);
  guestForm.hidden = !open;
  const dateLine = document.getElementById("guest-date");
  if (dateLine) dateLine.textContent = open ? `${selected}에 예약합니다.` : "";
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
    document.getElementById("calendar-title").textContent = `${snapshot.village_name} 체험 달력`;
    showPrograms();
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
        ? "날짜를 누르고 체험, 시간, 인원을 고릅니다."
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
  fillSelect(programSelect, snapshot.programs || []);
  fillSelect(guestProgram, snapshot.experience_names || []);
  form.hidden = mode !== "operator" || !snapshot.can_write;
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
  selected = key;
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
      item.textContent = `${row.booking_id}번 ${row.label}${clock} ${row.num_people}명${original}`;
      if (snapshot.open) addAnswerButtons(item);
    } else {
      item.textContent = `${row.booking_id}번 ${row.status_label} ${row.label}${clock} ${row.num_people}명${offerText(row)}`;
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

guestForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selected) {
    statusNode.textContent = "날짜를 먼저 눌러 주세요.";
    return;
  }
  const response = await fetch(`/api/book/${token}`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      label: guestProgram.value,
      visit_date: selected,
      visit_time: document.getElementById("visit-time").value,
      num_people: Number(document.getElementById("guest-people").value),
    }),
  });
  if (!response.ok) {
    statusNode.textContent = "예약하지 못했습니다.";
    return;
  }
  const saved = await response.json();
  statusNode.textContent = `${saved.label} ${saved.visit_date} ${saved.visit_time} ${saved.booking_id}번 예약을 접수했습니다.`;
  await load(true);
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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selected) {
    statusNode.textContent = "날짜를 먼저 눌러 주세요.";
    return;
  }
  const response = await fetch(`/api/calendar/${token}`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      label: programSelect.value,
      visit_date: selected,
      group_name: document.getElementById("group-name").value,
      num_people: Number(document.getElementById("num-people").value),
    }),
  });
  statusNode.textContent = response.ok ? "일정을 저장했습니다." : "저장하지 못했습니다.";
  if (response.ok) await load(true);
});

document.getElementById("prev-month").addEventListener("click", () => {
  shown = new Date(shown.getFullYear(), shown.getMonth() - 1, 1);
  draw();
});
document.getElementById("next-month").addEventListener("click", () => {
  shown = new Date(shown.getFullYear(), shown.getMonth() + 1, 1);
  draw();
});

load();
