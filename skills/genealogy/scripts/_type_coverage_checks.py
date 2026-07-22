"""`*Type` enum coverage checks.

Runs under the gramps_python interpreter (needs gramps.gen.db.utils).
Prints a JSON array of issue-dicts (matching gramps_validate.py's schema)
to stdout, and nothing else.

Checks fields left at their "blank" value (structural comparison of
enum/type values only — no prose/regex parsing of free text), treated as a
data-quality defect: every such field is emitted as its own finding, marked
`noise: True` given the volume these can reach in a real file (e.g. 363
blank Citation.Dates in the file this was investigated against).

A duplicate-vocabulary check (custom free-text value colliding with one of
the field's own standard labels) was considered and dropped: Gramps'
grampstype.py normalizes any custom string that exactly matches a standard
label (localized or English) back to the standard enum value during XML
parsing (see set_from_xml_str/_S2IMAP/_E2IMAP), before this script ever
sees it. So an exact-match duplicate check is a structural no-op — it can
never produce a finding on any real file, confirmed empirically (setting
`<attribute type="Cause">`, matching a real AttributeType label exactly,
comes back `is_custom() == False`, not custom). Catching real near-miss
cases like "Military" vs. "Military Service" would require substring/fuzzy
matching, which was out of scope for this pass.

`Person.Gender` and `EventRoleType` are out of scope: both are already
covered by Gramps' own `verify` tool (UnknownGender,
FamilyHasEventsOfTypeUnknown / PersonHasEventsOfTypeUnknown).
"""

import json
import sys

from gramps.gen.db.utils import import_as_dict
from gramps.gen.lib import (
    AttributeType,
    ChildRefType,
    EventType,
    FamilyRelType,
    NameOriginType,
    NameType,
    NoteType,
    PlaceType,
    RepositoryType,
    SourceMediaType,
    SrcAttributeType,
    UrlType,
)
from gramps.cli.user import User

# Fields where the blank/_DEFAULT value is indistinguishable from "explicitly
# reviewed and marked unknown" -- their blank-field findings get a caveat.
_AMBIGUOUS_BLANK_FIELDS = {"PlaceType", "UrlType"}


def _short(text: str, limit: int = 60) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _gather_event_type(db):
    for handle in db.get_event_handles():
        ev = db.get_event_from_handle(handle)
        yield "Event", ev.get_gramps_id(), _short(ev.get_description()), ev.get_type()


def _gather_family_rel_type(db):
    for handle in db.get_family_handles():
        fam = db.get_family_from_handle(handle)
        yield "Family", fam.get_gramps_id(), fam.get_gramps_id(), fam.get_relationship()


def _gather_place_type(db):
    for handle in db.get_place_handles():
        place = db.get_place_from_handle(handle)
        name = place.get_name()
        yield ("Place", place.get_gramps_id(),
               _short(name.get_value() if name else ""), place.get_type())


def _gather_note_type(db):
    for handle in db.get_note_handles():
        note = db.get_note_from_handle(handle)
        yield "Note", note.get_gramps_id(), _short(note.get()), note.get_type()


def _gather_repository_type(db):
    for handle in db.get_repository_handles():
        repo = db.get_repository_from_handle(handle)
        yield "Repository", repo.get_gramps_id(), repo.get_name(), repo.get_type()


def _gather_source_media_type(db):
    for handle in db.get_source_handles():
        src = db.get_source_from_handle(handle)
        for reporef in src.get_reporef_list():
            yield ("Source", src.get_gramps_id(), _short(src.get_title()),
                   reporef.get_media_type())


def _person_name(person) -> str:
    name = person.get_primary_name()
    return f"{name.get_first_name()} {name.get_surname()}".strip()


def _gather_name_type(db):
    for handle in db.get_person_handles():
        person = db.get_person_from_handle(handle)
        pname = _person_name(person)
        names = [person.get_primary_name()] + list(person.get_alternate_names())
        for name in names:
            yield "Person", person.get_gramps_id(), pname, name.get_type()


def _gather_name_origin_type(db):
    for handle in db.get_person_handles():
        person = db.get_person_from_handle(handle)
        pname = _person_name(person)
        names = [person.get_primary_name()] + list(person.get_alternate_names())
        for name in names:
            for surname in name.get_surname_list():
                yield "Person", person.get_gramps_id(), pname, surname.get_origintype()


def _gather_child_ref_type(db):
    for handle in db.get_family_handles():
        fam = db.get_family_from_handle(handle)
        for child_ref in fam.get_child_ref_list():
            child = db.get_person_from_handle(child_ref.ref)
            cname = _person_name(child) if child else child_ref.ref
            yield ("Family", fam.get_gramps_id(), f"{cname} (father relation)",
                   child_ref.get_father_relation())
            yield ("Family", fam.get_gramps_id(), f"{cname} (mother relation)",
                   child_ref.get_mother_relation())


