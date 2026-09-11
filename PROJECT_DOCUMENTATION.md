# Sarkari Scheme Finder — Project Documentation

**Purpose of this document:** This is a complete technical handoff document for the
"Sarkari Scheme Finder" project. Give this file to any AI assistant (or developer) and
they should be able to understand the entire codebase, what's already built, how it
works internally, known quirks/bugs already fixed, and what to build next — without
needing to re-read the whole conversation history.

**This version supersedes any earlier copy of this document** — it reflects the
project state after Document Checklist, Reminders, redesigned multi-platform Share,
and the Light/Dark theme button-visibility fix were added.

---

## 1. What This Project Is

A Streamlit web app (runs locally on the user's machine via `streamlit run app.py`)
that helps Indian citizens discover government welfare schemes (central + state-level)
they may be eligible for. Built as a personal/student portfolio project.

**Target user:** A CS engineering student building this as a resume/portfolio project.
Non-expert with Python/Streamlit — has needed heavy hand-holding for local setup
(Anaconda/Jupyter terminal, Windows paths with spaces, OneDrive-synced folders,
firewall/network issues for mobile testing). Assume the user needs plain-language,
step-by-step instructions for anything involving the terminal or file system. The user
also cares a lot about the app looking **professional** — has explicitly pushed back on
decorative emoji clutter, unstyled/invisible buttons, and raw-HTML-as-text rendering
bugs. Treat visual polish and correctness as first-class requirements, not nice-to-haves.

**Tech stack:** Python, Streamlit, Pandas, scikit-learn (TF-IDF search), fpdf2 (PDF
export). No backend server, no database — everything is local files (CSV + JSON).
Share icons are loaded from the public Simple Icons CDN (`cdn.simpleicons.org`) —
requires internet access, same as the Google Fonts import already in use.

**Environment note:** User runs this via Anaconda's Jupyter "Terminal" (a Jupyter
Notebook tab that gives a PowerShell prompt), not a plain Windows terminal. Folder is
inside OneDrive-synced Desktop, path has spaces (`C:\Users\hp\OneDrive\home
fight\Desktop\scheme-chatbot`), which has caused `cd` quoting issues before.

---

## 2. File Structure

```
scheme-chatbot/
├── app.py                 # Main Streamlit app — all UI, routing between 5 modes
├── matcher.py              # Rule-based eligibility matching (Eligibility Check mode)
├── nl_search.py             # Typo-tolerant natural language search (Search Schemes mode)
├── translations.py          # English/Hindi UI text dictionary (single source of truth)
├── history.py                # Search history persistence (local JSON)
├── favorites.py               # Favorites/bookmark persistence (local JSON)
├── reminders.py                 # Per-scheme reminder dates persistence (local JSON)
├── doc_checklist.py              # Category → commonly-required-documents lookup
├── pdf_export.py                   # Generates downloadable PDF report of results
├── requirements.txt                 # streamlit, pandas, scikit-learn, fpdf2
├── data/
│   └── schemes.csv                    # THE dataset — 58 schemes, 12 columns (see §4)
│   └── search_history.json             # auto-created at runtime, excluded from ZIP
│   └── favorites.json                   # auto-created at runtime, excluded from ZIP
│   └── reminders.json                    # auto-created at runtime, excluded from ZIP
├── assets/
│   └── logo.png                           # Custom PIL-generated logo (building + rupee coin badge, "K1" design)
├── .streamlit/
│   └── config.toml                          # Base Streamlit theme colors (dark, saffron accent)
└── README.md                                  # User-facing setup instructions
```

---

## 3. Feature Inventory — What's Built & How It Works

The sidebar has a **Theme toggle** (Dark/Light, at the very top, rendered before
anything else) and a **5-mode radio**: Eligibility Check, Search Schemes, Favorites,
Reminders, Search History.

### 3.1 Eligibility Check mode (`matcher.py`)
Rule-based filtering. User fills a sidebar form (age, gender, occupation, income,
social category, state, scheme category, "only show eligible" checkbox, sort order).
On submit, `match_schemes()`:
1. Filters candidate schemes by state (a scheme applies if its `applicable_state` is
   `"All"` OR matches the selected state) and by `category_type`.
2. For each candidate, `evaluate_scheme()` checks age range, income ceiling, gender,
   social category, occupation — each criterion returns pass/fail, collected into a
   `checks` list (shown as ✔/✘ in an expander).
