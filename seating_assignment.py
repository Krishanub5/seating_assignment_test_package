#!/usr/bin/env python3
"""Dinner seating assignment tool.

Rules implemented
-----------------
1. Non-vegetarian tables seat up to 10 non-vegetarians.
2. A non-vegetarian table may have one additional vegetarian only when it
   contains exactly 10 non-vegetarians (10+1 configuration).
3. A group_id keeps all members of that group at one table.
4. Vegetarian-only tables seat up to 10 vegetarians.
5. Groups smaller than a full table are kept together and may share a table
   with other compatible groups/guests.
6. Mixed requested groups are valid only when they are exactly 10
   non-vegetarians + 1 vegetarian. This is the strict interpretation of the
   10+1 rule.
7. Guests without group_id are shuffled with guests who have the same meal
   type and dietary type, then assigned automatically.
8. Exactly two halal-only tables are reserved by default. Halal tables accept
   non-vegetarian halal meals only, up to 10 people per table (20 in total).

Input CSV (recommended)
-----------------------
person_id,name,meal,diet,group_id
P001,Alex,regular,non_vegetarian,GROUP_A
P002,Bea,regular,vegetarian,
P003,Farid,halal,non_vegetarian,HALAL_1

meal: regular | halal
diet: non_vegetarian | vegetarian

Halal attendees must use diet=non_vegetarian. Halal vegetarian entries are not
allowed because the two halal tables serve halal non-vegetarian food only.
group_id: blank means no seating request.

You can use dietary_requirement instead of meal + diet, for example:
regular_non_vegetarian, regular_vegetarian, halal_non_vegetarian,
halal_vegetarian.

Usage
-----
python seating_assignment.py --input attendees.csv --outdir output --seed 2026

Optional --allow-auto-mixed-seating assigns ungrouped vegetarian guests to a
full table of 10 non-vegetarians. Keep this OFF unless the event policy allows
vegetarian guests to be placed with non-vegetarian guests without an explicit
shared group request.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


REGULAR = "regular"
HALAL = "halal"
NV = "non_vegetarian"
VEG = "vegetarian"


class SeatingError(Exception):
    """Raised when input cannot be assigned without breaking the rules."""

    def __init__(self, issues: list[dict[str, str]]):
        super().__init__("Seating assignment cannot be completed.")
        self.issues = issues


@dataclass(frozen=True)
class Person:
    person_id: str
    name: str
    meal: str
    diet: str
    group_id: str = ""


@dataclass
class Unit:
    """An indivisible requested group or one ungrouped attendee."""

    unit_id: str
    members: list[Person]
    meal: str
    kind: str  # nv, veg, mixed
    requested: bool
    group_id: str = ""

    @property
    def size(self) -> int:
        return len(self.members)

    @property
    def assignment_basis(self) -> str:
        return "requested_group" if self.requested else "dietary_random"


@dataclass
class Table:
    table_id: str
    meal: str
    mode: str  # non_vegetarian, vegetarian, mixed
    members: list[tuple[Person, str]] = field(default_factory=list)

    @property
    def nv_count(self) -> int:
        return sum(1 for person, _ in self.members if person.diet == NV)

    @property
    def veg_count(self) -> int:
        return sum(1 for person, _ in self.members if person.diet == VEG)

    @property
    def capacity(self) -> int:
        # Halal tables are strictly non-vegetarian and never use a +1 seat.
        if self.meal == HALAL:
            return 10
        if self.mode == "mixed":
            return 11
        return 10

    @property
    def configuration(self) -> str:
        if self.meal == HALAL:
            return "Halal non-vegetarian (up to 10)"
        if self.mode == "vegetarian":
            return "Vegetarian-only (up to 10)"
        if self.mode == "mixed":
            return "10 non-vegetarian + 1 vegetarian"
        return "Non-vegetarian (up to 10)"

    @property
    def remaining(self) -> int:
        return self.capacity - len(self.members)

    def can_fit(self, unit: Unit) -> bool:
        if self.meal != unit.meal:
            return False
        if self.meal == HALAL:
            return unit.kind == "nv" and self.nv_count + unit.size <= 10
        if self.mode == "vegetarian":
            return unit.kind == "veg" and self.veg_count + unit.size <= 10
        if self.mode == "non_vegetarian":
            return unit.kind == "nv" and self.nv_count + unit.size <= 10
        # A mixed table only represents one approved 10+1 group.
        return False

    def add(self, unit: Unit, basis: str | None = None) -> None:
        if not self.can_fit(unit):
            raise ValueError(f"Unit {unit.unit_id} cannot be seated at {self.table_id}.")
        basis = basis or unit.assignment_basis
        self.members.extend((person, basis) for person in unit.members)

    def add_auto_vegetarian(self, unit: Unit) -> None:
        if (
            self.meal != REGULAR
            or self.mode != "non_vegetarian"
            or self.nv_count != 10
            or unit.kind != "veg"
            or unit.size != 1
            or unit.requested
        ):
            raise ValueError("Automatic mixed seating requires one ungrouped vegetarian and 10 non-vegetarians.")
        self.mode = "mixed"
        self.members.extend((person, "automatic_mixed_seating") for person in unit.members)


def normalize_value(value: str) -> str:
    return "_".join(value.strip().lower().replace("-", " ").split())


def normalize_meal(value: str) -> str:
    value = normalize_value(value)
    aliases = {
        "regular": REGULAR,
        "normal": REGULAR,
        "standard": REGULAR,
        "halal": HALAL,
    }
    if value not in aliases:
        raise ValueError("meal must be regular or halal")
    return aliases[value]


def normalize_diet(value: str) -> str:
    value = normalize_value(value)
    if value in {"non_vegetarian", "nonvegetarian", "non_veg", "nonveg", "nv"}:
        return NV
    if value in {"vegetarian", "veg", "v"}:
        return VEG
    raise ValueError("diet must be non_vegetarian or vegetarian")


def parse_dietary_requirement(value: str) -> tuple[str, str]:
    """Parse dietary labels; halal_vegetarian is parsed then rejected by seating rules."""
    norm = normalize_value(value)
    if not norm:
        raise ValueError("dietary_requirement is empty")

    meal = HALAL if "halal" in norm.split("_") else REGULAR
    # Check non-vegetarian before vegetarian because of the shared word.
    if any(token in norm for token in ("non_vegetarian", "nonvegetarian", "non_veg", "nonveg")):
        diet = NV
    elif norm in {"vegetarian", "veg", "regular_vegetarian", "halal_vegetarian"} or norm.endswith("_vegetarian"):
        diet = VEG
    else:
        raise ValueError(
            "dietary_requirement must identify vegetarian or non_vegetarian "
            "(for example regular_non_vegetarian)"
        )
    return meal, diet


def issue(row: int | str, code: str, message: str, group_id: str = "") -> dict[str, str]:
    return {"row": str(row), "code": code, "group_id": group_id, "message": message}


def read_people(path: Path) -> list[Person]:
    issues: list[dict[str, str]] = []
    people: list[Person] = []
    seen_ids: set[str] = set()

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise SeatingError([issue("header", "EMPTY_FILE", "The CSV has no header row.")])

            headers = {header.strip().lower() for header in reader.fieldnames if header}
            required = {"person_id", "name"}
            missing = required - headers
            if missing:
                raise SeatingError([
                    issue("header", "MISSING_COLUMN", f"Missing required column(s): {', '.join(sorted(missing))}.")
                ])
            has_split_diet = {"meal", "diet"}.issubset(headers)
            has_combined_diet = "dietary_requirement" in headers
            if not has_split_diet and not has_combined_diet:
                raise SeatingError([
                    issue(
                        "header",
                        "MISSING_DIET_COLUMNS",
                        "Provide meal + diet columns, or a dietary_requirement column.",
                    )
                ])

            for row_number, raw in enumerate(reader, start=2):
                row = {(key or "").strip().lower(): (value or "").strip() for key, value in raw.items()}
                person_id = row.get("person_id", "")
                name = row.get("name", "")
                group_id = row.get("group_id", "").strip()
                if not person_id or not name:
                    issues.append(issue(row_number, "MISSING_PERSON_DETAILS", "person_id and name are required.", group_id))
                    continue
                if person_id in seen_ids:
                    issues.append(issue(row_number, "DUPLICATE_PERSON_ID", f"person_id '{person_id}' appears more than once.", group_id))
                    continue
                try:
                    if has_split_diet and row.get("meal") and row.get("diet"):
                        meal = normalize_meal(row["meal"])
                        diet = normalize_diet(row["diet"])
                    elif has_combined_diet:
                        meal, diet = parse_dietary_requirement(row.get("dietary_requirement", ""))
                    else:
                        raise ValueError("Provide values for both meal and diet, or dietary_requirement.")
                except ValueError as exc:
                    issues.append(issue(row_number, "INVALID_DIETARY_DATA", str(exc), group_id))
                    continue

                seen_ids.add(person_id)
                people.append(Person(person_id, name, meal, diet, group_id))
    except FileNotFoundError:
        raise SeatingError([issue("file", "INPUT_NOT_FOUND", f"Input file not found: {path}")])

    if issues:
        raise SeatingError(issues)
    if not people:
        raise SeatingError([issue("file", "NO_ATTENDEES", "No valid attendees were found.")])
    return people


def make_units(people: list[Person]) -> list[Unit]:
    # The two reserved halal tables provide halal non-vegetarian food only.
    # Reject invalid halal-vegetarian records before table assignment.
    halal_vegetarians = [person for person in people if person.meal == HALAL and person.diet == VEG]
    if halal_vegetarians:
        raise SeatingError([
            issue(
                person.person_id,
                "HALAL_VEGETARIAN_NOT_SUPPORTED",
                "Halal tables serve non-vegetarian halal food only. Change this attendee to regular vegetarian or remove the halal meal request.",
                person.group_id,
            )
            for person in halal_vegetarians
        ])

    issues: list[dict[str, str]] = []
    grouped: dict[str, list[Person]] = {}
    singles: list[Person] = []

    for person in people:
        if person.group_id:
            grouped.setdefault(person.group_id, []).append(person)
        else:
            singles.append(person)

    units: list[Unit] = []
    for group_id, members in grouped.items():
        meals = {member.meal for member in members}
        diets = [member.diet for member in members]
        nv_count = diets.count(NV)
        veg_count = diets.count(VEG)

        if len(meals) != 1:
            issues.append(issue("group", "GROUP_CROSSES_MEAL_TYPES", "All members of one group_id must have the same meal type (regular or halal).", group_id))
            continue
        if len(members) > 11:
            issues.append(issue("group", "GROUP_TOO_LARGE", "A requested group cannot exceed 11 seats.", group_id))
            continue

        if nv_count and not veg_count and nv_count <= 10:
            kind = "nv"
        elif veg_count and not nv_count and veg_count <= 10:
            kind = "veg"
        elif next(iter(meals)) == REGULAR and nv_count == 10 and veg_count == 1:
            kind = "mixed"
        else:
            issues.append(
                issue(
                    "group",
                    "INVALID_MIXED_GROUP",
                    "A mixed dietary group is allowed only as exactly 10 non-vegetarians + 1 vegetarian. "
                    "Use separate group_id values or revise the request.",
                    group_id,
                )
            )
            continue

        units.append(Unit(group_id, members, next(iter(meals)), kind, True, group_id))

    for person in singles:
        units.append(Unit(f"SINGLE_{person.person_id}", [person], person.meal, "nv" if person.diet == NV else "veg", False))

    if issues:
        raise SeatingError(issues)
    return units


def pack_units(units: list[Unit], meal: str, kind: str, prefix: str, start_number: int, rng: random.Random) -> list[Table]:
    """Best-fit decreasing packing while preserving every unit intact."""
    selected = [unit for unit in units if unit.meal == meal and unit.kind == kind]
    decorated = [(unit.size, rng.random(), unit) for unit in selected]
    decorated.sort(key=lambda item: (-item[0], item[1]))

    tables: list[Table] = []
    for _, _, unit in decorated:
        candidates = [table for table in tables if table.can_fit(unit)]
        if candidates:
            # Best fit: use the compatible table with the least remaining space after placement.
            target = min(candidates, key=lambda table: (table.remaining - unit.size, table.table_id))
        else:
            table_number = start_number + len(tables)
            mode = "vegetarian" if kind == "veg" else "non_vegetarian"
            target = Table(f"{prefix}-{table_number:02d}", meal, mode)
            tables.append(target)
        target.add(unit)
    return tables


def build_tables(
    units: list[Unit],
    meal: str,
    prefix: str,
    rng: random.Random,
    allow_auto_mixed: bool,
) -> list[Table]:
    # Halal tables are strictly non-vegetarian, capacity 10 per table.
    if meal == HALAL:
        return pack_units(units, HALAL, "nv", prefix, 1, rng)

    tables: list[Table] = []
    next_number = 1

    # A valid explicitly requested 10+1 group receives its own table.
    mixed_units = [unit for unit in units if unit.meal == meal and unit.kind == "mixed"]
    rng.shuffle(mixed_units)
    for unit in mixed_units:
        table = Table(f"{prefix}-{next_number:02d}", meal, "mixed")
        # mixed tables are intentionally created only for exact 10+1 units.
        table.members.extend((person, unit.assignment_basis) for person in unit.members)
        tables.append(table)
        next_number += 1

    nv_tables = pack_units(units, meal, "nv", prefix, next_number, rng)
    tables.extend(nv_tables)
    next_number += len(nv_tables)

    veg_units = [unit for unit in units if unit.meal == meal and unit.kind == "veg"]
    if allow_auto_mixed:
        # Only ungrouped vegetarian guests may be automatically placed with a full NV table.
        eligible_veg = [unit for unit in veg_units if not unit.requested and unit.size == 1]
        remaining_veg = [unit for unit in veg_units if unit not in eligible_veg]
        rng.shuffle(eligible_veg)
        full_nv_tables = [table for table in nv_tables if table.nv_count == 10]
        rng.shuffle(full_nv_tables)
        for table, veg_unit in zip(full_nv_tables, eligible_veg):
            table.add_auto_vegetarian(veg_unit)
        used = min(len(full_nv_tables), len(eligible_veg))
        veg_units = remaining_veg + eligible_veg[used:]

    # Pack remaining vegetarians into vegetarian-only tables.
    veg_tables = pack_units(veg_units, meal, "veg", prefix, next_number, rng)
    tables.extend(veg_tables)
    return tables


def assign_people(people: list[Person], seed: int, halal_table_limit: int, allow_auto_mixed: bool) -> list[Table]:
    units = make_units(people)
    rng = random.Random(seed)

    regular_tables = build_tables(units, REGULAR, "R", rng, allow_auto_mixed)
    halal_tables = build_tables(units, HALAL, "H", rng, allow_auto_mixed)

    issues: list[dict[str, str]] = []
    halal_people = sum(1 for person in people if person.meal == HALAL)
    if halal_people > halal_table_limit * 10:
        issues.append(
            issue(
                "halal",
                "HALAL_SEAT_CAPACITY_EXCEEDED",
                f"{halal_people} halal non-vegetarian guests were supplied, but {halal_table_limit} halal tables can seat at most {halal_table_limit * 10} people.",
            )
        )
    if len(halal_tables) > halal_table_limit:
        issues.append(
            issue(
                "halal",
                "HALAL_TABLE_LIMIT_EXCEEDED",
                f"The halal seating pattern requires {len(halal_tables)} tables, but only {halal_table_limit} are reserved. "
                f"This can happen even below {halal_table_limit * 10} guests when group rules prevent compatible sharing.",
            )
        )

    if issues:
        raise SeatingError(issues)

    # Include unused reserved halal tables in the report for catering visibility.
    for table_number in range(len(halal_tables) + 1, halal_table_limit + 1):
        halal_tables.append(Table(f"H-{table_number:02d}", HALAL, "non_vegetarian"))

    return regular_tables + halal_tables


def table_group_ids(table: Table) -> str:
    groups = sorted({person.group_id for person, _ in table.members if person.group_id})
    return "; ".join(groups)


def write_outputs(tables: list[Table], outdir: Path, attendees: int, seed: int, halal_table_limit: int) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    assignment_file = outdir / "table_assignments.csv"
    with assignment_file.open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "table_id", "meal", "table_configuration", "seat_number", "person_id", "name",
            "diet", "group_id", "assignment_basis",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for table in tables:
            for seat, (person, basis) in enumerate(table.members, start=1):
                writer.writerow({
                    "table_id": table.table_id,
                    "meal": table.meal,
                    "table_configuration": table.configuration,
                    "seat_number": seat,
                    "person_id": person.person_id,
                    "name": person.name,
                    "diet": person.diet,
                    "group_id": person.group_id,
                    "assignment_basis": basis,
                })

    summary_file = outdir / "table_summary.csv"
    with summary_file.open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "table_id", "meal", "table_configuration", "assigned_people", "capacity",
            "empty_seats", "non_vegetarian_count", "vegetarian_count", "requested_group_ids", "status",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for table in tables:
            assigned = len(table.members)
            status = "Unused reserved halal table" if table.meal == HALAL and assigned == 0 else "Assigned"
            writer.writerow({
                "table_id": table.table_id,
                "meal": table.meal,
                "table_configuration": table.configuration,
                "assigned_people": assigned,
                "capacity": table.capacity,
                "empty_seats": table.capacity - assigned,
                "non_vegetarian_count": table.nv_count,
                "vegetarian_count": table.veg_count,
                "requested_group_ids": table_group_ids(table),
                "status": status,
            })

    report_file = outdir / "assignment_report.txt"
    total_tables = sum(1 for table in tables if table.members)
    regular_tables = [table for table in tables if table.meal == REGULAR and table.members]
    halal_tables = [table for table in tables if table.meal == HALAL and table.members]
    with report_file.open("w", encoding="utf-8") as handle:
        handle.write("Dinner Seating Assignment Report\n")
        handle.write("=" * 32 + "\n")
        handle.write(f"Attendees assigned: {attendees}\n")
        handle.write(f"Tables used: {total_tables}\n")
        handle.write(f"Regular tables used: {len(regular_tables)}\n")
        handle.write(f"Halal tables used: {len(halal_tables)} of {halal_table_limit} reserved\n")
        handle.write(f"Randomisation seed: {seed}\n\n")
        for table in tables:
            if not table.members:
                continue
            handle.write(
                f"{table.table_id} | {table.meal} | {table.configuration} | "
                f"{len(table.members)}/{table.capacity}\n"
            )
            for person, basis in table.members:
                group_text = f" | group {person.group_id}" if person.group_id else ""
                handle.write(f"  - {person.name} ({person.diet}; {basis}{group_text})\n")
            handle.write("\n")


def write_issues(issues: Iterable[dict[str, str]], outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    file_path = outdir / "exceptions.csv"
    with file_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["row", "code", "group_id", "message"])
        writer.writeheader()
        writer.writerows(issues)
    return file_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assign dinner guests to tables under dietary and group rules.")
    parser.add_argument("--input", required=True, type=Path, help="Input attendee CSV file.")
    parser.add_argument("--outdir", default=Path("seating_output"), type=Path, help="Folder for output CSVs.")
    parser.add_argument("--seed", default=20260821, type=int, help="Randomisation seed for repeatable assignments.")
    parser.add_argument("--halal-tables", default=2, type=int, help="Number of reserved halal-only tables (default: 2).")
    parser.add_argument(
        "--allow-auto-mixed-seating",
        action="store_true",
        help="Allow ungrouped vegetarian guests to use the 11th seat at a full table of 10 non-vegetarians.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.halal_tables < 0:
        print("--halal-tables cannot be negative.", file=sys.stderr)
        return 2

    try:
        people = read_people(args.input)
        tables = assign_people(
            people,
            seed=args.seed,
            halal_table_limit=args.halal_tables,
            allow_auto_mixed=args.allow_auto_mixed_seating,
        )
        write_outputs(
            tables,
            args.outdir,
            attendees=len(people),
            seed=args.seed,
            halal_table_limit=args.halal_tables,
        )
    except SeatingError as exc:
        issue_file = write_issues(exc.issues, args.outdir)
        print("Assignment stopped because one or more rules cannot be met.", file=sys.stderr)
        print(f"Review: {issue_file}", file=sys.stderr)
        return 1

    print(f"Assignment completed for {len(people)} attendees.")
    print(f"Outputs written to: {args.outdir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
