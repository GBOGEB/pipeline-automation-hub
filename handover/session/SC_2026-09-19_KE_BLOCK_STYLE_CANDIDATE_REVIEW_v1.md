# KE_BLOCK governed visual-style candidate — user review handover

The previously approved DOCX/PDF remains the immutable visual regression baseline.

A new style-only candidate is now proven and received across the repository chain:

- style: `QPS_TECH_GRAPHITE_TEAL_COPPER_V1`
- consumer merge: `GBOGEB/DOCX_RTM_Automation@78de18967bae343b68f6e757c610262b2b385112`
- exact render head: `92468c5fb9210144901729d5385c48cc858b1099`
- workflow: `35428885415`, job `105859678433`
- artifact: `sha256:c7483e4253f7ff746121897b3b51383fee3b095b7ee1793c5a54cad9c70cac7e`
- producer receipt: `GBOGEB/document-organization-system#71` -> `5bbfb27e6875c1d4db081bedc5bffeb93a922819`

Visual changes are tokenized rather than hard-coded: font names, Word-native 0.5 pt sizes, heading colors, special numbers, requirement IDs, metadata labels, captions, title-rule policy, spacing, margins, tables and callouts.

The candidate removes the last inherited standard-blue title rule. Semantic source and Markdown projection are unchanged from the accepted baseline. DOCX/PDF/PNG render, numbering, pagination, visual-style contract and independent visual QA all pass.

The next gate is **USER_STYLE_REVIEW**. No baseline replacement is claimed.
