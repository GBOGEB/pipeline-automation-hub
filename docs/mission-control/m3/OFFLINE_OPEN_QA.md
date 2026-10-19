# M3 owner-gated publication — download/open QA and recovery

**Scope:** GitHub-native exact-head offline review artifact, not an authorized GitHub Pages release.

## Reproduced failure and corrected entrypoint

On native [run 39063607003](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/39063607003), the artifact `m3-graph-contract-39063607003-1` exists, is nonexpired, and its ZIP integrity and published GitHub SHA-256 digest were confirmed. **The failure was at the delivery/open surface**, not missing upload bytes:

1. A direct GitHub REST `/actions/artifacts/<id>/zip` URL is an **authenticated API download endpoint** with redirects, not a reliable shareable browser link or HTML preview. Use [the workflow run's Artifacts section](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/39063607003) after signing in with repository access.
2. The old `site/docs/mission-control/m3/index.html` fetches adjacent `state.json` and `telemetry.json`. Double-clicking this page from an extracted ZIP opens `file://`; browser CORS/secure-context rules may block the fetch/digest. Run the extracted `site/` through local HTTP when using the multisite M2/M3 view.
3. The **new native artifact** contains top-level `M3_OPEN_ME_OFFLINE.html` with embedded, digest-bound source/telemetry and no network GETs. Extract the ZIP before opening; do **not** open HTML directly inside a ZIP preview.
4. An HTTP-served site or offline HTML is a source-controlled review rendition. Owner Pages approval, deployed URL, hosted-byte parity, security admission and QPS acceptance remain separately **UNKNOWN/WITHHELD**.

## UI navigation to download the reviewed artifact

1. Open the specific [M3 Actions workflow run](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/39063607003) on GitHub while signed in.
2. Under **Artifacts**, select `m3-graph-contract-39063607003-1` (the reviewed 17 Oct historical run) or the same-name-prefix artifact on the new exact-head workflow.
3. Extract the ZIP. For the current corrected release candidate, double-click `M3_OPEN_ME_OFFLINE.html` in the extracted root.
4. Alternative full M2/M3 site: from the extracted ZIP folder, run `py -m http.server 8000 --directory site` on Windows; navigate to `http://localhost:8000/docs/mission-control/m3/index.html`. Requires Python in PATH. Do not point a browser at `file:///.../site/docs/.../index.html`.

The browser screenshot package is a **separate** artifact named `m3-browser-qa-<run>-<attempt>`; screenshots cannot be opened by pasting the GitHub API /zip URL into a public browser without required authentication.

## Generated source, negative controls and qualification

- Generator: `mission-control/federation-atlas/m3_session/m3_offline_delivery.js`.
- Native build: `node .../m3_offline_delivery.js --site out/m3/site --sha <EXACT_40_HEX> --out out/m3/M3_OPEN_ME_OFFLINE.html`.
- Static/negative tests: `test_m3_offline_delivery.js` (forged state/telemetry hash, missing file, source authority, SHA integrity).
- Browser: `m3_offline_browser_qa.py` on the *same downloaded native job artifact* with all external requests blocked; desktop 1440, laptop 1280, mobile 390; graph/reload/navigation/overflow/console checks and screenshot digests.
- Artifact authority stays **READ_ONLY_NOT_PUBLISHED**. No auto Pages deployment, GitHub token in browser, worker launch, branch rule relaxation or independent approval created by these changes.

If the new native workflow is not terminal successful, the earlier manually verified standalone file remains **LOCAL_REPRODUCIBILITY** only, and current native release approval is HOLD.
