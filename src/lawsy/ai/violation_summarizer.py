import os
from typing import Dict

import dspy

from lawsy.utils.logging import logger


def create_violation_summary_signature(max_items: int = 10):
    """動的にViolationSummaryシグネチャを作成"""

    class ViolationSummary(dspy.Signature):
        __doc__ = f"""あなたは日本の薬機法令に精通した専門家です。
        ユーザーの質問内容とレポート内容を分析し、以下の2点を簡潔にまとめてください：

        1. 何が問題なのか（具体的な問題点・違反の可能性）
        2. 各問題に対してどの法律に違反しているのか（該当する具体的な法律・省令）

        【極めて重要な指示】
        - **evidenceフィールドには、ユーザーの質問文から問題となる具体的な記述を必ず引用**
        - レポートからの引用は絶対に使用しない
        - ユーザーが「〜したい」「〜できますか」「〜について」と書いた部分をそのまま引用
        - 引用は正確に、省略せずに、原文のまま記載すること

        【重要度判定基準】
        **高（high）**: 表現修正では回避不可能な構造的・根本的な問題
        - 未承認医薬品・医療機器の販売行為そのもの
        - 無許可での製造業・製造販売業の実施
        - 治験における重大なプロトコル違反・データ改ざん
        - 承認されていない効能効果の標榜（医薬品的効能効果）
        - 安全性情報の意図的隠蔽・報告義務違反

        **中（medium）**: 表現修正や手続きで回避可能だが要注意な問題
        - 誇大広告表現（修正により適正化可能）
        - 承認事項軽微変更の未届（手続きにより解決可能）
        - 不適切な比較広告・最大級表現（表現変更で対応可能）
        - 必要な表示事項の記載不備（追記により解決可能）
        - ガイドライン逸脱（遵守により改善可能）

        **低（low）**: 予防的・推奨レベルの改善点
        - 業界ベストプラクティスからの逸脱
        - より適切な表現への変更提案
        - 予防的観点からの記載見直し
        - 関連研修・体制整備の推奨

        【重要な制限事項】
        - **薬機法関連の法律・省令のみを対象とすること**
        - 景表法、独占禁止法、個人情報保護法などの薬機法以外の法律は除外
        - 薬機法と併記されていても、薬機法以外の法律単独での違反は取り上げない

        【対象とする薬機法関連法令】
        - 薬機法（医薬品、医療機器等の品質、有効性及び安全性の確保等に関する法律）
        - GCP省令（医薬品の臨床試験の実施の基準に関する省令）
        - GMP省令（医薬品及び医薬部外品の製造管理及び品質管理の基準に関する省令）
        - GPSP省令（医薬品の製造販売後の調査及び試験の実施の基準に関する省令）
        - GVP省令（医薬品の製造販売後安全管理の基準に関する省令）
        - QMS省令（医療機器及び体外診断用医薬品の製造管理及び品質管理の基準に関する省令）
        - GQP省令（医薬品、医薬部外品、化粧品及び再生医療等製品の品質管理の基準に関する省令）
        - その他の薬機関連省令・通知

        【分析のポイント】
        - ユーザーの質問文を分析し、薬機法的に問題となりうる行為・状況を特定
        - 問題となる箇所は必ずユーザーの質問文から原文のまま引用
        - 該当する法律はレポートの内容を参考に特定
        - 問題点は{max_items}個まで、各問題に対して該当法律を関連付け
        - 各問題について重要度を適切に判定
        - 各問題に対して具体的で実行可能な対応方法を提案

        【推奨対応方法の指針】
        **高重要度の問題**: 構造的問題のため根本的な変更が必要
        - 「当該行為は実施不可能です。〜の許可・承認取得が必要」
        - 「薬機法に詳しい専門家への緊急相談が必要」
        - 「事業計画の根本的見直しが必要」
        - 「直ちに当該活動を中止し、適法な代替手段を検討」

        **中重要度の問題**: 表現修正や手続きで解決可能
        - 「〜の表現を『〜』に修正することで適法化可能」
        - 「〜の届出・申請手続きを行えば実施可能」
        - 「表示内容を薬機法ガイドラインに沿って修正」
        - 「専門家による表現チェックを受けて修正」

        **低重要度の問題**: より適切な対応への改善提案
        - 「より適切な表現として『〜』を推奨」
        - 「業界ベストプラクティスとして〜の実施を推奨」
        - 「予防的観点から〜の見直しを検討」

        【引用の例】
        ユーザーの質問: 「未承認の新薬をインターネットで販売したいのですが可能ですか」
        正しいevidence: 「未承認の新薬をインターネットで販売したい」
        間違ったevidence: 「薬機法第68条により未承認医薬品の広告は禁止」（これはレポートからの引用なのでNG）

        【出力形式】
        JSON形式で以下の構造を返してください：
        {{
            "specific_problems": [
                {{
                    "problem": "問題の内容（簡潔に）",
                    "evidence": "ユーザーの質問文から問題となる箇所を正確に引用（必須）",
                    "severity": "重要度（high/medium/low）",
                    "recommended_action": "推奨する対応方法（具体的で実行可能な内容）",
                    "applicable_laws": [
                        {{
                            "keyword": "法律の略称（例：薬機法、GCP省令）",
                            "full_name": "法律の正式名称",
                            "type": "分類（基本法、治験関連、製造関連、安全管理関連など）",
                            "relevant_articles": "関連する条文番号（あれば）"
                        }}
                    ]
                }}
            ]
        }}
        """

        query: str = dspy.InputField(desc="ユーザーの質問内容")
        report_content: str = dspy.InputField(desc="生成されたレポート全文")
        violation_summary: str = dspy.OutputField(desc="違反分析結果（JSON形式）")

    return ViolationSummary


