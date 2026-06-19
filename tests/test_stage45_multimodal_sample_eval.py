from collections import Counter

from scripts.evaluate_phase45_multimodal_sample import RetrievalQualityRow, summarize


def test_multimodal_sample_summary_passes_when_images_are_indexed_and_retrievable() -> None:
    summary = summarize(
        sample_ids={1, 2, 3, 4, 5},
        status_counts=Counter({"processed": 4, "failed": 1}),
        doc_stats={1: 2, 2: 1},
        image_rows=[
            (1, 11, "这是一段包含堆石混凝土施工图表信息的有效中文图片描述。" * 3),
            (1, 12, "这是一段包含堆石混凝土试验装置信息的有效中文图片描述。" * 3),
            (2, 21, "这是一段包含堆石混凝土强度曲线信息的有效中文图片描述。" * 3),
        ],
        image_embeddings=3,
        retrieval_rows=[
            RetrievalQualityRow("施工流程图", 5, 1, "image_description", 1),
            RetrievalQualityRow("抗压强度曲线", 5, 1, "text", 2),
            RetrievalQualityRow("级配曲线", 5, 0, "text", 3),
        ],
    )

    assert summary.passed_quality_gate is True
    assert summary.missing_image_embeddings == 0
    assert summary.vector_queries_with_image_hit == 2


def test_multimodal_sample_summary_fails_when_embeddings_are_missing() -> None:
    summary = summarize(
        sample_ids={1, 2, 3, 4, 5},
        status_counts=Counter({"processed": 5}),
        doc_stats={1: 1},
        image_rows=[(1, 11, "有效图片描述" * 20)],
        image_embeddings=0,
        retrieval_rows=[RetrievalQualityRow("施工流程图", 5, 1, "image_description", 1)],
    )

    assert summary.passed_quality_gate is False
    assert summary.missing_image_embeddings == 1
