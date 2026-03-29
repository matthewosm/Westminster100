"""
Import MP registered interests from CSVs into SQLite.

Loads:
  - MP list.csv -> members
  - Category 1   -> interests + payers
  - Category 1.1  -> payments (ad hoc, linked to parent interest)
  - Category 1.2  -> payments (regular, linked to parent interest)
  - Category 2    -> payments (donations)
  - Category 3    -> payments (gifts/hospitality)
  - Category 4    -> payments (visits, flattened multi-donor)
  - Category 5    -> payments (gifts from abroad)
"""

import csv
import sqlite3
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "Data"
DB_PATH = Path(__file__).parent / "interests.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"
MP_LIST_PATH = Path(__file__).parent / "MP list.csv"


def normalise_address(addr):
    """Normalise address for deduplication: collapse whitespace, newlines, trim."""
    if not addr or not addr.strip():
        return None
    addr = addr.replace("\r\n", ", ").replace("\n", ", ").replace("\r", ", ")
    addr = re.sub(r"\s+", " ", addr).strip()
    addr = re.sub(r",\s*,", ",", addr)  # collapse double commas
    return addr


def normalise_text(text):
    """Replace curly quotes and non-breaking spaces."""
    if not text:
        return text
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u00a0", " ")
    return text


def get_or_create_payer(cursor, name, address=None, nature=None, is_individual=False, donor_status=None):
    """Insert payer if not exists, return id. Uses normalised (name, address) for dedup."""
    name = normalise_text(name.strip()) if name else None
    if not name:
        return None
    address = normalise_address(address)
    nature = normalise_text(nature) if nature else None
    donor_status = donor_status.strip() if donor_status else None

    cursor.execute("SELECT id FROM payers WHERE name = ? AND address IS ?", (name, address))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute(
        "INSERT INTO payers (name, address, nature_of_business, is_private_individual, donor_status) VALUES (?, ?, ?, ?, ?)",
        (name, address, nature, 1 if is_individual else 0, donor_status),
    )
    return cursor.lastrowid


