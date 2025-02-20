import json
import os
from pathlib import Path
from typing import Annotated, Union

import streamlit as st
from google.cloud import storage
from pydantic import BaseModel, ConfigDict

from lawsy.retriever.search_result import ArticleSearchResult, WebSearchResult, to_search_result

SearchResultType = Annotated[Union[ArticleSearchResult, WebSearchResult], ...]


class Report(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # これを追加
    id: str
    timestamp: float
    query: str
    refined_query: str | None = None
    topics: list[str]
    title: str
    outline: str = ""  # 新規項目で既存のreportには含まれないのでその場合は空文字
    report_content: str
    mindmap: str
    references: list  # list[SearchResultType] にすると Pydantic が union の解決に失敗するらしくエラーが出る…
    search_results: list  # list[SearchResultType] にすると Pydantic が union の解決に失敗するらしくエラーが出る…
    messages: list[dict[str, str]] | None = (
        None  # reasoning history in chat completion messages format (a list of {"role": ..., "content": ...})
    )
    news: list | None = None  # News用に追加

    @staticmethod
    def from_dict(d: dict) -> "Report":
        d = d.copy()
        references = [to_search_result(dd) for dd in d.pop("references")]
        search_results = [to_search_result(dd) for dd in d.pop("search_results")]
        return Report(**d, references=references, search_results=search_results)

    def to_dict(self) -> dict:
        return dict(
            id=self.id,
            timestamp=self.timestamp,
            query=self.query,
            refined_query=self.refined_query,
            topics=self.topics,
            title=self.title,
            outline=self.outline,
            report_content=self.report_content,
            mindmap=self.mindmap,
            references=[reference.model_dump(mode="json") for reference in self.references],
            search_results=[search_result.model_dump(mode="json") for search_result in self.search_results],
            messages=self.messages,
            news=self.news,
        )

    def save(self, user_id: str) -> None:
        history = [self] + get_history(user_id)
        client = get_storage_client()
        bucket = client.bucket(os.environ["HISTORY_BUCKET_NAME"])
        blob = bucket.blob(f"{user_id}.json")
        json_data = json.dumps([report.to_dict() for report in history], ensure_ascii=False)
        blob.upload_from_string(data=json_data, content_type="text/json")  # type: ignore
        st.session_state.history = history


def get_storage_client() -> storage.Client:
    key_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or "sa.json"
    if Path(key_file).exists():
        client = storage.Client.from_service_account_json(key_file)
    else:
        client = storage.Client()
    return client


def get_history(user_id: str) -> list[Report]:
    if "history" in st.session_state:
        return st.session_state.history
    client = get_storage_client()
    bucket = client.bucket(os.environ["HISTORY_BUCKET_NAME"])
    blob = bucket.blob(f"{user_id}.json")
    if blob.exists():  # type: ignore
        data = json.loads(blob.download_as_text())  # type: ignore
        history = [Report.from_dict(d) for d in data]  # type: ignore
        st.session_state.history = history
        return history
    else:
        st.session_state.history = []
        return []