3. Results are NOT hidden if ineligible (unless "only eligible" is checked) — every
   scheme shows an ELIGIBLE/NOT ELIGIBLE badge. Deliberate design choice — user wants
   every scheme visible with a clear status, not silent filtering.
4. Sorted eligible-first by default; user can also sort by Name/Category/State
   (there is no numeric benefit-amount or deadline field in the data, so those
   sort options were deliberately NOT built — see §7 "explicitly deprioritized").

### 3.2 Search Schemes mode (`nl_search.py`)
Free-text natural language search (e.g. "scholarship for my daughter",
"skolarship" typo, "farm" partial word). Renamed from "Type Your Question" to
**"Search Schemes"** per user request — if you see either name in old notes, they're
the same mode.

- **Typo tolerance:** Uses **character n-gram** TF-IDF (`analyzer="char_wb",
  ngram_range=(3,5)`) instead of word-level matching, so "skolarship" still matches
  "scholarship" (they share enough 3-5 letter chunks).
- **Partial word boost:** `_prefix_bonus()` gives +0.35 score if the query is a
  prefix of any word in a scheme's text (e.g. "studen" → "student").
- **Live suggestions:** `build_vocabulary()` + `get_suggestions()` power an
  autocomplete row below the search box. Clicking a suggestion fills the box via an
  `on_click` callback (NOT direct `st.session_state` mutation after widget
  instantiation — that raises a StreamlitAPIException).
  - Typing a COMPLETE word no longer suggests itself back — exact matches are
    excluded, and complete known words trigger *related*-term suggestions from the
    `SYNONYMS` dict instead (e.g. "student" → "scholarship", "school", "college").
    Simple plural handling too.
- `SYNONYMS` dict maps common English/Hindi-transliterated words (loan, kisan,
  pension, health, etc.) to `category_type` values and gets appended to each
  scheme's search text.
- Search is **live** (reruns on every keystroke) — intentional, per user request
  ("Google jaisa live search").

### 3.3 Favorites mode (`favorites.py`)
Star icon (⭐/☆) on every scheme card, in the same action row as Apply/Share.
`toggle_favorite()` writes scheme names to `data/favorites.json`. Dedicated
"Favorites" sidebar mode lists all bookmarked schemes (joined back against
`schemes.csv`).

### 3.4 Reminders mode (`reminders.py`) — NEW
Each scheme card has a "Reminder" expander: a date picker + optional note + Save/
Remove buttons. Data stored as `{scheme_name: {"date": "YYYY-MM-DD", "note": str}}`
in `data/reminders.json`. The "Reminders" sidebar mode lists all set reminders
sorted by date, with a colored status chip:
- Red "Overdue" (date has passed) or "Due today"
- Orange "Due in N days" (≤7 days away)
- Green "Due in N days" (further out)

**Explicit limitation communicated to the user (keep repeating this if asked to
"add notifications"):** This is a local script, not an always-on server — it CANNOT
send real push/OS notifications. A reminder only becomes visible when the user
manually opens the app. This is stated in-app via `reminders_disclaimer` text and
must stay accurate — don't imply push notifications are supported without a real
backend + notification service, which is a much bigger undertaking (see §7).

### 3.5 Search History mode (`history.py`)
Same JSON-file pattern as favorites/reminders. `save_entry()` is called only on an
*explicit* Search button press (not on every live-search keystroke). Stores mode
(form/nl), key params, result counts, timestamp. Max 50 entries, newest first.
"Clear All History" button available.

### 3.6 Document Checklist (`doc_checklist.py`) — NEW
Every scheme card has a "Documents Required" expander. `get_documents(category_type,
lang)` looks up a **category-level** (not per-scheme) list of commonly-required
documents from a hardcoded `CATEGORY_DOCUMENTS` dict (bilingual). Falls back to a
generic `"default"` list if the category isn't found, and handles combined categories
like `"Welfare/Education"` by trying the first segment before the slash.

**Explicit limitation communicated to the user:** This is NOT a verified per-scheme
list (no reliable source data exists for that). It's general guidance based on common
Indian government scheme requirements (Aadhaar, income certificate, etc.), with a
disclaimer (`documents_disclaimer`) telling the user to confirm the exact list on the
official site. If asked to make this "more accurate," the honest answer is it would
require manually researching and verifying each of the 58 schemes individually — see
§7 priority #1 (data quality) which this is really a sub-problem of.

