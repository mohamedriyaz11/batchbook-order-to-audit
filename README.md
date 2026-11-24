# Batchbook

Batchbook takes a small snack factory from purchase receipt and recipe-based production to field orders, GST billing, collections, and monthly audit. The sample factory and all counterparties are fictional.

## Start the benchmark

With Docker Desktop or a Docker Engine with the Compose plugin installed, run:

```sh
docker compose up --build
```

Open **http://localhost:8000**. A persistent SQLite database is initialized with the benchmark masters and opening stock on first launch.

For local Python 3.12 development:

```sh
python -m pip install -r requirements.txt
python app.py
```

Use `python app.py --db data/another-benchmark.sqlite3` to start with a fresh database at an unused path. Use `python -m unittest discover -s tests -v` to run the benchmark, ledger, tax, and access-control tests.

### Test logins

All sample accounts use the password **`batchbook-demo`**. Selecting a benchmark account on the sign-in page fills its credentials.

| Username | Workspace |
| --- | --- |
| `sales-a` | Salesman A. Mobile order entry and own customer-wise sales |
| `sales-b` | Salesman B. Independent mobile order history |
| `production` | Supervisor. Receipts, production, inventory and demand planning |
| `admin` | Factory admin. Verification, invoicing, dispatch, collections and masters |
| `auditor` | External auditor. Read-only, date-filtered audit exports |
| `owner` | Factory owner. Read-only dashboard, balances and reports |

### Demo video

[Download the silent benchmark walkthrough](demo/batchbook-demo.mp4).

## Stack

Flask exposes a small same-origin JSON API, with role checks and transactions on the server. SQLite gives a single-factory prototype a durable ledger, foreign keys, and serialized stock posting without a separate database service. A plain HTML, CSS, and JavaScript front end keeps field order entry lightweight, while ReportLab produces server-side PDFs from the same data as the CSV downloads.

## Scope

| Tier | Included |
| --- | --- |
| Must have | Six test accounts across five roles, product and party masters, raw material and packaging masters, configurable BOM, mobile orders, admin edits/approval/rejection, GST invoice and credit-note PDFs, dispatch and inventory posting, planned vs actual variance, stock and sales exports |
| Should have | Supplier receipts, payments and receivables ageing, material and overhead costing, margin, GST worksheets, configurable variance limits, owner dashboard |
| Stretch | Offline order capture with a persistent queue and idempotent sync, low-stock thresholds, and batch recommendations from pending order demand |

Reports cover the sales register, customer and SKU sales, GST outward invoice/HSN detail and taxable outward totals, purchases, quantity reconciliation, stock movements, production variance, run costs, collections, receivables ageing, and user/time audit entries. Each report has CSV and PDF exports.

## Rerun Section 5

1. As **Production supervisor**, post a purchase of **60 kg flour at ₹45/kg** for Cauvery Flour Mills. Use a unique fictional supplier bill such as `FLOUR-01`.
2. Start a **Murukku 200 g** run for **one batch**. The recipe expects **200 packets**. Record **40 kg flour**, **10.5 L oil**, and **1.2 kg spice mix**.
3. Enter **188 good packets**, **188 pouches used**, **6 pouches scrap**, and **9 cartons used**. Post the run. Check the variance and the stock ledger.
4. As **Salesman A**, place an order for **Retailer A**, **150 packets** at the default price.
5. As **Factory admin**, review and approve this order, raise the GST invoice, download its PDF, and record dispatch.
6. As **Salesman B**, place an order for **Distributor B**, **120 packets**. In the admin order desk, check the 32-packet shortage. Approval stays blocked, and the order remains submitted with Karnataka as place of supply.
7. In Billing, record **₹4,000** against Retailer A's invoice using a unique payment reference.
8. Open the production run and save **₹1,200 labour** and **₹600 gas/power**. Check run cost and the margin against the list price.
9. As **External auditor**, select each report and generate it for the current month. Download CSV or PDF from the result. Receivables ageing uses the selected through date.

### Verified results

| Measure | Actual |
| --- | --- |
| Flour | 120 kg closing |
| Oil | 19.5 L closing |
| Spice mix | 3.8 kg closing |
| Pouches | 306 closing after 188 used and 6 scrapped |
| Cartons | 21 closing |
| Finished Murukku | 238 after production, 88 after dispatch |
| Yield variance | 188 vs 200, −6%, flagged |
| Oil variance | 10.5 L vs 10 L, +5%, flagged |
| Retailer A invoice | ₹7,500 taxable + ₹187.50 CGST + ₹187.50 SGST = ₹7,875 |
| Retailer A receivable | ₹3,875 after the ₹4,000 collection |
| Distributor B | Short by 32 packets. IGST treatment previewed without posting an invoice |
| Production cost | ₹5,855.00 total, ₹31.14 per good packet, ₹18.86 margin per packet |

Weighted-average flour after purchase costs `(100 × 42 + 60 × 45) / 160 = ₹43.125/kg`. The run issues ₹1,725 of flour, ₹1,470 of oil, ₹240 of spice mix, ₹485 of pouches including damage, and ₹135 of cartons. Direct overhead is ₹1,800. The run total is divided by 188 good packets and rounded to the nearest paisa.

## Assumptions and limits

- The assignment fixes the snack's GST rate at 5%. GSTINs, HSN, names, and addresses are sample values. The invoice uses the customer's state as the delivery place of supply, assumes forward charge, and uses per-line half-up rounding. State/HSN and tax amounts support GSTR-1 and 3B preparation as review worksheets. Zero-percent masters are treated as nil-rated in the 3B worksheet. Filing and e-invoicing are outside the prototype. [CBIC tax invoice rules](https://cbic-gst.gov.in/pdf/amended-01012022-CGST-Rules-2017-Part-A.pdf)
- Approved orders reserve stock. Posted deliveries are full dispatches. The prototype supports full credit notes for unpaid, undelivered invoices. Returns, refunds, and partial fulfilment are outside the prototype.
- Production consumes materials and receives output together with a single posting. The supervisor can revise run overheads through the audit trail. Posted stock quantities are corrected using a separately audited stock adjustment. Inventory reporting tracks quantities. Costing covers consumption and estimated unit margin. Opening finished stock carries no assumed cost, and finished-goods book valuation, COGS, and work in progress are outside scope.
- Business dates use India Standard Time and are assigned at posting. Payment terms are 30 days. Opening stock is dated on the first of the month when the database is seeded.
- Offline capture requires an initial online sign-in and a browser that supports service workers and local storage. The browser keeps the most recent field snapshot and the pending order queue on that device. The server revalidates orders and applies the current price list when they sync.
- Batch expiry and FEFO, route logging, Tally integration, and Tamil localization are optional extensions left outside this prototype.

[Design note and data model](DESIGN.md)
