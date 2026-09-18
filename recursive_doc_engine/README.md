# Recursive DOC / KE_BLOCK kernel

This bounded kernel turns the earlier GAN-style document metaphor into an auditable round-trip:

```text
MASTER(DOC/MD text)
   |
   v
parse_master
   |
   v
KE_BLOCKS[] -- per-block sequence + SHA-256
   |
   v
rebuild_master
   |
   v
CANDIDATE + cd.json
   |
   v
CD gate -> CONTROL | IMPROVE
```

It is deliberately **not** a trained adversarial GAN. The generator/discriminator analogy is retained only as a design metaphor. The executable contract is deterministic document fidelity with nurturing feedback.

## Run

```bash
python -m recursive_doc_engine.engine README.md --out /tmp/ke-run
python -m recursive_doc_engine.cd_gate /tmp/ke-run --result /tmp/ke-run/cd_gate_result.json
python -m unittest recursive_doc_engine.tests.test_roundtrip -v
```

## Produced artefacts

| Artefact | Role |
|---|---|
| `ke_blocks.json` | ordered knowledge/execution blocks with hashes |
| `candidate.md` | reconstructed candidate |
| `cd.json` | candidate descriptor, metrics, feedback state |
| `cd_gate_result.json` | fail-closed promotion evidence |

## 3P* + MIP interpretation

- **3PR Refresh:** consume current repository authority before changing code.
- **3PR Probe:** distinguish metaphor from executable invariant.
- **3PR Rank:** first useful red = exact, traceable round-trip plus one objective CD gate.
- **MIP Modernize:** replace prose-only flow with runnable stdlib kernel.
- **MIP Innovate:** per-block hashes, tamper detection, nurturing feedback.
- **MIP Perpetuate:** tests, CI, control receipt and lossless handover.
- **3PC Prepare/Prove/Commit:** local tests + repository CI + PR lineage.

Authority transfer is false. Formal engineering/release credit delta is zero.
