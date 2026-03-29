-- MPs Registered Interests - SQLite Schema
-- Tracks all monetary flows (cash and in-kind) to MPs from payers,
-- with support for one-off and regular recurring payments.
--
-- Edge cases handled:
--   - Cat 1.1/1.2 payer is ALWAYS on the parent Cat 1 record
--   - 114 Cat 1.1 rows have a different ultimate payer (IsUltimatePayerDifferent)
--   - 39 Cat 1.2 rows have no start date (ongoing, never formally dated)
--   - 249 Cat 2 rows have no received date
--   - 90 Cat 2 rows have ReceivedEndDate (ongoing support over months)
--   - Cat 4 rows have up to 5 donors each (flattened to separate payments)
--   - Same payer appears with many address variations across categories
--   - Private individuals never have addresses
--   - 18 rows have confidential ultimate payers

PRAGMA foreign_keys = ON;

-- ============================================================
-- LOOKUP TABLES
-- ============================================================

CREATE TABLE members (
    mnis_id     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    party       TEXT,
    constituency TEXT,  -- MemberFrom: constituency for Commons, peerage type for Lords
    house       TEXT,   -- 'Commons' or 'Lords'
    gender      TEXT,
    start_date  DATE    -- HouseStartDate
);

-- Payers are deduplicated by (name, address).
-- Private individuals will have address = NULL.
-- Address should be normalised before insert: trim whitespace,
-- collapse multiple spaces, replace newlines with ', '.
CREATE TABLE payers (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    name                    TEXT NOT NULL,
    address                 TEXT,
    nature_of_business      TEXT,
    is_private_individual   BOOLEAN DEFAULT 0,
    donor_status            TEXT,  -- 'Individual','Company','Trade Union','Unincorp assoc','Trust','Reg Party','LLP','Friendly Society','Other'
    UNIQUE(name, address)
);

-- ============================================================
-- PARENT EMPLOYMENT/ROLE RECORDS (Category 1)
-- These hold the "who pays for what role" context.
-- Child payments in Cat 1.1 / 1.2 link back here via interest_id.
-- ============================================================

CREATE TABLE interests (
    id          INTEGER PRIMARY KEY,   -- Interest ID from source data
    member_id   INTEGER NOT NULL REFERENCES members(mnis_id),
    payer_id    INTEGER REFERENCES payers(id),
    job_title   TEXT,
    summary     TEXT,
    start_date  DATE,
    end_date    DATE,
    is_until_further_notice BOOLEAN DEFAULT 0,
    is_director BOOLEAN DEFAULT 0,
    registered  DATE
);

CREATE INDEX idx_interests_member ON interests(member_id);
CREATE INDEX idx_interests_payer  ON interests(payer_id);

-- ============================================================
-- PAYMENTS - unified table for all money flows
-- ============================================================
--
-- One-off payments:  is_regular = 0, amount + payment_date populated (date may be NULL for Cat 2)
-- Regular payments:  is_regular = 1, amount (per period) + period populated
--                    start_date may be NULL (39 Cat 1.2 rows have no start date)
--
-- Payer resolution:
--   Cat 1.1/1.2 WITHOUT ultimate payer: interest_id set, payer comes from parent interest
--   Cat 1.1 WITH ultimate payer:        interest_id set AND payer_id set to the ultimate payer
--   Cat 2-5:                            payer_id set directly
--
-- Cat 4 flattening:
--   One source row with N donors becomes N payment rows.
--   id uses source_id * 10 + donor_slot (1-5) for Cat 4.
--   source_interest_id stores the original unmodified ID.

CREATE TABLE payments (
    id                  INTEGER PRIMARY KEY,
    interest_id         INTEGER REFERENCES interests(id),
    member_id           INTEGER NOT NULL REFERENCES members(mnis_id),
    payer_id            INTEGER REFERENCES payers(id),
    category            TEXT NOT NULL,  -- '1.1','1.2','2','3','4','5'
    summary             TEXT,
    description         TEXT,
    payment_type        TEXT CHECK(payment_type IN ('Monetary', 'In kind')),

    -- Payment amounts
    is_regular          BOOLEAN NOT NULL DEFAULT 0,
    amount              REAL NOT NULL DEFAULT 0,
    period              TEXT CHECK(period IN ('Weekly', 'Monthly', 'Quarterly', 'Yearly')),

    -- Dates
    payment_date        DATE,      -- one-off: date received (NULL allowed for Cat 2)
    start_date          DATE,      -- regular: agreement start (NULL allowed for undated Cat 1.2)
    end_date            DATE,      -- regular: agreement end (NULL = ongoing)

    is_received         BOOLEAN DEFAULT 1,  -- False for Cat 1.1 "expected" payments
    is_sole_beneficiary BOOLEAN DEFAULT 1,  -- False when benefit shared with staff/guests
    is_donated          BOOLEAN DEFAULT 0,  -- True when MP donated the payment to charity etc
    donated_to          TEXT,               -- e.g. 'Charity', 'Community organisation'

    appg                TEXT,      -- All-Party Parliamentary Group association (Cat 3, 4, 5)
    source_interest_id  INTEGER,   -- original CSV ID (differs from id for Cat 4 flattened rows)
    registered          DATE,

    CHECK (
        (is_regular = 0 AND period IS NULL)
        OR
        (is_regular = 1 AND period IS NOT NULL)
    )
);

