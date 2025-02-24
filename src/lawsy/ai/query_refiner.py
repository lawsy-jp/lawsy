import dspy


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
    refined_query = dspy.OutputField(desc="あなたの作成したクエリー", format=str)


class QueryRefiner(dspy.Module):
    def __init__(self, lm):
        self.refine_query = dspy.Predict(RefineQuery)
        self.lm = lm

    def forward(self, query: str) -> dspy.Prediction:
        with dspy.settings.context(lm=self.lm):
            refine_query_result = self.refine_query(query=query)
        return dspy.Prediction(refined_query=refine_query_result.refined_query)
