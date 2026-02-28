"""Test that extractors decode HTML entities in titles."""
import html


def test_html_unescape_smart_quotes():
    raw = "We don&#8217;t have to have unsupervised killer robots"
    assert html.unescape(raw) == "We don\u2019t have to have unsupervised killer robots"


def test_html_unescape_amp():
    raw = "ML &amp; AI"
    assert html.unescape(raw) == "ML & AI"


def test_html_unescape_noop():
    raw = "Normal title without entities"
    assert html.unescape(raw) == raw
