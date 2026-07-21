"""
Generates db/seed.sql with realistic fictitious data modeled after
Total Site Services' real service catalog (totalsiteservices.ca):
Site Prep & Development, Drilling & Blasting, Water & Septic,
Landscape & Home, Equipment & Supplies (incl. in-house aggregates).

Run: python3 generate_seed.py
Output: seed.sql (same folder)
"""
import random
from datetime import date, timedelta

random.seed(7)

# --- Service catalog: mirrors the exact site menu -----------------------
SERVICE_CATEGORIES = [
    ("Site Prep & Development", "Site Clearing"),
    ("Site Prep & Development", "Demolition"),
    ("Site Prep & Development", "Backfilling & Excavation"),
    ("Site Prep & Development", "Site Planning & Permitting"),
    ("Site Prep & Development", "Road Building"),
    ("Drilling & Blasting", "Geo-Thermal Drilling"),
    ("Drilling & Blasting", "Blasting"),
    ("Drilling & Blasting", "Quarry & Crushing"),
    ("Water & Septic", "Septic Pumping"),
    ("Water & Septic", "Water Well Drilling"),
    ("Water & Septic", "Septic Design & Installation"),
    ("Landscape & Home", "Driveways"),
    ("Landscape & Home", "Modular Home Construction"),
    ("Landscape & Home", "Landscaping"),
    ("Equipment & Supplies", "Stone Slinger Services"),
    ("Equipment & Supplies", "Heavy Equipment Services"),
    ("Equipment & Supplies", "Aggregate Supply"),
]

EQUIPMENT = [
    ("CAT 320 Excavator", "Excavator", "available", 185.00),
    ("CAT 336 Excavator", "Excavator", "in_use", 210.00),
    ("John Deere 850K Dozer", "Dozer", "available", 195.00),
    ("Atlas Copco Drill Rig #1", "Drill Rig", "available", 260.00),
    ("Atlas Copco Drill Rig #2", "Drill Rig", "maintenance", 260.00),
    ("Blasting Rig Unit A", "Blasting Rig", "available", 320.00),
    ("Vac-Con Septic Truck #1", "Septic Truck", "available", 150.00),
    ("Vac-Con Septic Truck #2", "Septic Truck", "in_use", 150.00),
    ("Stone Slinger Truck #1", "Stone Slinger", "available", 175.00),
    ("Stone Slinger Truck #2", "Stone Slinger", "available", 175.00),
    ("Water Well Rig #1", "Drill Rig", "available", 240.00),
    ("Crusher Plant Unit", "Crusher", "available", 400.00),
]

CLIENTS = [
    ("Sherman & Linda Cooper", "(705) 455-1122", "sherman.cooper@example.com", "1024 Kennisis Lake Rd", "Haliburton"),
    ("Donna & Chris Baker", "(705) 455-2233", "donna.baker@example.com", "88 Grass Lake Rd", "Haliburton"),
    ("Brent & Margaret Rochon", "(705) 789-3344", "brent.rochon@example.com", "212 Bala Falls Rd", "Muskoka"),
    ("Muskoka Lakeside Builders", "(705) 789-4455", "info@muskokalakeside.example.com", "45 Torrance Rd", "Muskoka"),
    ("Haliburton County Cottages Inc.", "(705) 455-5566", "office@hccottages.example.com", "7 Eagle Lake Rd", "Haliburton"),
    ("Pat Simmons", "(705) 789-6677", "pat.simmons@example.com", "301 Muskoka Rd 118", "Muskoka"),
    ("Logan & Erin Whitfield", "(705) 455-7788", "logan.whitfield@example.com", "19 Harburn Rd", "Haliburton"),
]

PROJECT_TYPES = ["New Build", "Driveway", "Septic Install", "Modular Home",
                  "Cottage Renovation", "Land Development", "Road Access"]
PROJECT_STATUSES = ["quoted", "scheduled", "in_progress", "completed", "on_hold"]

AGGREGATES = [
    ("AGG-001", '3/4" Crushed Stone', "ton", 28.00, 950, 150),
    ("AGG-002", '1.5" Crushed Stone', "ton", 26.50, 720, 150),
    ("AGG-003", "Clear Stone", "ton", 32.00, 480, 100),
    ("AGG-004", "Pit Run Gravel", "ton", 19.00, 1100, 200),
    ("AGG-005", "Granular A", "ton", 24.00, 860, 150),
    ("AGG-006", "Granular B", "ton", 21.00, 900, 150),
    ("AGG-007", "Screened Sand", "ton", 22.50, 540, 100),
    ("AGG-008", "Screened Topsoil", "yard", 35.00, 300, 60),
    ("AGG-009", "Fill Material", "yard", 15.00, 640, 120),
    ("AGG-010", "Armour Stone (large)", "ton", 65.00, 150, 30),
]

def rand_date_within(days_back, days_fwd=0):
    return date.today() - timedelta(days=random.randint(-days_fwd, days_back))

def esc(s):
    return s.replace("'", "''")

lines = []
lines.append("-- Seed data (fictitious) — Intelligent Site Services Copilot")
lines.append("-- Modeled after totalsiteservices.ca real service catalog\n")
lines.append("BEGIN;\n")

lines.append("INSERT INTO service_categories (group_name, name) VALUES")
rows = [f"('{esc(g)}', '{esc(n)}')" for g, n in SERVICE_CATEGORIES]
lines.append(",\n".join(rows) + ";\n")

