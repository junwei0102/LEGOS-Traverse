# LEGOS-TRAVERSE

Lightweight tooling for generating LTS traces with the LEGOs stack and probing augmentation strategies over those traces. The repository now focuses purely on backend logic—no Streamlit or UI layer.

## Quick Start
```bash
conda env create -f environment.yml
conda activate legos-traverse

# Augment an existing LTS
python run_augmentation.py input_lts.aut --mode domain --api-key <KEY>
```

## Core Modules
- `legos_integration.py` – Thin wrapper around LEGOs’ parser utilities for producing traces.
- `augmentation/`
  - `config.py` – Defines the augmentation modes (`domain-only`, `fixed extra dimensions`, `context-enriched`).
  - `prompt_builder.py` – Builds model prompts according to the selected mode.
  - `llm.py` – Minimal OpenAI/DeepSeek chat completion wrapper.
  - `response_parser.py` – Splits the model response into LTS, mapping, and scene summary.
  - `io_utils.py` – Helpers for loading the source LTS and saving augmentation artefacts.
- `run_augmentation.py` – CLI entry-point for running augmentation experiments.
- `extract_context.py`, `extract_sleec_properties.py`, `extract_combined_properties.py` – Optional scripts for mining contextual properties from case studies or SLEEC rules (no UI dependencies).

## Augmentation Workflow
1. Start from an LTS (e.g., `input_lts.aut`) generated via LEGOs or your own tooling.
2. Choose an augmentation mode via the CLI:
   - `domain` – stay strictly within the existing event/measure universe.
   - `dimensions` – allow a fixed set of extra contextual dimensions (time/weather/location/etc.).
   - `context` – ground the augmentation with external domain text (e.g., `DAISY.txt`).
3. Review the generated artefacts in the selected output directory:
   - `l1.aut` – original LTS
   - `l2.aut` – augmented LTS
   - `rename.ren` – mapping between augmented and original transitions
   - `augment_scene.txt` – concise scene timeline
   - `augmented_response.txt` – raw model response

## API Keys
Provide your `OPENAI_API_KEY` (or pass the key via `--api-key`). DeepSeek users must also set `--base-url`.

## License
MIT – see `LICENSE`.
