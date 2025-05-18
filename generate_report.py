import os
import json
import re
import nest_asyncio
import asyncio
from pathlib import Path
from typing import List, Optional, Callable, AsyncGenerator, Any, Literal

import dotenv
import numpy as np
import numpy.typing as npt
import faiss
import openai
from openai import OpenAI

import vertexai
from vertexai.preview.generative_models import GenerativeModel

import dspy
from dspy.adapters.chat_adapter import ChatAdapter
from pydantic import BaseModel, HttpUrl
import litellm
import requests
from bs4 import BeautifulSoup

# ---------------------------
# 環境変数と設定の初期化
# ---------------------------
# .env ファイルから環境変数を読み込む
dotenv.load_dotenv()

# OpenAIのクライアントを初期化
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Gemini（Vertex AI）の初期化
vertexai.init(project="lawsy-gov", location="asia-northeast1")
gemini = GenerativeModel("gemini-1.5-pro-002")

# Configの設定値
DEFAULT_CONFIG = {
    "free_web_search_enabled": True,
    "web_search_domains": ["go.jp", "courts.go.jp", "shugiin.go.jp", "sangiin.go.jp", "cao.go.jp"],
}

def get_config(name: str, default_value: Any = None) -> Any:
    return DEFAULT_CONFIG.get(name, default_value)

# Litellmの設定
litellm.vertex_location = "asia-northeast1"
litellm.cache = None

# ---------------------------
# 非同期処理のヘルパー関数
# ---------------------------
async def run_section_writer(writer, query, references, section_outline):
    async for _ in writer(query, references, section_outline):
        pass

async def run_conclusion_writer(writer, query, report_draft):
    async for _ in writer(query=query, report_draft=report_draft):
        pass

async def run_lead_writer(writer, query, title, draft):
    async for _ in writer(query=query, title=title, draft=draft):
        pass

nest_asyncio.apply()

# ---------------------------
# OpenAITextEmbeddingクラス
# ---------------------------
class OpenAITextEmbedding:
    def __init__(self, model: str = "text-embedding-3-small", dim: int = 1536):
        self.model = model
        self.dim = dim

    def _embed(self, texts: List[str]) -> List[List[float]]:
        response = client.embeddings.create(input=texts, model=self.model)
        return [e.embedding[:self.dim] for e in response.data]

    def get_query_embeddings(self, queries: List[str]) -> List[List[float]]:
        return self._embed(queries)

    def get_document_embeddings(self, documents: List[str]) -> np.ndarray:
        return np.array(self._embed(documents), dtype=np.float32)
    
# ---------------------------
# FaissFlatArticleRetrieverクラス
# ---------------------------
class Article(BaseModel):
    title: str
    url: str
    snippet: str
    anchor: str
    rev_id: str
    source_type: str

SourceType = Literal["article", "web"]

class BaseSearchResult(BaseModel):
    source_type: Optional[SourceType] = None

    title: str
    snippet: str
    score: Optional[float] = None
    url: HttpUrl | str
    meta: dict

    def to_dict(self) -> dict:
        return self.model_dump()
class ArticleSearchResult(BaseSearchResult):
    source_type: Optional[SourceType] = "article"
    law_id: str
    rev_id: str
    anchor: str

