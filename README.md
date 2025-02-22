# Lawsy - Making Law Easy

## Requirements

- Python
    - `uv pip install uv`
- OpenAI
    - `OPENAI_API_KEY`
- Tavily
    - `TAVILY_API_KEY`

## Run

### 1. Install dependencies

Install Python packages

```shell
make install
```

### 2. Create .env file

Create .env file and put it in the repository root directory.

```text
OUTPUT_DIR=./outputs  # path to the directory in which processed data are placed
OPENAI_API_KEY=sk-...  # OpenAI API KEY
TAVILY_API_KEY=tvly-...  # Tavly API KEY
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
