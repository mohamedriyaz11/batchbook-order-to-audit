import csv
from datetime import date
from decimal import Decimal
from io import BytesIO, StringIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from domain import FACTORY, Problem, rows, run_data

REPORTS = {
    "sales": "Sales register", "customers": "Customer-wise sales", "products": "Product-wise sales",
    "gst": "GST outward supplies", "gst-totals": "GST outward totals (3B)",
    "purchases": "Purchase register",
    "stock": "Stock reconciliation", "ledger": "Stock movement ledger",
    "production": "Production variance", "costing": "Product costing",
    "payments": "Payments and collections", "ageing": "Receivables ageing", "audit": "Audit trail",
}

DOCUMENTS = """
    SELECT i.*,i.number document,i.day posted,1 sign,'Invoice' type FROM invoices i
    UNION ALL
    SELECT i.*,c.number document,c.day posted,-1 sign,'Credit note' type
    FROM invoices i JOIN credit_notes c ON c.invoice=i.id
"""


def decimal_text(value, places=2):
    return f"{Decimal(value) / (10 ** places):.{places}f}"


def qty(value, unit):
    if unit in ("kg", "L"):
        return f"{decimal_text(value, 3).rstrip('0').rstrip('.')} {unit}"
    return f"{value} {unit}"


def percent(value):
    return f"{decimal_text(value).rstrip('0').rstrip('.')}%"


def signed(row, columns):
    return [decimal_text(row[k] * row["sign"]) for k in columns]


