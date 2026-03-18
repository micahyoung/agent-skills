---
name: genealogy
description: >
  Parse, explore, edit, and generate visual reports from GEDCOM (.ged) genealogy files. Use this skill whenever the user mentions a .ged file, GEDCOM data, family trees, ancestry, genealogy research, lineage, ancestors, descendants, pedigree charts, family history, heritage, great-grandparents, or wants to look up relatives, trace family connections, find out "who were my relatives", or correct/update genealogical records. Also trigger when the user has a .ged file open or referenced in conversation and asks questions about people, families, dates, or relationships — even if they don't say "genealogy" explicitly. Trigger for requests involving family tree charts, PDFs, or visualizations of genealogical data.
compatibility: Requires uv. Report Mode requires Docker. Uses Bash, Read, and Write tools.
---

# Genealogy Skill

You help users explore and edit GEDCOM 5.5 genealogy files. You have three modes:
- **Read Mode** (default)
- **Edit Mode**
- **Report Mode**

Always start in Read Mode unless the user explicitly asks to visualize or to make changes.

## How You Work

### Reading/Editing using python-gedcom in on-the-fly scripts

You accomplish most tasks by writing and executing short Python scripts on the fly using the `python-gedcom` library via `uv run`. This lets you handle arbitrarily complex queries and edits against real GEDCOM data rather than trying to eyeball the raw file.

Always run scripts with `uv run --with python-gedcom python ...` — this handles dependency installation automatically with no separate install step needed.

### Reporting with GRAMPS script

Specifically for generating reports, there is [./scripts/gramps_report.py](./scripts/gramps_report.py) which uses the `gramps` library to create any report supported by the application through the CLI interface. Call `./scripts/gramps_report.py --help` for usage details. Note: the script path is relative to this SKILL.md's directory — use `<skill-dir>/scripts/gramps_report.py` when constructing commands.

## Finding the GEDCOM File

If the user hasn't specified a file path:

1. **Glob for `**/*.ged`** in the working directory
2. **One file found** → use it, but confirm with the user: "I found `path/to/file.ged` — shall I use that?"
3. **Multiple files found** → list them and ask which one to use
4. **No files found** → ask the user for the path to their GEDCOM file

## Read Mode (default)

This is the primary mode. The user has a .ged file and wants to learn about the people and families in it. Your job is to answer their questions in warm, clear, natural language — like a knowledgeable family historian sitting beside them.

### Approach

1. **Parse the file** by writing a Python script that loads it with `gedcom.parser.Parser`
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

### Output format

Default to natural language prose. If the user asks for a specific format (markdown table, bullet list, a pedigree/ancestor chart in ASCII, etc.), provide that instead. For large result sets, use a concise format like a table to keep things scannable.

### Python scripting patterns for Read Mode

Here's the general shape of a read script:

```python
from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement
from gedcom.element.family import FamilyElement

parser = Parser()
parser.parse_file("path/to/file.ged")

elements = parser.get_element_dictionary()

# Example: find an individual by name fragment
for key, element in elements.items():
    if isinstance(element, IndividualElement):
        (first, last) = element.get_name()
        if "varnell" in last.lower():
            birth = element.get_birth_data()
            print(f"{first} {last}, born {birth[0]} in {birth[1]}")
```

Adapt freely. You're writing throwaway scripts to extract exactly what the user needs — not building a reusable library.

## Edit Mode

Switch to this mode only when the user explicitly wants to modify the .ged file — adding people, correcting names/dates, linking families, deleting records, etc.

Editing genealogical records is serious business. A wrong edit can propagate confusion through someone's family research. So this mode is deliberate and careful.

### The Edit Workflow

1. **Understand the change**: Confirm what the user wants to modify. If anything is ambiguous, ask before proceeding.

2. **Show a preview**: Before writing anything, describe the change in plain language:
   > I'm going to correct the surname on Individual @I5@ from "Smyth" to "Smith". This affects Clayton Rufus Smyth → Clayton Rufus Smith. Want me to go ahead?

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

6. **Increment the internal version**: Update the HEAD source version (e.g., `VERS 1.0` → `VERS 1.1`) each time edits are saved. This provides a simple audit trail within the file itself.

7. **Report what was done**: After writing, summarize the changes made.

### Edit safety rules

