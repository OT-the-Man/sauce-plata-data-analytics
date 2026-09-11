import csv

with open("item_review.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

problems = []
for i, row in enumerate(rows, start=2):  # row 2 = first data row in Excel
    name = row["standard_name"].strip()
    food = row["is_food"].strip().upper()
    if not name:
        problems.append(f"Row {i} ({row['item']}): standard_name is blank")
    if food not in ("YES", "NO"):
        problems.append(f"Row {i} ({row['item']}): is_food is '{row['is_food']}', must be YES or NO")

print(f"Checked {len(rows)} rows.")
if problems:
    print(f"{len(problems)} problems found:")
    for p in problems[:30]:
        print(" -", p)
    if len(problems) > 30:
        print(f"   ...and {len(problems) - 30} more")
else:
    print("All rows valid.")