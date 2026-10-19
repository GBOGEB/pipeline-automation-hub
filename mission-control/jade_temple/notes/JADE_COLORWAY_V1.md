# JADE Colorway V1 — visual convention (pilot)

- `N+3` is the *development iteration*, not a section. `J01–J08` are eight stable MIP work-package identities.
- `J08` is work package eight, **Bounded Execution and recursive stop rules**. The monogram now reads `JT` for JADE_TEMPLE; avoid `J8` because it suggests iteration eight.
- Dark mode describes a background and contrast choice. It **does not** equate to GoGREEN status. A temporary light-theme toggle changes presentation only and deliberately does not persist or alter evidence.
- Meaningful evidence colours: blue/cyan = source navigation & evidence, green/teal = **positive verified capability**, amber = pending or unknown, red/coral = first-red, blocked and failed, violet = MIP/DAG/execution.
- All eight cards have subtle individually assigned top-edge accents; their ID and text remain visible. Colour is **never the only status cue**.
- Status widgets preserve `PASS`, `FAIL`, `UNKNOWN`, `HOLD` and exact-head semantics. No status data are changed by theme selection.
- 1440x1000, 1280x800 and 390x844 Playwright checks required, including the theme switch, J08 selection and repo priority filters.
- `python mission-control/jade_temple/site/build_eightpoint.py --check` must pass after source changes. This colourway is a soft pilot, not a hard style gate.
