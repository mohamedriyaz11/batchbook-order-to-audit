from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app import create_app
from domain import connect, quantity, tax, Problem
from seed import DEMO_PASSWORD


class BenchmarkTest(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "test.sqlite3"
        self.app = create_app(self.path)
        self.clients = {}

    def login(self, account):
        client = self.app.test_client()
        result = client.post("/api/login", json={"login": account, "password": DEMO_PASSWORD})
        self.assertEqual(result.status_code, 200)
        self.clients[account] = client

    def post(self, account, url, data=None, status=200):
        result = self.clients[account].post("/api/" + url, json=data or {})
        self.assertEqual(result.status_code, status, result.get_json())
        return result.get_json()

    def get(self, account, url):
        return self.clients[account].get("/api/" + url)

    def order(self, account, customer, quantity_, token):
        return self.post(account, "orders", {
            "customer": customer, "token": token, "lines": [{"item": 6, "quantity": quantity_}],
        }, 201)["id"]

    def verify(self, order_id, qty, status=200):
        return self.post("admin", f"orders/{order_id}/verify", {
            "action": "approve", "lines": [{"item": 6, "quantity": qty, "price": 50}],
        }, status)

    def balances(self):
        data = self.get("production", "state").get_json()
        return {i["id"]: i["balance"] for i in data["items"]}

    def test_section_five(self):
        for account in ("production", "sales-a", "sales-b", "admin", "auditor", "owner"):
            self.login(account)
        self.post("production", "purchases", {
            "supplier": 3, "item": 1, "quantity": "60", "unit": "kg", "rate": "45", "bill": "FLOUR-01",
        }, 201)

        entries = {"1": ("40", "0", "kg"), "2": ("10.5", "0", "L"), "3": ("1200", "0", "g"),
                   "4": ("188", "6", "piece"), "5": ("9", "0", "piece")}
        payload = {"product": 6, "batches": 1, "output": 188, "note": "Six pouches damaged",
                   "consumption": {key: dict(zip(("used", "scrap", "unit"), row)) for key, row in entries.items()}}
        failed = {**payload, "consumption": {**payload["consumption"], "4": {"used": "1000", "unit": "piece"}}}
        self.post("production", "runs", failed, 409)
        self.assertEqual(self.balances(), {1: 160000, 2: 30000, 3: 5000, 4: 500, 5: 30, 6: 50})

        run_id = self.post("production", "runs", payload, 201)["id"]
        self.assertEqual(self.balances(), {1: 120000, 2: 19500, 3: 3800, 4: 306, 5: 21, 6: 238})
        run = self.get("production", "state").get_json()["runs"][0]
        self.assertEqual((run["expected"], run["output"], run["variance"], run["flag"]), (200, 188, -600, True))
        self.assertEqual((run["lines"][1]["variance"], run["lines"][1]["flag"]), (500, True))
        self.assertEqual(run["lines"][3]["scrap"], 6)

        order_a = self.order("sales-a", 1, 150, "a")
        self.assertEqual(order_a, self.order("sales-a", 1, 150, "a"))
        self.verify(order_a, 150)
        self.assertEqual(self.balances()[6], 238)
        inv = self.post("admin", f"orders/{order_a}/invoice")["id"]
        self.assertEqual(self.balances()[6], 238)
        invoice = self.get("admin", "state").get_json()["invoices"][0]
        self.assertEqual([invoice[k] for k in ("net", "cgst", "sgst", "igst", "total")],
                         [750000, 18750, 18750, 0, 787500])
        self.assertRegex(invoice["number"], r"^INV/\d{4}/00001$")
        self.assertTrue(self.get("admin", f"invoices/{inv}/invoice.pdf").data.startswith(b"%PDF"))
        self.post("admin", f"invoices/{inv}/dispatch")
        self.post("admin", f"invoices/{inv}/dispatch", status=409)
        self.assertEqual(self.balances()[6], 88)

        order_b = self.order("sales-b", 2, 120, "b")
        self.assertIn("short by 32 packets", self.verify(order_b, 120, 409)["error"])
        self.assertEqual([o["id"] for o in self.get("sales-b", "state").get_json()["orders"]], [order_b])
        self.assertEqual(self.get("sales-b", "reports/sales").status_code, 403)
        self.post("auditor", "purchases", status=403)
        self.post("production", f"orders/{order_b}/invoice", status=403)

        payment = {"amount": 4000, "mode": "UPI", "reference": "UPI-0001"}
        self.post("admin", f"invoices/{inv}/payment", payment)
        self.post("admin", f"invoices/{inv}/payment", payment)
        self.post("admin", f"invoices/{inv}/payment", {**payment, "amount": 5000, "reference": "over"}, 409)
        self.assertEqual(self.get("admin", "state").get_json()["invoices"][0]["outstanding"], 387500)
        self.assertEqual(self.get("owner", "state").get_json()["outstanding"], 387500)
        self.post("production", f"runs/{run_id}/overheads", {"revision": 0, "labour": 1200, "utilities": 600})
        self.post("production", f"runs/{run_id}/overheads", {"revision": 0, "labour": 1000}, 409)
        run = self.get("production", "state").get_json()["runs"][0]
        self.assertEqual((run["total"], run["unitCost"], run["margin"]), (585500, 3114, 1886))

        stock = self.get("auditor", "reports/stock").get_json()["rows"]
        self.assertEqual([row[-1] for row in stock], ["120 kg", "19.5 L", "3.8 kg", "306 piece", "21 piece", "88 packet"])
        ledger = self.get("auditor", "reports/ledger").get_json()["rows"]
        self.assertEqual(len(ledger), 15)
        self.assertIn(["Retailer A", "3875.00", "0.00", "0.00", "0.00", "0.00", "3875.00"],
                      self.get("auditor", "reports/ageing").get_json()["rows"])
        for key in self.get("auditor", "state").get_json()["reports"]:
            self.assertEqual(self.get("auditor", f"reports/{key}").status_code, 200, key)
            self.assertTrue(self.get("auditor", f"reports/{key}?format=pdf").data.startswith(b"%PDF"), key)
            self.assertTrue(self.get("auditor", f"reports/{key}?format=csv").data.startswith(b"\xef\xbb\xbf"), key)

    def test_interstate_credit_note_and_reservation(self):
        for account in ("sales-a", "sales-b", "admin"):
            self.login(account)
        order_b = self.order("sales-b", 2, 40, "b")
        self.verify(order_b, 40)
        order_a = self.order("sales-a", 1, 15, "a")
        self.assertIn("short by 5 packets", self.verify(order_a, 15, 409)["error"])
        inv = self.post("admin", f"orders/{order_b}/invoice")["id"]
        record = self.get("admin", "state").get_json()["invoices"][0]
        self.assertEqual((record["cgst"], record["sgst"], record["igst"], record["total"]), (0, 0, 10000, 210000))
        self.post("admin", f"invoices/{inv}/credit", {"reason": "Customer cancelled before dispatch"})
        self.verify(order_a, 15)
        self.assertTrue(self.get("admin", f"invoices/{inv}/credit.pdf").data.startswith(b"%PDF"))
        buckets = [row[2] for row in self.get("admin", "reports/gst").get_json()["rows"]]
        self.assertCountEqual(buckets, ["B2B", "CDNR"])
        self.assertEqual(self.get("admin", "reports/ageing").get_json()["rows"], [])
        with closing(connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM credit_notes").fetchone()[0], 1)

    def test_exact_units_and_tax_rounding(self):
        self.assertEqual(quantity({"unit": "kg", "kind": "raw"}, "1.2", "kg"), 1200)
        self.assertEqual(quantity({"unit": "kg", "kind": "raw"}, "1200", "g"), 1200)
        self.assertEqual(quantity({"unit": "L", "kind": "raw"}, "10500", "ml"), 10500)
        self.assertEqual(quantity({"unit": "packet", "kind": "finished", "carton": 20}, "2", "carton"), 40)
        with self.assertRaises(Problem):
            quantity({"unit": "kg", "kind": "raw"}, "1.0001", "kg")
        self.assertEqual(tax(5001, 500, False), (125, 125, 0))
        self.assertEqual(tax(5001, 500, True), (0, 0, 250))


if __name__ == "__main__":
    unittest.main()
