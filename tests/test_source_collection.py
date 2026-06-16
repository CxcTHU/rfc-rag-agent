from app.services.source_collection import (
    SourceCandidate,
    classify_categories,
    decode_openalex_abstract,
    dedupe_candidates,
    filter_relevant_candidates,
    metadata_markdown,
    mdpi_static_pdf_url,
    sanitize_filename,
    strip_markup,
)


def test_classify_categories_detects_rfc_topics() -> None:
    categories = classify_categories(
        "Seismic behavior and elastic modulus simulation of rock-filled concrete dam"
    )

    assert "seismic_response" in categories
    assert "mechanical_properties" in categories
    assert "numerical_modeling" in categories
    assert "dam_engineering" in categories


def test_dedupe_candidates_merges_by_doi_and_keeps_pdf_url() -> None:
    candidates = [
        SourceCandidate(
            source_id="openalex_1",
            title="Rock-filled concrete dam",
            doi="10.123/example",
            discovered_via="OpenAlex",
        ),
        SourceCandidate(
            source_id="s2_1",
            title="Rock-filled concrete dam",
            doi="https://doi.org/10.123/example",
            discovered_via="Semantic Scholar",
            pdf_url="https://example.org/paper.pdf",
        ),
    ]

    merged = dedupe_candidates(candidates)

    assert len(merged) == 1
    assert merged[0].pdf_url == "https://example.org/paper.pdf"
    assert merged[0].discovered_via == "OpenAlex;Semantic Scholar"


def test_sanitize_filename_removes_path_unsafe_characters() -> None:
    assert sanitize_filename("Rock-filled concrete: dam / test?") == "Rock-filled_concrete_dam_test"


def test_filter_relevant_candidates_keeps_rfc_and_drops_cfrd() -> None:
    candidates = [
        SourceCandidate(source_id="1", title="Study on rock-fill concrete dam"),
        SourceCandidate(source_id="2", title="Settlement behaviour of a concrete faced rock-fill dam"),
    ]

    filtered = filter_relevant_candidates(candidates)

    assert [candidate.source_id for candidate in filtered] == ["1"]


def test_filter_relevant_candidates_uses_abstract_and_keywords() -> None:
    candidates = [
        SourceCandidate(
            source_id="1",
            title="Filling capacity evaluation",
            abstract="This paper studies self-compacting concrete in rock-filled concrete.",
        ),
        SourceCandidate(
            source_id="2",
            title="Generic concrete strength study",
            abstract="This paper studies ordinary concrete strength.",
        ),
    ]

    filtered = filter_relevant_candidates(candidates)

    assert [candidate.source_id for candidate in filtered] == ["1"]


def test_filter_relevant_candidates_drops_random_forest_classifier_rfc_noise() -> None:
    candidates = [
        SourceCandidate(
            source_id="noise",
            title="Machine Learning Assessment for Severity of Liver Fibrosis for Chronic HBV",
            abstract=(
                "Random Forest Classifier (RFC) models were used with serum markers. "
                "The retrospective data set was used to establish a classifier."
            ),
        )
    ]

    assert filter_relevant_candidates(candidates) == []


def test_mdpi_static_pdf_url_converts_known_pdf_link() -> None:
    url = "https://www.mdpi.com/1996-1944/13/1/108/pdf?version=1577274421"

    assert mdpi_static_pdf_url(url) == (
        "https://mdpi-res.com/d_attachment/materials/materials-13-00108/"
        "article_deploy/materials-13-00108.pdf"
    )


def test_decode_openalex_abstract_rebuilds_text() -> None:
    inverted = {"Rock-filled": [0], "concrete": [1], "dam": [2]}

    assert decode_openalex_abstract(inverted) == "Rock-filled concrete dam"


def test_strip_markup_removes_crossref_jats_tags() -> None:
    value = "<jats:p>Rock-filled &amp; self-compacting concrete.</jats:p>"

    assert strip_markup(value) == "Rock-filled & self-compacting concrete."


def test_metadata_markdown_contains_abstract_and_source_fields() -> None:
    markdown = metadata_markdown(
        SourceCandidate(
            source_id="openalex_1",
            title="Study on rock-fill concrete dam",
            authors="Jin Feng",
            abstract="Rock-filled concrete is studied.",
            doi="10.123/example",
        )
    )

    assert "# Study on rock-fill concrete dam" in markdown
    assert "- source_id: openalex_1" in markdown
    assert "## Abstract" in markdown
    assert "Rock-filled concrete is studied." in markdown
