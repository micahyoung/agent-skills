#!/usr/bin/env python3
"""Generate Gramps reports from GEDCOM files."""

import argparse
import os
import subprocess
import sys

from _gramps_backend import TREE_NAME, remove_family_tree, run_gramps


def list_people(input_file):
    """Import GEDCOM into Gramps and list all people with Gramps IDs.

    Uses gramps_python (our bundled interpreter) to access the Gramps Python API,
    since the Gramps CLI -e export only exports Places, not People.
    """
    input_path = os.path.abspath(input_file)
    if not os.path.isfile(input_path):
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Find the gramps_python interpreter sibling to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gramps_python = os.path.join(script_dir, "gramps_python")

    python_code = f'''
from gramps.gen.db.utils import import_as_dict
from gramps.cli.user import User
db = import_as_dict({input_path!r}, User())
for handle in db.get_person_handles():
    person = db.get_person_from_handle(handle)
    name = person.get_primary_name()
    first = name.get_first_name()
    last = name.get_surname()
    gramps_id = person.get_gramps_id()
    print(f"{{gramps_id}}: {{first}} {{last}}")
'''

    result = subprocess.run(
        [gramps_python, "-c", python_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        print("Error: failed to list people from Gramps", file=sys.stderr)
        sys.exit(1)
    print(result.stdout, end="")


def main():
    parser = argparse.ArgumentParser(
        description="Run a Gramps report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
output formats (-f):
  dot           Graphviz DOT (text-based graph description)
  svg           SVG image (note: text rendered as glyph paths, not fonts)
  pdf           PDF document (embeds fonts)
  ps            PostScript
  png           PNG raster image (see -e dpi=N to control resolution)

report names (-r):
  rel_graph            Relationship Graph — full or filtered network of everyone
  ancestor_chart       Ancestor Tree — pedigree chart going back in time
  descend_chart        Descendant Tree — tree going forward from a person
  family_descend_chart Family Descendant Tree — descendant tree including spouses
  fan_chart            Fan Chart — circular ancestor chart
  hourglass_graph      Hourglass Graph — ancestors above, descendants below
  ancestor_report      Ahnentafel Report — numbered ancestor list
  descend_report       Descendant Report — text descendant list
  det_ancestor_report  Detailed Ancestral Report — ancestors with full details
  det_descendant_report Detailed Descendant Report — descendants with full details
  family_group         Family Group Report — single family unit detail sheet
  indiv_complete       Complete Individual Report — all info for one person
  kinship_report       Kinship Report — everyone related to center person
  endofline_report     End of Line Report — terminal ancestors (brick walls)
  timeline             Timeline Chart — chronological life events
  birthday_report      Birthday and Anniversary Report
  familylines_graph    Family Lines Graph — relationship graph with photos
  number_of_ancestors  Number of Ancestors Report
  place_report         Place Report — list of places in the database
  records              Records Report — oldest, youngest, largest families, etc.
  statistics_chart     Statistics Charts
  summary              Database Summary Report
  calendar             Calendar
  tag_report           Tag Report

extra report options (-e), passed as comma-separated key=value pairs:
  common options (most reports):
    filter=N            filter people included (use show=filter to list values):
                          0 = Entire Database
                          1 = Descendants of center person
                          2 = Descendant Families of center person
                          3 = Ancestors of center person
                          4 = People with common ancestor with center person
    incl_private=0|1    include private records (default: 1)
    living_people=0-4   how to handle living people

  rel_graph / graph reports:
    color=0|1           color nodes by gender (default: 1)
    dashed=0|1          dashed lines for non-birth relationships (default: 1)
    arrow=0-3           arrow direction (0=none, 1=descendants, 2=ancestors, 3=both)
    increlname=0|1      show relationship name to center person
    advrelinfo=0|1      show Ga/Gb relationship debug info
    includeImages=0|1   include thumbnail images
    imageOnTheSide=0|1  image placement relative to name
    inc_id=0-2          include Gramps IDs (0=no, 1=yes, 2=below name)
    occupation=0|1      include last known occupation
    event_choice=0-3    date/place inclusion (0=dates+places, 1=dates, 2=places, 3=none)
    dpi=N               dots per inch for raster output (e.g. 100, 300)
    font_family=0|1     font (0=default, 1=FreeSans for international chars)
    font_size=N         font size in points
    nodesep=N           spacing between nodes in inches (default: 0.20)
    ranksep=N           spacing between ranks in inches (default: 0.20)
    note="text"         add a note to the graph
    noteloc=t|b         note location (top or bottom)

  ancestor_chart / descend_chart / family_descend_chart:
    maxgen=N            maximum generations to include

  fan_chart:
    maxgen=N            max generations (default: 5)
    background=0-2      background style
    radial=0-2          radial display style

examples:
  # Relationship graph as PDF, filtered to descendant families:
  %(prog)s -i family.ged -o out.pdf -f pdf -r rel_graph -p I123 -e "filter=2"

  # Ancestor pedigree chart with 6 generations:
  %(prog)s -i family.ged -o ancestors.pdf -f pdf -r ancestor_chart -p I123 -e "maxgen=6"

  # High-res PNG of full database graph:
  %(prog)s -i family.ged -o full.png -f png -r rel_graph -p I123 -e "filter=0,dpi=300"

  # Fan chart as SVG:
  %(prog)s -i family.ged -o fan.svg -f svg -r fan_chart -p I123

  # List available filter values for a report:
  # gramps -O tree -a report -p "name=rel_graph,pid=I123,show=filter"
"""
    )
    parser.add_argument("-i", "--input", required=True,
                        help="Input GEDCOM file (e.g. family.ged)")
    parser.add_argument("-o", "--output",
                        help="Output file (e.g. family.pdf)")
    parser.add_argument("-f", "--format",
                        help="Output format: dot, svg, pdf, ps, png")
    parser.add_argument("-r", "--report",
                        help="Report name (see list below)")
    parser.add_argument("-p", "--pid",
                        help="Gramps person ID for center person (e.g. I333632792360003263)")
    parser.add_argument(
        "-e", "--extra", default="",
        help="Extra report options as comma-separated key=value pairs (see below)"
    )
    parser.add_argument(
        "--list-people", action="store_true",
        help="Import the GEDCOM into Gramps and list all people with their Gramps IDs, then exit"
    )
    args = parser.parse_args()

    if args.list_people:
        list_people(args.input)
        return

    # Validate required args for report mode
    for flag in ("output", "format", "report", "pid"):
        if not getattr(args, flag):
            parser.error(f"--{flag} is required when not using --list-people")

    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)

    if not os.path.isfile(input_path):
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    input_dir = os.path.dirname(input_path)
    input_name = os.path.basename(input_path)
    output_name = os.path.basename(output_path)

    # If output is in a different directory, we need to handle that
    output_dir = os.path.dirname(output_path)
    if output_dir != input_dir:
        print(f"Error: output file must be in the same directory as input file ({input_dir})", file=sys.stderr)
        sys.exit(1)

    # Ensure clean slate by removing any existing tmp_tree
    remove_family_tree(TREE_NAME)

    # Build report options string
    opts = f"name={args.report},pid={args.pid},off={args.format},of=$GRAMPS_WORK_DIR/{output_name}"
    if args.extra:
        opts += f",{args.extra}"

    shell_script = (
        f'gramps -y -C {TREE_NAME} -i "$GRAMPS_WORK_DIR/{input_name}" -q 2>&1 | tail -2 && '
        f'gramps -O {TREE_NAME} -a report -p "{opts}" -q 2>&1'
    )

    print(f"Running: {args.report} report -> {output_name} (format={args.format}, center={args.pid})")
    sys.stdout.flush()
    result = run_gramps(shell_script, input_dir)
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(f"Error: Gramps command failed (exit {result.returncode})", file=sys.stderr)
        sys.exit(1)

    # Gramps appends .gv to dot output files — rename if needed
    actual_output = os.path.join(input_dir, output_name + ".gv")
    if os.path.isfile(actual_output) and not os.path.isfile(output_path):
        os.rename(actual_output, output_path)

    if os.path.isfile(output_path):
        size = os.path.getsize(output_path)
        print(f"Written: {output_path} ({size:,} bytes)")
    else:
        print("Error: output file was not created", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
