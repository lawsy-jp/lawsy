from pathlib import Path

import dotenv
import typer

dotenv.load_dotenv()
app = typer.Typer()


@app.command()
def create_article_chunks(xml_dir: Path, output_jsonl_file: Path) -> None:
    import json

    from tqdm import tqdm

    from lawsy.chunker.article_chunker import ArticleChunker
    from lawsy.parser.parser import parse_from_xml_file
    from lawsy.utils.logging import get_logger

    logger = get_logger()

    chunker = ArticleChunker(indent=2)
    output_jsonl_file.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    total_length = 0
    with open(output_jsonl_file, "w") as fout:
        xml_files = list(xml_dir.glob("**/*.xml"))
        for xml_file in tqdm(xml_files):
            law = parse_from_xml_file(xml_file)
            law_title = law.law_body.law_title.text  # type: ignore
            for chunk in chunker(law):
                article = chunk["article_path"][-1]
                if chunk["anchor"].find("Sp-") >= 0:
                    article_title = law_title + " 附則 " + article.article_title.text  # type: ignore
                else:
                    article_title = law_title + " " + article.article_title.text  # type: ignore
                print(
                    json.dumps(
                        dict(
                            file_name=xml_file.stem, anchor=chunk["anchor"], title=article_title, chunk=chunk["chunk"]
                        ),
                        ensure_ascii=False,
                    ),
                    file=fout,
                )
                count += 1
                total_length += len(chunk["chunk"])
    avg_length = total_length / count if count > 0 else 0
    logger.info(f"Created {count} chunks (avg length: {avg_length}).")


@app.command()
def embed_article_chunks(
    input_jsonl_file: Path,
    output_parquet_file: Path,
    max_chars: int | None = 4096,
    model_name: str = "openai/text-embedding-3-small",
) -> None:
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq
    from tqdm import tqdm

    provider = model_name.split("/")[0]
    if provider == "openai":
        from lawsy.encoder.openai import OpenAITextEmbedding

        encoder = OpenAITextEmbedding(model_name)
    else:
        from lawsy.encoder.me5 import ME5Instruct

        assert model_name == "multilingual-e5-large-instruct"
        encoder = ME5Instruct()

    schema = pa.schema([("file_name", pa.string()), ("anchor", pa.string()), ("embedding", pa.list_(pa.float32()))])
    output_parquet_file.parent.mkdir(parents=True, exist_ok=True)
    with pq.ParquetWriter(output_parquet_file, schema) as writer:
        batch = []
        batch_size = 512
        with open(input_jsonl_file, "r") as fin:
            for line in tqdm(fin):
                d = json.loads(line)
                text = d["chunk"]
                if max_chars is not None:
                    text = text[:max_chars]
                if text.strip() == "":
                    continue
                embedding = encoder.get_document_embeddings([text])[0]
                batch.append(
                    (
                        d["file_name"],
                        d["anchor"],
                        embedding.tolist(),
                    )
                )
                if len(batch) >= batch_size:
                    table = pa.Table.from_arrays(
                        [pa.array([row[i] for row in batch], type=schema[i].type) for i in range(len(schema))],
                        schema=schema,
                    )
                    writer.write_table(table)
                    batch = []
            if batch:
                table = pa.Table.from_arrays(
                    [pa.array([row[i] for row in batch], type=schema[i].type) for i in range(len(schema))],
                    schema=schema,
                )
                writer.write_table(table)


@app.command()
def create_article_chunk_vector_index(
    input_parquet_file: Path, input_chunks_file: Path, output_dir: Path, dim: int | None = None
) -> None:
    import json
    from datetime import datetime

    import numpy as np
    import pandas as pd
    import pyarrow.parquet as pq
    from tqdm import tqdm

    from lawsy.retriever.article_search.faiss import FaissFlatArticleRetriever

    assert dim is None or dim > 0

    table = pq.read_table(input_parquet_file)
    file_names = table.column("file_name").to_pylist()
    anchors = table.column("anchor").to_pylist()
    embeddings = np.stack(table.column("embedding").to_numpy())
    if dim is None:
        dim = embeddings.shape[1]
    else:
        embeddings = embeddings[:, :dim]
    chunks = {}
    with open(input_chunks_file) as fin:
        for line in tqdm(fin):
            chunk = json.loads(line)
            chunks[chunk["file_name"], chunk["anchor"]] = chunk
    retriever = FaissFlatArticleRetriever.create(dim=dim)
    meta_data = [
        {
            "file_name": file_name,
            "anchor": anchor,
            "title": chunks[file_name, anchor]["title"],
            "chunk": chunks[file_name, anchor]["chunk"],
        }
        for file_name, anchor in zip(file_names, anchors)
    ]
    # 同一内容の条文は最も古い日時のみを残す
    df = pd.DataFrame(meta_data)
    df["date"] = df["file_name"].apply(lambda file_name: datetime.strptime(file_name.split("_")[1], "%Y%m%d"))
    index = df.sort_values("date")["chunk"].drop_duplicates().index
    embeddings = embeddings[index]
    meta_data = [meta_data[idx] for idx in index]
    retriever.add(embeddings, meta_data)
    retriever.save(output_dir)


if __name__ == "__main__":
    app()
