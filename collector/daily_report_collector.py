#!/usr/bin/env python3
"""Collect daily-report source data from MCP smart_search and structure it for Hermes."""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

# ── Project root (agent-daily-report/) ────────────────────────────────────────
PROJECT_DIR = Path(__file__).resolve().parent.parent


# ── MCP path resolution (portable across machines) ────────────────────────────
def get_mcp_server_path() -> Path:
    """Resolve MCP server path: env var → project-relative → error."""
    env_path = os.environ.get("MCP_SERVER_PATH")
    if env_path:
        return Path(env_path)
    local = PROJECT_DIR.parent / "agentwebsearch-mcp" / "mcp_server.py"
    if local.exists():
        return local
    raise FileNotFoundError(
        "MCP server not found. Set MCP_SERVER_PATH env var or place "
        "agentwebsearch-mcp/ alongside agent-daily-report/"
    )


def get_python_path() -> str:
    """Resolve Python interpreter: env var → current interpreter."""
    env_path = os.environ.get("MCP_PYTHON_PATH")
    if env_path:
        return env_path
    return sys.executable

import httpx
import httpx_sse
import requests
from bs4 import BeautifulSoup
from readability.readability import Document


MCP_SSE_ENDPOINT = "http://localhost:8902/sse"
MCP_MESSAGES_BASE = "http://localhost:8902/messages"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "ref_src",
    "source",
    "src",
}
BLOCKED_SCHEMES = {"javascript", "mailto"}
BLOCKED_HOST_TOKENS={"duck...om"}
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "about",
    "inside",
    "guide",
    "news",
    "what",
    "when",
    "your",
    "their",
    "more",
    "have",
    "will",
    "has",
    "its",
    "new",
    "released",
    "release",
    "launch",
    "launched",
    "update",
    "framework",
    "platform",
    "agent",
    "agents",
    "agentic",
    "system",
    "tool",
    "tools",
}


@dataclass
class SearchResult:
    query: str
    rank: int
    title: str
    url: str
    normalized_url: str
    domain: str
    snippet: str


@dataclass
class PageResult:
    url: str
    normalized_url: str
    title: str
    snippet: str
    domain: str
    content: str
    content_chars: int
    fetch_status: str
    fetched_at: str


@dataclass
class EventCluster:
    representative: PageResult
    sources: list[PageResult]
    tokens: set[str]
    release_signature: str


# ── MCP Smart Search Client ──────────────────────────────────────────────────
# Uses JSON-RPC over stdio (subprocess) — more stable than SSE

import subprocess
import json
import asyncio


