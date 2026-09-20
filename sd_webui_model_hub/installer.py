"""Small, idempotent launcher installer, without importing the model hub."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from packaging.requirements import Requirement


def install_requirements(path: Path, run_pip) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        requirement = Requirement(line)
        if requirement.marker and not requirement.marker.evaluate():
            continue
        try:
            installed = version(requirement.name)
        except PackageNotFoundError:
            installed = None
        if installed is not None and requirement.specifier.contains(installed):
            continue
        # The requirements file is shipped with the extension, not user input.
        run_pip(f'install "{requirement}"', f"SD Model Hub: {requirement}")
