import numpy as np
import numpy.typing as npt

from lawsy.utils.logging import logger


class ME5Instruct:
    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-large-instruct",
        device: str | None = None,
    ) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.model_name = model_name
        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        logger.info(f"device: {device}")
        self.device = device
        logger.info("loading tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        logger.info("loading model...")
        self.model = AutoModel.from_pretrained(self.model_name).to(self.device)
        logger.info("ME5Instruct is prepared")
        self.model.eval()

    def get_dimension(self) -> int:
        return 1024

    def get_name(self) -> str:
        return f"E5Instruct-{self.model_name}"

    def get_detailed_instruct(self, task_description: str, query: str) -> str:
        return f"Instruct: {task_description}\nQuery: {query}"

    def _get_embeddings(self, texts: list[str]) -> npt.NDArray[np.float64]:
        import torch

        def average_pool(last_hidden_states: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
            last_hidden = last_hidden_states.masked_fill(~attention_mask[..., None].bool(), 0.0)
            return last_hidden.sum(dim=1) / attention_mask.sum(dim=1)[..., None]

        batch_dict = self.tokenizer(texts, max_length=512, padding=True, truncation=True, return_tensors="pt").to(
            self.device
        )
        with torch.inference_mode():
            outputs = self.model(**batch_dict)
            embeddings = average_pool(outputs.last_hidden_state, batch_dict["attention_mask"])  # type: ignore
        if self.device != "cpu":
            embeddings = embeddings.cpu()
        return embeddings.numpy()

    def get_query_embeddings(
        self, queries: list[str], task_description: str = "Given a query, return the relevant law documents."
    ) -> npt.NDArray[np.float64]:
        queries = [self.get_detailed_instruct(task_description, query) for query in queries]
        return self._get_embeddings(queries)

    def get_document_embeddings(self, documents: list[str]) -> npt.NDArray[np.float64]:
        return self._get_embeddings(documents)
