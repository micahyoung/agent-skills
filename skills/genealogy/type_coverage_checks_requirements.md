# Requirements: `*Type` enum coverage checks for `gramps_validate.py`

## Background

`gramps_validate.py` is a wrapper script that validates a Gramps XML (`.gramps`) file
in three phases: (1) Gramps' native `import`, (2) Gramps' built-in `verify` tool (a
registered Gramps plugin, `plugins/tool/verify.py`, invoked via
`gramps -O <tree> -a tool -p name=verify`), and (3) a custom phase,
`_familysearch_checks.py`, which is a standalone script (not a registered Gramps
plugin) that loads the file directly via `gramps.gen.db.utils.import_as_dict` and
checks FamilySearch citation conventions. All three phases' findings are merged into
one JSON-issue list and printed as text or JSON.

This doc specifies a **fourth phase**: structural checks on Gramps' `*Type` enum
fields (`GrampsType` subclasses — `EventType`, `PlaceType`, `NameType`, etc.) and on
`Citation.Date`. The motivation: these fields carry real, structured, fixed-vocabulary
(or date) information that genealogical research quality depends on, but almost none
of them are currently checked by Gramps' own `verify` tool. Two specific bug classes
were found by hand in one `.gramps` file during this investigation and should now be
caught automatically:

1. A **duplicate-vocabulary bug**: a `*Type` field set to a `CUSTOM` (free-text)
   value whose text is actually a synonym of one of that type's own built-in standard
   values — e.g. an `EventType` of literal string `"Military"` when Gramps has a
   built-in standard `Military Service` type; an `AttributeType` of `"Cause"` when
   Gramps has a built-in standard `Cause` type. These happen when a user types free
   text instead of picking from the dropdown, and they're an unambiguous, fixable data
   error.
2. **Low field-coverage**: e.g. every `Citation` in the sample file had a blank
   `Date` field (0/363), `PlaceType` was essentially unused (0/284 using a standard
   value), and `NameOriginType` was 0/721. These aren't necessarily "wrong," but
   they're worth surfacing as a research-progress metric — a "how much of this
   category have we actually looked into" bar, not a pass/fail check.

**Do not duplicate what Gramps' built-in `verify` tool already checks.** Confirmed by
reading `plugins/tool/verify.py` in the Gramps installation used for this research:
`UnknownGender` (`Person.get_gender() == Person.UNKNOWN`) and
`FamilyHasEventsOfTypeUnknown` / `PersonHasEventsOfTypeUnknown` (despite the
"OfTypeUnknown" name, these actually check `EventRoleType == Unknown` on event
references, not `EventType`) are already implemented as ERROR-severity rules and
already run on every `gramps_validate.py` invocation, unconditionally (no rule
enable/disable option exists — `VerifyOptions` only exposes numeric thresholds like
`oldage`, `hwdif`). So: skip `Person.Gender` and `EventRoleType` in the new phase —
those are covered. Everything else in the field list below is not covered by anything
in stock Gramps, confirmed by grepping `verify.py` for every `Unknown` reference and by
web search turning up no addon that does this either.

## Before implementing: validate assumptions in the target repo

This doc was written against one specific Gramps installation
(`/Applications/Gramps.app`, a Gramps 5.x build) and one specific `.gramps` file.
Before writing code, in the target repo:

1. Confirm the bundled/available Python `gramps` package version and location (same
   pattern as this repo's `scripts/gramps_python` interpreter wrapper — find the
   equivalent entry point there).
2. Re-verify the field list below still matches that Gramps version's source, since
   `_DEFAULT` values, `_DATAMAP` contents, and even which `*Type` classes exist can
   change between Gramps releases. For each class, locate
   `gramps/gen/lib/<name>type.py` and read `_DATAMAP`, `_DEFAULT`, and `UNKNOWN`
   directly — don't trust this doc's numbers without re-checking against that repo's
   actual installed version.
