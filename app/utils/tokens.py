import tiktoken
import logging
from typing import List
import anthropic
import logging


def anthropic_count_tokens(user_prompt: str, system_prompt: str, model: str) -> int:
    client = anthropic.Anthropic()

    response = client.messages.count_tokens(
        model=model,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": user_prompt
        }],
    )

    logging.debug(response.model_dump_json())

    return response.model_dump_json().get("input_tokens")


def openai_count_tokens(user_prompt: str, model: str) -> int:
    enc = tiktoken.encoding_for_model(model)
    tokens = enc.encode(user_prompt)
    return len(tokens)
