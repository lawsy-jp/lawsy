import asyncio
import datetime
import os
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import dotenv
import numpy as np
import streamlit as st

from lawsy.ai.outline_creater import OutlineCreater
from lawsy.ai.query_expander import QueryExpander
from lawsy.ai.query_refiner import QueryRefiner
from lawsy.ai.report_writer import StreamConclusionWriter, StreamLeadWriter, StreamSectionWriter
from lawsy.app.config import get_config
from lawsy.app.report import REPORT_PAGES, create_report_page
from lawsy.app.styles.decorate_html import (
    get_hiddenbox_ref_html,
)
from lawsy.app.utils.history import Report
from lawsy.app.utils.lm import load_lm
from lawsy.app.utils.mindmap import draw_mindmap
from lawsy.app.utils.preload import (
    load_text_encoder,
    load_vector_search_article_retriever,
)
from lawsy.app.utils.web_retreiver import load_web_retriever
from lawsy.utils.logging import logger


def get_logo_path() -> Path:
    return Path(__file__).parent / "Lawsy_logo_circle.png"


def get_logotitle_path() -> Path:
    return Path(__file__).parent / "Lawsy_logo_title_long_trans.png"


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
        + ["- " + query for query in topics]
    )


async def write_section(section_placeholder, section_writer, query: str, references: str, section_outline: str):
    # section_placeholder.write_stream()
    text = ""
    async for chunk in section_writer(query, references, section_outline):
        text += chunk
        section_placeholder.write(text)


