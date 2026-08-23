# FIX_PROGRESS — Suppress Gramps per-object progress output in headless skill scripts

- **Component:** `genealogy` skill (`SKILL.md`, `scripts/`)
- **Affects:** all platforms; most visible in non-TTY contexts (agent shells, CI, piped output)
- **Verified against:** gramps 6.0.8 (PyPI), skill version `71b39f5e0138`
- **Status:** confirmed 2026-08-22; required fixes (items 1–8) applied and verified; optional items 9–10 not implemented
- **Priority:** low-medium (cosmetic noise, one latent parsing hazard)

## Problem

Every `import_as_dict(path, User())` (and `GrampsXmlWriter(..., user=User())`) call prints a
per-object progress bar to **stderr**: `00%01%02%…100%` on a single logical line. In an
interactive terminal the `\r` carriage returns overwrite one line (harmless), but in captured
or piped output the carriage returns do not clear the line, so the full percentage run is
dumped into the output. This pollutes every read/edit script run via `gramps_python`, and in
`gramps_validate.py` the progress text lands inside the import output that is parsed for
findings.

## Root cause

- The XML importer and XML exporter are both `UpdateCallback`s wrapping `user.callback`; they
  invoke it once per object read/written.
- `UserBase.callback` (`gramps/gen/user.py`) falls back to
  `UserBase._default_callback` when no custom `callback_function` is set:
  `self._fileout.write("\r%02d%%" % percentage)` with `_fileout = sys.stderr`.
- The CLI `User` (`gramps/cli/user.py`) does not override `callback`/`_default_callback`, so a
  plain `User()` always prints. `User(quiet=True)` replaces `_default_callback` with a no-op —
  this is the built-in switch the skill never uses.
- Separately, the gramps **CLI** has its own `-q/--quiet` ("Suppress progress output"); the
  skill passes it in `gramps_report.py` but not in `gramps_validate.py`.

## Required changes

One-token fix (`User()` → `User(quiet=True)`) at each site, plus one CLI flag:

1. `SKILL.md`, Read Mode scripting pattern — `db = import_as_dict("data.gramps", User())` →
   `User(quiet=True)`
2. `SKILL.md`, Edit Mode scripting pattern — `db = import_as_dict(filepath, User())` →
   `User(quiet=True)`
3. `SKILL.md`, Edit Mode scripting pattern — `GrampsXmlWriter(db, compress=0, version=VERSION,
   user=User())` → `user=User(quiet=True)` (export walks the same `UpdateCallback` path as
   import — `gramps/plugins/export/exportxml.py:122`)
4. `SKILL.md` — add a convention line in the Read Mode scripting section:
   > Always pass `quiet=True` to `User` in headless scripts — plain `User()` prints a
   > per-object progress bar to stderr that renders as a `00%…100%` dump outside a TTY.
   (This matters most: agents write throwaway scripts from these patterns, not just the two
   examples.)
5. `scripts/gramps_report.py` (`--list-people` embedded code, ~line 29) —
   `import_as_dict({input_path!r}, User())` → `User(quiet=True)`. Low urgency (stderr is
   captured, noise only leaks into the failure message) but same one-token fix.
   - The report path itself (~lines 200–201) already passes `-q` to both CLI invocations —
     no change needed.
6. `scripts/gramps_validate.py` (import command, ~line 59) —
   `gramps -y -C {TREE_NAME} -i "$GRAMPS_WORK_DIR/{input_name}" 2>&1` → add `-q`.
   **This is the only CLI invocation in the skill without `-q`, and the progress run lands in
   the parsed import text (`_parse_import`) — the one latent hazard in this ticket.**
7. `scripts/_familysearch_checks.py` (~line 206) — `import_as_dict(filepath, User())` →
   `User(quiet=True)` (runs in-process from `gramps_validate.py`; progress goes straight to
   the terminal)
8. `scripts/_type_coverage_checks.py` (~line 246) — same

## Optional (recommended): centralized fix

Items 1–8 only cover shipped code. Throwaway agent scripts that use a plain `User()` (e.g.
from a recalled or stale example) would still print. To make quiet-by-default a property of
the interpreter:

9. `scripts/_gramps_python_bootstrap/sitecustomize.py` — add a guarded patch after the
   existing locale patch:

   ```python
   try:
       from gramps.gen import user as _guser
       _guser.UserBase._default_callback = lambda self, pct, text=None: None
   except ImportError:
       pass
   ```

   Only the headless fallback is patched; GUI progress dialogs don't go through
   `_default_callback`.