### 3.7 PDF Export (`pdf_export.py`)
`build_pdf(results, profile=None)` uses `fpdf2` (chosen over `pypdf` for simple,
pure-Python install). Returns raw PDF bytes fed into `st.download_button`. PDF text
is always English — fpdf2's core Helvetica font doesn't support Devanagari glyphs,
and the underlying scheme data is English-only anyway. `_clean()` strips/replaces
non-latin-1 characters (₹ → "Rs.") to prevent encoding crashes. Uses the newer fpdf2
API (`new_x=XPos.LMARGIN, new_y=YPos.NEXT` from `fpdf.enums`, not the deprecated
`ln=True` cell parameter).

### 3.8 Share (multi-platform, icon-based) — REDESIGNED
Originally text-labeled buttons in a separate expander; now redesigned per explicit
user feedback ("look professional", "put icons not text", "same row as star/apply"):
- The action row for every card is now **`st.columns([1, 3, 1])`**: Star toggle |
  Apply Here button | Share popover trigger (`st.popover(..., icon=":material/share:")`).
- Inside the popover: a horizontal row of **circular icon links** (WhatsApp, Telegram,
  Twitter/X, Facebook, Gmail) built as raw HTML `<a><img></a>` tags pointing at
  `https://cdn.simpleicons.org/<slug>/<hexcolor>` — NOT Streamlit buttons, because
  `st.link_button` can't display a custom image, only text/emoji/material-icon labels.
  Styled via the `.share-icon-row` CSS class (40px circular background, hover
  highlight in orange).
  Below the icons, a plain-text fallback (`st.code(message)`) for copy-pasting into
  any other app.
- All share links are built from `urllib.parse.quote()`-encoded scheme
  name/benefit/link — these are just deep-link URL schemes (`wa.me`, `t.me/share`,
  `twitter.com/intent/tweet`, `facebook.com/sharer`, `mailto:`), no actual API
  integration/auth needed.

### 3.9 Bilingual UI (`translations.py`)
Every UI string lives in a `TRANSLATIONS` dict keyed `"English"` / `"हिंदी"`. Rule
enforced after user feedback: **no Hinglish mixing** — every string is fully one
language or the other, never mixed. `get_text(lang)` returns the active dict; app
code accesses strings via `t["key"]`. **When adding any new UI text, add it to BOTH
language blocks** or the app will crash with a `KeyError`. There's a verification
snippet worth re-running after any translation-touching change (see §6).

Recent label changes (if you see old names in earlier notes/screenshots, these are
now renamed):
- "Type Your Question" → **"Search Schemes"**
- "Apply / Official Site" → **"Apply Here"**
- "Share on WhatsApp" (old, WhatsApp-only) → **"Share"** (now multi-platform)

### 3.10 Theme toggle (Dark/Light)
A color dict (`C = {...}`) is chosen in a `with st.sidebar:` block placed BEFORE the
CSS injection code (Python top-to-bottom order matters — CSS depends on knowing the
theme first). An f-string `<style>` block is generated dynamically using those color
variables for custom elements (`.scheme-card`, `.stat-box`, `.chip-*`, `.hero`, etc.)

**Bug fixed — Light mode buttons were invisible:** Streamlit's native widgets
(`st.button`, `st.link_button`, `st.download_button`, popover trigger) follow the
FIXED dark base theme from `.streamlit/config.toml` regardless of our custom Light/
Dark toggle (which only re-styles our own custom HTML elements, not Streamlit's
native controls). In Light mode this made buttons render dark-on-light in a way that
looked broken/invisible. **Fix:** added explicit theme-aware CSS overrides targeting
`.stButton > button`, `.stDownloadButton > button`, `.stLinkButton > a`, and the
popover trigger button, forcing background/text/border colors from the `C` dict
(with a separate `!important` rule for `button[kind="primary"]` to keep it orange
regardless of theme). **If any NEW native Streamlit widget is added later and looks
wrong in Light mode, this is almost certainly the same root cause — add it to that
CSS override block.**

### 3.11 Custom logo/branding (`assets/logo.png`)
Generated programmatically with PIL (not sourced from the web, to avoid copyright
concern) — navy circle, white document/building icon, small orange rupee-coin badge
("K1" design, user-chosen from ~15 generated options). Embedded as base64 inline
`<img>` in the sidebar, hero banner, and browser favicon.

### 3.12 Mobile responsiveness
A `@media (max-width: 640px)` CSS block shrinks hero text/padding/chip sizes and
forces Streamlit's `div[data-testid="stHorizontalBlock"]` (multi-column rows like the
stats row) into `flex-direction: column` so columns don't get squeezed unreadably on
phone screens.

