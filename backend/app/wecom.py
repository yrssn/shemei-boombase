"""企业微信智能表格写回。

文档：https://developer.work.weixin.qq.com/document/path/99907 （add_records）
"""
import time

import httpx
from fastapi import HTTPException

from .config import Settings

API = "https://qyapi.weixin.qq.com/cgi-bin"
_token_cache: dict[str, tuple[str, float]] = {}


async def _get_token(client: httpx.AsyncClient, settings: Settings) -> str:
    cached = _token_cache.get(settings.wecom_corp_id)
    if cached and cached[1] > time.time():
        return cached[0]
    resp = await client.get(
        f"{API}/gettoken",
        params={"corpid": settings.wecom_corp_id, "corpsecret": settings.wecom_corp_secret},
    )
    data = resp.json()
    if data.get("errcode"):
        raise HTTPException(502, f"企业微信获取 token 失败：{data.get('errmsg')}")
    token = data["access_token"]
    _token_cache[settings.wecom_corp_id] = (token, time.time() + data.get("expires_in", 7200) - 60)
    return token


def _text(value: str) -> list[dict]:
    return [{"type": "text", "text": value or ""}]


async def add_record(
    settings: Settings, *, url: str, caption: str, author: str, sentiment_label: str, operator: str
) -> tuple[str, str]:
    if not settings.wecom_configured:
        raise HTTPException(400, "尚未配置企业微信（WECOM_CORP_ID / WECOM_CORP_SECRET / WECOM_DOCID / WECOM_SHEET_ID）")
    async with httpx.AsyncClient(timeout=15) as client:
        token = await _get_token(client, settings)
        values = {
            settings.wecom_field_link: [{"type": "url", "link": url, "text": url}],
            settings.wecom_field_caption: _text(caption),
            settings.wecom_field_author: _text(author),
            settings.wecom_field_sentiment: _text(sentiment_label),
            settings.wecom_field_operator: _text(operator),
        }
        body = {
            "docid": settings.wecom_docid,
            "sheet_id": settings.wecom_sheet_id,
            "key_type": "CELL_VALUE_KEY_TYPE_FIELD_TITLE",
            "records": [{"values": values}],
        }
        resp = await client.post(f"{API}/wedoc/smartsheet/add_records", params={"access_token": token}, json=body)
        data = resp.json()
        if data.get("errcode"):
            if data.get("errcode") in (40014, 42001):
                _token_cache.pop(settings.wecom_corp_id, None)
            raise HTTPException(502, f"写入企业微信文档失败：{data.get('errmsg')}（errcode {data.get('errcode')}）")
        records = data.get("records") or []
        record_id = records[0].get("record_id", "") if records else ""
        doc_url = f"https://doc.weixin.qq.com/smartsheet/{settings.wecom_docid}"
        return record_id, doc_url