class MCPClient:
    """MCP client using JSON-RPC over stdio (subprocess.Popen)."""
    
    def __init__(self):
        self._proc = None
        self._request_id = 0
    
    async def connect(self):
        """Start MCP server subprocess and initialize."""
        mcp_server_path = str(get_mcp_server_path())
        python_path = get_python_path()
        
        self._proc = subprocess.Popen(
            [python_path, mcp_server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Wait for server to start
        await asyncio.sleep(3)
        
        # Send initialize request
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "daily-report-collector", "version": "1.0"}
            }
        }
        self._proc.stdin.write(json.dumps(init_req) + "\n")
        self._proc.stdin.flush()
        init_resp = await self._read_response()
        print(f"[MCP] Initialized: {init_resp.get('result', {}).get('serverInfo', {}).get('name', 'unknown')}")
        
        # List tools to verify
        list_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        self._proc.stdin.write(json.dumps(list_req) + "\n")
        self._proc.stdin.flush()
        list_resp = await self._read_response()
        tools = list_resp.get('result', {}).get('tools', [])
        print(f"[MCP] Available tools: {[t.get('name') for t in tools]}")
    
    async def _read_response(self) -> dict:
        """Read a JSON-RPC response from the MCP server."""
        line = await asyncio.get_event_loop().run_in_executor(
            None, self._proc.stdout.readline
        )
        if line:
            return json.loads(line.strip())
        return {}
    
    async def smart_search(self, query: str, depth: str = "simple") -> list[dict]:
        """Call smart_search tool via stdio JSON-RPC."""
        self._request_id += 1
        call_req = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": "tools/call",
            "params": {
                "name": "smart_search",
                "arguments": {
                    "query": query,
                    "depth": depth
                }
            }
        }
        self._proc.stdin.write(json.dumps(call_req) + "\n")
        self._proc.stdin.flush()
        
        # Read response (may take multiple reads)
        responses = []
        for _ in range(10):
            line = await asyncio.get_event_loop().run_in_executor(
                None, self._proc.stdout.readline
            )
            if line:
                resp = json.loads(line.strip())
                responses.append(resp)
                if 'result' in resp and 'content' in resp.get('result', {}):
                    break
        
        # Parse the text content from smart_search response
        search_results = []
        for resp in responses:
            if 'result' in resp and 'content' in resp.get('result', {}):
                content = resp['result']['content']
                for item in content:
                    if item.get('type') == 'text':
                        text = item.get('text', '')
                        # Parse the markdown-style results
                        lines = text.split('\n')
                        in_results = False
                        current_item = None
                        for line in lines:
                            if 'Search Results' in line:
                                in_results = True
                                continue
                            if in_results:
                                import re
                                stripped = line.strip()
                                # Match title: "1. **title**"
                                title_match = re.match(r'\d+\.\s+\*+(.+?)\*+', stripped)
                                if title_match:
                                    current_item = {'title': title_match.group(1)}
                                    continue
                                # Match URL: "   URL: url" — match on original line for \s+
                                url_match = re.match(r'\s+URL:\s+(.+)', line)
                                if url_match and current_item:
                                    current_item['url'] = url_match.group(1).strip()
                                    continue
                                # Match snippet: starts with (google) or similar
                                if current_item and stripped.startswith('('):
                                    current_item['snippet'] = stripped
                                    if current_item.get('title') and current_item.get('url'):
                                        search_results.append({
                                            'title': current_item.get('title', ''),
                                            'href': current_item.get('url', ''),
                                            'body': current_item.get('snippet', ''),
                                        })
                                    current_item = None
                                elif current_item and stripped and not stripped.startswith('http'):
                                    # Catch any remaining non-empty lines as potential snippet continuation
                                    current_item['snippet'] = stripped
        return search_results
    
    async def initialize(self):
        """Alias for connect() — kept for compatibility."""
        if self._proc is None:
            await self.connect()
    
    async def list_tools(self):
        """List available MCP tools — kept for compatibility."""
        if self._proc is None:
            await self.connect()
        list_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        self._proc.stdin.write(json.dumps(list_req) + "\n")
        self._proc.stdin.flush()
        resp = await self._read_response()
        tools = resp.get('result', {}).get('tools', [])
        print(f"[MCP] Available tools: {[t.get('name') for t in tools]}")
    
    async def close(self):
        """Close the MCP client."""
        if self._proc:
            self._proc.terminate()
            self._proc.wait(timeout=5)


# ── Search & Fetch ───────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-name", required=True)
    parser.add_argument("--query", action="append", dest="queries", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--final-event-cap", type=int, default=12)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-content-chars", type=int, default=4000)
    parser.add_argument("--mcp", action="store_true", default=True, help="Use MCP smart_search")
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def timestamp_slug() -> str:
    return datetime.now().astimezone().strftime("%Y_%m_%d_%H%M%S")


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def decode_ddg_redirect(url: str) -> str:
    parsed = urlparse(url)
    if "duckduckgo.com" not in parsed.netloc:
        return url
    query = parse_qs(parsed.query)
    for key in ("uddg", "u3", "rut", "u"):
        if key in query and query[key]:
            return unquote(query[key][0])
    return url


def normalize_url(url: str) -> str:
    url = decode_ddg_redirect(url)
    parsed = urlparse(url)
    if not parsed.scheme or parsed.scheme.lower() in BLOCKED_SCHEMES:
        return ""
    query_pairs = []
    for key, values in parse_qs(parsed.query, keep_blank_values=False).items():
        if key.lower() not in TRACKING_PARAMS:
            for value in values:
                query_pairs.append((key, value))
    query_pairs.sort()
    query = "&".join(f"{quote_plus(k)}={quote_plus(v)}" for k, v in query_pairs)
    path = parsed.path or "/"
    normalized = parsed._replace(query=query, fragment="", path=path.rstrip("/") or "/")
    return normalized.geturl()