class FaissFlatArticleRetriever:
    def __init__(
        self,
        path: Path | str | None = None,
        dim: int | None = None,
    ) -> None:
        assert path is not None or dim is not None
        import json

        import faiss

        assert path is not None or (dim is not None and dim > 0)

        if path is not None:
            path = Path(path)
            self.index = faiss.read_index(str(path / "index.faiss"), faiss.IO_FLAG_MMAP)
            meta_data = []
            with open(path / "meta.jsonl") as fin:
                for line in fin:
                    meta_data.append(json.loads(line))
            self.meta_data = meta_data
            self.key_to_index = {(meta["file_name"], meta["anchor"]): i for i, meta in enumerate(self.meta_data)}
        else:
            self.index = faiss.IndexFlat(dim, faiss.METRIC_INNER_PRODUCT)
            self.meta_data = []
            self.key_to_index = {}

    @property
    def vector_dim(self) -> int:
        return self.index.d

    def get_vector(self, article: ArticleSearchResult) -> npt.NDArray[np.float32]:
        key = (article.rev_id, article.anchor)
        i = self.key_to_index[key]
        return self.index.reconstruct(i)  # type: ignore

    def search(self, vec: npt.NDArray[np.float64], k: int) -> list[ArticleSearchResult]:
        vec = vec[: self.vector_dim]
        vec = vec / np.linalg.norm(vec)
        cossims, indexs = self.index.search(vec.reshape(1, -1), k=k)  # type: ignore
        results = []
        for i, cossim in zip(indexs[0], cossims[0]):
            meta = self.meta_data[i]
            rev_id = meta["file_name"].split(".")[0]
            law_id = rev_id.split("_")[0]
            title = meta["title"]
            chunk = meta["chunk"]
            anchor = meta["anchor"]
            url = f"https://laws.e-gov.go.jp/law/{law_id}#{anchor}"
            result = ArticleSearchResult(
                law_id=law_id,
                rev_id=rev_id,
                title=title,
                snippet=chunk,
                score=cossim,
                anchor=anchor,
                url=url,
                meta=meta,
            )
            results.append(result)
        return results

    def add(self, vectors: npt.NDArray[np.float32], meta_data: list[dict]) -> None:
        self.index.add(vectors / np.linalg.norm(vectors, axis=1, keepdims=True))  # type: ignore
        self.meta_data.extend(meta_data)
        self.key_to_index.update({(meta["file_name"], meta["anchor"]): meta for meta in meta_data})

    def save(self, path: Path | str) -> None:
        import json

        import faiss

        path = Path(path)
        assert not path.exists() or path.is_dir()
        path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(path / "index.faiss"), faiss.IO_FLAG_MMAP)
        with open(path / "meta.jsonl", "w") as fout:
            for record in self.meta_data:
                print(json.dumps(record, ensure_ascii=False), file=fout)

    @staticmethod
    def create(dim: int) -> "FaissFlatArticleRetriever":
        assert dim > 0
        return FaissFlatArticleRetriever(dim=dim)

    @staticmethod
    def load(path: Path | str) -> "FaissFlatArticleRetriever":
        return FaissFlatArticleRetriever(path=path)

# ---------------------------
# DuckDuckGoSearchWebRetrieverクラス
# ---------------------------
class DuckDuckGoSearchWebRetriever:
    class Result(BaseModel):
        title: str
        url: str
        snippet: str
        source_type: str = "web"

    def search(self, query: str, k: int = 10, domains: Optional[List[str]] = None) -> List["DuckDuckGoSearchWebRetriever.Result"]:
        results = []
        headers = {"User-Agent": "Mozilla/5.0"}
        q = query
        if domains:
            q += " site:" + " OR site:".join(domains)

        url = f"https://html.duckduckgo.com/html?q={requests.utils.quote(q)}"

        try:
            r = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            links = soup.select(".result__a")
            snippets = soup.select(".result__snippet")
            for i in range(min(k, len(links))):
                title = links[i].get_text()
                href = links[i]["href"]
                snippet = snippets[i].get_text() if i < len(snippets) else ""
                results.append(self.Result(title=title, url=href, snippet=snippet))
        except Exception as e:
            print("Web search failed:", e)
        return results

# ---------------------------
# Query処理系 (Refinement and Expansion)
# ---------------------------
# RefineQuery: ユーザーのクエリを検索向けに変換
class RefineQuery(dspy.Signature):
    """
    あなたはWebの扱いに長けた優秀な法律家です。
    下記のユーザーのクエリーにたいして、法令観点からの回答を与えてくれそうな簡潔なクエリーを一つ作ってください。
    なお、作成にあたっては下記を守って下さい。

    - 法令観点からの回答を与えてくれそうなクエリーをつくること
    - あなたの作ったクエリーは可能な限りユーザーが作ったクエリーの意図と過不足なく一致させること
    - クエリーは日本語で作成すること
    - Web検索に最適化すること
    - 簡潔であること
    """

    query = dspy.InputField(desc="ユーザーのクエリー", format=str)
    refined_query = dspy.OutputField(desc="検索に最適化されたクエリー", format=str)

class QueryRefiner(dspy.Module):
    def __init__(self, lm):
        self.refine_query = dspy.Predict(RefineQuery)
        self.lm = lm

    def forward(self, query: str) -> dspy.Prediction:
        with dspy.settings.context(lm=self.lm):
            result = self.refine_query(query=query)
        return dspy.Prediction(refined_query=result.refined_query)

