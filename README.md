# lax_dx_hackathon_2025
A repository for 「法令」×「デジタル」ハッカソン


## Development
### Setup

install all dependencies:

```shell
pip install uv  # install uv
make install
```

### Format & Lint

format:

```shell
make format
```

lint:

```shell
make lint
```

## Applications

### Kokkai Crawler

国会の議事録を取得するためのコード
src: `src/kokkai_crawler`

全議事録の取得（既存がある場合、最終年/月以外はスキップ）:

```shell
make crawl-all
```
