const $ = (s, r = document) => r.querySelector(s);

function el(tag, props = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) n.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) n.append(k instanceof Node ? k : document.createTextNode(k ?? ""));
  return n;
}

async function api(path, { method = "GET", body } = {}) {
  const r = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await r.json(); } catch { /* пустой ответ */ }
  if (!r.ok) {
    let msg = data?.detail ?? r.statusText;
    if (Array.isArray(msg)) msg = msg.map((e) => e.msg).join("; ");
    throw new Error(msg);
  }
  return data;
}

function message(box, text, kind) {
  box.className = "msg " + kind;
  box.replaceChildren(...(Array.isArray(text) ? text : [text]));
  box.hidden = false;
}

/* ---------- выбор оффера с автокомплитом ---------- */
function offerPicker() {
  const input = el("input", { type: "search", placeholder: "Название или ID оффера", autocomplete: "off" });
  const list = el("ul", { class: "suggest", hidden: true });
  const root = el("div", { class: "picker" }, input, list);
  let selected = null, timer = null;

  function choose(o) {
    selected = o;
    input.value = `[${o.id}] ${o.name}`;
    list.hidden = true;
  }

  async function search() {
    const q = input.value.trim();
    if (!q) { list.hidden = true; return; }
    try {
      const items = await api("/api/offers?q=" + encodeURIComponent(q));
      list.replaceChildren(
        ...(items.length
          ? items.map((o) => el("li", { onclick: () => choose(o) },
              `[${o.id}] ${o.name}` + (o.country.length ? ` (${o.country.join(", ")})` : "")))
          : [el("li", { class: "empty" }, "Ничего не найдено")])
      );
    } catch (e) {
      list.replaceChildren(el("li", { class: "empty" }, e.message));
    }
    list.hidden = false;
  }

  input.addEventListener("input", () => {
    selected = null;
    clearTimeout(timer);
    timer = setTimeout(search, 250);
  });
  document.addEventListener("click", (e) => { if (!root.contains(e.target)) list.hidden = true; });

  return {
    root,
    get offer() { return selected; },
    clear() { selected = null; input.value = ""; },
  };
}

/* ---------- вкладки ---------- */
document.querySelectorAll(".tab").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === b));
    ["create", "edit"].forEach((id) => ($("#" + id).hidden = id !== b.dataset.tab));
    if (b.dataset.tab === "edit") loadRecent();
  })
);

/* ---------- часть 1: создание ---------- */
const createPicker = offerPicker();
$("#c-offer").append(createPicker.root);

$("#c-submit").addEventListener("click", async () => {
  const box = $("#c-msg"), btn = $("#c-submit");
  const name = $("#c-name").value.trim(), geo = $("#c-geo").value.trim();
  if (!name || !geo || !createPicker.offer) {
    return message(box, "Заполните название, гео и выберите оффер из списка", "err");
  }
  btn.disabled = true;
  try {
    const c = await api("/api/campaigns", { method: "POST", body: { name, geo, offer_id: createPicker.offer.id } });
    message(box, [
      `Кампания создана: ID ${c.id}, ссылка `, el("b", {}, c.url), ". ",
      el("a", { href: c.admin_url, target: "_blank", rel: "noopener" }, "Открыть в Keitaro"), " · ",
      el("a", { href: "#", onclick: (e) => { e.preventDefault(); openInEditor(c.id); } }, "Открыть в редакторе"),
    ], "ok");
    $("#c-name").value = ""; $("#c-geo").value = ""; createPicker.clear();
  } catch (e) {
    message(box, e.message, "err");
  } finally {
    btn.disabled = false;
  }
});

/* ---------- часть 2: редактор ---------- */
async function loadRecent() {
  try {
    const items = await api("/api/campaigns");
    $("#e-recent").replaceChildren(...items.map((c) =>
      el("button", { onclick: () => openInEditor(c.id), title: c.geo }, c.name)));
  } catch { /* список необязателен */ }
}

function openInEditor(id) {
  document.querySelector('.tab[data-tab="edit"]').click();
  $("#e-id").value = id;
  loadCampaign(id);
}

$("#e-open").addEventListener("click", () => loadCampaign($("#e-id").value));

async function loadCampaign(id) {
  const msg = $("#e-msg"), body = $("#e-body");
  msg.hidden = true;
  if (!id) return message(msg, "Введите ID кампании", "err");
  try {
    const c = await api("/api/campaigns/" + id);
    body.replaceChildren(
      el("h3", {}, `${c.name} (ID ${c.id})`),
      ...c.streams.map((s) => streamCard(c.id, s))
    );
  } catch (e) {
    body.replaceChildren();
    message(msg, e.message, "err");
  }
}

async function action(campaignId, fn) {
  try {
    await fn();
    await loadCampaign(campaignId);
  } catch (e) {
    message($("#e-msg"), e.message, "err");
  }
}

function streamCard(campaignId, s) {
  const card = el("div", { class: "stream" }, el("h3", {}, s.name),
    el("div", { class: "sub" }, s.filters || "Без фильтров"));

  if (!s.editable) {
    card.append(el("div", {}, "Редирект на ", el("b", {}, s.redirect_url || "—")));
    return card;
  }

  const sum = el("span", { class: "sum" });
  const save = el("button", { class: "primary" }, "Сохранить доли");
  const inputs = new Map();

  const recalc = () => {
    const total = [...inputs.values()].reduce((a, i) => a + (parseInt(i.value, 10) || 0), 0);
    sum.textContent = `Сумма: ${total}%`;
    sum.classList.toggle("bad", total !== 100);
    save.disabled = total !== 100;
  };

  const rows = s.offers.map((o) => {
    const inp = el("input", { type: "number", min: 0, max: 100, value: o.share });
    inp.addEventListener("input", recalc);
    inputs.set(o.offer_id, inp);
    return el("tr", {},
      el("td", {}, `[${o.offer_id}] ${o.name}`),
      el("td", { class: "num" }, inp, " %"),
      el("td", {}, el("button", {
        class: "danger",
        onclick: () => confirm(`Удалить оффер «${o.name}» из потока?`) &&
          action(campaignId, () => api(`/api/streams/${s.id}/offers/${o.offer_id}`, { method: "DELETE" })),
      }, "Удалить")));
  });

  card.append(el("table", {},
    el("thead", {}, el("tr", {}, el("th", {}, "Оффер"), el("th", {}, "Доля"), el("th", {}))),
    el("tbody", {}, rows)));

  save.addEventListener("click", () => {
    const shares = {};
    inputs.forEach((i, id) => (shares[id] = parseInt(i.value, 10) || 0));
    action(campaignId, () => api(`/api/streams/${s.id}/shares`, { method: "PUT", body: { shares } }));
  });
  card.append(el("div", { class: "actions" }, sum, save));
  recalc();

  const picker = offerPicker();
  card.append(el("label", {}, "Добавить оффер"), el("div", { class: "add-row" }, picker.root,
    el("button", {
      onclick: () => picker.offer
        ? action(campaignId, () => api(`/api/streams/${s.id}/offers`, { method: "POST", body: { offer_id: picker.offer.id } }))
        : message($("#e-msg"), "Выберите оффер из списка", "err"),
    }, "Добавить")));
  return card;
}
