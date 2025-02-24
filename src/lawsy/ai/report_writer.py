from typing import AsyncGenerator

import dspy

from lawsy.ai.utils.stream_writer import StreamLineWriter


class WriteLead(dspy.Signature):
    """あなたは日本の法令に精通し、分かりやすい解説を書くことに定評のある信頼できるライターです。
    下記のクエリーに関する調査をしており、レポートを作成しました。レポートタイトルの直後に表示する簡潔なリード文を生成してください。
    リード文とは、レポート全体のabstractとなる、レポート全体の論旨の展開や主要トピックを含めた簡潔な文章です。

    リード文の生成にあたって次のルールを厳守すること
    - リード文では、レポート全体の文脈やレポートで扱われている主要なトピックに対する簡潔な概要を提示し、それ単独でも読める内容にすること
    - リード文の文字数は140〜280文字程度とすること
    - リード文の文面のみ生成すること。
    """  # noqa: E501

    query = dspy.InputField(desc="クエリー", format=str)
    title = dspy.InputField(desc="レポートのタイトル", format=str)
    draft = dspy.InputField(desc="レポート内容", format=str)
    lead = dspy.OutputField(desc="リード文の文面", format=str)


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
    references = dspy.InputField(desc="収集された情報源と引用番号", format=str)
    section_outline = dspy.InputField(desc="セクションのアウトライン", format=str)
    section = dspy.OutputField(desc="生成されたセクション", format=str)


class WriteConclusion(dspy.Signature):
    """あなたは日本の法令に精通し、分かりやすい解説を書くことに定評のある信頼できるライターです。
    レポートのドラフトを踏まえて、レポート全体の要約を本文とはできるだけ異なる表現で記載しつつ、今後の方向性や対応策を含んだ結論部の中身を生成します。
    最低でも400字以上、可能なら600字以上記載してください。
    結論の文章部分のみ生成し、"## 結論" のようなヘッダ入れないでください。
    """

    query = dspy.InputField(desc="クエリー", format=str)
    report_draft = dspy.InputField(desc="レポートのドラフト", format=str)
    conclusion = dspy.OutputField(desc="生成された結論", format=str)


class StreamLeadWriter(StreamLineWriter):
    def __init__(self, lm) -> None:
        super().__init__(lm=lm, signature_cls=WriteLead)

    async def __call__(self, query: str, title: str, draft: str) -> AsyncGenerator[str, None]:
        async for chunk in self.generate({"query": query, "title": title, "draft": draft}):
            yield chunk
        lead = self.get_generated_text()
        self.lead = lead


class StreamSectionWriter(StreamLineWriter):
    def __init__(self, lm) -> None:
        super().__init__(lm=lm, signature_cls=WriteSection)

    async def __call__(self, query: str, references: str, section_outline: str) -> AsyncGenerator[str, None]:
        async for chunk in self.generate(
            {"query": query, "references": references, "section_outline": section_outline}
        ):
            yield chunk
        section_content = self.get_generated_text()
        self.section_content = section_content


class StreamConclusionWriter(StreamLineWriter):
    def __init__(self, lm) -> None:
        super().__init__(lm=lm, signature_cls=WriteConclusion)

    async def __call__(self, query: str, report_draft: str) -> AsyncGenerator[str, None]:
        async for chunk in self.generate({"query": query, "report_draft": report_draft}):
            yield chunk
        conclusion = self.get_generated_text()
        self.conclusion = conclusion
