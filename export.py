"""
Export interests.db to static JSON files for The Westminster 100 website.

Usage:
    python export.py                        # Uses today as as_of_date
    python export.py --as-of 2026-03-29     # Specific date
    python export.py --output-dir ./site/data
"""

import argparse
import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

PARTY_COLOURS = {
    'Conservative': '#0087DC',
    'Labour': '#E4003B',
    'Labour (Co-op)': '#E4003B',
    'Liberal Democrat': '#FAA61A',
    'Reform UK': '#12B6CF',
    'Scottish National Party': '#FDF38E',
    'Green Party': '#6AB023',
    'Plaid Cymru': '#005B54',
    'Democratic Unionist Party': '#D46A4C',
    'Sinn Féin': '#326760',
    'Social Democratic & Labour Party': '#2AA82C',
    'Alliance': '#F6CB2F',
    'Ulster Unionist Party': '#48A5EE',
    'Traditional Unionist Voice': '#0C3A6A',
    'Independent': '#AAAAAA',
    'Speaker': '#AAAAAA',
    'Restore Britain': '#7F3F98',
    'Your Party': '#999999',
}

CATEGORY_LABELS = {
    '1.1': 'Freelance Enterprise',
    '1.2': 'Retained Services',
    '2': 'Philanthropic Support',
    '3': 'Lifestyle Benefits',
    '4': 'International Fact-Finding',
    '5': 'Diplomatic Gifts',
}

THUMBNAIL_URL = 'https://members-api.parliament.uk/api/Members/{mnis_id}/Thumbnail'

# Pro-rata CASE expression reused across queries
PRORATA_CASE = """
    CASE pf.period
        WHEN 'Weekly'    THEN 7.0
        WHEN 'Monthly'   THEN 30.4375
        WHEN 'Quarterly' THEN 91.3125
        WHEN 'Yearly'    THEN 365.25
    END
"""

def _window_where(prefix='pf', include_donated=False):
    """WHERE clause fragment to filter payments within the 12m window.
    Expects params: [as_of_date, since_date, as_of_date, since_date, as_of_date, since_date]
    """
    p = prefix
    donated_filter = "" if include_donated else f"AND {p}.is_donated = 0"
    return f"""(
        ({p}.is_regular = 0 AND {p}.is_received = 1 {donated_filter} AND (
            ({p}.payment_date IS NOT NULL AND {p}.payment_date <= ? AND {p}.payment_date > ?)
            OR ({p}.payment_date IS NULL AND {p}.registered <= ? AND {p}.registered > ?)
        ))
        OR
        ({p}.is_regular = 1 {donated_filter} AND COALESCE({p}.start_date, {p}.registered) <= ?
         AND ({p}.end_date IS NULL OR {p}.end_date > ?))
    )"""

def _window_params(as_of_date, since_date):
    return [as_of_date, since_date, as_of_date, since_date, as_of_date, since_date]


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def has_payers_master(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='payers_master_map'"
    ).fetchone()
    return row[0] > 0


def compute_individual_totals(conn, as_of_date, since_date, monetary_only=True, include_donated=False):
    """Per-MP total earnings in the 12m window using pro-rata for regular payments."""
    pt_filter = "AND pf.payment_type = 'Monetary'" if monetary_only else ""
    donated_filter = "" if include_donated else "AND pf.is_donated = 0"

    sql = f"""
    SELECT member_id, ROUND(SUM(total), 2) AS total_received
    FROM (
        SELECT pf.member_id, pf.amount AS total
        FROM payments_full pf
        WHERE pf.is_regular = 0 AND pf.is_received = 1
          AND pf.payment_date IS NOT NULL
          AND pf.payment_date <= ? AND pf.payment_date > ?
          {pt_filter} {donated_filter}

        UNION ALL

        SELECT pf.member_id, pf.amount AS total
        FROM payments_full pf
        WHERE pf.is_regular = 0 AND pf.is_received = 1
          AND pf.payment_date IS NULL
          AND pf.registered <= ? AND pf.registered > ?
          {pt_filter} {donated_filter}

        UNION ALL

        SELECT pf.member_id,
            pf.amount * MAX(0,
                (julianday(MIN(COALESCE(pf.end_date, ?), ?))
                 - julianday(MAX(COALESCE(pf.start_date, pf.registered), ?)))
                / {PRORATA_CASE}
            ) AS total
        FROM payments_full pf
        WHERE pf.is_regular = 1
          AND COALESCE(pf.start_date, pf.registered) <= ?
          AND (pf.end_date IS NULL OR pf.end_date > ?)
          {pt_filter} {donated_filter}
    ) sub
    GROUP BY member_id
    """
    params = [
        as_of_date, since_date,
        as_of_date, since_date,
        as_of_date, as_of_date, since_date,
        as_of_date, since_date,
    ]
    return {r['member_id']: r['total_received'] or 0
            for r in conn.execute(sql, params)}