def host_allowed(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return bool(host) and not any(token in host for token in BLOCKED_HOST_TOKENS)


def extract_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def infer_ddgs_region(query: str) -> str:
    if re.search(r"[\u3040-\u30ff]", query):
        return "jp-jp"
    if re.search(r"[\uac00-\ud7af]", query):
        return "kr-kr"
    if re.search(r"[\u4e00-\u9fff]", query):
        return "cn-zh"
    if re.search(r"[\u0400-\u04ff]", query):
        return "ru-ru"
    if re.search(r"[àâçéèêëîïôûùüÿñæœ]", query, flags=re.IGNORECASE):
        return "fr-fr"
    if re.search(r"[áéíñóúü¡¿]", query, flags=re.IGNORECASE):
        return "es-es"
    if re.search(r"[ãõáâàçéêíóôõú]", query, flags=re.IGNORECASE):
        return "pt-pt"
    if re.search(r"[ğüşöçıİ]", query, flags=re.IGNORECASE):
        return "tr-tr"
    if re.search(r"[\u0590-\u05ff]", query):
        return "wt-wt"
    if re.search(r"[\u0600-\u06ff]", query):
        return "wt-wt"
    if re.search(r"[\u0900-\u097f]", query):
        return "in-en"
    if re.search(r"[\u0b80-\u0bff]", query):
        return "in-en"
    return "us-en"


async def search_query_mcp(query: str, top_k: int, mcp_client: MCPClient) -> list[SearchResult]:
    """Search using MCP smart_search tool."""
    raw_results = await mcp_client.smart_search(query, depth="simple")
    results: list[SearchResult] = []
    seen_urls: set[str] = set()
    
    for item in raw_results:
        title = normalize_whitespace(item.get("title", ""))
        raw_url = normalize_whitespace(item.get("href", ""))
        normalized_url = normalize_url(raw_url)
        if not title or not normalized_url or not host_allowed(normalized_url):
            continue
        if normalized_url in seen_urls:
            continue
        snippet = normalize_whitespace(item.get("body", ""))
        seen_urls.add(normalized_url)
        results.append(
            SearchResult(
                query=query,
                rank=len(results) + 1,
                title=title,
                url=raw_url,
                normalized_url=normalized_url,
                domain=extract_domain(normalized_url),
                snippet=snippet,
            )
        )
        if len(results) >= top_k:
            break
    return results


def search_query(query: str, top_k: int) -> list[SearchResult]:
    """Search using DuckDuckGo (legacy, kept for fallback)."""
    region = infer_ddgs_region(query)
    ddgs = __import__("ddgs", fromlist=["DDGS"]).DDGS(timeout=45)
    raw_results = ddgs.text(
        query,
        region=region,
        safesearch="moderate",
        timelimit="m",
        max_results=top_k,
    )
    results: list[SearchResult] = []
    seen_urls: set[str] = set()

    for item in raw_results:
        title = normalize_whitespace(item.get("title", ""))
        raw_url = normalize_whitespace(item.get("href", ""))
        normalized_url = normalize_url(raw_url)
        if not title or not normalized_url or not host_allowed(normalized_url):
            continue
        if normalized_url in seen_urls:
            continue
        snippet = normalize_whitespace(item.get("body", ""))
        seen_urls.add(normalized_url)
        results.append(
            SearchResult(
                query=query,
                rank=len(results) + 1,
                title=title,
                url=raw_url,
                normalized_url=normalized_url,
                domain=extract_domain(normalized_url),
                snippet=snippet,
            )
        )
        if len(results) >= top_k:
            break
    return results


# ── Page Fetching ────────────────────────────────────────────────────────────

def clean_page_text(text: str, max_chars: int) -> str:
    text = normalize_whitespace(text)
    boilerplate_patterns = [
        r"cookie(s)? policy",
        r"subscribe now",
        r"sign up",
        r"all rights reserved",
        r"advertisement",
        r"accept cookies",
    ]
    for pattern in boilerplate_patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    text = normalize_whitespace(text)
    return text[:max_chars].strip()


def extract_readable_text(html: str) -> tuple[str, str]:
    try:
        doc = Document(html)
        title = normalize_whitespace(doc.short_title())
        summary_html = doc.summary(html_partial=True)
        soup = BeautifulSoup(summary_html, "html.parser")
        text = normalize_whitespace(soup.get_text(" ", strip=True))
        if text:
            return title, text
    except Exception:
        pass

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        tag.decompose()
    title = normalize_whitespace(soup.title.get_text(" ", strip=True) if soup.title else "")
    text = normalize_whitespace(soup.get_text(" ", strip=True))
    return title, text


def fetch_page(
    session: requests.Session,
    result: SearchResult,
    max_content_chars: int,
) -> PageResult:
    fetched_at = now_iso()
    try:
        response = session.get(result.normalized_url, timeout=30, allow_redirects=True)
        response.raise_for_status()
        final_url = normalize_url(response.url)
        if not final_url or not host_allowed(final_url):
            raise ValueError("invalid final url")
        title, text = extract_readable_text(response.text)
        content = clean_page_text(text or result.snippet, max_content_chars)
        page_title = title or result.title
        status = "ok" if content else "empty_content"
        return PageResult(
            url=final_url,
            normalized_url=final_url,
            title=page_title,
            snippet=result.snippet,
            domain=extract_domain(final_url),
            content=content or result.snippet,
            content_chars=len(content or result.snippet),
            fetch_status=status,
            fetched_at=fetched_at,
        )
    except Exception as exc:
        fallback = clean_page_text(result.snippet, max_content_chars)
        return PageResult(
            url=result.normalized_url,
            normalized_url=result.normalized_url,
            title=result.title,
            snippet=result.snippet,
            domain=result.domain,
            content=fallback,
            content_chars=len(fallback),
            fetch_status=f"fallback:{type(exc).__name__}",
            fetched_at=fetched_at,
        )


# ── Clustering & Scoring ─────────────────────────────────────────────────────

def title_key(title: str) -> str:
    lowered = normalize_whitespace(title).lower()
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff ]", " ", lowered)
    tokens = [token for token in lowered.split() if len(token) > 2]
    return " ".join(tokens[:12])


