# PyCharm inspection findings: en-masse runbook

Method: classify → recurrence → one method per SYSTEMIC class → Kahn waves.
Classes and waves come from `inspection_triage.py`, which imports MAROON `hints.py` (GENERATED_RE,
PINNED_OID_RE, AUTHORITY) and `lifecycle.topo_layers` from the hub instead of copying them.

## What the 2026-11-17 export showed

* `index.html` (521 MB) is **truncated**: it stops mid-line inside Proofreading/Typo and `script.js`/`styles.css`
  were never written (C: was at 96 %). It holds 15 of the inspections; Python, YAML, Shell and the rest are missing.
  The header totals (3,689 errors, 7,045 warnings, 128,662 typos) are therefore not in the file.
* It inspected the **OneDrive working folder** (ABACUS checkout at `5f0dfebb1`, 1,634 dirty paths), not a clean clone.
* Of the 60k parsed findings: 68 % vendor (`.vscode/extensions`, `node-v24…`, `.venv`, `.AzureToolsForIntelliJ`),
  30 % in files git does not track, 1 % proofreading. **About 1,200 (2 %) are on tracked files**, of which 447 autofix,
  75 semi-auto (unresolved Markdown links), 9 real (EditorConfig overlap).

## W0: scope and profile (removes ~98 %)

Close PyCharm first (headless inspect refuses to run beside an open IDE using the same config).

```powershell
Set-Location "C:\repos\ABACUS"
git status --porcelain
git fetch origin
git switch --detach origin/main
$sha = git rev-parse HEAD
$out = "C:\repos\_cache\inspect\ABACUS_$($sha.Substring(0,9))"
New-Item -ItemType Directory -Force $out | Out-Null
& "C:\Users\gbonthuy\AppData\Local\Programs\PyCharm 2025.2.4\bin\inspect.bat" "C:\repos\ABACUS" "<this folder>\GBOGEB_Triage.xml" $out -v1 -format xml
```

* Clean clone at one SHA = vendor and untracked estate are simply not there (one pulse per snapshot).
* `GBOGEB_Triage.xml` switches off Typo / Grammar / language detection only; every other inspection keeps its default.
* XML output is one small file per inspection, not one 500 MB HTML page.

## W1: rerun baseline and classify

```powershell
Set-Location "C:\repos\ABACUS"
python "<this folder>\inspection_triage.py" --input $out --root "C:\repos\ABACUS" --out "$out\triage" --hub "C:\repos\pah_tools" --git-tracked --source-sha $sha
```

`C:\repos\pah_tools` already has `scripts` sparse-checked out; also add the two owner folders once:

```powershell
git -C "C:\repos\pah_tools" sparse-checkout add mission-control/maroon mission-control/jade_temple/devops
```

## W2: AUTOFIX (one branch, one concern)

```powershell
Set-Location "C:\repos\ABACUS"
git switch -c style/md-tables-lists origin/main
& "C:\Users\gbonthuy\AppData\Local\Programs\PyCharm 2025.2.4\bin\format.bat" -r -m "*.md" "C:\repos\ABACUS"
git diff --stat
```

Review the diff, commit, `git push -u origin HEAD`, draft PR. Re-run W1: table formatting and list numbering should be gone.
In the IDE the same thing is: right-click the folder ▸ Reformat Code, or Alt+Enter on one hit ▸ "Fix all … problems in file".

## W3: SEMI_AUTO (unresolved Markdown file / header links)

Resolve each broken link to the one canonical file by basename (ADR-0001: bind, don't copy). A link whose target
is gone is a decision, not a fix; list those for the owner.

## W4: DEFECT queue

Real findings (JSON errors, EditorConfig overlap, lossy encoding, and whatever the Python inspections add once the
export is complete) go to MAROON / the issue queue per finding. Every triage row is `DIAGNOSIS_HINT_NOT_CLOSURE_PROOF`.

## W5: fold-back

Each SYSTEMIC class gets one durable rule so it does not come back: the triage profile committed under
`.idea/inspectionProfiles/`, Markdown formatting in pre-commit, and the vendor folders excluded in `Master_Input.iml`.

## Housekeeping

`Master_Input\index.html` (521 MB) sits untracked inside the OneDrive ABACUS checkout. Move it to `C:\repos\_cache`
or delete it once the clean run exists.