def compute_alltime_totals(conn, as_of_date, monetary_only=True, include_donated=False):
    """Per-MP all-time total (no lower-bound clamp)."""
    pt_filter = "AND pf.payment_type = 'Monetary'" if monetary_only else ""
    donated_filter = "" if include_donated else "AND pf.is_donated = 0"

    sql = f"""
    SELECT member_id, ROUND(SUM(total), 2) AS total_received
    FROM (
        SELECT pf.member_id, pf.amount AS total
        FROM payments_full pf
        WHERE pf.is_regular = 0 AND pf.is_received = 1
          AND pf.payment_date IS NOT NULL AND pf.payment_date <= ?
          {pt_filter} {donated_filter}

        UNION ALL

        SELECT pf.member_id, pf.amount AS total
        FROM payments_full pf
        WHERE pf.is_regular = 0 AND pf.is_received = 1
          AND pf.payment_date IS NULL AND pf.registered <= ?
          {pt_filter} {donated_filter}

        UNION ALL

        SELECT pf.member_id,
            pf.amount * MAX(0,
                (julianday(MIN(COALESCE(pf.end_date, ?), ?))
                 - julianday(COALESCE(pf.start_date, pf.registered)))
                / {PRORATA_CASE}
            ) AS total
        FROM payments_full pf
        WHERE pf.is_regular = 1
          AND COALESCE(pf.start_date, pf.registered) <= ?
          {pt_filter} {donated_filter}
    ) sub
    GROUP BY member_id
    """
    params = [as_of_date, as_of_date, as_of_date, as_of_date, as_of_date]
    return {r['member_id']: r['total_received'] or 0
            for r in conn.execute(sql, params)}


def compute_category_breakdowns(conn, as_of_date, since_date):
    """Per-MP, per-category, per-payment_type breakdowns for 12m window."""
    sql = f"""
    SELECT pf.member_id, pf.category, pf.payment_type,
           COUNT(*) AS cnt,
           ROUND(SUM(
               CASE
                   WHEN pf.is_regular = 0 THEN pf.amount
                   ELSE pf.amount * MAX(0,
                       (julianday(MIN(COALESCE(pf.end_date, ?), ?))
                        - julianday(MAX(COALESCE(pf.start_date, pf.registered), ?)))
                       / CASE pf.period
                           WHEN 'Weekly'    THEN 7.0
                           WHEN 'Monthly'   THEN 30.4375
                           WHEN 'Quarterly' THEN 91.3125
                           WHEN 'Yearly'    THEN 365.25
                         END
                   )
               END
           ), 2) AS total
    FROM payments_full pf
    WHERE {_window_where()}
    GROUP BY pf.member_id, pf.category, pf.payment_type
    """
    params = [as_of_date, as_of_date, since_date] + _window_params(as_of_date, since_date)
    rows = conn.execute(sql, params).fetchall()

    result = {}
    for r in rows:
        mid = r['member_id']
        cat = r['category']
        pt = r['payment_type']
        if mid not in result:
            result[mid] = {}
        if cat not in result[mid]:
            result[mid][cat] = {'monetary': 0, 'inkind': 0, 'count': 0}
        key = 'monetary' if pt == 'Monetary' else 'inkind'
        result[mid][cat][key] += r['total'] or 0
        result[mid][cat]['count'] += r['cnt']
    return result


