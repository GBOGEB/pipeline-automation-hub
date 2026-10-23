---
layout: qps
title: gg_MATH Bridge Evidence
---
{% assign g = site.data.ggmath_bridge_figures %}

<div class="qps-card" data-ggmath-provider-sha="{{ g.provider.sha }}" data-ggmath-schema="{{ g.schema }}">
<p>Math kernels from <code>{{ g.provider.repo }}</code> pinned at <code>{{ g.provider.sha }}</code>, digest-verified before execution. Figures are derived from <code>{{ g.receipt }}</code> (sha256 <code>{{ g.receipt_sha256 }}</code>). This page transfers no authority: PCA outputs are never Bradley–Terry evidence, and <code>DEFER</code> states are shown as they are.</p>
<p id="ggmath-plotly-status">Interactive charts need the offline Plotly bundle that the build vendors from <code>{{ g.plotly_python_pin }}</code>. The tables below are the evidence either way.</p>
</div>

## Bridged results

<table>
<thead><tr><th>Figure</th><th>Status</th><th>Evidence class</th><th>Threshold kind</th><th>Reading</th></tr></thead>
<tbody>
{% for f in g.figures %}<tr><td><a href="#fig-{{ f.id }}">{{ f.id }}</a></td><td><code>{{ f.status }}</code></td><td>{{ f.evidence_class }}</td><td>{% for t in f.threshold_kind %}<code>{{ t[0] }}={{ t[1] }}</code> {% endfor %}</td><td>{{ f.headline }}</td></tr>
{% endfor %}</tbody>
</table>

## Deferred measured adapters

<ul>
{% for d in g.deferred_measured_adapters %}<li><code>{{ d.adapter }}</code>: <code>{{ d.status }}</code></li>
{% endfor %}</ul>

## Figures

{% for f in g.figures %}<section class="qps-card" aria-label="{{ f.id }}">
<h3 id="fig-{{ f.id }}">{{ f.id }}</h3>
<p><code>{{ f.status }}</code> · {{ f.evidence_class }} · {{ f.headline }}</p>
<div class="ggmath-figure" data-figure-id="{{ f.id }}"></div>
</section>
{% endfor %}

<script type="application/json" id="ggmath-figures" data-plotlyjs="{{ '/assets/js/plotly.min.js' | relative_url }}">{{ g | jsonify }}</script>
<script src="{{ '/assets/js/ggmath-bridge.js' | relative_url }}"></script>
