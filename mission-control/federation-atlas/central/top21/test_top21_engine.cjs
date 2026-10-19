'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {replay, validateRecord, groupDocumentFamilies, countLanguage} = require('./top21_engine.cjs');
function record(name='ABACUS') {
 return {repo:'GBOGEB/'+name,branch:'main',sha:'a'.repeat(40),tree_sha:'b'.repeat(40),complete:true,
 files:4,root_files:['README.md','report.md','report.pdf'],root_review:[
 {path:'report.md',reason:'ROOT_NARRATIVE_JUSTIFICATION'},
 {path:'report.pdf',reason:'ROOT_BINARY_OR_BUNDLE'}],
 extensions:{'.md':2,'.pdf':1,'.py':1},top_level:[{name:'[root]',files:3},{name:'src',files:1}]};
}
const part=r=>({schema:'missioncontrol.top21.tree_census.part.v1',records:[r]});
test('fully tracked same-population sum',()=>{const r=replay([part(record())],1);assert.equal(r.total.files,4);assert.equal(r.total.root_files,3);assert.equal(r.total.review_candidates,2);assert.equal(r.total.counts.python,1);});
test('stable repeat hash',()=>{assert.equal(replay([part(record())],1).semantic_sha256,replay([part(record())],1).semantic_sha256)});
test('semantic family is a candidate, not duplicate proof',()=>{const f=groupDocumentFamilies(record());assert.equal(f.length,1);assert.deepEqual(f[0].paths,['report.md','report.pdf']);});
test('no dispatch or promotion',()=>{const r=replay([part(record())],1);assert.equal(r.merge_admission,'HOLD');assert.equal(r.work_proposals[0].dispatch,'NOT_AUTHORIZED');});
test('reject truncated recursive tree',()=>{const r=record();r.complete=false;assert.throws(()=>validateRecord(r),/incomplete/);});
test('reject spoofed SHA',()=>{const r=record();r.sha='0';assert.throws(()=>validateRecord(r),/SHA/);});
test('reject family numerator mismatch',()=>{const r=record();r.extensions['.py']=2;assert.throws(()=>validateRecord(r),/denominator/);});
test('reject duplicate roots',()=>{const r=record();r.root_files.push('report.md');assert.throws(()=>validateRecord(r),/duplicate roots/);});
test('reject nested path counted as root',()=>{const r=record();r.root_files[0]='docs/README.md';assert.throws(()=>validateRecord(r),/nested path/);});
test('reject detached candidate',()=>{const r=record();r.root_review[0].path='phantom.md';assert.throws(()=>validateRecord(r),/detached/);});
test('reject duplicate repository in same cohort',()=>{assert.throws(()=>replay([part(record()),part(record())],2),/duplicate repository/);});
test('reject invalid schema',()=>{assert.throws(()=>replay([{schema:'other',records:[record()]}],1),/part schema/);});
test('validate cohort denominator and language classifications',()=>{assert.throws(()=>replay([part(record())],21),/cohort size/);assert.equal(countLanguage({'.ts':2,'.tsx':3},'typescript'),5);});
