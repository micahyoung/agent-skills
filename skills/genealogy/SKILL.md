---
name: genealogy
description: >
  Parse, explore, and edit GEDCOM (.ged) genealogy files. Use this skill whenever the user
  mentions a .ged file, GEDCOM data, family trees, ancestry, genealogy research, lineage,
  ancestors, descendants, pedigree charts, or wants to look up relatives, trace family
  connections, or correct/update genealogical records. Also trigger when the user has a .ged
  file open or referenced in conversation and asks questions about people, families, dates,
  or relationships — even if they don't say "genealogy" explicitly.
compatibility: Requires uv. Uses Bash, Read, and Write tools.
---

# Genealogy Skill

You help users explore and edit GEDCOM 5.5 genealogy files. You have two modes: **Read Mode** (default) and **Edit Mode**. Always start in Read Mode unless the user explicitly asks to make changes.

## How You Work

You accomplish tasks by writing and executing short Python scripts on the fly using the `python-gedcom` library via `uv run`. This lets you handle arbitrarily complex queries and edits against real GEDCOM data rather than trying to eyeball the raw file.

Always run scripts with `uv run --with python-gedcom python ...` — this handles dependency installation automatically with no separate install step needed.

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
from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement
import datetime

parser = Parser()
parser.parse_file("path/to/file.ged")

elements = parser.get_element_dictionary()
root = parser.get_root_child_elements()

# Find and modify the target individual
target = elements.get("@I5@")
if target and isinstance(target, IndividualElement):
    # Modify the element as needed
    # ... (specific edit logic here)

    # Add changelog note
    today = datetime.date.today().isoformat()
    # Add NOTE child element with changelog
    pass

# Write the modified file
# Note: python-gedcom's output may need manual assembly
# for complex edits — write a helper that walks the element tree
```

Because `python-gedcom`'s write support can be limited for complex structural edits, you may sometimes need to read the .ged as text, make targeted string-level edits, and write it back — that's fine as long as you validate the result still parses correctly. Always re-parse the output file as a sanity check after writing.

## Handling Errors Gracefully

- If the .ged file has encoding issues, try `UTF-8` and `latin-1` before giving up
- If the parser chokes on non-standard tags, catch the error and fall back to line-level parsing for those sections
- If a query returns no results, say so helpfully: "I didn't find anyone with that surname in the file. The surnames present are: Varnell, Decker, Caine..."
- If asked about relationships the file can't determine (no linking FAM records), explain what's missing rather than guessing
