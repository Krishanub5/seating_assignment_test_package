from __future__ import annotations

import csv
import random
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path('/mnt/data')
INPUT = BASE / 'synthetic_attendees_575.csv'
OUTDIR = BASE / 'test_575_output'
REPORT = BASE / 'test_575_validation_report.md'

rng = random.Random(5752026)

first_names = [
    'Aaron','Aisha','Akash','Alvin','Amelia','Ananya','Andre','Arjun','Benjamin','Brandon',
    'Caroline','Cheryl','Clarissa','Daniel','Darren','Deepak','Derrick','Dev','Dinesh','Eileen',
    'Elaine','Ethan','Farah','Farid','Felix','Gavin','Grace','Harish','Hazel','Ibrahim',
    'Irene','Jasmine','Jia Hui','Jonathan','Karthik','Kavya','Keith','Ken','Kiran','Krishna',
    'Lina','Marcus','Meera','Melissa','Muhammad','Nadia','Natalie','Nicholas','Nur','Olivia',
    'Prakash','Priya','Rahul','Rachel','Ravi','Sanjay','Siti','Sophia','Terence','Vikram',
    'Wei Ling','Xavier','Yasmin','Yong Wei','Zara','Alicia','Bala','Catherine','Daryl','Evan',
    'Fiona','Gaurav','Hannah','Ivan','Janice','Khalid','Lavanya','Maya','Naveen','Omar',
    'Pooja','Qistina','Ramesh','Sharon','Tanvi','Uma','Vijay','Wen Jie','Yvonne','Zhen',
]
last_names = [
    'Tan','Lim','Wong','Lee','Goh','Ng','Chua','Koh','Low','Teo','Kumar','Singh','Das','Roy',
    'Raman','Iyer','Nair','Sharma','Patel','Reddy','Ahmad','Hassan','Ismail','Rahman','Yusof',
    'Omar','Mohamed','Khan','Aziz','Pereira','Fernandes','D Souza','Taylor','Chan','Chew',
]
departments = [
    'Technology','Cloud Engineering','Cybersecurity','Data & Analytics','Finance','Human Resources',
    'Operations','Sales','Marketing','Customer Experience','Legal','Procurement','Product','Risk & Compliance',
]

people: list[dict[str, str]] = []
used_names: Counter[str] = Counter()


def make_name(index: int) -> str:
    base = f"{first_names[index % len(first_names)]} {last_names[(index * 7 + index // 3) % len(last_names)]}"
    used_names[base] += 1
    # Use a middle initial only when a generated full name would repeat.
    if used_names[base] == 1:
        return base
    initial = chr(ord('A') + (used_names[base] - 2) % 26)
    return f"{first_names[index % len(first_names)]} {initial}. {last_names[(index * 7 + index // 3) % len(last_names)]}"


