"""Keep the extension's toolbar separate from the embedded model manager."""

import sys
from html.parser import HTMLParser
from types import SimpleNamespace

from sd_webui_model_hub.host import access_urls, on_ui_tabs


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


def test_access_urls_for_the_start_up_log():
    def host(cmd, demo=None, **options):
        return demo, SimpleNamespace(cmd_opts=SimpleNamespace(**cmd), opts=SimpleNamespace(data=options))

    assert access_urls(*host({}, SimpleNamespace(server_port=7861))) == ["http://127.0.0.1:7861/sd-model-hub/"]
    # A wildcard bind is opened through the loopback address; --subpath is stripped by the proxy.
    assert access_urls(*host({"listen": True, "port": 9000, "subpath": "webui"})) == ["http://127.0.0.1:9000/sd-model-hub/"]
    assert access_urls(*host({"server_name": "::1"})) == ["http://[::1]:7860/sd-model-hub/"]
    demo, shared = host(
        {"share": True}, SimpleNamespace(server_port=7860, share_url="https://abc.gradio.live/"), model_hub_public_url="https://example.com/webui/sd-model-hub"
    )
    assert access_urls(demo, shared) == [
        "http://127.0.0.1:7860/sd-model-hub/",
        "https://abc.gradio.live/sd-model-hub/",
        "https://example.com/webui/sd-model-hub/",
    ]
