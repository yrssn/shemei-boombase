from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import auth, instagram, wecom
from .config import Settings, get_settings
from .schemas import ExtractRequest, HistoryItem, PostContent, WriteBackRequest, WriteBackResponse
from .storage import Storage

settings = get_settings()
app = FastAPI(title="内容矩阵管理发布系统 - Instagram 文案抓取", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
storage = Storage(settings.database_url)


@app.on_event("startup")
def init_db() -> None:
    storage.init_db()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "wecom_configured": settings.wecom_configured}


@app.post("/api/posts/extract", response_model=PostContent)
async def extract(body: ExtractRequest, user: str = Depends(auth.get_current_user),
                  settings: Settings = Depends(get_settings)) -> PostContent:
    return await instagram.fetch_post(body.url, proxy=settings.http_proxy_url)


@app.post("/api/posts/write-back", response_model=WriteBackResponse)
async def write_back(body: WriteBackRequest, user: str = Depends(auth.get_current_user),
                     settings: Settings = Depends(get_settings)) -> WriteBackResponse:
    record_id, doc_url = await wecom.add_record(
        settings, url=body.url, caption=body.caption, author=body.author,
        sentiment_label=body.sentiment_label, operator=user,
    )
    storage.add(url=body.url, shortcode=body.shortcode, author=body.author, caption=body.caption,
                sentiment_label=body.sentiment_label, operator=user, written_to_doc=True)
    return WriteBackResponse(ok=True, message="已写入企业微信文档", record_id=record_id, doc_url=doc_url)


@app.get("/api/posts/history", response_model=list[HistoryItem])
def history(user: str = Depends(auth.get_current_user)) -> list[HistoryItem]:
    return storage.list()
