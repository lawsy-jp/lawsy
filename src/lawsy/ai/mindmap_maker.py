import dspy


class MindMap(dspy.Signature):
    """あなたは与えられた文章から要点を読み取りわかりやすいマインドマップを作製することで定評のある信頼できるデザイナーです。
    あるクエリーに対して得られたレポートから、それをもとに下記のMarkdownの例に基づいたマインドマップを書いてください。
    マインドマップはレポートの主たる内容や項目を網羅しており、表現は端的でわかりやすくしてください。
        # A
        ## AA
        ### AAA
        #### AAAA
        ##### AAAAA
        # B
        ## BB
        ## BC
        ### BCA
        # C
        ## CC
        ## CD
        ### CDC
        ### CDD
        ## CE
        ### CEC
        ### CED
    """  # noqa: E501

    report = dspy.InputField(desc="記載されたレポート", format=str)
    mindmap = dspy.OutputField(desc="レポートを基に作成されたマインドマップ", format=str)


class MindMapMaker(dspy.Module):
    def __init__(self, lm) -> None:
        self.lm = lm
        self.make_mindmap = dspy.Predict(MindMap)

    def forward(self, report: str) -> dspy.Prediction:
        with dspy.settings.context(lm=self.lm):
            mindmap_result = self.make_mindmap(report=report)
        return mindmap_result
