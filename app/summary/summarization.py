import logging

from langchain.chains.llm import LLMChain
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
import langsmith as ls

from app.cache import conditional_lru_cache
from app.models import SUMMARIZATION_TYPE
from app.settings import get_settings
from app.transcribe.transcription import LANG_CODE


def get_template(type):
    templates = {
        SUMMARIZATION_TYPE.CONCISE:
            """Write a concise summary in language code={lang} of the following:\n"{text}"\nCONCISE SUMMARY:""",
        SUMMARIZATION_TYPE.TLDR:
            """Imagine you're a researcher who has only 30 seconds to summarize this article in language code={lang}. It should be based on the provided text and give 3 the most important details. \n{text}""",
        SUMMARIZATION_TYPE.DETAILED:
            """As a professional summarizer, create a detailed, in-depth, and concise summary in language code={lang} of the provided text, while strongly adhering to these guidelines:
            - Incorporate main ideas and essential information, eliminating extraneous language and focusing on critical aspects.
            - Rely strictly on the provided text, without including external information.
            - Format the summary in paragraph form for easy understanding.
            - The entire content should be organized in a clear and logical manner
            - use markdown to format the text, you can use emojis, bullet points, numbered lists, etc. to make the summary more engaging and easy to read.

            Include extra information such as:
            - list of mentioned articles, books, podcasts,persons, movies etc. in seperated subsections. If empty, just skip it
            - list of guidelines, practises,techniques, rules, principles, steps, procedures etc. in seperated subsections. If empty, just skip it
            - list of examples, scenarios, use cases, case studies etc. in seperated subsections. If empty, just skip it
            - list of tools, software, hardware, services, products etc. in seperated subsections. If empty, just skip it

            My needs:
            - I want to get super detailed summary of super important text. I use it for my research job and i need to get all the details from the text.

            I will pay you extra if you can provide me with a very detailed summary of the text. I need to get all the details from the text.

            Take a deep breath and return very detailed summary in markdown of below  transcription and nothing else. \n###\n{text}"""
    }
    return templates[type]

@ls.traceable(
    run_type="llm",
    name="Summarization",
    tags=["summarization"],
    metadata={"flow": "summarization"}
)
async def summarize(text: str, type: SUMMARIZATION_TYPE, lang: LANG_CODE) -> str:
    """
    Summarize text using OpenAI's GPT model.

    Args:
        text (str): The text to summarize.
        type (SUMMARIZATION_TYPE): The type of summary to generate.
        lang (LANG_CODE): The language of the text and desired summary.

    Returns:
        str: The generated summary.
    """
    logging.info(f"Summarizing text with type: {type.name}, lang: {lang}")

    from app.settings import client_openai
    response = await client_openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": f"You are a helpful assistant that summarizes text in {lang.value} language."},
            {"role": "user", "content": f"Please provide a {type.value} summary of the following text:\n\n{text}"}
        ]
    )

    return response.choices[0].message.content