def _gather_attribute_type(db):
    for handle in db.get_person_handles():
        person = db.get_person_from_handle(handle)
        pname = _person_name(person)
        for attr in person.get_attribute_list():
            yield "Person", person.get_gramps_id(), pname, attr.get_type()
    for handle in db.get_family_handles():
        fam = db.get_family_from_handle(handle)
        for attr in fam.get_attribute_list():
            yield "Family", fam.get_gramps_id(), fam.get_gramps_id(), attr.get_type()
    for handle in db.get_event_handles():
        ev = db.get_event_from_handle(handle)
        for attr in ev.get_attribute_list():
            yield ("Event", ev.get_gramps_id(), _short(ev.get_description()),
                   attr.get_type())


def _gather_src_attribute_type(db):
    for handle in db.get_source_handles():
        src = db.get_source_from_handle(handle)
        for attr in src.get_attribute_list():
            yield "Source", src.get_gramps_id(), _short(src.get_title()), attr.get_type()
    for handle in db.get_citation_handles():
        cit = db.get_citation_from_handle(handle)
        for attr in cit.get_attribute_list():
            yield "Citation", cit.get_gramps_id(), _short(cit.get_page()), attr.get_type()


def _gather_url_type(db):
    for handle in db.get_person_handles():
        person = db.get_person_from_handle(handle)
        pname = _person_name(person)
        for url in person.get_url_list():
            yield "Person", person.get_gramps_id(), pname, url.get_type()
    for handle in db.get_repository_handles():
        repo = db.get_repository_from_handle(handle)
        for url in repo.get_url_list():
            yield "Repository", repo.get_gramps_id(), repo.get_name(), url.get_type()


# Each entry: (field_label, gramps_class, gatherer). Person.Gender and
# EventRoleType are intentionally omitted -- already covered by stock verify.
_TYPE_FIELDS = [
    ("EventType", EventType, _gather_event_type),
    ("FamilyRelType", FamilyRelType, _gather_family_rel_type),
    ("PlaceType", PlaceType, _gather_place_type),
    ("NoteType", NoteType, _gather_note_type),
    ("RepositoryType", RepositoryType, _gather_repository_type),
    ("SourceMediaType", SourceMediaType, _gather_source_media_type),
    ("NameType", NameType, _gather_name_type),
    ("NameOriginType", NameOriginType, _gather_name_origin_type),
    ("ChildRefType", ChildRefType, _gather_child_ref_type),
    ("AttributeType", AttributeType, _gather_attribute_type),
    ("SrcAttributeType", SrcAttributeType, _gather_src_attribute_type),
    ("UrlType", UrlType, _gather_url_type),
]

def find_blank_fields(db) -> list[dict]:
    """Fields left at their "blank" value.

    "Blank" means UNKNOWN (or NONE for NameOriginType, which has no
    meaningful UNKNOWN of its own for this purpose) -- NOT `_DEFAULT`.
    `_DEFAULT` is just the value a new record starts with in the GUI (e.g.
    EventType._DEFAULT is BIRTH); it's a real, legitimate standard value for
    most fields, not an "unset" marker, so comparing against it would flag
    every genuinely-Birth-typed event as blank.
    """
    findings = []
    for field_label, gramps_class, gatherer in _TYPE_FIELDS:
        blank_value = (
            gramps_class.NONE if field_label == "NameOriginType" else gramps_class.UNKNOWN
        )
        for record_type, record_id, record_name, type_value in gatherer(db):
            if type_value.value != blank_value:
                continue
            message = f"{field_label} is unset (at its default value)."
            if field_label in _AMBIGUOUS_BLANK_FIELDS:
                message += (
                    " Note: this field can't distinguish 'never reviewed' from "
                    "'explicitly marked unknown' in Gramps, so treat this as a "
                    "lower-confidence signal than other blank-field warnings."
                )
            findings.append({
                "source": "type_coverage",
                "level": "W",
                "record_type": record_type,
                "record_id": record_id,
                "record_name": record_name,
                "message": message,
                "noise": True,
            })

    for handle in db.get_citation_handles():
        cit = db.get_citation_from_handle(handle)
        if cit.get_date_object().is_empty():
            findings.append({
                "source": "type_coverage",
                "level": "W",
                "record_type": "Citation",
                "record_id": cit.get_gramps_id(),
                "record_name": _short(cit.get_page()),
                "message": "Citation.Date is unset.",
                "noise": True,
            })

    return findings


def main():
    filepath = sys.argv[1]
    db = import_as_dict(filepath, User())

    print(json.dumps(find_blank_fields(db)))


if __name__ == "__main__":
    main()
