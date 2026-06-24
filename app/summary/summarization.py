import logging

from langchain_core.output_parsers import StrOutputParser
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
            """You are a professional summarizer. Create a comprehensive summary in language code={lang} based strictly on the provided transcription. Do not add external information.

## Output format (markdown)

### Summary
Write as many detailed paragraphs as needed to cover all key ideas, arguments, and conclusions. If the input includes timestamps, follow the chronological flow and summarize segment by segment.

### Referenced media
Articles, books, podcasts, movies, persons mentioned. For each item, add nested bullets with context of how/where it was mentioned. Omit this section if none found.

### Guidelines & techniques
Principles, rules, practices, steps, procedures mentioned. For each, add nested bullets with context. Omit if none found.

### Examples & case studies
Scenarios, use cases, examples mentioned. For each, add nested bullets with context. Omit if none found.

### Tools & products
Software, hardware, services, products mentioned. For each, add nested bullets with context. Omit if none found.

## Rules
- Use markdown formatting: headers, bullet points, numbered lists, bold for key terms.
- The input may include video metadata followed by a transcript. Use metadata only as context; base the summary on the transcript.
- When timestamps are present in [MM:SS] or [HH:MM:SS] format, use them to organize the summary chronologically.
- Return only the summary, no meta-commentary.

{text}"""
    }
    return templates[type]

@ls.traceable(
    run_type="llm",
    name="Summarization",
    tags=["summarization"],
    metadata={"flow": "summarization"}
)
@conditional_lru_cache
def summarize(text: str, type: SUMMARIZATION_TYPE, lang: LANG_CODE):
    logging.info(
        f"Summarizing text with type: '{type}', lang code: '{lang.value}'")

    if not text:
        logging.warning("Text is empty, returning empty string")
        return ""

    # Define prompt
    prompt_template = get_template(type)
    prompt = PromptTemplate.from_template(prompt_template)

    llm = ChatOpenAI(temperature=0.1, model_name="gpt-5.5", api_key=get_settings().openai_api_key)
    llm_chain = prompt | llm | StrOutputParser()

    return llm_chain.invoke({"text": text, "lang": lang.value})
