

1 # Westminster Interests — 
 Requirements                                             
    2                                                                                                                                                                                                              3 **Date:** 2026-04-18                                                                                                                                                                                     
    4 **Status:** Draft — ready for planning                                                                                                                                                                   
    5 **Supersedes:** The existing `astro/` site ("The Westminster 100")
    6                                                                                                                                                                                                              7 ## Summary                                                                                                                                                                                                   8                                                                                                                                                                                                          
    9 Rebuild the UK Parliamentary financial-interests site from scratch as a neutral, research-grade reference work. Sameunderlying data (SQLite → JSON pipeline). New identity: **Westminster Interests**
      . New UI system: **Starwind UI** (shadcn-for-Astro on Astro v6 + Tailwind v4). New voice: minimal, authoritative, objective. Newspaper-like monochrome visual language with a single accent colour. Th   
      e existing satirical wrap ("Franchises", "Patrons", "Principal Patron", "Revenue Streams", "Benefactors", "Elite Ten", gold rules, dickensian copy) is retired.
   10
   11 ## Goals
   12
   13 - Present the Parliamentary Register of Members' Financial Interests as a citable, browseable reference dataset.
   14 - Serve journalists and researchers first: accurate, linkable, verifiable.
   15 - Replace the satirical framing with an objective one without losing the density of information the current site provides.
   16 - Establish a visual and tonal baseline that can carry further research features over time.
   17
   18 ## Non-goals (explicit)
   19
   20 - No satirical copy, puns, or editorial framing anywhere on the site.
   21 - No dashboards-for-the-sake-of-dashboards. Charts appear only where they aid interpretation.
   22 - No live database; this remains a statically built Astro site fed by pre-computed JSON.
   23 - No CSV/JSON download surface in v1. (Deferred — revisit once the site is stable.)
   24 - No migration of the existing satirical site — the old `astro/` directory is preserved in the repo for reference until the new build replaces production.
   25
   26 ## Audience
   27
   28 **Primary:** journalists and researchers (reporters, academics, transparency campaigners) who need citable figures, primary-source links, date-window clarity, and deep filtering.
   29
   30 Secondary use by general public and constituents is accepted but does not drive design decisions.
   31
   32 ## Identity & voice
   33
   34 - **Name:** Westminster Interests
   35 - **Tagline candidate:** "UK MPs' declared financial interests, as registered with Parliament." (To confirm during build.)
   36 - **Voice:** neutral, declarative, precise. Short sentences. No editorial judgement. Numbers carry the weight.
   37 - **Retired terminology:**
   38   - "The Franchises" → Parties
   39   - "The Patrons" → Payers (or Donors where category-appropriate)
   40   - "The Philanthropists" (standalone page) → removed; surfaced as a flag/filter on payment rows (see below)
   41   - "Principal Patron" → Top payer
   42   - "Revenue Streams" → Payment count (or Sources)
   43   - "Benefactors" → Donors
   44   - "The Elite Ten" / "The Podium" → removed; replaced by plain "Highest earners" view
   45
   46 ## Organising principle
   47
   48 The site is framed as **a full register**, not a top-100 leaderboard.
   49
   50 - Default navigation entry points are **Members** (1,515 rows), **Payers**, **Parties**, **APPGs**, **Methodology**.
   51 - Ranking views (e.g. "Highest earners over the last 12 months") exist as **saved views** over the full dataset — sorted/filtered tables, not a separate curated list.
   52
   53 ## Time model
   54
   55 The site supports multiple, selectable date windows with **trailing 12 months as the default**.
   56
   57 - **Windows:** Trailing 12m · YTD · 2025 · 2024 · Since July 2024 general election · All-time.
   58 - **Implementation:** pre-compute one JSON snapshot per window at build time. The client swaps between snapshots; no runtime DB needed.
   59 - Every page displays an **"as of [date]"** stamp sourced from the build timestamp. Citations rely on this.
   60
   61 ## Information architecture
   62
   63 Top-level navigation:
   64
   65 - **Members** — `/members` (full list, filterable, sortable)
   66 - **Payers** — `/payers` (full list of payers, sortable by total paid)
   67 - **Parties** — `/parties` (party-level aggregates)
   68 - **APPGs** — `/appgs` (new: browse payments by All-Party Parliamentary Group)
   69 - **Methodology** — `/methodology` (new: sources, definitions, caveats)
   70
   71 Detail pages:
   72
   73 - `/member/[mnis_id]` — MP detail (replaces current `/mp/[mnis_id]`)
   74 - `/payer/[id]` — payer detail (replaces current `/patron/[id]`)
   75 - `/party/[slug]` — party detail
   76 - `/appg/[slug]` — APPG detail (new)
   77
   78 Homepage (`/`):
   79
   80 - Overview numbers (total declared across window, number of earning members, number of payers).
   81 - Small set of featured views: Highest earners (link to `/members?sort=total`), Largest payers (link to `/payers?sort=total`), Most recent updates.
   82 - "As of [date]" stamp + link to Methodology.
   83 - No ranked leaderboard on the homepage itself — the homepage points into the register rather than summarising it editorially.
   84
   85 URL migration: the old `/mp/[mnis_id]` and `/patron/[id]` URLs from the existing site should be preserved as permanent redirects to the new paths if possible. **Open question — see below.**
   86
   87 ## Key new capabilities
   88
   89 1. **Methodology page** — sources, the trailing-window logic, in-kind vs monetary, pro-rata regular payment calculation, data quality caveats (missing dates, payer dedup imperfection, sole-beneficia   
      ry flag, donated-onwards flag, confidential payers, Cat 1.2 per-period amounts), data freshness date.
   90 2. **Per-row source links** — every payment row links back to its underlying Parliamentary Register entry on `interests.parliament.uk`. Requires capturing the source URL (or a deterministic pattern    
      to reconstruct it) in the import pipeline.
   91 3. **APPG browsing** — index page and detail pages for All-Party Parliamentary Groups. 159 payments are APPG-linked. A **reconciliation pass is required** because APPG names are not standardised in    
      the source (e.g. "APPG on Ukraine" / "APPG Ukraine" / "Ukraine" all refer to the same group). This should be a maintainable mapping (e.g. a JSON/CSV alias file) rather than heuristic normalisation a   
      t build time.
   92
   93 ## Member detail page (research surface)
   94
   95 This is the most important page in the site. Requirements:
   96
   97 - Photo, name, party, constituency, house (Commons/Lords), start date.
   98 - Window selector (trailing 12m / YTD / 2025 / 2024 / since election / all-time). Persists in URL via query param so it's linkable.
   99 - Totals for the selected window: total monetary, total in-kind, count of payments, count of distinct payers.
  100 - Category breakdown (Cat 1.1, 1.2, 2, 3, 4, 5) with counts and totals — table first, optional restrained chart.
  101 - Full payment history for the selected window, as a dense table with columns: date, category, payer (linked to `/payer/[id]`), job title (Cat 1.1/1.2), amount, monetary/in-kind flag, APPG (if any,    
      linked), donated-onwards flag (if any), source link to parliament.uk.
  102 - Flags surfaced inline where relevant: `is_sole_beneficiary = 0` (shared benefit), `is_donated = 1` (donated onwards), ultimate-payer override, confidential payer.
  103
  104 ## Payer detail page
  105
  106 - Payer name, address (if shown in source), donor_status (Individual / Company / Trade Union / LLP / Trust / Friendly Society / Unincorporated Association / Registered Party / Other).
  107 - Totals paid across the selected window.
  108 - Full list of MPs paid, with amounts.
  109 - Full list of payments (same columns as MP detail, minus the "payer" column).
  110
  111 ## APPG detail page
  112
  113 - APPG canonical name + known aliases.
  114 - Total value of declared APPG-linked hospitality/visits/gifts across the selected window.
  115 - List of MPs with payments linked to the APPG.
  116 - List of payers (sponsors of the APPG-linked payments).
  117 - List of payments with source links.
  118
  119 ## Visual & design system
  120
  121 - **Framework:** Starwind UI components on Astro v6 + Tailwind v4. Use the CLI (`pnpx starwind@latest init` / `add <component>`).
  122 - **Palette:** monochrome + single accent.
  123   - Background: near-white. Text: near-black. Borders, dividers, rules: mid-gray.
  124   - Single accent colour (e.g. ink-red or deep blue — pick one during implementation) used sparingly: links, key figures, one-off emphasis.
  125   - Party identifiers: communicated via a 2–3 letter tag (CON, LAB, LD, SNP, etc.) and/or small neutral shape. **No party colours in the UI.** (This is a tonal decision — party colour scanning is co   
      nvenient but undermines the monochrome authority we want.)
  126   - Charts: grayscale only in v1. Reassess once the site is live.
  127 - **Typography:** serif for headlines and large figures (newspaper feel); sans-serif or mono for tables and small print. Respect Starwind's defaults where reasonable and override where the newspaper   
       feel requires it.
  128 - **Density:** tables take priority over cards. Dense, scannable, sortable. Cards only on homepage entry points.
  129 - **Motion:** minimal. No decorative transitions; only state changes (sort, filter, window swap).
  130 - **Dark mode:** Starwind supports dark mode by default. **Open question — see below.**
  131
  132 ## Data pipeline changes
  133
  134 - Continue building from the existing SQLite (`interests.db`) produced by `import.py`. Do not change the schema to support this rebuild unless necessary.
  135 - Extend the build step to produce **one JSON snapshot per time window** (12m, YTD, 2025, 2024, since-election, all-time), rather than a single 12m snapshot.
  136 - Extend the import / export pipeline to capture a **parliament.uk source URL (or reconstruction pattern)** for each payment.
  137 - Add an **APPG alias/canonicalisation mapping** (maintained file) applied at export time. Surface "unmapped APPG names" in the Methodology page so the mapping can be improved over time.
  138
  139 ## Success criteria
  140
  141 - A journalist can land on an MP's page, select a window, find a specific payment, click through to the Parliamentary source, and cite the figure with an "as of" date — without reading any editorial   
       copy.
  142 - Every numeric claim on the site is reproducible from the JSON snapshots and traceable to a row in `interests.db` and a row on `interests.parliament.uk`.
  143 - The site reads as a reference work, not a publication. A reader unfamiliar with the old site should not detect any satire, judgement, or voice.
  144 - Page titles, headings, and copy use neutral nouns throughout (Payments, Payers, Members, Parties, Groups) — no retained satirical terminology.
  145
  146 ## Out of scope for v1
  147
  148 - CSV/JSON downloads (deferred).
  149 - User accounts, saved searches, alerts.
  150 - Live/daily rebuilds. Rebuild cadence remains manual/periodic.
  151 - Visualisation-heavy features (interactive network graphs of MP↔payer relationships, etc.).
  152 - Internationalisation, accessibility beyond sensible defaults (WCAG AA contrast, semantic HTML, keyboard-navigable tables). No explicit assistive-tech audit in v1, but no deliberate regressions fro   
      m the current site either.
  153
  154 ## Open questions
  155
  156 These do not block planning but should be resolved during implementation.
  157
  158 1. **Dark mode on v1?** Starwind ships it free. Authority-register aesthetic trends light-only. Research use (long sessions) favours an optional dark theme. Recommendation: ship light-only on v1; ad   
      d dark mode later if researcher feedback asks for it.
  159 2. **Old URL redirects.** Should `/mp/[mnis_id]` and `/patron/[id]` 301 to the new `/member/` and `/payer/` paths? Depends on whether the old site has been shared/indexed externally. If no external    
      links exist, keep old paths.
  160 3. **Charts on MP and category pages.** Keep donut/category charts (reduced to grayscale), replace with horizontal bars, or drop entirely in favour of tables? Recommendation: start with tables only;   
       add small horizontal bar charts next to category totals if the tables feel too sparse once built.
  161 4. **Accent colour choice.** Ink-red (editorial) vs deep blue (civic / link-coded). Recommendation: deep blue — reads as civic/reference, avoids partisan connotation.
  162 5. **Tagline copy.** "UK MPs' declared financial interests, as registered with Parliament." — confirm, or propose alt  160 3. **Charts on MP and category pages.** Keep donut/category charts (reduced to grayscale), replace with horizontal bars, or drop entirely in favour of tables? Recommendation: start with tables only;
       add small horizontal bar charts next to category totals if the tables feel too sparse once built.
  161 4. **Accent colour choice.** Ink-red (editorial) vs deep blue (civic / link-coded). Recommendation: deep blue — reads as civic/reference, avoids partisan connotation.
  162 5. **Tagline copy.** "UK MPs' declared financial interests, as registered with Parliament." — confirm, or propose alternative, during implementation.
  163 6. **Deployment.** Does the new build take over the production domain at launch, or run in parallel at a different path/subdomain first? (Planning assumes the new build replaces production at launch
       unless told otherwise.)
  164
  165 ## References
  166
  167 - Source code of current site: `astro/` (to preserve during the rebuild; mined for data-pipeline logic, not design). 
  168 - Data pipeline: `import.py`, `schema.sql`, `rebuild_master.py`, `export.py`, `Data/`, `MP list.csv`.
  169 - Starwind UI docs: install via `pnpx starwind@latest init`, components added individually via CLI.
  170 - Parliamentary source: https://interests.parliament.uk/ (to confirm stable URL pattern for per-payment links during pipeline work).
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌

 189 +                                                                                                                      190 +---                                                                                                                   191 +                                                                                                                      192 +## Technical design — data, rendering, schema
 193 +
 194 +This section supersedes the earlier **Data pipeline changes** section where they disagree. It captures the decisions 
     +made during the Phase 1.3 deepening pass on 2026-04-18 covering build output, rendering stack, and schema changes.   
 195 +                                                                                                                     
 196 +### 1. Data storage
 197 +                                                                                                                     
 198 +**Pipeline shape:** `interests.db` (SQLite) remains the single source of truth. `export.py` reads it once per build a
     +nd produces a static tree of JSON files under `astro/src/data/`. No runtime DB, no live queries in the browser.      
 199 +                                                                                                                     
 200 +**Build output layout — per-entity, per-window JSON.** Each entity (member, payer, party, APPG) gets one JSON file. T
     +hat file carries all six windows inside it, so the window selector is a client-side key swap with no extra network ca
     +lls.
 201 +                                                                                                                     
 202 +```
 203 +astro/src/data/
 204 +  meta.json                      # generated_at, build timestamp, window definitions
 205 +  index/
 206 +    members.json                 # light list: id, name, party, totals[window], rank[window]
 207 +    payers.json                  # light list: id, canonical_name, status, totals[window]
 208 +    parties.json                 # party aggregates, all windows
 209 +    appgs.json                   # APPG list: slug, canonical_name, totals[window]
 210 +  members/
 211 +    {mnis_id}.json               # full MP detail: bio, categories, payments, top_payers per window
 212 +  payers/
 213 +    {payer_id}.json              # full payer detail: totals, mp_portfolio, payments per window
 214 +  appgs/
 215 +    {slug}.json                  # full APPG detail: totals, mps, payers, payments per window
 216 +```
 217 +                                                                                                                     
 218 +Index files drive the filterable list pages. Detail files drive `/member/[mnis_id]`, `/payer/[id]`, `/appg/[slug]`. P
     +arty detail is small enough to stay inside `index/parties.json`.
 219 +                                                                                                                     
 220 +**Why this shape:**
 221 +- Per-page transfer stays small (a single MP page pulls one `members/1423.json` rather than a multi-MB bundle).      
 222 +- Adding a window later means regenerating JSONs, not rewriting code.
 223 +- Grid.js on index pages fetches only the index file, not the detail rows.
 224 +- Storage cost on disk grows (roughly 6x today's size), but disk is cheap and Astro static hosts gzip on the wire.   
 225 +                                                                                                                     
 226 +**Reproducibility / "as of" stamp.** `meta.json` records the build timestamp and the exact `as_of_date` each window w
     +as computed against. Every page reads that stamp for the citation footer. For durable citeability, archive each produ
     +ction build's `meta.json` + data tree in-repo (e.g. `docs/snapshots/YYYY-MM-DD/`) during deploys. **Open question — c
     +onfirm retention policy during implementation.**
 227 +                                                                                                                     
 228 +**CSV input archive.** Keep `Data/` as-is. Consider timestamping the CSVs in `Data/archive/YYYY-MM-DD/` at each inges
     +t so any published figure can be re-derived from the exact source row that produced it.
 229 +                                                                                                                     
 230 +### 2. Rendering
 231 +                                                                                                                     
 232 +**Stack:** Astro v6 static build + Tailwind v4 + Starwind UI for the design system. Pages are prerendered HTML. No SS
     +R.
 233 +                                                                                                                     
 234 +**Interactive tables:** [Grid.js](https://gridjs.io/) (~45KB, vanilla, framework-agnostic) dropped in as Astro island
     +s on the index and detail pages that need sort / filter / search.
 235 +                                                                                                                     
 236 +- `/members` → Grid.js island reading `index/members.json`. Columns: name, party, constituency, total (window), payme
     +nt count (window), donor count (window). Header-click sort. Free-text filter across name + constituency. Window selec
     +tor re-keys the displayed totals without re-fetching.
 237 +- `/payers` → Grid.js island reading `index/payers.json`. Columns: payer name, status, total paid (window), MP count,
     + payment count. Sort + filter.
 238 +- `/appgs` → Grid.js island reading `index/appgs.json`.
 239 +- MP / payer / APPG detail pages: Grid.js on the dense payment-history table (source link, date, category, counterpar
     +ty, amount, flags). Static totals + category breakdown above it.
 240 +                                                                                                                     
 241 +**Window selector:** small vanilla-JS control in the page chrome, writes the chosen window to the URL (`?window=12m` 
     +etc.) and emits an event that the Grid.js island listens for to switch which totals key it displays. Default = `12m`.
     + URL persistence keeps views linkable.
 242 +                                                                                                                     
 243 +**Charts:** grayscale only in v1. Implementation choice (inline SVG vs a tiny chart lib like uPlot or observable-plot
     +) deferred until a real chart is needed — the open question in the original brainstorm about whether to have charts a
     +t all still stands. Start with tables.
 244 +                                                                                                                     
 245 +**Search:** Pagefind already runs in the current `astro/` site's `postbuild`. Keep it. Indexed content = member names
     +, payer names, APPG names, constituencies.
 246 +                                                                                                                     
 247 +**No-JS fallback:** static HTML renders the default window view with an unsortable table. Sort / filter / window-swit
     +ch degrade gracefully.
 248 +                                                                                                                     
 249 +### 3. Schema
 250 +                                                                                                                     
 251 +**SQLite additions.** The existing schema stays intact; we add an APPG reference model and a per-payment source URL. 
 252 +                                                                                                                     
 253 +```sql
 254 +CREATE TABLE appgs (
 255 +    id              INTEGER PRIMARY KEY AUTOINCREMENT,
 256 +    slug            TEXT NOT NULL UNIQUE,       -- url-safe canonical identifier
 257 +    canonical_name  TEXT NOT NULL,              -- display name
 258 +    description     TEXT,                       -- optional short description
 259 +    registered_date DATE                        -- APPG registration date if known
 260 +);
 261 +                                                                                                                     
 262 +CREATE TABLE appg_aliases (
 263 +    raw_name        TEXT PRIMARY KEY,            -- the string as it appears in source data
 264 +    appg_id         INTEGER NOT NULL REFERENCES appgs(id)
 265 +);
 266 +                                                                                                                     
 267 +ALTER TABLE payments
 268 +    ADD COLUMN appg_id    INTEGER REFERENCES appgs(id);   -- replaces free-text payments.appg
 269 +ALTER TABLE payments
 270 +    ADD COLUMN source_url TEXT;                            -- parliament.uk deep link
 271 +```
 272 +                                                                                                                     
 273 +**Migration approach:**
 274 +1. `rebuild_master.py` (or a new `migrate_appgs.py`) seeds `appgs` + `appg_aliases` from a checked-in JSON/CSV mappin
     +g file (`data/appg_map.csv`).
 275 +2. A one-time backfill populates `payments.appg_id` from `payments.appg` via the alias table; unmapped strings are su
     +rfaced to stderr and listed on `/methodology` so the mapping can be improved.
 276 +3. `payments.appg` (free text) is retained for provenance but new code reads `appg_id`.
 277 +4. `source_url` backfill depends on confirming the parliament.uk URL pattern (still an open question in the original 
     +doc).
 278 +                                                                                                                     
 279 +**Views:** extend `payments_full` to include `appg_slug`, `appg_canonical_name`, and `source_url`.
 280 +                                                                                                                     
 281 +**Export JSON shape.** Single nested `totals` block per entity replaces today's flat `total_monetary_12m` / `total_co
     +mbined_alltime` fields. Same shape for every entity and every window, so the window selector is a single key lookup. 
 282 +                                                                                                                     
 283 +```
 284 +totals: {
 285 +  '12m':       { monetary, inkind, combined, payment_count, donor_count },
 286 +  'ytd':       { ... },
 287 +  '2025':      { ... },
 288 +  '2024':      { ... },
 289 +  'since_election': { ... },
 290 +  'all_time':  { ... }
 291 +}
 292 +```
 293 +                                                                                                                     
 294 +Payment rows surface flags inline: `is_sole_beneficiary`, `is_donated`, `donated_to`, `is_ultimate_payer_override`, `
     +is_confidential_payer`. The standalone philanthropists page is retired (per the identity section above); the `is_dona
     +ted` flag is still exported on payment rows so it can surface as a filter chip and an inline badge.
 295 +                                                                                                                     
 296 +**TypeScript types.** One module per entity in `astro/src/types/`, hand-written, imported by pages. No runtime valida
     +tion (zod etc.) — the Python exporter is the only producer, so drift is a build-time concern caught by `tsc`.        
 297 +                                                                                                                     
 298 +```
 299 +astro/src/types/
 300 +  window.ts        # Window = '12m' | 'ytd' | '2025' | '2024' | 'since_election' | 'all_time'
 301 +  totals.ts        # WindowTotals, TotalsByWindow
 302 +  payment.ts       # Payment, PaymentFlags
 303 +  member.ts        # Member, MemberIndexRow
 304 +  payer.ts         # Payer, PayerIndexRow
 305 +  appg.ts          # Appg, AppgIndexRow
 306 +  party.ts         # Party
 307 +  meta.ts          # Meta
 308 +```
 309 +                                                                                                                     
 310 +Pages `import type { Member } from '@/types/member'` and read the corresponding JSON with that type. Field renames in
     + `export.py` surface as `astro build` failures rather than silent runtime breakage.
 311 +                                                                                                                     
 312 +### 4. Updated pipeline contract
 313 +                                                                                                                     
 314 +The original **Data pipeline changes** section (above) is now specifically:
 315 +                                                                                                                     
 316 +1. `interests.db` schema: add `appgs`, `appg_aliases`, `payments.appg_id`, `payments.source_url` (§3).
 317 +2. `data/appg_map.csv` (checked in): alias → canonical mapping maintained by hand. Seeded into `appgs` / `appg_aliase
     +s` on rebuild.
 318 +3. `export.py` emits the per-entity/per-window tree described in §1 instead of today's six flat JSONs.
 319 +4. `export.py` writes `meta.json` with build timestamp + window `as_of_date` values.
 320 +5. Every payment record in the exported JSON carries `source_url` (or null with a flag if the pattern couldn't be rec
     +onstructed).
 321 +                                                                                                                     
 322 +### 5. Decisions still deferred to planning
 323 +                                                                                                                     
 324 +- Exact column set for each Grid.js table (cut vs keep as the design comes together).
 325 +- Whether to ship the per-build snapshot archive (`docs/snapshots/`) or accept that only the live site is citable.   
 326 +- Chart-library choice (still gated by the "do we need charts at all?" open question).
 327 +- Parliament.uk `source_url` reconstruction pattern — confirm against real URLs before declaring schema v2 final.    
 328 +- Pagefind index scope (which fields get indexed)