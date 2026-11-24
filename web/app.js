import {blankLine, decimal, lineRow, loginView, money, pages, reportUrl, scaled, shell, view} from "./views.js";

const app = document.querySelector("#app");
const notice = document.querySelector("#notice");
const store = {
  get(key, fallback) {
    try { return JSON.parse(localStorage.getItem("batchbook:" + key)) ?? fallback; }
    catch { return fallback; }
  },
  set(key, value) {
    localStorage.setItem("batchbook:" + key, JSON.stringify(value));
  },
};

let state;
let page;
let ui;
let lineKey = 0;
let toastTimer;
let syncing = false;
const newLine = () => blankLine(++lineKey);

async function api(url, body) {
  const response = await fetch(url, body === undefined ? {} : {
    method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(body),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw Object.assign(new Error(result.error || "The factory server could not complete the request."), {status:response.status});
  }
  return result;
}

function toast(message) {
  notice.textContent = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { notice.textContent = ""; }, 4000);
}

function initialUi() {
  const isSales = state.user.role === "sales";
  return {
    orderLines:[newLine()], customer:"", queue:isSales ? store.get("queue:" + state.user.login,[]) : [],
    offline:false, queueError:"", orderFilter:"All",
    selectedOrder:0, selectedInvoice:0, selectedRun:0, showRun:false, showAdjustment:false,
    kind:"finished", masterId:0, recipeProduct:0, recipeLines:[],
    from:state.day.slice(0,8) + "01", to:state.day, reportKey:"sales", ledger:null,
  };
}

function print() {
  app.innerHTML = state ? shell(state,page,view(page,state,ui)) : loginView();
  if (state?.user.role === "sales") estimate();
}

function capture(form) {
  const list = [...form.querySelectorAll("[data-line]")].map(row => ({
    key:Number(row.dataset.line), item:row.querySelector('[name="item"]').value,
    unit:row.querySelector('[name="unit"]').value, quantity:row.querySelector('[name="quantity"]').value,
  }));
  if (form.dataset.form === "order") {
    ui.orderLines = list;
    ui.customer = form.elements.customer.value;
  } else {
    ui.recipeLines = list;
  }
  return list;
}

function estimate() {
  const label = document.querySelector("#estimate");
  const form = document.querySelector('[data-form="order"]');
  if (!label || !form) return;
  const lines = capture(form);
  let total = 0;
  for (const line of lines) {
    const item = state.items.find(i => i.id === Number(line.item));
    if (item) total += item.price * Number(line.quantity || 0) * (line.unit === "carton" ? item.carton : 1);
  }
  label.textContent = lines.some(l => l.item) ? "Estimated subtotal before GST · " + money(total) :
    "Estimated subtotal appears after you select products.";
}

function saveSalesSnapshot() {
  if (state.user.role !== "sales") return;
  try { store.set("sales-snapshot", state); }
  catch { /* Connected order entry still works when browser storage is unavailable. */ }
}

function saveQueue(queue) {
  store.set("queue:" + state.user.login, queue);
  ui.queue = queue;
}

async function refresh() {
  state = await api("/api/state");
  saveSalesSnapshot();
}

async function sync() {
  if (syncing || state?.user.role !== "sales") return;
  syncing = true;
  const login = state.user.login;
  try {
    for (const order of [...ui.queue]) {
      await api("/api/orders",order);
      if (state?.user.login !== login) return;
      saveQueue(ui.queue.filter(entry => entry.token !== order.token));
    }
    await refresh();
    ui.queueError = "";
    ui.offline = false;
  } catch (error) {
    if (state?.user.login !== login) return;
    ui.offline = !error.status || error.status >= 500;
    ui.queueError = error.status === 401 ? "Sign in as this salesperson to resume syncing." :
      error.status && !ui.offline ? error.message : "";
  } finally {
    syncing = false;
    if (state?.user.login === login) {
      const active = document.activeElement;
      const form = document.querySelector('[data-form="order"]');
      if (!form?.contains(active) || form.querySelector("button:disabled")) print();
      else toast(ui.queue.length ? "Orders are still waiting to sync." : "Orders are up to date.");
    }
  }
}

