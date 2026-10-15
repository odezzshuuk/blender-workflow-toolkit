"""Build an installable extension ZIP using only Python's standard library."""

from pathlib import Path
import tomllib
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    root = Path(__file__).resolve().parents[1]
    source = root / "blender_workflow_toolkit"
    manifest = tomllib.loads((source / "blender_manifest.toml").read_text())
    destination = root / "dist"
    destination.mkdir(exist_ok=True)
    archive = destination / f"{manifest['id']}-{manifest['version']}.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
                continue
            if path.is_file() and path.suffix not in {".pyc", ".zip"}:
                bundle.write(path, relative)
    print(archive)


if __name__ == "__main__":
    main()
