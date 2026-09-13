# QPS Browser Support Contract v1.2

Owner: H4_QPS_TRIAGE
Status: CONTROLLED_DRAFT

## Operational surface

The Next/React cockpit targets maintained modern browsers supported by the active Next.js release. Internet Explorer 11 is not an operational target.

## Static evidence surface

The Jekyll publication layer shall remain semantic, readable HTML with CSS progressive enhancement. Core mission/evidence meaning must remain available without client-side JavaScript.

## Degradation rule

If a browser cannot execute the operational application, the static evidence atlas remains the durable read-only fallback. No evidence identity, state label, lineage, or required navigation may depend solely on JavaScript, animation, hover, or color.

## Triage gate

Any package/browser configuration that claims IE11 support while the operational framework does not support IE11 is a contract contradiction and shall fail QPS web review until reconciled.