def report(db, key, start, end):
    if key not in REPORTS:
        raise Problem("Unknown report.", 404)
    window = (start, end)
    docs = f"WITH d AS ({DOCUMENTS})"
    taxes = ("net", "cgst", "sgst", "igst", "total")
    if key == "sales":
        data = rows(db, docs + " SELECT * FROM d WHERE posted BETWEEN ? AND ? ORDER BY posted,document", *window)
        heads = ["Posted", "Document", "Type", "Customer", "Supply", "Taxable", "CGST", "SGST", "IGST", "Total"]
        return heads, [[d[k] for k in ("posted", "document", "type", "name", "state")] + signed(d, taxes) for d in data]
    if key == "gst":
        data = rows(db, docs + """ SELECT d.posted,d.document,d.type,d.name,d.gstin,d.state,d.code,d.sign,
                    l.hsn,l.rate,SUM(l.net) net,SUM(l.cgst) cgst,SUM(l.sgst) sgst,SUM(l.igst) igst
                    FROM d JOIN invoice_lines l ON l.invoice=d.id WHERE posted BETWEEN ? AND ?
                    GROUP BY d.document,l.hsn,l.rate ORDER BY posted,document""", *window)
        heads = ["Date", "Document", "Return bucket", "GSTIN", "Place of supply", "HSN", "Rate", "Taxable", "CGST", "SGST", "IGST"]
        result = []
        for d in data:
            bucket = "CDNR" if d["type"] == "Credit note" and d["gstin"] else (
                "CDNUR" if d["type"] == "Credit note" else ("B2B" if d["gstin"] else "B2C"))
            result.append([d["posted"], d["document"], bucket, d["gstin"] or "Unregistered",
                           f"{d['code']} {d['state']}", d["hsn"], percent(d["rate"])] + signed(d, taxes[:-1]))
        return heads, result
    if key == "gst-totals":
        data = rows(db, docs + """ SELECT CASE WHEN l.rate=0 THEN '3.1(c) Zero-rate master'
                    ELSE '3.1(a) Taxable outward' END bucket,
                    SUM(l.net*d.sign) net,SUM(l.cgst*d.sign) cgst,SUM(l.sgst*d.sign) sgst,SUM(l.igst*d.sign) igst
                    FROM d JOIN invoice_lines l ON l.invoice=d.id WHERE posted BETWEEN ? AND ?
                    GROUP BY bucket ORDER BY bucket""", *window)
        return ["Return worksheet bucket", "Taxable value", "CGST", "SGST", "IGST"], [
            [entry["bucket"], *[decimal_text(entry[k]) for k in taxes[:-1]]] for entry in data]
    if key == "customers":
        data = rows(db, docs + """ SELECT customer,name,SUM(net*sign) net,SUM(total*sign) total
                    FROM d WHERE posted BETWEEN ? AND ? GROUP BY customer,name ORDER BY name""", *window)
        return ["Customer", "Taxable", "Total with GST"], [[d["name"], decimal_text(d["net"]), decimal_text(d["total"])] for d in data]
    if key == "products":
        data = rows(db, docs + """ SELECT l.description,SUM(l.quantity*d.sign) qty,SUM(l.net*d.sign) net
                    FROM d JOIN invoice_lines l ON l.invoice=d.id WHERE posted BETWEEN ? AND ?
                    GROUP BY l.item,l.description ORDER BY l.description""", *window)
        return ["Product", "Packets", "Taxable"], [[d["description"], d["qty"], decimal_text(d["net"])] for d in data]
    if key == "purchases":
        data = rows(db, """SELECT p.*,s.name supplier_name,i.name,i.unit FROM purchases p
                           JOIN parties s ON s.id=p.supplier JOIN items i ON i.id=p.item
                           WHERE p.day BETWEEN ? AND ? ORDER BY p.day,p.id""", *window)
        return ["Date", "Receipt", "Supplier", "Supplier bill", "Item", "Quantity", "Rate", "Taxable", "GST", "Total"], [
            [d["day"], f"PUR-{d['id']:04}", d["supplier_name"], d["bill"], d["name"], qty(d["quantity"], d["unit"]),
             *[decimal_text(d[k]) for k in ("rate", "net", "tax")], decimal_text(d["net"] + d["tax"])] for d in data]
    if key == "stock":
        data = rows(db, """SELECT i.name,i.kind,i.unit,
            SUM(CASE WHEN m.day<? OR (m.kind='Opening' AND m.day<=?) THEN m.quantity ELSE 0 END) opening,
            SUM(CASE WHEN m.day BETWEEN ? AND ? AND m.kind IN ('Purchase receipt','Production output')
                THEN m.quantity ELSE 0 END) receipts,
            SUM(CASE WHEN m.day BETWEEN ? AND ? AND m.kind IN ('Production use','Production scrap','Dispatch')
                THEN -m.quantity ELSE 0 END) issues,
            SUM(CASE WHEN m.day BETWEEN ? AND ? AND m.kind LIKE 'Adjustment %' THEN m.quantity ELSE 0 END) adjustment
            FROM items i LEFT JOIN movements m ON i.id=m.item GROUP BY i.id ORDER BY i.id""", start, end, *window, *window, *window)
        return ["Item", "Category", "Opening", "Receipts", "Issues", "Adjustments", "Closing"], [
            [d["name"], d["kind"].title(), *[qty(d[k], d["unit"]) for k in ("opening", "receipts", "issues", "adjustment")],
             qty(d["opening"] + d["receipts"] - d["issues"] + d["adjustment"], d["unit"])] for d in data]
    if key == "ledger":
        data = rows(db, """WITH balances AS (SELECT m.*,SUM(quantity) OVER (PARTITION BY item ORDER BY day,id) balance
                           FROM movements m) SELECT b.*,i.sku,i.name,i.unit,u.name actor_name
                           FROM balances b JOIN items i ON i.id=b.item JOIN users u ON u.id=b.actor
                           WHERE b.day BETWEEN ? AND ? ORDER BY b.day,b.id""", *window)
        return ["Date", "Source", "Movement", "Item", "Change", "Balance", "By"], [
            [d["day"], d["source"], d["kind"], f"{d['sku']} · {d['name']}", qty(d["quantity"], d["unit"]),
             qty(d["balance"], d["unit"]), d["actor_name"]] for d in data]
    if key in ("production", "costing"):
        runs = rows(db, """SELECT r.*,i.name FROM runs r JOIN items i ON i.id=r.product
                           WHERE r.day BETWEEN ? AND ? ORDER BY r.day,r.id""", *window)
        runs = [run_data(db, run) for run in runs]
        if key == "production":
            result = []
            for run in runs:
                prefix = [run["day"], f"RUN-{run['id']:04}", run["name"]]
                result.append(prefix + ["Good output", qty(run["expected"], "packet"), qty(run["output"], "packet"),
                                        "", percent(run["variance"]), "Review" if run["flag"] else "Within limit", run["note"]])
                for line in run["lines"]:
                    result.append(prefix + [line["name"], *[qty(line[k], line["unit"]) for k in ("planned", "actual", "scrap")],
                                            percent(line["variance"]), "Review" if line["flag"] else "Within limit", ""])
            return ["Date", "Run", "Product", "Measure", "Planned", "Actual", "Scrap", "Variance", "Tolerance", "Run note"], result
        result = []
        for run in runs:
            result.append([run["day"], f"RUN-{run['id']:04}", run["name"], run["output"],
                           *[decimal_text(run[k]) for k in ("materials", "packaging", "labour", "utilities", "other", "total")],
                           *[decimal_text(run[k]) if run[k] is not None else "—" for k in ("unitCost", "price", "margin")]])
        return ["Date", "Run", "Product", "Good packets", "Materials", "Packaging", "Labour",
                "Gas/power", "Other", "Run cost", "Cost/pack", "Price/pack", "Margin/pack"], result
    if key == "payments":
        data = rows(db, """SELECT p.*,i.number,i.name FROM payments p JOIN invoices i ON i.id=p.invoice
                           WHERE p.day BETWEEN ? AND ? ORDER BY p.day,p.id""", *window)
        return ["Date", "Receipt", "Invoice", "Customer", "Mode", "Reference", "Received"], [
            [d["day"], f"PAY-{d['id']:04}", d["number"], d["name"], d["mode"], d["reference"], decimal_text(d["amount"])] for d in data]
    if key == "ageing":
        return ageing(db, end)
    data = rows(db, """SELECT a.*,u.name FROM audit a JOIN users u ON u.id=a.actor
                       WHERE date(a.at,'+05:30') BETWEEN ? AND ? ORDER BY a.id DESC""", *window)
    return ["Time (UTC)", "User", "Action", "Source", "Detail"], [[d[k] for k in ("at","name","action","entity","detail")] for d in data]


