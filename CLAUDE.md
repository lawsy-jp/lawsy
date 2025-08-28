# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lawsy Pharma is an AI-powered tool specialized in Japanese pharmaceutical law research. It searches and analyzes pharmaceutical regulations (薬機法, GCP省令, GMP省令, etc.) and generates comprehensive reports with violation analysis and mind map visualizations.

## Tech Stack

- **Frontend**: Streamlit (runs on port 8502)
- **LLM**: OpenAI GPT-4 / GPT-4o-mini via DSPy framework
- **Vector Search**: FAISS
- **Embedding**: OpenAI text-embedding-3-small
- **Language**: Python 3.12+
- **Package Manager**: uv

## Essential Commands

### Setup and Installation
```bash
make install                # Install dependencies with uv
cp .env.example .env       # Set up environment variables (requires OPENAI_API_KEY)
make pharma-setup          # Complete pharma dataset setup (initial setup only, ~30 minutes)
```

### Running the Application
```bash
make pharma-run            # Start pharma-specialized version (recommended, port 8502)
make lawsy-run-app         # Start standard version (port 8501)
```

### Data Preparation (if needed separately)
```bash
make pharma-prepare        # Create complete pharma dataset
make pharma-download-laws  # Download pharma law XMLs from e-Gov API
make pharma-process-xml    # Process XML files
make pharma-create-article-chunks  # Split laws into chunks
make pharma-embed-article-chunks   # Generate embeddings
make pharma-create-article-chunk-vector-index  # Create vector index
```

### Development
```bash
make format               # Code formatting with ruff
make lint                 # Lint check with ruff + pyright
make pharma-clean         # Clean generated data
make help                 # Show all available commands
```

## Code Architecture

### Core Application Structure
- **Main App**: `src/lawsy/app/app.py` - Streamlit application entry point
- **Research Logic**: `src/lawsy/app/research.py` - Core research functionality
- **Report Generation**: `src/lawsy/app/report.py` - Report display and formatting

### AI Components (in `src/lawsy/ai/`)
- **Query Processing**: `pharma_query_processor.py` - Specialized pharma query handling
- **Report Writing**: `report_writer.py` - Comprehensive report generation
- **Violation Analysis**: `violation_summarizer.py` - Identifies legal violations/issues
- **Mind Map Generation**: `mindmap_maker.py` - Creates visual mind maps
- **Query Enhancement**: `query_expander.py`, `query_refiner.py` - Query optimization

### Data Processing Pipeline
- **Chunking**: `src/lawsy/chunker/article_chunker.py` - Breaks down legal documents
- **Encoding**: `src/lawsy/encoder/` - Text embeddings (OpenAI, multilingual-e5)
- **Retrieval**: `src/lawsy/retriever/` - Vector search and web search
- **Parsing**: `src/lawsy/parser/parser.py` - Legal document parsing

### Environment Configuration
Key environment variables in `.env`:
- `OPENAI_API_KEY` - Required for LLM and embeddings
- `LAWSY_LM` - LLM model (default: openai/gpt-4o-mini)
- `LAWSY_OUTPUT_DIR` - Data storage (default: ./outputs)
- `LAWSY_VIOLATION_SUMMARY_MAX_ITEMS` - Max violation items to show (default: 10)

### Data Flow
1. User query → Query processor → Query expansion/refinement
2. Vector search in FAISS index + web search for supplementary info
3. Retrieved articles → Report writer → Comprehensive analysis
4. Violation summarizer → Issue identification
5. Mind map generator → Visual representation
6. Results displayed in Streamlit UI

### Code Style
- Formatter: ruff (line length: 119)
- Linter: ruff + pyright
- Quote style: double quotes
- Python target: 3.12+
- Import organization: combine-as-imports = true

## Development Notes

### Testing the Application
After making changes, test by running `make pharma-run` and accessing http://localhost:8502

### Working with Legal Data
The pharma dataset includes processed XMLs from e-Gov API. The preprocessing pipeline creates:
- Article chunks in JSONL format
- Embeddings in Parquet format  
- FAISS vector indices

### Pharma Specialization
This fork is specialized for pharmaceutical law. Key differences from standard Lawsy:
- Focused dataset (薬機法, GCP省令, GMP省令, etc.)
- Pharma-specific query processing
- Violation analysis tailored to pharmaceutical regulations