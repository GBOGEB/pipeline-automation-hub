import {readFileSync,writeFileSync,mkdirSync} from "node:fs";
import {dirname,resolve} from "node:path";
import {suite} from "./probe.mjs";
const profile=JSON.parse(readFileSync(new URL("./arm.json",import.meta.url),"utf8"));
const output=process.argv[2];
if(!output)throw Error("output receipt path required");
const receipt=suite(profile);
if(receipt.metrics.false_green!==0||receipt.metrics.rejected_negatives!==20||
   receipt.metrics.git_writes!==0||receipt.metrics.remote_writes!==0||
   receipt.boundary.merge_admission!=="HOLD")throw Error("MCEX_FAIL_CLOSED_INVARIANT");
receipt.native_run={
 source_checkout_sha:process.env.MCEX_EXACT_HEAD||null,
 github_run_id:process.env.GITHUB_RUN_ID||null,
 github_job:process.env.GITHUB_JOB||null,
 github_run_attempt:process.env.GITHUB_RUN_ATTEMPT||null,
 live_terminal_result:"NOT_ATTESTED_BY_SELF_GENERATED_REPORT"
};
mkdirSync(dirname(resolve(output)),{recursive:true});
writeFileSync(output,JSON.stringify(receipt,null,2)+"\n","utf8");
console.log("MCEX_ARM_SIMULATION=PASS",JSON.stringify(receipt.metrics),
 "remote mutation=DENY","native & owner admission=HOLD");
