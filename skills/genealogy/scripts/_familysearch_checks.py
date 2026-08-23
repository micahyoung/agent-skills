"""FamilySearch citation convention checks.

Runs under the gramps_python interpreter (needs gramps.gen.db.utils).
Prints a JSON array of issue-dicts (matching gramps_validate.py's schema)
to stdout, and nothing else.

Conventions checked, established from:
  - FamilySearch developer docs (canonical ARK form has no "www." prefix)
    https://developers.familysearch.org/main/docs/persistent-identifiers
  - Gramps wiki citation example (cite the original record via the Source's
    Repository Call Number)
    https://www.gramps-project.org/wiki/index.php/Citation_examples:FamilySearch

Call Number nuance: a Call Number (Digital Folder Number) only exists for a
single FamilySearch catalog item (one digitized book/film) -- catalog items
are the ones with a RepoRef into a Repository named "FamilySearch Digital
Library". A browsable collection/index Source (e.g. "United States Census,
1930") is instead linked to the general "FamilySearch.org" Repository and has
no Digital Folder Number to assign; flagging those as missing one would be a
false positive. A Source with no RepoRef at all (e.g. one that only cites a
FamilySearch Family Tree person profile, not an archival record) is naturally
never flagged either, since there's no RepoRef to hold a Call Number in the
first place. This split was verified against a real Gramps file: every
Source referencing "FamilySearch Digital Library" had a Call Number set, and
every Source referencing "FamilySearch.org" (or lacking a RepoRef) had none --
so the check keys off the linked Repository's Name field rather than parsing
Source titles or Citation text.
"""

import json
import re
import sys

from gramps.gen.db.utils import import_as_dict
from gramps.gen.lib import Citation
from gramps.cli.user import User

FS_URL_RE = re.compile(
    r'((https?://)?(www\.)?familysearch\.org[^\s"\'<>\)]*'
    r'|ark:/61903/[^\s"\'<>\)]*)',
    re.IGNORECASE,
)

# A title that is nothing but (optionally "FamilySearch" +) a bare/URL ARK,
# with no descriptive text of its own.
_ARK_ONLY_TITLE_RE = re.compile(
    r'^\s*(https?://)?(www\.)?(familysearch\.org/)?(familysearch\s+)?ark:/61903/\S+\s*$',
    re.IGNORECASE,
)

# The FamilySearch Repository whose RepoRefs carry a Call Number (Digital
# Folder Number) -- as opposed to a Repository named e.g. "FamilySearch.org"
# for the general historical-records site, which never has one.
_FS_CATALOG_REPO_RE = re.compile(r'digital library', re.IGNORECASE)


def _is_www(url: str) -> bool:
    return url.lower().startswith(("http://www.", "https://www.", "www."))


def _is_standalone(match_text: str, field_text: str) -> bool:
    """True if the match essentially IS the field's content, not one citation
    embedded among other prose (e.g. a research Note listing several ARKs in
    sentences). Trailing punctuation corruption / host-prefix style only make
    sense to flag when the field is meant to hold just the URL/ARK itself."""
    stripped = (field_text or "").strip()
    if not stripped:
        return False
    return len(match_text) / len(stripped) >= 0.5


def _short(text: str, limit: int = 60) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def scan_familysearch_urls(db) -> list[dict]:
    """Check B (non-canonical www host)."""
    findings = []

    def scan(text, record_type, record_id, record_name):
        for m in FS_URL_RE.finditer(text or ""):
            url = m.group(0)
            if not _is_standalone(url, text):
                # One citation embedded among prose (e.g. a research Note) —
                # this check only makes sense when the field is meant to hold
                # just the URL/ARK itself, not one mention among other text.
                continue
            if _is_www(url):
                findings.append({
                    "source": "familysearch", "level": "W",
                    "record_type": record_type, "record_id": record_id,
                    "record_name": record_name,
                    "message": f"FamilySearch URL uses non-canonical 'www.' prefix "
                               f"(canonical form omits it): {url}",
                    "noise": True,
                })

    for handle in db.get_source_handles():
        src = db.get_source_from_handle(handle)
        rid, rname = src.get_gramps_id(), _short(src.get_title())
        scan(src.get_title(), "Source", rid, rname)
        scan(src.get_author(), "Source", rid, rname)
        scan(src.get_publication_info(), "Source", rid, rname)

    for handle in db.get_citation_handles():
        cit = db.get_citation_from_handle(handle)
        scan(cit.get_page(), "Citation", cit.get_gramps_id(), _short(cit.get_page()))

    for handle in db.get_note_handles():
        note = db.get_note_from_handle(handle)
        scan(note.get(), "Note", note.get_gramps_id(), _short(note.get()))

    for handle in db.get_person_handles():
        person = db.get_person_from_handle(handle)
        name = person.get_primary_name()
        pname = f"{name.get_first_name()} {name.get_surname()}".strip()
        for attr in person.get_attribute_list():
            scan(attr.get_value(), "Person", person.get_gramps_id(), pname)

    for handle in db.get_event_handles():
        event = db.get_event_from_handle(handle)
        scan(event.get_description(), "Event", event.get_gramps_id(),
             _short(event.get_description()))

    return findings


