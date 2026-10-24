"""Create a complete, commit-pinned Luau manifest from committed source bytes.

This intentionally refuses uncommitted or missing source. It prepares a release
manifest but does not fetch, execute, publish, or start any game action.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


PROJECT = Path(__file__).resolve().parents[1]


def git(repo, *args):
    result = subprocess.run(["git", *args], cwd=repo, check=True,
                            capture_output=True)
    return result.stdout


def module_id(relative):
    path = Path(relative)
    if path.name == "Module.luau" and len(path.parts) == 4 \
            and path.parts[:2] == ("src", "tabs"):
        return path.parts[2][0].upper() + path.parts[2][1:] + "Tab"
    return path.stem


def scan_sources(project):
    project = Path(project).resolve()
    paths = sorted(p.relative_to(project).as_posix()
                   for p in (project / "src").rglob("*.luau") if p.is_file())
    if not paths:
        raise ValueError("No Luau sources")
    if len(paths) > 256:
        raise ValueError("Manifest exceeds loader module limit")
    seen = set()
    for path in paths:
        name = module_id(path)
        if name in seen:
            raise ValueError("Duplicate module ID: " + name)
        seen.add(name)
    if "App" not in seen or "EmberAdapter" not in seen:
        raise ValueError("Required application modules missing")
    return paths


def build(project, commit):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("A full lowercase Git commit SHA is required")
    project = Path(project).resolve()
    repo = Path(git(project, "rev-parse", "--show-toplevel").decode().strip())
    resolved = git(repo, "rev-parse", "--verify", commit + "^{commit}").decode().strip()
    if resolved != commit:
        raise ValueError("Commit pin does not resolve exactly")
    prefix = project.relative_to(repo).as_posix() + "/"
    paths = scan_sources(project)
    committed = {name for name in git(repo, "ls-tree", "-r", "--name-only", "-z",
                        commit, "--", prefix + "src").decode().split("\0")
                 if name.endswith(".luau")}
    if {prefix + p for p in paths} != committed:
        raise ValueError("Committed source list differs from working tree")
    entries, ids = [], set()
    for path in paths:
        name = module_id(path)
        if name in ids:
            raise ValueError("Duplicate module ID: " + name)
        ids.add(name)
        source = (project / path).read_bytes()
        pinned = git(repo, "show", commit + ":" + prefix + path)
        if source != pinned:
            raise ValueError("Working source differs from commit: " + path)
        entries.append({"id": name, "path": path,
                        "sha256": hashlib.sha256(source).hexdigest(), "deps": []})
    entries.sort(key=lambda row: (row["id"] == "App", row["path"]))
    return {"schema": 1, "releaseCommit": commit, "modules": entries}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", help="Exact 40-character release commit")
    parser.add_argument("--preflight", action="store_true",
                        help="Check working-tree module IDs without a commit")
    parser.add_argument("--project", type=Path, default=PROJECT)
    parser.add_argument("--output", type=Path, default=PROJECT / "manifest.json")
    args = parser.parse_args()
    if args.preflight:
        if args.commit:
            parser.error("Choose --preflight or --commit")
        paths = scan_sources(args.project)
        print(f"Scanned {len(paths)} Luau modules; IDs are unique")
        return
    if not args.commit:
        parser.error("--commit is required unless --preflight is used")
    manifest = build(args.project, args.commit)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Pinned {len(manifest['modules'])} modules to {args.commit}")


if __name__ == "__main__":
    main()
