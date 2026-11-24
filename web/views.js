export const esc = value => String(value ?? "").replace(/[&<>"']/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
export const money = n => new Intl.NumberFormat("en-IN", {style:"currency",currency:"INR"}).format(n / 100);
export const decimal = n => (n / 100).toFixed(2);
export const scaled = (n, unit) => ["kg","L"].includes(unit) ? n / 1000 : n;
const qty = (n, unit) => `${scaled(n,unit)} ${unit === "packet" && n !== 1 ? "packets" : unit}`;
const percent = (n, sign = false) => `${sign && n > 0 ? "+" : ""}${n / 100}%`;
const code = (prefix,id) => `${prefix}-${String(id).padStart(4,"0")}`;
const roleNames = {admin:"Factory admin",production:"Production",sales:"Field sales",auditor:"Auditor",owner:"Owner"};

const icons = {
  overview:'<path d="M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z"/>',
  orders:'<path d="M7 7h13l-2 10H6L3 4H1m6 17h1m9 0h1"/>',
  production:'<path d="M3 21V9l6 4V9l6 4V4h4l2 17zM7 17h1m4 0h1m4 0h1"/>',
  purchases:'<path d="M4 8h16v12H4zM3 8l3-4h12l3 4m-9 0v7m-3-3 3 3 3-3"/>',
  inventory:'<path d="m12 3 9 5v9l-9 5-9-5V8zm0 9 9-4M3 8l9 4v10m-5-12 9-5"/>',
  billing:'<path d="M5 3h14v18l-3-2-4 2-4-2-3 2zM8 8h8m-8 4h8m-8 4h5"/>',
  reports:'<path d="M4 3h16v18H4zM8 16v-3m4 3V9m4 7V6"/>',
  masters:'<path d="M4 5h16M4 12h16M4 19h16M8 3v4m8 3v4m-6 3v4"/>',
};
const icon = key => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true">${icons[key] || icons.orders}</svg>`;
const brand = `<div class="brand"><svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><path d="M16 3a13 13 0 1 1-9 3.6M16 8a8 8 0 1 1-8 8c0-1.7.5-3.1 1.5-4.4M16 13a3 3 0 1 1-2.7 4.3"/><path d="M5 4l3 2.6L5 9"/></svg>Batchbook</div>`;
const nav = {
  admin: {overview:"Overview",orders:"Order desk",billing:"Billing",production:"Production runs",purchases:"Purchases",
    inventory:"Stock & ledger",reports:"Audit reports",masters:"Master data"},
  production: {production:"Production runs",purchases:"Purchases",inventory:"Stock & ledger"},
  sales: {orders:"My orders"}, auditor:{reports:"Audit reports"}, owner:{overview:"Overview",inventory:"Stock",reports:"Audit reports"}
};
export const pages = role => nav[role];
export const pageStart = (title, description, action = "", context = "") => `<header class="page-head"><div>
  ${context ? `<p class="context">${esc(context)}</p>` : ""}<h1>${title}</h1>${description ? `<p>${description}</p>` : ""}</div>${action}</header>`;
const panel = (title, body) => `<section class="panel">${title ? `<h2>${title}</h2>` : ""}${body}</section>`;
const empty = text => `<p class="empty">${esc(text)}</p>`;
const pill = (text, color = "") => `<span class="pill ${color}">${esc(text)}</span>`;
const status = value => pill(value, ({Submitted:"warn",Rejected:"bad",Cancelled:"bad",Approved:"good",Dispatched:"good"})[value] || "");
export const button = (text, action, value = "", cls = "") =>
  `<button type="button" class="${cls}" data-action="${action}" data-value="${esc(value)}">${esc(text)}</button>`;
const submit = (text, value = "", cls = "primary") => `<button class="${cls}" type="submit" value="${value}">${text}</button>`;
const link = (text, href, extra = "") => `<a class="button" href="${esc(href)}" ${extra}>${esc(text)}</a>`;
const table = (heads, data, message = "No entries in this period.", numeric = [], cls = "") => data.length
  ? `<div class="table-scroll ${cls}"><table><thead><tr>${heads.map((h,i) => `<th scope="col" class="${numeric.includes(i) ? "numeric" : ""}">${esc(h)}</th>`).join("")}</tr></thead>
    <tbody>${data.map(row => `<tr>${row.map((v,i) => `<td class="${numeric.includes(i) ? "numeric" : ""}">${v}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`
  : empty(message);
const metrics = data => `<div class="metrics">${data.map(([label,value,detail,tone]) => `<div class="metric">
  <small>${label}</small><strong class="${tone || ""}">${value}</strong>${detail ? `<small>${detail}</small>` : ""}</div>`).join("")}</div>`;
const field = (label, name, value = "", options = "") =>
  `<label>${label}<input aria-label="${esc(label)}" name="${name}" value="${esc(value)}" ${options}></label>`;
const number = (label,name,value = "",step = "1",min = "0") =>
  field(label,name,value,`type="number" step="${step}" min="${min}" required`);
const select = (label,name,options,value = "",extra = "") => `<label>${label}<select aria-label="${esc(label)}" name="${name}" required ${extra}>
  ${options.map(([key,title]) => `<option value="${esc(key)}" ${String(key) === String(value) ? "selected" : ""}>${esc(title)}</option>`).join("")}</select></label>`;
const itemOptions = items => [["","Choose an item"], ...items.map(i => [i.id,i.name])];
const unitOptions = item => ({kg:[["kg","kg"],["g","g"]],L:[["L","L"],["ml","ml"]],piece:[["piece","piece"]],
  packet:[["packet","packets"],["carton",`cartons of ${item?.carton}`]]})[item?.unit] || [["","Choose item first"]];
const form = (name, body, action, id) => `<form data-form="${name}" ${id ? `data-id="${id}"` : ""}>${body}
  <p role="alert" class="form-error" hidden></p><div class="actions">${action}</div></form>`;
const grid = body => `<div class="form-grid">${body}</div>`;
const rowsOf = (formName, state) => state.items?.filter(i => formName === "order" ? i.kind === "finished" || state.user.role === "sales" : i.kind !== "finished") || [];
export const blankLine = key => ({key,item:"",unit:"",quantity:""});

export function lineRow(kind, row, state) {
  const items = rowsOf(kind,state);
  const item = items.find(i => String(i.id) === String(row.item));
  return `<div class="form-line" data-line="${row.key}">
    ${select(kind === "order" ? "Product" : "Component","item",itemOptions(items),row.item,"data-line-item")}
    ${number("Quantity","quantity",row.quantity,["kg","L"].includes(item?.unit) ? ".001" : "1",["kg","L"].includes(item?.unit) ? ".001" : "1")}
    ${select("Unit","unit",unitOptions(item && {...item,unit:item.unit || "packet"}),row.unit)}
    <button type="button" aria-label="Remove line" data-action="remove-line" data-value="${row.key}">×</button>
  </div>`;
}

export function loginView() {
  const accounts = [
    ["sales-a","Salesman A","Field sales"],["sales-b","Salesman B","Field sales"],["production","Production supervisor","Factory floor"],
    ["admin","Factory admin","Order desk"],["auditor","External auditor","Read-only"],["owner","Factory owner","Read-only"]
  ];
  return `<main class="login"><div class="login-top">${brand}<p class="muted">Food factory operations · Tiruchirappalli</p></div>
    <div class="login-grid">
      ${panel("",`<h1>Sign in</h1><p class="muted">Open your factory workspace.</p>
      ${form("login",`<div class="login-form">
        ${field("Username","login","","required autocomplete=username")}${field("Password","password","","type=password required autocomplete=current-password")}
        </div>`,submit("Sign in"))}`)}
      ${panel("Benchmark accounts",`<p class="muted">Select an account to fill its test credentials.</p>
        <div class="quick">${accounts.map(([login,name,role]) => `<button type="button" aria-label="${name}" data-action="demo-login" data-value="${login}">
          <span>${name}</span><small>${role}</small></button>`).join("")}</div>`)}
    </div></main>`;
}

export function shell(state, page, html) {
  const u = state.user;
  return `<div class="shell"><div class="mobile-bar">${brand}${button("Menu","menu")}</div>
    <aside class="sidebar" aria-label="Workspace navigation">${brand}<small class="scope">Tiruchirappalli factory</small>
    <nav class="nav">${Object.entries(nav[u.role]).map(([id,label]) => `<a href="#${id}" ${page === id ? 'aria-current="page"' : ""}>
      ${icon(id)}${label}</a>`).join("")}</nav>
    <div class="account"><span class="avatar" aria-hidden="true">${esc(u.name[0])}</span><div><strong>${esc(u.name)}</strong><br>
      <small>${roleNames[u.role]}</small></div>${button("Sign out","logout")}</div></aside>
    <main id="main">${html}</main></div>`;
}

function overview(state) {
  const todays = state.orders.filter(o => o.day === state.day);
  const flagged = state.runs.filter(r => r.flag || r.lines.some(l => l.flag));
  const latestByProduct = [...new Map([...state.runs].reverse().map(r => [r.product,r])).values()];
  const finished = state.items.filter(i => i.kind === "finished");
  const low = state.items.filter(i => i.kind !== "finished" && i.balance < i.reorder);
  const stock = finished.reduce((sum,i) => sum + i.balance,0);
  const due = state.outstanding ?? state.invoices.reduce((sum,i) => sum + i.outstanding,0);
  const active = ["Submitted","Approved","Invoiced","Dispatched"].map(k => [k,todays.filter(o => o.status === k).length]);
  const max = Math.max(1,...active.map(([,n]) => n));
  const flow = `<div class="flow">${active.map(([label,n]) => `<div><span>${label}</span>
    <div class="track" aria-hidden="true"><span style="width:${n/max*100}%"></span></div><strong>${n}</strong></div>`).join("")}</div>`;
  return pageStart("Factory overview","Orders, stock and production at the Tiruchirappalli factory.",
    state.user.role === "admin" ? link("Open order desk","#orders") : link("Open audit reports","#reports"),
    new Date(state.day + "T12:00:00").toLocaleDateString("en-IN",{dateStyle:"long"})) +
    metrics([["Today's orders",todays.length],["Finished stock",stock,"Packets on hand"],["Runs to review",flagged.length,"Beyond recipe tolerance"],
      ["Outstanding dues",money(due)]]) +
    `<div class="grid two">${panel("Today's order pipeline",flow)}${panel("Stock to reorder",table(["Material","On hand","Reorder level"],
      low.map(i => [esc(i.name),qty(i.balance,i.unit),qty(i.reorder,i.unit)]),"Raw material and packaging balances are above reorder levels.",[1,2]))}
    ${panel("Latest cost per product",table(["Product","Run","Cost per pack","Margin per pack"],latestByProduct.map(r => [esc(r.name),
      code("RUN",r.id),r.unitCost == null ? "—" : money(r.unitCost),r.margin == null ? "—" : money(r.margin)]),"Post a production run to see unit cost.",[2,3]))}
    ${panel("Variance alerts",table(["Run","Measure","Variance"],flagged.flatMap(r => [
      ...(r.flag ? [[code("RUN",r.id),esc(r.name) + " yield",pill(percent(r.variance,true),"warn")]] : []),
      ...r.lines.filter(l => l.flag).map(l => [code("RUN",r.id),esc(l.name),pill(percent(l.variance,true),"warn")])
    ]).slice(0,10),"No runs need variance review.",[2]))}</div>`;
}

function sales(state, ui) {
  const customers = state.customers.map(c => [c.id,`${c.name} · ${c.state}`]);
  const totals = new Map();
  for (const order of state.orders.filter(o => ["Invoiced","Dispatched"].includes(o.status))) {
    totals.set(order.customer,(totals.get(order.customer) || 0) + order.net);
  }
  const orders = state.orders.map(o => [`<strong>${code("ORD",o.id)}</strong><small>${esc(o.day)}</small>`,esc(o.customer),
    o.lines.map(l => `${l.quantity} × ${esc(l.name)}`).join("<br>"),money(o.net),status(o.status)]);
  const queue = ui.queue.length || ui.offline ? `<div class="callout ${ui.offline ? "warn" : ""}">${ui.offline ? "Offline. New orders are saved on this device." : "Orders saved on this device."}
    ${ui.queue.length ? `${ui.queue.length} waiting to sync. ${button("Sync now","sync","","inline")}` : ""}
    ${ui.queueError ? `<p>${esc(ui.queueError)}</p>` : ""}
    ${ui.queue.map(q => `<div class="details"><small>${esc(state.customers.find(c => c.id == q.customer)?.name || "Customer")} ·
     ${q.lines.map(l => `${esc(l.quantity)} ${esc(l.unit)}`).join(", ")}</small>${button("Remove queued order","drop-queued",q.token,"inline")}</div>`).join("")}</div>` : "";
  return pageStart("My orders","Take retail and distributor orders on your route.") + queue +
    panel("New order",form("order",
      select("Customer","customer",[["","Choose a customer"],...customers],ui.customer) +
      `<div class="form-list">${ui.orderLines.map(r => lineRow("order",r,state)).join("")}</div>
      <p class="muted" id="estimate">Estimated subtotal appears after you select products.</p>`,
      button("Add product","add-line","order") + submit("Submit order"))) +
    panel("Order history",table(["Order","Customer","Products","Subtotal","Status"],orders,"You haven’t submitted any orders.",[3],"sales-table") +
      (orders.length ? `<div class="sales-cards">${orders.map(r => `<article class="sales-card"><div><span>${r[0]}</span>${r[4]}</div>
        <strong>${r[1]}</strong><div><small>${r[2]}</small><strong>${r[3]}</strong></div></article>`).join("")}</div>` : "")) +
    panel("Customer-wise sales",table(["Customer","Invoiced sales before GST"],[...totals].map(([c,n]) => [esc(c),money(n)]),
      "Sales appear here once the factory invoices your orders.",[1]));
}

function orderDesk(state, ui) {
  const order = state.orders.find(o => o.id === ui.selectedOrder);
  const filters = ["All","Submitted","Approved","Invoiced","Dispatched","Rejected","Cancelled"];
  const visible = state.orders.filter(o => ui.orderFilter === "All" || o.status === ui.orderFilter);
  let detail = "";
  if (order) {
    const check = order.lines.filter(l => l.available !== undefined && l.quantity > l.available);
    const supply = order.code === "33" ? "CGST + SGST" : "IGST";
    const stock = check.length ? `<div class="callout warn" id="availability">${check.map(l =>
      `${esc(l.name)} is short by <strong>${l.quantity-l.available} packets</strong> (${l.available} available).`).join(" ")}
      Keep this order submitted until stock is replenished, or revise the quantities.</div>`
      : order.status === "Submitted" ? `<div class="callout" id="availability">Ready to approve. Available stock covers this order.</div>` : "";
    const fields = order.lines.map(l => `<div class="form-line verify" data-verify="${l.item}" data-available="${l.available}">
      <strong>${esc(l.name)}</strong>${number("Packets","quantity",l.quantity,"1","1")}${number("Price / pack (₹)","price",decimal(l.price),".01")}
      <small>${l.available} packets available</small></div>`).join("");
    const edit = order.status === "Submitted" ? form("verify",stock + fields +
      `<details><summary>Reject order</summary>${field("Rejection reason","reason", "", "maxlength=120")}${submit("Reject order","reject","danger")}</details>`,
      submit("Approve order","approve") + submit("Save edits","save",""),order.id)
      : order.status === "Approved" ? button("Raise GST invoice","invoice",order.id,"primary")
      : order.invoice ? button("Open invoice","open-invoice",order.invoice) : "";
    detail = panel("",`<div class="panel-head"><h2>${code("ORD",order.id)} · ${esc(order.customer)}</h2>${status(order.status)}</div>
      <div class="details"><small>${esc(order.salesman)} · ${esc(order.day)}</small><small>Place of supply ${esc(order.state)} · ${supply}</small><small>${esc(order.gstin || "Unregistered")}</small></div>
      ${order.status === "Submitted" ? "" : table(["Product","Packets","Price per pack"],order.lines.map(l => [esc(l.name),l.quantity,money(l.price)]),"",[1,2])}
      ${edit}`);
  }
  return pageStart("Order desk","Verify incoming orders, reserve stock and raise GST invoices.",
    button("Refresh orders","refresh-orders")) + detail +
    panel("",`<div class="panel-head"><h2>Incoming orders</h2><small>${visible.length} orders</small></div>
      <div class="section-links" aria-label="Filter orders">${filters.map(k => `<button data-action="order-filter" data-value="${k}"
        aria-pressed="${ui.orderFilter === k}">${k}</button>`).join("")}</div><br>
      ${table(["Order","Customer","Salesman","Subtotal","Status",""],visible.map(o => [
        `<strong>${code("ORD",o.id)}</strong><small>${esc(o.day)}</small>`,`${esc(o.customer)}<small>${esc(o.state)}</small>`,
        esc(o.salesman),money(o.net),status(o.status),button("Review","open-order",o.id,"inline")
      ]),"No orders in this view.",[3])}`);
}

function billing(state, ui) {
  const inv = state.invoices.find(i => i.id === ui.selectedInvoice);
  let detail = "";
  if (inv) {
    const pdf = `/api/invoices/${inv.id}/invoice.pdf`;
    const email = `mailto:${inv.email || ""}?subject=${encodeURIComponent("Invoice " + inv.number)}&body=${encodeURIComponent(
      `Hello ${inv.name},\n\nPlease find invoice ${inv.number} attached.\n\nBatchbook Foods`)}`;
    const payment = inv.outstanding > 0 ? form("payment",grid(number("Amount (₹)","amount","",".01",".01") +
      select("Mode","mode",[["Cash","Cash"],["UPI","UPI"],["Bank transfer","Bank transfer"],["Cheque","Cheque"]]) +
      field("Payment reference","reference","","required maxlength=120")),submit("Record payment"),inv.id) : "";
    const credit = !inv.credit && !inv.dispatched && !inv.paid ?
      `<details><summary>Cancel with credit note</summary>${form("credit",field("Reason for credit note","reason","","required maxlength=120"),
        submit("Issue credit note","","danger"),inv.id)}</details>` : "";
    detail = panel("",`<div class="panel-head"><h2>${esc(inv.number)} · ${esc(inv.name)}</h2>
      <div class="actions">${link("Download invoice PDF",pdf)}${link("Preview PDF",pdf+"?view=1",'target="_blank" rel="noopener"')}
      ${link("Email invoice",email,'title="Attach the downloaded PDF to the email"')}</div></div>
      <div class="details"><small>Issued ${inv.day} · Due ${inv.due}</small><small>Place of supply ${esc(inv.state)} (${inv.code})</small>
      <small>GSTIN ${esc(inv.gstin || "Unregistered")}</small></div>
      ${metrics([["Taxable",money(inv.net)],["CGST",money(inv.cgst)],["SGST",money(inv.sgst)],["IGST",money(inv.igst)],
        ["Invoice total",money(inv.total)],["Outstanding",money(inv.outstanding)]])}
      ${table(["Product","HSN","Packets","Rate / pack","Taxable","GST"],inv.lines.map(l => [esc(l.description),esc(l.hsn),l.quantity,
        money(l.price),money(l.net),percent(l.rate)]),"",[2,3,4,5])}
      ${inv.credit ? `<div class="callout warn">Cancelled via ${esc(inv.credit)} · ${esc(inv.creditReason)}
        ${link("Download credit note",`/api/invoices/${inv.id}/credit.pdf`)}</div>` : ""}
      ${!inv.credit && !inv.dispatched ? `<div class="actions"><p class="muted">Awaiting dispatch</p>
        ${button("Record dispatch","dispatch",inv.id,"primary")}</div>` : inv.dispatched ? `<p class="callout">Dispatched on ${inv.dispatched} · Finished stock updated.</p>` : ""}
      ${credit}`) + panel("Collections",`<p class="muted">Received ${money(inv.paid)} · Outstanding ${money(inv.outstanding)}</p>
      ${table(["Date","Mode","Reference","Amount"],inv.payments.map(p => [p.day,esc(p.mode),esc(p.reference),money(p.amount)]),"No payments recorded.",[3])}
      ${payment}`);
  }
  return pageStart("Billing","Download tax invoices, dispatch orders and track payments.") + detail +
    panel("Invoice register",table(["Invoice","Customer","Dispatch","Total","Outstanding",""],state.invoices.map(i => [
      `<strong>${esc(i.number)}</strong><small>${i.day}</small>`,esc(i.name),
      i.credit ? pill("Cancelled","bad") : i.dispatched ? pill("Dispatched","good") : pill("Awaiting dispatch","warn"),
      money(i.total),money(i.outstanding),button("Open","open-invoice",i.id,"inline")
    ]),"Approve and invoice an order to start billing.",[3,4]));
}

function production(state, ui) {
  const products = state.items.filter(i => i.kind === "finished" && state.recipes[i.id]?.length);
  const product = products.find(i => i.id === ui.runProduct) || products[0];
  const recipe = product ? state.recipes[product.id] : [];
  const active = state.runs.find(r => r.id === ui.selectedRun);
  const varianceBadge = (n, flag) => flag ? pill(percent(n,true) + " · Review","warn") : percent(n,true);
  const runDetail = active ? panel("",`<div class="panel-head"><h2>${code("RUN",active.id)} · ${esc(active.name)}</h2>
      <small>${active.day} · Tolerance ±${percent(active.tolerance)}</small></div>
      ${metrics([["Expected yield",`${active.expected} packets`],["Actual yield",`${active.output} packets`],
       ["Yield variance",percent(active.variance,true),active.flag ? "Outside tolerance" : "Within tolerance",active.flag ? "warn" : ""],
       ["Cost per packet",active.unitCost === null ? "—" : money(active.unitCost)],["Margin per packet",active.margin === null ? "—" : money(active.margin)]])}
      ${table(["Component","Planned","Actual issued","Scrap","Variance","Cost"],active.lines.map(l => [esc(l.name),
        qty(l.planned,l.unit),qty(l.actual,l.unit),qty(l.scrap,l.unit),varianceBadge(l.variance,l.flag),money(l.value)]),"",[1,2,3,4,5])}
      ${active.note ? `<p class="callout">${esc(active.note)}</p>` : ""}
      <p class="callout">Weighted average materials ${money(active.materials)} · Packaging ${money(active.packaging)}
        · Direct run overhead ${money(active.labour+active.utilities+active.other)} · Total run cost <strong>${money(active.total)}</strong></p>
      ${form("overheads",grid(number("Labour (₹)","labour",decimal(active.labour),".01") +
        number("Gas and power (₹)","utilities",decimal(active.utilities),".01") + number("Other overhead (₹)","other",decimal(active.other),".01") +
        `<input type="hidden" name="revision" value="${active.revision}">`),submit("Save overheads"),active.id)}`) : "";
  const runForm = product ? form("run",grid(
    select("Product","product",products.map(i => [i.id,i.name]),product.id,"data-run-product") +
    number("Recipe batches","batches","1","1","1") + number("Actual good output","output") +
    select("Output unit","outputUnit",unitOptions(product),"packet") +
    field("Run note","note","","maxlength=240") + `<p class="muted">Expected <strong id="expected">${product.yield}</strong> good packets</p>`) +
    `<div class="form-list">${recipe.map(l => `<div class="materials" data-material="${l.id}" data-plan="${scaled(l.planned,l.unit)}">
      <strong>${esc(l.name)}<small>On hand ${qty(state.items.find(i => i.id === l.id).balance,l.unit)}</small></strong>
      <small><span data-planned>${qty(l.planned,l.unit)}</span> planned</small>
      ${number("Used","used","",["kg","L"].includes(l.unit) ? ".001" : "1")}
      ${number("Scrap","scrap","0",["kg","L"].includes(l.unit) ? ".001" : "1")}
      ${select("Unit","unit",unitOptions(l),l.unit)}</div>`).join("")}</div>
      <p class="muted">Enter good-use quantities and additional scrap. Both are deducted from stock.</p>`,
    submit("Post production run") + button("Close","toggle-run")) : empty("Configure a product recipe in Master data first.");
  const demand = (state.pendingDemand || []).map(i => {
    const short = Math.max(0,i.demand - state.items.find(item => item.id === i.id).balance);
    return [esc(i.name),i.demand,short,i.yield ? Math.ceil(short/i.yield) : "Set recipe"];
  });
  return pageStart("Production runs","Post recipe use, reconcile yields, and calculate cost per good packet.",
    ui.showRun ? "" : button("New production run","toggle-run","","primary")) +
    (ui.showRun ? panel("New production run",runForm) : "") + runDetail +
    panel("Run history",table(["Run","Product","Expected","Good output","Yield variance","Cost per packet",""],state.runs.map(r => [
      `<strong>${code("RUN",r.id)}</strong><small>${r.day}</small>`,esc(r.name),r.expected,r.output,varianceBadge(r.variance,r.flag),
      r.unitCost == null ? "—" : money(r.unitCost),button("Open","open-run",r.id,"inline")
    ]),"No production runs have been posted.",[2,3,4,5])) +
    (state.pendingDemand ? panel("Planning from pending orders",table(["Product","Pending packets","Additional packets needed","Suggested batches"],
      demand,"There is no pending order demand.",[1,2,3])) : "");
}

function purchases(state, ui) {
  const materials = state.items.filter(i => i.kind !== "finished");
  const item = materials.find(i => i.id === ui.purchaseItem);
  return pageStart("Purchases","Receive raw materials and packaging against supplier bills.") +
    panel("Record purchase receipt",form("purchase",grid(
      select("Supplier","supplier",[["","Choose supplier"],...state.suppliers.map(s => [s.id,s.name])]) +
      field("Supplier bill","bill","","required maxlength=120") +
      select("Material","item",itemOptions(materials),item?.id,"data-purchase-item") +
      number("Received quantity","quantity","",item?.unit === "piece" ? "1" : ".001",item?.unit === "piece" ? "1" : ".001") +
      select("Receipt unit","unit",unitOptions(item),item?.unit) +
      number(item ? `Rate per ${item.unit} (₹)` : "Rate per stock unit (₹)","rate","",".01",".01") +
      number("Purchase GST amount (₹)","tax","0",".01")),submit("Post purchase receipt"))) +
    panel("Purchase register",table(["Receipt","Supplier","Supplier bill","Material","Received","Unit rate","Taxable"],
      state.purchases.map(p => [`<strong>${code("PUR",p.id)}</strong><small>${p.day}</small>`,esc(p.supplier_name),
        esc(p.bill),esc(p.name),qty(p.quantity,p.unit),money(p.rate),money(p.net)]),"No receipts recorded.",[4,5,6]));
}

function inventory(state, ui) {
  const item = state.items.find(i => i.id === ui.adjustItem);
  const rows = state.items.map(i => [`<strong>${esc(i.name)}</strong><small>${esc(i.sku)}</small>`,qty(i.balance,i.unit),qty(i.reorder,i.unit),
    i.balance < i.reorder ? pill("Low stock","warn") : pill("In stock","good")]);
  let adjust = "";
  if (ui.showAdjustment) adjust = panel("Record stock adjustment",form("adjust",grid(
    select("Item","item",itemOptions(state.items),item?.id,"data-adjust-item") +
    select("Direction","direction",[["Increase","Increase"],["Decrease","Decrease"]]) +
    number("Quantity","quantity","",["kg","L"].includes(item?.unit) ? ".001" : "1",["kg","L"].includes(item?.unit) ? ".001" : "1") +
    select("Unit","unit",unitOptions(item),item?.unit) +
    number("Rate per stock unit (₹)","rate","0",".01") +
    field("Reason","reason","","required maxlength=240")),submit("Post adjustment") + button("Close","toggle-adjust")));
  return pageStart("Stock & ledger","Balances come from posted receipts, production, dispatch and adjustments.",
    state.user.role === "admin" ? button("Stock adjustment","toggle-adjust") : "") + adjust +
    ["finished","raw","packaging"].map((kind,index) => panel(
      ["Finished goods","Raw materials","Packaging"][index],table(["Item","On hand","Reorder level","Stock status"],
        rows.filter((_,i) => state.items[i].kind === kind),"No items in this category.",[1,2]))).join("") +
    (state.user.role === "owner" ? "" : panel("Stock movement ledger",
      ui.ledger ? reportTable(ui.ledger) : empty("Loading stock movements…")));
}

export const reportUrl = (key, from, to, format = "") => `/api/reports/${key}?${new URLSearchParams({from,to,...(format ? {format} : {})})}`;
function reportTable(data) {
  return table(data.headings,data.rows.map(row => row.map(v => v === "Review" ? pill(v,"warn") : esc(v))),
    "No entries in this period.",data.headings.map((h,i) => /amount|rate|total|closing|opening|received|tax|cgst|sgst|igst|margin|cost|variance|current|days|outstanding|packets|planned|actual|scrap|issues|receipts|balance/i.test(h) && h !== "Date" ? i : -1),"report-table");
}

function reports(state, ui) {
  return pageStart("Audit reports","Review the monthly registers and download the selected report.", "", "Accounts and audit") +
    panel("",form("report",grid(select("Report","key",Object.entries(state.reports),ui.reportKey,"data-report-key") +
      field("From date","from",ui.from,'type=date required') + field("Through date","to",ui.to,'type=date required')),
    submit("Generate report"))) +
    (ui.reportData ? panel("",`<div class="panel-head"><div><h2>${esc(ui.reportData.title)}</h2>
      <small>${ui.loaded.key === "ageing" ? `As of ${ui.loaded.to}` : `${ui.loaded.from} to ${ui.loaded.to}`} · ${ui.reportData.rows.length} rows</small></div>
      <div class="actions">${link("Download CSV",reportUrl(ui.loaded.key,ui.loaded.from,ui.loaded.to,"csv"))}
      ${link("Download PDF",reportUrl(ui.loaded.key,ui.loaded.from,ui.loaded.to,"pdf"))}</div></div>${reportTable(ui.reportData)}`) : "");
}

function masters(state, ui) {
  const kinds = [["finished","Products"],["raw","Raw materials"],["packaging","Packaging"],
    ["retailer","Retailers"],["distributor","Distributors"],["supplier","Suppliers"],["recipe","Bill of materials"]];
  const kind = ui.kind;
  const products = state.items.filter(i => i.kind === "finished");
  const items = [...state.items,...state.customers,...state.suppliers].filter(i => i.kind === kind);
  const current = items.find(i => i.id === ui.masterId);
  const m = current || {};
  let body;
  if (kind === "recipe") {
    const recipe = state.recipes[ui.recipeProduct] || [];
    body = panel("Bill of materials",products.length ? form("recipe",
      select("Product","product",products.map(i => [i.id,i.name]),ui.recipeProduct,"data-recipe-product") +
      `<div class="form-list">${ui.recipeLines.map(r => lineRow("recipe",r,state)).join("")}</div>
      <p class="muted">Standard quantities are per batch. ${recipe.length ? "Saving replaces the current recipe for future runs." : "Add ingredients and packaging to start a recipe."}</p>`,
      button("Add component","add-line","recipe")+submit("Save recipe")) : empty("Create a product first."));
  } else {
    const stockItem = ["finished","raw","packaging"].includes(kind);
    let fields = field("Name","name",m.name,"required maxlength=120");
    if (stockItem) {
      fields += field("SKU","sku",m.sku,"required maxlength=32") +
        select("Stock unit","unit",kind === "finished" ? [["packet","packet"]] : [["kg","kg"],["L","L"],["piece","piece"]],m.unit) +
        number("Reorder level","reorder",m.unit ? scaled(m.reorder,m.unit) : 0, kind === "finished" ? "1" : ".001");
      if (kind === "finished") fields += number("Selling price (₹)","price",decimal(m.price || 0),".01") +
        field("HSN","hsn",m.hsn,"required pattern='[0-9]{4}|[0-9]{6}|[0-9]{8}'") +
        number("GST (%)","gst",(m.gst || 0)/100,".01") + number("Packets per carton","carton",m.carton || 20,"1","1") +
        number("Expected batch yield","yield",m.yield || 200,"1","1") + number("Variance tolerance (%)","tolerance",(m.tolerance ?? 300)/100,".01");
    } else {
      fields += field("State","state",m.state,"required") + field("State code","code",m.code,"required pattern='[0-9]{2}'") +
        field("GSTIN","gstin",m.gstin,"maxlength=15") + field("Billing and delivery address","address",m.address,"required maxlength=240") +
        field("Email","email",m.email,"type=email maxlength=120");
    }
    body = panel(current ? `Edit ${esc(m.name)}` : "New master record",form("master",grid(fields),
      submit(current ? "Save changes" : "Create record") + (current ? button("Cancel edit","edit-master",0) : ""), m.id)) +
      panel("Saved records",table(stockItem ? ["Name","SKU","Stock unit",""] : ["Name","State","GSTIN",""],items.map(i => [
        esc(i.name),esc(stockItem ? i.sku : i.state),esc(stockItem ? i.unit : i.gstin || "Unregistered"),button("Edit","edit-master",i.id,"inline")
      ]),"No records in this category."));
  }
  return pageStart("Master data","Maintain products, recipes, materials, customers and suppliers.") +
    panel("",`<div class="section-links">${kinds.map(([key,label]) => `<button data-action="set-kind" data-value="${key}"
      aria-pressed="${kind === key}">${label}</button>`).join("")}</div>`) + body;
}

export function view(page,state,ui) {
  const render = {overview, orders: state.user.role === "sales" ? sales : orderDesk, billing, production, purchases, inventory, reports, masters};
  return render[page](state,ui);
}
