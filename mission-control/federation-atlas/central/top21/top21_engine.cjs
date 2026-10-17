#!/usr/bin/env node
'use strict';
/** Read-only, exact-source repository census replay and triage planner. */
const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');
const SHA = /^[0-9a-f]{40}$/;
const CLASSES = Object.freeze({
  python: ['.py'], markdown: ['.md', '.markdown'],
  yaml: ['.yaml', '.yml'], json: ['.json'], toml: ['.toml'],
  javascript: ['.js', '.jsx', '.mjs', '.cjs'],
  typescript: ['.ts', '.tsx'], powershell: ['.ps1', 'PowerShell module'],
  shell: ['.sh', '.bash'], batch: ['.bat', '.cmd'],
  makefile: ['Makefile'], dockerfile: ['Dockerfile'],
  notebook: ['.ipynb'], html: ['.html'], css: ['.css'],
});
function fail(msg) { throw new Error('N11_CENSUS_FAIL_CLOSED: ' + msg); }
function countLanguage(extensions, group) {
  return (CLASSES[group] || []).reduce((s, k) => s + (extensions[k] || 0), 0);
}
function validateRecord(r) {
  if (!r || !r.repo || !/^GBOGEB\/[\w.-]+$/.test(r.repo)) fail('repository identity');
  if (!SHA.test(r.sha || '') || !SHA.test(r.tree_sha || '')) fail(r.repo + ' SHA identity');
  if (r.complete !== true) fail(r.repo + ' tree incomplete/truncated');
  if (!Number.isSafeInteger(r.files) || r.files < 0) fail(r.repo + ' file count');
  if (!Array.isArray(r.root_files) || !Array.isArray(r.root_review)) fail(r.repo + ' root arrays');
  if (new Set(r.root_files).size !== r.root_files.length) fail(r.repo + ' duplicate roots');
  const roots = new Set(r.root_files);
  if (r.root_files.some(p => p.includes('/'))) fail(r.repo + ' nested path as root');
  if (r.root_review.some(x => !roots.has(x.path))) fail(r.repo + ' detached review candidate');
  const extensionCount = Object.values(r.extensions || {}).reduce((sum, n) => {
    if (!Number.isSafeInteger(n) || n < 0) fail(r.repo + ' invalid file family');
    return sum + n;
  }, 0);
  if (extensionCount !== r.files) fail(r.repo + ' family/files denominator mismatch');
  if (r.root_review.length > r.root_files.length) fail(r.repo + ' reviews exceed root population');
  return true;
}
function groupDocumentFamilies(r) {
  const map = new Map();
  for (const f of r.root_review) {
    const stem = f.path.replace(/\.(?:md|markdown|pdf|docx?|pptx?|xlsx?|json|ya?ml|txt|html)$/i, '').toLowerCase();
    if (!map.has(stem)) map.set(stem, []);
    map.get(stem).push(f.path);
  }
  return [...map].filter(([, paths]) => paths.length > 1)
    .map(([stem, paths]) => ({stem, paths: paths.sort()}))
    .sort((a, b) => a.stem.localeCompare(b.stem));
}
function replay(parts, expectedRepositories = 21) {
  if (!Array.isArray(parts) || !parts.length) fail('missing part documents');
  const input = parts.flatMap(p => {
    if (p.schema !== 'missioncontrol.top21.tree_census.part.v1') fail('part schema');
    if (!Array.isArray(p.records)) fail('part records');
    return p.records;
  });
  if (input.length !== expectedRepositories) fail('unexpected cohort size');
  const seen = new Set();
  for (const r of input) {
    validateRecord(r);
    if (seen.has(r.repo)) fail('duplicate repository ' + r.repo);
    seen.add(r.repo);
  }
  const records = [...input].sort((a, b) => a.repo.localeCompare(b.repo));
  const files = records.reduce((s, x) => s + x.files, 0);
  const rootFiles = records.reduce((s, x) => s + x.root_files.length, 0);
  const reviews = records.reduce((s, x) => s + x.root_review.length, 0);
  const shares = records.map(x => x.files / Math.max(files, 1));
  const reviewShares = records.map(x => x.root_review.length / Math.max(reviews, 1));
  const keyTotals = Object.fromEntries(Object.keys(CLASSES).map(k => [k, records.reduce(
    (s, x) => s + countLanguage(x.extensions, k), 0,
  )]));
  const rows = records.map(r => ({
    repo: r.repo, branch: r.branch, sha: r.sha, tree_sha: r.tree_sha,
    files: r.files, root_files: r.root_files.length,
    review_candidates: r.root_review.length,
    review_fraction_of_files: r.root_review.length / Math.max(1, r.files),
    review_fraction_of_root: r.root_review.length / Math.max(1, r.root_files.length),
    doc_family_candidates: groupDocumentFamilies(r),
    extensions: Object.fromEntries(Object.keys(CLASSES).map(k => [k, countLanguage(r.extensions, k)])),
    wireframe: r.top_level,
    launch_sha: r.sha,
  }));
  const work = [...rows].sort((a, b) => b.review_candidates - a.review_candidates).map((r, i) => ({
    wave: 'ROOT-AUDIT-' + String(i + 1).padStart(2, '0'),
    repo: r.repo, source_sha: r.sha,
    candidate_files: r.review_candidates, kind: 'READ_ONLY_STEWARDSHIP',
    dispatch: 'NOT_AUTHORIZED', source_mutation: false,
    entry: 'CLASSIFY_PURPOSE_AND_CONSUMERS',
    verify: 'PATH_REFERENCE_SCAN_THEN_INDEPENDENT_REVIEW',
  }));
  const out = {
    schema: 'missioncontrol.top21.replay.v1',
    source_class: 'EXACT_DEFAULT_BRANCH_GIT_TREE',
    authority_transfer: false, merge_admission: 'HOLD',
    total: {repos: records.length, files, root_files: rootFiles, review_candidates: reviews,
      counts: keyTotals},
    stats: {file_hhi: shares.reduce((s, v) => s + v*v, 0),
      review_hhi: reviewShares.reduce((s, v) => s + v*v, 0),
      inference: 'DESCRIPTIVE_COMPLETE_COHORT_ONLY'},
    repositories: rows,
    work_proposals: work,
    note: 'Root review candidates and same-stem files are not proven defects or duplicates.',
  };
  out.semantic_sha256 = crypto.createHash('sha256').update(JSON.stringify(out)).digest('hex');
  return out;
}
function main(argv) {
  if (argv.length < 4) fail('usage: node top21_engine.cjs <parts-directory> <output-json>');
  const dir = argv[2], output = argv[3];
  const files = fs.readdirSync(dir).filter(n => /^CENSUS_[A-Z0-9_]+_PART[0-9]+\.json$/.test(n)).sort()
    .map(n => path.join(dir, n));
  if (!files.length) fail('missing append-only census pulse parts');
  const docs = files.map(file => JSON.parse(fs.readFileSync(file, 'utf8')));
  const expected = argv[4] === undefined ? 21 : Number(argv[4]);
  if (!Number.isSafeInteger(expected) || expected < 1 || expected > 100) fail('cohort size must be 1..100');
  const result = replay(docs, expected);
  fs.mkdirSync(path.dirname(output), {recursive:true});
  fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({source:files, output, ...result.total, sha256:result.semantic_sha256}));
}
if (require.main === module) main(process.argv);
module.exports = {replay, validateRecord, groupDocumentFamilies, countLanguage, CLASSES};