---

## 4. Data Model — `data/schemes.csv`

12 columns, 58 rows (22 states/UTs + central schemes):

| Column | Type | Notes |
|---|---|---|
| `scheme_name` | string | |
| `category_type` | string | e.g. Agriculture, Health, Pension, Education, Business/Loan, Welfare, Housing, Employment, Skill Development, Banking, Insurance, Food Security (some combined like "Welfare/Education") — `doc_checklist.py` keys off this |
| `min_age` / `max_age` | float (nullable) | blank = no limit |
| `max_annual_income` | float (nullable) | blank = no income cap |
| `applicable_state` | string | `"All"` = central scheme, else exact state name (must match dropdown exactly, e.g. `"Jammu and Kashmir"`) |
| `social_category` | string | `"All"`, or `/`-separated combos like `"SC/ST/OBC"` |
| `occupation` | string | `"All"` or specific like `"Farmer"`, `"Student"` |
| `gender` | string | `"All"`, `"Male"`, or `"Female"` |
| `description` | string | one-line plain description |
| `benefits` | string | one-line benefit summary |
| `apply_link` | string (URL) | official .gov.in link (**not verified against live sites — see §6/§7 caveats**) |

**No document-checklist or deadline columns exist in this CSV** — documents are
looked up generically by `category_type` (§3.6), and there is no deadline data at
all (which is why "Reminders" is a user-set personal date, not a scraped official
deadline — see §7).

**Honest caveat already communicated to the user, repeatedly:** 58 schemes is a small
fraction of the 1000+ real schemes across India. Data was manually authored from
training knowledge of well-known schemes, NOT scraped/verified against
myscheme.gov.in or other live sources. Eligibility criteria are approximate. The app
disclaims this, but it's still the single highest-leverage gap — see §7 priority #1.

---

## 5. Known Bugs Already Fixed (do not reintroduce)

1. **Pandas source build failure on user's Windows/Anaconda setup** — not actually
   blocking; Anaconda's base env already ships pandas, so the app runs fine even if
   this specific pip install line errors out. Don't be alarmed by it.
2. **NL search returning 0 results on typos** — fixed via char n-gram TF-IDF (§3.2).
3. **NL search suggesting the exact word you just typed** — fixed by excluding exact
   matches, falling back to synonym suggestions.
4. **Suggestion-button click not filling the search box** — fixed by using the
   button's `on_click` callback instead of inline `st.session_state` mutation after
   the widget was already instantiated (which raises a StreamlitAPIException).
5. **Favorites star click wiping out the Eligibility Check results list** — root
   cause: `submitted = st.button(...)` is only `True` on the exact rerun triggered by
   clicking Search; any other widget interaction (like the star) triggers a rerun
   where `submitted` is `False` again. Fixed by wrapping `render_scheme_card()` in
   `@st.fragment`, so a star/share/reminder click only reruns that fragment, not the
   whole page/script.
6. **Scheme cards rendering as literal raw HTML text (with a Streamlit code-block
   copy icon) instead of styled cards — this took TWO attempts to fully fix:**
   - First attempt: assumed it was a CommonMark "4+ space indentation = code block"
     issue and applied `textwrap.dedent(f"""\...""")`. This was **incomplete** — it
     fixed the *leading* indentation but the real trigger was different (see next
     bullet), so the bug persisted after this fix and the user reported it again.
   - **Actual root cause:** the multi-line f-string had a line containing ONLY
     `{extra_badge}`, which is an empty string whenever a card has no
     eligible/not-eligible badge and no match-percentage badge (e.g. every card in
     Favorites mode, since those dicts don't carry an `"eligible"` or `"score"` key).
     An empty-string substitution on its own line becomes a **blank line** in the
     rendered markdown. CommonMark's HTML-block Rule 6 (which is what makes a
     `<div>`-starting block get treated as raw HTML passthrough) terminates at the
     first blank line — so the blank line ended the raw-HTML treatment early, and
     the still-indented lines AFTER it got reinterpreted as a fresh indented code
     block.
   - **Final, correct fix:** rebuilt the card HTML (and the sidebar-logo HTML and
     the history-card HTML) as **single-line strings via string concatenation**
     (`f'<div>...' f'<span>...' ...` chained together with no `\n` anywhere), which
     sidesteps this entire class of Markdown block-detection bug regardless of which
     substituted values are empty.
   - **This is a recurring risk class — any NEW `st.markdown(..., unsafe_allow_html=
     True)` call with multi-line/templated HTML must either (a) be built as a
     single-line string with no embedded newlines, or (b) be very carefully checked
     for any line that could go fully blank when a variable is empty.** Prefer (a).
