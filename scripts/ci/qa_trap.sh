# shellcheck shell=bash
# GOGREEN G10: sourced at the top of a QA step. On a NON-ZERO exit it emits the last
# assertion/error lines of the step's own output as a ::error check annotation, so a red QA
# step is diagnosable from the Checks UI without downloading logs. The step's exit code and
# success path are unchanged. Revert = delete the one `source` line (or this file: callers
# guard with `[ -f ]`, so a missing helper is a no-op).
#   usage (first line of a run: block):
#   [ -f "$GITHUB_WORKSPACE/scripts/ci/qa_trap.sh" ] && QA_TITLE="step name" . "$GITHUB_WORKSPACE/scripts/ci/qa_trap.sh"
__qa_title="${QA_TITLE:-${GITHUB_JOB:-qa}}"
__qa_title="${__qa_title//[$'\n\r:,']/ }"
__qa_log="$(mktemp "${RUNNER_TEMP:-/tmp}/qa-step.XXXXXX")"
exec 3>&1 4>&2
exec > >(tee -a "$__qa_log") 2>&1
__qa_on_exit() {
  local rc=$?
  set +e +u +o pipefail   # never let the handler itself abort or mask the step's code
  if [ "$rc" -ne 0 ]; then
    exec 1>&3 2>&4   # close the tee pipe so every byte of step output reaches the log
    sleep 0.3
    local msg
    msg=$(grep -E "Error|error:|assert|Assert|require|FAIL|mismatch|parity|Traceback|Timeout|denied|not found" "$__qa_log" \
          | grep -v '^::' | tail -n 3 | tr '\n' ' ' | sed 's/%/%25/g' | cut -c1-900)
    echo "::error title=${__qa_title}::${msg:-exit $rc (no assertion text captured)}"
  fi
  return "$rc"
}
trap __qa_on_exit EXIT
