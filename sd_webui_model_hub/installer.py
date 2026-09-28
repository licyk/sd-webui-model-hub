"""Small, idempotent launcher installer, without importing the model hub."""

import re
from pathlib import Path

from .package_analyzer import evaluate_marker, get_parse_bindings, is_package_installed, parse_requirement


def install_requirements(path: Path, run_pip) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = re.sub(r"(^|\s+)#.*$", "", line).strip()
        if not line or not evaluate_marker(parse_requirement(line, get_parse_bindings()).marker):
            continue
        if is_package_installed(line):
            continue
        # The requirements file is shipped with the extension, not user input.
        run_pip(f'install "{line}"', f"SD Model Hub: {line}")