class ViolationSummarizer(dspy.Module):
    def __init__(self, lm):
        super().__init__()
        self.lm = lm
        # 環境変数から最大表示数を取得（デフォルト: 10）
        self.max_items = int(os.getenv("LAWSY_VIOLATION_SUMMARY_MAX_ITEMS", "10"))
        logger.info(f"ViolationSummarizer max_items: {self.max_items}")
        # 動的にシグネチャを作成
        ViolationSummaryClass = create_violation_summary_signature(self.max_items)
        self.summarize = dspy.Predict(ViolationSummaryClass)

    def forward(self, query: str, report_content: str) -> Dict:
        """レポート内容から違反・問題点を分析"""
        import json

        with dspy.settings.context(lm=self.lm):
            result = self.summarize(query=query, report_content=report_content)

        try:
            # JSON文字列をパース
            violation_data = json.loads(result.violation_summary)

            # データの整形と検証
            specific_problems = violation_data.get("specific_problems", [])

            # 薬機法関連法令のキーワードリスト
            pharma_law_keywords = [
                "薬機法",
                "薬事法",
                "GCP",
                "GMP",
                "GPSP",
                "GVP",
                "QMS",
                "GQP",
                "医薬品",
                "医療機器",
                "体外診断",
                "再生医療",
                "製造販売",
                "臨床試験",
                "治験",
                "品質管理",
                "安全管理",
            ]

            # 薬機法関連のみをフィルタリングし、法律名のマッピング
            law_mappings = {
                "薬機法": "医薬品、医療機器等の品質、有効性及び安全性の確保等に関する法律",
                "薬事法": "医薬品、医療機器等の品質、有効性及び安全性の確保等に関する法律",
                "GCP省令": "医薬品の臨床試験の実施の基準に関する省令",
                "GMP省令": "医薬品及び医薬部外品の製造管理及び品質管理の基準に関する省令",
                "GPSP省令": "医薬品の製造販売後の調査及び試験の実施の基準に関する省令",
                "GVP省令": "医薬品の製造販売後安全管理の基準に関する省令",
                "QMS省令": "医療機器及び体外診断用医薬品の製造管理及び品質管理の基準に関する省令",
                "GQP省令": "医薬品、医薬部外品、化粧品及び再生医療等製品の品質管理の基準に関する省令",
            }

            # max_itemsで制限し、各問題の該当法律情報を補完
            filtered_problems = []
            for problem in specific_problems[: self.max_items]:
                # applicable_lawsが存在しない場合は空リストで初期化
                if "applicable_laws" not in problem:
                    problem["applicable_laws"] = []

                # 各法律の情報を補完
                filtered_laws = []
                for law in problem.get("applicable_laws", []):
                    keyword = law.get("keyword", "")
                    # キーワードが薬機法関連かチェック
                    if any(pharma_keyword in keyword for pharma_keyword in pharma_law_keywords):
                        # 正式名称が不足している場合の補完
                        if "full_name" not in law and keyword in law_mappings:
                            law["full_name"] = law_mappings[keyword]
                        filtered_laws.append(law)

                problem["applicable_laws"] = filtered_laws
                filtered_problems.append(problem)

            return {
                "specific_problems": filtered_problems,
                "has_violations": len(filtered_problems) > 0,
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse violation summary JSON: {e}")
            # フォールバック：空の結果を返す
            return {"specific_problems": [], "has_violations": False}