CREATE INDEX idx_payments_member       ON payments(member_id);
CREATE INDEX idx_payments_payer        ON payments(payer_id);
CREATE INDEX idx_payments_interest     ON payments(interest_id);
CREATE INDEX idx_payments_category     ON payments(category);
CREATE INDEX idx_payments_payment_date ON payments(payment_date);
CREATE INDEX idx_payments_regular      ON payments(is_regular, start_date, end_date);

-- ============================================================
-- VIEW: Denormalised payment rows with resolved payer
-- ============================================================
-- Payer resolution order:
--   1. Direct payer_id on payment (Cat 2-5, or Cat 1.1 ultimate payer override)
--   2. Parent interest's payer_id (Cat 1.1/1.2 normal case)

CREATE VIEW payments_full AS
SELECT
    p.id,
    p.member_id,
    m.name                                       AS member_name,
    COALESCE(p.payer_id, i.payer_id)             AS resolved_payer_id,
    COALESCE(py_direct.name, py_parent.name)     AS payer_name,
    COALESCE(py_direct.address, py_parent.address) AS payer_address,
    p.category,
    p.summary,
    p.description,
    p.payment_type,
    p.is_regular,
    p.amount,
    p.period,
    p.payment_date,
    p.start_date,
    p.end_date,
    p.is_received,
    p.is_sole_beneficiary,
    p.is_donated,
    p.donated_to,
    p.registered,
    p.appg,
    p.source_interest_id,
    i.job_title,
    i.summary AS interest_summary
FROM payments p
JOIN members m             ON m.mnis_id = p.member_id
LEFT JOIN interests i      ON i.id = p.interest_id
LEFT JOIN payers py_direct ON py_direct.id = p.payer_id
LEFT JOIN payers py_parent ON py_parent.id = i.payer_id;

-- ============================================================
-- SAMPLE QUERIES
-- ============================================================

-- All queries below use :as_of_date as a parameter.
-- Replace with e.g. '2026-03-29' when running.

-- ---------------------------------------------------------
-- 1a. Total RECEIVED by each MP up to a given date
--     Includes all money that flowed to the MP, even if donated onwards.
--     (one-off + pro-rata regular, monetary only)
-- ---------------------------------------------------------
-- SELECT
--     member_name,
--     ROUND(SUM(total), 2) AS total_received
-- FROM (
--     -- One-off payments received up to the date
--     SELECT
--         pf.member_name,
--         pf.amount AS total
--     FROM payments_full pf
--     WHERE pf.is_regular = 0
--       AND pf.is_received = 1
--       AND pf.payment_date <= :as_of_date
--       AND pf.payment_type = 'Monetary'
--
--     UNION ALL
--
--     -- One-off payments with no date (Cat 2 undated donations)
--     -- included at registered date as best proxy
--     SELECT
--         pf.member_name,
--         pf.amount AS total
--     FROM payments_full pf
--     WHERE pf.is_regular = 0
--       AND pf.is_received = 1
--       AND pf.payment_date IS NULL
--       AND pf.registered <= :as_of_date
--       AND pf.payment_type = 'Monetary'
--
--     UNION ALL
--
--     -- Regular payments (pro-rata from exact start date)
--     -- For undated Cat 1.2: uses registered date as fallback start
--     SELECT
--         pf.member_name,
--         pf.amount * MAX(0,
--             (julianday(MIN(COALESCE(pf.end_date, :as_of_date), :as_of_date))
--              - julianday(COALESCE(pf.start_date, pf.registered)))
--             / CASE pf.period
--                 WHEN 'Weekly'    THEN 7.0
--                 WHEN 'Monthly'   THEN 30.4375
--                 WHEN 'Quarterly' THEN 91.3125
--                 WHEN 'Yearly'    THEN 365.25
--               END
--         ) AS total
--     FROM payments_full pf
--     WHERE pf.is_regular = 1
--       AND COALESCE(pf.start_date, pf.registered) <= :as_of_date
--       AND pf.payment_type = 'Monetary'
-- ) sub
-- GROUP BY member_name
-- ORDER BY total_received DESC;

