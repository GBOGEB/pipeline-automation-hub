#!/usr/bin/env python3
"""Read-only census of the cross-repo fine-grained tokens and what they changed.

For every secret in REGISTRY.json it compares each consumer workflow's
default-branch runs before and after the secret was saved, reads the failing
job's log for a token or setting signal, and probes the hub's own secrets with
one GET each. Telemetry only: no secret value is printed or stored, nothing is
written to GitHub, and the receipt carries no closure or merge credit.
"""
import argparse, json, os, pathlib, re, sys, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.github.com"
PROBE_REPO = "GBOGEB/cryoplant-project"  # private: only a valid token that selects it reads it
RED = {"failure", "timed_out", "startup_failure", "action_required"}
REDIRECT = {301, 302, 303, 307, 308}
# First match wins. Read from failed job logs only, so soft-skip notices never count.
SIGNALS = (
    ("AUTH_INVALID", re.compile(r'Bad credentials|"http_status":\s*401\b|\bHTTP[ :]401\b')),
    ("FORBIDDEN", re.compile(r'"http_status":\s*403\b|\bHTTP[ :]403\b|Resource not accessible by personal access token')),
    ("REPO_SETTING", re.compile(r"GitHub Actions is not permitted to create or approve pull requests")),
    ("SECRET_MISSING", re.compile(r"is required for governed PR|[A-Z_]+_TOKEN not configured")),
)
TOKEN_SIGNALS = {"AUTH_INVALID", "FORBIDDEN", "SECRET_MISSING"}
PROBE_STATES = {200: "VALID", 401: "INVALID", 403: "FORBIDDEN", 404: "NOT_SELECTED"}
OWNER_TEXT = {
    "AUTH_INVALID": "re-save this secret from token #{token}: GitHub rejects the stored value (401)",
    "FORBIDDEN": "token #{token} lacks a permission this workflow needs (403)",
    "SECRET_MISSING": "the workflow reports the secret as missing",
    "REPO_SETTING": "repo setting: Settings > Actions > General > allow GitHub Actions to create pull requests",
}


