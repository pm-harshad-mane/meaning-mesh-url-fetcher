"""
Fetch a URL and extract cleaned page text using the provided BeautifulSoup approach.

This module intentionally mirrors the root-level `fetch_with_beautiful_soup.py` helper
and extends it with HTTP status and content type metadata required by the fetcher queue
contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag
from curl_cffi import requests
from curl_cffi.requests.exceptions import HTTPError, RequestException, Timeout

from app.models import PageContent

DEFAULT_REQUEST_TIMEOUT = 9
RETRYABLE_HTTP_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


@dataclass
class FetchFailure(RuntimeError):
    error_code: str
    message: str
    retryable: bool
    status_code: Optional[int] = None
    final_url: Optional[str] = None
    attempt_count: int = 1

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.message)


def _normalize_text(s: str) -> str:
    s = "" if s is None else str(s)
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out


def _build_fetch_failure(exc: Exception) -> FetchFailure:
    if isinstance(exc, Timeout):
        return FetchFailure(
            error_code="FETCH_TIMEOUT",
            message=str(exc) or "Request timed out",
            retryable=True,
        )

    if isinstance(exc, HTTPError):
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        final_url = str(getattr(response, "url", "") or "") or None
        retryable = status_code in RETRYABLE_HTTP_STATUS_CODES
        error_code = "FETCH_HTTP_RETRYABLE_ERROR" if retryable else "FETCH_HTTP_ERROR"
        return FetchFailure(
            error_code=error_code,
            message=str(exc) or f"HTTP error {status_code}",
            retryable=retryable,
            status_code=status_code,
            final_url=final_url,
        )

    if isinstance(exc, RequestException):
        message = str(exc) or exc.__class__.__name__
        normalized = message.lower()
        error_code = "FETCH_REQUEST_ERROR"
        retryable = False

        if "could not resolve host" in normalized:
            error_code = "FETCH_DNS_ERROR"
        elif "timed out" in normalized:
            error_code = "FETCH_TIMEOUT"
            retryable = True
        elif any(
            marker in normalized
            for marker in (
                "connection refused",
                "connection reset",
                "failed to connect",
                "network is unreachable",
                "connection was aborted",
            )
        ):
            error_code = "FETCH_CONNECTION_ERROR"
            retryable = True
        elif "too many redirects" in normalized:
            error_code = "FETCH_TOO_MANY_REDIRECTS"
        elif any(marker in normalized for marker in ("ssl", "tls", "certificate")):
            error_code = "FETCH_TLS_ERROR"

        return FetchFailure(
            error_code=error_code,
            message=message,
            retryable=retryable,
        )

    return FetchFailure(
        error_code="FETCH_UNKNOWN_ERROR",
        message=str(exc) or exc.__class__.__name__,
        retryable=False,
    )


def _fetch_url_response(url: str, timeout: int):
    headers = {"Accept-Language": "en-US,en;q=0.9"}
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            impersonate="chrome",
        )
        response.raise_for_status()
        return response
    except Exception as exc:
        raise _build_fetch_failure(exc) from exc


def _get_meta_content(soup: BeautifulSoup, attrs: Dict[str, str]) -> str:
    tag = soup.find("meta", attrs=attrs)
    if tag and tag.get("content"):
        return _normalize_text(tag.get("content"))
    return ""


def _remove_noise_nodes(soup: BeautifulSoup) -> None:
    selectors = [
        "script",
        "style",
        "noscript",
        "svg",
        "iframe",
        "canvas",
        "form",
        "nav",
        "footer",
        "header",
        "aside",
    ]
    for selector in selectors:
        for tag in soup.select(selector):
            tag.decompose()

    for tag in soup.find_all(True):
        if tag is None or getattr(tag, "attrs", None) is None:
            continue
        classes = " ".join(tag.get("class", [])) if tag.get("class") else ""
        id_ = tag.get("id", "")
        marker = f"{classes} {id_}".lower()
        if any(
            x in marker
            for x in [
                "cookie",
                "consent",
                "newsletter",
                "subscribe",
                "promo",
                "advert",
                "ad-",
                "ads",
                "banner",
                "breadcrumb",
                "related",
                "social-share",
                "share",
                "outbrain",
                "taboola",
                "recommended",
            ]
        ):
            tag.decompose()


def _extract_best_text_container(soup: BeautifulSoup) -> Optional[Tag]:
    priority_selectors = [
        "article",
        "main",
        "[role='main']",
        ".article",
        ".post",
        ".entry-content",
        ".article-content",
        ".post-content",
        ".story-body",
        ".content",
    ]
    for selector in priority_selectors:
        node = soup.select_one(selector)
        if node:
            return node

    body = soup.body
    if not body:
        return None

    best_node = None
    best_score = -1
    for node in body.find_all(["div", "section"], recursive=True):
        text = _normalize_text(node.get_text(" ", strip=True))
        if not text:
            continue

        p_count = len(node.find_all("p"))
        heading_count = len(node.find_all(["h1", "h2", "h3"]))
        text_len = len(text)
        score = text_len + (p_count * 200) + (heading_count * 100)
        if score > best_score:
            best_score = score
            best_node = node

    return best_node or body


def _extract_headings(root: Tag, limit: int = 8) -> List[str]:
    headings = []
    for tag in root.find_all(["h1", "h2", "h3"]):
        txt = _normalize_text(tag.get_text(" ", strip=True))
        if txt and len(txt) > 2:
            headings.append(txt)
    return _dedupe_preserve_order(headings)[:limit]


def _extract_body_text(root: Tag) -> str:
    paras = []
    for tag in root.find_all(["p", "li"]):
        txt = _normalize_text(tag.get_text(" ", strip=True))
        if txt and len(txt) >= 40:
            paras.append(txt)

    if not paras:
        return _normalize_text(root.get_text(" ", strip=True))
    return "\n".join(_dedupe_preserve_order(paras))


def _strip_noise(text: str) -> str:
    text = _normalize_text(text)
    noise_patterns = [
        r"\bprivacy policy\b",
        r"\bterms\s*(and|&)\s*conditions\b",
        r"\bcontact us\b",
        r"\bfollow us\b",
        r"\bdownload app\b",
        r"\badvertisement\b",
        r"\ball rights reserved\b",
        r"\bnews archive\b",
        r"\btopics archive\b",
        r"\bread more\b",
        r"\bclick here\b",
    ]
    for pattern in noise_patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def fetch_page_content(url: str, *, timeout: int = DEFAULT_REQUEST_TIMEOUT) -> PageContent:
    response = _fetch_url_response(url, timeout)
    soup = BeautifulSoup(response.text, "html.parser")
    _remove_noise_nodes(soup)

    title = (
        _get_meta_content(soup, {"property": "og:title"})
        or _get_meta_content(soup, {"name": "twitter:title"})
        or _normalize_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    )
    meta_description = (
        _get_meta_content(soup, {"property": "og:description"})
        or _get_meta_content(soup, {"name": "description"})
        or _get_meta_content(soup, {"name": "twitter:description"})
    )

    root = _extract_best_text_container(soup)
    if root is None:
        headings = []
        body_text = ""
    else:
        headings = _extract_headings(root)
        body_text = _extract_body_text(root)

    parsed = urlparse(str(response.url))
    return PageContent(
        url=str(response.url),
        domain=parsed.netloc.lower(),
        title=_strip_noise(title),
        meta_description=_strip_noise(meta_description),
        headings=[h for h in (_strip_noise(h) for h in headings) if h],
        body_text=_strip_noise(body_text),
        http_status=int(response.status_code),
        content_type=str(response.headers.get("content-type", "text/html")),
    )