-- ---------------------------------------------------------
-- 1b. Total RETAINED by each MP up to a given date
--     Excludes payments the MP donated onwards to charity etc.
--     (one-off + pro-rata regular, monetary only, is_donated = 0)
-- ---------------------------------------------------------
-- SELECT
--     member_name,
--     ROUND(SUM(total), 2) AS total_retained
-- FROM (
--     SELECT
--         pf.member_name,
--         pf.amount AS total
--     FROM payments_full pf
--     WHERE pf.is_regular = 0
--       AND pf.is_received = 1
--       AND pf.is_donated = 0
--       AND pf.payment_date <= :as_of_date
--       AND pf.payment_type = 'Monetary'
--
--     UNION ALL
--
--     SELECT
--         pf.member_name,
--         pf.amount AS total
--     FROM payments_full pf
--     WHERE pf.is_regular = 0
--       AND pf.is_received = 1
--       AND pf.is_donated = 0
--       AND pf.payment_date IS NULL
--       AND pf.registered <= :as_of_date
--       AND pf.payment_type = 'Monetary'
--
--     UNION ALL
--
--     SELECT
--         pf.member_name,
--         pf.amount * MAX(0,
--             (julianday(MIN(COALESCE(pf.end_date, :as_of_date), :as_of_date))
--              - julianday(COALESCE(pf.start_date, pf.registered)))
--             / CASE pf.period
--                 WHEN 'Weekly'    THEN 7.0
--                 WHEN 'Monthly'   THEN 30.4375
--                 WHEN 'Quarterly' THEN 91.3125
--                 WHEN 'Yearly'    THEN 365.25
--               END
--         ) AS total
--     FROM payments_full pf
--     WHERE pf.is_regular = 1
--       AND pf.is_donated = 0
--       AND COALESCE(pf.start_date, pf.registered) <= :as_of_date
--       AND pf.payment_type = 'Monetary'
-- ) sub
-- GROUP BY member_name
-- ORDER BY total_retained DESC;

-- ---------------------------------------------------------
-- 2. All payments from a specific payer across all MPs
-- ---------------------------------------------------------
-- SELECT
--     pf.member_name,
--     pf.payer_name,
--     pf.category,
--     pf.summary,
--     pf.amount,
--     pf.payment_type,
--     pf.payment_date,
--     pf.is_regular,
--     pf.period,
--     pf.start_date,
--     pf.end_date
-- FROM payments_full pf
-- WHERE pf.payer_name LIKE '%Microsoft%'
-- ORDER BY pf.payment_date DESC;

-- ---------------------------------------------------------
-- 3. Breakdown by category for a single MP
-- ---------------------------------------------------------
-- SELECT
--     pf.category,
--     pf.payment_type,
--     COUNT(*) AS num_payments,
--     ROUND(SUM(pf.amount), 2) AS raw_total
-- FROM payments_full pf
-- WHERE pf.member_name = 'Rishi Sunak'
-- GROUP BY pf.category, pf.payment_type;

-- ---------------------------------------------------------
-- 4. Active regular payments as of a date
-- ---------------------------------------------------------
-- SELECT
--     pf.member_name,
--     pf.payer_name,
--     pf.amount,
--     pf.period,
--     pf.start_date,
--     pf.end_date,
--     pf.job_title
-- FROM payments_full pf
-- WHERE pf.is_regular = 1
--   AND COALESCE(pf.start_date, pf.registered) <= :as_of_date
--   AND (pf.end_date IS NULL OR pf.end_date >= :as_of_date)
-- ORDER BY pf.amount DESC;

-- ---------------------------------------------------------
-- 5. Payments where MP was NOT sole beneficiary
--    (value may overstate personal benefit)
-- ---------------------------------------------------------
-- SELECT
--     pf.member_name,
--     pf.payer_name,
--     pf.amount,
--     pf.category,
--     pf.description
-- FROM payments_full pf
-- WHERE pf.is_sole_beneficiary = 0
-- ORDER BY pf.amount DESC;

-- ---------------------------------------------------------
-- 6. Payments the MP donated onwards (e.g. to charity)
-- ---------------------------------------------------------
-- SELECT
--     pf.member_name,
--     pf.payer_name,
--     pf.amount,
--     pf.donated_to,
--     pf.category
-- FROM payments_full pf
-- WHERE pf.is_donated = 1
-- ORDER BY pf.amount DESC;
