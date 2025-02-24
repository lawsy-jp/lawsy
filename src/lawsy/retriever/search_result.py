from typing import Literal, Optional

from pydantic import BaseModel, HttpUrl

SourceType = Literal["article", "web"]


class BaseSearchResult(BaseModel):
    source_type: Optional[SourceType] = None

    # 共通情報
    title: str
    snippet: str
    score: Optional[float] = None
    url: HttpUrl | str  # (ugly fix) str is added to prevent https://github.com/pydantic/pydantic/issues/1684
    meta: dict

    def to_dict(self) -> dict:
        return self.model_dump()


class ArticleSearchResult(BaseSearchResult):
    source_type: Optional[SourceType] = "article"
    law_id: str
    rev_id: str  # xxx_xxx_xxx
    anchor: str


class WebSearchResult(BaseSearchResult):
    source_type: Optional[SourceType] = "web"
    full_content: Optional[str] = None


def to_search_result(data: dict) -> ArticleSearchResult | WebSearchResult:
    if "source_type" not in data:
        raise ValueError("data has no source_type")
    source_type = data["source_type"]
    if source_type == "article":
        return ArticleSearchResult(**data)
    elif source_type == "web":
        return WebSearchResult(**data)
    else:
        raise ValueError(f"invalid source_type: {source_type}")
