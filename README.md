# Lawsy - Making Law Easy

## Requirements

- Python
    - `uv pip install uv`
- OpenAI
    - `OPENAI_API_KEY`

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