def compute_top_payers_per_mp(conn, as_of_date, since_date, use_master):
    """All payers per MP, sorted by amount descending."""
    if use_master:
        payer_join = """
            JOIN payers_master_map pmm ON pmm.payer_id = pf.resolved_payer_id
            JOIN payers_master pm ON pm.id = pmm.master_id
        """
        payer_name = "pm.canonical_name"
        group_col = "pmm.master_id"
    else:
        payer_join = ""
        payer_name = "pf.payer_name"
        group_col = "pf.resolved_payer_id"

    sql = f"""
    SELECT
        pf.member_id,
        {payer_name} AS payer_name,
        ROUND(SUM(
            CASE
                WHEN pf.is_regular = 0 THEN pf.amount
                ELSE pf.amount * MAX(0,
                    (julianday(MIN(COALESCE(pf.end_date, ?), ?))
                     - julianday(MAX(COALESCE(pf.start_date, pf.registered), ?)))
                    / {PRORATA_CASE}
                )
            END
        ), 2) AS total
    FROM payments_full pf
    {payer_join}
    WHERE {_window_where()}
    GROUP BY pf.member_id, {group_col}
    ORDER BY pf.member_id, total DESC
    """
    params = [as_of_date, as_of_date, since_date] + _window_params(as_of_date, since_date)
    rows = conn.execute(sql, params).fetchall()

    result = {}
    for r in rows:
        mid = r['member_id']
        if mid not in result:
            result[mid] = []
        result[mid].append({'name': r['payer_name'], 'total': r['total'] or 0})
    return result


def compute_active_regular(conn, as_of_date, use_master):
    """Active recurring payments as of date."""
    if use_master:
        payer_join = """
            LEFT JOIN payers_master_map pmm ON pmm.payer_id = pf.resolved_payer_id
            LEFT JOIN payers_master pm ON pm.id = pmm.master_id
        """
        payer_name = "COALESCE(pm.canonical_name, pf.payer_name)"
    else:
        payer_join = ""
        payer_name = "pf.payer_name"

    sql = f"""
    SELECT
        pf.member_id,
        {payer_name} AS payer_name,
        pf.amount, pf.period, pf.job_title, pf.start_date, pf.end_date,
        ROUND(pf.amount * 365.25 / {PRORATA_CASE}, 2) AS annual_rate
    FROM payments_full pf
    {payer_join}
    WHERE pf.is_regular = 1
      AND COALESCE(pf.start_date, pf.registered) <= ?
      AND (pf.end_date IS NULL OR pf.end_date >= ?)
    ORDER BY annual_rate DESC
    """
    rows = conn.execute(sql, [as_of_date, as_of_date]).fetchall()

    result = {}
    for r in rows:
        mid = r['member_id']
        if mid not in result:
            result[mid] = []
        result[mid].append({
            'payer': r['payer_name'],
            'amount_per_period': r['amount'],
            'period': r['period'],
            'annual_rate': r['annual_rate'],
            'job_title': r['job_title'],
            'start_date': r['start_date'],
            'end_date': r['end_date'],
        })
    return result


def compute_donor_counts(conn, as_of_date, since_date, use_master):
    """Count of distinct payers per MP in 12m window."""
    if use_master:
        sql = f"""
        SELECT pf.member_id, COUNT(DISTINCT pmm.master_id) AS donor_count
        FROM payments_full pf
        JOIN payers_master_map pmm ON pmm.payer_id = pf.resolved_payer_id
        WHERE {_window_where()}
        GROUP BY pf.member_id
        """
    else:
        sql = f"""
        SELECT pf.member_id, COUNT(DISTINCT pf.resolved_payer_id) AS donor_count
        FROM payments_full pf
        WHERE {_window_where()}
        GROUP BY pf.member_id
        """
    params = _window_params(as_of_date, since_date)
    return {r['member_id']: r['donor_count']
            for r in conn.execute(sql, params)}


def compute_payment_counts(conn, as_of_date, since_date):
    """Count of payments per MP in 12m window."""
    sql = f"""
    SELECT member_id, COUNT(*) AS payment_count
    FROM payments_full pf
    WHERE {_window_where()}
    GROUP BY member_id
    """
    return {r['member_id']: r['payment_count']
            for r in conn.execute(sql, _window_params(as_of_date, since_date))}


