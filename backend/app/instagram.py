"""抓取 Instagram 帖子文案与图片 / 视频（含多图轮播）。

优先使用 /embed/captioned/ 页面（无需登录），失败时回退到帖子页的 og:description / og:image。
"""
import html
import json
import logging
import re
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from .schemas import MediaItem, PostContent
from .sentiment import analyze

logger = logging.getLogger("uvicorn.error")
NETWORK_ERRORS = ("ConnectError", "ConnectTimeout", "ReadTimeout", "ProxyError", "RemoteProtocolError", "ReadError")
NETWORK_HINT = "请在 backend/.env 配置 HTTP_PROXY_URL（如 Clash 填 http://127.0.0.1:7890，v2rayN 填 http://127.0.0.1:10809）后重启后端"
SHORTCODE_RE = re.compile(r"^/(?:[\w.]+/)?(p|reel|reels|tv)/([A-Za-z0-9_-]+)/?")
SHARE_RE = re.compile(r"^/share/(?:p/|reel/|reels/)?[A-Za-z0-9_-]+/?")
IG_HOSTS = ("instagram.com", "instagr.am")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
# embed 页面对搜索引擎爬虫 UA 不弹登录墙，是目前最稳的未登录抓取方式
BOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
IG_APP_ID = "936619743392459"
SHORTCODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def shortcode_to_media_id(shortcode: str) -> int:
    media_id = 0
    for ch in shortcode:
        media_id = media_id * 64 + SHORTCODE_ALPHABET.index(ch)
    return media_id


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
        logger.warning("解析分享链接失败 %s：%r", url, exc)
        raise HTTPException(502, f"解析分享链接失败：{exc.__class__.__name__}，{NETWORK_HINT}")
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


def _gql_node_media(node: dict) -> MediaItem | None:
    dims = node.get("dimensions") or {}
    resources = node.get("display_resources") or []
    best = max(resources, key=lambda r: r.get("config_width", 0), default={})
    image = best.get("src") or node.get("display_url") or ""
    width, height = dims.get("width", 0), dims.get("height", 0)
    if node.get("is_video") and node.get("video_url"):
        return MediaItem(type="video", url=node["video_url"], thumbnail=image, width=width, height=height)
    if image:
        return MediaItem(type="image", url=image, width=width, height=height)
    return None


def _media_from_gql(media: dict) -> list[MediaItem]:
    edges = (media.get("edge_sidecar_to_children") or {}).get("edges") or []
    nodes = [e.get("node") or {} for e in edges] or [media]
    return [m for m in map(_gql_node_media, nodes) if m]


def _api_item_media(item: dict) -> MediaItem | None:
    images = (item.get("image_versions2") or {}).get("candidates") or []
    best_image = max(images, key=lambda c: c.get("width", 0), default={})
    videos = item.get("video_versions") or []
    if videos:
        best = max(videos, key=lambda v: v.get("width", 0) * v.get("height", 0))
        return MediaItem(type="video", url=best["url"], thumbnail=best_image.get("url", ""),
                         width=best.get("width", 0), height=best.get("height", 0))
    if best_image.get("url"):
        return MediaItem(type="image", url=best_image["url"], width=best_image.get("width", 0),
                         height=best_image.get("height", 0))
    return None


def _media_from_api(item: dict) -> list[MediaItem]:
    children = item.get("carousel_media") or [item]
    return [m for m in map(_api_item_media, children) if m]