7. **fpdf2's `ln=True` / old-style `cell()` API deprecated** in the installed fpdf2
   version — fixed with `new_x=XPos.LMARGIN, new_y=YPos.NEXT` (`from fpdf.enums
   import XPos, YPos`).
8. **Missing `share_copy_label` translation key** caused a latent `KeyError` risk —
   always cross-check `translations.py` has matching keys in both language blocks
   whenever `app.py` references a new `t["..."]` key.
9. **Light-theme native buttons invisible** — see §3.10. Fixed with explicit CSS
   targeting Streamlit's native widget classes, not just custom HTML elements.

---

## 6. Debugging Tips Specific to This User's Setup

- User is non-technical about tooling. Any instruction involving the terminal needs
  numbered, literal steps (exact commands to type, where to click).
- They run via **Anaconda Navigator → base environment → Open Terminal**, which opens
  inside a **Jupyter Notebook browser tab** (PowerShell underneath), not a native
  terminal app.
- Project folder lives under **OneDrive sync** with a space in the path
  (`...\home fight\Desktop\scheme-chatbot`) — always wrap paths in quotes in any `cd`
  instruction given to them.
- After any `requirements.txt` change (new library added), the user must be
  explicitly reminded to re-run `pip install -r requirements.txt` — they've missed
  this before (fpdf2 ModuleNotFoundError).
- When giving a new ZIP, tell them to **delete the entire old folder** before
  extracting — Windows Explorer silently creates `app (1).py`-style duplicates
  otherwise, and they end up running stale code. This has directly caused at least
  one "my fix isn't working" false alarm before.
- They test on mobile via their laptop's Ethernet/hotspot tethering IP (found via
  `ipconfig` — look for the actual Wi-Fi/tethering adapter section, NOT a
  `10.233.x.x`-style VPN virtual adapter). Common failure: pasting the URL into a
  search engine's search box instead of the browser's address bar.
- User does NOT yet want cloud deployment (Streamlit Community Cloud) — explicitly
  said "abhi nahi, baad mein" (not now, later) when asked once already. Don't push it
  unprompted; mention it's available if they ask about permanent/shareable links.
- **Always verify new code with THREE checks, in order, before considering a fix
  complete** — syntax-only checking has repeatedly missed real bugs in this project:
  1. `python3 -c "import ast; ast.parse(open('app.py').read())"` — catches syntax
     errors only.
  2. Cross-check every `t["..."]` key used in `app.py` exists in BOTH language
     dicts in `translations.py`:
     ```python
     import re
     from translations import TRANSLATIONS
     code = open("app.py").read()
     used = set(re.findall(r"t\[[\"']([a-zA-Z_]+)[\"']\]", code))
     for lang, d in TRANSLATIONS.items():
         print(lang, "missing:", used - set(d.keys()))
     ```
  3. Actually launch it and hit it: `streamlit run app.py --server.headless true
     --server.port <N> &`, `curl -s http://localhost:<N> -o /dev/null -w "%{http_code}"`,
     then `grep -i "exception|traceback" <logfile>`. Several bugs (favorites,
     markdown-as-code) were NOT caught by steps 1-2 and only surfaced visually in the
     browser — when in doubt, also manually reason through what the rendered HTML
     string will look like for edge cases (empty fields, no badge, etc.), since the
     sandbox can't click buttons in a real browser to verify interactive behavior.

---

## 7. Recommended Next Steps — What & Why

Ordered roughly by leverage (impact vs effort):

### High priority
1. **Data quality / expansion — still the single biggest gap.** Only 58 of 1000+
   real schemes, unverified against live sources, and the new Document Checklist
   feature (§3.6) is explicitly a workaround for not having real per-scheme document
   data. Recommend either (a) a research pass verifying/correcting the existing 58
   entries' eligibility criteria, links, AND adding real per-scheme document lists
   against myscheme.gov.in, or (b) if scraping is feasible and permitted by their
   terms, a script to pull structured data. This would upgrade the Document Checklist
   from "generic category guidance" to real per-scheme accuracy, and would let
   Reminders eventually show real official deadlines instead of only user-set ones.
