import dspy


class NewsAPIQuery(dspy.Signature):
    """あなたは与えられた文章検索クエリや出力予定のレポートアウトラインから、関連するニュースをGoogle検索するためのクエリ作成で定評のある堅実な検索クエリ生成者
    です。

    与えられた文章から、Google検索用のクエリを作成してください。その際次の事項を厳守してください.
    1.様々な観点からのニュース検索のため、異なる観点からキーワードを3つだけ選び、クエリへ入れてください。
    2.4つ以上のクエリを入れると該当するニュースが一つもなくなってしまうことがあるため、絶対にクエリを3つだけとしてください。
    クエリの例を下記に示します。
    ---例---
    法令 ハッカソン
    SMR 建設
    生成AI 法律
    """

    documents = dspy.InputField(desc="与えられた文章", format=str)
    newsquery = dspy.OutputField(desc="文章を基に作成されたNewsAPIへのクエリ", format=str)


class NewsQueryMaker(dspy.Module):
    def __init__(self, lm) -> None:
        self.lm = lm
        self.make_newsapi_query = dspy.Predict(NewsAPIQuery)

    def forward(self, documents: str) -> dspy.Prediction:
        with dspy.settings.context(lm=self.lm):
            newsapi_query = self.make_newsapi_query(documents=documents)
        return newsapi_query
