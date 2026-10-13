# ClusterSLM — repository-scale vulnerability analysis prototype

ClusterSLM is a research prototype for repository ingestion, Python and JavaScript/TypeScript structural parsing, import-aware symbol resolution, graph-guided partitioning, boundary-aware finding reconciliation, a rule-based static baseline, and optional small-language-model inference.

## Current capabilities

- Scans repositories and reports parsed versus detected-only languages.
- Parses Python and JavaScript/TypeScript where parser dependencies are installed.
- Builds module/symbol nodes and repository-local call/import edges.
- Resolves supported named/module import aliases conservatively.
- Partitions the graph and exports scoped symbol snippets with boundary metadata.
- Provides a heuristic static source-to-sink baseline (`--engine static`).
- Optionally invokes a Hugging Face causal LM or PEFT adapter (`--engine model`).
- Supports a combined static + SLM mode (`--engine hybrid`).
- Reconciles duplicate findings and reports cross-partition graph paths.
- Includes a starter LoRA training script and Kaggle notebook for Qwen2.5-Coder-1.5B-Instruct.

## Quick start (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Run a static baseline against a repository:

```powershell
python main.py PATH_TO_REPOSITORY --engine static
```

Export partition contexts for inspection or external processing:

```powershell
python main.py PATH_TO_REPOSITORY --export
```

Optional model inference requires additional packages and model weights:

```powershell
python -m pip install -r requirements-model.txt
python main.py PATH_TO_REPOSITORY --engine model --model-id Qwen/Qwen2.5-Coder-1.5B-Instruct
```

Use `--adapter PATH` to load a LoRA adapter; add `--load-in-4bit` only on a compatible Linux/CUDA environment. For fine-tuning, follow [KAGGLE_FINETUNING.md](KAGGLE_FINETUNING.md).

## Validation

Run the test suite with `python -m unittest discover -s tests -v`. Tests that require the optional Tree-sitter language pack are skipped when it is not installed. The suite validates components and synthetic cases, not real-world detection quality.

## Research and safety limitations

This is not yet a production security scanner. The static analyzer is heuristic, the SLM can produce false positives/negatives, and cross-function/cross-language taint propagation is incomplete. Treat all findings as candidates for manual review. The included synthetic dataset is a smoke-test fixture, not an adequate training or benchmark dataset. See [KAGGLE_FINETUNING.md](KAGGLE_FINETUNING.md) for the data and evaluation requirements.
