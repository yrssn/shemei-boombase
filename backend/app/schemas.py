from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class ExtractRequest(BaseModel):
    url: str = Field(..., description="Instagram 帖子链接")


class MediaItem(BaseModel):
    type: str = Field("image", description="image / video")
    url: str
    thumbnail: str = ""
    width: int = 0
    height: int = 0
    filename: str = ""
    proxy_url: str = ""
    thumbnail_proxy_url: str = ""
    download_url: str = ""


class MediaZipRequest(BaseModel):
    shortcode: str = ""
    items: list[MediaItem]


class PostContent(BaseModel):
    url: str
    shortcode: str
    author: str = ""
    caption: str = ""
    media: list[MediaItem] = []
    hashtags: list[str] = []
    mentions: list[str] = []
    sentiment: str = "neutral"
    sentiment_label: str = "中性"
    sentiment_score: float = 0.0
    source: str = ""


class WriteBackRequest(BaseModel):
    url: str
    shortcode: str = ""
    author: str = ""
    caption: str
    sentiment_label: str = "中性"


class WriteBackResponse(BaseModel):
    ok: bool
    message: str
    record_id: str = ""
    doc_url: str = ""


class HistoryItem(BaseModel):
    id: int
    url: str
    shortcode: str
    author: str
    caption: str
    sentiment_label: str
    operator: str
    written_to_doc: bool
    created_at: str
