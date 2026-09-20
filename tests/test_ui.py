"""Keep the extension's toolbar separate from the embedded model manager."""

import sys
from html.parser import HTMLParser
from types import SimpleNamespace

from sd_webui_model_hub.host import on_ui_tabs


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []

    def handle_starttag(self, tag, attrs):
        self.items.append((tag, dict(attrs)))


def test_tab_has_no_toolbar_and_hides_normal_status(monkeypatch):
    html = []

    class Blocks:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setitem(sys.modules, "gradio", SimpleNamespace(Blocks=Blocks, HTML=html.append))
    tabs = on_ui_tabs()
    assert tabs[0][1:] == ("Model Hub", "sd_model_hub")
    elements = Elements()
    elements.feed(html[0])
    actions = [attrs["data-action"] for _, attrs in elements.items if "data-action" in attrs]
    assert actions == []
    assert not any(tag in {"button", "a"} for tag, _ in elements.items)
    assert not any(tag == "details" for tag, _ in elements.items)
    status = next(attrs for _, attrs in elements.items if attrs.get("class") == "model-hub-status")
    assert "hidden" in status
    assert "正在连接" not in html[0] and "已连接" not in html[0]
    assert any(tag == "iframe" for tag, _ in elements.items)
