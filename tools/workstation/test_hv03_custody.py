"""HV-03 local git fixture replay, no network, no repository mutation by collector."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import hv03_custody as hv03

def git(repo, *args):
    p = subprocess.run(["git", "-C", str(repo), *args], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=True)
    return p.stdout.decode("utf-8", "replace").strip()

class HV03Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "master")
        git(self.repo, "config", "user.email", "test@example.invalid")
        git(self.repo, "config", "user.name", "HV03 Fixture")
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        (self.repo / "plan.pdf").write_bytes(b"synthetic-pdf-bytes")
        git(self.repo, "add", "tracked.txt", "plan.pdf")
        git(self.repo, "commit", "-qm", "fixture")

    def test_empty_scan_tracked_binary_hash(self):
        data = hv03.scan(self.repo)
        self.assertEqual(data["schema"], hv03.SCHEMA)
        self.assertEqual(len(data["worktrees"]), 1)
        self.assertEqual(len(data["source_refs"]), 1)
        r = data["worktrees"][0]["files"]
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["kind"], "TRACKED_BINARY")
        self.assertEqual(r[0]["sha256"], hashlib.sha256(b"synthetic-pdf-bytes").hexdigest())
        self.assertEqual(r[0]["owner_state"], "UNKNOWN")
        self.assertFalse(data["remote_credential_or_api_use"])

    def test_staged_worktree_and_untracked_are_distinct(self):
        (self.repo / "tracked.txt").write_bytes(b"staged\n")
        git(self.repo, "add", "tracked.txt")
        (self.repo / "tracked.txt").write_bytes(b"unstaged\n")
        (self.repo / "untracked.docx").write_bytes(b"doc")
        rows = hv03.scan(self.repo)["worktrees"][0]["files"]
        staged = next(r for r in rows if r["path"] == "tracked.txt")
        self.assertEqual(staged["status"], "MM")
        self.assertEqual(staged["sha256"], hashlib.sha256(b"unstaged\n").hexdigest())
        self.assertEqual(staged["staged_index"][0]["index_sha256"],
                         hashlib.sha256(b"staged\n").hexdigest())
        fresh = next(r for r in rows if r["path"] == "untracked.docx")
        self.assertEqual(fresh["status"], "??")
        self.assertEqual(fresh["sha256"], hashlib.sha256(b"doc").hexdigest())

    def test_second_scan_stable_and_no_writes(self):
        initial = git(self.repo, "status", "--porcelain", "--untracked-files=all")
        a = hv03.scan(self.repo)
        b = hv03.scan(self.repo)
        self.assertEqual(hv03.canonical(a), hv03.canonical(b))
        self.assertEqual(hv03.public_summary(a)["private_manifest_sha256"],
                         hv03.public_summary(b)["private_manifest_sha256"])
        self.assertEqual(git(self.repo, "status", "--porcelain", "--untracked-files=all"), initial)

    def test_local_worktree_enumeration(self):
        linked = self.root / "other"
        git(self.repo, "worktree", "add", "-qb", "feature-hv03", str(linked))
        data = hv03.scan(self.repo)
        self.assertEqual(len(data["worktrees"]), 2)
        self.assertEqual(len(data["source_refs"]), 2)
        self.assertTrue(all(w["remote_head"] == "UNKNOWN_OFFLINE" for w in data["worktrees"]))

    def test_owner_collision_and_declared_identity(self):
        self.assertEqual(hv03.owners("docs/a.pdf", [
            {"glob": "docs/**", "owner": "A", "pr": 1002},
            {"glob": "docs/*.pdf", "owner": "B", "pr": 1022}])["owner_state"], "COLLISION")
        self.assertEqual(hv03.owners("docs/a.pdf", [
            {"glob": "docs/**", "owner": "A", "pr": 1002}])["owner_state"], "DECLARED_UNVERIFIED")

    def test_bounded_hash_and_deleted_file(self):
        self.assertEqual(hv03.hash_file(self.repo, "plan.pdf", 1)["state"], "SIZE_LIMIT")
        (self.repo / "tracked.txt").unlink()
        rows = hv03.scan(self.repo)["worktrees"][0]["files"]
        gone = next(r for r in rows if r["path"] == "tracked.txt")
        self.assertEqual(gone["state"], "MISSING")

    def test_never_hash_outside_scope(self):
        self.assertEqual(hv03.hash_file(self.repo, "../elsewhere", 100)["state"], "UNSAFE_PATH")
        self.assertEqual(hv03.hash_file(self.repo, "/etc/passwd", 100)["state"], "UNSAFE_PATH")

    def test_private_receipts_require_external_directory(self):
        data = hv03.scan(self.repo)
        summary = hv03.public_summary(data)
        with self.assertRaisesRegex(ValueError, "cannot write"):
            hv03.write_private(self.repo / ".hv03", data, summary)
        outside = self.root / "private"
        hv03.write_private(outside, data, summary)
        self.assertTrue((outside / "HV03_PRIVATE.json").is_file())
        self.assertEqual(json.loads((outside / "HV03_PRIVATE.json").read_text()), data)
        self.assertEqual(json.loads((outside / "HV03_SUMMARY.json").read_text()), summary)
        if os.name != "nt":
            self.assertEqual((outside / "HV03_PRIVATE.json").stat().st_mode & 0o077, 0)

    def test_owner_allowlist_rejects_false_format(self):
        owners = self.root / "owners.json"
        owners.write_text('{"rules":[{"glob":"*","owner":"x"}]}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "allowlist schema"):
            hv03.load_owner_rules(owners)
        owners.write_text(json.dumps({"schema":"gbo.hv03.owner-allowlist.v1",
                                      "rules":[{"glob":"*.pdf","owner":"DOCUMENT","pr":1022}]}),
                          encoding="utf-8")
        self.assertEqual(hv03.load_owner_rules(owners)[0]["owner"], "DOCUMENT")

    def test_summary_no_paths_or_secrets(self):
        secret_name = "PRIVATE_LOCAL_FILENAME.pdf"
        (self.repo / secret_name).write_bytes(b"secret bytes")
        summary = hv03.public_summary(hv03.scan(self.repo))
        text = json.dumps(summary)
        self.assertNotIn(secret_name, text)
        self.assertNotIn(str(self.repo), text)
        self.assertEqual(summary["merge_admission"], "HOLD")
        self.assertEqual(summary["publication"], "NOT_AUTHORIZED")

    def test_private_receipts_owner_only_acl_or_refuse(self):
        data = hv03.scan(self.repo)
        summary = hv03.public_summary(data)
        outside = self.root / "acl"
        hv03.write_private(outside, data, summary)
        for path in (outside, outside / "HV03_PRIVATE.json", outside / "HV03_SUMMARY.json"):
            self.assertTrue(hv03.private_acl_ok(path), path.name)
            if os.name == "nt":
                self.assertTrue(hv03.sddl_owner_only(hv03.windows_dacl_sddl(path),
                                                     hv03.current_user_sid()))
        refused = self.root / "refused"
        with mock.patch.object(hv03, "private_acl_ok", return_value=False):
            with self.assertRaisesRegex(ValueError, "cannot verify private receipt ACL"):
                hv03.write_private(refused, data, summary)
        self.assertEqual(list(refused.iterdir()), [])

    def test_sddl_owner_only_rejects_inherited_or_shared(self):
        me = "S-1-5-21-1-2-3-1001"
        self.assertTrue(hv03.sddl_owner_only(f"D:PAI(A;OICI;FA;;;{me})", me))
        self.assertFalse(hv03.sddl_owner_only(f"D:AI(A;;FA;;;{me})", me))
        self.assertFalse(hv03.sddl_owner_only(f"D:P(A;;FA;;;{me})(A;;FR;;;WD)", me))
        self.assertFalse(hv03.sddl_owner_only(f"D:P(D;;FA;;;{me})", me))
        self.assertFalse(hv03.sddl_owner_only("D:P", me))

    def test_summary_counts_unhashed_staged_index(self):
        (self.repo / "tracked.txt").write_bytes(b"x" * 200)
        git(self.repo, "add", "tracked.txt")
        (self.repo / "tracked.txt").write_bytes(b"small\n")
        data = hv03.scan(self.repo, max_bytes=100)
        row = next(r for r in data["worktrees"][0]["files"] if r["path"] == "tracked.txt")
        self.assertEqual(row["state"], "HASHED")
        self.assertEqual(row["staged_index"][0]["index_sha_state"], "SIZE_LIMIT")
        self.assertEqual(hv03.public_summary(data)["incomplete_hashes"], 1)

    def test_same_size_rewrite_during_read_is_changed(self):
        target = self.repo / "plan.pdf"
        original = target.read_bytes()
        real = hashlib.sha256

        class RewriteOnFirstChunk:
            def __init__(self):
                self.h, self.done = real(), False
            def update(self, chunk):
                self.h.update(chunk)
                if not self.done:
                    self.done = True
                    with target.open("r+b") as f:
                        f.write(bytes(255 - b for b in original))
                    st = target.stat()
                    os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
            def hexdigest(self):
                return self.h.hexdigest()

        with mock.patch.object(hv03.hashlib, "sha256", RewriteOnFirstChunk):
            result = hv03.hash_file(self.repo, "plan.pdf", 1024)
        self.assertEqual(target.stat().st_size, len(original))
        self.assertEqual(result["state"], "CHANGED_DURING_SCAN")
        self.assertIsNone(result["sha256"])

    def test_configured_fsmonitor_hook_never_runs(self):
        marker = self.root / "fsmonitor-ran"
        hook = self.root / "fsmonitor-hook"
        hook.write_bytes(b"#!/bin/sh\necho ran > '" + marker.as_posix().encode() + b"'\n")
        hook.chmod(0o755)
        git(self.repo, "config", "core.fsmonitor", hook.as_posix())
        (self.repo / "tracked.txt").write_bytes(b"dirty\n")
        rows = hv03.scan(self.repo)["worktrees"][0]["files"]
        self.assertIn("tracked.txt", {r["path"] for r in rows})
        self.assertFalse(marker.exists())

    def test_repo_local_git_environment_is_ignored(self):
        other = self.root / "other-repo"
        other.mkdir()
        git(other, "init", "-q", "-b", "master")
        (other / "decoy.pdf").write_bytes(b"decoy")
        overrides = {"GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other),
                     "GIT_INDEX_FILE": str(other / ".git" / "index")}
        with mock.patch.dict(os.environ, overrides):
            data = hv03.scan(self.repo)
        self.assertEqual(Path(data["repository_root"]), self.repo.resolve())
        paths = {r["path"] for r in data["worktrees"][0]["files"]}
        self.assertEqual(paths, {"plan.pdf"})
        env = hv03.git_env()
        for name in overrides:
            self.assertNotIn(name, env)

    def test_missing_worktree_counted_incomplete(self):
        linked = self.root / "gone"
        git(self.repo, "worktree", "add", "-qb", "feature-gone", str(linked))
        shutil.rmtree(linked)
        self.assertEqual(sorted(prunable for _, prunable in hv03.worktrees(self.repo)),
                         [False, True])
        data = hv03.scan(self.repo)
        states = sorted(w["state"] for w in data["worktrees"])
        self.assertEqual(states, ["MISSING_WORKTREE", "OBSERVED"])
        summary = hv03.public_summary(data)
        self.assertEqual(summary["incomplete_worktrees"], 1)

if __name__ == "__main__":
    unittest.main()
