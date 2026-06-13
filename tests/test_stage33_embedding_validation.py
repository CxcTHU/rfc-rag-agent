from pathlib import Path

from scripts import evaluate_stage33_embedding_migration as migration


def test_stage33_embedding_migration_dry_run_outputs_jina_and_glm(tmp_path, monkeypatch) -> None:
    results_path = tmp_path / "stage33_embedding_migration_results.csv"
    summary_path = tmp_path / "stage33_embedding_migration_summary.csv"

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate_stage33_embedding_migration.py",
            "--out-results",
            str(results_path),
            "--out-summary",
            str(summary_path),
            "--top-k",
            "5",
        ],
    )

    migration.main()

    results = results_path.read_text(encoding="utf-8")
    summary = summary_path.read_text(encoding="utf-8")

    assert "jina_baseline,jina,jina-embeddings-v3,1024" in summary
    assert "glm_candidate,paratera,GLM-Embedding-3,2048" in summary
    assert "dry_run" in results
    assert "dry_run_only" in summary


def test_stage33_design_names_real_faiss_index_pairs() -> None:
    design = Path("docs/stage33_rag_performance_embedding_validation.md").read_text(
        encoding="utf-8"
    )

    assert "data/faiss/jina_jina-embeddings-v3_dim1024.index" in design
    assert "data/faiss/jina_jina-embeddings-v3_dim1024_ids.json" in design
    assert "data/faiss/paratera_GLM-Embedding-3_dim2048.index" in design
    assert "data/faiss/paratera_GLM-Embedding-3_dim2048_ids.json" in design
