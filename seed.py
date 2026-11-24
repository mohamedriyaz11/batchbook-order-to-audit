from werkzeug.security import generate_password_hash

DEMO_PASSWORD = "batchbook-demo"


def seed(db, opening_day):
    if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        return
    accounts = [
        ("sales-a", "Salesman A", "sales"), ("sales-b", "Salesman B", "sales"),
        ("admin", "Factory admin", "admin"), ("production", "Production supervisor", "production"),
        ("auditor", "External auditor", "auditor"), ("owner", "Factory owner", "owner"),
    ]
    password = generate_password_hash(DEMO_PASSWORD)
    db.executemany("INSERT INTO users(login,name,role,password) VALUES (?,?,?,?)",
                   [(*account, password) for account in accounts])
    db.executemany("""
        INSERT INTO items(id,sku,name,kind,unit,reorder,price,hsn,gst,carton,yield)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, [
        (1, "RM-001", "Flour", "raw", "kg", 25000, 0, None, 0, 1, 0),
        (2, "RM-002", "Cooking oil", "raw", "L", 20000, 0, None, 0, 1, 0),
        (3, "RM-003", "Salt and spice mix", "raw", "kg", 1000, 0, None, 0, 1, 0),
        (4, "PK-001", "200 g pouch", "packaging", "piece", 100, 0, None, 0, 1, 0),
        (5, "PK-002", "Carton (20 packets)", "packaging", "piece", 10, 0, None, 0, 1, 0),
        (6, "FG-200", "Murukku 200 g", "finished", "packet", 30, 5000, "210690", 500, 20, 200),
    ])
    db.executemany("INSERT INTO bom VALUES (6,?,?)",
                   [(1, 40000), (2, 10000), (3, 1200), (4, 200), (5, 10)])
    db.executemany("""
        INSERT INTO parties(id,name,kind,state,code,gstin,address,email) VALUES (?,?,?,?,?,?,?,?)
    """, [
        (1, "Retailer A", "retailer", "Tamil Nadu", "33", "33AAAAA0000A1ZK",
         "8 Demo Bazaar Road, Tiruchirappalli, Tamil Nadu", "retailer-a@example.test"),
        (2, "Distributor B", "distributor", "Karnataka", "29", "29BBBBB0000B1ZG",
         "12 Demo Market Road, Bengaluru, Karnataka", "distributor-b@example.test"),
        (3, "Cauvery Flour Mills", "supplier", "Tamil Nadu", "33", "33DDDDD0000D1Z6",
         "24 Demo Mill Road, Tiruchirappalli, Tamil Nadu", "mill@example.test"),
    ])
    db.executemany("""
        INSERT INTO movements(item,day,kind,source,quantity,value,actor)
        VALUES (?,?,'Opening','OPEN-001',?,?,3)
    """, [(item, opening_day, qty, value) for item, qty, value in [
        (1, 100000, 420000), (2, 30000, 420000), (3, 5000, 100000),
        (4, 500, 125000), (5, 30, 45000), (6, 50, 0),
    ]])