# GenerateDetailedTopics: Web検索結果から有用なトピックを抽出
class GenerateDetailedTopics(dspy.Signature):
    """あなたは日本の法令に精通した専門家です。
    下記のクエリーに関して、事前にWeb検索をして簡単に下調べしてあります。
    Web検索結果もふまえ、クエリーに関する法令の解説・解釈文書を作成するために必要な法令を検索しようとしています。
    法令検索はセマンティックサーチできるのでキーワード・短文などで検索可能です。

    解説・解釈に必要な法令を適切にヒットさせきるための検索トピックを以下の形式でリストアップしてください。

    出力フォーマット：
    - xxx
    - yyy
    - ...
    - zzz

    検索トピックをリストアップするにあたり、以下の条件を遵守してください。

    - クエリーの意味を十分汲み取ること
    - クエリーに対する法令解説・解釈を行うのに必要な法令が揃うように検索トピックをリストアップしてください
    - 一般的な用語は法令での専門用語を優先してください。法令用語が含まれていない場合は、該当しそうな法令用語や関連用語を補完してください
    - 検索トピックは可能な限り互いに重複せず、個別に調査可能な形にしてください。 **self-contained** であるべきです
    - 検索トピックは法令コーパスに準拠した具体的なものにしてください（短文または具体的な法令用語）
    - 検索精度を高めるため、法令での使用が想定される具体的な専門用語や関連する条文番号を含めてください
    - 検索トピックをナンバリングする必要はありません。検索トピックの内容のみ記載してください
    - 検索トピックの個数は多くても10個までにしてください。多ければよいというわけではないです
    """

    query = dspy.InputField(desc="クエリー", format=str)
    web_search_results = dspy.InputField(desc="Web検索結果", format=str)
    topics = dspy.OutputField(desc="検索トピック", format=str)

def cleanse_topic(topic: str) -> str:
    topic = topic.strip()
    if topic.startswith("- "):
        topic = topic[2:].strip()
    return topic.strip()

class QueryExpander(dspy.Module):
    def __init__(self, lm):
        self.generate_detailed_topics = dspy.Predict(GenerateDetailedTopics)
        self.lm = lm

    def forward(self, query: str, web_search_results: str) -> dspy.Prediction:
        with dspy.settings.context(lm=self.lm):
            result = self.generate_detailed_topics(query=query, web_search_results=web_search_results)
            topics = [cleanse_topic(t) for t in result.topics.splitlines() if t.strip()]
        return dspy.Prediction(topics=topics)

# ---------------------------
# アウトライン生成系
# ---------------------------
class SubsectionOutline(BaseModel):
    title: str
    reference_ids: list[int]

    def to_text(self) -> str:
        return "\n".join([
            "### " + self.title,
            "".join([f"[{ref_id}]" for ref_id in self.reference_ids])
        ]).strip()

class SectionOutline(BaseModel):
    title: str
    subsection_outlines: list[SubsectionOutline]

    def to_text(self) -> str:
        return "\n".join([
            "## " + self.title
        ] + [s.to_text() for s in self.subsection_outlines])

class Outline(BaseModel):
    title: str
    section_outlines: list[SectionOutline]

    def to_text(self) -> str:
        return "\n".join([
            "# " + self.title
        ] + [s.to_text() for s in self.section_outlines])

