import pytest

from rate_limit import SlidingWindow, client_key, parse_spec


class FakeRequest:
    def __init__(self, headers=None, host="1.2.3.4"):
        self.headers = headers or {}
        self.client = type("C", (), {"host": host})() if host else None


class TestParseSpec:
    @pytest.mark.parametrize("spec,expected", [
        ("5/hour", (5, 3600)),
        ("10/minute", (10, 60)),
        ("2/second", (2, 1)),
        ("100/day", (100, 86400)),
        (" 7 / HOUR ", (7, 3600)),
    ])
    def test_parses_valid_specs(self, spec, expected):
        assert parse_spec(spec) == expected

    @pytest.mark.parametrize("spec", ["5", "5/fortnight", "hour/5", "", "-1/hour"])
    def test_rejects_invalid_specs(self, spec):
        with pytest.raises(ValueError):
            parse_spec(spec)


class TestSlidingWindow:
    def test_allows_up_to_the_limit(self):
        window = SlidingWindow(limit=3, window_seconds=60)
        assert [window.check("a", now=100.0)[0] for _ in range(3)] == [True, True, True]

    def test_blocks_past_the_limit(self):
        window = SlidingWindow(limit=2, window_seconds=60)
        window.check("a", now=100.0)
        window.check("a", now=100.0)
        allowed, retry_after = window.check("a", now=100.0)
        assert allowed is False
        assert retry_after > 0

    def test_clients_are_tracked_independently(self):
        window = SlidingWindow(limit=1, window_seconds=60)
        assert window.check("a", now=100.0)[0] is True
        assert window.check("b", now=100.0)[0] is True
        assert window.check("a", now=100.0)[0] is False

    def test_window_slides_so_old_hits_stop_counting(self):
        window = SlidingWindow(limit=1, window_seconds=60)
        assert window.check("a", now=100.0)[0] is True
        assert window.check("a", now=130.0)[0] is False
        assert window.check("a", now=161.0)[0] is True

    def test_retry_after_shrinks_as_the_window_advances(self):
        window = SlidingWindow(limit=1, window_seconds=60)
        window.check("a", now=100.0)
        early = window.check("a", now=110.0)[1]
        later = window.check("a", now=150.0)[1]
        assert later < early

    def test_sweep_drops_cold_keys(self):
        window = SlidingWindow(limit=5, window_seconds=60)
        window.check("a", now=100.0)
        assert window.sweep(now=200.0) == 1
        assert window._hits == {}

    def test_sweep_keeps_active_keys(self):
        window = SlidingWindow(limit=5, window_seconds=60)
        window.check("a", now=100.0)
        assert window.sweep(now=120.0) == 0


class TestClientKey:
    def test_falls_back_to_socket_peer_without_a_forwarded_header(self):
        assert client_key(FakeRequest(host="9.9.9.9")) == "9.9.9.9"

    def test_reads_the_hop_added_by_our_own_proxy(self, monkeypatch):
        import rate_limit

        monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS", 1)
        request = FakeRequest({"x-forwarded-for": "203.0.113.9"})
        assert client_key(request) == "203.0.113.9"

    def test_ignores_spoofed_entries_further_left(self, monkeypatch):
        import rate_limit

        monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS", 1)
        # A client can prepend anything it likes; only the rightmost hop was
        # written by infrastructure we control.
        request = FakeRequest({"x-forwarded-for": "evil-spoof, 203.0.113.9"})
        assert client_key(request) == "203.0.113.9"

    def test_header_is_ignored_when_no_proxy_is_trusted(self, monkeypatch):
        import rate_limit

        monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS", 0)
        request = FakeRequest({"x-forwarded-for": "203.0.113.9"}, host="9.9.9.9")
        assert client_key(request) == "9.9.9.9"

    def test_handles_a_request_with_no_client(self):
        assert client_key(FakeRequest(host=None)) == "unknown"
