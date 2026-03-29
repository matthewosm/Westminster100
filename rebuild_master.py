import sqlite3, re, sys, io
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

conn = sqlite3.connect('interests.db')
c = conn.cursor()
c.execute('SELECT id, name, address, nature_of_business, donor_status, is_private_individual FROM payers ORDER BY name')
rows = c.fetchall()

def normalize(name):
    n = name.lower().strip()
    n = n.rstrip('.,;:')
    n = re.sub(r'\b(limited|ltd)\b\.?', 'ltd', n)
    n = re.sub(r'\b(plc|p\.l\.c\.)\b', 'plc', n)
    n = re.sub(r'\b(incorporated|inc)\b\.?', 'inc', n)
    n = re.sub(r'\b(company|co)\b\.?', 'co', n)
    n = re.sub(r'^the\s+', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    n2 = re.sub(r'[^a-z0-9 ]', '', n).strip()
    return n2

# Phase 1: group by normalized name
groups = defaultdict(list)
for row in rows:
    key = normalize(row[1])
    groups[key].append(row)

# Phase 2: Manual merge rules
manual_merges = [
    # Doha Forum variants
    ['doha forum', 'doha forum  ministry of foreign affairs of the state of qatar',
     'doha forum ministry of foreign affairs of the state of qatar',
     'doha forumministry of foreign affairs of the state of qatar'],

    # Taiwan Ministry of Foreign Affairs
    ['taiwan ministry of foreign affairs', 'taiwanese ministry of foreign affairs',
     'taiwans ministry of foreign affairs', 'ministry of foreign affairs taiwan'],

    # Typos
    ['armed force parliamentary scheme', 'armed forces parliamentary scheme'],
    ['communication workers union', 'communications workers union'],
    ['commewealth war graves commission', 'commonwealth war graves commission'],
    ['pece and justice project', 'peace and justice project'],
    ['r  a chamionships ltd', 'r  a championships ltd', 'ra championships ltd'],
    ['mr abdul sattar sheremohammod known as shere m sattar',
     'mr adbul sattar sheremohammod known as shere m sattar'],
    ['alan montgomery', 'alan montomery'],

    # Punctuation/spacing
    ['j c bamford excavators ltd', 'jc bamford excavators ltd'],
    ['viking  penguin', 'viking penguin'],
    ['a m heath  co ltd', 'am heath  co ltd'],

    # BPI mega-group
    ['bpi', 'bpi british recorded music industry ltd', 'bpi british recorded music ltd',
     'british recorded music industry', 'british recorded music industry ltd'],

    # Conservative Friends of Israel
    ['conservative friends of israel', 'conservative friends of israel ltd',
     'conservative friends of israel cfi ltd', 'conservative friends of israel ltd cfi ltd'],

    # Government of Gibraltar
    ['government of gibraltar', 'hm government of gibraltar', 'hm government gibraltar'],

    # ALCS / Authors Licensing
    ['alcs', 'authors licensing and collecting society',
     'authors licensing and collecting society alcs'],

    # & vs "and"
    ['energy  climate intelligence unit', 'energy and climate intelligence unit'],
    ['centre for turkey studies  development', 'centre for turkey studies and development',
     'centre for turkey studies and development ltd'],

    # Hyphenation
    ['konrad adenauer stiftung', 'konradadenauerstiftung'],

    # Missing words
    ['house of representatives cyprus', 'house of representatives of cyprus'],

    # Football Association + FA Group (NOT Premier League)
    ['football association', 'football association ltd', 'fa group'],

    # Football Association Premier League (merge Ltd variants only)
    ['football association premier league', 'football association premier league ltd'],

    # EFL / English Football League
    ['efl', 'english football league'],

    # Football clubs with/without Ltd
    ['sunderland association football club', 'sunderland association football club ltd'],
    ['nottingham forest football club', 'nottingham forest football club ltd'],
    ['warwickshire county cricket club', 'warwickshire county cricket club ltd'],

    # Acronyms in parens
    ['national union of journalists', 'national union of journalists nuj'],
    ['university and college union', 'university and college union ucu'],
    ['public and commercial services union', 'public and commercial services union pcs'],
    ['coalition for global prosperity', 'coalition for global prosperity cgp'],
    ['international centre of justice for palestinians',
     'international centre of justice for palestinians icjp'],

    # European Parliamentary Forum (merge, shorter canonical name)
    ['european parliamentary forum for sexual  reproductive rights',
     'european parliamentary forum for sexual  reproductive rights epf'],

    # Acronym prefix
    ['marketing in partnership ltd', 'mip marketing in partnership ltd'],
    ['uk interactive entertainment association ltd',
     'ukie uk interactive entertainment association ltd'],

    # United Nations Population Fund
    ['united nations population fund via the all party parliamentary group on global sexual and reproductive health and as per its appg register',
     'united nations un population fund via the all party parliamentary group on global sexual and reproductive health and as per its appg register'],

    # Friedrich-Ebert-Stiftung + UK
    ['friedrichebertstiftung', 'friedrichebertstiftung uk'],

    # Home/Homes for Britain (typo)
    ['home for britain ltd', 'homes for britain ltd'],

    # Patrick Foster
    ['patrick foster', 'patrick h foster'],
]

# Canonical name overrides: normalized_key -> desired name
canonical_overrides = {
    'european parliamentary forum for sexual  reproductive rights': 'European Parliamentary Forum',
    'united nations population fund via the all party parliamentary group on global sexual and reproductive health and as per its appg register': 'United Nations Population Fund',
    'doha forum': 'Doha Forum',
    'authors licensing and collecting society': "Authors' Licensing and Collecting Society (ALCS)",
}

# IDs to exclude from their auto-matched group and keep as standalone
# (ID 943 is "London Football Association", not "The Football Association")
standalone_overrides = {943: 'London Football Association'}

# Pull out standalone overrides before merging
pulled_out = {}  # id -> row tuple
for key in list(groups.keys()):
    groups[key] = [e for e in groups[key] if e[0] not in standalone_overrides or
                   pulled_out.update({e[0]: e}) is not None]  # hack: always falsy update
    # Clean version:
groups = defaultdict(list)
for row in rows:
    if row[0] in standalone_overrides:
        pulled_out[row[0]] = row
    else:
        key = normalize(row[1])
        groups[key].append(row)

# Apply manual merges
for merge_group in manual_merges:
    existing_keys = [k for k in merge_group if k in groups]
    if len(existing_keys) <= 1:
        continue
    target = existing_keys[0]
    for k in existing_keys[1:]:
        groups[target].extend(groups[k])
        del groups[k]


def pick_best(entries):
    def score(e):
        s = 0
        if e[2]: s += 2  # has address
        if e[3]: s += 3  # has nature_of_business
        if e[4]: s += 2  # has donor_status
        s += len(e[1]) / 100  # prefer longer/more complete names
        if e[2]: s += len(e[2]) / 200  # prefer longer addresses
        return s
    return max(entries, key=score)


# Build master table
c.execute('DROP TABLE IF EXISTS payers_master_map')
c.execute('DROP TABLE IF EXISTS payers_master')

c.execute('''
CREATE TABLE payers_master (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name          TEXT NOT NULL,
    address                 TEXT,
    nature_of_business      TEXT,
    is_private_individual   BOOLEAN DEFAULT 0,
    donor_status            TEXT,
    UNIQUE(canonical_name)
)
''')

c.execute('''
CREATE TABLE payers_master_map (
    payer_id    INTEGER NOT NULL REFERENCES payers(id),
    master_id   INTEGER NOT NULL REFERENCES payers_master(id),
    PRIMARY KEY (payer_id)
)
''')

dupe_count = 0
for key in sorted(groups.keys()):
    entries = groups[key]
    best = pick_best(entries)
    name = canonical_overrides.get(key, best[1].strip().rstrip(','))

    c.execute(
        '''INSERT INTO payers_master (canonical_name, address, nature_of_business,
           donor_status, is_private_individual) VALUES (?, ?, ?, ?, ?)''',
        (name, best[2], best[3], best[4], best[5]))
    master_id = c.lastrowid
    for e in entries:
        c.execute('INSERT INTO payers_master_map (payer_id, master_id) VALUES (?, ?)',
                  (e[0], master_id))

    if len(entries) > 1:
        dupe_count += 1

# Add standalone overrides as their own master entries
for payer_id, row in pulled_out.items():
    name = standalone_overrides[payer_id]
    c.execute(
        '''INSERT INTO payers_master (canonical_name, address, nature_of_business,
           donor_status, is_private_individual) VALUES (?, ?, ?, ?, ?)''',
        (name, row[2], row[3], row[4], row[5]))
    master_id = c.lastrowid
    c.execute('INSERT INTO payers_master_map (payer_id, master_id) VALUES (?, ?)',
              (payer_id, master_id))

conn.commit()

# Stats
c.execute('SELECT COUNT(*) FROM payers_master')
master_count = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM payers_master_map')
map_count = c.fetchone()[0]

print(f"Original payers: {len(rows)}")
print(f"Master records: {master_count}")
print(f"Rows saved: {len(rows) - master_count}")
print(f"Duplicate groups: {dupe_count}")
print(f"Mapping entries: {map_count}")

# Top consolidated groups
print("\n--- Top 25 consolidated groups ---")
c.execute('''
    SELECT pm.id, pm.canonical_name, COUNT(*) as cnt, GROUP_CONCAT(m.payer_id, ', ') as ids
    FROM payers_master pm
    JOIN payers_master_map m ON m.master_id = pm.id
    GROUP BY pm.id
    HAVING cnt > 1
    ORDER BY cnt DESC
    LIMIT 25
''')
for row in c.fetchall():
    print(f"  {row[2]:>2}x  '{row[1]}'  <- IDs: [{row[3]}]")

# Verify all mapped
c.execute('''SELECT COUNT(*) FROM payers p
             LEFT JOIN payers_master_map m ON m.payer_id = p.id
             WHERE m.master_id IS NULL''')
unmapped = c.fetchone()[0]
print(f"\nUnmapped payers: {unmapped}")

conn.close()
