"""A release must include exact committed Luau bytes, including each tab."""
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("git"):
            self.skipTest("Git unavailable")
        spec = importlib.util.spec_from_file_location(
            "manifest_builder", ROOT / "tools/build_release_manifest.py")
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.project = self.repo / "idle-mafia-ember"
        for path, body in {
            "src/App.luau": b"return {start=function() return {} end}",
            "src/ui/EmberAdapter.luau": b"return {}",
            "src/tabs/jobs/Module.luau": b"return {}",
        }.items():
            target = self.project / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "-qm", "fixture")
        self.commit = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo,
                              check=True, capture_output=True, text=True).stdout

    def test_manifest_contains_exact_committed_modules(self):
        manifest = self.builder.build(self.project, self.commit)
        self.assertEqual(manifest["releaseCommit"], self.commit)
        self.assertEqual({entry["id"] for entry in manifest["modules"]},
                         {"App", "EmberAdapter", "JobsTab"})
        self.assertEqual(manifest["modules"][-1]["id"], "App")
        source = (self.project / "src/App.luau").read_bytes()
        self.assertEqual(manifest["modules"][-1]["sha256"],
                         hashlib.sha256(source).hexdigest())

    def test_dirty_or_uncommitted_module_is_rejected(self):
        target = self.project / "src/App.luau"
        target.write_bytes(target.read_bytes() + b" -- dirty")
        with self.assertRaisesRegex(ValueError, "differs from commit"):
            self.builder.build(self.project, self.commit)
        target.write_bytes(b"return {start=function() return {} end}")
        (self.project / "src/tabs/jobs/Extra.luau").write_bytes(b"return {}")
        with self.assertRaisesRegex(ValueError, "source list differs"):
            self.builder.build(self.project, self.commit)

    def test_abbreviated_or_invented_pin_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "full lowercase"):
            self.builder.build(self.project, self.commit[:12])

    def test_working_tree_preflight_detects_duplicate_ids_before_commit(self):
        self.assertEqual({self.builder.module_id(path)
            for path in self.builder.scan_sources(self.project)},
            {"App", "EmberAdapter", "JobsTab"})
        for path in ("src/features/Collision.luau",
                     "src/game/Collision.luau"):
            target = self.project / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"return {}")
        with self.assertRaisesRegex(ValueError, "Duplicate module ID"):
            self.builder.scan_sources(self.project)


if __name__ == "__main__":
    unittest.main()