def detect_language_hint(text: str) -> str:
    if not text:
        return "unknown"
    sample = normalize_whitespace(text)
    if re.search(r"[\u4e00-\u9fff]", sample):
        return "zh"
    if re.search(r"[\u3040-\u30ff]", sample):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", sample):
        return "ko"
    if re.search(r"[\u0400-\u04ff]", sample):
        return "ru"
    latin_chars = re.findall(r"[A-Za-z]", sample)
    if latin_chars:
        return "en"
    return "unknown"


def make_source_excerpt(text: str, max_chars: int = 320) -> str:
    cleaned = normalize_whitespace(text)
    if len(cleaned) <= max_chars:
        return cleaned
    clipped = cleaned[:max_chars].rsplit(" ", 1)[0].strip()
    return f"{clipped}..."


def normalize_text_for_tokens(text: str) -> list[str]:
    lowered = normalize_whitespace(text).lower()
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff.+-]", " ", lowered)
    tokens = []
    for token in lowered.split():
        if len(token) <= 2:
            continue
        if token in STOPWORDS:
            continue
        tokens.append(token)
    return tokens


def page_tokens(page: PageResult) -> set[str]:
    combined = f"{page.title} {page.snippet} {page.content[:800]}"
    return set(normalize_text_for_tokens(combined))


def extract_release_signature(page: PageResult) -> str:
    haystack = f"{page.title} {page.snippet} {page.content[:400]}".lower()
    version_match = re.search(r"\b(v?(?:\d+\.){1,3}\d+)\b", haystack)
    title_tokens = normalize_text_for_tokens(page.title)
    core = [token for token in title_tokens if token not in {"open", "source", "python", "github"}]
    phrase = " ".join(core[:4])
    if version_match and phrase:
        return f"{phrase}::{version_match.group(1)}"
    return phrase


def extract_version_token(page: PageResult) -> str:
    haystack = f"{page.title} {page.snippet} {page.content[:400]}".lower()
    version_match = re.search(r"\b(v?(?:\d+\.){1,3}\d+)\b", haystack)
    return version_match.group(1) if version_match else ""


def title_token_set(page: PageResult) -> set[str]:
    return set(normalize_text_for_tokens(page.title))


