"""Screen and internet skills, without a screen or the internet."""

from vector.skills import screen, web


def test_screenshot_scaling_round_trips():
    scale = screen.shrink(2560, 1600)
    assert scale == min(1366 / 2560, 900 / 1600)
    assert screen.shrink(1280, 720) == 1.0                  # small screens aren't enlarged
    x, y = screen.to_screen(2560 * scale / 2, 1600 * scale / 2, scale)  # middle of the screenshot...
    assert abs(x - 1280) <= 1 and abs(y - 800) <= 1        # ...is the middle of the real screen
    assert screen.to_image(1280, 800, scale) == (round(1280 * scale), round(800 * scale))


def test_html_to_text():
    html = """<html><head><title> Hello page </title><style>p{color:red}</style></head>
    <body><nav>Menu</nav><script>var x = 1;</script><h1>Big news</h1>
    <p>First   paragraph &amp; more.</p><p>Second</p></body></html>"""
    title, text = web.html_to_text(html)
    assert title == "Hello page"
    assert "Big news" in text and "First paragraph & more." in text and "Second" in text
    assert "var x" not in text and "color:red" not in text


def test_search_results_parsing():
    html = """
    <div class="result"><h2><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa&rut=x">Example <b>A</b></a></h2>
    <a class="result__snippet" href="#">Snippet   one.</a></div>
    <div class="result"><h2><a class="result__a" href="https://python.org/">Python</a></h2>
    <div class="result__snippet">The language.</div></div>
    <div class="result"><a class="result__a" href="https://duckduckgo.com/y.js?ad=1">Ad</a></div>
    """
    results = web.parse_results(html)
    assert results == [
        {"title": "Example A", "url": "https://example.com/a", "snippet": "Snippet one."},
        {"title": "Python", "url": "https://python.org/", "snippet": "The language."},
    ]


def test_fetch_webpage_reads_text(monkeypatch):
    page = b"<html><title>T</title><body><p>Hello there</p></body></html>"
    monkeypatch.setattr(web, "_get", lambda url, data=None, timeout=20:
                        (page, "text/html; charset=utf-8", "https://x.test/"))
    out = web.fetch_webpage("x.test")
    assert out.startswith("T\nhttps://x.test/") and "Hello there" in out


import os  # noqa: E402

import pytest  # noqa: E402


@pytest.mark.skipif(not os.environ.get("VECTOR_LIVE_WEB_TEST"), reason="needs the real internet")
def test_live_search_and_read():
    for name, engine in web._search_engines("python programming language official site"):
        try:
            found = engine(5)
            print(f"{name}: {len(found)} results", [r["url"] for r in found[:3]])
        except Exception as exc:  # report every engine, even ones that fail
            print(f"{name}: error {exc}")
    results = web.search_web("python programming language official site", 5)
    print(results)
    assert "python.org" in results.lower()
    page = web.fetch_webpage("https://www.python.org", 2000)
    print(page[:300])
    assert "python" in page.lower()


def test_bing_and_lite_parsing():
    import base64

    wrapped = "https://www.bing.com/ck/a?!&&p=abc&u=a1" + base64.urlsafe_b64encode(
        b"https://www.python.org/").decode().rstrip("=") + "&ntb=1"
    bing = f"""<ol id="b_results">
      <li class="b_algo"><h2><a href="{wrapped}">Welcome to <strong>Python</strong>.org</a></h2>
        <div class="b_caption"><p class="b_lineclamp2">The official home of Python.</p></div></li>
      <li class="b_ad"><a href="https://www.bing.com/aclick?ad">Ad</a></li>
      <li class="b_algo"><h2><a href="https://docs.python.org/3/">Python docs</a></h2><p>Docs.</p></li>
    </ol>"""
    assert web.parse_bing(bing) == [
        {"title": "Welcome to Python.org", "url": "https://www.python.org/",
         "snippet": "The official home of Python."},
        {"title": "Python docs", "url": "https://docs.python.org/3/", "snippet": "Docs."},
    ]
    lite = """<table><tr><td><a rel="nofollow" href="https://www.python.org/" class='result-link'>Python</a></td></tr>
    <tr><td class='result-snippet'>Official site.</td></tr></table>"""
    assert web.parse_lite(lite) == [
        {"title": "Python", "url": "https://www.python.org/", "snippet": "Official site."}]


def test_search_falls_back_to_the_next_engine(monkeypatch):
    calls = []

    def fake_get(url, data=None, timeout=20):
        calls.append(url)
        if "html.duckduckgo" in url:
            return b"<html>anomaly - are you a robot?</html>", "text/html", url
        return (b'<li class="b_algo"><h2><a href="https://python.org/">Python</a></h2><p>Hi</p></li>',
                "text/html", url)

    monkeypatch.setattr(web, "_get", fake_get)
    out = web.search_web("python")
    assert out.startswith("Results from Bing") and "https://python.org/" in out
    assert len(calls) == 2