def _embed_shortcode_media(page: str) -> dict:
    m = re.search(r'"contextJSON":("(?:[^"\\]|\\.)*")', page)
    if m:
        try:
            ctx = json.loads(json.loads(m.group(1)))
            media = (ctx.get("gql_data") or {}).get("shortcode_media")
            if media:
                return media
        except (ValueError, TypeError, AttributeError):
            pass
    m = re.search(r"window\.__additionalDataLoaded\('extra',(\{.*?\})\);</script>", page, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            return data.get("shortcode_media") or data.get("graphql", {}).get("shortcode_media", {}) or {}
        except (ValueError, TypeError, AttributeError):
            pass
    return {}


def _parse_embed(page: str) -> tuple[str, str, list[MediaItem]]:
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
    media = _embed_shortcode_media(page)
    if media:
        if not caption:
            edges = (media.get("edge_media_to_caption") or {}).get("edges") or []
            if edges:
                caption = (edges[0].get("node") or {}).get("text", "").strip()
        author = author or (media.get("owner") or {}).get("username", "")
    items = _media_from_gql(media) if media else []
    if not items:
        m = re.search(r'class="EmbeddedMediaImage"[^>]*?src="([^"]+)"', page)
        if m:
            items = [MediaItem(type="image", url=html.unescape(m.group(1)))]
    return author, caption, items


def _parse_og(page: str) -> tuple[str, str, list[MediaItem]]:
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
    items: list[MediaItem] = []
    image = re.search(r'<meta property="og:image" content="([^"]+)"', page)
    video = re.search(r'<meta property="og:video(?::secure_url)?" content="([^"]+)"', page)
    if video:
        items.append(MediaItem(type="video", url=html.unescape(video.group(1)),
                               thumbnail=html.unescape(image.group(1)) if image else ""))
    elif image:
        items.append(MediaItem(type="image", url=html.unescape(image.group(1))))
    return author, caption.strip(), items


async def _fetch_graphql(client: httpx.AsyncClient, shortcode: str) -> tuple[str, str, list[MediaItem]]:
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
    return media.get("owner", {}).get("username", ""), caption, _media_from_gql(media)


async def _fetch_with_session(client: httpx.AsyncClient, shortcode: str,
                              sessionid: str) -> tuple[str, str, list[MediaItem]]:
    """登录态接口：需要浏览器 cookie 中的 sessionid，最可靠。"""
    media_id = shortcode_to_media_id(shortcode)
    resp = await client.get(
        f"https://www.instagram.com/api/v1/media/{media_id}/info/",
        headers={"User-Agent": UA, "X-IG-App-ID": IG_APP_ID, "Accept": "*/*"},
        cookies={"sessionid": sessionid},
    )
    if resp.status_code >= 400:
        raise httpx.HTTPStatusError(f"HTTP {resp.status_code}", request=resp.request, response=resp)
    item = resp.json()["items"][0]
    caption = (item.get("caption") or {}).get("text", "") or ""
    return item.get("user", {}).get("username", ""), caption.strip(), _media_from_api(item)


async def fetch_post(url: str, proxy: str = "", sessionid: str = "") -> PostContent:
    url = normalize_url(url)
    headers = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    author = caption = source = media_source = ""
    media: list[MediaItem] = []
    # og:image 只有封面缩略图，仅在其它来源都拿不到媒体时使用
    og_media: list[MediaItem] = []
    errors: list[str] = []

    def collect(name: str, a: str, c: str, m: list[MediaItem]) -> None:
        nonlocal author, caption, source, media, media_source, og_media
        author = author or a
        if c and not caption:
            caption, source = c, name
        if m and not media:
            if name == "og":
                og_media = og_media or m
            else:
                media, media_source = m, name

    async with httpx.AsyncClient(
        headers=headers, timeout=15, follow_redirects=True, proxy=proxy or None
    ) as client:
        if is_share_link(url):
            url = await resolve_share_link(client, url)
        shortcode = parse_shortcode(url)
        if sessionid:
            try:
                collect("session", *await _fetch_with_session(client, shortcode, sessionid))
            except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
                errors.append(f"session: {exc.__class__.__name__}（sessionid 可能已失效）")
        embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
        for candidate, parser, name, ua in (
            (embed_url, _parse_embed, "embed", BOT_UA),
            (embed_url, _parse_embed, "embed-browser", UA),
            (f"https://www.instagram.com/p/{shortcode}/", _parse_og, "og", UA),
        ):
            if caption and media:
                break
            try:
                resp = await client.get(candidate, headers={"User-Agent": ua})
                if resp.status_code >= 400:
                    errors.append(f"{name}: HTTP {resp.status_code}")
                    continue
                collect(name, *parser(resp.text))
            except httpx.HTTPError as exc:
                errors.append(f"{name}: {exc.__class__.__name__}")
        if not (caption and media):
            try:
                collect("graphql", *await _fetch_graphql(client, shortcode))
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                errors.append(f"graphql: {exc.__class__.__name__}")
    if not media and og_media:
        media, media_source = og_media, "og"
    if not caption and not media:
        detail = "；".join(errors) if errors else "帖子可能为私密账号、链接无效或当前服务器 IP 被 Instagram 限制（可配置 HTTP_PROXY_URL）"
        logger.warning("抓取失败 %s（代理：%s）：%s", url, proxy or "未配置", detail)
        if errors and all(any(n in e for n in NETWORK_ERRORS) for e in errors):
            raise HTTPException(502, f"无法连接 Instagram，{NETWORK_HINT if not proxy else f'当前代理 {proxy} 不可用，请确认代理软件已开启且端口正确'}（{detail}）")
        raise HTTPException(502, f"抓取失败：{detail}")
    for idx, item in enumerate(media, start=1):
        ext = "mp4" if item.type == "video" else "jpg"
        item.filename = f"{shortcode}_{idx:02d}.{ext}" if len(media) > 1 else f"{shortcode}.{ext}"
    if media_source and media_source != source:
        source = f"{source or '无文案'} / 媒体: {media_source}"

    hashtags = re.findall(r"#([^\s#@]+)", caption)
    mentions = re.findall(r"@([\w.]+)", caption)
    sentiment, label, score = analyze(caption)
    return PostContent(
        url=f"https://www.instagram.com/p/{shortcode}/",
        shortcode=shortcode,
        author=author,
        caption=caption,
        media=media,
        hashtags=hashtags,
        mentions=mentions,
        sentiment=sentiment,
        sentiment_label=label,
        sentiment_score=score,
        source=source,
    )
