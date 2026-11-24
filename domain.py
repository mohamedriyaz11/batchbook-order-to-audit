from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from pathlib import Path
import re
import sqlite3

from seed import seed

FACTORY = {"name": "Batchbook Foods", "state": "Tamil Nadu", "code": "33",
           "gstin": "33CCCCC0000C1ZJ", "address": "17 Demo Industrial Estate, Tiruchirappalli, Tamil Nadu"}
ROOT = Path(__file__).resolve().parent
UNITS = {"kg": {"kg": 1000, "g": 1}, "L": {"L": 1000, "ml": 1},
         "piece": {"piece": 1}, "packet": {"packet": 1}}


class Problem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def today():
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).date().isoformat()


def connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


@contextmanager
def write(db):
    try:
        db.execute("BEGIN IMMEDIATE")
        yield
        db.commit()
    except BaseException:
        db.rollback()
        raise


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
        with write(db):
            seed(db, today().replace(today()[-2:], "01"))


def rows(db, sql, *args):
    return [dict(row) for row in db.execute(sql, args)]


def one(db, sql, *args):
    row = db.execute(sql, args).fetchone()
    if row is None:
        raise Problem("Record not found.", 404)
    return dict(row)


def insert(db, sql, *args):
    return db.execute(sql, args).lastrowid


def clean(value, name, limit=120):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise Problem(f"Enter a valid {name} (up to {limit} characters).")
    return value.strip()


def scaled(value, scale, name, minimum=0, maximum=100000000):
    try:
        number = Decimal(str(value)) * scale
        if number.is_finite() and minimum <= number <= maximum and number == number.to_integral_value():
            return int(number)
    except (InvalidOperation, ValueError):
        pass
    raise Problem(f"Enter a valid {name} with the supported precision.")


def integer(value, name, minimum=1, maximum=100000000):
    return scaled(value, 1, name, minimum, maximum)


def money(value, name="amount", minimum=0):
    return scaled(value, 100, name, minimum, 10000000000)


