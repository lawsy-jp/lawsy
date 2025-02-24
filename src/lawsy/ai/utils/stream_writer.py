from typing import AsyncGenerator, Callable

import litellm
from dspy.adapters.chat_adapter import ChatAdapter

from lawsy.utils.logging import logger


class StreamLineWriter:
    def __init__(self, lm, signature_cls) -> None:
        self.lm = lm
        self.signature_cls = signature_cls
        self.keywords = list(signature_cls.model_fields.keys()) + ["completed"]
        self.__text = None

    def get_generated_text(self) -> str:
        assert self.__text is not None
        return self.__text

    async def generate(
        self, input_kwargs: dict[str, str], line_fixer: Callable | None = None
    ) -> AsyncGenerator[str, None]:
        adapter = ChatAdapter()
        messages = adapter.format(
            self.signature_cls,  # type:ignore
            [],
            input_kwargs,
        )
        response = await litellm.acompletion(
            model=self.lm.model,
            messages=messages,
            stream=True,
            num_retries=self.lm.num_retries,
            extra_headers={"Connection": "close"},
            **self.lm.kwargs,
        )
        buf = ""
        text = ""
        async for chunk in response:  # type: ignore
            content = chunk.choices[0]["delta"]["content"] or ""  # type:ignore
            buf += content
            for keyword in self.keywords:
                buf = buf.replace(f"[[ ## {keyword} ## ]]", "")
            if buf.find("\n") >= 0:
                head, tail = buf.split("\n", 1)
                if line_fixer:
                    head = line_fixer(head)
                yield head + "\n"
                text += head + "\n"
                buf = tail
        if buf:
            yield buf
            text += buf
        self.__text = text

        logger.info(
            " ".join(
                [
                    f"[{self.signature_cls.__name__}]",
                    " ".join([f"(in) {key}: {len(val)} chars" for key, val in input_kwargs.items()]),
                    f"(out) text: {len(text)} chars",
                ]
            )
        )
