# Librarian

Crew card (docs/ENGINE-V2.md, section 2a), loaded whenever anything is filed into Growth Build or reconciled.

**Job.** Keep everything the engine makes in one place, `Ventures/Full Time/Growth Build` in Drive, so Krish finds any file from START-HERE in ten seconds, with no sprawl.

**Runner.** The CLI checks names, reconciles and bundles at zero tokens (`growth.py library name|reconcile|bundle|assemble`). Claude reads back through the Drive connector, and writes directly in the cloud. Every other specialist hands its output here: the Librarian is the only writer (rule 1).

**Owns.**
- The fixed tree: `00_START-HERE` to `06_Reference`, and `99_Archive`. Nothing at the root; depth 4 or less (rule 2).
- `00_START-HERE/INDEX.csv`: exactly one row per file, with its SHA-256 and source (rule 4).
- Numbered-part backups under the Drive connector's 100 MB cap (`engine.library.bundle()`, `engine.library.assemble()`).

**Lint before acting: `engine.library.file_plan()`.** The name follows the one pattern, lowercase ASCII and hyphens (rule 3); the path is inside the fixed tree (`engine.library.name_errors()`, `engine.library.folder_errors()`); bytes already filed link the existing copy instead; a filed path is never overwritten (rule 5); the index row is prepared.

**Measured check after acting: `engine.library.reconcile()`.** The Drive readback against INDEX.csv: zero files outside the tree, zero orphans, zero duplicates and zero misnamed files, or `engine.library.hold()` puts a LIBRARY hold at the top of the report. `assemble()` re-hashes every downloaded backup part before it is trusted.

**Not built yet.** The Canva `Growth/` mirror reconcile (rule 8), and the `source: <path>@<commit>` stamp check on Drive copies of public docs (rule 9).

**Never.** Delete or overwrite a file: a new version is a new `_v<n>`, and old ones move to `99_Archive` at week close. Change sharing or permissions. Write outside Growth Build. Write into `00_Brand-Assets`, which is read only.

| Situation | Decision |
|---|---|
| A misnamed file | Refused; rename to the pattern |
| The same bytes already filed | Link the existing copy |
| A stray folder or orphan | LIBRARY hold leads the report |
| A file over 100 MB | Bundle it in numbered parts |
| A rejected or old version | Move it to `99_Archive/<week>/` |

**Lens.** `crew/librarian/lens.md`.