3. Confirm the DTD (`grampsxml.dtd`, ships alongside the Gramps install) still shows
   `srcattribute`/`attribute` `type` as `CDATA #REQUIRED` (i.e. always a free string,
   with standard-vs-custom distinguished only by whether the string matches a known
   `_DATAMAP` label) — this affects how "custom" is detected in code (see Field
   Reference below).

## Field reference

For each field: how to reach it from a loaded `import_as_dict()` database object, its
class's `_DEFAULT` value, and whether `UNKNOWN` is distinguishable from "never
touched."

| Field | Accessor | `_DEFAULT` | Is `UNKNOWN` a real "reviewed, unknown" signal? |
|---|---|---|---|
| `EventType` | `Event.get_type()` for every `db.get_event_handles()` | `BIRTH` | Yes |
| `FamilyRelType` | `Family.get_relationship()` for every `db.get_family_handles()` | `MARRIED` | Yes |
| `PlaceType` | `Place.get_type()` for every `db.get_place_handles()` | **`UNKNOWN`** | **No** — default and "explicitly marked unknown" are the same stored value, indistinguishable from data alone |
| `NoteType` | `Note.get_type()` for every `db.get_note_handles()` | `GENERAL` | Yes |
| `RepositoryType` | `Repository.get_type()` for every `db.get_repository_handles()` | `LIBRARY` | Yes |
| `SourceMediaType` | `RepoRef.get_media_type()` for every `RepoRef` in every `Source.get_reporef_list()` | `BOOK` | Yes |
| `NameType` | `Name.get_type()` for `Person.get_primary_name()` + every `Person.get_alternate_names()` | `BIRTH` | Yes |
| `NameOriginType` | `Surname.get_origintype()` for every `Surname` in every `Name.get_surname_list()` | **`NONE`** (a distinct value from `UNKNOWN`, display string `""`) | Yes, but note: the "blank" bucket for this field is `NONE`, not `UNKNOWN` — don't conflate the two in code (`str(t)` for `NONE` is `""`, for `UNKNOWN` is `"Unknown"` with tests observed to include a trailing space quirk — compare by `.value`/enum constant, not string, to avoid this trap) |
| `ChildRefType` | `ChildRef.get_father_relation()` and `.get_mother_relation()`, for every `ChildRef` in every `Family.get_child_ref_list()` (2 values per child ref) | `BIRTH` | Yes |
| `EventRoleType` | **Skip** — already covered by stock `verify` (see Background) | — | — |
| `AttributeType` | `Attribute.get_type()` for every `Attribute` in `Person.get_attribute_list()`, `Family.get_attribute_list()`, `Event.get_attribute_list()` | `ID` | Yes |
| `SrcAttributeType` | `Attribute.get_type()` for every `Attribute` in `Source.get_attribute_list()`, `Citation.get_attribute_list()` | n/a — ships with **no built-in standard values at all** beyond `Unknown`/`Custom` (confirmed: `_DATAMAP` in `srcattrtype.py` has only those two entries) | Every real value here will show as `CUSTOM`; this field's duplicate-vocabulary check is a no-op (there's no standard vocabulary to collide with) — coverage-stat it, but don't run the duplicate check against it |
| `UrlType` | `Url.get_type()` for every `Url` in `Person.get_url_list()`, `Repository.get_url_list()` | **`UNKNOWN`** | **No** — same ambiguity as `PlaceType` |
| `Citation.Date` | `Citation.get_date_object().is_empty()` for every `db.get_citation_handles()` | n/a, not a `GrampsType` | n/a — this is a plain `Date` field, not an enum; "filled" just means `not is_empty()` |

`Person.Gender` and `EventRoleType`: **explicitly out of scope**, already covered.

## Checks to implement

Two independent checks, both structural (no prose/regex-over-free-text parsing —
that approach was considered and rejected earlier in this project specifically
because it's unreliable; stick to comparing enum/type values only).

### Check 1: Duplicate vocabulary (bug-class, should be a WARNING)

For every field in the table above (except `SrcAttributeType`, see note), for every
value that `is_custom()`, compare its custom string (case-insensitive, whitespace-
trimmed) against every standard label in that field's own `_DATAMAP` (excluding the
`Unknown`/`Custom` pseudo-entries). On a match, emit a finding: this record is using
free text that duplicates an existing standard dropdown value it should have used
instead.