def create_research_page():
    dotenv.load_dotenv()
    css = (Path(__file__).parent / "styles" / "style.css").read_text()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

    text_encoder = load_text_encoder()
    vector_search_article_retriever = load_vector_search_article_retriever()
    web_search_engine_name = os.getenv("LAWSY_WEB_SEARCH_ENGINE", "DuckDuckGo")
    logger.info(f"using web search engine: {web_search_engine_name}")
    web_retriever = load_web_retriever(web_search_engine_name)
    logo = get_logo_path()

    lm_name = os.getenv("LAWSY_LM", "openai/gpt-4o")
    logger.info(f"using LM: {lm_name}")
    lm = load_lm(lm_name)

    logo_col, _ = st.columns([1, 5])
    with logo_col:
        st.image(get_logotitle_path())

    with st.container():
        query_container = st.empty()
        query = query_container.chat_input(
            placeholder="法令について何でも聞いてください！",
            key="research_page_query_chat_input",
        )
        st.markdown(
            """
            <style>
            .custom-text-warning {
                color: grey !important;
                font-size: 12px !important;
                margin-top: -30px !important; /* 上に詰める */
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        warning_text = (
            '<p class="custom-text-warning">'
            "　 ※Lawsyの回答は必ずしも正しいとは限りません。重要な情報は確認するようにしてください。"
            "</p>"
        )
        st.markdown(warning_text, unsafe_allow_html=True)
    if not query:
        return

    messages = []
    query_container.empty()
    logger.info("query: " + query)

    ph = st.empty()
    status = st.status("推論中...", expanded=False)

    content = query
    with status:
        status.update(state="running")
        with st.chat_message("user"):
            st.write(content)
    ph.empty()
    with ph.container():
        with st.chat_message("user"):
            st.write(content)
    messages.append({"role": "user", "content": content})

    # refine query
    if len(query) >= 64:
        status.update(label="クエリーを検索向けに変換...", state="running")
        query_refiner = QueryRefiner(lm=lm)
        query_refiner_result = query_refiner(query=query)
        refined_query = query_refiner_result.refined_query
        logger.info(f"refined_query: {refined_query}")
        content = f"検索向けに変換されたクエリー:\n\n{refined_query}"
        with status:
            with st.chat_message("assistant", avatar=logo):
                st.write(content)
        ph.empty()
        with ph.container():
            with st.chat_message("assistant", avatar=logo):
                st.write(content)
        messages.append({"role": "assistant", "content": content})
    else:
        refined_query = query

    web_search_results = []

    # free web search
    if get_config("free_web_search_enabled", True):
        status.update(label="Web 検索（フリードメイン）...", state="running")
        logger.info("free web search")
        hits = web_retriever.search(refined_query, k=10)
        logger.info("\n".join(["- " + result.title + " (" + str(result.url) + ")" for result in hits]))
        web_search_results.extend(hits)
        content = "\n\n".join(
            [
                "Web 検索結果（フリードメイン）:",
                "\n".join(["- " + result.title + " (" + str(result.url) + ")" for result in hits]),
            ]
        )
        with status:
            with st.chat_message("assistant", avatar=logo):
                st.write(content)
        ph.empty()
        with ph.container():
            with st.chat_message("assistant", avatar=logo):
                st.write(content)
        messages.append({"role": "assistant", "content": content})

    # web search on specified domains
    if len(get_config("web_search_domains")) > 0:
        status.update(label="Web 検索（ドメイン指定）...", state="running")
        domains = get_config("web_search_domains")
        logger.info("web search with domains: " + ", ".join(domains))
        hits = web_retriever.search(refined_query, k=10, domains=domains)
        web_search_results.extend(hits)
        content = "\n\n".join(
            [
                "Web 検索結果（ドメイン指定）:",
                "\n".join(["- " + result.title + " (" + str(result.url) + ")" for result in hits]),
            ]
        )
        with status:
            with st.chat_message("assistant", avatar=logo):
                st.write(content)
        ph.empty()
        with ph.container():
            with st.chat_message("assistant", avatar=logo):
                st.write(content)
        messages.append({"role": "assistant", "content": content})

    # query expansion
    status.update(label="クエリー展開...", state="running")
    query_expander = QueryExpander(lm=lm)
    web_search_result_texts = []
    for i, result in enumerate(web_search_results, start=1):
        web_search_result_texts.append(f"[{i}] {result.title}\n{result.snippet}")
    web_search_results_text = "\n\n".join(web_search_result_texts)
    query_expander_result = query_expander(query=query, web_search_results=web_search_results_text)
    logger.info(
        " ".join(
            [
                "[query expansion]",
                f"(in) query: {len(query)} chars",
                f"(in) web_search_results: {len(web_search_results_text)} chars",
                f"(out) topics: {sum([len(topic) for topic in query_expander_result.topics])} chars",
            ]
        )
    )
    expanded_queries = [query] + query_expander_result.topics
    content = "\n\n".join(
        [
            "展開されたクエリー:",
            "\n\n".join([f"[{i}] {topic}" for i, topic in enumerate(query_expander_result.topics, start=1)]),
        ]
    )
    with status:
        with st.chat_message("assistant", avatar=logo):
            st.write(content)
    ph.empty()
    with ph.container():
        with st.chat_message("assistant", avatar=logo):
            st.write(content)
    messages.append({"role": "assistant", "content": content})

    # article search
    status.update(label="法令検索...", state="running")
    article_search_results = []
    query_vectors = text_encoder.get_query_embeddings(expanded_queries)
    for expanded_query, query_vector in zip(expanded_queries, query_vectors):
        logger.info("vector search: " + expanded_query)
        hits = vector_search_article_retriever.search(query_vector, k=10)
        article_search_results.extend(hits)
        logger.info("\n".join(["- " + result.title + " (" + str(result.url) + ")" for result in hits]))
        content = "\n\n".join(
            [
                "法令検索結果:",
                expanded_query,
                "\n".join(["- " + result.title + " (" + str(result.url) + ")" for result in hits]),
            ]
        )
        with status:
            with st.chat_message("assistant", avatar=logo):
                st.write(content)
        ph.empty()
        with ph.container():
            with st.chat_message("assistant", avatar=logo):
                st.write(content)
        messages.append({"role": "assistant", "content": content})
    # fusion by bi-encoder
    status.update(label="収集したナレッジのリランキング...", state="running")
    url_to_articles = {result.url: result for result in article_search_results}
    unique_article_search_results = list(url_to_articles.values())
    url_to_web_pages = {
        result.url: result for result in web_search_results if result.url not in url_to_articles
    }  # 法令もURLをもつので除外
    unique_web_search_results = list(url_to_web_pages.values())
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
    content = "\n\n".join(
        [
            f"リランキングされたナレッジ（全 {len(search_results)} 件）:",
            *[f"[{i}] {result.title}" for i, result in enumerate(search_results, start=1)],
        ]
    )
    with status:
        with st.chat_message("assistant", avatar=logo):
            st.write(content)
    ph.empty()
    with ph.container():
        with st.chat_message("assistant", avatar=logo):
            st.write(content)
    messages.append({"role": "assistant", "content": content})

    # knowledge selection
    status.update(label="レポート作成に参照するナレッジの抽出...", state="running")
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
    logger.info(f"effective knowledges: {len(seen)}")

    # create outline
    status.update(label="アウトラインの生成...", state="running")
    outline_creater = OutlineCreater(lm=lm)
    outline_creater_result = outline_creater(query=query, topics=query_expander_result.topics, references=references)
    content = "\n\n".join(
        [
            "生成されたアウトライン:",
            f"```{outline_creater_result.outline.to_text()}```",
        ]
    )
    with status:
        with st.chat_message("assistant", avatar=logo):
            st.write(content)
    ph.empty()
    with ph.container():
        with st.chat_message("assistant", avatar=logo):
            st.write(content)
    messages.append({"role": "assistant", "content": content})
    logger.info(
        " ".join(
            [
                "[outline_creater]",
                f"(in) query: {len(query)} chars",
                f"(in) topics: {sum([len(topic) for topic in query_expander_result.topics])} chars",
                f"(in) references: {sum([len(ref) for ref in references])} chars",
                f"(out) outline: {len(outline_creater_result.outline.to_text())} chars",
            ]
        )
    )
    # complete
    status.update(label="Reasoning Details", state="complete", expanded=False)
    ph.empty()

    id2reference = {i: search_result for i, search_result in enumerate(search_results, start=1)}

    # show
    outline = outline_creater_result.outline
    st.write("# " + outline.title)  # title
    lead_box = st.empty()  # lead
    mindmap_box = st.empty()  # mindmap
    section_boxes = [st.empty() for _ in outline.section_outlines]  # section
    conclusion_header_box = st.empty()
    conclusion_box = st.empty()  # conclusion
    with mindmap_box.container():
        mindmap = outline.to_text()
        logger.info("mindmap :\n" + mindmap)
        draw_mindmap(mindmap)
    stream_section_writers = [StreamSectionWriter(lm=lm) for _ in outline.section_outlines]
    tasks = []
    for section_box, section_outline, stream_section_writer in zip(
        section_boxes, outline.section_outlines, stream_section_writers
    ):
        ref_ids = set()
        for subsection_outline in section_outline.subsection_outlines:
            ref_ids.update(subsection_outline.reference_ids)
        ref_ids = sorted(ref_ids)
        refs = []
        for ref_id in ref_ids:
            if ref_id not in id2reference:
                logger.warning(f"invalid ref_id: {ref_id}")
                continue
            ref = id2reference[ref_id]
            refs.append(f"[{ref_id}] " + ref.title + "\n" + ref.snippet)
        refs = "\n\n".join(refs)
        tasks.append(write_section(section_box, stream_section_writer, query, refs, section_outline.to_text()))

    async def finish_section_writing():
        await asyncio.gather(*tasks)

    asyncio.run(finish_section_writing())
    conclusion_header_box.write("## 結論")
    report_draft = "\n".join(["# " + outline.title] + [writer.section_content for writer in stream_section_writers])
    stream_conclusion_writer = StreamConclusionWriter(lm)
    conclusion_box.write_stream(stream_conclusion_writer(query, report_draft))
    conclusion = stream_conclusion_writer.conclusion

    stream_lead_writer = StreamLeadWriter(lm=lm)
    report_draft = "\n".join(
        ["# " + outline.title]
        + [writer.section_content for writer in stream_section_writers]
        + ["## 結論", conclusion]
    )
    lead_box.write_stream(stream_lead_writer(query=query, title=outline.title, draft=report_draft))
    lead = stream_lead_writer.lead

    report_content = "\n".join(
        ["# " + outline.title, lead]
        + [writer.section_content for writer in stream_section_writers]
        + ["## 結論", conclusion]
    )

    st.write("## References")
    for i, result in enumerate(search_results, start=1):
        html = get_hiddenbox_ref_html(i, result)
        st.markdown(html, unsafe_allow_html=True)
        st.write("")

    # save
    title = outline.title
    now = datetime.datetime.now()
    if not title:
        jst = now.astimezone(ZoneInfo("Asia/Tokyo"))
        title = jst.strftime("%Y-%m-%d %H:%M:%S.%f")
    references = []
    new_report = Report(
        id=str(uuid4()),
        timestamp=now.timestamp(),
        query=query,
        topics=query_expander_result.topics,
        title=title,
        outline=outline.to_text(),
        report_content=report_content,
        mindmap=mindmap,
        references=search_results,  # reference = search result for now
        search_results=search_results,
        messages=messages,
    )
    new_report.save(get_config("history_dir"))
    REPORT_PAGES[new_report.id] = st.Page(
        create_report_page(new_report), title=new_report.title, url_path=new_report.id
    )
    logger.info("saved report")

    st.switch_page(page=REPORT_PAGES[new_report.id])
