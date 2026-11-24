import argparse
from decimal import Decimal
import hashlib
import os
from pathlib import Path
import secrets
import time

from flask import Flask, Response, g, jsonify, request, send_from_directory
from werkzeug.security import check_password_hash

import domain as d
from reports import REPORTS, csv_bytes, invoice_pdf, pdf, report


def create_app(path=None):
    app = Flask(__name__, static_folder="web", static_url_path="/assets")
    app.config["MAX_CONTENT_LENGTH"] = 128 * 1024
    path = Path(path or os.environ.get("BATCHBOOK_DB", d.ROOT / "data" / "batchbook.sqlite3"))
    d.initialize(path)

    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    @app.before_request
    def load():
        if not request.path.startswith("/api/"):
            return
        g.db = d.connect(path)
        token = request.cookies.get("batchbook_session", "")
        g.token = digest(token) if token else ""
        users = d.rows(g.db, """SELECT u.id,u.login,u.name,u.role FROM sessions s JOIN users u ON u.id=s.user
                                WHERE s.digest=? AND s.expires>?""", g.token, int(time.time()))
        g.user = users[0] if users else None

    @app.teardown_request
    def close(_error):
        if hasattr(g, "db"):
            g.db.close()

    @app.after_request
    def headers(response):
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.errorhandler(d.Problem)
    def problem(exc):
        return jsonify(error=str(exc)), exc.status

    def allow(*roles):
        if g.user is None:
            raise d.Problem("Sign in to continue.", 401)
        if roles and g.user["role"] not in roles:
            raise d.Problem("This role does not have access.", 403)
        return g.user["id"]

    def payload():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise d.Problem("Send a JSON object.")
        return data

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/sw.js")
    def service_worker():
        return send_from_directory(app.static_folder, "sw.js", max_age=0)

    @app.post("/api/login")
    def login():
        data = payload()
        username = d.clean(data.get("login"), "username", 50).lower()
        password = d.clean(data.get("password"), "password", 100)
        account = d.rows(g.db, "SELECT * FROM users WHERE login=?", username)
        if not account or not check_password_hash(account[0]["password"], password):
            raise d.Problem("The username or password is incorrect.", 401)
        user = account[0]
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        ttl = 12 * 60 * 60
        with d.write(g.db):
            g.db.execute("DELETE FROM sessions WHERE expires<=? OR digest=?", (now, g.token))
            g.db.execute("INSERT INTO sessions VALUES (?,?,?)", (digest(token), user["id"], now + ttl))
        response = jsonify(user={k: user[k] for k in ("login", "name", "role")})
        response.set_cookie("batchbook_session", token, httponly=True, samesite="Lax",
                            secure=request.is_secure, max_age=ttl)
        return response

    @app.post("/api/logout")
    def logout():
        payload()
        with d.write(g.db):
            g.db.execute("DELETE FROM sessions WHERE digest=?", (g.token,))
        response = jsonify(ok=True)
        response.delete_cookie("batchbook_session")
        return response

    def orders(actor, role):
        result = d.rows(g.db, """SELECT o.id,o.day,o.status,p.name customer,p.state,p.code,p.gstin,u.name salesman,
                                 i.id invoice,i.number FROM orders o JOIN parties p ON p.id=o.customer
                                 JOIN users u ON u.id=o.salesman LEFT JOIN invoices i ON i.order_id=o.id
                                 WHERE (?<>'sales' OR o.salesman=?) ORDER BY o.id DESC""", role, actor)
        for order in result:
            order["lines"] = d.rows(g.db, """SELECT l.*,i.name FROM order_lines l JOIN items i ON i.id=l.item
                                             WHERE l.order_id=? ORDER BY l.item""", order["id"])
            order["net"] = sum(l["quantity"] * l["price"] for l in order["lines"])
            if role == "admin" and order["status"] in ("Submitted", "Approved", "Invoiced"):
                for line in order["lines"]:
                    line["available"] = max(0, d.availability(g.db, line["item"], order["id"]))
            if role == "sales":
                order.pop("gstin")
                order.pop("invoice")
        return result

    @app.get("/api/state")
    def state():
        actor = allow()
        role = g.user["role"]
        day = d.today()
        result = {"user": g.user, "day": day}
        if role in ("admin", "production", "owner"):
            result["items"] = d.inventory(g.db)
        if role == "sales":
            result["items"] = d.rows(g.db, "SELECT id,name,sku,price,carton FROM items WHERE kind='finished' ORDER BY name")
            result["customers"] = d.rows(g.db, """SELECT id,name,kind,state FROM parties WHERE kind<>'supplier' ORDER BY name""")
        if role in ("admin", "production"):
            result["recipes"] = {i["id"]: d.recipe(g.db, i["id"]) for i in result["items"] if i["kind"] == "finished"}
            result["suppliers"] = d.rows(g.db, "SELECT * FROM parties WHERE kind='supplier' ORDER BY name")
            result["purchases"] = d.rows(g.db, """SELECT p.*,i.name,i.unit,s.name supplier_name FROM purchases p
                JOIN items i ON p.item=i.id JOIN parties s ON s.id=p.supplier ORDER BY p.id DESC""")
        if role in ("admin", "production", "owner"):
            result["runs"] = [d.run_data(g.db, r) for r in d.rows(g.db, """SELECT r.*,i.name FROM runs r
                                       JOIN items i ON i.id=r.product ORDER BY r.id DESC""")]
        if role in ("sales", "admin", "owner"):
            result["orders"] = orders(actor, role)
        if role == "admin":
            result["customers"] = d.rows(g.db, "SELECT * FROM parties WHERE kind<>'supplier' ORDER BY name")
            result["invoices"] = [d.invoice_data(g.db, i["id"]) for i in
                                  d.rows(g.db, "SELECT id FROM invoices ORDER BY id DESC")]
        if role in ("admin", "auditor", "owner"):
            result["reports"] = REPORTS
        if role == "owner":
            result["outstanding"] = sum(int(Decimal(row[-1]) * 100) for row in report(g.db, "ageing", day, day)[1])
        if role == "production":
            result["pendingDemand"] = d.rows(g.db, """SELECT i.id,i.name,i.yield,SUM(l.quantity) demand
                FROM order_lines l JOIN orders o ON o.id=l.order_id JOIN items i ON i.id=l.item
                WHERE o.status IN ('Submitted','Approved','Invoiced') GROUP BY i.id ORDER BY i.name""")
        return jsonify(result)

    @app.post("/api/<operation>")
    def create(operation):
        actions = {
            "orders": (("sales",), d.submit),
            "purchases": (("production", "admin"), d.purchase),
            "runs": (("production", "admin"), d.production),
            "adjustments": (("admin",), d.adjust),
            "masters": (("admin",), None),
        }
        if operation not in actions:
            raise d.Problem("Unknown action.", 404)
        roles, action = actions[operation]
        actor = allow(*roles)
        data = payload()
        with d.write(g.db):
            key = action(g.db, actor, data, d.today()) if action else d.master(g.db, actor, data)
        return jsonify(id=key), 201

    @app.post("/api/<operation>/<int:key>/<action>")
    def update(operation, key, action):
        actions = {
            ("orders", "verify"): (("admin",), lambda actor, data: d.verify(g.db, actor, key, data)),
            ("orders", "invoice"): (("admin",), lambda actor, data: d.invoice(g.db, actor, key, d.today())),
            ("invoices", "dispatch"): (("admin",), lambda actor, data: d.dispatch(g.db, actor, key, d.today())),
            ("invoices", "payment"): (("admin",), lambda actor, data: d.payment(g.db, actor, key, data, d.today())),
            ("invoices", "credit"): (("admin",), lambda actor, data: d.credit(g.db, actor, key, data, d.today())),
            ("runs", "overheads"): (("production", "admin"), lambda actor, data: d.overheads(g.db, actor, key, data)),
            ("masters", "recipe"): (("admin",), lambda actor, data: d.save_recipe(g.db, actor, key, data)),
        }
        entry = actions.get((operation, action))
        if entry is None:
            raise d.Problem("Unknown action.", 404)
        roles, handler = entry
        actor = allow(*roles)
        data = payload()
        with d.write(g.db):
            result = handler(actor, data)
        return jsonify(id=result)

    @app.get("/api/reports/<key>")
    def get_report(key):
        allow("admin", "auditor", "owner", "production")
        if g.user["role"] == "production" and key not in ("ledger", "stock", "purchases", "production", "costing"):
            raise d.Problem("This role does not have access to this report.", 403)
        day = d.today()
        start = d.day_value(request.args.get("from", day[:8] + "01"))
        end = d.day_value(request.args.get("to", day))
        if start > end:
            raise d.Problem("The start date must be before or equal to the end date.")
        headings, data = report(g.db, key, start, end)
        format_ = request.args.get("format")
        title = REPORTS[key]
        if format_ == "csv":
            return attachment(csv_bytes(headings, data), "text/csv", f"{key}-{end}.csv")
        if format_ == "pdf":
            label = f"As of {end}" if key == "ageing" else f"{start} to {end}"
            return attachment(pdf(title, label, headings, data), "application/pdf", f"{key}-{end}.pdf")
        return jsonify(title=title, headings=headings, rows=data)

    @app.get("/api/invoices/<int:key>/<document>.pdf")
    def document_pdf(key, document):
        allow("admin", "auditor")
        record = d.invoice_data(g.db, key)
        if document not in ("invoice", "credit") or (document == "credit" and not record["credit"]):
            raise d.Problem("Document not found.", 404)
        number = record["credit"] if document == "credit" else record["number"]
        name = number.replace("/", "-") + ".pdf"
        return attachment(invoice_pdf(record, document == "credit"), "application/pdf", name,
                          inline=request.args.get("view") == "1")

    return app


def attachment(content, mime, filename, inline=False):
    return Response(content, mimetype=mime, headers={
        "Content-Disposition": f'{"inline" if inline else "attachment"}; filename="{filename}"'
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start Batchbook with seeded benchmark masters.")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--db", type=Path)
    args = parser.parse_args()
    create_app(args.db).run(host=args.host, port=args.port, threaded=True)
