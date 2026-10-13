# ClusterSLM: Kaggle LoRA fine-tuning handoff

## What is included

- `train_lora.py`: QLoRA/LoRA fine-tuning entry point for chat-formatted JSONL.
- `requirements-kaggle.txt`: optional Linux/GPU training dependencies.
- `model_worker.py`: optional Transformers inference worker; supports a base model or a saved PEFT adapter.
- `dataset_builder.py`: creates a small deterministic synthetic smoke-test dataset under `data/synthetic/`.
- `evaluate.py`: exact `(symbol, CWE)` precision/recall/F1 calculator for labeled JSON findings.

## Important research warning

The generated dataset is **synthetic starter data only**. It is useful to check that data loading, chat formatting, training, adapter saving, and inference plumbing work. It is not enough to produce a trustworthy vulnerability detector or a publishable evaluation. Before claiming detection performance, create a reviewed dataset with real, licensed code examples, realistic safe/vulnerable pairs, repository-level splits, and ground-truth labels verified by a human. Keep train/test projects separate to prevent leakage.

## A. Prepare a starter dataset locally

From the project root (Windows PowerShell or Linux):

```bash
python dataset_builder.py
```

This creates:

- `data/synthetic/train.jsonl`
- `data/synthetic/test.jsonl`
- `data/synthetic/dataset_metadata.json`

The JSONL rows use a `messages` array (`system`, `user`, `assistant`) and are compatible with `train_lora.py`.

## B. Prepare Kaggle

1. Create a Kaggle Notebook and turn **GPU** on in Notebook settings.
2. Enable Internet only if your Kaggle account/session permits it and you need to download the base model/packages.
3. Upload this project ZIP as a Kaggle Dataset, or attach the extracted project files to the notebook.
4. Create a second Kaggle Dataset containing `train.jsonl` and `test.jsonl`. Start with the generated synthetic data only to validate the workflow; replace it with reviewed data before real experiments.
5. Add both datasets to the notebook through **Add Input**.
6. Open `Kaggle_ClusterSLM_Qwen_LoRA.ipynb` from this project, attach the two inputs, and run the cells in order. The discovery cell prints which paths it found. If it cannot find a file, edit the two path variables in that cell to the exact paths under `/kaggle/input/`.

The notebook fine-tunes `Qwen/Qwen2.5-Coder-1.5B-Instruct` with a LoRA adapter and saves the adapter under `/kaggle/working/clusterslm-qwen-lora`. Download the notebook output before the session expires. This is an adapter checkpoint, not a full merged model; retain the base model ID with it.

## C. Use the trained adapter locally

After downloading and extracting the adapter folder, install the optional inference dependencies in your project environment:

```powershell
python -m pip install -r requirements-model.txt
```

Run the real model worker with the adapter path:

```powershell
python main.py PATH_TO_REPOSITORY --engine model --model-id Qwen/Qwen2.5-Coder-1.5B-Instruct --adapter PATH_TO_EXTRACTED_ADAPTER --load-in-4bit
```

On Windows, 4-bit loading may not be supported by your exact PyTorch/bitsandbytes/CUDA setup. If it fails, omit `--load-in-4bit` or run inference in Kaggle/Linux. The model worker is optional; the normal test suite does not download a model.

For a first static baseline, use:

```powershell
python main.py PATH_TO_REPOSITORY --engine static
```

For combined static + model suggestions:

```powershell
python main.py PATH_TO_REPOSITORY --engine hybrid --model-id Qwen/Qwen2.5-Coder-1.5B-Instruct --adapter PATH_TO_EXTRACTED_ADAPTER --load-in-4bit
```

## D. Evaluate against labeled findings

Prepare two JSON files. Each can be a top-level list of findings or a report object with a `findings` list. Each finding should have `symbol` and `cwe` fields.

```bash
python evaluate.py --predicted clusterslm_report.json --gold path/to/gold_findings.json
```

The evaluator matches exact `(symbol, CWE)` pairs and reports precision, recall, and F1. This first evaluator is intentionally simple; it does not yet score line-level localization, severity, or cross-language taint paths.

## Current limitations

- Python and JavaScript/TypeScript have structural parser adapters; other recognized extensions are detection-only.
- Import-aware symbol resolution is static and incomplete; it is not a full compiler/type resolver.
- The static engine is a rule-based heuristic baseline. It can miss issues and produce false positives; it is not a sound or complete taint engine.
- The SLM can hallucinate. Findings are marked `needs_review`; always validate evidence before acting on a report.
- Boundary-aware reconciliation traces graph connectivity but does not yet prove data propagation through values across functions/languages.
- Training on tiny synthetic data can teach templates rather than general security reasoning. Do not use synthetic test metrics as real-world performance claims.