def _familysearch_catalog_source_handles(db) -> set:
    """Sources with a RepoRef into a Repository named "FamilySearch Digital
    Library" -- the only FamilySearch repository type that assigns Call
    Numbers (Digital Folder Numbers)."""
    catalog_repo_handles = set()
    for handle in db.get_repository_handles():
        repo = db.get_repository_from_handle(handle)
        if _FS_CATALOG_REPO_RE.search(repo.get_name() or ""):
            catalog_repo_handles.add(handle)

    catalog_source_handles = set()
    for handle in db.get_source_handles():
        src = db.get_source_from_handle(handle)
        for reporef in src.get_reporef_list():
            if reporef.ref in catalog_repo_handles:
                catalog_source_handles.add(handle)
                break

    return catalog_source_handles


def scan_citation_structure(db) -> list[dict]:
    """Check D (missing Call Number)."""
    findings = []
    catalog_source_handles = _familysearch_catalog_source_handles(db)

    citations_by_source = {}
    for handle in db.get_citation_handles():
        cit = db.get_citation_from_handle(handle)
        citations_by_source.setdefault(cit.get_reference_handle(), []).append(cit)

    for handle in catalog_source_handles:
        src = db.get_source_from_handle(handle)
        call_numbers = [rr.get_call_number() for rr in src.get_reporef_list() if rr.get_call_number()]
        if call_numbers:
            continue
        related = citations_by_source.get(handle, [])
        if related and all(c.get_confidence_level() == Citation.CONF_VERY_LOW for c in related):
            # Every citation for this source is already flagged as unreliable/estimated
            # evidence, so chasing down a precise Call Number isn't worth the noise.
            continue
        findings.append({
            "source": "familysearch", "level": "W",
            "record_type": "Source", "record_id": src.get_gramps_id(),
            "record_name": _short(src.get_title()),
            "message": "Source linked to the FamilySearch Digital Library catalog has no "
                       "Call Number (Digital Folder Number) set on its Repository reference; "
                       "the 'cite the original record' convention uses this to uniquely "
                       "identify the record independent of the FamilySearch web presentation.",
            "noise": False,
        })

    return findings


def scan_title_quality(db) -> list[dict]:
    """Check E: Source title is nothing but a bare/URL ARK, not descriptive text."""
    findings = []
    for handle in db.get_source_handles():
        src = db.get_source_from_handle(handle)
        title = src.get_title() or ""
        if _ARK_ONLY_TITLE_RE.match(title):
            findings.append({
                "source": "familysearch", "level": "W",
                "record_type": "Source", "record_id": src.get_gramps_id(),
                "record_name": _short(title),
                "message": f"Source title is just a bare FamilySearch ARK ({title!r}) "
                           f"with no descriptive text; the wiki's own style guide says "
                           f"Title 'should ensure the source can be uniquely identified' "
                           f"by a human reader, not just an opaque id.",
                "noise": False,
            })
    return findings


def main():
    filepath = sys.argv[1]
    db = import_as_dict(filepath, User(quiet=True))

    findings = (
        scan_familysearch_urls(db)
        + scan_citation_structure(db)
        + scan_title_quality(db)
    )
    print(json.dumps(findings))


if __name__ == "__main__":
    main()
