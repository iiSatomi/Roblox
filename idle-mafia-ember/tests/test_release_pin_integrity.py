"""Release pins must authenticate Git blob bytes, including their line endings."""
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def committed_files(commit):
    data = subprocess.check_output(['git', 'archive', commit, 'idle-mafia-ember'], cwd=ROOT.parent)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        return {member.name.removeprefix('idle-mafia-ember/'): archive.extractfile(member).read()
                for member in archive.getmembers() if member.isfile()}


class ReleasePinIntegrityTests(unittest.TestCase):
    def test_every_manifest_hash_matches_exact_committed_source(self):
        manifest = json.loads((ROOT / 'manifest.json').read_bytes())
        files = committed_files(manifest['releaseCommit'])
        entries = {row['path']: row['sha256'] for row in manifest['modules']}
        self.assertEqual(set(entries), {path for path in files if path.startswith('src/') and path.endswith('.luau')})
        mismatches = [path for path, digest in entries.items()
                      if hashlib.sha256(files[path]).hexdigest() != digest]
        self.assertEqual(mismatches, [], 'Manifest hashes must use Git bytes, not text-normalized working files')

    def test_both_entries_pin_the_same_exact_source_and_manifest_bytes(self):
        working_manifest = json.loads((ROOT / 'manifest.json').read_bytes())
        for name in ('RuntimeEntry.luau', 'TestEntry.luau'):
            with self.subTest(entry=name):
                entry = (ROOT / name).read_text(encoding='utf-8')
                source = re.search(r'local sourceCommit = "([a-f0-9]{40})"', entry).group(1)
                manifest_commit = re.search(r'local manifestCommit = "([a-f0-9]{40})"', entry).group(1)
                self.assertEqual(source, working_manifest['releaseCommit'])
                files = committed_files(source)
                for path, digest in re.findall(r'pinnedModule\("([^\"]+)", "([a-f0-9]{64})"\)', entry):
                    self.assertEqual(hashlib.sha256(files[path]).hexdigest(), digest, name + ': ' + path)
                manifest_bytes = committed_files(manifest_commit)['manifest.json']
                expected = re.search(r'project \.\. "manifest.json",\s*"([a-f0-9]{64})"', entry).group(1)
                self.assertEqual(hashlib.sha256(manifest_bytes).hexdigest(), expected)
                self.assertEqual(json.loads(manifest_bytes), working_manifest)