10. `scripts/gramps_python` (Linux path, ~line 95) — prepend the bootstrap dir to `PYTHONPATH`
    before `execve`, mirroring the macOS path (lines 72–77). As-is, the Linux path execs the
    venv python with an unmodified environment, so `sitecustomize` never loads there.

    Trade-offs to document in the ticket/commit:
    - every `gramps_python` invocation pays a `gramps.gen` import at startup (scripts import
      it anyway);
    - any `gramps` CLI subprocess spawned *from* a gramps_python script inherits the patched
      environment and goes quiet too (desirable side effect).

## Verification

All run 2026-08-22 against gramps 6.0.8 (venv `/home/user/gramps-venv`) and
`test-fixtures/data.gramps` (164 people).

- [x] `gramps_python -c "...import_as_dict(..., User())..."` on a real `.gramps` file:
      before fix, plain `User()` wrote 405 bytes of `\r00%\r01%\r…\r100%` to stderr;
      `User(quiet=True)` wrote 0 bytes. (Items 9/10 not implemented — direct use of a plain
      `User()` still prints; the shipped skill code and examples no longer do.)
- [x] `gramps_report.py --list-people -i data.gramps`: clean output (0 stderr bytes).
      Failure path (corrupt file): stderr dropped 819 → 419 bytes, zero `NN%` tokens — the
      remainder is unrelated GTK/PyGI import-time warnings (see Notes).
- [x] `gramps_report.py -i data.gramps -o out.pdf -f pdf -r fan_chart -p I0002` → fan.pdf
      (31,672 bytes), 0 stderr bytes, no progress tokens (report path already had `-q`).
- [x] `gramps_validate.py -i data.gramps`: internal import section dropped 855 → 450 bytes,
      101 → 0 percent tokens; findings identical before/after (1 error, 7 warnings,
      229 noise suppressed). JSON diff of a quiet-export round-trip: byte-identical findings.
- [x] Edit Mode round-trip: `GrampsXmlWriter(..., user=User(quiet=True))` output re-validated
      with `gramps_validate.py` — zero new/missing findings.
- [x] Hazard demonstration: importing a truncated file without `-q` produced
      `E [line ?] 99%Error reading …` (percent run fused to the error message, no newline
      between them); with the item-6 `-q` fix the detail is clean:
      `E [line ?] Error reading …`.
- [ ] macOS path still works (bootstrap `sitecustomize` loads in both paths after item 10;
      locale patch unaffected). — not applicable: items 9–10 not implemented; macOS path
      untouched by this fix.

### Confirmation notes

- All code-site line numbers in this ticket were exact against the current source tree.
- Item 7's rationale is imprecise: `_familysearch_checks.py` / `_type_coverage_checks.py`
  do **not** run in-process from `gramps_validate.py` — they run as `gramps_python`
  subprocesses with `stderr=PIPE` (gramps_validate.py:92–97, 121–126). Their progress was
  captured, not terminal-bound; it only reached the terminal on the check-failure path. The
  one-token fix is still correct.
- `gramps_validate.py:61` (the `verify` tool command) was checked and needs no `-q`:
  `Verify` is an `UpdateCallback` but the CLI `uistate.pulse_progressbar` emits no progress
  in headless mode (0 tokens observed).
- The pre-existing `startswith("00%")` guard in `_parse_import` (gramps_validate.py:25) is
  now dead defensive code (harmless); it was a band-aid for exactly this interleaving and
  could theoretically swallow an error line landing on the `00%` fragment.
- Unrelated pre-existing noise, out of scope for this ticket: every headless gramps process
  in this container also emits GTK/PyGI/Glycin warnings to stderr (`PyGIWarning: Gtk was
  imported…`, `Gtk-CRITICAL: gtk_icon_theme_get_for_screen`, `WARNING: Glycin running
  without sandbox`). They appear in the captured validate import section but contain neither
  "error" nor progress patterns, so they are parse-harmless.

## Notes

- The paths above are from the installed plugin cache
  (`~/.claude/plugins/cache/micahyoung-agent-skills/genealogy/71b39f5e0138/…`); line numbers
  should be re-checked against the source tree when implementing.
- No behavior change is intended for interactive terminal use: a progress bar is still
  *available* (pass `User()` or a custom callback), it is just no longer emitted by the
  skill's own code or examples.
