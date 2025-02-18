import asyncio
import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import dotenv
import numpy as np
import streamlit as st
from loguru import logger
from streamlit_markmap import markmap

from lawsy.ai.outline_creater import OutlineCreater
from lawsy.ai.query_expander import QueryExpander
from lawsy.ai.report_writer import StreamConclusionWriter, StreamLeadWriter, StreamSectionWriter
from lawsy.app.config import get_config
from lawsy.app.styles.decorate_html import (
    embed_tooltips,
    get_hiddenbox_ref_html,
    get_reference_tooltip_html,
)
from lawsy.app.utils.cloud_logging import gcp_logger
from lawsy.app.utils.cookie import get_user_id
from lawsy.app.utils.history import Report
from lawsy.app.utils.lm import load_lm
from lawsy.app.utils.preload import (
    load_tavily_search_web_retriever,
    load_text_encoder,
    load_vector_search_article_retriever,
)

PAGES = {}


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


def draw_mindmap(mindmap: str):
    return markmap(mindmap, height=400)


def create_lawsy_page(report: Report | None = None):
    def page_func():
        dotenv.load_dotenv()
        css = (Path(__file__).parent / "styles" / "style.css").read_text()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

        if report is not None:
            logger.info("reproduce previous report")
            with st.status("Reasoning Details"):
                st.write("query:")
                st.write(report.query)
                st.write("generated topics:")
                for i, topic in enumerate(report.topics, start=1):
                    st.write(f"[{i}] {topic}")
                st.write(f"found {len(report.references)} sources:")
                for i, result in enumerate(report.references, start=1):
                    st.write(f"[{i}] " + result.title)
                st.write("generated outline:")
                st.code(report.outline)
            tooltips = get_reference_tooltip_html(report.references)
            # show
            pos = report.report_content.find("## ")
            assert pos >= 0
            title_and_lead = report.report_content[:pos]
            rest = report.report_content[pos:]
            st.write(title_and_lead)
            draw_mindmap(report.mindmap)
            rest = embed_tooltips(rest, tooltips)
            st.write(rest, unsafe_allow_html=True)
            st.markdown("## References")
            for i, result in enumerate(report.references, start=1):
                html = get_hiddenbox_ref_html(i, result)
                st.markdown(html, unsafe_allow_html=True)
            return

        assert report is None
        user_id = get_user_id()
        logger.info(f"user_id: {user_id}")
        text_encoder = load_text_encoder()
        vector_search_article_retriever = load_vector_search_article_retriever()
        tavily_search_web_retriever = load_tavily_search_web_retriever()

        gpt_4o = load_lm("openai/gpt-4o")
        # gpt_4o_mini = load_lm("openai/gpt-4o-mini")
        # gemini_pro = "vertex_ai/gemini-2.0-exp-02-05"
        # gemini_flash = "vertex_ai/gemini-2.0-flash-001"
        # gemini_flash_lite = "vertex_ai/gemini-2.0-flash-lite-preview-02-05"

        st.title(" " if report is None else report.title)
        query = st.text_area(
            "Your Research Topic", key="research_page_query_text_input", value="" if report is None else report.query
        )
        if query is not None:
            query = query.strip()
        clicked = st.button("Research", key="research_page_research_button")

        if query and clicked:
            logger.info("query: " + query)
            gcp_logger.log_struct({"event": "start-research", "user_id": user_id, "query": query}, severity="INFO")
            with st.status("processing", expanded=True) as status:
                # web search
                status.update(label="web search...")
                web_search_results = []
                if get_config("free_web_search_enabled", True):
                    logger.info("free web search")
                    hits = tavily_search_web_retriever.search(query, k=10)
                    logger.info("\n".join(["- " + result.title + " (" + str(result.url) + ")" for result in hits]))
                    web_search_results.extend(hits)
                if len(get_config("web_search_domains")) > 0:
                    domains = get_config("web_search_domains")
                    logger.info("web search with domains: " + ", ".join(domains))
                    hits = tavily_search_web_retriever.search(query, k=10, domains=domains)
                    logger.info("\n".join(["- " + result.title + " (" + str(result.url) + ")" for result in hits]))
                    web_search_results.extend(hits)

                # query expansion
                status.update(label="query expansion...")
                query_expander = QueryExpander(lm=gpt_4o)
                web_search_result_texts = []
                for i, result in enumerate(web_search_results, start=1):
                    web_search_result_texts.append(f"[{i}] {result.title}\n{result.snippet}")
                web_search_results_text = "\n\n".join(web_search_result_texts)
                query_expander_result = query_expander(query=query, web_search_results=web_search_results_text)
                expanded_queries = [query] + query_expander_result.topics
                st.write("generated topics:")
                for i, topic in enumerate(query_expander_result.topics, start=1):
                    st.write(f"[{i}] {topic}")

                # article search
                article_search_results = []
                status.update(label="legal article search...")
                query_vectors = text_encoder.get_query_embeddings(expanded_queries)
                for expanded_query, query_vector in zip(expanded_queries, query_vectors):
                    logger.info("vector search: " + expanded_query)
                    hits = vector_search_article_retriever.search(query_vector, k=10)
                    article_search_results.extend(hits)
                    logger.info("\n".join(["- " + result.title + " (" + str(result.url) + ")" for result in hits]))

                # fusion by bi-encoder
                status.update(label="fuse search results...")
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
                st.write(f"found {len(search_results)} sources:")
                for i, result in enumerate(search_results, start=1):
                    st.write(f"[{i}] " + result.title)

                # prepare report
                status.update(label="writing report...")
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
                status.update(label="creating outline...")
                outline_creater = OutlineCreater(lm=gpt_4o)
                outline_creater_result = outline_creater(
                    query=query, topics=query_expander_result.topics, references=references
                )
                st.write("generated outline:")
                st.code(outline_creater_result.outline.to_text())

                # complete
                status.update(label="complete", state="complete", expanded=False)

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
            stream_section_writers = [StreamSectionWriter(lm=gpt_4o) for _ in outline.section_outlines]
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
                    ref = id2reference[ref_id]
                    refs.append(f"[{ref_id}] " + ref.title + "\n" + ref.snippet)
                refs = "\n\n".join(refs)
                tasks.append(write_section(section_box, stream_section_writer, query, refs, section_outline.to_text()))

            async def finish_section_writing():
                await asyncio.gather(*tasks)

            asyncio.run(finish_section_writing())
            conclusion_header_box.write("## 結論")
            report_draft = "\n".join(
                ["# " + outline.title] + [writer.section_content for writer in stream_section_writers]
            )
            stream_conclusion_writer = StreamConclusionWriter(gpt_4o)
            conclusion_box.write_stream(stream_conclusion_writer(query, report_draft))
            conclusion = stream_conclusion_writer.conclusion

            stream_lead_writer = StreamLeadWriter(lm=gpt_4o)
            report_draft = "\n".join(
                ["# " + outline.title, "[リード文]"]
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
            )
            new_report.save(user_id=user_id)
            PAGES[new_report.id] = st.Page(
                create_lawsy_page(new_report), title=new_report.title, url_path=new_report.id
            )
            logger.info("saved report")
            gcp_logger.log_struct(
                {
                    "event": "finish-research",
                    "user_id": user_id,
                    "report": {"id": new_report.id, "title": new_report.title},
                },
                severity="INFO",
            )

            st.switch_page(page=PAGES[new_report.id])

    return page_func
