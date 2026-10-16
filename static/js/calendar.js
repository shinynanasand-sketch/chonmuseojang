const app = document.getElementById("calendar-app");
const token = app.dataset.token;
const statusNode = document.getElementById("calendar-status");
const monthLabel = document.getElementById("month-label");
const grid = document.getElementById("month-grid");
const dayTitle = document.getElementById("day-title");
const dayEntries = document.getElementById("day-entries");
const form = document.getElementById("entry-form");
const programSelect = document.getElementById("program-label");

let snapshot = null;
let shown = new Date();
let selected = "";

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

async function load(keepStatus) {
  const response = await fetch(`/api/calendar/${token}`);
  if (!response.ok) {
    statusNode.textContent = "달력을 열 수 없습니다.";
    return;
  }
  snapshot = await response.json();
  document.getElementById("calendar-title").textContent = `${snapshot.village_name} 체험 달력`;
  if (!keepStatus) {
    statusNode.textContent = snapshot.can_write
      ? "날짜를 누르고 단체와 인원을 저장합니다."
      : "자기 체험 일정만 봅니다.";
  }
  programSelect.innerHTML = "";
  (snapshot.programs || []).forEach((label) => {
    const option = document.createElement("option");
    option.value = label;
    option.textContent = label;
    programSelect.appendChild(option);
  });
  form.hidden = !snapshot.can_write;
  draw();
  if (selected) showDay(selected);
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
    if (dayBookings.some((row) => row.status === "pending")) button.classList.add("pending");
    else if (dayBookings.some((row) => row.status === "confirmed")) button.classList.add("confirmed");
    else if (entriesOn(key).length || dayBookings.length) button.classList.add("has");
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
    const item = document.createElement("p");
    if (row.status === "pending") item.className = "booking-pending";
    if (row.status === "confirmed") item.className = "booking-confirmed";
    item.textContent = `${row.booking_id}번 ${row.status_label} ${row.label} ${row.num_people}명`;
    if (snapshot.can_write) {
      ["confirmed", "rejected"].forEach((status) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = status === "confirmed" ? "승인" : "거절";
        button.addEventListener("click", () => decideBooking(row, status));
        item.appendChild(button);
      });
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
  draw();
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