def ageing(db, end):
    data = rows(db, """SELECT i.*, i.total-COALESCE((SELECT SUM(p.amount) FROM payments p
                       WHERE p.invoice=i.id AND p.day<=?),0) balance FROM invoices i
                       WHERE i.day<=? AND NOT EXISTS (SELECT 1 FROM credit_notes c WHERE c.invoice=i.id AND c.day<=?)
                       ORDER BY i.name,i.due""", end, end, end)
    groups = {}
    for d in data:
        if not d["balance"]:
            continue
        days = (date.fromisoformat(end) - date.fromisoformat(d["due"])).days
        bucket = 0 if days <= 0 else min((days - 1) // 30 + 1, 4)
        amounts = groups.setdefault((d["customer"], d["name"]), [0] * 5)
        amounts[bucket] += d["balance"]
    return ["Customer", "Current", "1–30 days", "31–60 days", "61–90 days", "91+ days", "Outstanding"], [
        [name, *map(decimal_text, amounts), decimal_text(sum(amounts))] for (_, name), amounts in groups.items()]


def csv_bytes(headings, values):
    out = StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(headings)
    for row in values:
        writer.writerow(["'" + c if isinstance(c, str) and c.startswith(("=", "+", "-", "@", "\t", "\r"))
                         and not c.lstrip("-").replace(".", "", 1).isdigit() else c for c in row])
    return out.getvalue().encode("utf-8-sig")


def pdf(title, subtitle, heads, data, sections=(), wide=True, footer="Amounts in INR unless otherwise shown."):
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4) if wide else A4,
                            leftMargin=29, rightMargin=29, topMargin=28, bottomMargin=34)
    styles = getSampleStyleSheet()
    styles["Normal"].fontSize = 9
    styles["Normal"].leading = 13
    styles["Code"].fontName = "Helvetica"
    styles["Code"].fontSize = 7
    styles["Code"].leading = 10

    def p(value, style="Normal"):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), styles[style])

    flow = [p(title, "Title"), p(subtitle), Spacer(1, 12)]
    for heading, detail in sections:
        flow += [p(heading, "Heading3"), p(detail)]
    if sections:
        flow.append(Spacer(1, 12))
    values = [[p(c, "Code") for c in heads]]
    values += [[p(c, "Code") for c in row] for row in data]
    if len(values) == 1:
        values.append([p("No entries in this period.", "Code")] + [""] * (len(heads) - 1))
    available = doc.width
    weights = [max(7, min(30, max(len(str(head)), *(len(str(row[i])) for row in data[:100]), 7)))
               for i, head in enumerate(heads)]
    table = Table(values, colWidths=[available * w / sum(weights) for w in weights],
                  repeatRows=1, splitInRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3ed")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.HexColor("#496550")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#d8e0d9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    flow += [table, Spacer(1, 12), p(footer)]

    def page(canvas, document):
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(doc.pagesize[0] - 29, 18, f"Batchbook  •  Page {document.page}")

    doc.build(flow, onFirstPage=page, onLaterPages=page)
    return output.getvalue()


def invoice_pdf(inv, credit=False):
    number = inv["credit"] if credit else inv["number"]
    day = inv["creditDay"] if credit else inv["day"]
    sections = [
        ("Supplier", f"{FACTORY['name']}\n{FACTORY['address']}\nGSTIN {FACTORY['gstin']}"),
        ("Bill to / deliver to", f"{inv['name']}\n{inv['address']}\nGSTIN {inv['gstin'] or 'Unregistered'}"),
        ("Place of supply", f"{inv['state']} ({inv['code']})  ·  Reverse charge: No"),
    ]
    if credit:
        sections.append(("Original invoice and reason", f"{inv['number']} dated {inv['day']} · {inv['creditReason']}"))
    else:
        sections.append(("Payment due", inv["due"]))
    heads = ["Description / HSN", "Packets", "Rate", "Taxable", "GST %", "CGST", "SGST", "IGST"]
    data = [[f"{d['description']} / {d['hsn']}", d["quantity"], decimal_text(d["price"]), decimal_text(d["net"]),
             percent(d["rate"]), *[decimal_text(d[k]) for k in ("cgst", "sgst", "igst")]] for d in inv["lines"]]
    data.append(["Totals", "", "", decimal_text(inv["net"]), "",
                 *[decimal_text(inv[k]) for k in ("cgst", "sgst", "igst")]])
    label = "Credit amount" if credit else "Invoice total"
    return pdf(f"{'Credit Note' if credit else 'GST Tax Invoice'} · {number}", f"Issue date {day}",
               heads, data, sections, wide=False,
               footer=f"{label}: INR {decimal_text(inv['total'])}\nFor {FACTORY['name']} · Authorised signatory")
