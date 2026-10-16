"""抓取 Instagram 帖子文案。

优先使用 /embed/captioned/ 页面（无需登录），失败时回退到帖子页的 og:description。
"""
import html
import json
import re
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from .schemas import PostContent
from .sentiment import analyze

SHORTCODE_RE = re.compile(r"^/(?:[\w.]+/)?(p|reel|reels|tv)/([A-Za-z0-9_-]+)/?")
SHARE_RE = re.compile(r"^/share/(?:p/|reel/|reels/)?[A-Za-z0-9_-]+/?")
IG_HOSTS = ("instagram.com", "instagr.am")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def normalize_url(url: str) -> str:
    url = url.strip()
    m = re.search(r"https?://\S+", url)
    if m:
        url = m.group(0).rstrip("，。、,.;)]》」")
    if not url:
        raise HTTPException(400, "请输入 Instagram 帖子链接")
    if not url.startswith("http"):
        url = "https://" + url
    parsed = urlparse(url)
    if not any(h in parsed.netloc for h in IG_HOSTS):
        raise HTTPException(400, "只支持 instagram.com 的帖子链接")
    return url


def is_share_link(url: str) -> bool:
    return bool(SHARE_RE.match(urlparse(url).path))


def parse_shortcode(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    match = SHORTCODE_RE.match(parsed.path)
    if not match:
        raise HTTPException(400, "无法识别帖子链接，示例：https://www.instagram.com/p/XXXXXXXX/")
    return match.group(2)


async def resolve_share_link(client: httpx.AsyncClient, url: str) -> str:
    """分享短链 /share/xxx 会 302 到真实帖子地址，跟随跳转后再解析。"""
    try:
        resp = await client.get(url)
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"解析分享链接失败：{exc.__class__.__name__}")
    final = str(resp.url)
    if SHORTCODE_RE.match(urlparse(final).path):
        return final
    m = re.search(r'instagram\.com/(?:p|reel|reels|tv)/[A-Za-z0-9_-]+', resp.text)
    if m:
        return "https://www." + m.group(0) + "/"
    raise HTTPException(400, "分享链接无法解析出帖子地址，请在浏览器打开后复制地址栏的完整链接")


def _html_to_text(fragment: str) -> str:
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"</(p|div)>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    text = html.unescape(fragment)
    text = text.replace("\r\n", "\n").replace("\xa0", " ")
    lines = [line.rstrip() for line in text.split("\n")]
    cleaned = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def _parse_embed(page: str) -> tuple[str, str]:
    author = ""
    caption = ""
    m = re.search(r'class="CaptionUsername"[^>]*>(.*?)</a>', page, re.S)
    if m:
        author = _html_to_text(m.group(1))
    m = re.search(r'<div class="Caption">(.*?)<div class="CaptionComments">', page, re.S)
    if m:
        block = m.group(1)
        block = re.sub(r'<a class="CaptionUsername".*?</a>', "", block, flags=re.S)
        caption = _html_to_text(block)
    if not caption:
        m = re.search(r"window\.__additionalDataLoaded\('extra',(\{.*?\})\);</script>", page, re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                media = data.get("shortcode_media") or data.get("graphql", {}).get("shortcode_media", {})
                edges = media.get("edge_media_to_caption", {}).get("edges", [])
                if edges:
                    caption = edges[0]["node"]["text"].strip()
                author = author or media.get("owner", {}).get("username", "")
            except (ValueError, KeyError, TypeError):
                pass
    return author, caption


def _parse_og(page: str) -> tuple[str, str]:
    author = ""
    caption = ""
    m = re.search(r'<meta property="og:description" content="([^"]*)"', page)
    if m:
        desc = html.unescape(m.group(1))
        # 典型格式：123 likes, 4 comments - user on Month DD, YYYY: "caption"
        q = re.search(r'^.*? - ([\w.]+) on .*?: [“"](.*)[”"]\s*$', desc, re.S)
        if q:
            author, caption = q.group(1), q.group(2)
        else:
            caption = desc
    if not author:
        m = re.search(r'<meta property="og:title" content="([^"]*)"', page)
        if m:
            t = re.search(r"@([\w.]+)", html.unescape(m.group(1)))
            if t:
                author = t.group(1)
    return author, caption.strip()


async def _fetch_graphql(client: httpx.AsyncClient, shortcode: str) -> tuple[str, str]:
    """未登录可用的 GraphQL 接口（doc_id 为 Instagram 网页端使用的查询 ID）。"""
    resp = await client.post(
        "https://www.instagram.com/graphql/query",
        data={
            "doc_id": "8845758582119845",
            "variables": json.dumps({"shortcode": shortcode}),
        },
        headers={"X-IG-App-ID": "936619743392459", "Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code >= 400:
        raise httpx.HTTPStatusError(f"HTTP {resp.status_code}", request=resp.request, response=resp)
    media = resp.json()["data"]["xdt_shortcode_media"]
    edges = media.get("edge_media_to_caption", {}).get("edges", [])
    caption = edges[0]["node"]["text"].strip() if edges else ""
    return media.get("owner", {}).get("username", ""), caption


async def fetch_post(url: str, proxy: str = "") -> PostContent:
    url = normalize_url(url)
    headers = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    author = caption = source = ""
    errors: list[str] = []
    async with httpx.AsyncClient(
        headers=headers, timeout=15, follow_redirects=True, proxy=proxy or None
    ) as client:
        if is_share_link(url):
            url = await resolve_share_link(client, url)
        shortcode = parse_shortcode(url)
        for candidate, parser, name in (
            (f"https://www.instagram.com/p/{shortcode}/embed/captioned/", _parse_embed, "embed"),
            (f"https://www.instagram.com/p/{shortcode}/", _parse_og, "og"),
        ):
            try:
                resp = await client.get(candidate)
                if resp.status_code >= 400:
                    errors.append(f"{name}: HTTP {resp.status_code}")
                    continue
                a, c = parser(resp.text)
                author = author or a
                if c:
                    caption, source = c, name
                    break
            except httpx.HTTPError as exc:
                errors.append(f"{name}: {exc.__class__.__name__}")
        if not caption:
            try:
                a, c = await _fetch_graphql(client, shortcode)
                author = author or a
                if c:
                    caption, source = c, "graphql"
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                errors.append(f"graphql: {exc.__class__.__name__}")
    if not caption:
        detail = "；".join(errors) if errors else "帖子可能为私密账号、链接无效或当前服务器 IP 被 Instagram 限制（可配置 HTTP_PROXY_URL）"
        raise HTTPException(502, f"抓取文案失败：{detail}")

    hashtags = re.findall(r"#([^\s#@]+)", caption)
    mentions = re.findall(r"@([\w.]+)", caption)
    sentiment, label, score = analyze(caption)
    return PostContent(
        url=f"https://www.instagram.com/p/{shortcode}/",
        shortcode=shortcode,
        author=author,
        caption=caption,
        hashtags=hashtags,
        mentions=mentions,
        sentiment=sentiment,
        sentiment_label=label,
        sentiment_score=score,
        source=source,
    )