def build_individuals(conn, as_of_date, since_date, use_master):
    """Build the full individuals dataset."""
    totals_12m = compute_individual_totals(conn, as_of_date, since_date, monetary_only=True)
    totals_12m_all = compute_individual_totals(conn, as_of_date, since_date, monetary_only=False)
    totals_alltime = compute_alltime_totals(conn, as_of_date, monetary_only=True)
    totals_alltime_all = compute_alltime_totals(conn, as_of_date, monetary_only=False)
    categories = compute_category_breakdowns(conn, as_of_date, since_date)
    top_payers = compute_top_payers_per_mp(conn, as_of_date, since_date, use_master)
    active_regular = compute_active_regular(conn, as_of_date, use_master)
    donor_counts = compute_donor_counts(conn, as_of_date, since_date, use_master)
    payment_counts = compute_payment_counts(conn, as_of_date, since_date)

    all_member_ids = set(totals_12m) | set(totals_alltime)

    members = {row['mnis_id']: dict(row)
               for row in conn.execute('SELECT * FROM members')}

    individuals = []
    for mid in all_member_ids:
        m = members.get(mid)
        if not m:
            continue

        monetary_12m = totals_12m.get(mid, 0)
        combined_12m = totals_12m_all.get(mid, 0)
        inkind_12m = max(0, round(combined_12m - monetary_12m, 2))
        monetary_alltime = totals_alltime.get(mid, 0)
        combined_alltime = totals_alltime_all.get(mid, 0)

        cat_data = {}
        for cat in ['1.1', '1.2', '2', '3', '4', '5']:
            cat_data[cat] = (categories.get(mid, {}).get(cat)
                             or {'monetary': 0, 'inkind': 0, 'count': 0})

        individuals.append({
            'mnis_id': mid,
            'name': m['name'],
            'party': m['party'],
            'constituency': m['constituency'],
            'house': m['house'],
            'gender': m['gender'],
            'thumbnail_url': THUMBNAIL_URL.format(mnis_id=mid),
            'total_monetary_12m': monetary_12m,
            'total_inkind_12m': inkind_12m,
            'total_combined_12m': combined_12m,
            'total_monetary_alltime': monetary_alltime,
            'total_combined_alltime': combined_alltime,
            'payment_count': payment_counts.get(mid, 0),
            'donor_count': donor_counts.get(mid, 0),
            'categories': cat_data,
            'top_payers': top_payers.get(mid, []),
            'active_regular_payments': active_regular.get(mid, []),
        })

    individuals.sort(key=lambda x: x['total_monetary_12m'], reverse=True)
    for i, ind in enumerate(individuals):
        ind['rank'] = i + 1
    return individuals


def build_parties(individuals, conn):
    """Aggregate individual data by party."""
    party_member_counts = {}
    for row in conn.execute(
        'SELECT party, COUNT(*) as cnt FROM members WHERE house = "Commons" GROUP BY party'
    ):
        party_member_counts[row['party']] = row['cnt']

    party_data = {}
    for ind in individuals:
        p = ind['party']
        if p not in party_data:
            party_data[p] = {
                'members': [],
                'total_monetary_12m': 0,
                'total_inkind_12m': 0,
                'total_combined_12m': 0,
                'categories': {c: {'monetary': 0, 'inkind': 0, 'count': 0}
                               for c in ['1.1', '1.2', '2', '3', '4', '5']},
            }
        pd = party_data[p]
        pd['members'].append(ind)
        pd['total_monetary_12m'] += ind['total_monetary_12m']
        pd['total_inkind_12m'] += ind['total_inkind_12m']
        pd['total_combined_12m'] += ind['total_combined_12m']
        for cat in ['1.1', '1.2', '2', '3', '4', '5']:
            for key in ['monetary', 'inkind', 'count']:
                pd['categories'][cat][key] += ind['categories'][cat][key]

    parties = []
    for p, pd in party_data.items():
        pd['members'].sort(key=lambda x: x['total_monetary_12m'], reverse=True)
        earning = [m for m in pd['members'] if m['total_monetary_12m'] > 0]
        star = pd['members'][0] if pd['members'] else None
        total_members = party_member_counts.get(p, len(pd['members']))

        parties.append({
            'party': p,
            'member_count_total': total_members,
            'member_count_with_payments': len(pd['members']),
            'member_count_earning': len(earning),
            'total_monetary_12m': round(pd['total_monetary_12m'], 2),
            'total_inkind_12m': round(pd['total_inkind_12m'], 2),
            'total_combined_12m': round(pd['total_combined_12m'], 2),
            'avg_per_member': round(pd['total_monetary_12m'] / max(1, total_members), 2),
            'avg_per_earning_member': round(pd['total_monetary_12m'] / max(1, len(earning)), 2),
            'star_player': {
                'mnis_id': star['mnis_id'],
                'name': star['name'],
                'total_monetary_12m': star['total_monetary_12m'],
                'constituency': star['constituency'],
                'thumbnail_url': star['thumbnail_url'],
            } if star else None,
            'categories': pd['categories'],
            'top_earners': [{
                'mnis_id': m['mnis_id'], 'name': m['name'],
                'total_monetary_12m': m['total_monetary_12m'],
                'constituency': m['constituency'], 'thumbnail_url': m['thumbnail_url'],
            } for m in pd['members'][:5]],
        })

    parties.sort(key=lambda x: x['total_monetary_12m'], reverse=True)
    return parties