async function route() {
  if (!state) { print(); return; }
  const login = state.user.login;
  if (!ui.offline) {
    try {
      const updated = await api("/api/state");
      if (state?.user.login !== login) return;
      state = updated;
      saveSalesSnapshot();
    } catch {
      if (state?.user.login !== login) return;
    }
  }
  const choices = pages(state.user.role);
  const requested = location.hash.slice(1);
  page = Object.hasOwn(choices,requested) ? requested : Object.keys(choices)[0];
  print();
  window.scrollTo(0,0);
  if (page === "inventory" && state.user.role !== "owner") await ledger();
  if (page === "reports") {
    try { await loadReport(); } catch (error) { toast(error.message); }
  }
}

async function ledger() {
  try {
    ui.ledger = await api(reportUrl("ledger",ui.from,state.day));
    if (page === "inventory") print();
  } catch (error) { toast(error.message); }
}

async function loadReport() {
  const query = {key:ui.reportKey,from:ui.from,to:ui.to};
  const result = await api(reportUrl(query.key,query.from,query.to));
  ui.loaded = query;
  ui.reportData = result;
  if (page === "reports") print();
}

async function login(data) {
  await api("/api/login",data);
  await refresh();
  ui = initialUi();
  history.replaceState(null,"",location.pathname);
  await route();
  if (ui.queue.length) await sync();
}

async function post(path, data, message, after = () => {}) {
  const result = await api(path,data);
  await refresh();
  after(result);
  print();
  toast(message);
}

function go(target) {
  if (page === target) { print(); window.scrollTo(0,0); }
  else location.hash = target;
}

function loadRecipe(key) {
  ui.recipeProduct = key;
  ui.recipeLines = (state.recipes[key] || []).map(i => ({
    key:++lineKey, item:i.id, unit:i.unit, quantity:scaled(i.planned,i.unit),
  }));
  if (!ui.recipeLines.length) ui.recipeLines = [newLine()];
}

function restoreForm(name, values, excluded) {
  const form = document.querySelector(`[data-form="${name}"]`);
  for (const [k,v] of Object.entries(values)) {
    if (!excluded.includes(k) && form?.elements[k]) form.elements[k].value = v;
  }
}

function formData(form) {
  return Object.fromEntries(new FormData(form));
}

function valuesIn(form, selector) {
  return [...form.querySelectorAll(selector)].map(row => Object.fromEntries(
    [...row.querySelectorAll("input,select")].map(el => [el.name,el.value])));
}

function verifyAvailability() {
  const form = document.querySelector('[data-form="verify"]');
  if (!form) return;
  const short = [...form.querySelectorAll("[data-verify]")].map(row => ({
    name:row.querySelector("strong").textContent, available:Number(row.dataset.available),
    required:Number(row.querySelector('[name="quantity"]').value),
  })).filter(row => row.required > row.available);
  const box = document.querySelector("#availability");
  box.classList.toggle("warn",!!short.length);
  box.textContent = short.length ? short.map(l => `${l.name} is short by ${l.required-l.available} packets (${l.available} available).`).join(" ")
    + " Keep this order submitted until stock is replenished, or revise the quantities."
    : "Ready to approve. Available stock covers this order.";
}

app.addEventListener("change", event => {
  const input = event.target;
  const form = input.form;
  if (!form) return;
  if (input.hasAttribute("data-line-item")) {
    const name = form.dataset.form;
    const lines = capture(form);
    const row = input.closest("[data-line]");
    const model = lines.find(line => line.key === Number(row.dataset.line));
    model.unit = state.items.find(i => i.id === Number(input.value))?.unit || (input.value ? "packet" : "");
    row.outerHTML = lineRow(name,model,state);
    form.querySelector(`[data-line="${model.key}"] select[name="item"]`)?.focus();
    if (name === "order") estimate();
  }
  if (input.hasAttribute("data-purchase-item") || input.hasAttribute("data-adjust-item")) {
    const isPurchase = input.hasAttribute("data-purchase-item");
    const saved = formData(form);
    ui[isPurchase ? "purchaseItem" : "adjustItem"] = Number(input.value);
    print();
    restoreForm(form.dataset.form,saved,["item","unit"]);
    document.querySelector(`[data-form="${form.dataset.form}"] [name="item"]`)?.focus();
  }
  if (input.hasAttribute("data-run-product")) { ui.runProduct = Number(input.value); print(); }
  if (input.hasAttribute("data-recipe-product")) { loadRecipe(Number(input.value)); print(); }
});

