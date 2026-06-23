# 575-Attendee Seating Assignment Test Package

This package is a synthetic, realistic-style test dataset for the dinner seating program. All names are fictional.

## Dataset composition

- 575 total attendees
- 485 regular non-vegetarian attendees
- 70 regular vegetarian attendees
- 20 halal non-vegetarian attendees
- 0 halal vegetarian attendees

## Group-request coverage

The dataset includes:

- Five regular non-vegetarian groups of 10 people.
- Smaller regular non-vegetarian groups of 8, 6, 4, and 3 people.
- One requested mixed group of exactly 10 non-vegetarians + 1 vegetarian.
- One vegetarian-only group of 10 people and additional vegetarian groups below 10 people.
- Four halal non-vegetarian groups that pack into exactly two tables of 10 people each.
- Hundreds of ungrouped attendees for automatic, diet-compatible random allocation.

## Test command used

```bash
python seating_assignment.py \
  --input synthetic_attendees_575.csv \
  --outdir test_575_output \
  --seed 5752026
```

## Result

PASS. The program assigned all 575 attendees to 58 tables:

- 56 regular tables
- 2 halal tables

The independent validation verifies that each attendee was seated once, requested groups were not split, meal/diet rules were respected, and both halal tables contain exactly 10 halal non-vegetarian guests.
