"""Verify real published-entry pins against raw committed blobs, never fixtures."""
import hashlib
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from engine_harness import Harness


ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "491ca8967867a50b4170ccd852da6257f4777ab8"
MANIFEST_COMMIT = "8df2342c0118e11c048661759fa61d6988da4ae2"
EMBER_SHA256 = "0aebb331911619d0c791de1d0d3e9b2e51ead3fb4472cd038807155ad8bcf412"
FINGERPRINT = "7032df7733506f1f80739faca9c9d66d688d6d5a38b2a506b1e8de1fd6c22c78"
BOOTSTRAP_PATHS = {"Loader.luau", "src/loader/Manifest.luau", "Bootstrap.luau",
                   "ReleaseAdapters.luau", "ExecutorEntry.luau"}


def git(*args, input=None):
    return subprocess.run(
        [shutil.which("git") or "C:/Program Files/Git/cmd/git.exe", "-c",
         "safe.directory=" + ROOT.parent.as_posix(), *args], cwd=ROOT,
        input=input, check=True, capture_output=True).stdout


def blobs(commit, paths):
    """Git's batch protocol preserves CRLF and avoids one process per module."""
    requests = [commit + ":idle-mafia-ember/" + path for path in paths]
    data = git("cat-file", "--batch", input=("\n".join(requests) + "\n").encode())
    result, offset = {}, 0
    for path in paths:
        end = data.index(b"\n", offset)
        _, kind, length = data[offset:end].split()
        if kind != b"blob":
            raise AssertionError("Not a committed blob: " + path)
        start, size = end + 1, int(length)
        result[path] = data[start:start + size]
        if data[start + size:start + size + 1] != b"\n":
            raise AssertionError("Invalid Git batch boundary")
        offset = start + size + 1
    if offset != len(data):
        raise AssertionError("Unexpected Git batch data")
    return result


class EntryReleasePinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest_bytes = blobs(MANIFEST_COMMIT, ["manifest.json"])["manifest.json"]
        cls.manifest = json.loads(cls.manifest_bytes)
        cls.paths = [row["path"] for row in cls.manifest["modules"]]
        cls.sources = blobs(SOURCE_COMMIT, cls.paths + sorted(BOOTSTRAP_PATHS - set(cls.paths))
                            + ["preview/catalog.json"])
        cls.features = {row["id"] for row in json.loads(cls.sources["preview/catalog.json"])["features"]}

    def test_both_entries_pin_the_exact_reviewed_source_manifest_bootstrap_and_dependency(self):
        for name in ("RuntimeEntry.luau", "TestEntry.luau"):
            with self.subTest(entry=name):
                source = (ROOT / name).read_text(encoding="utf-8")
                self.assertEqual(re.search(r'local sourceCommit = "([^"]+)"', source)[1], SOURCE_COMMIT)
                self.assertEqual(re.search(r'local manifestCommit = "([^"]+)"', source)[1], MANIFEST_COMMIT)
                actual = dict(re.findall(r'pinnedModule\("([^"]+)", "([0-9a-f]{64})"\)', source))
                self.assertEqual(set(actual), BOOTSTRAP_PATHS)
                for path, expected in actual.items():
                    self.assertEqual(hashlib.sha256(self.sources[path]).hexdigest(), expected, path)
                manifest_hash = re.search(r'"manifest.json",\s*"([0-9a-f]{64})"', source)[1]
                self.assertEqual(manifest_hash, hashlib.sha256(self.manifest_bytes).hexdigest())
                self.assertEqual(re.search(r'"https://rbx.lol/ember.lua",\s*"([0-9a-f]{64})"', source)[1], EMBER_SHA256)
                self.assertIn('place = "73897506680154", gameVersion = "0.26.645.1"', source)
                self.assertIn('fingerprint = "' + FINGERPRINT + '"', source)
                self.assertIn('directory = "IdleMafiaEmber"', source)

    def test_manifest_exactly_covers_all_committed_modules_and_hashes_raw_bytes(self):
        self.assertEqual(self.manifest["releaseCommit"], SOURCE_COMMIT)
        self.assertEqual(self.manifest["schema"], 1)
        self.assertEqual(len(self.paths), 298)
        committed = set(git("ls-tree", "--full-tree", "-r", "--name-only", SOURCE_COMMIT, "--",
                            "idle-mafia-ember/src").decode().splitlines())
        self.assertEqual({"idle-mafia-ember/" + p for p in self.paths}, committed)
        self.assertEqual(len({row["id"] for row in self.manifest["modules"]}), len(self.paths))
        self.assertEqual(self.manifest["modules"][-1]["id"], "App")
        for row in self.manifest["modules"]:
            self.assertEqual(hashlib.sha256(self.sources[row["path"]]).hexdigest(), row["sha256"], row["path"])

    def test_runtime_exposes_all_catalog_permissions_with_committed_switch_defaults_off_and_test_entry_inert(self):
        runtime = (ROOT / "RuntimeEntry.luau").read_text(encoding="utf-8")
        body = re.search(r'allowedFeatures = \{([^}]+)\}', runtime)[1]
        entries = re.findall(r'([A-Za-z][A-Za-z0-9_]*)\s*=\s*true', body)
        self.assertEqual(len(entries), 55)
        self.assertEqual(len(entries), len(set(entries)))
        self.assertEqual(set(entries), self.features)
        self.assertEqual(re.sub(r'[\s,]+', '', re.sub(r'[A-Za-z][A-Za-z0-9_]*\s*=\s*true', '', body)), '')
        self.assertRegex(runtime, r'},\s*true\)\s*assert\(app,')
        smoke = (ROOT / "TestEntry.luau").read_text(encoding="utf-8")
        self.assertRegex(smoke, r'},\s*false\)\s*assert\(app,')
        h = Harness()
        catalog = h.lua.execute(self.sources["src/ui/Catalog.luau"].decode())
        model = h.lua.execute(self.sources["src/storage/Settings.luau"].decode()).new(catalog, True)
        self.assertEqual(len(catalog.pages), 26)
        self.assertFalse(model.paused)
        self.assertEqual({key[:-8] for key, value in model["values"].items()
                          if key.endswith(".enabled") and value is False}, self.features)


if __name__ == "__main__":
    unittest.main()
