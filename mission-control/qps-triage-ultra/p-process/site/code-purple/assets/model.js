// Code Purple model: nodes, edges, stages, lifecycle triggers and recorded telemetry.
// Single source for index.html (assets/app.js), build_deck.js and tools/check_model.ts.
// Types: ../types/code-purple-model.d.ts
(function (root) {
"use strict";
const PH={D:"Define",M:"Measure",A:"Analyse",I:"Improve",C:"Control"};
const KIND={auth:"Authority",proc:"Process",dec:"Gate",rep:"Repair",pass:"Admitted path",hold:"Hold",evid:"Evidence store"};
const LANE={spine:"Admission spine",ev:"Evidence · hold",rep:"Repair loop"};
const STATUS={ok:"Seeded / committed",progress:"In progress",hold:"On hold",partial:"Partial",todo:"Not implemented",none:"Not reached"};
const EKIND={flow:"Sequence",yes:"Pass",fail:"Material red",hold:"Hold",evid:"Evidence",rec:".self recursion"};

const NODES=[
 {id:"N01",label:"Mission controller",sub:["global input N · GLOB census"],kind:"auth",phase:"D",lane:"spine",x:380,y:70,w:280,h:60,status:"ok",
  owner:"Global lookup · Dock interface",artefact:"CODEX GLOB.yaml, .mesh/MESH_DOCK.yaml",does:"Takes global input N, discovers authorities and capabilities, and resolves producer, consumer, receipts and scope for this pulse.",evidence:"Census snapshot",state:"Seed contract committed in PR #984. Controller not yet executed as code.",
  actions:["Receive trigger: new head, schedule or material change","Load GLOB.yaml census","Read MESH_DOCK producer and consumer map","Open iteration N record"]},
 {id:"N02",label:"Asymmetric allocation",sub:["pin SHA · budget by cost of a red"],kind:"auth",phase:"D",lane:"spine",x:380,y:160,w:280,h:60,status:"ok",
  owner:"Mission controller",artefact:"Seed YAML execution contract",does:"Pins the exact head under test and spends compute where a red is most expensive. Cheap I/O runs async; costly checks get dedicated lanes.",evidence:"Pinned SHA pair, lane budget",state:"CODEX main@4da26fdf → PR head ea37fa15.",
  actions:["Pin base and head SHA","Score lanes by cost of a red","Assign async and dedicated lanes","Write lane budget"]},
 {id:"N03",label:"Async I/O",sub:["evidence collection"],kind:"proc",phase:"M",lane:"ev",x:110,y:250,w:210,h:60,status:"todo",
  owner:"Semantic and provenance",artefact:"REX and KEB lookups, GitHub check readback",does:"Collects existing evidence without blocking the workers, including prior receipts that may already prove a result.",evidence:"Evidence bundle",state:"Not implemented.",
  actions:["Query REX and KEB for prior receipts","Read back GitHub check states","Fetch runner status","Assemble evidence bundle"]},
 {id:"N04",label:"Parallel worker lanes",sub:["independent · no shared state"],kind:"proc",phase:"M",lane:"spine",x:380,y:250,w:280,h:120,status:"partial",chips:["parse","ruff","sarif","smoke"],note:"local result ≠ GitHub check",
  owner:"Runtime self-test · Lint · Security",artefact:"ABACUS scripts/testpilot_preflight.py, pre-commit, Ruff, Bandit, Semgrep",does:"Runs parse, Ruff, SARIF security scans and smoke in parallel with no shared state.",evidence:"Per-lane JSON and SARIF",state:"Tools exist; not yet run as a .self harness. A local pass never counts as a GitHub check.",
  actions:["Parse YAML, JSON and TOML","Ruff lint","Bandit and Semgrep to SARIF","Smoke test","Write per-lane result"]},
 {id:"N05",label:"Preflight + pre-match cache",sub:["reuse exact-match results"],kind:"proc",phase:"M",lane:"spine",x:380,y:400,w:280,h:60,status:"todo",receipt:true,
  owner:"Runtime self-test",artefact:"Receipts keyed by exact commit and input hash",does:"Merges worker output with collected evidence. A result already proven for the identical commit and inputs is reused instead of rerun.",evidence:"Preflight receipt",state:"Not implemented. Cache hits must match the exact SHA, never a near match.",
  actions:["Hash commit and inputs","Match cached receipts","Run the unmatched remainder","Write preflight receipt"]},
 {id:"N06",label:"First completed material red?",lines:["First completed","material red?"],kind:"dec",phase:"A",lane:"spine",shape:"diamond",cx:520,cy:540,hw:130,hh:50,status:"todo",
  owner:"Derived analysis",artefact:"ABACUS DOW",does:"Ranks findings and selects the first completed red that matters, classified as source defect, inherited debt, review capacity or runner failure.",evidence:"Ranked disposition",state:"Reds on ABACUS #1856, #1857 and #1859 not yet classified.",
  actions:["Rank findings with DOW","Assign a failure class","Select the first completed material red"]},
 {id:"N07",label:"Isolated repair",sub:["smallest common cause"],kind:"rep",phase:"I",lane:"rep",x:720,y:510,w:240,h:60,status:"todo",
  owner:"Owning repository",artefact:"Smallest-scope branch",does:"Fixes the smallest common cause only. Security-sensitive governance changes cannot approve themselves.",evidence:"Commit",state:"Waiting on classification.",
  actions:["Branch from the exact head","Apply the smallest fix","Confirm no governance self-approval"]},
 {id:"N08",label:"Impacted retest",sub:["+ new exact-commit receipt"],kind:"rep",phase:"I",lane:"rep",x:720,y:620,w:240,h:60,status:"todo",receipt:true,
  owner:"Runtime self-test",artefact:"Impacted test set",does:"Reruns only what the repair touches and writes a new exact-commit receipt.",evidence:"Exact-commit receipt",state:"Not started.",
  actions:["Select impacted tests","Rerun them","Write exact-commit receipt"]},
 {id:"N09",label:"Exact-head final admission",sub:["CI · Codex review · PR Feedback Gate"],kind:"proc",phase:"C",lane:"spine",x:380,y:630,w:280,h:70,ty:28,status:"progress",receipt:true,
  owner:"Delivery",artefact:"GitHub Actions, PR Feedback Gate, Codex review and security review",does:"Independent verification on the exact head SHA, including required reviews.",evidence:"Check records, review states",state:"#984: 49 check records; 2 pass, Ruff neutral, the rest pending at first readback.",
  actions:["Trigger exact-head CI","Codex review","Security review","PR Feedback Gate"]},
 {id:"N10",label:"All non-waivable gates green?",lines:["All non-waivable","gates green?"],kind:"dec",phase:"C",lane:"spine",shape:"diamond",cx:520,cy:780,hw:140,hh:45,status:"hold",
  owner:"Delivery · QPS domain",artefact:"Required checks and reviews at exact head",does:"Admits only when every non-waivable check and review is green on the same SHA. Waivable checks are recorded, not counted.",evidence:"Admission decision",state:"HOLD for #984. 0 ABACUS PRs ready to merge.",
  actions:["Collect non-waivable gate states","Record waivable checks separately","Admit or hold"]},
 {id:"N11",label:"HOLD",sub:["log · REX · next pulse"],kind:"hold",phase:"C",lane:"ev",x:110,y:750,w:210,h:60,status:"hold",
  owner:"Semantic and provenance",artefact:"REX entry",does:"Logs the blocking reason to REX and plans the next pulse. A material change re-enters at the mission controller.",evidence:"Hold record",state:"#984 held pending checks. #1858 held pending independent, owner-controlled admission (P0).",
  actions:["Record the blocking reason","Write REX entry","Schedule the next pulse"]},
 {id:"N12",label:"REX · KEB evidence",sub:["receipt identity","recurrence · lessons"],kind:"evid",phase:"C",lane:"ev",x:110,y:400,w:210,h:120,ty:46,status:"partial",
  owner:"Semantic and provenance",artefact:"CODEX KEB and REX",does:"Holds evidence identity, recurrence counts and reusable lessons. Async I/O reads from it at the start of each pulse.",evidence:"Lessons, recurrence",state:"REX exists; capture starts once the controls actually execute.",
  actions:["Store receipt identity","Increment recurrence","Publish lesson"]},
 {id:"N13",label:"Single-flight merge controller",sub:["one admitted PR at a time"],kind:"pass",phase:"C",lane:"spine",x:380,y:860,w:280,h:56,status:"none",
  owner:"Delivery",artefact:"Merge queue discipline",does:"Merges one admitted PR at a time so no head goes stale behind another merge.",evidence:"Merge commit",state:"Nothing admitted yet.",
  actions:["Acquire merge lock","Confirm head unchanged","Merge one PR","Release lock"]},
 {id:"N14",label:"Exact-main CI · metrics",sub:["publication readback · Pages"],kind:"pass",phase:"C",lane:"spine",x:380,y:946,w:280,h:56,status:"none",receipt:true,
  owner:"Delivery",artefact:"GitHub Actions on main, Pages",does:"Proves main is green after the merge, records metrics and reads the published result back.",evidence:"Post-merge receipt",state:"Not reached.",
  actions:["Run exact-main CI","Record metrics","Publish to Pages","Read back the publication"]},
 {id:"N15",label:"Output N · control",sub:["becomes input N+1 via ⊕"],kind:"auth",phase:"C",lane:"spine",x:380,y:1032,w:280,h:56,status:"none",
  owner:"All lanes",artefact:"Iteration census",does:"Becomes the input of iteration N+1 through governed reconciliation (⊕).",evidence:"Census row",state:"Not reached.",
  actions:["Write census row","Reconcile O_N ⊕ ΔE_N ⊕ C_N+1","Emit input N+1"]}
];
const EDGES=[
 {id:"E01",f:"N01",t:"N02",k:"flow",d:"M520,130 L520,158",m:"Every pulse starts at the controller."},
 {id:"E02",f:"N02",t:"N04",k:"flow",d:"M520,220 L520,248",m:"Costly checks get dedicated lanes."},
 {id:"E03",f:"N02",t:"N03",k:"flow",d:"M380,190 L215,190 L215,248",lab:["async · cheap"],lx:295,ly:189.5,m:"Cheap I/O runs without blocking the workers."},
 {id:"E04",f:"N04",t:"N05",k:"flow",d:"M520,370 L520,398",m:"Per-lane JSON and SARIF results."},
 {id:"E05",f:"N03",t:"N05",k:"evid",d:"M320,280 L350,280 L350,430 L378,430",lab:["pre-match"],lx:323,ly:354.5,m:"Prior receipts offered for exact-match reuse."},
 {id:"E06",f:"N05",t:"N06",k:"flow",d:"M520,460 L520,488",m:"Merged preflight result."},
 {id:"E07",f:"N06",t:"N07",k:"fail",d:"M650,540 L718,540",lab:["yes"],lx:685,ly:528.5,m:"A completed material red exists."},
 {id:"E08",f:"N07",t:"N08",k:"fail",d:"M840,570 L840,618",m:"Repair committed on an isolated branch."},
 {id:"E09",f:"N08",t:"N09",k:"flow",d:"M720,658 L662,658",lab:["verify"],lx:690,ly:638.5,m:"Retest receipt goes to exact-head verification."},
 {id:"E10",f:"N06",t:"N09",k:"yes",d:"M520,590 L520,628",lab:["no red"],lx:560,ly:608.5,m:"No material red among completed checks."},
 {id:"E11",f:"N09",t:"N10",k:"flow",d:"M520,700 L520,733",m:"Check and review states on the exact head."},
 {id:"E12",f:"N10",t:"N11",k:"hold",d:"M380,780 L322,780",lab:["no"],lx:350,ly:766.5,m:"A non-waivable gate is red or pending."},
 {id:"E13",f:"N10",t:"N13",k:"yes",d:"M520,825 L520,858",lab:["yes"],lx:549,ly:842.5,m:"Every non-waivable gate is green on the same SHA."},
 {id:"E14",f:"N13",t:"N14",k:"yes",d:"M520,916 L520,944",m:"One PR merged at a time."},
 {id:"E15",f:"N14",t:"N15",k:"yes",d:"M520,1002 L520,1030",m:"Main green; metrics and publication read back."},
 {id:"E16",f:"N11",t:"N12",k:"evid",d:"M215,750 L215,522",lab:["hold record"],lx:215,ly:630.5,m:"Blocking reason recorded."},
 {id:"E17",f:"N12",t:"N03",k:"evid",d:"M215,400 L215,312",lab:["reuse proven","evidence"],lx:215,ly:357,m:"Lessons and receipts reused in the next pulse."},
 {id:"E18",f:"N11",t:"N01",k:"hold",d:"M110,780 L70,780 L70,100 L378,100",lab:["material change","→ next pulse"],lx:70,ly:613,m:"A material change triggers the next pulse."},
 {id:"E19",f:"N15",t:"N01",k:"rec",d:"M660,1060 L990,1060 L990,90 L662,90",lab:[".self · validated input N → N+1"],lx:990,ly:600,rot:-90,m:"Validated output becomes input N+1 through ⊕."}
];
const STAGES=[
 {n:1,name:"Mobilise",ph:"D",nodes:["N01","N02"],entry:["A trigger: new head, schedule or material change"],acts:["Census authorities and capabilities","Pin the exact SHA","Budget lanes by the cost of a red"],exit:["Pinned SHA pair","Lane budget"]},
 {n:2,name:"Collect and run",ph:"M",nodes:["N03","N04"],entry:["SHA pinned, lanes budgeted"],acts:["Collect prior evidence asynchronously from REX, KEB and GitHub","Run parse, Ruff, SARIF and smoke lanes in parallel"],exit:["Evidence bundle","Per-lane results"]},
 {n:3,name:"Pre-match",ph:"M",nodes:["N05"],entry:["Lane results and evidence bundle"],acts:["Reuse results proven for the identical commit and inputs","Run only the remainder"],exit:["Preflight receipt (local, not CI proof)"]},
 {n:4,name:"Triage",ph:"A",nodes:["N06"],entry:["Preflight receipt"],acts:["Rank findings with DOW","Assign one of four failure classes","Select the first completed material red"],exit:["One red to repair, or none"]},
 {n:5,name:"Repair loop",ph:"I",nodes:["N07","N08"],entry:["One classified red"],acts:["Fix the smallest common cause on an isolated branch","Retest the impacted set","Write a new exact-commit receipt"],exit:["Repaired head submitted for verification"]},
 {n:6,name:"Admission",ph:"C",nodes:["N09","N10"],entry:["Exact head with no known material red"],acts:["Run CI, Codex review and PR Feedback Gate on the exact SHA","Evaluate non-waivable gates only"],exit:["Admit, or hold"]},
 {n:7,name:"Hold and learn",ph:"C",nodes:["N11","N12"],entry:["A non-waivable gate red or pending"],acts:["Record the reason in REX","Update recurrence and lessons","Plan the next pulse"],exit:["Hold record","Next pulse on material change"]},
 {n:8,name:"Merge and prove",ph:"C",nodes:["N13","N14","N15"],entry:["Admission green"],acts:["Merge one PR at a time","Run exact-main CI, record metrics, read back the publication","Write the census row"],exit:["Output N becomes input N+1"]}
];


/* ================= LIFECYCLE ================= */
const LSTATES=[
 {id:"PENDING",label:"Test pending",sub:"new head",k:"hold",x:20,y:90},
 {id:"SETUP",label:"Set-up",sub:"preconfig",k:"proc",x:175,y:90},
 {id:"RUN",label:"Run lanes",sub:"#1856 #1857 #1859 red",k:"proc",x:330,y:90},
 {id:"RETRY",label:"Retry",sub:"infra red, once",k:"proc",x:330,y:8},
 {id:"DEBUG",label:"Debug",sub:"debug lanes on",k:"rep",x:330,y:250},
 {id:"FIX",label:"Fix",sub:"isolated branch",k:"rep",x:175,y:250},
 {id:"INTEGRATE",label:"Integrate",sub:"push to PR head",k:"rep",x:20,y:250},
 {id:"ADMIT",label:"Admission",sub:"exact-head gate",k:"dec",x:520,y:90},
 {id:"FOLLOW",label:"PR follow-up",sub:"threads · reviews",k:"hold",x:520,y:250},
 {id:"HOLD",label:"HOLD",sub:"#1858 here",k:"hold",x:680,y:250},
 {id:"MERGED",label:"Merged",sub:"#984 here",k:"pass",x:680,y:90},
 {id:"FED",label:"Federate",sub:"adopt in peer repo",k:"auth",x:840,y:90}
];
const TRIGGERS=[
 {id:"T01",f:"PENDING",t:"SETUP",k:"flow",d:"M150,113 L173,113",ev:"Pull request opened or synchronised, or a push",guard:"Head SHA pinned",act:"Start CI; mark the gate pending",nodes:["N01","N02"],w:"partial",wn:"GitHub starts CI on these events. ABACUS's gate re-evaluates on workflow_run and review events, not on synchronize (#1858 thread, line 599)."},
 {id:"T02",f:"SETUP",t:"RUN",k:"flow",d:"M305,113 L328,113",ev:"Preconfig receipt written",guard:"Python runtime, dependencies and devcontainer resolved",act:"Start the parallel lanes",nodes:["N03","N04"],w:"proposed",wn:"Needs the .self harness."},
 {id:"T03",f:"RUN",t:"RETRY",k:"hold",d:"M375,88 L375,50",lab:"infra red",lx:340,ly:69,ev:"A lane goes red with class runner or infrastructure (5xx, runner lost, cancelled)",guard:"No earlier retry on this SHA",act:"Re-run the failed jobs once; log a REX entry",nodes:["N05","N06"],w:"manual",wn:"Re-run all jobs button on GitHub."},
 {id:"T03b",f:"RETRY",t:"RUN",k:"flow",d:"M440,50 L440,88",lab:"done",lx:478,ly:69,ev:"Retry finished",guard:"—",act:"Results re-enter triage",nodes:["N06"],w:"manual",wn:"Same re-run."},
 {id:"T04",f:"RUN",t:"DEBUG",k:"fail",d:"M395,136 L395,248",lab:"defect red",lx:395,ly:192,ev:"Red classified as a source defect that doesn't reproduce locally",guard:"It is the first completed material red",act:"Re-run that lane with debug on (debugpy, LLDB) and keep the trace",nodes:["N06"],w:"partial",wn:"CODEX main already runs LLDB, lldb-dap and debugpy lanes (green); nothing triggers them from a red yet."},
 {id:"T05",f:"DEBUG",t:"FIX",k:"fail",d:"M330,273 L307,273",ev:"Root cause recorded",guard:"Fix scope is the smallest common cause",act:"Branch from the exact head",nodes:["N07"],w:"manual",wn:"—"},
 {id:"T06",f:"FIX",t:"INTEGRATE",k:"fail",d:"M175,273 L152,273",ev:"Impacted retest green, with an exact-commit receipt",guard:"No governance change approves itself",act:"Push to the PR head",nodes:["N08"],w:"manual",wn:"—"},
 {id:"T07",f:"INTEGRATE",t:"PENDING",k:"flow",d:"M85,248 L85,138",lab:"new head",lx:85,ly:192,ev:"New head on the PR",guard:"—",act:"Old receipts retired; the cycle restarts at T01",nodes:["N01"],w:"wired",wn:"Push event."},
 {id:"T08",f:"RUN",t:"ADMIT",k:"yes",d:"M460,113 L518,113",lab:"no red",lx:489,ly:100,ev:"All lanes terminal",guard:"No material red",act:"Exact-head CI plus Codex code and security review",nodes:["N09"],w:"partial",wn:"CI is automatic. The Codex review request is manual, and the allowance is exhausted."},
 {id:"T09",f:"ADMIT",t:"FOLLOW",k:"hold",d:"M570,136 L570,248",lab:"thread",lx:570,ly:192,ev:"Review thread, Codex comment or gate failure",guard:"—",act:"Answer, fix, or record an owner residual-risk decision",nodes:["N09","N11"],w:"partial",wn:"Detection is wired: pr-feedback-gate.yml runs on pull_request_review and review-comment events. The response is manual."},
 {id:"T10",f:"FOLLOW",t:"ADMIT",k:"flow",d:"M610,248 L610,138",ev:"Thread resolved or review submitted",guard:"Zero unresolved threads",act:"The gate re-evaluates",nodes:["N10"],w:"wired",wn:"Review events trigger the gate."},
 {id:"T11",f:"ADMIT",t:"HOLD",k:"hold",d:"M650,125 L700,248",lab:"gate red",lx:690,ly:180,ev:"A non-waivable gate is red or pending (e.g. Codex outage)",guard:"—",act:"Write the HOLD record and a REX entry",nodes:["N10","N11","N12"],w:"partial",wn:"The gate holds. The REX record is manual."},
 {id:"T12",f:"HOLD",t:"PENDING",k:"hold",d:"M745,296 L745,318 L10,318 L10,113 L18,113",lab:"scheduled readback · material change",lx:380,ly:318,ev:"Scheduled readback, or a material change",guard:"Something changed since the last pulse",act:"Start a new pulse",nodes:["N11","N01"],w:"proposed",wn:"Needs a scheduled task (burndown item 7)."},
 {id:"T13",f:"HOLD",t:"MERGED",k:"hold",d:"M770,248 L770,138",lab:"break-glass",lx:785,ly:192,ev:"Owner decision with a written residual risk",guard:"Owner only. One-time ruleset bypass, restored straight after the merge",act:"Squash-merge, restore the ruleset, write REX",nodes:["N10","N13"],w:"manual",wn:"Owner edits ruleset 24494381. This is the proposed path for #1858."},
 {id:"T14",f:"ADMIT",t:"MERGED",k:"yes",d:"M650,113 L678,113",ev:"All non-waivable gates green on the same SHA",guard:"Single-flight: no other merge in progress",act:"Squash-merge",nodes:["N13"],w:"partial",wn:"ABACUS: ruleset enforces it. CODEX: no ruleset; #984 merged with 4 reds."},
 {id:"T15",f:"MERGED",t:"FED",k:"rec",d:"M810,113 L838,113",ev:"Exact-main CI green and read back",guard:"Consumer listed in MESH_DOCK",act:"Open an adoption PR in the peer repo; write the census row",nodes:["N14","N15"],w:"proposed",wn:"Not built. For #984, CODEX main has 2 post-merge reds to clear first."},
 {id:"T16",f:"MERGED",t:"MERGED",k:"yes",d:"M705,90 C705,50 785,50 785,88",lab:"floor ratchet",lx:745,ly:54,ev:"Exact-main CI measures coverage at or above floor + 1 point",guard:"Exact-main CI green; measurement on the same SHA",act:"Raise the coverage floor to the measured value; write the census row (total, breadth, depth, per area)",nodes:["N14","N12"],w:"proposed",wn:"Not built. Today the gate is a fixed 75% and fails on every PR."}
];
const WIRED={wired:"Wired",partial:"Partly wired",manual:"Manual",proposed:"Proposed"};
const TEL_RECORDED={schema:"code-purple.census/v1",source:"recorded",iteration:0,generated_at:"2026-10-12T15:16:00Z (GitHub API readback)",
 vcs:{repo:"GBOGEB/CODEX · GBOGEB/ABACUS",branch:"#984 merged · #1858 fix/gate-owner-attestation-fallback",head:"ABACUS #1858 203d63aff64b9d6b4c69dec0a1d3f5cf3f1f8bf1",base:"CODEX main 6edf28b7 · ABACUS main 53688f26 (#1838, 2026-10-06)",dirty:null},
 runtime:{python:"3.10 · 3.11 · 3.12 (ABACUS CI matrix, all green on #1858)",implementation:"CPython (GitHub-hosted runners)",platform:"ubuntu-24.04",container:"not reported",debug:"CODEX main: LLDB, lldb-dap + MCP, debugpy + js-debug lanes green"},
 rex:[],
 nodes:{
  N01:{preconfig:{stage:"pass",test:"none",debug:null},logs:[{ts:"10-12 12:16",level:"INFO",msg:"Code Purple execution seed merged to CODEX main via #984 (12 commits)"}]},
  N02:{logs:[{ts:"10-12 17:01",level:"INFO",msg:"Pinned heads: ABACUS #1858 10fdaaa5; CODEX main 6edf28b7"}]},
  N04:{preconfig:{stage:"pass",test:"pass",debug:"on"},
   runs:[{name:"ABACUS Python 3.10–3.12 matrix (#1858)",attempts:3,pass:3},{name:"Ruff security, Semgrep, CodeQL, OSV (#1858)",attempts:6,pass:6},{name:"smoke, measured-pulse, real-api-runtime (#1858)",attempts:3,pass:3},{name:"CODEX main debug lanes (LLDB, debugpy)",attempts:3,pass:3}]},
  N09:{preconfig:{stage:"pass",test:"pass",debug:null},
   runs:[{name:"ABACUS #1858 head checks (203d63af)",attempts:96,pass:89,fail:6,neutral:1},{name:"CODEX #984 merge-head checks",attempts:59,pass:55,fail:4}],
   errors:[{ts:"10-12 12:09",code:"CODEX-984",msg:"ruff, governance-gate ×2 and validate failed on merge head 90e3396a"},{ts:"10-12 16:56",code:"GATE-1858",msg:"PR Feedback Gate failure: 2 unresolved threads; Codex code and security review pending"},{ts:"10-12 17:14",code:"PUSH-203d63af",msg:"New head (workflow_policy.json +1): Code Coverage, Code Quality, Full Red Proof, Security Scanning, policy-and-inventory red"}],
   logs:[{ts:"10-12 16:56",level:"ERROR",msg:"ABACUS #1858 PR Feedback Gate: state=failure, ci_seen=15"},{ts:"10-12 12:09",level:"ERROR",msg:"CODEX #984: 4 failing checks on head 90e3396a"},{ts:"10-12 13:11",level:"INFO",msg:"ABACUS #1858: 3 duplicate gate evaluations cancelled, 1 succeeded"}]},
  N10:{runs:[{name:"ABACUS required gate (#1858)",attempts:1,fail:1}],
   errors:[{ts:"10-12 12:16",code:"NO-GATE",msg:"CODEX main has no required-check ruleset; #984 merged without a green admission"}],
   logs:[{ts:"10-12 16:56",level:"WARN",msg:"ABACUS gate runs main's code; #1858's own fallback cannot admit #1858 (no self-approval)"},{ts:"10-12 12:16",level:"WARN",msg:"CODEX #984 merged with red checks: admission step bypassed"}]},
  N11:{logs:[{ts:"10-12 13:10",level:"WARN",msg:"#1858 threads L599 and outage correlation: owner residual-risk replies, unresolved"},{ts:"10-12 17:01",level:"WARN",msg:"Nothing merged to ABACUS main since #1838 (2026-10-06)"}]},
  N13:{runs:[{name:"CODEX #984 squash merge",attempts:1,pass:1}]},
  N14:{runs:[{name:"CODEX main 768c9e35 post-merge CI",attempts:40,pass:38,fail:2},{name:"CODEX main 6edf28b7 (current)",attempts:9,pass:9}],
   errors:[{ts:"10-12 12:20",code:"MAIN-768c9e35",msg:"validate and scheduled osv-scan failed after the #984 merge; not rerun on later heads"}]}
 }};
const TEL_EXAMPLE={schema:"code-purple.census/v1",source:"example",iteration:3,generated_at:"2026-10-12T11:40:00+02:00",
 vcs:{repo:"GBOGEB/CODEX",branch:"code-purple/global-self-preflight-20261012",head:"ea37fa15ca1a9ccd504ca164204b8adabaf08837",base:"main@4da26fdf",dirty:false},
 runtime:{python:"3.11.9",implementation:"CPython",platform:"linux-x86_64",container:"devcontainer (example)",debug:"off"},
 rex:[{id:"REX-EX-007",node:"N03",title:"Retry check-runs readback on 5xx before declaring a red",recurrence:3},
      {id:"REX-EX-011",node:"N04",title:"A configured port is not a listening port",recurrence:2},
      {id:"REX-EX-014",node:"N10",title:"Neutral checks never count as green",recurrence:1}],
 nodes:{
  N01:{preconfig:{stage:"pass",test:"pass",debug:"off"},runs:[{name:"census load",attempts:3,pass:3,ms:820}],logs:[{ts:"11:02:10",level:"INFO",msg:"GLOB census loaded: 14 authorities, 9 lanes"}]},
  N02:{preconfig:{stage:"pass",test:"pass",debug:"off"},runs:[{name:"SHA pin",attempts:3,pass:3,ms:140},{name:"lane budget",attempts:3,pass:3,ms:95}]},
  N03:{preconfig:{stage:"pass",test:"pending",debug:"on"},runtime:{python:"3.12.4"},runs:[{name:"REX lookup",attempts:3,pass:3,ms:410},{name:"GitHub readback",attempts:6,pass:4,fail:2,ms:2300}],
   errors:[{ts:"11:05:31",code:"HTTP-502",msg:"Check-runs API returned 502; retried",rex:"REX-EX-007"}],
   logs:[{ts:"11:05:31",level:"ERROR",msg:"Check-runs readback failed (502)"},{ts:"11:05:44",level:"DEBUG",msg:"Retry 1/3 succeeded after 13 s"}]},
  N04:{preconfig:{stage:"pass",test:"pass",debug:"off"},runtime:{python:"3.11.9"},
   runs:[{name:"parse",attempts:3,pass:3,ms:900},{name:"ruff",attempts:3,pass:2,fail:1,ms:1800},{name:"bandit",attempts:3,pass:3,ms:5200},{name:"semgrep",attempts:3,pass:2,neutral:1,ms:21000},{name:"smoke",attempts:3,pass:1,fail:2,ms:14000}],
   errors:[{ts:"11:09:12",code:"RUF100",msg:"Unused noqa directive in federation/mesh/loader.py:41"},{ts:"11:10:03",code:"SMOKE-PORT",msg:"Port 8080 configured but not listening",rex:"REX-EX-011"}],
   logs:[{ts:"11:08:40",level:"INFO",msg:"5 lanes started"},{ts:"11:10:03",level:"ERROR",msg:"smoke: connection refused on :8080"}]},
  N05:{preconfig:{stage:"pass",test:"pass",debug:"off"},runs:[{name:"cache match",attempts:3,pass:3,ms:60},{name:"remainder run",attempts:3,pass:2,fail:1,ms:9000}],logs:[{ts:"11:11:20",level:"INFO",msg:"Pre-match reused 3 of 5 lane receipts"}]},
  N06:{preconfig:{stage:"pass",test:"pass",debug:"off"},runs:[{name:"DOW rank",attempts:3,pass:3,ms:300}],logs:[{ts:"11:11:41",level:"WARN",msg:"First material red: smoke (runner or infrastructure)"}]},
  N07:{preconfig:{stage:"pass",test:"none",debug:"off"},runs:[{name:"repair",attempts:2,pass:1,fail:1}]},
  N08:{preconfig:{stage:"pass",test:"pass",debug:"trace"},runs:[{name:"impacted retest",attempts:2,pass:1,fail:1,ms:12000}]},
  N09:{preconfig:{stage:"pass",test:"pending",debug:"off"},runs:[{name:"exact-head CI",attempts:2,pass:1,pending:1},{name:"Codex review",attempts:1,pending:1}]},
  N10:{runs:[{name:"gate evaluation",attempts:2,fail:1,pending:1}],logs:[{ts:"11:30:02",level:"WARN",msg:"HOLD: Codex review pending"}]},
  N11:{runs:[{name:"hold record",attempts:2,pass:2}],logs:[{ts:"11:30:03",level:"INFO",msg:"Next pulse scheduled on material change"}]},
  N12:{runs:[{name:"lesson write",attempts:4,pass:4}]}
 }};
const CP_MODEL = Object.freeze({PH,KIND,LANE,STATUS,EKIND,NODES,EDGES,STAGES,LSTATES,TRIGGERS,WIRED,TEL_RECORDED,TEL_EXAMPLE});
if (typeof module === 'object' && module.exports) module.exports = CP_MODEL;
root.CP_MODEL = CP_MODEL;
})(typeof globalThis !== 'undefined' ? globalThis : this);
