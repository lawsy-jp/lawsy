import os
from typing import Dict

import dspy

from lawsy.utils.logging import logger


def create_violation_summary_signature(max_items: int = 10):
    """動的にViolationSummaryシグネチャを作成"""

    class ViolationSummary(dspy.Signature):
        __doc__ = f"""あなたは日本の薬機法令に精通した専門家です。
        
        【最初に確認すること】
        1. ユーザーの質問が薬機法的観点から問題ないか判断
        2. 以下の場合は「問題なし」と判定：
           - 一般的な法令の質問や情報収集（「〜について教えて」など）
           - 既に適法な表現を使用している広告文案の確認
           - 純粋な学習目的の質問
           - 既に必要な許可・承認を取得済みと明記されている案件
           - 薬機法上問題のない商品・サービスに関する質問

        【判定フロー】
        1. 明確な薬機法違反があるか？
           → YES: 高・中重要度で出力
           → NO: 次へ
        2. 表現修正や手続きで解決可能な問題があるか？
           → YES: 中重要度で出力
           → NO: 次へ
        3. いずれも該当しない場合：
           → 「問題なし」と判定（compliance_status = "compliant"）

        【問題なしの場合の出力例】
        {{
            "specific_problems": [],
            "compliance_status": "compliant",
            "message": "薬機法的な問題は検出されませんでした。提示された内容は適法です。"
        }}

        【極めて重要な指示】
        - **evidenceフィールドには、ユーザーの質問文から問題となる具体的な記述を必ず引用**
        - レポートからの引用は絶対に使用しない
        - ユーザーが「〜したい」「〜できますか」「〜について」と書いた部分をそのまま引用
        - 引用は正確に、省略せずに、原文のまま記載すること

        【重要度判定基準】
        **高（high）**: 法的に実施不可能な構造的問題
        - 未承認医薬品・医療機器の販売行為そのもの
        - 無許可での製造業・製造販売業の実施
        - 治験における重大なプロトコル違反・データ改ざん
        - 承認されていない効能効果の標榜（医薬品的効能効果）
        - 安全性情報の意図的隠蔽・報告義務違反

        **中（medium）**: 修正・手続きで解決可能な問題
        - 誇大広告表現（具体的な修正案で適正化可能）
        - 承認事項軽微変更の未届（手続きにより解決可能）
        - 不適切な比較広告・最大級表現（表現変更で対応可能）
        - 必要な表示事項の記載不備（追記により解決可能）

        【推奨対応方法の指針】
        **高重要度の問題**: 法的に実施不可、許可・承認が必要
        - 「医薬品製造販売業許可（薬機法第12条）の取得が必須。申請先：都道府県薬務課」
        - 「治験届（薬機法第80条の2）をPMDAに提出後に実施可能」
        - 「当該行為は薬機法第○条により実施不可能。代替方法として△△を検討」

        **中重要度の問題**: 具体的な修正で対応可能
        - 「『風邪が治る』→『健康維持をサポート』に変更（医薬品的効能効果の標榜禁止）」
        - 「使用前後の比較写真を削除（薬機法第66条：誇大広告の禁止）」
        - 「『最高の効果』→『当社比較において』を追加（根拠の明示）」
        - 「『必ず効く』→『〇〇をサポートします』に変更」

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

        【出力形式】
        JSON形式で以下の構造を返してください：
        {{
            "specific_problems": [
                {{
                    "problem": "問題の内容（簡潔に）",
                    "evidence": "ユーザーの質問文から問題となる箇所を正確に引用（必須）",
                    "severity": "重要度（high/medium）",
                    "recommended_action": "具体的で実行可能な対応方法",
                    "applicable_laws": [
                        {{
                            "keyword": "法律の略称（例：薬機法、GCP省令）",
                            "full_name": "法律の正式名称",
                            "type": "分類（基本法、治験関連、製造関連、安全管理関連など）",
                            "relevant_articles": "関連する条文番号（あれば）"
                        }}
                    ]
                }}
            ],
            "compliance_status": "判定結果（compliant/non-compliant/needs-modification）",
            "message": "全体的な判定メッセージ"
        }}
        
        compliance_status の値：
        - "compliant": 薬機法的に問題なし
        - "needs-modification": 修正で適法化可能
        - "non-compliant": 重大な違反、実施不可
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
            # レスポンスの型を確認して適切に処理
            violation_data = None
            
            if hasattr(result, 'violation_summary'):
                raw_result = result.violation_summary
            else:
                raw_result = result
                
            # 既に辞書型の場合
            if isinstance(raw_result, dict):
                violation_data = raw_result
                logger.info("Received dict response from LLM")
            # JSON文字列の場合
            elif isinstance(raw_result, str):
                try:
                    violation_data = json.loads(raw_result)
                    logger.info("Successfully parsed JSON string from LLM")
                except json.JSONDecodeError as json_err:
                    # JSON形式でない文字列の場合、空の結果を返す
                    logger.error(f"Invalid JSON string: {raw_result[:200]} - Error: {json_err}")
                    violation_data = {"specific_problems": []}
            else:
                # 予期しない型の場合
                logger.error(f"Unexpected type from LLM: {type(raw_result)}")
                violation_data = {"specific_problems": []}

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
            for problem in specific_problems[:self.max_items]:
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

            # compliance_statusとmessageを含める
            compliance_status = violation_data.get("compliance_status", "non-compliant" if len(filtered_problems) > 0 else "compliant")
            message = violation_data.get("message", "")

            return {
                "specific_problems": filtered_problems,
                "has_violations": len(filtered_problems) > 0,
                "compliance_status": compliance_status,
                "message": message,
            }

        except Exception as e:
            logger.error(f"Unexpected error in ViolationSummarizer: {e}")
            # フォールバック：空の結果を返す
            return {"specific_problems": [], "has_violations": False}