def score_result(page: PageResult) -> tuple[int, int]:
    domain_score = 0
    host = page.domain
    if any(token in host for token in ("github.com", "openai.com", "anthropic.com", "google.com")):
        domain_score += 3
    if any(token in host for token in ("arxiv.org", "docs.", "blog.")):
        domain_score += 2
    if any(token in host for token in ("news", "techcrunch", "venturebeat", "theverge")):
        domain_score += 1
    return domain_score, page.content_chars


def dedupe_pages(pages: Iterable[PageResult]) -> list[PageResult]:
    selected: dict[str, PageResult] = {}
    title_selected: dict[str, PageResult] = {}
    for page in pages:
        existing = selected.get(page.normalized_url)
        if existing is None or score_result(page) > score_result(existing):
            selected[page.normalized_url] = page

    for page in selected.values():
        key = title_key(page.title)
        existing = title_selected.get(key)
        if not key:
            continue
        if existing is None or score_result(page) > score_result(existing):
            title_selected[key] = page

    final_set = {page.normalized_url for page in title_selected.values()}
    return [page for page in selected.values() if page.normalized_url in final_set]


def select_representative_source(sources: list[PageResult]) -> PageResult:
    def rep_score(page: PageResult) -> tuple[int, int, int]:
        host = page.domain
        official_bonus = 0
        if any(
            token in host
            for token in (
                "github.com",
                "openai.com",
                "anthropic.com",
                "google.com",
                "microsoft.com",
                "techcommunity.microsoft.com",
                "devblogs.microsoft.com",
            )
        ):
            official_bonus += 4
        return official_bonus, *score_result(page)

    return max(sources, key=rep_score)


