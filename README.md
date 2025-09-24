# Lawsy - Making Law Easy

Lawsy is a hackathon-born Legal Search tool for Japanese statutes and regulations. This open-source repository reflects the prototype developed during the hackathon and is not a production-ready implementation. It integrates semantic search, statute databases, and authoritative web sources to generate clear, referenced reports, showing how legal research can be made more accessible and transparent.

## Requirements

- uv
    - `pip install uv`
- OpenAI
    - `OPENAI_API_KEY`
- GCloud CLI
    - https://cloud.google.com/sdk/docs/install

## Run

### 1. Install dependencies

Install Python packages

```shell
make install
```

### 2. Create .env file

Create .env file and put it in the repository root directory.

```text
OPENAI_API_KEY=sk-...  # OpenAI API KEY
LAWSY_WEB_SEARCH_ENGINE=DuckDuckGo
LAWSY_LM=openai/gpt-4o-mini
```

### 3. Download Preprocessed Data

```shell
make lawsy-download-preprocessed-data
```

## Run App

```shell
make lawsy-run-app
```

## Development

### Format & Lint

format:

```shell
make format
```

lint:

```shell
make lint
```

## References

- 2025-03-16 [行政と技術の融合へ—法令Deep ResearchツールLawsyの開発記録](https://note.com/policygarage/n/nbea6a40f9a0a)
- 2025-03-14[第三弾：「法令」×「デジタル」ハッカソンを開催しました](https://www.digital.go.jp/news/9fb5ef8e-c631-4974-96d9-0b145304c553)
- 2025-03-06 [法令 Deep Research ツール Lawsy を OSS として公開しました](https://note.com/tatsuyashirakawa/n/nbda706503902)