class CreateOutline(dspy.Signature):
    """あなたは、ニュースを常にフォローしつつ、日本の法令に精通している専門家です。収集された情報源をもとに、下記のクエリーに対するレポートとして適切なアウトラインと簡潔なタイトルを作成してください。また、最後にレポートのタイトルを作成してください。結論パートは絶対に作成しないでください。

    アウトラインは以下のMarkdownフォーマットに従って作成し、次のルールを厳守すること。
    1. クエリーに対して、法令観点での解説・解釈を含む回答を目的とした構成にする。
    2. "# Title" をレポートのタイトルに用いる。
    3. "## Title" をセクションのタイトルとして用いる。
       - 各セクション ("## Title") に対して、必ず2～3個以上のサブセクション ("### Title") を生成すること
       - セクション数はクエリーに応じて5～20個の間で作成すること。網羅的な回答が必要な場合、セクション数は多い方が好ましい
    4. "### Title" をサブセクションのタイトルとして用いる。
       - 各サブセクションには、収集された情報源をできるだけ多く含めるようにし、必ず最低3～5個以上の異なる引用番号を使用すること
       - サブセクション同士で内容が類似しそうな場合（情報源の法令・条文が同じ、タイトルが酷似）、サブセクションは統合し、他の論点のサブセクションを追加すること
       - サブセクションの引用番号が他と重複する場合、より多様な情報源を取り入れるために、アウトライン全体を統合・再編成すること
       - 必要に応じて、さらに下位の階層も同様に2つ以上生成すること。
    5. 引用情報の記載方法
       - 今後必要となるので、"### Title"のサブセクションタイトル作成の際には参照した条文の引用番号を記載
       - 引用番号はサブセクションの次の行に記載すること。セクション、サブセクションの行には引用番号はつけない。
       - "### Title [3][4]" のように同じ行に引用番号を記載してはならない
    6. Markdownフォーマットに関するルール
       - "## 結論"という結論パートは絶対に作成してはいけない
       - 出力には "# Title", "## Title"、"### Title"、"#### Title" などのMarkdown形式のタイトル以外のテキストを一切含めないこと
       - "#### Title"というサブサブセクションは作成しないこと
       - ナンバリングは不要
       - "#", "##", "###" の階層のみ作成すること
    7. 各行はタイトル、セクション、サブセクション、引用番号のいずれかでそれ以外の情報を記載してはならない

    【出力例】
    # レポートタイトル
    ## セクション1
    ### サブセクション1
    [4][67]
    ### サブセクション2
    [30][28][1][27][102]
    ## セクション2
    ### サブセクション1
    [14][25][9][96]
    ### サブセクション2
    [2][24][51]
    ### サブセクション3
    [29][11][4][56]
    ...

    【不適切な出力例】
    # レポートタイトル: xxx    // 「レポートタイトル: 」という修飾はNG
    ## セクション1
    ### サブセクション1 [4][67]    // 引用はサブセクションの行にはつけない
    [4][67]
    このサブセクションでは...    // 説明文など要求していない不要な行は削除
    ### サブセクション2 [30][28][1][27][102]    // 同上
    [30][28][1][27][102]
    ## セクション2
    [2][24][29][11][4]    // セクション自体に引用がついている
    ### サブセクション1
    ### サブセクション: yyy    // 「サブセクション: 」という修飾はNG
    [2][24][51]
    ### サブセクション3
    [29][11][4][156]     // （引用が例えば110までしかない場合）156は存在しない引用
    """

    query = dspy.InputField(desc="クエリー", format=str)
    topics = dspy.InputField(desc="拡張トピック", format=str)
    references = dspy.InputField(desc="情報源（引用番号付き）", format=str)
    outline = dspy.OutputField(desc="アウトライン", format=str)

class FixOutline(dspy.Signature):
    """あなたは校正や編集業務に定評のある腕利きのアシスタントです。
    収集された情報源をもとに、法令解説・解釈レポートのアウトラインを作ったのですが、一部、下記のアウトライン作成ルールを逸脱している可能性があります。
    下記のルールを守るように校正・編集してください。

    1. クエリーに対して、法令観点での解説・解釈を含む回答を目的とした構成にする。
    2. "# Title" をレポートのタイトルに用いる。
    3. "## Title" をセクションのタイトルとして用いる。
       - 各セクション ("## Title") に対して、必ず2～3個以上のサブセクション ("### Title") を生成すること
       - セクション数はクエリーに応じて5～20個の間で作成すること。網羅的な回答が必要な場合、セクション数は多い方が好ましい
    4. "### Title" をサブセクションのタイトルとして用いる。
       - 各サブセクションには、収集された情報源をできるだけ多く含めるようにし、必ず最低3～5個以上の異なる引用番号を使用すること
       - サブセクション同士で内容が類似しそうな場合（情報源の法令・条文が同じ、タイトルが酷似）、サブセクションは統合し、他の論点のサブセクションを追加すること
       - サブセクションの引用番号が他と重複する場合、より多様な情報源を取り入れるために、アウトライン全体を統合・再編成すること
       - 必要に応じて、さらに下位の階層も同様に2つ以上生成すること。
    5. 引用情報の記載方法
       - 今後必要となるので、"### Title"のサブセクションタイトル作成の際には参照した条文の引用番号を記載
       - 引用番号はサブセクションの次の行に記載すること。
       - "### Title [3][4]" のように同じ行に引用番号を記載してはならない
       - 存在しない引用番号を引用してはならない
    6. Markdownフォーマットに関するルール
       - "## 結論"という結論パートは絶対に作成してはいけない
       - 出力には "# Title", "## Title"、"### Title"、"#### Title" などのMarkdown形式のタイトル以外のテキストを一切含めないこと
       - "#### Title"というサブサブセクションは作成しないこと
       - ナンバリングは不要
       - "#", "##", "###" の階層のみ作成すること
    7. 各行はタイトル、セクション、サブセクション、引用番号のいずれかでそれ以外情報を決して記載しない


    【修正が必要な入力アウトライン例】

    ```
    # レポートタイトル: xxx    // 「レポートタイトル: 」という修飾はNG
    ## セクション1
    ### サブセクション1 [4][67]    // 引用はサブセクションの行にはつけない
    [4][67]
    このサブセクションでは...    // 説明文など要求していない不要な行は削除
    ### サブセクション2 [30][28][1][27][102]    // 同上
    [30][28][1][27][102]
    ## セクション2
    [2][24][29][11][4]    // セクション自体に引用がついている
    ### サブセクション1
    ### サブセクション: yyy    // 「サブセクション: 」という修飾はNG
    [2][24][51]
    ### サブセクション3
    [29][11][4][56]
    ```

    【修正済みアウトライン例】

    ```
    # xxx
    ## セクション1
    ### サブセクション1
    [4][67]
    ### サブセクション2
    [30][28][1][27][102]
    ## セクション2
    ### サブセクション1
    [14][25][9]
    ### yyy
    [2][24][51]
    ### サブセクション3
    [29][11][4][56]
    ```
    """

    outline = dspy.InputField(desc="元のアウトライン", format=str)
    fixed_outline = dspy.OutputField(desc="修正されたアウトライン", format=str)

