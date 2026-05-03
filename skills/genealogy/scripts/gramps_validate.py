#!/usr/bin/env python3
"""Validate a GEDCOM file using Gramps."""

import argparse
import json
import os
import re
import sys

from _gramps_backend import TREE_NAME, remove_family_tree, run_gramps

# Verify output line: "W: <message>, Person: <ID>, <Name>"
_VERIFY_RE = re.compile(r"^([WE]):\s+(.+?),\s+(Person|Family):\s+(\S+),\s+(.+)$")

# Import warning line: "Tag recognized but not supported  Line N: <tag>"
_IMPORT_TAG_RE = re.compile(r"Tag recognized but not supported\s+Line\s+(\d+):\s+(.+)")
_IMPORT_VERS_RE = re.compile(r"GEDCOM version not supported\s+Line\s+(\d+):")

# Verify warnings that are not meaningful genealogical errors
_NOISE_MESSAGES = {
    "Husband and wife with the same surname",
}


def _parse_import(text: str) -> list[dict]:
    issues = []
    for line in text.splitlines():
        m = _IMPORT_TAG_RE.search(line)
        if m:
            issues.append({
                "source": "import", "level": "W",
                "category": "unsupported_tag",
                "line": int(m.group(1)), "detail": m.group(2).strip(),
                "noise": True,
            })
            continue
        m = _IMPORT_VERS_RE.search(line)
        if m:
            issues.append({
                "source": "import", "level": "W",
                "category": "gedcom_version",
                "line": int(m.group(1)), "detail": "GEDCOM version not supported",
                "noise": True,
            })
    return issues


def _parse_verify(text: str) -> list[dict]:
    issues = []
    for line in text.splitlines():
        m = _VERIFY_RE.match(line.strip())
        if m:
            level, message, record_type, record_id, record_name = m.groups()
            issues.append({
                "source": "verify", "level": level,
                "message": message,
                "record_type": record_type,
                "record_id": record_id,
                "record_name": record_name,
                "noise": message in _NOISE_MESSAGES,
            })
    return issues


def validate(input_path: str, input_name: str, input_dir: str) -> tuple[list[dict], list[dict]]:
    # Ensure clean slate by removing any existing tmp_tree
    remove_family_tree(TREE_NAME)

    shell_script = (
        f"echo '=== IMPORT ===' && "
        f"gramps -y -C {TREE_NAME} -i /data/{input_name} 2>&1 && "
        f"echo '=== VERIFY ===' && "
        f"gramps -O {TREE_NAME} -a tool -p name=verify 2>&1"
    )

    result = run_gramps(shell_script, input_dir)
    output = result.stdout

    import_text = ""
    verify_text = ""
    if "=== IMPORT ===" in output and "=== VERIFY ===" in output:
        parts = output.split("=== VERIFY ===", 1)
        import_text = parts[0].replace("=== IMPORT ===", "").strip()
        verify_text = parts[1].strip() if len(parts) > 1 else ""

    if result.returncode != 0 and not verify_text:
        print(output, file=sys.stderr)
        print("Error: Gramps command failed", file=sys.stderr)
        sys.exit(1)

    return _parse_import(import_text), _parse_verify(verify_text)


def _print_text(issues: list[dict], show_noise: bool, input_path: str) -> int:
    visible = issues if show_noise else [i for i in issues if not i["noise"]]
    suppressed = [i for i in issues if i["noise"]] if not show_noise else []

    errors = [i for i in visible if i["level"] == "E"]
    warnings = [i for i in visible if i["level"] == "W"]

    # Noise breakdown for suppressed message
    noise_tags = sum(1 for i in suppressed if i.get("category") == "unsupported_tag")
    noise_vers = sum(1 for i in suppressed if i.get("category") == "gedcom_version")
    noise_surname = sum(1 for i in suppressed if i.get("message") == "Husband and wife with the same surname")
    noise_other = len(suppressed) - noise_tags - noise_vers - noise_surname

    print(f"\nValidating: {input_path}\n")

    if errors:
        print(f"Errors ({len(errors)}):")
        for i in errors:
            if i["source"] == "verify":
                print(f"  E [{i['record_type']} {i['record_id']}] {i['record_name']} — {i['message']}")
            else:
                print(f"  E [line {i.get('line', '?')}] {i.get('detail', '')}")
    else:
        print("Errors: none")

    print()

    if warnings:
        print(f"Warnings ({len(warnings)}):")
        for i in warnings:
            if i["source"] == "verify":
                print(f"  W [{i['record_type']} {i['record_id']}] {i['record_name']} — {i['message']}")
            else:
                print(f"  W [line {i.get('line', '?')}] {i.get('detail', '')}")
    else:
        print("Warnings: none")

    if suppressed:
        print()
        parts = []
        if noise_tags:
            parts.append(f"{noise_tags} unsupported-tag import warning{'s' if noise_tags != 1 else ''}")
        if noise_vers:
            parts.append(f"{noise_vers} GEDCOM-version warning{'s' if noise_vers != 1 else ''}")
        if noise_surname:
            parts.append(f"{noise_surname} same-surname warning{'s' if noise_surname != 1 else ''}")
        if noise_other:
            parts.append(f"{noise_other} other low-signal warning{'s' if noise_other != 1 else ''}")
        print(f"Noise suppressed: {', '.join(parts)} (use --all to show)")

    print(f"\nResult: {len(errors)} error{'s' if len(errors) != 1 else ''}, "
          f"{len(warnings)} warning{'s' if len(warnings) != 1 else ''}")

    return len(errors)


def _print_json(issues: list[dict], show_noise: bool) -> int:
    visible = issues if show_noise else [i for i in issues if not i["noise"]]
    suppressed_count = sum(1 for i in issues if i["noise"]) if not show_noise else 0

    errors = [i for i in visible if i["level"] == "E"]
    warnings = [i for i in visible if i["level"] == "W"]

    output = {
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "noise_suppressed": suppressed_count,
        },
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(output, indent=2))
    return len(errors)


def main():
    parser = argparse.ArgumentParser(
        description="Validate a GEDCOM file using Gramps.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
exit codes:
  0   No errors found (warnings may still be present)
  1   One or more errors found

noise filtering:
  By default, low-signal issues are suppressed from output:
    - "Tag recognized but not supported" (EMAIL/PHON Geni.com extensions)
    - "GEDCOM version not supported" (spec version mismatch)
    - "Husband and wife with the same surname" (coincidental, not an error)
  Use --all to include them.

examples:
  %(prog)s -i family.ged
  %(prog)s -i family.ged -f json
  %(prog)s -i family.ged --all
"""
    )
    parser.add_argument("-i", "--input", required=True,
                        help="Input GEDCOM file (e.g. family.ged)")
    parser.add_argument("-f", "--format", choices=["text", "json"], default="text",
                        help="Output format: text (default) or json")
    parser.add_argument("--all", action="store_true",
                        help="Include low-signal noise warnings (suppressed by default)")
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.isfile(input_path):
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    input_dir = os.path.dirname(input_path)
    input_name = os.path.basename(input_path)

    import_issues, verify_issues = validate(input_path, input_name, input_dir)
    all_issues = import_issues + verify_issues

    if args.format == "json":
        error_count = _print_json(all_issues, show_noise=args.all)
    else:
        error_count = _print_text(all_issues, show_noise=args.all, input_path=args.input)

    sys.exit(1 if error_count > 0 else 0)


if __name__ == "__main__":
    main()
