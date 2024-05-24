import logging
from enum import Enum

from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain.chains.llm import LLMChain
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI


class SUMMARIZATON_TYPE(Enum):
    CONCISE = """Write a concise summary of the following:
    "{text}"
    CONCISE SUMMARY:"""
    TLDR = """Imagine you're a news reporter who has only 30 seconds to summarize this article for a broadcast.
    
    {text}
    """
    DETAILED = """
As a professional summarizer, create a detailed, in-depth, and concise summary of the provided text, while adhering to these guidelines: Incorporate main ideas and essential information, eliminating extraneous language and focusing on critical aspects. Rely strictly on the provided text, without including external information. Format the summary in paragraph form for easy understanding. Return summmary and nothing else.

{text}
    """


def summarize(text, type:str):
    logging.info(f"Summarizing text with type: ${type}")

    # Define prompt
    prompt_template = SUMMARIZATON_TYPE[type].value
    prompt = PromptTemplate.from_template(prompt_template)

    # Define LLM chain
    llm = ChatOpenAI(temperature=0, model_name="gpt-4o")
    llm_chain = LLMChain(llm=llm, prompt=prompt)

    return llm_chain.run(text)
