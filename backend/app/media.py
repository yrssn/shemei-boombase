"""帖子图片 / 视频的代理预览与下载。

Instagram CDN 链接会过期、跨域时浏览器忽略 download 文件名，且部分网络只有服务器（经 HTTP_PROXY_URL）能访问，
所以统一由后端转发。代理地址带 HMAC 签名，<img>/<video> 无需携带 token，也不会变成开放代理。
"""
import asyncio
import hashlib
import hmac
import io
import zipfile
from urllib.parse import quote, urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from starlette.background import BackgroundTask

from . import auth
from .config import Settings, get_settings
from .schemas import MediaItem, MediaZipRequest

router = APIRouter(prefix="/api/media", tags=["media"])
ALLOWED_HOST_SUFFIXES = (".cdninstagram.com", ".fbcdn.net")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
PASS_HEADERS = ("content-type", "content-length", "content-range", "accept-ranges", "last-modified", "etag")
EXT_BY_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/heic": "heic", "video/mp4": "mp4"}
MAX_ZIP_ITEMS = 30


def _sign(url: str, secret: str) -> str:
    return hmac.new(secret.encode(), url.encode(), hashlib.sha256).hexdigest()[:32]


def _check_host(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or not host.endswith(ALLOWED_HOST_SUFFIXES):
        raise HTTPException(400, "仅支持 Instagram 图片/视频地址")


def proxy_url(url: str, secret: str, download: str = "") -> str:
    params = {"u": url, "s": _sign(url, secret)}
    if download:
        params["dl"] = download
    return f"/api/media/proxy?{urlencode(params)}"


def attach_proxy_urls(items: list[MediaItem], secret: str) -> list[MediaItem]:
    for item in items:
        item.proxy_url = proxy_url(item.url, secret)
        item.download_url = proxy_url(item.url, secret, item.filename)
        if item.thumbnail:
            item.thumbnail_proxy_url = proxy_url(item.thumbnail, secret)
    return items


def _client(settings: Settings, timeout: float = 30) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": UA}, timeout=timeout, follow_redirects=True, proxy=settings.http_proxy_url or None
    )


@router.get("/proxy")
async def proxy(u: str, s: str, request: Request, dl: str = "",
                settings: Settings = Depends(get_settings)) -> StreamingResponse:
    if not hmac.compare_digest(_sign(u, settings.secret_key), s):
        raise HTTPException(403, "签名无效")
    _check_host(u)
    headers = {}
    if request.headers.get("range"):
        headers["Range"] = request.headers["range"]
    client = _client(settings)
    try:
        resp = await client.send(client.build_request("GET", u, headers=headers), stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(502, f"获取媒体失败：{exc.__class__.__name__}")
    if resp.status_code >= 400:
        await resp.aclose()
        await client.aclose()
        raise HTTPException(502, f"获取媒体失败：HTTP {resp.status_code}（链接可能已过期，请重新抓取）")
    out = {k: resp.headers[k] for k in PASS_HEADERS if k in resp.headers}
    out["Cache-Control"] = "private, max-age=3600"
    if dl:
        out["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(dl)}"

    async def close() -> None:
        await resp.aclose()
        await client.aclose()

    return StreamingResponse(resp.aiter_raw(), status_code=resp.status_code, headers=out,
                             background=BackgroundTask(close))


@router.post("/zip")
async def download_zip(body: MediaZipRequest, user: str = Depends(auth.get_current_user),
                       settings: Settings = Depends(get_settings)) -> Response:
    if not body.items:
        raise HTTPException(400, "没有可下载的媒体")
    if len(body.items) > MAX_ZIP_ITEMS:
        raise HTTPException(400, f"一次最多打包 {MAX_ZIP_ITEMS} 个文件")
    for item in body.items:
        _check_host(item.url)
    semaphore = asyncio.Semaphore(4)

    async with _client(settings, timeout=120) as client:
        async def fetch(item: MediaItem) -> tuple[bytes, str]:
            async with semaphore:
                resp = await client.get(item.url)
                resp.raise_for_status()
                return resp.content, resp.headers.get("content-type", "").split(";")[0]

        try:
            results = await asyncio.gather(*(fetch(i) for i in body.items))
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"下载媒体失败：{exc.__class__.__name__}（链接可能已过期，请重新抓取）")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for idx, (item, (content, ctype)) in enumerate(zip(body.items, results), start=1):
            name = item.filename or f"{body.shortcode or 'media'}_{idx:02d}.{EXT_BY_TYPE.get(ctype, 'bin')}"
            zf.writestr(name, content)
    zip_name = f"{body.shortcode or 'instagram'}_media.zip"
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(zip_name)}"})