def build_donors(conn, as_of_date, since_date, use_master):
    """Build donor data."""
    if use_master:
        payer_join = """
            JOIN payers_master_map pmm ON pmm.payer_id = pf.resolved_payer_id
            JOIN payers_master pm ON pm.id = pmm.master_id
        """
        payer_id_col = "pmm.master_id AS payer_key"
        payer_name_col = "pm.canonical_name AS canonical_name"
        payer_status_col = "pm.donor_status"
        payer_indiv_col = "pm.is_private_individual"
    else:
        payer_join = """
            LEFT JOIN payers py ON py.id = pf.resolved_payer_id
        """
        payer_id_col = "pf.resolved_payer_id AS payer_key"
        payer_name_col = "pf.payer_name AS canonical_name"
        payer_status_col = "py.donor_status"
        payer_indiv_col = "COALESCE(py.is_private_individual, 0)"

    sql = f"""
    SELECT
        {payer_id_col},
        {payer_name_col},
        {payer_status_col} AS donor_status,
        {payer_indiv_col} AS is_private_individual,
        pf.member_id,
        m.name AS member_name,
        m.party,
        m.constituency,
        pf.category,
        pf.payment_type,
        ROUND(
            CASE
                WHEN pf.is_regular = 0 THEN pf.amount
                ELSE pf.amount * MAX(0,
                    (julianday(MIN(COALESCE(pf.end_date, ?), ?))
                     - julianday(MAX(COALESCE(pf.start_date, pf.registered), ?)))
                    / {PRORATA_CASE}
                )
            END
        , 2) AS computed_amount
    FROM payments_full pf
    {payer_join}
    JOIN members m ON m.mnis_id = pf.member_id
    WHERE {_window_where()}
    ORDER BY payer_key, computed_amount DESC
    """
    params = ([as_of_date, as_of_date, since_date]
              + _window_params(as_of_date, since_date))
    rows = conn.execute(sql, params).fetchall()

    donors = {}
    for r in rows:
        key = r['payer_key']
        amt = r['computed_amount'] or 0
        if amt <= 0:
            continue

        if key not in donors:
            donors[key] = {
                'payer_id': key,
                'canonical_name': r['canonical_name'],
                'donor_status': r['donor_status'] or 'Employers & Other',
                'is_private_individual': bool(r['is_private_individual']),
                'total_amount': 0, 'total_monetary': 0, 'total_inkind': 0,
                'payment_count': 0, 'mp_set': {},
                'category_breakdown': {c: 0 for c in ['1.1', '1.2', '2', '3', '4', '5']},
            }

        d = donors[key]
        d['total_amount'] += amt
        d['payment_count'] += 1
        if r['payment_type'] == 'Monetary':
            d['total_monetary'] += amt
        else:
            d['total_inkind'] += amt

        cat = r['category']
        if cat in d['category_breakdown']:
            d['category_breakdown'][cat] += amt

        mp_id = r['member_id']
        if mp_id not in d['mp_set']:
            d['mp_set'][mp_id] = {
                'mnis_id': mp_id, 'name': r['member_name'],
                'party': r['party'], 'constituency': r['constituency'],
                'amount': 0, 'categories': set(),
            }
        d['mp_set'][mp_id]['amount'] += amt
        d['mp_set'][mp_id]['categories'].add(cat)

    donor_list = []
    for d in donors.values():
        portfolio = sorted(d['mp_set'].values(), key=lambda x: x['amount'], reverse=True)
        for p in portfolio:
            p['amount'] = round(p['amount'], 2)
            p['categories'] = sorted(p['categories'])
        donor_list.append({
            'payer_id': d['payer_id'],
            'canonical_name': d['canonical_name'],
            'donor_status': d['donor_status'],
            'is_private_individual': d['is_private_individual'],
            'total_amount': round(d['total_amount'], 2),
            'total_monetary': round(d['total_monetary'], 2),
            'total_inkind': round(d['total_inkind'], 2),
            'payment_count': d['payment_count'],
            'mp_count': len(portfolio),
            'portfolio': portfolio,
            'category_breakdown': {k: round(v, 2) for k, v in d['category_breakdown'].items()},
        })

    donor_list.sort(key=lambda x: x['total_amount'], reverse=True)

    status_agg = {}
    for d in donor_list:
        s = d['donor_status']
        if s not in status_agg:
            status_agg[s] = {'status': s, 'count': 0, 'total': 0}
        status_agg[s]['count'] += 1
        status_agg[s]['total'] += d['total_amount']
    status_summary = sorted(status_agg.values(), key=lambda x: x['total'], reverse=True)
    for s in status_summary:
        s['total'] = round(s['total'], 2)

    return donor_list, status_summary


