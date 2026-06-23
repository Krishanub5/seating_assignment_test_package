# Synthetic 575-Attendee Seating Test

**Result:** PASS

## Test Data

- Total attendees: **575**
- Regular non-vegetarian: **485**
- Regular vegetarian: **70**
- Halal non-vegetarian: **20** across exactly two halal tables
- Halal vegetarian: **0**
- Requested-group patterns included: full 10-person groups, groups below 10, one 10 non-vegetarian + 1 vegetarian group, full 10-person vegetarian group, and halal groups.

## Assignment Results

- Assignment rows: **575**
- Used tables: **58**
- Regular tables used: **56**
- Halal tables used: **2 of 2**
- Full tables: **56**
- Partially filled tables: **2**
- Randomisation seed: **5752026**

## Independent Rule Validation

- PASS: Every source attendee appears exactly once in the seating output.
- PASS: Every requested group remains at one table.
- PASS: Regular non-vegetarian tables do not exceed 10 guests.
- PASS: Vegetarian-only tables do not exceed 10 guests.
- PASS: The only mixed table uses exactly 10 non-vegetarians + 1 vegetarian.
- PASS: The two halal tables contain only halal non-vegetarian guests, 10 people each.
