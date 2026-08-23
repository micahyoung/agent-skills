---
name: genealogy
description: >
  Parse, explore, edit, and generate visual reports from Gramps XML (.gramps) genealogy files. Use this skill whenever the user mentions a .gramps file, Gramps XML data, family trees, ancestry, genealogy research, lineage, ancestors, descendants, pedigree charts, family history, heritage, great-grandparents, or wants to look up relatives, trace family connections, find out "who were my relatives", or correct/update genealogical records. Also trigger when the user has a .gramps file open or referenced in conversation and asks questions about people, families, dates, or relationships — even if they don't say "genealogy" explicitly. Trigger for requests involving family tree charts, PDFs, or visualizations of genealogical data.
compatibility: Requires uv and native Gramps. Uses Bash, Read, and Write tools. Research
  Mode additionally requires a browser-automation tool.
---

# Genealogy Skill

You help users explore and edit Gramps XML (.gramps) genealogy files. You have five modes:
- **Read Mode** (default)
- **Edit Mode**
- **Research Mode**
- **Validation Mode**
- **Report Mode**

Always start in Read Mode unless the user explicitly asks to visualize, validate, or make
changes, or gives an open-ended research goal (e.g. "/genealogy Research ..." or phrasing
like "Research X's military service," "Verify Y's immigration record," "Trace Z's land
grants") — in which case start in Research Mode. If it's ambiguous whether the user wants
a quick lookup in the existing file (Read Mode) or active external research (Research
Mode), ask.

## How You Work

### Scripting with gramps_python

You accomplish most tasks by writing and executing short Python scripts on the fly using the bundled `gramps_python` interpreter. It gives you full access to the Gramps Python libraries — no install step needed.

Run scripts with:
```
<skill-dir>/scripts/gramps_python script.py
<skill-dir>/scripts/gramps_python -c "one-liner code"
```

Use `gramps_python` for all Read and Edit mode work. Three additional bundled scripts handle deeper operations:
- **[./scripts/gramps_validate.py](./scripts/gramps_validate.py)** — validates a Gramps XML file and reports errors/warnings
- **[./scripts/gramps_report.py](./scripts/gramps_report.py)** — generates graphical reports (pedigree charts, PDFs, etc.)

Run either script with `--help` for full usage. Note: paths are relative to this SKILL.md's directory — use `<skill-dir>/scripts/<script>.py` when constructing commands.

## Finding the Gramps XML File

If the user hasn't specified a file path:

1. **Glob for `**/*.gramps`** in the working directory
2. **One file found** → use it, but confirm with the user: "I found `path/to/data.gramps` — shall I use that?"
3. **Multiple files found** → list them and ask which one to use
4. **No files found** → ask the user for the path to their Gramps XML file

## Read Mode (default)

This is the primary mode. The user has a .gramps file and wants to learn about the people and families in it. Your job is to answer their questions in warm, clear, natural language — like a knowledgeable family historian sitting beside them.

### Approach

1. **Parse the file** by writing a Python script that loads it with `import_as_dict` and run it with `gramps_python`
2. **Extract the relevant data** — names, dates, places, relationships, notes
3. **Respond in natural language** — weave the facts into readable sentences and paragraphs, not raw data dumps

### What good responses look like

When someone asks "Who are Dennis's children?", don't reply with:

```
@I5@ Clayton Rufus Varnell (b. 14 NOV 1984)
@I6@ Nora Colleen Varnell (b. 27 FEB 1987)
@I7@ Judith Elaine Varnell (b. 20 APR 1993)
```

Instead, reply like:

> Dennis and Lorraine have three children. **Clay** (Clayton Rufus), the eldest, was born on November 14, 1984. **Nora Colleen** followed on February 27, 1987, and the youngest, **Jude** (Judith Elaine), was born on April 20, 1993. All three were born in Millhaven.

Key principles:
- **Use nicknames and given names naturally** — introduce someone as "Clay (Clayton Rufus)" on first mention, then just "Clay"
- **Include dates and places** when they add value, but don't force them into every sentence
- **Note interesting details** from NOTE fields when relevant — occupations, biographical tidbits
- **Explain relationships clearly** — "Dennis's half-brother Malcolm" is better than "Malcolm Caine, son of Roderick Varnell and an unknown woman"
- **When the data is incomplete**, say so honestly: "The file doesn't include a birth date for Malcolm, but it notes he was born around 1957 in Dunmore."

### Common query patterns

Write Python scripts to handle these (and similar) requests:

- **List/search people**: "Who's in this file?", "Find everyone named Decker"
- **Relationships**: "How is Clay related to Warren?", "Who are Nora's grandparents?"
- **Timeline**: "List births in order", "What happened in the 1950s?"
- **Family structure**: "Show me Dennis's family", "Who are the Decker sisters?"
- **Statistics**: "How many people are in this file?", "What's the average number of children?"
- **Notes and details**: "What do we know about Estelle?", "Any military service records?"
- For ancestor/descendant queries, end by offering a visual chart: "Would you like me to generate a pedigree chart as a PDF?"

### Output format

Default to natural language prose. If the user asks for a specific format (markdown table, bullet list, a pedigree/ancestor chart in ASCII, etc.), provide that instead. For large result sets, use a concise format like a table to keep things scannable.

### Python scripting patterns for Read Mode

Here's the general shape of a read script (run with `<skill-dir>/scripts/gramps_python script.py`):

Always pass `quiet=True` to `User` in headless scripts — a plain `User()` prints a per-object progress bar to stderr that renders as a `00%…100%` dump outside a TTY.

```python
from gramps.gen.db.utils import import_as_dict
from gramps.cli.user import User
from gramps.gen.datehandler import displayer as date_displayer

db = import_as_dict("data.gramps", User(quiet=True))

# Example: find an individual by surname fragment
for handle in db.get_person_handles():
    person = db.get_person_from_handle(handle)
    name = person.get_primary_name()
    first = name.get_first_name()
    last = name.get_surname()

    if "varnell" in last.lower():
        birth_ref = person.get_birth_ref()
        birth_date = birth_place = ""
        if birth_ref:
            birth_event = db.get_event_from_handle(birth_ref.ref)
            birth_date = date_displayer.display(birth_event.get_date_object())
            place_h = birth_event.get_place_handle()
            if place_h:
                birth_place = db.get_place_from_handle(place_h).get_title()
        print(f"{first} {last}, born {birth_date} in {birth_place}")
```

Ancestor traversal — show parents and grandparents concretely (run with `<skill-dir>/scripts/gramps_python script.py`):

```python
# Find parents and grandparents — 2 levels, no queue needed
for fam_handle in person.get_parent_family_handle_list():
    fam = db.get_family_from_handle(fam_handle)
    for parent_handle in [fam.get_father_handle(), fam.get_mother_handle()]:
        if not parent_handle:
            continue
        parent = db.get_person_from_handle(parent_handle)
        pn = parent.get_primary_name()
        nick = pn.get_nick_name()
        print(f"Parent: {pn.get_first_name()}" + (f" ({nick})" if nick else ""))
        # Grandparents — same pattern, nested one level deeper
        for gfam in parent.get_parent_family_handle_list():
            gf = db.get_family_from_handle(gfam)
            for gph in [gf.get_father_handle(), gf.get_mother_handle()]:
                if gph:
                    gp = db.get_person_from_handle(gph)
                    gpn = gp.get_primary_name()
                    print(f"  Grandparent: {gpn.get_first_name()} {gpn.get_surname()}")
```

**Key API methods:**

| Need | Call |
|---|---|
| All people | `db.get_person_handles()` → `db.get_person_from_handle(h)` |
| Look up by Gramps ID (human-facing id, e.g. `I0001`, not the opaque `handle`) | `db.get_person_from_gramps_id(id)`, and equivalently `get_family_from_gramps_id`, `get_event_from_gramps_id`, `get_place_from_gramps_id`, `get_source_from_gramps_id`, `get_citation_from_gramps_id`, `get_repository_from_gramps_id`; reverse (object → id) is `obj.get_gramps_id()` |
| Name | `person.get_primary_name().get_first_name()` / `.get_surname()` |
| Birth date | `date_displayer.display(db.get_event_from_handle(person.get_birth_ref().ref).get_date_object())` (import `displayer as date_displayer` from `gramps.gen.datehandler`; `.get_text()` returns `""` for all structured dates) |
| Birth place | `db.get_place_from_handle(event.get_place_handle()).get_title()` |
| Families | `db.get_family_handles()` → `db.get_family_from_handle(h)` |
| Family members | `fam.get_father_handle()`, `.get_mother_handle()`, `.get_child_ref_list()` |
| Person count | `db.get_number_of_people()` |
| Gender | `person.get_gender() == Person.MALE` / `== Person.FEMALE` — returns int, not enum methods |
| Nickname | `name.get_nick_name()` — not `get_call_name()` |
| Parent family | `person.get_parent_family_handle_list()` — list of family handles where person is a child |
| Child handle | `child_ref.ref` — ChildRef uses `.ref` (same as EventRef) |
| Notes | `person.get_referenced_handles_recursively()` → filter `cls == "Note"` → `db.get_note_from_handle(h).get()` |
| Occupation | Iterate `person.get_event_ref_list()`, check `str(event.get_type()) == "Occupation"` → `event.get_description()` |
| Death | `person.get_death_ref()` — same EventRef pattern as birth |

Adapt freely. You're writing throwaway scripts to extract exactly what the user needs — not building a reusable library.

## Edit Mode

Switch to this mode only when the user explicitly wants to modify the .gramps file — adding people, correcting names/dates, linking families, deleting records, etc.

Editing genealogical records is serious business. A wrong edit can propagate confusion through someone's family research. So this mode is deliberate and careful.

### The Edit Workflow

1. **Understand the change**: Confirm what the user wants to modify. If anything is ambiguous, ask before proceeding.

2. **Show a preview**: Before writing anything, describe the change in plain language:
   > I'm going to correct the surname on Clayton Rufus (I0005) from "Smyth" to "Smith". Want me to go ahead?

3. **Wait for confirmation**: Do not write the file until the user says yes.

4. **Apply the edit** via a Python script that:
   - Parses the file
   - Makes the targeted modification
   - Adds a changelog NOTE to the modified record
   - Writes the output

5. **Add a changelog note** to every modified record:
   ```
   NOTE [CHANGELOG] 2026-03-15: Corrected surname from Smyth to Smith (source: baptism record St. Mary's 1842)
   ```
   - Always include today's date
   - Describe what changed and from what to what
   - Include the source/reason if the user provided one; if not, ask or note "per user correction"

6. **Report what was done**: After writing, summarize the changes made.

### Edit safety rules

- **One logical change at a time**. If the user asks for multiple edits, handle them sequentially with individual confirmations, unless they explicitly say "go ahead and do all of these."
- **Never delete records without explicit confirmation**, even if the user implies it. Say: "This would remove [person/family] from the file entirely. Are you sure?"
- **Back up before bulk edits**. If the user asks for sweeping changes (e.g., "fix all the date formats"), save a backup copy first (e.g., `data_backup_20260617.gramps`) and tell them you did.
- **Preserve structure**. Don't reorder records unnecessarily. Don't strip existing notes or custom tags unless asked.

### Python scripting patterns for Edit Mode

For edits, use the Gramps API — import with `import_as_dict`, modify objects in memory using `DbTxn`, then serialize back with `GrampsXmlWriter`. Run with `<skill-dir>/scripts/gramps_python script.py`.

```python
from gramps.gen.db.utils import import_as_dict
from gramps.cli.user import User
from gramps.gen.db import DbTxn
from gramps.plugins.export.exportxml import GrampsXmlWriter
from gramps.version import VERSION
from gramps.gen.lib import Note, NoteType
import datetime

filepath = "data.gramps"
db = import_as_dict(filepath, User(quiet=True))

# Locate target person, make changes to the object...

# Changelog note — add as a linked Gramps Note object
note = Note()
note.set_type(NoteType.GENERAL)
note.set(f"[CHANGELOG] {datetime.date.today().isoformat()}: Updated occupation from "
         f"'Student, Millhaven Middle School' to 'Foreman, Millhaven Grain Processing' "
         f"(source: per family member correction March 2026)")

with DbTxn("Update Clay's occupation", db) as txn:
    db.add_note(note, txn)
    person.add_note(note.handle)
    db.commit_person(person, txn)

GrampsXmlWriter(db, compress=0, version=VERSION, user=User(quiet=True)).write(filepath)
print(f"Saved. {db.get_number_of_people()} people in file.")
```

Always use `DbTxn` to wrap all write operations, and re-serialize with `GrampsXmlWriter` after editing.

## Research Mode

Switch to this mode when the user gives an open-ended genealogical research goal rather
than a single question about existing data — "Research census gaps for [person]'s
[surname] lineage," "Verify [person]'s immigration record," "Trace [person]'s military
service," "Find land grants for [person]." Research Mode is not limited to any one record
type or relationship shape — trust your general genealogical knowledge (census, vital
records, military, land, probate, immigration, church, DNA, etc.) the same way Read Mode
trusts you to "adapt freely" to whatever question is asked. The worked example later in
this section (census-gap analysis) is illustrative, not the whole scope.

### Prerequisites

Research Mode drives real searches against external genealogy sites (e.g. FamilySearch,
Ancestry) via a browser-automation tool, so it needs one connected and already
authenticated on the target site. Before starting the search phase:
- Confirm a browser-automation tool is available in this session.
- Take a snapshot/screenshot of the target site early and confirm you're logged in, not
  looking at a login page.

If no browser-automation tool is available, don't guess or silently skip searching — tell
the user and ask how to proceed. If a search session appears to have expired mid-task
(empty or nonsensical results), stop and re-check login state rather than concluding a gap.

### The Research Workflow

1. **Survey existing state.** Read any existing `research-notes/*.md` files (dated-section
   prose research logs, if this project uses that convention) alongside the Gramps XML
   file. For `data.gramps` itself (persons, families, events, notes — including
   `[CHANGELOG]` notes from Edit Mode), query it the same way Read Mode does: a Python
   script using `import_as_dict` and `gramps_python` (see "Python scripting patterns for
   Read Mode" above for the script shape and the Key API methods table) — never grep the
   raw XML directly. This is fuzzy prose- and data-reading — read closely so you don't
   redo settled work or contradict a prior conclusion.
   - If a note contains `[Display Name](gramps:<id>)` links, resolve each one back to its
     current record with the matching `get_*_from_gramps_id` call (see the Key API methods
     table) rather than trusting the display name alone. This catches drift — a person
     renamed, merged, or deleted since the note was written — before you build new
     conclusions on top of a stale reference. If a link's id no longer resolves, or the
     record's current display name no longer matches the text in brackets, flag it and
     confirm with the user before relying on that note's claims.

2. **Formulate a plan.** Break the goal into concrete sub-questions (e.g. per-ancestor-
   pair, per-record, per-event). For each, check *structural possibility* before spending
   effort searching: given known dates, places, and record-availability facts (destroyed/
   missing record years, digitization gaps, a person's lifespan or residence), is the
   thing you're looking for even possible to find? Skip sub-questions that are already
   structurally impossible, and say why.

3. **Execute searches, one sub-question at a time**, using the browser-automation tool.
   Expect noisy results — a same-name/same-surname search can return dozens of irrelevant
   matches; use dates, places, and family context to filter before treating a result as a
   candidate.

4. **Verify before concluding — always.** Before recording any finding, especially "not
   found" or "permanent gap," open the full primary record (not just a search-result
   snippet or an existing research note) and check it directly. This step is not
   optional: a plausible-looking gap or match can turn out to be wrong once you look at
   the actual record.

5. **Classify each finding** using the vocabulary below.

6. **Present findings and stop for confirmation** before writing anything — the same
   "preview → wait for confirmation → apply" rule as Edit Mode. Batch confirmation at
   natural stopping points rather than after every single item, but never batch
   `permanent-gap` conclusions without checking in — those read as authoritative once
   written and could wrongly discourage future research if incorrect.

7. **Write back on confirmation, to both places:**
   - Structured facts (Events, Citations, Notes, and Tags if this project already uses
     one) go into `data.gramps` via Edit Mode's existing workflow: `DbTxn` + a
     `[CHANGELOG]`-prefixed Note + `GrampsXmlWriter`. Reuse that workflow, don't reinvent
     it — for new Citations, set confidence per the Evidence Classification mapping
     below, not left at default.
   - Prose findings get appended to the relevant `research-notes/*.md` file, in the same
     dated-section style already used there. If no `research-notes/` directory exists,
     ask the user before creating one — this convention varies by project.
   - **Link records the first time they're mentioned.** When prose in a
     `research-notes/*.md` file names a person, family, source, citation, or repository
     that exists (or now exists, after this write) in `data.gramps`, write that first
     mention as a markdown link of the form `[Display Name](gramps:<gramps_id>)` — e.g.
     `[Clayton Rufus Varnell](gramps:I0005)`,
     `[Repository R0001](gramps:R0001)`, `[Citation C0001](gramps:C0001)`. Get the id with
     `obj.get_gramps_id()` (not `.handle`, which is an opaque internal string, not
     human-meaningful, and not stable for this purpose). Only the *first* mention of a
     given record within a bullet/section needs the link — don't re-link every repeated
     mention of the same name later in the same paragraph or section; plain text is fine
     after that. This applies only to `gramps:` ids for records inside `data.gramps` —
     never wrap external record identifiers (FamilySearch ark IDs, Ancestry record URLs,
     etc.) in this syntax; those stay as plain text exactly as returned by the source.

8. **Checkpoint as you go.** For goals spanning many sub-questions or sessions, append
   each pass's results to the research-notes entry as you finish it, so a resumed session
   can pick up by reading the file's own accumulated history.

### Evidence Classification

Use this vocabulary consistently across research goals — not just census work:

| Label | Meaning |
|---|---|
| `PROVED` | Direct primary evidence found and verified against the full record. |
| `found-and-added` | A new, relevant record was located and attached; not yet elevated to `PROVED`. |
| `not-found-retriable` | Searched and not found, but not proven impossible — worth another pass later. |
| `permanent-gap` | Provably impossible to find — state the specific structural reason. |

When a finding above `not-found-retriable`/`permanent-gap` produces a Citation, set its
confidence explicitly — never leave it at the Gramps default and never set every
citation to the same level:

| Label | Citation confidence |
|---|---|
| `PROVED` | `citation.set_confidence_level(Citation.CONF_VERY_HIGH)` |
| `found-and-added` | `citation.set_confidence_level(Citation.CONF_LOW)` |
| `not-found-retriable` | n/a — no citation created |
| `permanent-gap` | n/a — no citation created |

Edit Mode changelog notes may reuse these same labels.

### Example: structural pre-check for census-gap research

One instance of the "check structural possibility before searching" step (step 2), for a
census-based lineage-gap goal — say, "Research census gaps for Estelle's Varnell
lineage" — other goal types substitute their own constraints for the same pattern:

- Was Estelle born before the census's enumeration date, and still plausibly living with
  her father Warren (unmarried, right age) at that time?
- Was that census year *not* one of the known destroyed/missing years (e.g. 1890 US)?

If no census year satisfies both for Estelle and Warren, this is a `permanent-gap`
candidate — verify the specific reason against primary sources before concluding, then
skip straight to classification instead of searching. The same shape applies elsewhere: a
record's known digitization coverage for immigration research, or whether a land-grant
office existed for a given jurisdiction and period for land research.

## Validation Mode

Switch to this mode when the user wants to check their Gramps XML file for errors, data quality issues, or structural problems.

### When to use Validation Mode

Trigger when the user asks:
- "Validate my file", "Check for errors", "What's wrong with my file?"
- "Find data quality issues", "Are there any problems in the file?"
- "Run a health check on my family tree"

### The Validation Workflow

Run the bundled `scripts/gramps_validate.py` script:

```bash
python <skill-dir>/scripts/gramps_validate.py -i path/to/data.gramps
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `-i / --input` | required | Gramps XML file path |
| `-f / --format` | `text` | Output format: `text` or `json` |
| `--all` | off | Show suppressed noise warnings too |

**Prerequisites:** Gramps must be available; the script handles setup automatically.

### Interpreting results

The script runs four phases:
1. **Import** — catches structural problems loading the Gramps XML file
2. **Verify** — catches semantic issues (invalid dates, out-of-order births, age anomalies)
3. **FamilySearch checks** — catches citation convention issues on any Citation/Source/Note/Person attribute/Event description mentioning familysearch.org (non-canonical `www.` URLs, missing Call Number on a FamilySearch Digital Library-linked Source, bare-ARK Source titles)
4. **Type coverage checks** — catches records left at a blank/unset value on structural fields (EventType, PlaceType, NameType, NameOriginType, ChildRefType, AttributeType, SrcAttributeType, UrlType, RepositoryType, NoteType, FamilyRelType, SourceMediaType, and Citation.Date) instead of being reviewed and set

**Error levels:**
- `E` (error) — definite data problem; worth investigating and fixing
- `W` (warning) — possible issue; may be legitimate (e.g. large age gap between siblings)

**Noise filtering:** By default, low-signal issues are suppressed:
- `"Husband and wife with the same surname"` — coincidental surname match, rarely meaningful
- FamilySearch URLs using the non-canonical `www.` host prefix — style only
- Blank/unset `*Type` field warnings — can number in the hundreds on a lightly-reviewed file

Use `--all` to see the full unfiltered output.

**Exit codes:** `0` = no errors; `1` = one or more errors found (useful for scripting).

### After validation

For any real errors found, switch to Edit Mode to fix them. Common fixes:
- `"Invalid birth date"` with an empty `DATE` field — remove the empty `BIRT` tag or add a date
- `"Person events not in chronological order"` — check event dates for that individual
- `"Children not in chronological order"` — check birth dates of children in that family

### JSON output for programmatic use

```bash
python <skill-dir>/scripts/gramps_validate.py -i data.gramps -f json
```

Output structure:
```json
{
  "summary": {"errors": 3, "warnings": 2, "noise_suppressed": 0},
  "errors": [
    {"source": "verify", "level": "E", "record_type": "Person",
     "record_id": "IJANPETERRYNDERS", "record_name": "Rynders, Jan Peter",
     "message": "Person events are not in chronological order"}
  ],
  "warnings": [...]
}
```

## Report Mode

Switch to this mode when the user wants a visual report — a pedigree chart, relationship graph, fan chart, descendant tree, or any other graphical output from their genealogy data. Report Mode uses the bundled `scripts/gramps_report.py` script, which produces publication-quality reports.

### When to use Report Mode

Trigger Report Mode when the user asks for something visual or printable:
- "Draw me a family tree", "Show me a pedigree chart"
- "Generate a relationship graph for everyone descended from Warren"
- "I need a fan chart of Clay's ancestors"
- "Export a PDF of the descendant tree"
- "Create a timeline chart for Estelle"

If the user asks for an ASCII chart or text-based tree, stay in Read Mode and generate it with a Python script instead. Report Mode is specifically for graphical output (PDF, PNG, SVG, DOT).

### Prerequisites

- Gramps must be available; the script handles setup automatically.
- The output file must be in the **same directory** as the input Gramps XML file.

### The Report Workflow

1. **Identify the center person**. Most reports require a Gramps `pid`. Gramps assigns its own internal person IDs. Run `python <skill-dir>/scripts/gramps_report.py --list-people -i data.gramps` to list all people with their Gramps-assigned IDs. Match by name and use that ID as the `--pid` value.

2. **Choose the report type and format**. Match the user's request to one of the available reports:
   - `rel_graph` — Relationship Graph (full or filtered network)
   - `ancestor_chart` — Pedigree / Ancestor Tree
   - `descend_chart` — Descendant Tree
   - `family_descend_chart` — Descendant Tree including spouses
   - `fan_chart` — Circular ancestor chart
   - `hourglass_graph` — Ancestors above, descendants below
   - `timeline` — Chronological life events
   - `indiv_complete` — Complete Individual Report
   - `kinship_report` — Everyone related to center person
   - `family_group` — Single family unit detail sheet

   See `scripts/gramps_report.py --help` for the full list and available options.

3. **Run the script**:
   ```bash
   python <skill-dir>/scripts/gramps_report.py \
     -i path/to/data.gramps \
     -o path/to/output.pdf \
     -f pdf \
     -r rel_graph \
     -p I123 \
     -e "filter=2,dpi=300"
   ```
   *(Replace `<skill-dir>` with the actual path to this skill's directory.)*

4. **Report the result**. Tell the user what was generated, the file path, and file size. If the format is viewable (PNG, SVG), offer to open or display it.

### Tips for good reports

- **PDF is the safest default** for output format — it embeds fonts and renders reliably.
- **SVG** is great for web use but renders text as glyph paths (not searchable text).
- **PNG** works well for sharing; use `-e "dpi=300"` for print quality.
- **DOT** format is useful when the user wants to customize the graph layout further with Graphviz.
- For large trees, **use filters** to avoid overwhelming graphs. `filter=1` (descendants) or `filter=3` (ancestors) keeps things focused. `filter=0` includes the entire database.
- Use `-e "maxgen=N"` on ancestor/descendant charts to limit depth.

## Handling Errors Gracefully

- If a script fails with an XML parse error, the .gramps file may be corrupted — verify the file starts with valid XML
- If import returns an unexpected error, run gramps_validate.py on the file to get a structured report
- If a query returns no results, say so helpfully: "I didn't find anyone with that surname in the file. The surnames present are: Varnell, Decker, Caine..."
- If asked about relationships the file can't determine (no linking family records), explain what's missing rather than guessing
- If genders appear swapped, use `person.get_gender() == Person.MALE` / `== Person.FEMALE` — never compare against raw integers