def build_philanthropists(conn, as_of_date, since_date, use_master):
    """Build data for MPs who donated their earnings to charity/community."""
    if use_master:
        payer_name = "COALESCE(pm.canonical_name, pf.payer_name)"
        payer_join = """
            LEFT JOIN payers_master_map pmm ON pmm.payer_id = pf.resolved_payer_id
            LEFT JOIN payers_master pm ON pm.id = pmm.master_id
        """
    else:
        payer_name = "pf.payer_name"
        payer_join = ""

    sql = f"""
    SELECT
        pf.member_id,
        pf.member_name,
        m.party,
        m.constituency,
        {payer_name} AS payer_name,
        pf.amount,
        pf.donated_to,
        pf.category,
        pf.payment_date,
        pf.registered
    FROM payments_full pf
    JOIN members m ON m.mnis_id = pf.member_id
    {payer_join}
    WHERE pf.is_donated = 1
      AND pf.is_received = 1
    ORDER BY pf.amount DESC
    """
    rows = conn.execute(sql).fetchall()

    # Aggregate by MP
    mp_data = {}
    for r in rows:
        mid = r['member_id']
        if mid not in mp_data:
            mp_data[mid] = {
                'mnis_id': mid,
                'name': r['member_name'],
                'party': r['party'],
                'constituency': r['constituency'],
                'thumbnail_url': THUMBNAIL_URL.format(mnis_id=mid),
                'total_donated': 0,
                'donations': [],
            }
        mp_data[mid]['total_donated'] += r['amount']
        mp_data[mid]['donations'].append({
            'amount': r['amount'],
            'payer': r['payer_name'],
            'donated_to': r['donated_to'],
            'category': r['category'],
            'date': r['payment_date'] or r['registered'],
        })

    philanthropists = sorted(mp_data.values(), key=lambda x: x['total_donated'], reverse=True)
    for i, p in enumerate(philanthropists):
        p['rank'] = i + 1
        p['total_donated'] = round(p['total_donated'], 2)
        for d in p['donations']:
            d['amount'] = round(d['amount'], 2)

    return philanthropists


