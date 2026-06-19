import struct
import zlib
from pathlib import Path

import fitz
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk, Document
from app.db.repositories import ChunkEmbeddingRepository
from app.db.session import create_sqlite_engine
from app.services.ingestion.image_extractor import PdfImageExtractionConfig, PdfImageExtractor
from app.services.ingestion.multimodal_pipeline import MultimodalIngestionPipeline
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_search import VectorSearchService


class StaticVisionProvider:
    provider_name = "deterministic"
    model_name = "static-vision-test"

    def describe_image(self, image_path, prompt=None):
        return "图表显示堆石混凝土抗压强度随龄期增长，并在后期趋于稳定。"


def test_multimodal_pipeline_creates_image_description_chunk_and_embedding(tmp_path) -> None:
    database_path = tmp_path / "multimodal.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    pdf_path = tmp_path / "figure.pdf"
    write_pdf_with_image(pdf_path)

    with TestingSessionLocal() as db:
        document = Document(
            title="多模态测试文档",
            source_type="open_access_pdf",
            source_path=str(pdf_path),
            file_name="figure.pdf",
            file_extension=".pdf",
            content_hash="stage45-multimodal-pdf",
            raw_path=str(pdf_path),
        )
        db.add(document)
        db.commit()
        document_id = document.id

        embedding_provider = DeterministicEmbeddingProvider(dimension=16)
        pipeline = MultimodalIngestionPipeline(
            db=db,
            image_extractor=PdfImageExtractor(
                PdfImageExtractionConfig(output_dir=tmp_path / "images")
            ),
            vision_provider=StaticVisionProvider(),
            embedding_provider=embedding_provider,
        )
        first_result = pipeline.process_document(document_id)
        second_result = pipeline.process_document(document_id)

        image_chunk = db.scalar(
            select(Chunk).where(
                Chunk.document_id == document_id,
                Chunk.chunk_type == "image_description",
            )
        )
        embeddings = ChunkEmbeddingRepository(db).list_embeddings(
            provider=embedding_provider.provider_name,
            model_name=embedding_provider.model_name,
        )
        search_results = VectorSearchService(db, embedding_provider).search("抗压强度 增长", top_k=3)

    assert first_result.extracted_images == 1
    assert first_result.created_chunks == 1
    assert first_result.embedding_result is not None
    assert first_result.embedding_result.indexed_chunks == 1
    assert second_result.created_chunks == 0
    assert second_result.skipped_images == 1
    assert image_chunk is not None
    assert image_chunk.source_image_path is not None
    assert image_chunk.heading_path == "多模态测试文档 > [图表]"
    assert len(embeddings) == 1
    assert search_results
    assert search_results[0].chunk_id == image_chunk.id


def write_pdf_with_image(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=240, height=180)
    page.insert_image(fitz.Rect(30, 30, 150, 150), stream=make_png_bytes(120, 120, (80, 120, 200)))
    document.save(path)
    document.close()


def make_png_bytes(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(raw))
        + png_chunk(b"IEND", b"")
    )


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)