class ReadError(Exception):
    def __init__(self, status):
        super().__init__("HTTP %s" % status)
        self.status = status


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def http(url, token=None, timeout=30):
    """GET without following redirects, so a log redirect never carries the token."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "GoGREEN-Token-Census",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, headers=headers), timeout=timeout) as response:
            return response.status, response.read(), None
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get("Location")


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_registry(path):
    return load_registry_from(json.loads(pathlib.Path(path).read_text(encoding="utf-8")))


def load_registry_from(registry):
    if registry.get("schema") != "gogreen.token.registry.v1":
        raise ValueError("unexpected registry schema")
    tokens = {t["id"] for t in registry["tokens"]}
    seen = set()
    for s in registry["secrets"]:
        key = (s["repo"], s.get("environment"), s["name"])
        if key in seen:
            raise ValueError("duplicate secret " + s["name"])
        seen.add(key)
        if s["token"] not in tokens:
            raise ValueError("secret %s names unknown token %s" % (s["name"], s["token"]))
        if s.get("set_at") is None and not s.get("optional"):
            raise ValueError("required secret %s has no save time" % s["name"])
        if s.get("set_at"):
            parse_time(s["set_at"])
        if not s["consumers"]:
            raise ValueError("secret %s has no consumer" % s["name"])
        for c in s["consumers"]:
            if not all(c.get(k) for k in ("repo", "workflow", "branch", "without")):
                raise ValueError("incomplete consumer for " + s["name"])
            if "events" in c and not (isinstance(c["events"], list) and c["events"]):
                raise ValueError("consumer events must be a non-empty list for " + s["name"])
            if "job" in c and not (isinstance(c["job"], str) and c["job"]):
                raise ValueError("consumer job must be a job name for " + s["name"])
    if not set(registry["private_readers"]) <= {s["name"] for s in registry["secrets"]}:
        raise ValueError("private reader is not a registered secret")
    return registry


def _state(run):
    return "GREEN" if run.get("conclusion") == "success" else "RED"


def lane_verdict(set_at, runs):
    """Compare the last terminal run before the secret was saved with the latest one after."""
    terminal = sorted((r for r in runs if _terminal(r)), key=lambda r: r["created_at"])
    latest = terminal[-1] if terminal else None
    out = {"latest": _state(latest) if latest else None,
           "latest_run": ({"id": latest["id"], "created_at": latest["created_at"],
                           "event": latest.get("event"), "url": latest.get("html_url")}
                          if latest else None)}
    if set_at is None:
        out.update(verdict="NOT_SET", before=None, after=None, runs_since_set=0)
        return out
    before = [r for r in terminal if parse_time(r["created_at"]) < set_at]
    after = [r for r in terminal if parse_time(r["created_at"]) >= set_at]
    was = _state(before[-1]) if before else None
    now = _state(after[-1]) if after else None
    if now is None:
        verdict = "NO_RUN_SINCE_SET"
    elif was is None:
        verdict = "NEW_" + now
    elif (was, now) == ("RED", "GREEN"):
        verdict = "FIXED"
    elif (was, now) == ("GREEN", "GREEN"):
        verdict = "GREEN"
    elif (was, now) == ("GREEN", "RED"):
        verdict = "BROKE"
    else:
        verdict = "STILL_RED"
    out.update(verdict=verdict, before=was, after=now, runs_since_set=len(after),
               green_since_set=sum(1 for r in after if _state(r) == "GREEN"),
               red_since_set=sum(1 for r in after if _state(r) == "RED"))
    return out


def classify_log(text):
    for name, pattern in SIGNALS:
        if pattern.search(text):
            return name
    return "NONE"


class GitHub:
    def __init__(self, public_token, private_token, private_repos, fetch=http):
        self.public_token, self.private_token = public_token, private_token
        self.private_repos, self.fetch = set(private_repos), fetch

    def _token(self, repo):
        return self.private_token if repo in self.private_repos else self.public_token

    def json(self, repo, path):
        status, body, _ = self.fetch(API + "/repos/" + repo + path, self._token(repo))
        if status != 200:
            raise ReadError(status)
        return json.loads(body)

    def log(self, repo, job_id):
        status, body, location = self.fetch(
            "%s/repos/%s/actions/jobs/%d/logs" % (API, repo, job_id), self._token(repo))
        if status in REDIRECT and location:
            status, body, _ = self.fetch(location, None)
        if status != 200:
            raise ReadError(status)
        return body.decode("utf-8", "replace")


def _terminal(run):
    return run.get("status") == "completed" and (
        run.get("conclusion") == "success" or run.get("conclusion") in RED)


def list_runs(gh, consumer, set_at, per_page=100, max_pages=10):
    """Page newest-first until a terminal run from before the save is in hand.

    Returns (runs, baseline_complete). Without a save time one page is enough.
    """
    runs = []
    for page in range(1, max_pages + 1):
        raw = gh.json(consumer["repo"], "/actions/workflows/%s/runs?branch=%s&per_page=%d&page=%d"
                      % (consumer["workflow"], consumer["branch"], per_page, page)).get("workflow_runs", [])
        batch = ([r for r in raw if r.get("event") in consumer["events"]]  # events that use the secret
                 if consumer.get("events") else raw)
        runs += batch
        if set_at is None or any(_terminal(r) and parse_time(r["created_at"]) < set_at for r in batch):
            return runs, True
        if len(raw) < per_page:
            return runs, True  # history exhausted: there is no earlier run
    return runs, False


def job_view(gh, repo, runs, job, set_at, max_runs=15):
    """Replace each run's conclusion with that of the named job; drop runs where it did not run.

    A workflow can be green while the job that uses the secret was skipped (for
    example dispatch without the opt-in), which must not count as the token working.
    """
    out = []
    for run in sorted((r for r in runs if r.get("status") == "completed"),
                      key=lambda r: r["created_at"], reverse=True)[:max_runs]:
        jobs = gh.json(repo, "/actions/runs/%d/jobs?per_page=100" % run["id"]).get("jobs", [])
        mine = [j for j in jobs if j.get("name") == job]
        if not mine or not all(_terminal(j) for j in mine):
            continue
        state = "success" if all(j["conclusion"] == "success" for j in mine) else "failure"
        out.append(dict(run, conclusion=state))
        if set_at is not None and parse_time(run["created_at"]) < set_at:
            break  # baseline found
    return out


def red_signal(gh, repo, run_id, max_jobs=3):
    try:
        jobs = gh.json(repo, "/actions/runs/%d/jobs?per_page=100" % run_id).get("jobs", [])
        failed = [j for j in jobs if j.get("conclusion") in RED][:max_jobs]
        for job in failed:
            signal = classify_log(gh.log(repo, job["id"]))
            if signal != "NONE":
                return signal
        return "NONE"
    except ReadError:
        return "UNREAD"


def probe(token, fetch=http):
    if not token:
        return "UNSET"
    status, _, _ = fetch(API + "/repos/" + PROBE_REPO, token)
    return PROBE_STATES.get(status, "HTTP_%d" % status)


def action_for(lane):
    """OK, WAIT, OWNER (the token owner acts) or THREAD (a red that is not the token)."""
    if lane["verdict"] == "UNREAD":
        return "OWNER", "the census cannot read this workflow (HTTP %s)" % lane.get("read_status")
    if lane.get("probe") not in (None, "VALID", "NOT_PROBED"):
        return "OWNER", "hub probe says %s: re-save from token #%s" % (lane["probe"], lane["token"])
    if lane["verdict"] == "NO_RUN_SINCE_SET":
        return "WAIT", "no default-branch run has used the secret since it was saved"
    if lane.get("latest") != "RED":
        return "OK", "latest run green"
    signal = lane.get("signal", "NONE")
    if signal in OWNER_TEXT:
        return "OWNER", OWNER_TEXT[signal].format(token=lane["token"])
    return "THREAD", "red for a reason other than the token (signal %s); needs a lane owner" % signal


def census(registry, gh, probes, now):
    lanes = []
    for s in registry["secrets"]:
        set_at = parse_time(s["set_at"]) if s.get("set_at") else None
        for c in s["consumers"]:
            lane = {"secret": s["name"], "secret_repo": s["repo"], "environment": s.get("environment"),
                    "token": s["token"], "optional": bool(s.get("optional")), "repo": c["repo"],
                    "workflow": c["workflow"], "branch": c["branch"], "without_secret": c["without"]}
            if s["repo"] == registry["hub"]:
                lane["probe"] = probes.get(s["name"], "UNSET")
            try:
                runs, lane["baseline_complete"] = list_runs(gh, c, set_at)
                if c.get("job"):  # judge only runs where the secret's own job actually ran
                    runs = job_view(gh, c["repo"], runs, c["job"], set_at)
                lane.update(lane_verdict(set_at, runs))
                if lane["latest"] == "RED":
                    lane["signal"] = red_signal(gh, c["repo"], lane["latest_run"]["id"])
            except ReadError as exc:
                lane.update(verdict="UNREAD", read_status=exc.status)
            lane["action"], lane["why"] = action_for(lane)
            lanes.append(lane)
    tokens = []
    for t in registry["tokens"]:
        own = [s for s in registry["secrets"] if s["token"] == t["id"]]
        saved = [parse_time(s["set_at"]) for s in own if s.get("set_at")]
        mine = [l for l in lanes if l["token"] == t["id"]]
        expires = min(saved) + timedelta(days=t["expires_days"]) if saved else None
        tokens.append({"id": t["id"], "name": t["name"],
                       "secrets_saved": len(saved), "secrets_required": sum(1 for s in own if not s.get("optional")),
                       "probes": {s["name"]: probes[s["name"]] for s in own if s["name"] in probes},
                       "lanes": {a: sum(1 for l in mine if l["action"] == a) for a in ("OK", "OWNER", "THREAD", "WAIT")},
                       "expires_estimate": expires.strftime("%Y-%m-%d") if expires else None,
                       "days_left": (expires - now).days if expires else None})
    stacks = {}
    for lane in lanes:
        if lane["action"] == "THREAD":
            stacks.setdefault(lane["repo"], []).append(lane["workflow"])
    unhealthy = [l for l in lanes if l.get("signal") in TOKEN_SIGNALS
                 or l.get("probe") not in (None, "VALID", "NOT_PROBED")]
    return {"schema": "gogreen.token.census.v1", "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "registry_observed_at": registry["observed_at"], "probes": probes, "tokens": tokens, "lanes": lanes,
            "totals": {"lanes": len(lanes), **{a.lower(): sum(1 for l in lanes if l["action"] == a)
                                               for a in ("OK", "OWNER", "THREAD", "WAIT")},
                       "fixed": sum(1 for l in lanes if l.get("verdict") == "FIXED"),
                       "broke": sum(1 for l in lanes if l.get("verdict") == "BROKE"),
                       "runs_since_set": sum(l.get("runs_since_set", 0) for l in lanes)},
            "threads_needed": [{"stack": repo, "lanes": wfs} for repo, wfs in sorted(stacks.items())],
            "token_health": "ACTION_REQUIRED" if unhealthy else "HEALTHY",
            "formal_root_closure_credit": 0, "merge_authorized": False}


def markdown(receipt):
    t = receipt["totals"]
    lines = ["# Token census, %s" % receipt["generated_at"], "",
             "Token health: **%s**. %d lanes: %d OK, %d owner action, %d need a thread, %d waiting for a run. "
             "%d fixed and %d broken since their secret was saved; %d consumer runs since."
             % (receipt["token_health"], t["lanes"], t["ok"], t["owner"], t["thread"], t["wait"],
                t["fixed"], t["broke"], t["runs_since_set"]), "",
             "| # | Token | Secrets saved | Hub probe | OK / owner / thread / wait | Expires (days left) |",
             "|---|---|---|---|---|---|"]
    for tok in receipt["tokens"]:
        probes = ", ".join("%s %s" % (k, v) for k, v in tok["probes"].items()) or "n/a"
        lanes = "{OK} / {OWNER} / {THREAD} / {WAIT}".format(**tok["lanes"])
        lines.append("| %d | `%s` | %d of %d | %s | %s | %s (%s) |" % (
            tok["id"], tok["name"], tok["secrets_saved"], tok["secrets_required"], probes, lanes,
            tok["expires_estimate"], tok["days_left"]))
    lines += ["", "| Secret | Consumer | Before → after | Runs since | Signal | Action |", "|---|---|---|---|---|---|"]
    for l in receipt["lanes"]:
        lines.append("| `%s` | %s `%s` | %s → %s (%s) | %s | %s | **%s**: %s |" % (
            l["secret"], l["repo"].split("/")[1], l["workflow"], l.get("before") or "-", l.get("after") or "-",
            l["verdict"], l.get("runs_since_set", 0), l.get("signal", "-"), l["action"], l["why"]))
    lines.append("")
    if receipt["threads_needed"]:
        lines.append("Threads needed (reds that are not the token):")
        lines += ["- %s: %s" % (s["stack"], ", ".join(s["lanes"])) for s in receipt["threads_needed"]]
    else:
        lines.append("No new thread is needed: every red lane is a token or setting action for the owner.")
    return "\n".join(lines) + "\n"


def _esc(text):
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def annotations(receipt):
    """Check annotations (Actions workflow commands) for every finding the owner must act on.

    The step summary and artifact are not visible everywhere a check is; annotations are.
    Only secret names, probe states and lane verdicts appear, never a value.
    """
    names = {t["id"]: t["name"] for t in receipt["tokens"]}
    out = []
    for tok in receipt["tokens"]:
        for secret, state in sorted(tok["probes"].items()):
            if state not in ("VALID", "NOT_PROBED"):
                out.append("::error title=token census: %s::%s" % (_esc(secret), _esc(
                    "hub probe of %s returned %s for token #%d %s (UNSET: secret empty; INVALID: re-save; "
                    "NOT_SELECTED: the token does not select that repo or its org approval is pending)"
                    % (PROBE_REPO, state, tok["id"], tok["name"]))))
    for lane in receipt["lanes"]:
        if lane["action"] in ("OWNER", "THREAD"):
            level = "error" if lane["action"] == "OWNER" else "warning"
            out.append("::%s title=token census %s: %s::%s" % (level, lane["action"], _esc(lane["workflow"]), _esc(
                "%s (token #%d %s) on %s: %s [verdict %s, signal %s]" % (
                    lane["secret"], lane["token"], names.get(lane["token"], "?"), lane["repo"], lane["why"],
                    lane.get("verdict"), lane.get("signal", "-")))))
    return out


def main(argv=None, environ=None, fetch=http, now=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registry", required=True, type=pathlib.Path)
    parser.add_argument("--out", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    env = os.environ if environ is None else environ
    registry = load_registry(args.registry)
    hub_secrets = [s["name"] for s in registry["secrets"] if s["repo"] == registry["hub"]]
    # CI passes every PROBE_<secret> (empty when unset); a local owner run passes none.
    probes = {name: probe(env["PROBE_" + name], fetch) if "PROBE_" + name in env else "NOT_PROBED"
              for name in hub_secrets}
    private = env.get("PRIVATE_READ_TOKEN") or next(
        (env["PROBE_" + n] for n in registry["private_readers"] if probes.get(n) == "VALID"), "")
    gh = GitHub(env.get("GH_TOKEN", ""), private, registry["private_repos"], fetch)
    receipt = census(registry, gh, probes, now or datetime.now(timezone.utc))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "token_census.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    (args.out / "token_census.md").write_text(markdown(receipt), encoding="utf-8")
    if env.get("GITHUB_ACTIONS") == "true":  # live CI only; offline tests stay silent
        for line in annotations(receipt):
            print(line)
    print(json.dumps({"token_health": receipt["token_health"], **receipt["totals"]}))
    return 1 if receipt["token_health"] != "HEALTHY" else 0


if __name__ == "__main__":
    sys.exit(main())