def add_people(count: int, meal: str, diet: str, group_id: str = '') -> None:
    for _ in range(count):
        idx = len(people) + 1
        people.append({
            'person_id': f'P{idx:04d}',
            'name': make_name(idx - 1),
            'department': departments[(idx * 5 + idx // 7) % len(departments)],
            'meal': meal,
            'diet': diet,
            'group_id': group_id,
        })

# Explicit 10 non-vegetarian + 1 vegetarian requested table.
add_people(10, 'regular', 'non_vegetarian', 'MIXED_10NV_1V')
add_people(1, 'regular', 'vegetarian', 'MIXED_10NV_1V')

# Full and partial regular non-vegetarian groups.
for group_id, size in [
    ('TEAM_ALPHA', 10), ('TEAM_BRAVO', 10), ('TEAM_CHARLIE', 10), ('TEAM_DELTA', 10), ('TEAM_ECHO', 10),
    ('PROJECT_ORBIT', 8), ('PROJECT_NOVA', 8),
    ('CLOUD_GUILD', 6), ('DATA_CREW', 6), ('OPS_SQUAD', 6), ('SECURITY_TEAM', 6),
    ('PLATFORM_PALS', 4), ('FINANCE_FOUR', 4), ('PEOPLE_TEAM', 4),
    ('MARKETING_TRIO', 3), ('SALES_TRIO', 3),
]:
    add_people(size, 'regular', 'non_vegetarian', group_id)

# Regular non-vegetarian attendees with no seating request.
add_people(367, 'regular', 'non_vegetarian')

# Full and partial vegetarian groups.
for group_id, size in [
    ('VEG_TABLE_A', 10), ('VEG_FRIENDS', 8), ('DESIGN_VEG', 6),
    ('CULTURE_VEG', 5), ('GREEN_TEAM', 4), ('HEALTH_VEG', 3),
]:
    add_people(size, 'regular', 'vegetarian', group_id)

# Regular vegetarian attendees with no seating request.
add_people(33, 'regular', 'vegetarian')

# Two halal-only, non-vegetarian tables. Group sizes are intentionally packable into 10 + 10.
for group_id, size in [
    ('HALAL_EAST', 7), ('HALAL_NORTH', 6), ('HALAL_NORTH_SUPPORT', 4), ('HALAL_EAST_SUPPORT', 3),
]:
    add_people(size, 'halal', 'non_vegetarian', group_id)

assert len(people) == 575
assert sum(p['meal'] == 'halal' for p in people) == 20
assert sum(p['meal'] == 'regular' and p['diet'] == 'non_vegetarian' for p in people) == 485
assert sum(p['meal'] == 'regular' and p['diet'] == 'vegetarian' for p in people) == 70

# Shuffle source order to mimic registration order, without changing IDs/names.
rng.shuffle(people)

with INPUT.open('w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['person_id', 'name', 'department', 'meal', 'diet', 'group_id'])
    writer.writeheader()
    writer.writerows(people)

# Validate program output independently.
assignments_file = OUTDIR / 'table_assignments.csv'
summary_file = OUTDIR / 'table_summary.csv'
if not assignments_file.exists() or not summary_file.exists():
    raise SystemExit('Expected program output files do not exist.')

with assignments_file.open(encoding='utf-8', newline='') as f:
    assignments = list(csv.DictReader(f))
with summary_file.open(encoding='utf-8', newline='') as f:
    summaries = list(csv.DictReader(f))

errors: list[str] = []
source_ids = {p['person_id'] for p in people}
assigned_ids = [r['person_id'] for r in assignments]
if len(assignments) != 575:
    errors.append(f'Expected 575 assignment rows; found {len(assignments)}.')
if set(assigned_ids) != source_ids:
    errors.append('Assigned person IDs do not exactly match the source attendee list.')
if len(assigned_ids) != len(set(assigned_ids)):
    errors.append('At least one attendee was assigned more than once.')

by_table: dict[str, list[dict[str, str]]] = defaultdict(list)
for row in assignments:
    by_table[row['table_id']].append(row)

# Table-level rules.
for table_id, rows in by_table.items():
    meal = {r['meal'] for r in rows}
    if len(meal) != 1:
        errors.append(f'{table_id}: has multiple meal types.')
        continue
    meal_value = next(iter(meal))
    nv = sum(r['diet'] == 'non_vegetarian' for r in rows)
    veg = sum(r['diet'] == 'vegetarian' for r in rows)
    if meal_value == 'halal':
        if len(rows) > 10 or nv != len(rows) or veg != 0:
            errors.append(f'{table_id}: invalid halal configuration ({nv} NV, {veg} veg, {len(rows)} total).')
    elif veg > 0 and nv > 0:
        if not (nv == 10 and veg == 1 and len(rows) == 11):
            errors.append(f'{table_id}: invalid regular mixed configuration ({nv} NV, {veg} veg).')
    elif veg > 0:
        if len(rows) > 10:
            errors.append(f'{table_id}: vegetarian-only table exceeds 10 seats.')
    else:
        if len(rows) > 10:
            errors.append(f'{table_id}: non-vegetarian table exceeds 10 seats.')

# Requested group rule.
group_tables: dict[str, set[str]] = defaultdict(set)
source_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
for p in people:
    if p['group_id']:
        source_groups[p['group_id']].append(p)
for row in assignments:
    if row['group_id']:
        group_tables[row['group_id']].add(row['table_id'])
for group_id, member_rows in source_groups.items():
    if len(group_tables[group_id]) != 1:
        errors.append(f'{group_id}: group was split across {sorted(group_tables[group_id])}.')

halal_tables_used = sorted(table_id for table_id, rows in by_table.items() if rows and rows[0]['meal'] == 'halal')
if len(halal_tables_used) != 2:
    errors.append(f'Expected exactly two used halal tables; found {len(halal_tables_used)}.')
if sum(len(by_table[t]) for t in halal_tables_used) != 20:
    errors.append('Halal attendee total in assignments is not 20.')

summary_rows_assigned = [row for row in summaries if row['status'] == 'Assigned']
full_tables = sum(int(row['assigned_people']) == int(row['capacity']) for row in summary_rows_assigned)
part_tables = len(summary_rows_assigned) - full_tables
regular_summary = [r for r in summaries if r['meal'] == 'regular' and r['status'] == 'Assigned']
halal_summary = [r for r in summaries if r['meal'] == 'halal' and r['status'] == 'Assigned']

with REPORT.open('w', encoding='utf-8') as f:
    f.write('# Synthetic 575-Attendee Seating Test\n\n')
    f.write('**Result:** ' + ('PASS' if not errors else 'FAIL') + '\n\n')
    f.write('## Test Data\n\n')
    f.write('- Total attendees: **575**\n')
    f.write('- Regular non-vegetarian: **485**\n')
    f.write('- Regular vegetarian: **70**\n')
    f.write('- Halal non-vegetarian: **20** across exactly two halal tables\n')
    f.write('- Halal vegetarian: **0**\n')
    f.write('- Requested-group patterns included: full 10-person groups, groups below 10, one 10 non-vegetarian + 1 vegetarian group, full 10-person vegetarian group, and halal groups.\n\n')
    f.write('## Assignment Results\n\n')
    f.write(f'- Assignment rows: **{len(assignments)}**\n')
    f.write(f'- Used tables: **{len(summary_rows_assigned)}**\n')
    f.write(f'- Regular tables used: **{len(regular_summary)}**\n')
    f.write(f'- Halal tables used: **{len(halal_summary)} of 2**\n')
    f.write(f'- Full tables: **{full_tables}**\n')
    f.write(f'- Partially filled tables: **{part_tables}**\n')
    f.write(f'- Randomisation seed: **5752026**\n\n')
    f.write('## Independent Rule Validation\n\n')
    if errors:
        for e in errors:
            f.write(f'- FAIL: {e}\n')
    else:
        f.write('- PASS: Every source attendee appears exactly once in the seating output.\n')
        f.write('- PASS: Every requested group remains at one table.\n')
        f.write('- PASS: Regular non-vegetarian tables do not exceed 10 guests.\n')
        f.write('- PASS: Vegetarian-only tables do not exceed 10 guests.\n')
        f.write('- PASS: The only mixed table uses exactly 10 non-vegetarians + 1 vegetarian.\n')
        f.write('- PASS: The two halal tables contain only halal non-vegetarian guests, 10 people each.\n')

print(f'Generated: {INPUT}')
print(f'Validation report written: {REPORT}')
print(f'Errors: {len(errors)}')
if errors:
    for e in errors:
        print('ERROR:', e)
    raise SystemExit(1)
