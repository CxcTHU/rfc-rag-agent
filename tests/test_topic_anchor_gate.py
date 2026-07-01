from app.services.brain.workflow import has_topic_anchor


def test_topic_anchor_gate_accepts_chinese_domain_questions() -> None:
    assert has_topic_anchor("堆石混凝土有哪些优点？")
    assert has_topic_anchor("大坝裂缝成因有哪些？")
    assert has_topic_anchor("请给我相关表格证据，最好包含施工配合比")


def test_topic_anchor_gate_rejects_unrelated_questions() -> None:
    assert not has_topic_anchor("How should I cook pasta for dinner?")
