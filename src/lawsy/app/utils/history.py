import json
import os
from pathlib import Path
from typing import Annotated, Union

import streamlit as st
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
        )

    def save(self, history_dir: Path | str) -> None:
        if is_history_dir_enabled():
            history_dir = Path(history_dir)
            history_dir.mkdir(parents=True, exist_ok=True)
            with open(history_dir / f"{self.id}.json", "w") as fout:
                json.dump(self.to_dict(), fout, ensure_ascii=False)
        st.session_state.history.insert(0, self)


def is_history_dir_enabled() -> bool:
    disabled = str(os.getenv("LAWSY_HISTORY_DIR_DISABLED", "False")).lower() not in ("0", "false", "no")
    return not disabled


def get_history(history_dir: Path | str) -> list[Report]:
    print(history_dir, is_history_dir_enabled())
    if is_history_dir_enabled():
        history_dir = Path(history_dir)
        if history_dir.exists():  # type: ignore
            history = []
            for history_file in history_dir.glob("*.json"):
                with open(history_file) as fin:
                    data = json.load(fin)
                history.append(Report.from_dict(data))
            history = sorted(history, key=lambda report: -report.timestamp)
            st.session_state.history = history
            return history
    if "history" not in st.session_state:
        st.session_state.history = []
    return st.session_state.history