- **One logical change at a time**. If the user asks for multiple edits, handle them sequentially with individual confirmations, unless they explicitly say "go ahead and do all of these."
- **Never delete records without explicit confirmation**, even if the user implies it. Say: "This would remove [person/family] from the file entirely. Are you sure?"
- **Back up before bulk edits**. If the user asks for sweeping changes (e.g., "fix all the date formats"), save a backup copy first (e.g., `filename_backup_20260315.ged`) and tell them you did.
- **Preserve structure**. Don't reorder records unnecessarily. Don't strip existing notes or custom tags unless asked.

### Python scripting patterns for Edit Mode

For edits, you'll typically need to work at a lower level — reading the file, modifying the element tree, and writing back. Here's the general approach:

```python
import datetime
from gedcom.parser import Parser

filepath = "path/to/file.ged"
target_xref = "@I5@"

# Read the file as lines for text-level editing
with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

today = datetime.date.today().isoformat()
new_lines = []
in_target = False
found = False

for i, line in enumerate(lines):
    stripped = line.strip()

    # Detect when we enter/leave the target individual record
    if stripped.startswith("0") and target_xref in stripped and "INDI" in stripped:
        in_target = True
    elif stripped.startswith("0") and in_target:
        in_target = False

    # Replace an OCCU field within the target individual
    if in_target and stripped.startswith("1 OCCU"):
        new_lines.append("1 OCCU Foreman, Millhaven Grain Processing\n")
        new_lines.append(f"1 NOTE [CHANGELOG] {today}: Updated occupation from "
                         f"'{stripped[7:]}' to 'Foreman, Millhaven Grain Processing' "
                         f"(source: per family member correction)\n")
        found = True
        continue

    # Increment VERS in the HEAD section
    if stripped.startswith("2 VERS") and any(
        l.strip().startswith("1 SOUR") for l in lines[max(0,i-5):i]
    ):
        parts = stripped.split()
        if len(parts) == 3:
            try:
                major, minor = parts[2].split(".")
                new_vers = f"{major}.{int(minor)+1}"
                new_lines.append(f"2 VERS {new_vers}\n")
                continue
            except ValueError:
                pass

    new_lines.append(line)

if found:
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    # Sanity check: re-parse to ensure the file is still valid
    parser = Parser()
    parser.parse_file(filepath)
    print("Edit applied and file re-parsed successfully.")
else:
    print(f"Warning: OCCU field not found for {target_xref}")
```

This text-level approach gives full control over field edits, changelog notes, and version incrementing. Always re-parse the output file as a sanity check after writing.

## Report Mode

Switch to this mode when the user wants a visual report — a pedigree chart, relationship graph, fan chart, descendant tree, or any other graphical output from their GEDCOM data. Report Mode uses the bundled `scripts/gramps_report.py` script, which runs Gramps inside Docker to produce publication-quality reports.

### When to use Report Mode

Trigger Report Mode when the user asks for something visual or printable:
- "Draw me a family tree", "Show me a pedigree chart"
- "Generate a relationship graph for everyone descended from Warren"
- "I need a fan chart of Clay's ancestors"
- "Export a PDF of the descendant tree"
- "Create a timeline chart for Estelle"

If the user asks for an ASCII chart or text-based tree, stay in Read Mode and generate it with a Python script instead. Report Mode is specifically for graphical output (PDF, PNG, SVG, DOT).

### Prerequisites

- **Docker must be running**. The script pulls `ghcr.io/gramps-project/grampsweb:latest`. If Docker isn't available, tell the user and suggest they start it.
- The output file must be in the **same directory** as the input GEDCOM file.

### The Report Workflow

1. **Identify the center person**. Most reports require a Gramps `pid`. Gramps assigns its own internal IDs during import, which may differ from the GEDCOM `@XREF@` identifiers. To get the correct Gramps ID:
   1. First, find the person's name using a Read Mode python-gedcom script (to confirm you have the right individual).
   2. Then run `python <skill-dir>/scripts/gramps_report.py --list-people -i file.ged` to see Gramps-assigned IDs alongside names.
   3. Match by name and use that Gramps ID as the `--pid` value.

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
     -i path/to/family.ged \
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

- If the .ged file has encoding issues, try `UTF-8` and `latin-1` before giving up
- If the parser chokes on non-standard tags, catch the error and fall back to line-level parsing for those sections
- If a query returns no results, say so helpfully: "I didn't find anyone with that surname in the file. The surnames present are: Varnell, Decker, Caine..."
- If asked about relationships the file can't determine (no linking FAM records), explain what's missing rather than guessing
