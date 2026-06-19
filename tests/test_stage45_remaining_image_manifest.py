import sqlite3

from scripts.build_phase45_remaining_image_manifest import main
from tests.test_stage45_image_extractor import write_pdf_with_images


def test_build_remaining_image_manifest_marks_existing_and_pending(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "docs.sqlite"
    pdf_path = tmp_path / "paper.pdf"
    write_pdf_with_images(pdf_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "create table documents (id integer primary key, title text, file_extension text, raw_path text)"
        )
        connection.execute(
            "create table chunks (id integer primary key, document_id integer, chunk_type text, source_image_path text)"
        )
        connection.execute(
            "insert into documents (id, title, file_extension, raw_path) values (1, 'doc', '.pdf', ?)",
            (str(pdf_path),),
        )
        connection.execute(
            "insert into chunks (id, document_id, chunk_type, source_image_path) values (1, 1, 'image_description', ?)",
            ((tmp_path / "images" / "1" / "page1_img1.png").as_posix(),),
        )
        connection.commit()
    ids_path = tmp_path / "ids.txt"
    ids_path.write_text("1\n", encoding="utf-8")
    output_csv = tmp_path / "manifest.csv"
    output_summary = tmp_path / "summary.json"
    split_dir = tmp_path / "split"
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_phase45_remaining_image_manifest.py",
            "--document-ids-file",
            str(ids_path),
            "--db-path",
            str(db_path),
            "--image-output-dir",
            str(tmp_path / "images"),
            "--min-width",
            "50",
            "--min-height",
            "100",
            "--output-csv",
            str(output_csv),
            "--output-summary",
            str(output_summary),
            "--split-output-dir",
            str(split_dir),
            "--split-count",
            "2",
        ],
    )

    main()

    manifest_text = output_csv.read_text(encoding="utf-8-sig")
    assert ",existing," in manifest_text
    assert ",pending," in manifest_text
    assert (split_dir / "image_route_1.csv").exists()
    assert (split_dir / "image_route_2.csv").exists()
