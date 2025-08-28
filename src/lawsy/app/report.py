from pathlib import Path

import dotenv
import streamlit as st

from lawsy.app.styles.decorate_html import (
    embed_tooltips,
    get_hiddenbox_ref_html,
    get_reference_tooltip_html,
)
from lawsy.app.utils.history import Report
from lawsy.app.utils.mindmap import draw_mindmap
from lawsy.utils.logging import logger

REPORT_PAGES = {}


def get_logo_path() -> Path:
    return Path(__file__).parent / "Lawsy_logo_circle.png"


def get_logotitle_path() -> Path:
    return Path(__file__).parent / "Lawsy_logo_title_long_trans.png"


def create_report_page(report: Report):
    def page_func():
        dotenv.load_dotenv()
        css = (Path(__file__).parent / "styles" / "style.css").read_text()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

        # title logo
        logo_col, _ = st.columns([1, 5])
        with logo_col:
            st.image(get_logotitle_path())

        logo = get_logo_path()
        logger.info("reproduce previous report")
        if st.session_state.config_reasoning_details_display_enabled and report.messages is not None:
            with st.expander("Reasoning Details"):
                for message in report.messages:
                    role = message["role"]
                    content = message["content"]
                    if role == "user":
                        with st.chat_message(role):
                            st.write(content)
                    else:
                        with st.chat_message(role, avatar=logo):
                            st.write(content)
        pos = report.report_content.find("## ")
        assert pos >= 0
        title_and_lead = report.report_content[:pos]
        rest = report.report_content[pos:]
        title, lead = title_and_lead.split("\n", 1)

        # 結論部分を分離
        conclusion_pos = rest.find("## 結論")
        if conclusion_pos >= 0:
            sections_content = rest[:conclusion_pos]
            conclusion_content = rest[conclusion_pos:]
        else:
            sections_content = rest
            conclusion_content = ""

        # title
        st.write(title)

        # 違反・問題サマリーを表示（research.pyからの遷移後も表示）
        logger.info(f"Report has violation_analysis: {hasattr(report, 'violation_analysis')}")
        if hasattr(report, "violation_analysis"):
            logger.info(f"violation_analysis content: {report.violation_analysis}")

        def get_severity_order(severity):
            """重要度の順序を返す（高→中→低）"""
            order_map = {"high": 0, "medium": 1, "low": 2}
            return order_map.get(severity, 3)  # 不明な重要度は最後

        def display_problem_with_severity(problem, index):
            """重要度に応じた問題の表示（該当法律も含む）"""
            severity = problem.get("severity", "medium")
            problem_text = problem.get("problem", "")
            evidence = problem.get("evidence", "")
            recommended_action = problem.get("recommended_action", "")
            applicable_laws = problem.get("applicable_laws", [])

            # 重要度に応じたアイコンと表示関数
            severity_config = {
                "high": {"icon": "🔴", "label": "高", "func": st.error},
                "medium": {"icon": "🟡", "label": "中", "func": st.warning},
                "low": {"icon": "🔵", "label": "低", "func": st.info},
            }

            config = severity_config.get(severity, severity_config["medium"])

            # すべての情報を1つのボックスにまとめて表示
            message_parts = [f"{config['icon']} **問題 {index} [重要度: {config['label']}]**", ""]
            message_parts.append(f"**問題内容:** {problem_text}")

            if evidence:
                message_parts.append(f"**該当箇所:** 「{evidence}」")

            # 該当法律の表示
            if applicable_laws:
                message_parts.append("**📖 該当法律:**")
                for law in applicable_laws:
                    law_keyword = law.get("keyword", "不明")
                    law_type = law.get("type", "")
                    law_info = f"• {law_keyword}"
                    if law_type:
                        law_info += f" ({law_type})"
                    message_parts.append(law_info)

                    if law.get("full_name"):
                        message_parts.append(f"  正式名称: {law['full_name']}")
                    if law.get("relevant_articles"):
                        message_parts.append(f"  関連条文: {law['relevant_articles']}")

            if recommended_action:
                message_parts.append(f"**推奨対応:** {recommended_action}")

            config["func"]("\n\n".join(message_parts))

        if hasattr(report, "violation_analysis") and report.violation_analysis:
            # compliance_statusに基づいて表示を変更
            compliance_status = report.violation_analysis.get("compliance_status", "non-compliant")
            message = report.violation_analysis.get("message", "")
            
            if compliance_status == "compliant":
                # 問題なしの場合
                with st.expander("**✅ 薬機法コンプライアンス判定結果**", expanded=True):
                    st.success(f"✅ **薬機法的な問題は検出されませんでした**")
                    if message:
                        st.info(f"**判定詳細:** {message}")
            else:
                # 問題ありの場合
                expander_title = "**⚠️ 具体的な問題・違反と該当法律**"
                if compliance_status == "needs-modification":
                    expander_title = "**🟡 修正推奨事項と該当法律**"
                elif compliance_status == "non-compliant":
                    expander_title = "**🔴 重要な違反・問題と該当法律**"
                    
                with st.expander(expander_title, expanded=True):
                    if message:
                        st.info(f"**全体判定:** {message}")
                        
                    if (
                        report.violation_analysis.get("specific_problems")
                        and len(report.violation_analysis["specific_problems"]) > 0
                    ):
                        status_icon = "🚨" if compliance_status == "non-compliant" else "⚠️"
                        st.markdown(f"**{status_icon} 検出された問題点と該当法律**")

                        # 重要度でソート（高→中→低）
                        sorted_problems = sorted(
                            report.violation_analysis["specific_problems"],
                            key=lambda x: get_severity_order(x.get("severity", "medium")),
                        )

                        for i, problem in enumerate(sorted_problems, 1):
                            display_problem_with_severity(problem, i)
                    else:
                        st.info("具体的な問題は検出されませんでした。")

        st.write(lead)

        # 結論をサマリーの下、マインドマップの上に表示
        if conclusion_content:
            st.write(conclusion_content)

        draw_mindmap(report.mindmap)

        # セクション内容を表示（結論を除いた部分）
        tooltips = get_reference_tooltip_html(report.references)
        sections_with_tooltips = embed_tooltips(sections_content, tooltips)
        st.write(sections_with_tooltips, unsafe_allow_html=True)
        st.markdown("## References")
        for i, result in enumerate(report.references, start=1):
            html = get_hiddenbox_ref_html(i, result)
            st.markdown(html, unsafe_allow_html=True)
        st.markdown(
            """
            <style>
            .custom-text-warning {
                color: grey !important;
                font-size: 12px !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        warning_text = (
            '<p class="custom-text-warning">'
            "※Lawsyの回答は必ずしも正しいとは限りません。重要な情報は確認するようにしてください。"
            "</p>"
        )
        st.markdown(warning_text, unsafe_allow_html=True)

        return

    return page_func
