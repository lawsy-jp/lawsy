import numpy as np
import numpy.typing as npt


class OpenAITextEmbedding:
    def __init__(
        self,
        model_name: str = "text-embedding-3-small",
        dim: int | None = None,
    ) -> None:
        from openai import OpenAI

        assert model_name in ("text-embedding-3-large", "text-embedding-3-small")
        assert model_name != "text-embedding-3-large" or dim is None or 0 < dim <= 3072
        assert model_name != "text-embedding-3-small" or dim is None or 0 < dim <= 1536
        self.model_name = model_name
        if dim is None:
            if model_name == "text-embedding-3-large":
                dim = 3072
            elif model_name == "text-embedding-3-small":
                dim = 1536
        assert dim is not None
        self.dim = dim
        self.client = OpenAI()

    def get_dimension(self) -> int:
        return self.dim

    def get_name(self) -> str:
        return f"OpenAI-{self.model_name}"

    def get_detailed_instruct(self, task_description: str, query: str) -> str:
        return f"Instruct: {task_description}\nQuery: {query}"

    def _get_embeddings(self, texts: list[str]) -> npt.NDArray[np.float64]:
        texts = [text.replace("\n", " ")[:6000] for text in texts]
        response = self.client.embeddings.create(input=texts, model=self.model_name)
        result = np.asarray([d.embedding for d in response.data])
        return result[:, : self.dim]

    def get_query_embeddings(
        self, queries: list[str], task_description: str = "Retrieve passages that answer the following query"
    ) -> npt.NDArray[np.float64]:
        queries = [self.get_detailed_instruct(task_description, query) for query in queries]
        return self._get_embeddings(queries)

    def get_document_embeddings(self, documents: list[str]) -> npt.NDArray[np.float64]:
        return self._get_embeddings(documents)