def read_csv(filename):
    path = DATA_DIR / filename
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_members(cursor):
    """Load MP list into members table."""
    with open(MP_LIST_PATH, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            mnis_id = int(row["_Member_Id"])
            name = row["DisplayAs"].strip()
            party = row.get("Party/__text", "").strip() or None
            constituency = row.get("MemberFrom", "").strip() or None
            house = row.get("House", "").strip() or None
            gender = row.get("Gender", "").strip() or None
            start_date = row.get("HouseStartDate", "").strip()[:10] or None  # "2024-07-04T00:00:00" -> "2024-07-04"

            cursor.execute(
                "INSERT OR IGNORE INTO members (mnis_id, name, party, constituency, house, gender, start_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mnis_id, name, party, constituency, house, gender, start_date),
            )
    print(f"  members: {cursor.execute('SELECT COUNT(*) FROM members').fetchone()[0]} rows")


def ensure_member(cursor, mnis_id, name):
    """Insert member if not already present (for MPs in interest data but not in MP list)."""
    cursor.execute("SELECT 1 FROM members WHERE mnis_id = ?", (mnis_id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO members (mnis_id, name) VALUES (?, ?)",
            (int(mnis_id), normalise_text(name.strip())),
        )


def load_cat1(cursor):
    """Category 1: Employment roles -> interests + payers."""
    rows = read_csv("PublishedInterest-Category_1.csv")
    for row in rows:
        mnis_id = int(row["MNIS ID"])
        ensure_member(cursor, mnis_id, row["Member"])

        payer_id = get_or_create_payer(
            cursor,
            row["PayerName"],
            row["PayerPublicAddress"],
            row["PayerNatureOfBusiness"],
            is_individual=(row.get("PayerIsPrivateIndividual", "") == "True"),
        )

        cursor.execute(
            """INSERT OR IGNORE INTO interests (id, member_id, payer_id, job_title, summary, start_date, end_date,
               is_until_further_notice, is_director, registered)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                int(row["ID"]),
                mnis_id,
                payer_id,
                normalise_text(row.get("JobTitle", "").strip()) or None,
                normalise_text(row.get("Summary", "").strip()) or None,
                row.get("StartDate", "").strip() or None,
                row.get("EndDate", "").strip() or None,
                1 if row.get("IsUntilFurtherNotice") == "True" else 0,
                1 if row.get("IsPaidAsDirectorOfPayer") == "True" else 0,
                row.get("Registered", "").strip() or None,
            ),
        )
    print(f"  interests: {cursor.execute('SELECT COUNT(*) FROM interests').fetchone()[0]} rows")


def load_cat11(cursor):
    """Category 1.1: Ad hoc payments -> payments (linked to parent interest)."""
    rows = read_csv("PublishedInterest-Category_1.1.csv")
    for row in rows:
        mnis_id = int(row["MNIS ID"])
        ensure_member(cursor, mnis_id, row["Member"])

        parent_id = int(row["Parent Interest ID"])

        # If ultimate payer is different, create a direct payer link
        payer_id = None
        if row.get("IsUltimatePayerDifferent") == "True":
            ult_name = row.get("UltimatePayerName", "").strip()
            ult_addr = row.get("UltimatePayerAddress", "").strip()
            ult_biz = row.get("UltimatePayerNatureOfBusiness", "").strip()
            if ult_name:
                payer_id = get_or_create_payer(cursor, ult_name, ult_addr, ult_biz)

        is_donated = row.get("IsPaymentDonated") == "True"

        cursor.execute(
            """INSERT OR IGNORE INTO payments
               (id, interest_id, member_id, payer_id, category, summary, description, payment_type,
                is_regular, amount, payment_date, is_received, is_donated, donated_to,
                source_interest_id, registered)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                int(row["ID"]),
                parent_id,
                mnis_id,
                payer_id,
                "1.1",
                normalise_text(row.get("Summary", "").strip()) or None,
                normalise_text(row.get("PaymentDescription", "").strip()) or None,
                row.get("PaymentType", "").strip() or None,
                0,  # not regular
                float(row["Value"]),
                row.get("ReceivedDate", "").strip() or None,
                1 if row.get("PaymentReceived") == "True" else 0,
                1 if is_donated else 0,
                row.get("DonateeType", "").strip() or None if is_donated else None,
                int(row["ID"]),
                row.get("Registered", "").strip() or None,
            ),
        )
    print(f"  Cat 1.1 payments: {len(rows)} rows")


def load_cat12(cursor):
    """Category 1.2: Ongoing paid employment -> payments (regular, linked to parent)."""
    rows = read_csv("PublishedInterest-Category_1.2.csv")
    for row in rows:
        mnis_id = int(row["MNIS ID"])
        ensure_member(cursor, mnis_id, row["Member"])

        parent_id = int(row["Parent Interest ID"])
        is_donated = row.get("IsPaymentDonated") == "True"

        cursor.execute(
            """INSERT OR IGNORE INTO payments
               (id, interest_id, member_id, category, summary, description, payment_type,
                is_regular, amount, period, start_date, end_date,
                is_donated, donated_to, source_interest_id, registered)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                int(row["ID"]),
                parent_id,
                mnis_id,
                "1.2",
                normalise_text(row.get("Summary", "").strip()) or None,
                normalise_text(row.get("PaymentDescription", "").strip()) or None,
                row.get("PaymentType", "").strip() or None,
                1,  # regular
                float(row["Value"]),
                row.get("RegularityOfPayment", "").strip() or None,
                row.get("StartDate", "").strip() or None,
                row.get("EndDate", "").strip() or None,
                1 if is_donated else 0,
                row.get("DonateeType", "").strip() or None if is_donated else None,
                int(row["ID"]),
                row.get("Registered", "").strip() or None,
            ),
        )
    print(f"  Cat 1.2 payments: {len(rows)} rows")


def load_donation_category(cursor, filename, category):
    """Load Cat 2, 3, or 5: donations/gifts -> payments + payers."""
    rows = read_csv(filename)
    for row in rows:
        mnis_id = int(row["MNIS ID"])
        ensure_member(cursor, mnis_id, row["Member"])

        donor_name = row.get("DonorName", "").strip()
        donor_addr = row.get("DonorPublicAddress", "").strip()
        donor_status = row.get("DonorStatus", "").strip()
        is_individual = (donor_status == "Individual")

        payer_id = get_or_create_payer(
            cursor, donor_name, donor_addr,
            donor_status=donor_status,
            is_individual=is_individual,
        )

        payment_date = row.get("ReceivedDate", "").strip() or None
        end_date = row.get("ReceivedEndDate", "").strip() or None

        appg = row.get("Appg", "").strip() or None

        cursor.execute(
            """INSERT OR IGNORE INTO payments
               (id, member_id, payer_id, category, summary, description, payment_type,
                is_regular, amount, payment_date, end_date,
                is_sole_beneficiary, appg, source_interest_id, registered)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                int(row["ID"]),
                mnis_id,
                payer_id,
                category,
                normalise_text(row.get("Summary", "").strip()) or None,
                normalise_text(row.get("PaymentDescription", "").strip()) or None,
                row.get("PaymentType", "").strip() or None,
                0,
                float(row["Value"]),
                payment_date,
                end_date,
                1 if row.get("IsSoleBeneficiary") == "True" else 0,
                appg,
                int(row["ID"]),
                row.get("Registered", "").strip() or None,
            ),
        )
    print(f"  Cat {category} payments: {len(rows)} rows")


