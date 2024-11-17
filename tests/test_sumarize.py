from app.models import SUMMARIZATION_TYPE
from app.transcribe.transcription import LANG_CODE
from app.summary.summarization import summarize
import langsmith as ls

@ls.traceable(
    run_type="llm",
    name="Summarization test",
    tags=["summarization", "test"],
    metadata={"flow": "summarization", "env": "test"}
)
def test_summarize():
    text = """
    Fallout 4 is a post-apocalyptic action role-playing video game developed by Bethesda Game Studios. 
    The game is set in a post-apocalyptic Boston in the year 2287, 210 years after a devastating nuclear war. 
    Players can freely roam the game's world and leave a conversation at any time.
    The player character can engage in first- or third-person combat using various weapon types and abilities.
    """

    summary = summarize(text, SUMMARIZATION_TYPE.TLDR, LANG_CODE.ENGLISH)
    assert summary is not None
    assert len(summary) > 0
    assert "Fallout" in summary


def test_summarize_with_empty_input():
    summary = summarize("", SUMMARIZATION_TYPE.TLDR, LANG_CODE.ENGLISH)
    assert summary == ""

@ls.traceable(
    run_type="llm",
    name="Summarization test",
    tags=["summarization", "test"],
    metadata={"flow": "summarization", "env": "test"}
)
def test_summarize_with_different_types():
    text = "This is a test text that needs to be summarized in different ways."

    tldr_summary = summarize(text, SUMMARIZATION_TYPE.TLDR, LANG_CODE.ENGLISH)
    assert tldr_summary is not None
    assert len(tldr_summary) > 0

    concise_summary = summarize(text, SUMMARIZATION_TYPE.CONCISE, LANG_CODE.ENGLISH)
    assert concise_summary is not None
    assert len(concise_summary) > 0

    detailed_summary = summarize(text, SUMMARIZATION_TYPE.DETAILED, LANG_CODE.ENGLISH)
    assert detailed_summary is not None
    assert len(detailed_summary) > 0
