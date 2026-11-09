import io
import json
import threading
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from stonks.services import yahoo_api


@pytest.fixture(autouse=True)
def reset_session():
    yahoo_api._opener = None
    yahoo_api._crumb = None
    yield
    yahoo_api._opener = None
    yahoo_api._crumb = None


def _response(payload: dict):
    return io.BytesIO(json.dumps(payload).encode())


def _unauthorized():
    return urllib.error.HTTPError("url", 401, "Unauthorized", {}, None)


def _opener(*responses):
    opener = MagicMock()
    opener.open.side_effect = list(responses)
    return opener


def test_request_reuses_session_across_calls():
    opener = _opener(_response({"a": 1}), _response({"b": 2}))
    with patch.object(yahoo_api, "_fetch_fresh_session", return_value=(opener, "c1")) as fresh:
        assert yahoo_api._request("https://x") == {"a": 1}
        assert yahoo_api._request("https://x") == {"b": 2}
    fresh.assert_called_once()


def test_request_refreshes_session_once_on_401_and_retries():
    stale = _opener(_unauthorized())
    fresh_opener = _opener(_response({"ok": True}))
    with patch.object(
        yahoo_api, "_fetch_fresh_session", side_effect=[(stale, "old"), (fresh_opener, "new")]
    ):
        assert yahoo_api._request("https://x", {"q": "AAPL"}) == {"ok": True}
    retried_url = fresh_opener.open.call_args.args[0].full_url
    assert "crumb=new" in retried_url
    assert "q=AAPL" in retried_url
    assert yahoo_api._crumb == "new"


def test_request_does_not_refresh_again_if_another_thread_already_did():
    yahoo_api._opener, yahoo_api._crumb = _opener(_response({"ok": True})), "newer"
    with patch.object(yahoo_api, "_fetch_fresh_session") as fresh:
        opener, crumb = yahoo_api._session(stale_crumb="older")
    fresh.assert_not_called()
    assert crumb == "newer"


def test_request_propagates_non_401_errors():
    err = urllib.error.HTTPError("url", 500, "Server Error", {}, None)
    with patch.object(yahoo_api, "_fetch_fresh_session", return_value=(_opener(err), "c")):
        with pytest.raises(urllib.error.HTTPError):
            yahoo_api._request("https://x")


def test_request_with_body_posts_json():
    opener = _opener(_response({"ok": True}))
    with patch.object(yahoo_api, "_fetch_fresh_session", return_value=(opener, "c")):
        yahoo_api._request("https://x", {"k": "v"}, body={"a": 1})
    req = opener.open.call_args.args[0]
    assert req.get_method() == "POST"
    assert json.loads(req.data) == {"a": 1}


def test_concurrent_requests_share_a_single_session_fetch():
    def make_opener():
        opener = MagicMock()
        opener.open.side_effect = lambda *_a, **_k: _response({"ok": True})
        return opener

    with patch.object(
        yahoo_api, "_fetch_fresh_session", side_effect=lambda: (make_opener(), "c")
    ) as fresh:
        threads = [
            threading.Thread(target=yahoo_api._request, args=("https://x",)) for _ in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    fresh.assert_called_once()
