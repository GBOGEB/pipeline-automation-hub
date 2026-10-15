# Hosted publication — **NOT enabled in Wave 1 or Wave 2**

The current `GBOGEB/pipeline-automation-hub` default branch `master` was observed unprotected. The G4 method atlas currently uploads GitHub Actions artifacts; it does **not** itself publish GitHub Pages. No `gh-pages` branch was found at the last readback. A public Pages candidate URL is therefore **not proof of deployment**.

Recommended owner-approved future W3 transaction (not executed here):

1. Land the source/renderer in a governed PR, after security/review/Code Purple checks. Keep `permissions: contents: read` on test/render jobs.
2. Reconcile working one-owner review/override policy **without silently replacing failed required checks with fake success**. Configure meaningful branch ruleset/required context on `master` and record authorized exceptions as explicit carry-over, not green.
3. On terminal successful exact-main run, use `actions/upload-pages-artifact@v3` and a distinct `deploy-pages` job with `environment: github-pages`, `pages: write` and `id-token: write`. Owner enables Pages source = GitHub Actions and deploy environment protection.
4. Deploy only sanitized static render files and their provenance manifest; never expose corporate restricted inputs, GitHub tokens, company non-public documents or local user review notes.
5. Fetch hosted `/index.html` and `/manifest.json` via independent HTTP reader, compare semantic source hash and published content digest against the exact-main artifact. Record site URL, run, SHA, timestamp and content hashes in the wave receipt. Until confirmed, display `HOSTED_UNKNOWN`.
6. Trigger recensus on any source/policy/renderer/dataset revision. Do not reissue original Office/PDF files without corporate controlled-document version and owner acceptance.

A protection ruleset, a pages deploy job and a rendered green HTML are **three different proofs**; they do not substitute for each other.