This can be written as one generic function parameterized by:
- the field's Gramps class (to pull `_DATAMAP` off, e.g. `EventType._DATAMAP`)
- a list of `(object_type_str, gramps_id, record_name, type_value)` tuples gathered
  per the accessors in the table

Suggested finding shape (matching the existing `_familysearch_checks.py` schema so
`gramps_validate.py` can merge it without changes to the parsing/printing code):

```python
{
    "source": "type_coverage",
    "level": "W",
    "record_type": "Event",       # or Person/Family/Source/Citation/etc.
    "record_id": ev.get_gramps_id(),
    "record_name": "...",          # short human-readable label for the record
    "message": (
        f"{field_name} is set to custom value {custom_str!r}, which duplicates "
        f"the built-in standard value {standard_label!r} — should use the "
        f"standard type instead of free text."
    ),
    "noise": False,
}
```

### Check 2: Coverage stats (progress metric, not pass/fail)

For every field in the table (including `Citation.Date`), compute:
`total`, `standard` (real value from `_DATAMAP`, i.e. `not is_custom()` and not
equal to the field's blank-state value), `custom`, and `blank`
(`UNKNOWN` for most fields; `NONE` for `NameOriginType`; `is_empty()` for
`Citation.Date`).

For the two fields flagged in the table as "not distinguishable from data alone"
(`PlaceType`, `UrlType`), the `blank` bucket must be labeled/reported distinctly —
e.g. `"blank_or_unknown": true` in its output — so downstream consumers know not to
treat that number as a trustworthy "needs research" queue the way they could for,
say, `FamilyRelType`'s `Unknown` count.

This check does not need to emit per-record findings (that would be hundreds of
`.gramps` files' worth of noise for a merely-informational metric). Instead:
- Add a `--coverage` flag to `gramps_validate.py` (or a new small script/CLI, your
  call) that prints a table like the one produced by hand during this
  investigation — one row per field, columns `total / standard / custom / blank`,
  plus the `blank_or_unknown` caveat flag where applicable.
- This is explicitly **not** wired into the pass/fail exit code (`errors` count) —
  it's a visibility tool for tracking research progress over time, not a lint that
  should block anything.

## Integration

- New file: `_type_coverage_checks.py`, sibling to `_familysearch_checks.py`, same
  invocation contract (`gramps_python _type_coverage_checks.py <path-to-.gramps>`,
  prints one JSON array of finding-dicts to stdout for Check 1's findings).
- Wire it into `gramps_validate.py` the same way `_run_familysearch_checks` is
  wired in: a `_run_type_coverage_checks(input_path)` function following the same
  subprocess + JSON-parse + best-effort-failure pattern (don't fail the whole
  validate run if this phase errors — print a warning to stderr and return `[]`,
  matching the existing FamilySearch phase's error handling).
- Check 2 (coverage stats) is a separate concern from Check 1's findings list —
  don't try to cram percentage/summary stats into the same per-issue JSON schema
  that `_print_text`/`_print_json` expect. Give it its own flag and output path.

## Testing guidance

- Validate Check 1 against a `.gramps` file with a known duplicate-vocabulary case
  (e.g. an `EventType` custom value `"Military"` when `Military Service` is a
  standard value) and confirm it's flagged.
- Validate Check 1 does *not* false-positive on legitimate custom values that don't
  collide with any standard label (e.g. FamilySearch-import artifacts like `RFN` or
  `_FSFTID` as custom `AttributeType` values — these should pass through silently).
- Validate Check 2's counts against a hand count on a small fixture file (e.g. 3-4
  people, a couple of events, one citation with a date and one without) to catch
  off-by-one errors in the accessor loops (especially `ChildRefType`, which yields
  *two* values per child ref, and `NameType`/`NameOriginType`, which must include
  alternate names, not just each person's primary name).
