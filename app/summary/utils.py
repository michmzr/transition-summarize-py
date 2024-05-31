import logging
from enum import Enum

from langchain.chains.llm import LLMChain
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI


class SUMMARIZATION_TYPE(str, Enum):
    CONCISE = "concise"
    TLDR = "tldr"
    DETAILED = "detailed"


def get_template(type):
    templates = {
        SUMMARIZATION_TYPE.CONCISE:
            """Write a concise summary in language {lang} of the following:\n"{text}"\nCONCISE SUMMARY:""",
        SUMMARIZATION_TYPE.TLDR:
            """Imagine you're a news reporter who has only 30 seconds to summarize this article in language {lang} for a broadcast.\n{text}""",
        SUMMARIZATION_TYPE.DETAILED:
            """As a professional summarizer, create a detailed, in-depth, and concise summary in language {lang} of the provided text, while adhering to these guidelines: Incorporate main ideas and essential information, eliminating extraneous language and focusing on critical aspects. Rely strictly on the provided text, without including external information. Format the summary in paragraph form for easy understanding. Return summary and nothing else.\n{text}"""
    }
    return templates[type]


def summarize(text: str, type: SUMMARIZATION_TYPE, lang: str = "en"):
    logging.info(f"Summarizing text with type: ${type}, lang: {lang}")

    # Define prompt
    prompt_template = get_template(type)
    prompt = PromptTemplate.from_template(prompt_template)

    # Define LLM chain
    llm = ChatOpenAI(temperature=0, model_name="gpt-4o")
    llm_chain = LLMChain(llm=llm, prompt=prompt)

    return llm_chain.run({"text": text, "lang": lang})
