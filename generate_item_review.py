import os
import csv
from dotenv import load_dotenv
import psycopg2
from rapidfuzz import fuzz

load_dotenv()

NON_FOOD_KEYWORDS = [
    "salary", "wages", "credit", "rent", "chris", "chef sami", "chef feb",
    "mr cudjoe", "mr. cudjoe", "light", "gas ", "gas&", "electric", "cylinder",
    "regulator", "dstv", "socket", "fridge", "stove", "blender", "grinder",
    "fixing", "repair", "electrician", "carpenter", "scaffold", "welding",
    "wall nails", "fire extinguisher", "ice chest", "fan", "chair", "table",
    "mosquito", "fruit picker", "laddle", "banner", "sticker", "printing",
    "transport", "delivery", "madina", "okada", "bowl", "rubber", "foil",
    "tissue", "napkin", "cup", "spoon", "fork", "straw", "sack", "basket",
    "wrapper", "container", "disposable", "takeaway", "take away", "carpet",
    "washing powder", "dettol", "liquid soap", "floor cleaner", "mop",
    "sponge", "soap", "airtime", "powerzone", "matches", "vest", "shirt",
    "gloves", "note book", "notebook", "vermox", "phone repair", "speaker",
    "sticker design", "brandings", "silver", "leaves carpet", "trash",
    "meat grinder", "toothpick", "paper", "gabbage", "iron sponge",
]

def guess_is_food(item):
    lower = item.lower()
    return not any(kw in lower for kw in NON_FOOD_KEYWORDS)

load_dotenv()
conn = psycopg2.connect(
    dbname="sauce_plata",
    user="postgres",
    password=os.getenv("DB_PASSWORD"),
    host="localhost",
    port="5432",
)
cur = conn.cursor()
cur.execute("SELECT item, COUNT(*) FROM staging_purchases GROUP BY item ORDER BY item;")
rows = cur.fetchall()
cur.close()
conn.close()

items = [r[0] for r in rows]
counts = {r[0]: r[1] for r in rows}

# group items whose normalized form is identical (case/whitespace only) automatically
normalized_groups = {}
for item in items:
    key = item.strip().lower()
    normalized_groups.setdefault(key, []).append(item)

# for remaining distinct normalized keys, fuzzy-cluster against each other
norm_keys = list(normalized_groups.keys())
cluster_of = {}  # norm_key -> cluster representative
for i, key in enumerate(norm_keys):
    if key in cluster_of:
        continue
    cluster_of[key] = key
    for other in norm_keys[i+1:]:
        if other in cluster_of:
            continue
        if fuzz.token_sort_ratio(key, other) >= 85:
            cluster_of[other] = key

# already-confirmed decisions from chat review, carried over so they don't need redoing
CONFIRMED = {
    "Adja": ("Adja", "YES"),
    "Adjis": ("Adja", "YES"),
    "Adja 2": ("Adja", "YES"),
    "Adja 4": ("Adja", "YES"),
    "Airtime": ("Airtime", "NO"),
    "Ajinomoto": ("Ajinomoto", "YES"),
}

with open("item_review.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["item", "count", "suggested_standard_name", "is_food_guess", "standard_name", "is_food"])
    for item in items:
        norm = item.strip().lower()
        cluster_rep = cluster_of[norm]
        # pick the most frequent original-case spelling in the cluster as suggested canonical
        cluster_items = [it for k, its in normalized_groups.items() if cluster_of.get(k) == cluster_rep for it in its]
        suggested = max(set(cluster_items), key=lambda x: counts[x])
        confirmed_name, confirmed_food = CONFIRMED.get(item, ("", ""))
        writer.writerow([item, counts[item], suggested, guess_is_food(item), confirmed_name, confirmed_food])

print(f"Wrote item_review.csv with {len(items)} rows.")