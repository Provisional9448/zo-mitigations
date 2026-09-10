#!/usr/bin/env python3
"""Offline, non-overwriting installer for an isolated mitigation package."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


ROOT = Path(__file__).resolve().parent
CONTENT = ("zo_mitigations", "tests", "docs", "examples", "README.md", "PRIVACY.md", "install.py", ".gitignore")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    result = []
    for name in CONTENT:
        source = ROOT / name
        if source.is_symlink():
            raise ValueError("Package symlinks are not supported")
        if not source.exists():
            raise ValueError(f"Missing package content: {name}")
        candidates = sorted(source.rglob("*")) if source.is_dir() else [source]
        for candidate in candidates:
            if candidate.is_symlink():
                raise ValueError("Package symlinks are not supported")
            if "__pycache__" in candidate.parts or candidate.suffix == ".pyc":
                continue
            if candidate.is_file():
                relative = candidate.relative_to(ROOT)
                if relative.name != ".gitignore" and (any(part.startswith(".") for part in relative.parts) or candidate.suffix not in {".py", ".md", ".json"}):
                    raise ValueError(f"Unexpected package file: {relative}")
                result.append(candidate)
    return result


def install(destination, apply=False):
    if destination.exists() or destination.is_symlink():
        raise ValueError("Destination exists; choose a new versioned install directory")
    files = sources()
    manifest = {str(path.relative_to(ROOT)): digest(path) for path in files}
    if apply:
        if not destination.parent.is_dir():
            raise ValueError("Destination parent must already exist")
        temporary = Path(tempfile.mkdtemp(prefix=".mitigations-install-", dir=destination.parent))
        try:
            for path in files:
                target = temporary / path.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                target.chmod(0o600)
            (temporary / "install-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            (temporary / "install-manifest.json").chmod(0o600)
            temporary.rename(destination)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    return {"operation": "install", "applied": apply, "destination": str(destination), "files": manifest}


def uninstall(destination, apply=False):
    if destination.is_symlink():
        raise ValueError("Refusing a symlink destination")
    manifest_file = destination / "install-manifest.json"
    manifest = json.loads(manifest_file.read_text())
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError("Invalid manifest")
    owned = []
    for relative, expected in manifest.items():
        name = Path(relative)
        if name.is_absolute() or ".." in name.parts:
            raise ValueError("Invalid manifest path")
        path = destination / name
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != destination.parent):
            raise ValueError("Refusing a symlink in installed content")
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"Installed file changed or missing: {relative}; preserve and reconcile manually")
        owned.append(path)
    if apply:
        for path in owned:
            path.unlink()
        manifest_file.unlink()
        directories = {parent for path in owned for parent in path.parents if parent != destination and destination in parent.parents}
        for path in sorted(directories, key=lambda path: len(path.parts), reverse=True):
            if path.is_dir() and not path.is_symlink():
                try:
                    path.rmdir()
                except OSError:
                    pass
        try:
            destination.rmdir()
        except OSError:
            pass
    return {"operation": "uninstall", "applied": apply, "destination": str(destination), "owned_files": len(owned), "untracked_data": "preserved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["install", "uninstall"])
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="Apply; otherwise only describe the operation")
    args = parser.parse_args()
    destination = args.destination.absolute()
    if destination == Path("/") or destination == Path.home() or destination == ROOT:
        parser.error("Choose a dedicated installation directory")
    try:
        result = (install if args.operation == "install" else uninstall)(destination, args.apply)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
