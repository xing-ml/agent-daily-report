#!/usr/bin/env python3
"""Collect daily-report source data from DuckDuckGo and structure it for Hermes."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from readability import Document


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
BLOCKED_HOST_TOKENS = {"duckduckgo.com"}
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-name", required=True)
    parser.add_argument("--query", action="append", dest="queries", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--final-event-cap", type=int, default=12)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-content-chars", type=int, default=4000)
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


def search_query(query: str, top_k: int) -> list[SearchResult]:
    region = infer_ddgs_region(query)
    ddgs = DDGS(timeout=45)
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
    clusters: list[EventCluster] = []
    for page in pages:
        merged = False
        for idx, cluster in enumerate(clusters):
            if should_merge_clusters(page, cluster):
                clusters[idx] = merge_into_cluster(cluster, page)
                merged = True
                break
        if merged:
            continue
        clusters.append(
            EventCluster(
                representative=page,
                sources=[page],
                tokens=page_tokens(page),
                release_signature=extract_release_signature(page),
            )
        )

    clusters.sort(
        key=lambda cluster: (
            len(cluster.sources),
            *score_result(cluster.representative),
        ),
        reverse=True,
    )
    return clusters[:final_event_cap]


def build_event(cluster: EventCluster, index: int) -> dict:
    page = cluster.representative
    sources = sorted(cluster.sources, key=score_result, reverse=True)
    source_language_hints = [
        detect_language_hint(f"{source.title} {source.snippet} {source.content[:500]}")
        for source in sources
    ]
    event_language_hint = source_language_hints[0] if source_language_hints else "unknown"
    return {
        "event_id": f"evt_{index:03d}",
        "title": page.title,
        "summary_hint": page.content[:500],
        "date": "",
        "category": infer_category(page),
        "language_hint": event_language_hint,
        "importance_score": round(
            min(0.99, 0.4 + (page.content_chars / 5000) + min(0.2, 0.04 * (len(sources) - 1))),
            2,
        ),
        "sources": [
            {
                "title": source.title,
                "url": source.url,
                "domain": source.domain,
                "snippet": source.snippet,
                "content": source.content,
                "source_excerpt": make_source_excerpt(source.content or source.snippet),
                "fetch_status": source.fetch_status,
                "language_hint": source_language_hints[idx],
            }
            for idx, source in enumerate(sources)
        ],
    }


def infer_category(page: PageResult) -> str:
    haystack = f"{page.title} {page.snippet} {page.content}".lower()
    category_rules = {
        "security": ("security", "safety", "alignment", "guardrail"),
        "research": ("paper", "research", "arxiv", "benchmark", "evaluation"),
        "open_source": ("open source", "github", "sdk", "api"),
        "platform": ("platform", "framework", "workspace", "studio"),
        "product": ("launch", "release", "pricing", "enterprise", "production"),
    }
    for category, keywords in category_rules.items():
        if any(keyword in haystack for keyword in keywords):
            return category
    return "general"


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    session = make_session()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_stamp = timestamp_slug()

    raw_search_results: list[SearchResult] = []
    search_errors: list[dict] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(args.queries) or 1)) as executor:
        future_map = {
            executor.submit(search_query, query, args.top_k): query
            for query in args.queries
        }
        for future in concurrent.futures.as_completed(future_map):
            query = future_map[future]
            try:
                raw_search_results.extend(future.result())
            except Exception as exc:
                search_errors.append({"query": query, "error": repr(exc)})

    # Retry failed queries up to 3 times with 10s delay between attempts
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        if not search_errors:
            break
        print(f"[retry] attempt {attempt}/{max_retries}: {len(search_errors)} queries failed, waiting 10s...")
        time.sleep(10)
        retry_errors: list[dict] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(search_errors))) as executor:
            future_map = {
                executor.submit(search_query, err["query"], args.top_k): err
                for err in search_errors
            }
            for future in concurrent.futures.as_completed(future_map):
                err = future_map[future]
                try:
                    raw_search_results.extend(future.result())
                except Exception as exc:
                    retry_errors.append({"query": err["query"], "error": f"retry {attempt}: {repr(exc)}"})
        if retry_errors:
            search_errors.extend(retry_errors)
            print(f"[retry] attempt {attempt}/{max_retries}: {len(retry_errors)} queries still failed")
        else:
            print(f"[retry] all queries recovered on attempt {attempt}")

    unique_results: dict[str, SearchResult] = {}
    for result in raw_search_results:
        existing = unique_results.get(result.normalized_url)
        if existing is None or len(result.snippet) > len(existing.snippet):
            unique_results[result.normalized_url] = result

    page_results: list[PageResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(12, len(unique_results) or 1)) as executor:
        future_map = {
            executor.submit(fetch_page, session, result, args.max_content_chars): result.normalized_url
            for result in unique_results.values()
        }
        for future in concurrent.futures.as_completed(future_map):
            page_results.append(future.result())

    deduped_pages = dedupe_pages(page_results)
    deduped_pages.sort(key=score_result, reverse=True)
    final_clusters = cluster_pages(deduped_pages, args.final_event_cap)

    events = [build_event(cluster, idx) for idx, cluster in enumerate(final_clusters, start=1)]
    generated_at = now_iso()

    raw_search_payload = {
        "task_name": args.task_name,
        "generated_at": generated_at,
        "queries": args.queries,
        "top_k": args.top_k,
        "search_errors": search_errors,
        "results": [asdict(item) for item in raw_search_results],
    }
    raw_pages_payload = {
        "task_name": args.task_name,
        "generated_at": generated_at,
        "pages": [asdict(item) for item in page_results],
    }
    structured_payload = {
        "task_name": args.task_name,
        "generated_at": generated_at,
        "queries": args.queries,
        "stats": {
            "raw_results": len(raw_search_results),
            "unique_results": len(unique_results),
            "fetched_pages": len(page_results),
            "deduped_pages": len(deduped_pages),
            "clustered_events": len(final_clusters),
            "final_events": len(events),
            "search_errors": len(search_errors),
        },
        "events": events,
    }
    agent_input_payload = {
        "task_name": args.task_name,
        "generated_at": generated_at,
        "time_window": "recent / past week / past month (as inferred from query set)",
        "query_count": len(args.queries),
        "queries": args.queries,
        "stats": structured_payload["stats"],
        "events": events,
        "instructions": {
            "summary_language": "zh-CN",
            "must_ground_in_input": True,
            "no_external_search": True,
            "preserve_source_language_signal": True,
            "require_english_original_or_translation": True,
        },
    }

    prefix = f"{args.task_name}_"
    write_json(output_dir / f"{prefix}raw_search_{run_stamp}.json", raw_search_payload)
    write_json(output_dir / f"{prefix}raw_pages_{run_stamp}.json", raw_pages_payload)
    write_json(output_dir / f"{prefix}structured_{run_stamp}.json", structured_payload)
    write_json(output_dir / f"{prefix}agent_input_{run_stamp}.json", agent_input_payload)
    write_json(output_dir / f"{args.task_name}_agent_input.json", agent_input_payload)

    print(str(output_dir / f"{args.task_name}_agent_input.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
