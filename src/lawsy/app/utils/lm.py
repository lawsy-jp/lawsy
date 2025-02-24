import json
import os
from pathlib import Path

import dspy


def load_lm(model_name: str, **kwargs) -> dspy.LM:
    """
    params:
        model_name (str)  ex. openai/gpt-4o  vertex_ai/gemini-2.0-flash-001
    """
    kwargs = dict(max_tokens=8192, temperature=0.0, cache=False, **kwargs)
    assert len(model_name.split("/")) == 2
    provider = model_name.split("/")[0]
    if provider == "openai":
        return dspy.LM(model_name, api_key=os.environ["OPENAI_API_KEY"], **kwargs)  # type: ignore
    elif provider == "vertex_ai":
        sa_file = Path(os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or "sa.json")
        if sa_file.exists():
            with open(sa_file) as fin:
                vertex_credentials = json.load(fin)
            vertex_credentials_json = json.dumps(vertex_credentials)
            return dspy.LM(model_name, vertex_credentials=vertex_credentials_json, **kwargs)  # type: ignore
        else:
            return dspy.LM(model_name, **kwargs)  # type: ignore
    else:
        raise ValueError(f"provider must be one of [openai, vertex_ai] but {provider} was given")