def load_cat4(cursor):
    """Category 4: Visits outside UK -> flattened payments (one row per donor)."""
    rows = read_csv("PublishedInterest-Category_4.csv")
    count = 0
    for row in rows:
        mnis_id = int(row["MNIS ID"])
        ensure_member(cursor, mnis_id, row["Member"])

        source_id = int(row["ID"])
        visit_start = row.get("StartDate", "").strip() or None
        purpose = row.get("Purpose", "").strip() or None
        appg = row.get("Appg", "").strip() or None

        for slot in range(1, 6):
            donor_name = row.get(f"Donors_Name_{slot}", "").strip()
            value_str = row.get(f"Donors_Value_{slot}", "").strip()
            if not donor_name or not value_str:
                continue

            donor_addr = row.get(f"Donors_PublicAddress_{slot}", "").strip()
            is_individual = row.get(f"Donors_IsPrivateIndividual_{slot}", "").strip().lower() == "true"
            payment_type = row.get(f"Donors_PaymentType_{slot}", "").strip() or None
            description = row.get(f"Donors_PaymentDescription_{slot}", "").strip() or None
            is_sole = row.get(f"Donors_IsSoleBeneficiary_{slot}", "").strip() == "True"

            payer_id = get_or_create_payer(
                cursor, donor_name, donor_addr,
                is_individual=is_individual,
            )

            payment_id = source_id * 10 + slot

            cursor.execute(
                """INSERT OR IGNORE INTO payments
                   (id, member_id, payer_id, category, summary, description, payment_type,
                    is_regular, amount, payment_date, is_sole_beneficiary,
                    appg, source_interest_id, registered)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    payment_id,
                    mnis_id,
                    payer_id,
                    "4",
                    normalise_text(f"{row.get('Summary', '').strip()} — {purpose}" if purpose else row.get("Summary", "").strip()) or None,
                    normalise_text(description),
                    payment_type,
                    0,
                    float(value_str),
                    visit_start,
                    1 if is_sole else 0,
                    appg,
                    source_id,
                    row.get("Registered", "").strip() or None,
                ),
            )
            count += 1
    print(f"  Cat 4 payments: {count} rows (from {len(rows)} visits)")


def main():
    # Remove existing DB
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # Create schema
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)

    print("Loading data...")
    load_members(cursor)
    conn.commit()

    load_cat1(cursor)
    conn.commit()

    load_cat11(cursor)
    conn.commit()

    load_cat12(cursor)
    conn.commit()

    load_donation_category(cursor, "PublishedInterest-Category_2.csv", "2")
    conn.commit()

    load_donation_category(cursor, "PublishedInterest-Category_3.csv", "3")
    conn.commit()

    load_cat4(cursor)
    conn.commit()

    load_donation_category(cursor, "PublishedInterest-Category_5.csv", "5")
    conn.commit()

    # Summary
    print("\n=== Summary ===")
    for table in ["members", "payers", "interests", "payments"]:
        n = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {n}")

    cats = cursor.execute(
        "SELECT category, COUNT(*), ROUND(SUM(amount), 2) FROM payments GROUP BY category ORDER BY category"
    ).fetchall()
    print("\n  By category:")
    for cat, n, total in cats:
        print(f"    {cat}: {n} payments, total amount {total:,.2f}")

    conn.close()
    print(f"\nDatabase written to {DB_PATH}")


if __name__ == "__main__":
    main()