class OutlineCreater(dspy.Module):
    def __init__(self, lm):
        self.lm = lm
        self.gen_outline = dspy.Predict(CreateOutline)
        self.fix_outline = dspy.Predict(FixOutline)

    @staticmethod
    def __parse_outline(outline: str) -> Outline:
        report_title = None
        section_title = None
        subsection_title = None
        section_outlines = []
        subsection_outlines = []
        reference_ids = []

        for line in outline.splitlines():
            if not line.strip():
                continue
            elif line.startswith("# "):
                report_title = line[2:].strip()
            elif line.startswith("## "):
                if section_title and subsection_outlines:
                    section_outlines.append(
                        SectionOutline(title=section_title, subsection_outlines=subsection_outlines)
                    )
                section_title = line[3:].strip()
                subsection_outlines = []
            elif line.startswith("### "):
                if subsection_title is not None:
                    subsection_outlines.append(
                        SubsectionOutline(title=subsection_title, reference_ids=reference_ids)
                    )
                subsection_title = line[4:].strip()
                reference_ids = []
            else:
                reference_ids = [int(x) for x in re.findall(r"\[(\d+)\]", line)]
                if subsection_title:
                    subsection_outlines.append(
                        SubsectionOutline(title=subsection_title, reference_ids=reference_ids)
                    )
                    subsection_title = None

        if subsection_title and reference_ids:
            subsection_outlines.append(SubsectionOutline(title=subsection_title, reference_ids=reference_ids))
        if section_title and subsection_outlines:
            section_outlines.append(SectionOutline(title=section_title, subsection_outlines=subsection_outlines))

        return Outline(title=report_title or "Untitled", section_outlines=section_outlines)

    def forward(self, query: str, topics: list[str], references: list[str]) -> dspy.Prediction:
        topics_text = "\n".join([f"- {t}" for t in topics])
        references_text = "\n\n".join(references)
        with dspy.settings.context(lm=self.lm):
            create_result = self.gen_outline(query=query, topics=topics_text, references=references_text)
            fix_result = self.fix_outline(outline=create_result.outline)
        outline = self.__parse_outline(fix_result.fixed_outline)
        return dspy.Prediction(outline=outline)


# ---------------------------
# ライター群：本文、結論、リード生成
# ---------------------------
class StreamLineWriter:
    def __init__(self, lm, signature_cls) -> None:
        self.lm = lm
        self.signature_cls = signature_cls
        self.keywords = list(signature_cls.model_fields.keys()) + ["completed"]
        self.__text = None

    def get_generated_text(self) -> str:
        assert self.__text is not None
        return self.__text

    async def generate(
        self, input_kwargs: dict[str, str], line_fixer: Callable | None = None
    ) -> AsyncGenerator[str, None]:
        adapter = ChatAdapter()
        messages = adapter.format(
            self.signature_cls, [], input_kwargs
        )
        response = await litellm.acompletion(
            model=self.lm.model,
            messages=messages,
            stream=True,
            num_retries=self.lm.num_retries,
            extra_headers={"Connection": "close"},
            **self.lm.kwargs,
        )
        buf = ""
        text = ""
        async for chunk in response:
            content = chunk.choices[0]["delta"].get("content", "")
            if content is None:
                content = ""
            buf += content
            for keyword in self.keywords:
                buf = buf.replace(f"[[ ## {keyword} ## ]]", "")
            if "\n" in buf:
                head, buf = buf.split("\n", 1)
                if line_fixer:
                    head = line_fixer(head)
                yield head + "\n"
                text += head + "\n"
        if buf:
            yield buf
            text += buf
        self.__text = text