lines.append("INSERT INTO equipment (name, type, status, hourly_rate, last_service_date) VALUES")
rows = []
for name, etype, status, rate in EQUIPMENT:
    d = rand_date_within(120)
    rows.append(f"('{esc(name)}', '{etype}', '{status}', {rate}, '{d.isoformat()}')")
lines.append(",\n".join(rows) + ";\n")

lines.append("INSERT INTO clients (name, phone, email, address, municipality) VALUES")
rows = [f"('{esc(n)}', '{p}', '{e}', '{esc(a)}', '{m}')" for n, p, e, a, m in CLIENTS]
lines.append(",\n".join(rows) + ";\n")

lines.append("INSERT INTO projects (client_id, site_address, project_type, status, start_date, est_completion) VALUES")
rows = []
project_count = 0
for ci, (n, p, e, a, m) in enumerate(CLIENTS, start=1):
    for _ in range(random.randint(1, 3)):
        ptype = random.choice(PROJECT_TYPES)
        status = random.choice(PROJECT_STATUSES)
        start = rand_date_within(150, 30)
        est = start + timedelta(days=random.randint(10, 90))
        rows.append(f"({ci}, '{esc(a)}', '{ptype}', '{status}', '{start.isoformat()}', '{est.isoformat()}')")
        project_count += 1
lines.append(",\n".join(rows) + ";\n")

lines.append("INSERT INTO permits (project_id, permit_type, status, submitted_date, approved_date, notes) VALUES")
permit_types = ["Septic Permit", "Building Permit", "Blasting Permit", "Site Alteration Permit"]
permit_statuses = ["pending", "submitted", "approved", "rejected"]
rows = []
for pid in range(1, project_count + 1):
    if random.random() < 0.55:
        ptype = random.choice(permit_types)
        status = random.choice(permit_statuses)
        submitted = rand_date_within(120)
        if status == "approved":
            approved_sql = f"'{(submitted + timedelta(days=random.randint(5, 25))).isoformat()}'"
        else:
            approved_sql = "NULL"
        rows.append(f"({pid}, '{ptype}', '{status}', '{submitted.isoformat()}', {approved_sql}, 'Auto-generated demo record')")
lines.append(",\n".join(rows) + ";\n")

lines.append("INSERT INTO service_requests (project_id, service_category_id, equipment_id, crew_name, scheduled_date, completed_date, status, estimated_cost, final_cost, notes) VALUES")
crews = ["Crew A", "Crew B", "Crew C", "North Crew", "South Crew"]
sr_statuses = ["scheduled", "in_progress", "completed", "cancelled"]
rows = []
for pid in range(1, project_count + 1):
    for _ in range(random.randint(1, 3)):
        cat_id = random.randint(1, len(SERVICE_CATEGORIES))
        eq_id = random.randint(1, len(EQUIPMENT)) if random.random() < 0.8 else "NULL"
        crew = random.choice(crews)
        sched = rand_date_within(100, 45)
        status = random.choice(sr_statuses)
        if status == "completed":
            completed_sql = f"'{(sched + timedelta(days=random.randint(0, 5))).isoformat()}'"
        else:
            completed_sql = "NULL"
        est_cost = round(random.uniform(800, 15000), 2)
        final_cost_sql = round(est_cost * random.uniform(0.9, 1.15), 2) if status == "completed" else "NULL"
        rows.append(
            f"({pid}, {cat_id}, {eq_id}, '{crew}', '{sched.isoformat()}', {completed_sql}, "
            f"'{status}', {est_cost}, {final_cost_sql}, 'Demo record')"
        )
lines.append(",\n".join(rows) + ";\n")

lines.append("INSERT INTO aggregates (sku, name, unit, unit_price, stock_qty, reorder_point, source, last_updated) VALUES")
rows = []
for sku, name, unit, price, stock, reorder in AGGREGATES:
    d = rand_date_within(10)
    rows.append(f"('{sku}', '{esc(name)}', '{unit}', {price}, {stock}, {reorder}, 'in-house crushing plant', '{d.isoformat()}')")
lines.append(",\n".join(rows) + ";\n")

lines.append("INSERT INTO aggregate_price_history (aggregate_id, price, recorded_at) VALUES")
rows = []
for i, (sku, name, unit, price, stock, reorder) in enumerate(AGGREGATES, start=1):
    p = price
    for m in range(6, 0, -1):
        d = date.today() - timedelta(days=30 * m)
        p = round(p * (1 + random.uniform(-0.02, 0.04)), 2)
        rows.append(f"({i}, {p}, '{d.isoformat()}')")
lines.append(",\n".join(rows) + ";\n")

lines.append("INSERT INTO aggregate_orders (aggregate_id, client_id, project_id, quantity, total_price, delivery_date) VALUES")
rows = []
for _ in range(180):
    agg_idx = random.randint(1, len(AGGREGATES))
    _, _, unit, price, _, _ = AGGREGATES[agg_idx - 1]
    qty = round(random.uniform(2, 40), 2)
    total = round(qty * price, 2)
    client_id = random.randint(1, len(CLIENTS))
    project_id = random.randint(1, project_count) if random.random() < 0.7 else "NULL"
    d = rand_date_within(90)
    rows.append(f"({agg_idx}, {client_id}, {project_id}, {qty}, {total}, '{d.isoformat()}')")
lines.append(",\n".join(rows) + ";\n")

lines.append("COMMIT;\n")

with open("seed.sql", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"seed.sql generated. Projects: {project_count}")
