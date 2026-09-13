---
layout: qps
title: QPS Triage Evidence Atlas
---

This static surface publishes governed MissionControl evidence. It does not own operational state.

![QPS web architecture](assets/diagrams/qps-web-architecture.svg)

## Fleet

Grand Mission and Horizontal Mission state, launch/hold boundaries, and federation returns.

## Topology

Breadth (Geographer), depth (Geologist), and penetration `PEN = breadth × depth`, including parent/child structure.

## Crew

Crew registry, competency vectors, home base, secondment, runtime receipts, REX learned/generated, load, and CONTROL eligibility.

## Execution

Active, queued, blocked, and deferred work with queue-time versus execute-time telemetry.

## REX

Global and mission-local lessons, recurrence prevention, repair routing, and promotion into CONTROL rules.

## Historian

Commit history, PR history, PR lineage, mission genealogy, and evidence SHA lineage.

## Evidence economics

Crew-time, queue-time, execution-time, information gain, disposition yield, and evidence cost by frontier.

## PCA / BT

Measured telemetry features for PCA and observed pairwise evidence for Bradley–Terry reverse-pressure ranking.

## Publication contract

Every built page carries `release_id`, `source_sha`, `schema_version`, `evidence_state`, and `QPS-UI/CSS v1.2` identity. Canonical diagrams must be pre-rendered to durable SVG; browser-side CDN rendering is not evidence.