def token_overlap_ratio(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    return overlap / max(1, min(len(left), len(right)))


def should_merge_clusters(page: PageResult, cluster: EventCluster) -> bool:
    page_sig = extract_release_signature(page)
    if page_sig and cluster.release_signature and page_sig == cluster.release_signature:
        return True

    page_token_set = page_tokens(page)
    overlap = token_overlap_ratio(page_token_set, cluster.tokens)
    if overlap >= 0.72:
        return True

    page_title_tokens = title_token_set(page)
    cluster_title_tokens = title_token_set(cluster.representative)
    title_overlap = token_overlap_ratio(page_title_tokens, cluster_title_tokens)
    page_version = extract_version_token(page)
    cluster_version = extract_version_token(cluster.representative)
    shared_named_tokens = {
        token
        for token in (page_title_tokens & cluster_title_tokens)
        if not re.fullmatch(r"v?(?:\d+\.){1,3}\d+", token)
    }
    if page_version and cluster_version and page_version == cluster_version:
        if title_overlap >= 0.5 and shared_named_tokens:
            return True

    return title_overlap >= 0.75 and overlap >= 0.45


def merge_into_cluster(cluster: EventCluster, page: PageResult) -> EventCluster:
    merged_sources = cluster.sources + [page]
    representative = select_representative_source(merged_sources)
    merged_tokens = set(cluster.tokens)
    merged_tokens.update(page_tokens(page))
    release_signature = cluster.release_signature or extract_release_signature(page)
    return EventCluster(
        representative=representative,
        sources=merged_sources,
        tokens=merged_tokens,
        release_signature=release_signature,
    )


def cluster_pages(pages: list[PageResult], final_event_cap: int) -> list[EventCluster]:
    if not pages:
        return []

    clusters: list[EventCluster] = []
    remaining = list(pages)

    while remaining:
        page = remaining.pop(0)
        merged_idx = -1
        for i, cluster in enumerate(clusters):
            if should_merge_clusters(page, cluster):
                merged_idx = i
                break

        if merged_idx >= 0:
            clusters[merged_idx] = merge_into_cluster(clusters[merged_idx], page)
        else:
            clusters.append(
                EventCluster(
                    representative=page,
                    sources=[page],
                    tokens=page_tokens(page),
                    release_signature=extract_release_signature(page),
                )
            )

    # Sort clusters by representative score
    clusters.sort(key=lambda c: score_result(c.representative), reverse=True)
    return clusters[:final_event_cap]


# ── Report Generation ────────────────────────────────────────────────────────

def generate_markdown_report(clusters: list[EventCluster], task_name: str) -> str:
    lines = [f"# Daily Report: {task_name}", f"Generated: {now_iso()}", ""]
    
    for i, cluster in enumerate(clusters, 1):
        rep = cluster.representative
        lines.append(f"## {i}. {rep.title}")
        lines.append("")
        lines.append(f"- **URL**: {rep.url}")
        lines.append(f"- **Domain**: {rep.domain}")
        lines.append(f"- **Status**: {rep.fetch_status}")
        lines.append(f"- **Content Length**: {rep.content_chars} chars")
        lines.append(f"- **Sources**: {len(cluster.sources)}")
        lines.append("")
        lines.append("### Content Preview")
        lines.append("")
        preview = rep.content[:500] + "..." if len(rep.content) > 500 else rep.content
        lines.append(preview)
        lines.append("")
        
        if len(cluster.sources) > 1:
            lines.append("### Additional Sources")
            lines.append("")
            for src in cluster.sources[1:]:
                lines.append(f"- [{src.title}]({src.url}) ({src.domain})")
            lines.append("")
        
        lines.append("---")
        lines.append("")
    
    return "\n".join(lines)


def generate_json_output(clusters: list[EventCluster], task_name: str, output_dir: str) -> str:
    output_data = {
        "task_name": task_name,
        "generated_at": now_iso(),
        "total_clusters": len(clusters),
        "clusters": [],
    }
    
    for i, cluster in enumerate(clusters, 1):
        rep = cluster.representative
        cluster_data = {
            "id": i,
            "title": rep.title,
            "url": rep.url,
            "domain": rep.domain,
            "status": rep.fetch_status,
            "content_chars": rep.content_chars,
            "content": rep.content[:2000],
            "source_count": len(cluster.sources),
            "sources": [
                {
                    "title": s.title,
                    "url": s.url,
                    "domain": s.domain,
                }
                for s in cluster.sources
            ],
        }
        output_data["clusters"].append(cluster_data)
    
    output_path = Path(output_dir) / f"daily_report_{timestamp_slug()}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    return str(output_path)


# ── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    args = parse_args()
    
    print(f"[INFO] Task: {args.task_name}")
    print(f"[INFO] Queries: {args.queries}")
    print(f"[INFO] Top-K: {args.top_k}")
    print(f"[INFO] Output: {args.output_dir}")
    
    # Initialize MCP client
    mcp_client = MCPClient()
    await mcp_client.connect()
    await mcp_client.initialize()
    await mcp_client.list_tools()
    
    # Search across all queries
    all_results: list[SearchResult] = []
    for query in args.queries:
        print(f"[INFO] Searching: {query}")
        try:
            search_results = await search_query_mcp(query, args.top_k, mcp_client)
            print(f"[INFO] Found {len(search_results)} results for '{query}'")
            all_results.extend(search_results)
        except Exception as exc:
            print(f"[WARN] MCP search failed for '{query}': {exc}, falling back to DDGS")
            fallback_results = search_query(query, args.top_k)
            all_results.extend(fallback_results)
    
    print(f"[INFO] Total search results: {len(all_results)}")
    
    # Fetch pages
    session = make_session()
    all_pages: list[PageResult] = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        loop = asyncio.get_event_loop()
        
        def _fetch_page(result: SearchResult) -> PageResult:
            return fetch_page(session, result, args.max_content_chars)
        
        futures = [
            loop.run_in_executor(executor, _fetch_page, result)
            for result in all_results
        ]
        
        for future in asyncio.as_completed(futures):
            try:
                page = await future
                all_pages.append(page)
            except Exception as exc:
                print(f"[WARN] Page fetch error: {exc}")
    
    print(f"[INFO] Fetched {len(all_pages)} pages")
    
    # Dedupe & cluster
    deduped = dedupe_pages(all_pages)
    print(f"[INFO] After dedupe: {len(deduped)} pages")
    
    clusters = cluster_pages(deduped, args.final_event_cap)
    print(f"[INFO] Clusters: {len(clusters)}")
    
    # Generate outputs
    md_report = generate_markdown_report(clusters, args.task_name)
    md_path = Path(args.output_dir) / f"daily_report_{timestamp_slug()}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"[INFO] Markdown report: {md_path}")
    
    json_path = generate_json_output(clusters, args.task_name, args.output_dir)
    print(f"[INFO] JSON output: {json_path}")
    
    await mcp_client.close()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