app.addEventListener("input", event => {
  const input = event.target;
  const kind = input.form?.dataset.form;
  if (kind === "order") estimate();
  if (kind === "verify" && input.name === "quantity") verifyAvailability();
  if (kind === "run" && input.name === "batches") {
    const product = state.items.find(i => i.id === Number(input.form.elements.product.value));
    document.querySelector("#expected").textContent = product.yield * Number(input.value);
    for (const row of input.form.querySelectorAll("[data-material]")) {
      const item = state.items.find(i => i.id === Number(row.dataset.material));
      row.querySelector("[data-planned]").textContent = `${+(Number(row.dataset.plan) * Number(input.value)).toFixed(3)} ${item.unit}`;
    }
  }
});

app.addEventListener("click", async event => {
  const el = event.target.closest("[data-action]");
  if (!el) return;
  const action = el.dataset.action;
  const value = el.dataset.value;
  const id = Number(value);
  try {
    if (action === "demo-login") {
      const form = app.querySelector("form");
      form.elements.login.value = value;
      form.elements.password.value = "batchbook-demo";
      form.elements.login.focus();
    } else if (action === "menu") {
      const open = document.querySelector(".sidebar").classList.toggle("open");
      el.setAttribute("aria-expanded",String(open));
    } else if (action === "logout") {
      if (syncing) { toast("Wait for order sync to finish."); return; }
      if (!ui.offline) await api("/api/logout",{});
      store.set("sales-snapshot",null);
      state = null;
      history.replaceState(null,"",location.pathname);
      print();
    } else if (action === "add-line" || action === "remove-line") {
      const form = el.form;
      const name = form.dataset.form;
      let lines = capture(form);
      if (action === "add-line") lines.push(newLine());
      else lines = lines.filter(line => line.key !== id);
      if (!lines.length) lines.push(newLine());
      ui[name === "order" ? "orderLines" : "recipeLines"] = lines;
      const list = form.querySelector(".form-list");
      list.innerHTML = lines.map(line => lineRow(name,line,state)).join("");
      if (action === "add-line") list.lastElementChild.querySelector("select")?.focus();
      if (name === "order") estimate();
    } else if (action === "sync") {
      await sync();
    } else if (action === "drop-queued") {
      if (syncing) return;
      saveQueue(ui.queue.filter(entry => entry.token !== value)); print();
    } else if (action === "open-order") {
      ui.selectedOrder = id; go("orders");
    } else if (action === "refresh-orders") {
      await refresh();
      ui.selectedOrder = 0;
      print();
      toast("Order desk refreshed.");
    } else if (action === "order-filter") {
      ui.orderFilter = value; ui.selectedOrder = 0; print();
    } else if (action === "open-invoice") {
      ui.selectedInvoice = id; go("billing");
    } else if (action === "invoice") {
      el.disabled = true;
      await post(`/api/orders/${id}/invoice`,{},"GST invoice posted.",r => { ui.selectedInvoice = r.id; });
      go("billing");
    } else if (action === "dispatch") {
      el.disabled = true;
      await post(`/api/invoices/${id}/dispatch`,{},"Dispatch posted. Finished stock updated.");
    } else if (action === "toggle-run") {
      ui.showRun = !ui.showRun; ui.selectedRun = 0; print();
    } else if (action === "open-run") {
      ui.selectedRun = id; ui.showRun = false; go("production");
    } else if (action === "toggle-adjust") {
      ui.showAdjustment = !ui.showAdjustment; print();
    } else if (action === "set-kind") {
      ui.kind = value; ui.masterId = 0;
      if (value === "recipe") loadRecipe(state.items.find(i => i.kind === "finished")?.id || 0);
      print();
    } else if (action === "edit-master") {
      ui.masterId = id; go("masters");
    }
  } catch (error) {
    toast(error.message);
    el.disabled = false;
  }
});