2. **Persist Eligibility Check results via `st.session_state`, not just
   `@st.fragment` isolation.** The fragment fix (§5 bug #5) solves the immediate
   symptom, but the underlying fragility (results tied to a transient button-press
   boolean) could resurface with any future widget added outside the fragment
   boundary. Storing `results` + `profile` in `st.session_state` on submit and always
   rendering from session_state (regardless of what triggered the rerun) is the more
   robust long-term fix.
3. **Real per-scheme deadlines**, once data quality (priority #1) makes this
   possible — would upgrade Reminders from "purely user-set" to able to pre-fill/
   suggest a date based on actual scheme deadlines, and would make Eligibility
   Check's disclaimer stronger ("last date to apply: ...").

### Medium priority
4. **Deployment to Streamlit Community Cloud.** User has deferred this before but
   will likely want it eventually for a shareable resume link. Needs a GitHub repo
   push + share.streamlit.io connection. **Important:** the local `data/*.json`
   (history/favorites/reminders) won't persist across cloud restarts/redeploys — a
   cloud deploy would reset these on every redeploy unless moved to a real database
   (e.g. a small hosted SQLite/Postgres, or Supabase). Flag this clearly if/when
   deployment happens, don't let the user be surprised their favorites/reminders
   vanish after a redeploy.
5. **Admin/edit interface for `schemes.csv`** — a simple Streamlit form (or a
   documented helper script) to append/validate a new row, instead of hand-editing
   the CSV.
6. **Comparison mode** (2-3 schemes side by side) — discussed as an idea, not built.

### Lower priority / nice-to-have
7. **Voice input for search** — aligns with the project's "help the common aadmi"
   goal, but adds real complexity (browser mic permissions, speech-to-text API,
   Hindi accuracy).
8. **Real notifications (not just in-app reminders)** — would require a genuinely
   different architecture: a persistently-running backend/server (not this local
   script) plus a push-notification service (browser push API, or a scheduled
   email/SMS sender). This is a substantial scope increase from the current
   local-only tool — don't casually promise "I'll add notifications" without
   flagging this architectural jump to the user first.
9. **User accounts / login** — only worth doing once/if this goes to a real
   multi-user cloud deployment; premature for a local single-user tool where
   favorites/history/reminders are already effectively single-user by nature.

### Explicitly deprioritized / rejected ideas (don't re-suggest without new data)
- "Benefit-amount" and "deadline" sorting were requested early on but the dataset has
  no numeric benefit-amount or deadline fields (benefits are free-text strings like
  "Rs 6000 per year"). Implemented Name/Category/State sort instead. Don't fake-sort
  on unstructured text — only revisit if priority #1/#3 above add real structured
  fields.
- A fully "verified, accurate" Document Checklist per scheme was requested implicitly
  — current implementation is honest category-level guidance with a disclaimer. This
  is a data problem (see priority #1), not a code problem — don't try to "fix" this
  by writing more plausible-sounding but unverified per-scheme document lists.

---

## 8. Quick-Start for a New AI/Developer Picking This Up

```bash
cd scheme-chatbot
pip install -r requirements.txt
streamlit run app.py
```

Before touching `app.py`, read `translations.py` fully (the `t["..."]` convention),
then `matcher.py` + `nl_search.py` (the two "engines" behind the two search modes),
then `favorites.py` / `history.py` / `reminders.py` (all follow the same
local-JSON-file persistence pattern — copy that pattern for any new "save something
locally" feature rather than inventing a new one).

Any new UI-facing feature should:
1. Add both English + Hindi strings to `translations.py` (run the verification
   snippet in §6 afterward).
2. Reuse the `render_scheme_card()` component in `app.py` rather than duplicating
   card-rendering HTML — it already handles the star/apply/share row and the
   documents/reminder expanders consistently across Eligibility Check, Search
   Schemes, and Favorites modes.
3. If it involves `st.markdown(..., unsafe_allow_html=True)`, build the HTML as a
   **single-line concatenated string** (see §5 bug #6) — do not use a multi-line
   triple-quoted f-string for `<div>`/block-level HTML, even with `textwrap.dedent`.
4. If it adds any new native Streamlit widget (button, input, etc.) that should look
   different in Light vs Dark mode, add it to the theme-aware CSS override block
   (§3.10) rather than assuming Streamlit's base theme will adapt on its own.
5. Test with an actual `streamlit run` + `curl` + log-grep (§6), not just a Python
   syntax check — and manually trace through what any generated HTML string looks
   like when template variables are empty/None.
