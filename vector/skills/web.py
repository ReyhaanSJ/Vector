"""The internet: search the web and read pages yourself (nothing opens in the browser),
and download files."""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from vector.registry import tool

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/140.0 Safari/537.36 VECTOR")
SKIP = {"script", "style", "noscript", "svg", "template", "iframe", "head"}
BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article",
         "header", "footer", "pre", "blockquote", "table", "ul", "ol"}


def _get(url: str, data: bytes | None = None, timeout: int = 20) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
        **({"Content-Type": "application/x-www-form-urlencoded"} if data else {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(5_000_000), resp.headers.get("Content-Type", ""), resp.geturl()


class _Text(HTMLParser):
    """Readable text from a web page: drops scripts/menus clutter, keeps paragraphs."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag in BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in raw.split("\n")]
        out, blank = [], 0
        for ln in lines:
            blank = blank + 1 if not ln else 0
            if blank <= 1:
                out.append(ln)
        return "\n".join(out).strip()


def html_to_text(html: str) -> tuple[str, str]:
    parser = _Text()
    parser.feed(html)
    return parser.title.strip(), parser.text()


def _decode(body: bytes, content_type: str) -> str:
    match = re.search(r"charset=([\w-]+)", content_type)
    return body.decode(match.group(1) if match else "utf-8", errors="replace")


@tool
def fetch_webpage(url: str, max_chars: int = 8000) -> str:
    """Read a web page (or any text/JSON at a URL) and return its text, so you can answer from it.

    url: The address, e.g. "https://en.wikipedia.org/wiki/Python".
    max_chars: Only return this many characters.
    """
    if "://" not in url:
        url = "https://" + url
    try:
        body, ctype, final = _get(url)
    except urllib.error.HTTPError as exc:
        return f"The site answered with error {exc.code} for {url}."
    except (urllib.error.URLError, OSError) as exc:
        return f"Couldn't open {url}: {getattr(exc, 'reason', exc)}"
    text = _decode(body, ctype)
    if "html" in ctype or text.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        title, text = html_to_text(text)
        header = f"{title}\n{final}\n\n" if title else f"{final}\n\n"
    else:
        header = f"{final}\n\n"
    if not text.strip():
        return f"{final} has no readable text (it may need a browser to load)."
    cut = text[:max_chars] + ("\n... (cut short)" if len(text) > max_chars else "")
    return header + cut


class _Results(HTMLParser):
    """Results from DuckDuckGo's plain-HTML page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results: list[dict] = []
        self._field = None

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class") or ""
        if tag == "a" and "result__a" in cls:
            href = dict(attrs).get("href") or ""
            self.results.append({"title": "", "url": clean_result_url(href), "snippet": ""})
            self._field = "title"
        elif "result__snippet" in cls and self.results:
            self._field = "snippet"

    def handle_endtag(self, tag):
        if tag in ("a", "td", "div") and self._field:
            self._field = None

    def handle_data(self, data):
        if self._field and self.results:
            self.results[-1][self._field] += data


def clean_result_url(href: str) -> str:
    """Unwrap search-engine redirect links to the real address:
    DuckDuckGo //duckduckgo.com/l/?uddg=<url>, Bing bing.com/ck/a?...&u=a1<base64 url>."""
    import base64

    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    query = urllib.parse.parse_qs(parsed.query)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/") and query.get("uddg"):
        return query["uddg"][0]
    if "bing.com" in parsed.netloc and parsed.path.startswith("/ck/") and query.get("u"):
        code = query["u"][0]
        if code.startswith("a1"):
            code = code[2:]
            try:
                return base64.urlsafe_b64decode(code + "=" * (-len(code) % 4)).decode()
            except (ValueError, UnicodeDecodeError):
                pass
    return href


def parse_results(html: str, limit: int = 8) -> list[dict]:
    parser = _Results()
    parser.feed(html)
    out = []
    for r in parser.results:
        r = {k: " ".join(v.split()) for k, v in r.items()}
        if r["url"].startswith("http") and "duckduckgo.com/y.js" not in r["url"]:
            out.append(r)
    return out[:limit]


class _Bing(HTMLParser):
    """Results from Bing's normal results page (li.b_algo blocks)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results: list[dict] = []
        self._in_result = 0
        self._in_h2 = False
        self._field = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "li" and "b_algo" in (a.get("class") or ""):
            self._in_result = 1
            self.results.append({"title": "", "url": "", "snippet": ""})
            return
        if not self._in_result:
            return
        if tag == "li":
            self._in_result += 1
        if tag == "h2":
            self._in_h2 = True
        elif tag == "a" and self._in_h2 and not self.results[-1]["url"]:
            self.results[-1]["url"] = clean_result_url(a.get("href") or "")
            self._field = "title"
        elif tag == "p" and not self.results[-1]["snippet"]:
            self._field = "snippet"

    def handle_endtag(self, tag):
        if not self._in_result:
            return
        if tag == "h2":
            self._in_h2 = False
        if tag in ("a", "p"):
            self._field = None
        if tag == "li":
            self._in_result -= 1

    def handle_data(self, data):
        if self._field and self.results:
            self.results[-1][self._field] += data


class _Lite(HTMLParser):
    """Results from DuckDuckGo Lite (a.result-link + td.result-snippet)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results: list[dict] = []
        self._field = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        if tag == "a" and "result-link" in cls:
            self.results.append({"title": "", "url": clean_result_url(a.get("href") or ""),
                                 "snippet": ""})
            self._field = "title"
        elif tag == "td" and "result-snippet" in cls and self.results:
            self._field = "snippet"

    def handle_endtag(self, tag):
        if tag in ("a", "td"):
            self._field = None

    def handle_data(self, data):
        if self._field and self.results:
            self.results[-1][self._field] += data


def _tidy(results: list[dict], limit: int) -> list[dict]:
    out, seen = [], set()
    for r in results:
        r = {k: " ".join(v.split()) for k, v in r.items()}
        url = r["url"]
        if not url.startswith("http") or url in seen or "duckduckgo.com/y.js" in url:
            continue
        if "bing.com/aclick" in url or not r["title"]:
            continue
        seen.add(url)
        out.append(r)
    return out[:limit]


def parse_bing(html: str, limit: int = 8) -> list[dict]:
    parser = _Bing()
    parser.feed(html)
    return _tidy(parser.results, limit)


def parse_lite(html: str, limit: int = 8) -> list[dict]:
    parser = _Lite()
    parser.feed(html)
    return _tidy(parser.results, limit)


def _search_engines(query: str):
    """(name, function returning results) in the order to try them."""
    form = urllib.parse.urlencode({"q": query, "kl": "wt-wt"}).encode()

    def ddg(limit):
        body, ctype, _ = _get("https://html.duckduckgo.com/html/", data=form)
        return parse_results(_decode(body, ctype), limit)

    def bing(limit):
        url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query, "setlang": "en"})
        body, ctype, _ = _get(url)
        return parse_bing(_decode(body, ctype), limit)

    def lite(limit):
        body, ctype, _ = _get("https://lite.duckduckgo.com/lite/", data=form)
        return parse_lite(_decode(body, ctype), limit)

    return [("DuckDuckGo", ddg), ("Bing", bing), ("DuckDuckGo Lite", lite)]


