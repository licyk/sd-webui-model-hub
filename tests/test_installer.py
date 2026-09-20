from importlib.metadata import PackageNotFoundError
from unittest.mock import Mock

import pytest

from sd_webui_model_hub import installer


@pytest.mark.parametrize("installed,needs_install", [("0.1.1", False), ("0.1.10", False), ("0.1.0", True), ("0.2.0", True), (None, True)])
def test_semantic_versions_and_missing_package(tmp_path, monkeypatch, installed, needs_install):
    path = tmp_path / "requirements.txt"
    path.write_text('# comment\n\nsd-model-hub>=0.1.1,<0.2\nnot-needed; python_version < "3.0"\n')

    def version(_name):
        if installed is None:
            raise PackageNotFoundError
        return installed

    monkeypatch.setattr(installer, "version", version)
    pip = Mock()
    installer.install_requirements(path, pip)
    assert pip.call_count == int(needs_install)
    if needs_install:
        command = pip.call_args.args[0]
        assert "sd-model-hub" in command and "--upgrade" not in command
