def test_summary_result_accepts_metadata():
    from app.models import SummaryResult

    result = SummaryResult(
        summary="Test summary",
        metadata={"title": "Video", "description": "Desc"},
    )

    assert result.metadata == {"title": "Video", "description": "Desc"}


def test_summary_result_metadata_defaults_to_none():
    from app.models import SummaryResult

    result = SummaryResult(summary="Test summary")

    assert result.metadata is None


def test_api_processing_result_accepts_metadata():
    from app.models import ApiProcessingResult

    result = ApiProcessingResult(result=True, metadata={"title": "Video"})

    assert result.metadata == {"title": "Video"}


def test_api_processing_result_metadata_defaults_to_none():
    from app.models import ApiProcessingResult

    result = ApiProcessingResult(result=True)

    assert result.metadata is None