class WriteSection(dspy.Signature):
    """あなたは日本の法令に精通し、適切な法令解釈を行い、分かりやすい解説を書くことに定評のある信頼できる粘り強いライターです。
    下記のクエリーに関する調査をしており、クエリーをもとにレポートのアウトラインを作成しました。
    アウトラインの中にある引用番号は漏れることなく必ず参照し、収集された情報源の内容を適切に解釈しながら各セクションの内容を記載してください。必ず各サブセクションごとに400字以上記載してください。
    解説は緻密かつ包括的で情報量が多く、情報源に基づいたものであることが望ましいです。法令に詳しくない人向けにわかりやすくかみ砕いて説明することも重要です。必要に応じて、用いている法令の概要、関連法規、適切な事例、歴史的背景、最新の判例などを盛り込んでください。
    なお、内容の信頼性が重要なので、必ず情報源にあたり、下記指示にあるように引用をするのを忘れないで下さい。
    1. アウトラインの"# Title"、"## Title"、"### Title"のタイトルは変更しないでください。
    2. 必ず情報源の情報に基づき記載し、ハルシネーションに気をつけること。
       記載の根拠となる参照すべき情報源は "...です[4][1][27]。" "...ます[21][9]。" のように明示。
       その記述に対しての関連性が高そうな順に付与してください。
    3. 正しく引用を明示されているほどあなたの解説は高く評価されます。
       引用なしの創作は論拠が明確でない限り全く評価されません。
    4. 情報源を解説の末尾に含める必要はありません。
    5. 日本語のですます調で解説を書いてください。
    6. 引用は文面を引用する論理的な必要性がない限り、引用番号の引用のみにしてください。
    7. 「収集された情報源と引用番号」にない番号を引用しないでください。それは創作になってしまい価値を既存します。
    """

    query = dspy.InputField(desc="クエリー", format=str)
    references = dspy.InputField(desc="引用情報", format=str)
    section_outline = dspy.InputField(desc="アウトライン", format=str)
    section = dspy.OutputField(desc="生成されたセクション本文", format=str)


class StreamSectionWriter(StreamLineWriter):
    def __init__(self, lm) -> None:
        super().__init__(lm=lm, signature_cls=WriteSection)

    async def __call__(self, query: str, references: str, section_outline: str) -> AsyncGenerator[str, None]:
        async for chunk in self.generate(
            {"query": query, "references": references, "section_outline": section_outline}
        ):
            yield chunk
        self.section_content = self.get_generated_text()

class WriteConclusion(dspy.Signature):
    """あなたは日本の法令に精通し、分かりやすい解説を書くことに定評のある信頼できるライターです。
    レポートのドラフトを踏まえて、レポート全体の要約を本文とはできるだけ異なる表現で記載しつつ、今後の方向性や対応策を含んだ結論部の中身を生成します。
    最低でも400字以上、可能なら600字以上記載してください。
    結論の文章部分のみ生成し、"## 結論" のようなヘッダは入れないでください。
    """
    query = dspy.InputField(desc="クエリー", format=str)
    report_draft = dspy.InputField(desc="ドラフト本文", format=str)
    conclusion = dspy.OutputField(desc="結論文", format=str)


class StreamConclusionWriter(StreamLineWriter):
    def __init__(self, lm) -> None:
        super().__init__(lm=lm, signature_cls=WriteConclusion)

    async def __call__(self, query: str, report_draft: str) -> AsyncGenerator[str, None]:
        async for chunk in self.generate({"query": query, "report_draft": report_draft}):
            yield chunk
        self.conclusion = self.get_generated_text()

class WriteLead(dspy.Signature):
    """あなたは日本の法令に精通し、分かりやすい解説を書くことに定評のある信頼できるライターです。
    下記のクエリーに関する調査をしており、レポートを作成しました。レポートタイトルの直後に表示する簡潔なリード文を生成してください。
    リード文とは、レポート全体のabstractとなる、レポート全体の論旨の展開や主要トピックを含めた簡潔な文章です。

    リード文の生成にあたって次のルールを厳守すること
    - リード文では、レポート全体の文脈やレポートで扱われている主要なトピックに対する簡潔な概要を提示し、それ単独でも読める内容にすること
    - リード文の文字数は140〜280文字程度とすること
    - リード文の文面のみ生成すること。
    """
    query = dspy.InputField(desc="クエリー", format=str)
    title = dspy.InputField(desc="レポートタイトル", format=str)
    draft = dspy.InputField(desc="レポートドラフト", format=str)
    lead = dspy.OutputField(desc="リード文", format=str)