def build_payment_details(conn, use_master):
    """Export every payment record grouped by member_id for detail pages."""
    if use_master:
        payer_name = "COALESCE(pm.canonical_name, pf.payer_name)"
        payer_join = """
            LEFT JOIN payers_master_map pmm ON pmm.payer_id = pf.resolved_payer_id
            LEFT JOIN payers_master pm ON pm.id = pmm.master_id
        """
        payer_id_col = "COALESCE(pmm.master_id, pf.resolved_payer_id)"
    else:
        payer_name = "pf.payer_name"
        payer_join = ""
        payer_id_col = "pf.resolved_payer_id"

    sql = f"""
    SELECT
        pf.member_id,
        {payer_id_col} AS payer_id,
        {payer_name} AS payer_name,
        pf.category,
        pf.summary,
        pf.description,
        pf.payment_type,
        pf.is_regular,
        pf.amount,
        pf.period,
        pf.payment_date,
        pf.start_date,
        pf.end_date,
        pf.is_sole_beneficiary,
        pf.is_donated,
        pf.donated_to,
        pf.registered,
        pf.job_title
    FROM payments_full pf
    {payer_join}
    ORDER BY pf.member_id, pf.amount DESC
    """
    rows = conn.execute(sql).fetchall()

    result = {}
    for r in rows:
        mid = r['member_id']
        if mid not in result:
            result[mid] = []
        result[mid].append({
            'payer_id': r['payer_id'],
            'payer': r['payer_name'],
            'category': r['category'],
            'summary': r['summary'],
            'description': r['description'],
            'payment_type': r['payment_type'],
            'is_regular': bool(r['is_regular']),
            'amount': r['amount'],
            'period': r['period'],
            'payment_date': r['payment_date'],
            'start_date': r['start_date'],
            'end_date': r['end_date'],
            'is_sole_beneficiary': bool(r['is_sole_beneficiary']),
            'is_donated': bool(r['is_donated']),
            'donated_to': r['donated_to'],
            'registered': r['registered'],
            'job_title': r['job_title'],
        })

    return result


def build_meta(as_of_date, since_date, individuals):
    total_monetary = sum(i['total_monetary_12m'] for i in individuals)
    total_inkind = sum(i['total_inkind_12m'] for i in individuals)
    return {
        'generated_at': datetime.now().isoformat(),
        'as_of_date': as_of_date,
        'since_date': since_date,
        'total_mps_with_payments': len(individuals),
        'total_monetary_12m': round(total_monetary, 2),
        'total_inkind_12m': round(total_inkind, 2),
        'total_combined_12m': round(total_monetary + total_inkind, 2),
        'party_colours': PARTY_COLOURS,
        'category_labels': CATEGORY_LABELS,
    }


def main():
    parser = argparse.ArgumentParser(description='Export interests.db to JSON for The Westminster 100')
    parser.add_argument('--as-of', type=str, default=None, help='As-of date (YYYY-MM-DD)')
    parser.add_argument('--output-dir', type=str, default='site/data')
    parser.add_argument('--db', type=str, default='interests.db')
    args = parser.parse_args()

    as_of_date = args.as_of or date.today().isoformat()
    since_date = (date.fromisoformat(as_of_date) - timedelta(days=365)).isoformat()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Exporting data as of {as_of_date} (since {since_date})")

    conn = get_connection(args.db)
    use_master = has_payers_master(conn)
    if use_master:
        print("Using payers_master for canonical donor names")
    else:
        print("payers_master not found, using payers table directly")

    print("Building individuals...")
    individuals = build_individuals(conn, as_of_date, since_date, use_master)
    print(f"  {len(individuals)} MPs with payments")
    if individuals:
        print(f"  #1: {individuals[0]['name']} — £{individuals[0]['total_monetary_12m']:,.2f}")

    print("Building parties...")
    parties = build_parties(individuals, conn)
    print(f"  {len(parties)} parties")

    print("Building donors...")
    donor_list, status_summary = build_donors(conn, as_of_date, since_date, use_master)
    print(f"  {len(donor_list)} donors")

    print("Building philanthropists...")
    philanthropists = build_philanthropists(conn, as_of_date, since_date, use_master)
    total_donated = sum(p['total_donated'] for p in philanthropists)
    print(f"  {len(philanthropists)} MPs donated £{total_donated:,.2f}")

    print("Building payment details...")
    payment_details = build_payment_details(conn, use_master)
    total_payments = sum(len(v) for v in payment_details.values())
    print(f"  {total_payments} payments across {len(payment_details)} MPs")

    meta = build_meta(as_of_date, since_date, individuals)

    def write_json(filename, data):
        path = output_dir / filename
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  Written {filename} ({path.stat().st_size / 1024:.1f} KB)")

    write_json('meta.json', meta)
    write_json('individuals.json', individuals)
    write_json('parties.json', parties)
    write_json('donors.json', {'donors': donor_list, 'donor_status_summary': status_summary})
    write_json('philanthropists.json', philanthropists)
    # Payment details keyed by string member_id for JS lookup
    write_json('payments_detail.json', {str(k): v for k, v in payment_details.items()})

    conn.close()
    print("Done!")


if __name__ == '__main__':
    main()