@tool
def search_web(query: str, max_results: int = 8) -> str:
    """Search the internet and get the results (titles, links, snippets) to read. Follow up with
    fetch_webpage to read a result in full. Use this for news, facts, prices, how-tos, anything.

    query: What to search for.
    max_results: How many results to return.
    """
    problems = []
    for name, engine in _search_engines(query):
        try:
            results = engine(max_results)
        except (urllib.error.URLError, OSError) as exc:
            problems.append(f"{name}: {getattr(exc, 'reason', exc)}")
            continue
        if results:
            lines = [f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}"
                     for i, r in enumerate(results, 1)]
            return f"Results from {name}:\n\n" + "\n\n".join(lines)
        problems.append(f"{name}: no results")
    return ("Searching didn't work right now (" + "; ".join(problems) + "). Check the internet "
            "connection, try again in a moment, or fetch_webpage a site you know.")


@tool(dangerous=True)
def download_file(url: str, folder: str = "downloads", filename: str = "") -> str:
    """Download a file from the internet and save it.

    url: Link to the file.
    folder: Where to save it (e.g. "downloads", "desktop" or a full path).
    filename: Optional name; defaults to the name in the link.
    """
    from vector.skills.files import resolve

    target_dir = resolve(folder)
    target_dir.mkdir(parents=True, exist_ok=True)
    name = filename or Path(urllib.parse.urlparse(url).path).name or "download"
    target = target_dir / re.sub(r'[<>:"/\\|?*]', "_", name)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as resp, target.open("wb") as fh:
            size = 0
            while chunk := resp.read(1 << 16):
                size += len(chunk)
                if size > 2 * 1024**3:
                    raise OSError("file is bigger than 2 GB")
                fh.write(chunk)
    except (urllib.error.URLError, OSError) as exc:
        target.unlink(missing_ok=True)
        return f"Download failed: {getattr(exc, 'reason', exc)}"
    return f"Saved {target} ({size / 1_048_576:.1f} MB)."