class StreamLeadWriter(StreamLineWriter):
    def __init__(self, lm) -> None:
        super().__init__(lm=lm, signature_cls=WriteLead)

    async def __call__(self, query: str, title: str, draft: str) -> AsyncGenerator[str, None]:
        async for chunk in self.generate({"query": query, "title": title, "draft": draft}):
            yield chunk
        self.lead = self.get_generated_text()

# ---------------------------
# 補助関数：拡張トピックを用いた融合用クエリの構築
def construct_query_for_fusion(expanded_queries: list[str]) -> str:
    query = expanded_queries[0]
    topics = expanded_queries[1:]
    return "\n".join(
        [
            "以下の内容に関する法令解説文書を作るにあたって参考になるWebページや法令がほしい",
            "",
            "主題となるクエリー: " + query,
            "関連するトピック:",
        ]
        + ["- " + topic for topic in topics]
    )

# ---------------------------
# メイン関数：レポート生成処理
async def generate_report(query: str) -> str:
    print("レポートを生成中...")

    # 1. モデルと検索器の初期化
    #lm = dspy.LM("openai/gpt-4o", api_key=os.environ["OPENAI_API_KEY"], max_tokens=8192, temperature=0.0)
    lm = dspy.LM(provider="vertexai",
                 model="gemini-1.5-pro-002", 
                 project="lawsy-gov", 
                 location="asia-northeast1",
                 max_tokens=8192, 
                 temperature=0.0)
    vector_search_article_retriever = FaissFlatArticleRetriever.load(Path("outputs/lawsy/article_chunks_faiss"))
    # Faissのインデックスとメタ情報を読み込み
    text_encoder = OpenAITextEmbedding(dim=vector_search_article_retriever.vector_dim)
    web_retriever = DuckDuckGoSearchWebRetriever()

    # 2. Web検索（フリードメインとドメイン指定検索の両方）
    web_search_results = []
    # フリー検索
    if str(get_config("free_web_search_enabled", "True")).lower() == "true":
        hits = web_retriever.search(query, k=10)
        web_search_results.extend(hits)
    # ドメイン指定検索
    domains_config = get_config("web_search_domains", "go.jp, courts.go.jp, shugiin.go.jp, sangiin.go.jp, mof.go.jp")
    if isinstance(domains_config, str):
        domains = [d.strip() for d in domains_config.split(",") if d.strip()]
    elif isinstance(domains_config, list):
        domains = domains_config
    else:
        domains = []

    if domains:
        hits = web_retriever.search(query, k=10, domains=domains)
        web_search_results.extend(hits)
    print(f"🌐 Web検索結果: {len(web_search_results)}件")

    # 3. クエリのリファイン（検索最適化）
    query_refiner = QueryRefiner(lm=lm)
    query_refiner_result = query_refiner(query=query)
    refined_query = query_refiner_result.refined_query
    print(f"\n🔍 検索向けクエリ: {refined_query}\n")

    # 4. refined_query でもう一度Web検索
    free_hits = web_retriever.search(refined_query, k=10)
    domain_hits = web_retriever.search(refined_query, k=10, domains=domains) if domains else []
    web_search_results = free_hits + domain_hits
    print(f"🌐 Web検索結果 (refined): {len(web_search_results)}件")

    # 5. 拡張トピック生成（Web結果から法令トピック抽出）
    query_expander = QueryExpander(lm=lm)
    web_search_result_texts = []
    for i, result in enumerate(web_search_results, start=1):
        web_search_result_texts.append(f"[{i}] {result.title}\n{result.snippet}")
    web_search_results_text = "\n\n".join(web_search_result_texts)
    query_expander_result = query_expander(query=query, web_search_results=web_search_results_text)
    expanded_queries = [query] + query_expander_result.topics
    print(f"🧠 拡張トピック: {query_expander_result.topics}")

    # 6. 法令検索：埋め込みベクトルを使って法令記事を検索
    article_search_results = []
    query_vectors = text_encoder.get_query_embeddings(expanded_queries)
    for expanded_query, query_vector in zip(expanded_queries, query_vectors):
        hits = vector_search_article_retriever.search(query_vector, k=10)
        article_search_results.extend(hits)

    print(f"📚 法令検索ヒット数: {len(article_search_results)}")

    # 7. 検索結果の統合とリランキング（Web+法令）
    url_to_articles = {result.url: result for result in article_search_results}
    unique_article_search_results = list(url_to_articles.values())
    url_to_web_pages = {
        result.url: result for result in web_search_results if result.url not in url_to_articles
    }
    unique_web_search_results = list(url_to_web_pages.values())

    # セマンティック融合用クエリとベクトル化
    rich_query = construct_query_for_fusion(expanded_queries=expanded_queries)
    dim = vector_search_article_retriever.vector_dim
    rich_query_vec = text_encoder.get_query_embeddings([rich_query])[0][:dim]
    web_page_vecs = text_encoder.get_document_embeddings(
        [result.title + "\n" + result.snippet for result in unique_web_search_results]
    )[:, :dim]
    article_vecs = np.asarray(
        [vector_search_article_retriever.get_vector(result) for result in unique_article_search_results]
    )
    search_results = unique_web_search_results + unique_article_search_results
    vecs = np.vstack([web_page_vecs, article_vecs])
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    cossims = vecs.dot(rich_query_vec / np.linalg.norm(rich_query_vec))
    index = np.argsort(cossims)[::-1]
    search_results = [search_results[i] for i in index]

    # 8. 引用用の参照情報の整理
    references = []
    seen = set()
    total_length = 0
    for i, result in enumerate(search_results, start=1):
        if result.source_type == "article":
            if (result.rev_id, result.anchor) in seen:
                continue
            chunk_after_title = "\n".join(result.snippet.split("\n")[1:])
            reference = f"[{i}] {result.title}\n{chunk_after_title[:1024]}"
            references.append(reference)
            total_length += len(reference)
            seen.add((result.rev_id, result.anchor))
        elif result.source_type == "web":
            if result.url in seen:
                continue
            reference = f"[{i}] {result.title}\n{result.snippet}"
            references.append(reference)
            total_length += len(reference)
            seen.add(result.url)
        if len(seen) >= 200 or total_length >= 100000:  # max 128k tokens for GPT-4o
            break

    print(f"✅ 参照文献数: {len(references)}")

    # 9. アウトライン生成：生成された拡張トピックと参照情報をもとにアウトラインを作成
    outline_creater = OutlineCreater(lm=lm)
    outline_result = outline_creater(query=query, topics=query_expander_result.topics, references=references)
    outline = outline_result.outline
    print(f"\n🗂 レポートタイトル: {outline.title}")


    # 10. セクション本文生成：アウトラインに沿って各セクションの本文を生成
    section_tasks = []
    section_writers = []
    id2ref = {i + 1: result for i, result in enumerate(search_results)}

    for section in outline.section_outlines:
        writer = StreamSectionWriter(lm=lm)
        section_writers.append(writer)

        # 各セクションで利用する引用情報を集める
        ref_ids = set()
        for ss in section.subsection_outlines:
            ref_ids.update(ss.reference_ids)
        ref_texts = "\n\n".join([
            f"[{i}] {id2ref[i].title}\n{id2ref[i].snippet}"
            for i in sorted(ref_ids) if i in id2ref
        ])

        # run_section_writer で非同期タスクを作成
        section_tasks.append(run_section_writer(writer, query, ref_texts, section.to_text()))

    async def run_all_section_tasks():
      for task in section_tasks:
        await task

    await run_all_section_tasks()

    # セクション本文を全て連結
    section_text = "\n".join([writer.section_content for writer in section_writers])

    # 11. 結論生成：レポート全体のドラフトを元に結論を生成
    conclusion_writer = StreamConclusionWriter(lm=lm)
    report_draft = "# " + outline.title + "\n" + section_text
    await run_conclusion_writer(conclusion_writer, query, report_draft)
    conclusion = conclusion_writer.conclusion

    # 12. リード生成：レポート全体を要約するリード文を生成
    lead_writer = StreamLeadWriter(lm=lm)
    full_draft = report_draft + "\n\n## 結論\n" + conclusion
    await run_lead_writer(lead_writer, query, outline.title, full_draft)
    lead = lead_writer.lead

    # 13. 参考文献セクションの生成
    references_section = "\n\n".join(references)

    # 13. レポート全体の組み立て：タイトル、リード、本文、結論、参考文献を結合
    final_report = "\n".join([
        "# " + outline.title,
        lead,
        section_text,
        "## 結論",
        conclusion,
        "## References",
        references_section
    ])

    print("\n🎉 レポート生成完了！\n")
    return final_report

if __name__ == "__main__":
    q = input("調べたい法令に関する質問を入力してください：")
    import asyncio
    report = asyncio.run(generate_report(q))
    print("\n" + "="*80 + "\n")
    print(report)