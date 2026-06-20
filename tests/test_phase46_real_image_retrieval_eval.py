import csv

from scripts.evaluate_phase46_real_image_retrieval import (
    EvaluationRecord,
    StoredEmbeddingProxyProvider,
    read_questions,
    summarize_records,
)


def test_real_image_retrieval_questions_schema_fixture(tmp_path) -> None:
    questions_csv = tmp_path / "questions.csv"
    with questions_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "query_id",
                "question",
                "category",
                "expected_has_image",
                "expected_image_keywords",
                "expected_caption_keywords",
                "expected_doc_keywords",
                "expected_source_image_path",
                "expected_page_number",
                "notes",
            ],
        )
        writer.writeheader()
        for index in range(25):
            writer.writerow(
                {
                    "query_id": f"must_{index}",
                    "question": "请召回应力应变曲线图",
                    "category": "must_have_image",
                    "expected_has_image": "true",
                    "expected_image_keywords": "应力应变|曲线",
                    "expected_caption_keywords": "应力应变",
                    "expected_doc_keywords": "力学性能",
                    "expected_source_image_path": f"data/images/1/page{index + 1}_img1.png",
                    "expected_page_number": str(index + 1),
                    "notes": "fixture",
                }
            )
        for index in range(25):
            writer.writerow(
                {
                    "query_id": f"help_{index}",
                    "question": "说明强度趋势时图片有帮助",
                    "category": "image_helpful",
                    "expected_has_image": "true",
                    "expected_image_keywords": "强度",
                    "expected_caption_keywords": "强度",
                    "expected_doc_keywords": "强度",
                    "expected_source_image_path": f"data/images/2/page{index + 1}_img1.png",
                    "expected_page_number": str(index + 1),
                    "notes": "fixture",
                }
            )
        for index in range(25):
            writer.writerow(
                {
                    "query_id": f"text_{index}",
                    "question": "什么是堆石混凝土？不要图片。",
                    "category": "text_only",
                    "expected_has_image": "false",
                    "expected_image_keywords": "",
                    "expected_caption_keywords": "",
                    "expected_doc_keywords": "",
                    "expected_source_image_path": "",
                    "expected_page_number": "",
                    "notes": "fixture",
                }
            )
        for index in range(25):
            writer.writerow(
                {
                    "query_id": f"noimg_{index}",
                    "question": "写一个 Python 示例。",
                    "category": "no_image",
                    "expected_has_image": "false",
                    "expected_image_keywords": "",
                    "expected_caption_keywords": "",
                    "expected_doc_keywords": "",
                    "expected_source_image_path": "",
                    "expected_page_number": "",
                    "notes": "fixture",
                }
            )

    questions = read_questions(questions_csv)

    assert len(questions) == 100
    assert {question.category for question in questions} == {
        "must_have_image",
        "image_helpful",
        "text_only",
        "no_image",
    }
    assert questions[0].expected_page_number == 1
    assert questions[0].expected_caption_keywords == ["应力应变"]


def test_stored_embedding_proxy_provider_returns_query_specific_vectors() -> None:
    provider = StoredEmbeddingProxyProvider(
        provider_name="paratera",
        model_name="GLM-Embedding-3",
        dimension=3,
        query_vectors={"hello world": [0.1, 0.2, 0.3]},
    )

    assert provider.embed_query(" hello   world ") == [0.1, 0.2, 0.3]
    assert provider.embed_query("missing") == [0.0, 0.0, 0.0]


def test_real_image_retrieval_summary_metrics() -> None:
    records = [
        EvaluationRecord(
            query_id="must_ok",
            question="请召回应力应变曲线图",
            category="must_have_image",
            expected_has_image=True,
            returned_image_count=2,
            relevant_image_count=1,
            top1_relevant=True,
            suppressed=False,
            expected_path_hit=True,
            top1_caption_match=True,
            topk_caption_match=True,
            top1_doc_match=True,
            wrong_generic_curve=False,
            top_score=0.9,
            top_caption="图1 应力应变曲线",
            top_page_number=5,
            top_document_title="力学性能",
            top_source_image_path="data/images/1/page5_img1.png",
            top_image_url="/assets/images/1/page5_img1.png",
            captions_present=2,
            page_numbers_present=2,
            error="",
        ),
        EvaluationRecord(
            query_id="help_ok",
            question="强度趋势图有帮助",
            category="image_helpful",
            expected_has_image=True,
            returned_image_count=1,
            relevant_image_count=1,
            top1_relevant=True,
            suppressed=False,
            expected_path_hit=True,
            top1_caption_match=True,
            topk_caption_match=True,
            top1_doc_match=True,
            wrong_generic_curve=False,
            top_score=0.8,
            top_caption="图2 强度曲线",
            top_page_number=6,
            top_document_title="强度研究",
            top_source_image_path="data/images/2/page6_img1.png",
            top_image_url="/assets/images/2/page6_img1.png",
            captions_present=1,
            page_numbers_present=1,
            error="",
        ),
        EvaluationRecord(
            query_id="text_ok",
            question="不要图片",
            category="text_only",
            expected_has_image=False,
            returned_image_count=0,
            relevant_image_count=0,
            top1_relevant=False,
            suppressed=True,
            expected_path_hit=False,
            top1_caption_match=False,
            topk_caption_match=False,
            top1_doc_match=False,
            wrong_generic_curve=False,
            top_score=0.0,
            top_caption="",
            top_page_number=None,
            top_document_title="",
            top_source_image_path="",
            top_image_url="",
            captions_present=0,
            page_numbers_present=0,
            error="",
        ),
        EvaluationRecord(
            query_id="noimg_ok",
            question="离题",
            category="no_image",
            expected_has_image=False,
            returned_image_count=0,
            relevant_image_count=0,
            top1_relevant=False,
            suppressed=True,
            expected_path_hit=False,
            top1_caption_match=False,
            topk_caption_match=False,
            top1_doc_match=False,
            wrong_generic_curve=False,
            top_score=0.0,
            top_caption="",
            top_page_number=None,
            top_document_title="",
            top_source_image_path="",
            top_image_url="",
            captions_present=0,
            page_numbers_present=0,
            error="",
        ),
    ]

    summary = summarize_records(
        records,
        elapsed_seconds=0.0,
        min_score=0.5,
        query_embedding_mode="stored_embedding_proxy",
    )

    assert summary["image_precision"] == "0.6667"
    assert summary["must_have_recall"] == "1.0000"
    assert summary["image_suppression"] == "1.0000"
    assert summary["topk_caption_match_rate"] == "1.0000"
    assert summary["threshold_decision"] == "needs_rerank"
