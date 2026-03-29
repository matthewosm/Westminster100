# UK MPs Registered Interests Database

A SQLite database consolidating the UK Parliament's Register of Members' Financial Interests into a queryable format, with support for date-based totals across one-off and recurring payments.

## Data Source

The source data is the [Parliamentary Register of Members' Financial Interests](https://interests.parliament.uk/), downloaded as CSV exports across 10 categories. The MP list comes from the [Members API](https://members-api.parliament.uk/).

### Source Files

```
MP list.csv                              — 1,515 members (650 Commons, 865 Lords)
Data/PublishedInterest-Category_1.csv    — Employment and earnings (parent roles)
Data/PublishedInterest-Category_1.1.csv  — Ad hoc payments (children of Cat 1)
Data/PublishedInterest-Category_1.2.csv  — Ongoing paid employment (children of Cat 1)
Data/PublishedInterest-Category_2.csv    — Donations and other support
Data/PublishedInterest-Category_3.csv    — Gifts, benefits and hospitality (UK sources)
Data/PublishedInterest-Category_4.csv    — Visits outside the UK
Data/PublishedInterest-Category_5.csv    — Gifts and benefits from outside the UK
Data/PublishedInterest-Category_6.csv    — Land and property (no monetary values — not imported)
Data/PublishedInterest-Category_7.csv    — Shareholdings (no monetary values — not imported)
Data/PublishedInterest-Category_8.csv    — Miscellaneous interests (roles, not payments — not imported)
Data/PublishedInterest-Category_9.csv    — Family members employed (no monetary values — not imported)
Data/PublishedInterest-Category_10.csv   — Family members in lobbying (no monetary values — not imported)
```

Categories 6-10 are not imported because they contain no monetary amounts.

## Database

### Schema (`schema.sql`)

Four tables and one view:

**`members`** — All MPs and Lords from the Parliament members API.
- `mnis_id` (PK) — Parliament's Member Name Information Service ID
- `name`, `party`, `constituency`, `house` (Commons/Lords), `gender`, `start_date`

**`payers`** — Deduplicated entities that pay or donate to MPs.
- Deduplicated on `UNIQUE(name, address)` after normalisation
- `donor_status` captures the entity type: Individual, Company, Trade Union, LLP, Trust, Friendly Society, Unincorporated Association, Registered Party, Other
- Private individuals never have addresses (by Parliament's privacy rules)

**`interests`** — Category 1 parent records: the employment role linking an MP to a payer.
- Contains the job title, payer, and role dates
- Has no monetary value itself — the money is on child payments in Cat 1.1 / 1.2
- 59 of 283 have no child payments yet (newly registered roles)

**`payments`** — All monetary flows, unified across categories.
- 2,385 rows from 6 source categories
- Both one-off and regular recurring payments in the same table
- See "How Payments Work" below for details

**`payments_full`** (view) — Denormalised view joining payments to members, payers, and parent interests. Automatically resolves the correct payer for every row (see payer resolution below).

### How Payments Work

#### One-off payments (`is_regular = 0`)
A single payment on a single date. `amount` is the total, `payment_date` is when it was received.

Sources: Cat 1.1 (ad hoc earnings), Cat 2 (donations), Cat 3 (gifts/hospitality), Cat 4 (visit sponsorship), Cat 5 (gifts from abroad).

#### Regular payments (`is_regular = 1`)
An ongoing agreement paying a fixed amount per period. `amount` is the per-period figure, `period` is Weekly/Monthly/Quarterly/Yearly, `start_date` is when it began, `end_date` is when it ends (NULL = ongoing).

Source: Cat 1.2 only.

To compute total received up to a given date, the sample queries use pro-rata day-based arithmetic:

```
effective_end = MIN(COALESCE(end_date, as_of_date), as_of_date)
days_elapsed  = julianday(effective_end) - julianday(start_date)
periods       = days_elapsed / days_per_period
total         = amount * periods
```

Where days_per_period is: Weekly=7, Monthly=30.4375, Quarterly=91.3125, Yearly=365.25.

#### Payer resolution

The `payments_full` view resolves payers automatically using `COALESCE`:

1. **Cat 2, 3, 4, 5**: Payer is set directly on the payment row (`payer_id`).
2. **Cat 1.1 / 1.2 (normal)**: Payer comes from the parent interest record. The payment has `interest_id` set and `payer_id` NULL.
3. **Cat 1.1 with ultimate payer**: 114 payments where the actual payer differs from the intermediary on the parent interest. Both `interest_id` and `payer_id` are set; `payer_id` wins in the COALESCE.

#### APPG association

Payments in Categories 3, 4, and 5 may be linked to an All-Party Parliamentary Group. This is stored in the `appg` column (159 payments have one). Note that APPG names are not standardised in the source data — the same group can appear as "APPG on Ukraine", "APPG Ukraine", and "Ukraine".

#### Payment type

Every payment has `payment_type` of either `'Monetary'` (cash) or `'In kind'` (non-cash benefit with an estimated value). Both are stored in the same table. Filter on this column to include or exclude in-kind benefits from totals.

- Cat 1.1: 99.3% Monetary
- Cat 2: 74.4% Monetary, 25.6% In kind
- Cat 3: 98.5% In kind (hospitality, event tickets)
- Cat 4: 91.5% In kind (flights, accommodation)
- Cat 5: 100% In kind

### Category Breakdown

| Category | Rows | Total Amount | Description |
|----------|------|-------------|-------------|
| 1.1 | 583 | 4,010,351 | Ad hoc earnings (speaking fees, legal work, writing) |
| 1.2 | 84 | 2,757,898 | Ongoing employment (per-period amounts, not cumulative) |
| 2 | 547 | 4,469,189 | Donations to support MP activities |
| 3 | 671 | 2,794,182 | Gifts, benefits, hospitality from UK sources |
| 4 | 483 | 1,484,046 | Overseas visit sponsorship |
| 5 | 17 | 75,259 | Gifts from outside the UK |

## Import Script (`import.py`)

Reads all source CSVs and populates `interests.db`. Run with:

```
python import.py
```

Deletes any existing `interests.db` and rebuilds from scratch.

### What the import handles

- **Text normalisation**: Replaces curly quotes (U+2018/2019/201C/201D) with straight quotes, non-breaking spaces (U+00A0) with regular spaces.
- **Address normalisation**: Collapses whitespace, replaces newlines with `, `, removes double commas.
- **Payer deduplication**: Uses normalised `(name, address)` pairs. Same payer at the same normalised address reuses the existing row.
- **Cat 1.1 ultimate payer**: When `IsUltimatePayerDifferent=True`, creates a separate payer record for the ultimate payer and sets it directly on the payment.
- **Cat 4 multi-donor flattening**: Each source row with N donors (up to 5) becomes N payment rows. The synthetic `id` is `source_id * 10 + donor_slot`. The original ID is preserved in `source_interest_id`.
- **Member backfill**: If an MNIS ID appears in the interest data but not in the MP list, a minimal member record is created.
- **APPG capture**: The `Appg` field from Categories 3, 4, and 5 source CSVs is stored on payments (159 rows).

## Known Data Quality Issues

### Payer deduplication is imperfect

The same real-world entity appears with different address formats across records:
- "2 Derry Street" vs "2 Derry  Street" (extra space)
- "Old Queen St" vs "Old Queen Street" (abbreviation)
- "GB News" vs "GB News Ltd" (name variation)
- Multiline vs single-line addresses
- Organisations that relocated (same name, genuinely different address)

The current import uses exact match on normalised `(name, address)`. Fuzzy matching or manual entity resolution would further reduce duplicates.

### Missing dates

- **249 Cat 2 donations** (45.5%) have no `ReceivedDate`. The `registered` date is available as a proxy.
- **39 Cat 1.2 regular payments** have no `start_date`. The pro-rata query falls back to `registered` date.

### Sole beneficiary

50% of Cat 3 and 20% of Cat 4 payments have `is_sole_beneficiary = 0`, meaning the value covers the MP plus guests/staff. The `amount` may overstate the MP's personal benefit in these cases.

### Donated payments

24 payments across Cat 1.1 and 1.2 were donated onwards by the MP (e.g. to charity). These are flagged with `is_donated = 1` and `donated_to` describing the recipient type. The amount was received by the MP but not retained. As of 2026-03-29 this accounts for ~1,080,553 of the monetary total. Use query 1b ("total retained") to exclude these.

### Confidential payers

18 Cat 1.1 rows have `UltimatePayerName = 'Confidential'`. These are stored as a payer named "Confidential".

### Cat 1.2 amounts are per-period, not totals

A row showing amount=3000 with period=Monthly means 3,000/month, not 3,000 total. The raw `SUM(amount)` for Cat 1.2 (2,757,898) is the sum of per-period rates, not cumulative spend. Use the pro-rata query in `schema.sql` to compute actual totals up to a date.

## Sample Queries

The bottom of `schema.sql` contains commented-out sample queries:

1a. **Total received by MP** up to a given date (handles one-off + pro-rata regular + undated donations)
1b. **Total retained by MP** — same as 1a but excludes payments donated onwards to charity
2. **Payments from a specific payer** across all MPs
3. **Category breakdown** for a single MP
4. **Active regular payments** as of a date
5. **Shared-benefit payments** where MP was not sole beneficiary
6. **Donated payments** that the MP passed on to charity
