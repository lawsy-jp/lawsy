import re

import dspy
from pydantic import BaseModel

from lawsy.utils.logging import logger


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
    """  # noqa: E501

    query = dspy.InputField(desc="クエリー", format=str)
    references = dspy.InputField(desc="収集された情報源と引用番号", format=str)
    outline = dspy.OutputField(desc="レポートのアウトライン", format=str)


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
    """  # noqa: E501

    outline = dspy.InputField(desc="入力アウトライン", foramt=str)
    fixed_outline = dspy.OutputField(desc="修正済みアウトライン", format=str)


class SubsectionOutline(BaseModel):
    title: str
    reference_ids: list[int]

    def to_text(self) -> str:
        return "\n".join(
            ["### " + self.title, "".join([f"[{reference_id}]" for reference_id in self.reference_ids])]
        ).strip()


class SectionOutline(BaseModel):
    title: str
    subsection_outlines: list[SubsectionOutline]

    def to_text(self) -> str:
        return "\n".join(
            ["## " + self.title] + [subsection_outline.to_text() for subsection_outline in self.subsection_outlines]
        )


class Outline(BaseModel):
    title: str
    section_outlines: list[SectionOutline]

    def to_text(self) -> str:
        return "\n".join(
            ["# " + self.title] + [section_outline.to_text() for section_outline in self.section_outlines]
        )


class OutlineCreater(dspy.Module):
    def __init__(self, lm) -> None:
        self.lm = lm
        self.gen_outline = dspy.Predict(CreateOutline)
        self.fix_outline = dspy.Predict(FixOutline)

    @staticmethod
    def __parse_outline(outline) -> Outline:
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
                assert report_title is None
                report_title = line[2:].strip()
                continue
            elif line.startswith("## "):
                if section_title is not None:
                    assert len(subsection_outlines) > 0
                    section_outlines.append(
                        SectionOutline(title=section_title, subsection_outlines=subsection_outlines)
                    )  # noqa: E501
                section_title = line[3:].strip()
                subsection_outlines = []
                continue
            elif line.startswith("### "):
                if subsection_title is not None:
                    subsection_outlines.append(SubsectionOutline(title=subsection_title, reference_ids=reference_ids))
                subsection_title = line[4:].strip()
                reference_ids = []
                continue
            else:
                assert subsection_title is not None
                assert re.match(r"\[\d+\]+", line)
                reference_ids = [int(matched) for matched in re.findall(r"\[(\d+)\]", line)]
                subsection_outlines.append(SubsectionOutline(title=subsection_title, reference_ids=reference_ids))
                subsection_title = None
                reference_ids = []
                continue
        if subsection_title:
            assert section_title is not None
            subsection_outlines.append(SubsectionOutline(title=subsection_title, reference_ids=reference_ids))
            section_outlines.append(SectionOutline(title=section_title, subsection_outlines=subsection_outlines))
        assert report_title is not None
        return Outline(title=report_title, section_outlines=section_outlines)

    def forward(self, query: str, topics: list, references: list[str]) -> dspy.Prediction:
        topics_text = "\n".join([f"- {topic}" for topic in topics])
        references_text = "\n\n".join(references)
        with dspy.settings.context(lm=self.lm):
            create_outline_result = self.gen_outline(
                query=query,
                topics=topics_text,
                references=references_text,
            )
            logger.info(f"created outline: \n{create_outline_result.outline}")
            fix_outline_result = self.fix_outline(outline=create_outline_result.outline)
            logger.info(f"fixed outline: \n{fix_outline_result.fixed_outline}")
        parsed_outline = self.__parse_outline(fix_outline_result.fixed_outline)
        return dspy.Prediction(outline=parsed_outline)