app.addEventListener("submit", async event => {
  if (!event.target.matches("[data-form]")) return;
  event.preventDefault();
  const form = event.target;
  const kind = form.dataset.form;
  const id = Number(form.dataset.id);
  const data = formData(form);
  const action = event.submitter?.value;
  const errorLabel = form.querySelector(".form-error");
  errorLabel.hidden = true;
  const buttons = [...form.querySelectorAll("button")];
  buttons.forEach(button => { button.disabled = true; });
  try {
    if (kind === "login") {
      await login(data);
    } else if (kind === "order") {
      const token = crypto.randomUUID();
      const order = {customer:data.customer, token, lines:valuesIn(form,"[data-line]")};
      try {
        await api("/api/orders",order);
      } catch (error) {
        if (error.status && error.status < 500) throw error;
        saveQueue([...ui.queue,order]);
        ui.offline = true;
      }
      ui.orderLines = [newLine()]; ui.customer = "";
      if (!ui.offline) {
        try { await refresh(); } catch { ui.offline = true; }
      }
      print();
      toast(ui.queue.some(entry => entry.token === token) ? "Order queued on this device." : "Order submitted to the factory.");
    } else if (kind === "verify") {
      const lines = valuesIn(form,"[data-verify]").map((line,index) => ({
        ...line,item:form.querySelectorAll("[data-verify]")[index].dataset.verify,
      }));
      await post(`/api/orders/${id}/verify`,
        {action:action || "approve",reason:data.reason,lines},action === "reject" ? "Order rejected." : action === "save" ? "Order changes saved." : "Order approved. Stock reserved.");
    } else if (kind === "purchase") {
      await post("/api/purchases",data,"Purchase receipt posted. Stock updated.",() => { ui.purchaseItem = 0; });
    } else if (kind === "run") {
      const consumption = Object.fromEntries(valuesIn(form,"[data-material]").map((value,index) =>
        [form.querySelectorAll("[data-material]")[index].dataset.material,value]));
      await post("/api/runs",{...data,consumption},"Production posted. Stock and variances updated.",r => {
        ui.selectedRun = r.id; ui.showRun = false;
      });
    } else if (kind === "overheads") {
      await post(`/api/runs/${id}/overheads`,data,"Overheads saved. Unit cost updated.");
    } else if (kind === "payment") {
      await post(`/api/invoices/${id}/payment`,data,"Payment recorded.");
    } else if (kind === "credit") {
      await post(`/api/invoices/${id}/credit`,data,"Credit note issued.");
    } else if (kind === "report") {
      ui.reportKey = data.key; ui.from = data.from; ui.to = data.to;
      await loadReport();
    } else if (kind === "master") {
      await post("/api/masters",{...data,kind:ui.kind,id},"Master record saved.",() => { ui.masterId = 0; });
    } else if (kind === "recipe") {
      await post(`/api/masters/${ui.recipeProduct}/recipe`,{lines:valuesIn(form,"[data-line]")},"Recipe saved.",() => loadRecipe(ui.recipeProduct));
    } else if (kind === "adjust") {
      await post("/api/adjustments",data,"Stock adjustment posted.",() => { ui.showAdjustment = false; ui.adjustItem = 0; });
      await ledger();
    }
  } catch (error) {
    errorLabel.textContent = error.message;
    errorLabel.hidden = false;
    errorLabel.scrollIntoView({block:"nearest"});
  } finally { buttons.forEach(button => { button.disabled = false; }); }
});

window.addEventListener("hashchange",route);
window.addEventListener("online",sync);
window.addEventListener("offline",() => {
  if (state?.user.role === "sales") {
    ui.offline = true;
    toast("Offline. New orders will queue on this device.");
  }
});
document.addEventListener("visibilitychange",() => {
  if (document.visibilityState === "visible" && ui?.queue.length) sync();
});
setInterval(() => { if (ui?.queue.length && navigator.onLine) sync(); },15000);

async function start() {
  try { await refresh(); }
  catch (error) {
    if (!error.status) state = store.get("sales-snapshot",null);
    if (!state) { print(); return; }
    ui = initialUi();
    ui.offline = true;
    await route();
    return;
  }
  ui = initialUi();
  await route();
  if (ui.queue.length) await sync();
}

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
start();