def rounded(numerator, denominator):
    return int((Decimal(numerator) / denominator).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def quantity(item, value, unit, minimum=1):
    units = dict(UNITS[item["unit"]])
    if item["kind"] == "finished":
        units["carton"] = item["carton"]
    if unit not in units:
        raise Problem(f"Unsupported unit for {item['name']}.")
    return scaled(value, units[unit], "quantity", minimum)


def day_value(value):
    try:
        parsed = date.fromisoformat(value)
    except (ValueError, TypeError):
        raise Problem("Enter a valid date.") from None
    if value != parsed.isoformat():
        raise Problem("Use YYYY-MM-DD for dates.")
    return value


def item_by_id(db, key):
    return one(db, "SELECT * FROM items WHERE id=?", integer(key, "item"))


def stock(db, item):
    return one(db, """SELECT COALESCE(SUM(quantity),0) quantity, COALESCE(SUM(value),0) value
                     FROM movements WHERE item=?""", item)


def move(db, actor, item, day, kind, source, qty, value=0):
    if qty or value:
        db.execute("""INSERT INTO movements(item,day,kind,source,quantity,value,actor)
                      VALUES (?,?,?,?,?,?,?)""", (item, day, kind, source, qty, value, actor))


def issue(db, actor, item, day, kind, source, qty, valued=True):
    balance = stock(db, item["id"])
    if qty > balance["quantity"]:
        raise Problem(f"Insufficient stock for {item['name']}.", 409)
    value = rounded(balance["value"] * qty, balance["quantity"]) if qty and valued else 0
    move(db, actor, item["id"], day, kind, source, -qty, -value)
    return value


def audit(db, actor, action, entity, **detail):
    db.execute("INSERT INTO audit(actor,action,entity,detail) VALUES (?,?,?,?)",
               (actor, action, entity, json.dumps(detail, ensure_ascii=False)))


def inventory(db):
    return rows(db, """SELECT i.*, COALESCE(SUM(m.quantity),0) balance
                       FROM items i LEFT JOIN movements m ON m.item=i.id
                       GROUP BY i.id ORDER BY i.id""")


def purchase(db, actor, data, day):
    supplier = one(db, "SELECT * FROM parties WHERE id=? AND kind='supplier'", integer(data.get("supplier"), "supplier"))
    item = item_by_id(db, data.get("item"))
    if item["kind"] == "finished":
        raise Problem("Purchase receipts are for raw materials and packaging.")
    qty = quantity(item, data.get("quantity"), data.get("unit"))
    rate = money(data.get("rate"), "rate", 1)
    bill = clean(data.get("bill"), "supplier bill")
    if db.execute("SELECT 1 FROM purchases WHERE supplier=? AND bill=? AND item=?",
                  (supplier["id"], bill, item["id"])).fetchone():
        raise Problem("This item is already recorded for that supplier bill.", 409)
    value = rounded(qty * rate, UNITS[item["unit"]][item["unit"]])
    tax = money(data.get("tax", 0), "purchase tax")
    key = insert(db, "INSERT INTO purchases VALUES (NULL,?,?,?,?,?,?,?,?)",
                 supplier["id"], bill, day, item["id"], qty, rate, value, tax)
    move(db, actor, item["id"], day, "Purchase receipt", f"PUR-{key:04}", qty, value)
    audit(db, actor, "Receipt posted", f"PUR-{key:04}", bill=bill)
    return key


def recipe(db, product):
    return rows(db, """SELECT i.*, b.quantity planned FROM bom b
                       JOIN items i ON i.id=b.item WHERE b.product=? ORDER BY i.id""", product)


def production(db, actor, data, day):
    product = item_by_id(db, data.get("product"))
    materials = recipe(db, product["id"])
    if product["kind"] != "finished" or not product["yield"] or not materials:
        raise Problem("Choose a finished product with a configured recipe.")
    batches = integer(data.get("batches"), "batch count", 1, 10000)
    output = quantity(product, data.get("output"), data.get("outputUnit", "packet"), 0)
    note = str(data.get("note", "")).strip()[:240]
    if output == 0 and not note:
        raise Problem("Explain the loss when a run produces no good packets.")
    consumption = data.get("consumption", {})
    if not isinstance(consumption, dict) or set(consumption) != {str(i["id"]) for i in materials}:
        raise Problem("Enter actual usage for every recipe component.")
    key = insert(db, """INSERT INTO runs(product,day,batches,expected,output,note,tolerance,price)
                        VALUES (?,?,?,?,?,?,?,?)""", product["id"], day, batches,
                 product["yield"] * batches, output, note, product["tolerance"], product["price"])
    code = f"RUN-{key:04}"
    totals = {"raw": 0, "packaging": 0}
    for item in materials:
        entry = consumption[str(item["id"])]
        if not isinstance(entry, dict):
            raise Problem("Enter material usage and scrap.")
        used = quantity(item, entry.get("used"), entry.get("unit"), 0)
        scrap = quantity(item, entry.get("scrap", 0), entry.get("unit"), 0)
        value = issue(db, actor, item, day, "Production use", code, used)
        value += issue(db, actor, item, day, "Production scrap", code, scrap)
        totals[item["kind"]] += value
        db.execute("INSERT INTO run_lines VALUES (?,?,?,?,?,?)",
                   (key, item["id"], item["planned"] * batches, used + scrap, scrap, value))
    db.execute("UPDATE runs SET materials=?, packaging=? WHERE id=?", (totals["raw"], totals["packaging"], key))
    move(db, actor, product["id"], day, "Production output", code, output)
    audit(db, actor, "Run posted", code, batches=batches, output=output)
    return key


def overheads(db, actor, key, data):
    run = one(db, "SELECT * FROM runs WHERE id=?", key)
    if integer(data.get("revision"), "revision", 0) != run["revision"]:
        raise Problem("This run has changed. Reload it before saving.", 409)
    before = {field: run[field] for field in ("labour", "utilities", "other")}
    after = {field: money(data.get(field, 0), field) for field in before}
    db.execute("UPDATE runs SET labour=?,utilities=?,other=?,revision=revision+1 WHERE id=?",
               (*after.values(), key))
    audit(db, actor, "Run overheads revised", f"RUN-{key:04}", before=before, after=after)


def variance(actual, planned):
    return rounded((actual - planned) * 10000, planned)


def run_data(db, run):
    lines = rows(db, """SELECT l.*,i.name,i.unit,i.kind FROM run_lines l
                        JOIN items i ON i.id=l.item WHERE l.run=? ORDER BY i.id""", run["id"])
    for line in lines:
        line["variance"] = variance(line["actual"], line["planned"])
        line["flag"] = abs(line["actual"] - line["planned"]) * 10000 > line["planned"] * run["tolerance"]
    run["lines"] = lines
    run["variance"] = variance(run["output"], run["expected"])
    run["flag"] = abs(run["output"] - run["expected"]) * 10000 > run["expected"] * run["tolerance"]
    run["total"] = sum(run[k] for k in ("materials", "packaging", "labour", "utilities", "other"))
    run["unitCost"] = rounded(run["total"], run["output"]) if run["output"] else None
    run["margin"] = run["price"] - run["unitCost"] if run["output"] else None
    return run


def order_lines(db, data, sales):
    entries = data.get("lines")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 40:
        raise Problem("Add between 1 and 40 products.")
    result = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise Problem("Enter a valid product line.")
        item = item_by_id(db, entry.get("item"))
        if item["kind"] != "finished":
            raise Problem("Orders can contain finished products only.")
        if item["id"] in result:
            raise Problem("Combine repeat products into one order line.")
        qty = quantity(item, entry.get("quantity"), entry.get("unit", "packet"))
        price = item["price"] if sales else money(entry.get("price"), "selling price")
        result[item["id"]] = (qty, price)
    return [(item, qty, price) for item, (qty, price) in result.items()]


def save_lines(db, key, lines):
    db.execute("DELETE FROM order_lines WHERE order_id=?", (key,))
    db.executemany("INSERT INTO order_lines VALUES (?,?,?,?)", [(key, *line) for line in lines])


def submit(db, actor, data, day):
    token = clean(data.get("token"), "order reference", 80)
    previous = rows(db, "SELECT id FROM orders WHERE salesman=? AND token=?", actor, token)
    if previous:
        return previous[0]["id"]
    customer = one(db, "SELECT id FROM parties WHERE id=? AND kind IN ('retailer','distributor')",
                   integer(data.get("customer"), "customer"))
    lines = order_lines(db, data, True)
    key = insert(db, "INSERT INTO orders VALUES (NULL,?,?,?,'Submitted',?)", customer["id"], actor, day, token)
    save_lines(db, key, lines)
    audit(db, actor, "Order submitted", f"ORD-{key:04}")
    return key


def availability(db, item, current_order):
    reserved = one(db, """SELECT COALESCE(SUM(l.quantity),0) n FROM order_lines l JOIN orders o ON o.id=l.order_id
                          WHERE l.item=? AND o.status IN ('Approved','Invoiced') AND o.id<>?""",
                   item, current_order)["n"]
    return stock(db, item)["quantity"] - reserved


def verify(db, actor, key, data):
    order = one(db, "SELECT * FROM orders WHERE id=?", key)
    if order["status"] != "Submitted":
        raise Problem("Only submitted orders can be verified.", 409)
    action = data.get("action")
    old = rows(db, "SELECT item,quantity,price FROM order_lines WHERE order_id=? ORDER BY item", key)
    if action == "reject":
        reason = clean(data.get("reason"), "rejection reason")
        status = "Rejected"
        audit(db, actor, "Order rejected", f"ORD-{key:04}", reason=reason)
    else:
        if action not in ("save", "approve"):
            raise Problem("Choose a verification action.")
        lines = order_lines(db, data, False)
        if action == "approve":
            for item, qty, _ in lines:
                available = availability(db, item, key)
                if qty > available:
                    name = item_by_id(db, item)["name"]
                    raise Problem(f"{name} is short by {qty - max(available, 0)} packets. Approval is blocked.", 409)
        save_lines(db, key, lines)
        status = "Approved" if action == "approve" else "Submitted"
        audit(db, actor, f"Order {status.lower()}" if action == "approve" else "Order edited",
              f"ORD-{key:04}", before=old, after=lines)
    db.execute("UPDATE orders SET status=? WHERE id=?", (status, key))


def tax(net, bps, interstate):
    if interstate:
        return 0, 0, rounded(net * bps, 10000)
    split = rounded(net * bps, 20000)
    return split, split, 0


def new_number(db, kind, day):
    d = date.fromisoformat(day)
    year = d.year - (d.month < 4)
    series = f"{kind}/{year % 100:02}{(year + 1) % 100:02}"
    sequence = one(db, """INSERT INTO sequences VALUES (?,1) ON CONFLICT(series)
                          DO UPDATE SET number=number+1 RETURNING number""", series)["number"]
    number = f"{series}/{sequence:05}"
    if len(number) > 16:
        raise Problem("Financial-year document sequence exhausted.", 409)
    return number


def invoice(db, actor, key, day):
    order = one(db, "SELECT * FROM orders WHERE id=?", key)
    if order["status"] != "Approved":
        raise Problem("Approve the order before invoicing.", 409)
    customer = one(db, "SELECT * FROM parties WHERE id=?", order["customer"])
    lines = rows(db, """SELECT l.*,i.name,i.hsn,i.gst FROM order_lines l JOIN items i ON i.id=l.item
                        WHERE l.order_id=?""", key)
    number = new_number(db, "INV", day)
    items = []
    for line in lines:
        net = line["price"] * line["quantity"]
        taxes = tax(net, line["gst"], customer["code"] != FACTORY["code"])
        items.append((line["item"], line["name"], line["quantity"], line["price"], line["hsn"],
                      line["gst"], net, *taxes))
    net, cgst, sgst, igst = (sum(item[column] for item in items) for column in range(6, 10))
    due = (date.fromisoformat(day) + timedelta(days=30)).isoformat()
    inv = insert(db, """INSERT INTO invoices(order_id,number,day,due,customer,name,gstin,address,state,code,email,net,
                        cgst,sgst,igst,total) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                 key, number, day, due, customer["id"], customer["name"], customer["gstin"], customer["address"],
                 customer["state"], customer["code"], customer["email"], net, cgst, sgst, igst, net + cgst + sgst + igst)
    db.executemany("INSERT INTO invoice_lines VALUES (?,?,?,?,?,?,?,?,?,?,?)", [(inv, *item) for item in items])
    db.execute("UPDATE orders SET status='Invoiced' WHERE id=?", (key,))
    audit(db, actor, "Invoice posted", number, order=key, total=net + cgst + sgst + igst)
    return inv


def dispatch(db, actor, key, day):
    inv = one(db, """SELECT i.*,o.status FROM invoices i JOIN orders o ON o.id=i.order_id WHERE i.id=?""", key)
    if inv["status"] != "Invoiced":
        raise Problem("This invoice is not awaiting dispatch.", 409)
    for line in rows(db, "SELECT item,quantity FROM invoice_lines WHERE invoice=?", key):
        item = item_by_id(db, line["item"])
        if line["quantity"] > availability(db, item["id"], inv["order_id"]):
            raise Problem(f"Insufficient available stock for {item['name']}.", 409)
        issue(db, actor, item, day, "Dispatch", inv["number"], line["quantity"], valued=False)
    db.execute("UPDATE invoices SET dispatched=? WHERE id=?", (day, key))
    db.execute("UPDATE orders SET status='Dispatched' WHERE id=?", (inv["order_id"],))
    audit(db, actor, "Invoice dispatched", inv["number"])


def invoice_data(db, key):
    result = one(db, """SELECT i.*, c.number credit, c.day creditDay, c.reason creditReason
                        FROM invoices i LEFT JOIN credit_notes c ON c.invoice=i.id WHERE i.id=?""", key)
    result["lines"] = rows(db, "SELECT * FROM invoice_lines WHERE invoice=? ORDER BY item", key)
    result["payments"] = rows(db, "SELECT * FROM payments WHERE invoice=? ORDER BY id", key)
    result["paid"] = sum(p["amount"] for p in result["payments"])
    result["outstanding"] = 0 if result["credit"] else result["total"] - result["paid"]
    return result


def payment(db, actor, key, data, day):
    inv = invoice_data(db, key)
    amount = money(data.get("amount"), minimum=1)
    reference = clean(data.get("reference"), "payment reference")
    mode = data.get("mode")
    if mode not in ("Cash", "UPI", "Bank transfer", "Cheque"):
        raise Problem("Choose a payment mode.")
    existing = rows(db, "SELECT amount,mode FROM payments WHERE invoice=? AND reference=?", key, reference)
    if existing:
        if existing[0] == {"amount": amount, "mode": mode}:
            return
        raise Problem("That payment reference is already in use.", 409)
    if amount > inv["outstanding"]:
        raise Problem("Payment exceeds the outstanding invoice balance.", 409)
    insert(db, "INSERT INTO payments VALUES (NULL,?,?,?,?,?)", key, day, amount, mode, reference)
    audit(db, actor, "Payment recorded", inv["number"], amount=amount, reference=reference)


def credit(db, actor, key, data, day):
    inv = invoice_data(db, key)
    if inv["credit"] or inv["dispatched"] or inv["paid"]:
        raise Problem("Only unpaid, undelivered invoices can be cancelled here.", 409)
    reason = clean(data.get("reason"), "credit note reason")
    number = new_number(db, "CN", day)
    insert(db, "INSERT INTO credit_notes VALUES (NULL,?,?,?,?)", key, number, day, reason)
    db.execute("UPDATE orders SET status='Cancelled' WHERE id=?", (inv["order_id"],))
    audit(db, actor, "Invoice cancelled by credit note", inv["number"], credit=number, reason=reason)


def adjust(db, actor, data, day):
    item = item_by_id(db, data.get("item"))
    qty = quantity(item, data.get("quantity"), data.get("unit"))
    reason = clean(data.get("reason"), "adjustment reason", 240)
    code = f"ADJ-{one(db, 'SELECT COALESCE(MAX(id),0)+1 n FROM movements')['n']:04}"
    if data.get("direction") == "Decrease":
        issue(db, actor, item, day, "Adjustment decrease", code, qty)
    elif data.get("direction") == "Increase":
        rate = money(data.get("rate", 0), "adjustment rate", int(item["kind"] != "finished"))
        value = rounded(qty * rate, UNITS[item["unit"]][item["unit"]])
        move(db, actor, item["id"], day, "Adjustment increase", code, qty, value)
    else:
        raise Problem("Choose an adjustment direction.")
    audit(db, actor, "Stock adjusted", code, reason=reason, item=item["id"])
    return code


def master(db, actor, data):
    kind = data.get("kind")
    key = integer(data["id"], "record") if data.get("id") else None
    name = clean(data.get("name"), "name")
    if kind in ("retailer", "distributor", "supplier"):
        state = clean(data.get("state"), "state")
        code = clean(data.get("code"), "state code", 2)
        gstin = str(data.get("gstin") or "").strip().upper()
        if not re.fullmatch(r"[0-9]{2}", code) or (gstin and not re.fullmatch(code + r"[A-Z0-9]{13}", gstin)):
            raise Problem("Enter a two-digit state code and a matching 15-character GSTIN if registered.")
        address = clean(data.get("address"), "address", 240)
        email = str(data.get("email") or "").strip()[:120]
        if email and not re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", email):
            raise Problem("Enter a valid email address.")
        if key:
            one(db, "SELECT id FROM parties WHERE id=? AND kind=?", key, kind)
            db.execute("UPDATE parties SET name=?,state=?,code=?,gstin=?,address=?,email=? WHERE id=?",
                       (name, state, code, gstin, address, email, key))
        else:
            key = insert(db, "INSERT INTO parties VALUES (NULL,?,?,?,?,?,?,?)",
                         name, kind, state, code, gstin, address, email)
    elif kind in ("raw", "packaging", "finished"):
        unit = data.get("unit")
        if unit not in UNITS or (kind == "finished") != (unit == "packet"):
            raise Problem("Choose a valid unit for this stock category.")
        sku = clean(data.get("sku"), "SKU", 32)
        if db.execute("SELECT 1 FROM items WHERE sku=? AND id<>?", (sku, key or 0)).fetchone():
            raise Problem("That SKU already exists.", 409)
        prev = item_by_id(db, key) if key else None
        if prev and (prev["unit"] != unit or prev["kind"] != kind):
            raise Problem("An existing item's category and stock unit are fixed.")
        reorder = quantity({"kind": kind, "unit": unit, "carton": 1}, data.get("reorder", 0), unit, 0)
        fields = (sku, name, kind, unit, reorder)
        if kind == "finished":
            hsn = clean(data.get("hsn"), "HSN", 8)
            if not re.fullmatch(r"\d{4}|\d{6}|\d{8}", hsn):
                raise Problem("Enter a 4-, 6- or 8-digit HSN.")
            fields += (money(data.get("price")), hsn, scaled(data.get("gst"), 100, "GST rate", 0, 10000),
                       integer(data.get("carton"), "packets per carton"), integer(data.get("yield"), "batch yield"),
                       scaled(data.get("tolerance"), 100, "tolerance", 0, 10000))
        else:
            fields += (0, None, 0, 1, 0, 300)
        if key:
            db.execute("""UPDATE items SET sku=?,name=?,kind=?,unit=?,reorder=?,price=?,hsn=?,gst=?,carton=?,
                          yield=?,tolerance=? WHERE id=?""", (*fields, key))
        else:
            key = insert(db, "INSERT INTO items VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?)", *fields)
    else:
        raise Problem("Unknown master record category.")
    audit(db, actor, "Master saved", f"{kind}-{key}", name=name)
    return key


def save_recipe(db, actor, key, data):
    product = item_by_id(db, key)
    if product["kind"] != "finished":
        raise Problem("Only finished goods have a recipe.")
    entries = data.get("lines")
    if not isinstance(entries, list) or not entries or len(entries) > 80:
        raise Problem("Add at least one recipe component.")
    before = recipe(db, key)
    lines = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise Problem("Enter a valid recipe component.")
        item = item_by_id(db, entry.get("item"))
        if item["kind"] == "finished" or item["id"] in lines:
            raise Problem("Use each raw or packaging component once.")
        lines[item["id"]] = quantity(item, entry.get("quantity"), entry.get("unit"))
    db.execute("DELETE FROM bom WHERE product=?", (key,))
    db.executemany("INSERT INTO bom VALUES (?,?,?)", [(key, item, qty) for item, qty in lines.items()])
    audit(db, actor, "Recipe revised", product["sku"],
          before={line["id"]: line["planned"] for line in before}, after=lines)
