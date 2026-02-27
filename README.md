# Supplementary material for:
# From Rules to Scenarios: Validating Normative Requirements via Contextualised Textual Scenarios

## This repo contains:
- The SLEEC-TRAVERSE approach for generating abstract plan and augmenting them into scene timelines.
- Context extraction tooling for building a fixed measure domain from background text.
- Sample assets (SLEEC domains, background contexts, traces, and augmentation outputs).

# Instruction for running the pipeline:
### prerequisite:
1. Python 3.10 and later
2. `pip install -r requirements.txt`
3. SLEEC-TRAVERSE abstract plan generation uses additional dependencies (pysmt, z3-solver, textx, ordered-set). Follow the existing state-of-the-art LEGOs tool folder README.md for instruction. With this, you could run `legos_integration.py`

### Run the pipeline
Generate a abstract plan from SLEEC:
```bash
python legos_integration.py \
  --sleec domains/DAISY.sleec \
  --time-window 600 \
  --output traces/DAISY_ALL_600.txt
```

Extract the measure domain from background context:
```bash
OPENAI_API_KEY=... python extract_context.py \
  backgrounds/DAISY.txt \
  --output extractions/DAISY.json
```

Augment the abstract plan with the extracted measure domain:
```bash
OPENAI_API_KEY=... python run_augmentation.py \
  traces/DAISY_ALL_600.txt \
  --measure-domain extractions/DAISY.json \
  --output-dir augments/demo
```

Outputs (under the chosen output dir):
- `augment_scene.txt` - natural-language scene timeline with CLOCK annotations
- `legos_augment_trace.txt` - Abstract plan with original events plus Measure(...)

### Utilities
Only keep mutual-exclusive pairs where both sides appear in rules:
```bash
python rules.py domains/ALMI.sleec mutual-exclusive --require-both
```

Filter measures in an abstracy plan to those used by a rule subset:
```bash
python clean.py traces/DAISY_ALL_600.txt domains/DAISY.sleec --rules R1 R4
```

### Sample assets
Please find here the core inputs used in the pipeline:

1. [ALMI background](backgrounds/ALMI.txt) and [SLEEC](domains/ALMI.sleec)
2. [ASPEN background](backgrounds/ASPEN.txt) and [SLEEC](domains/ASPEN.sleec)
3. [DAISY background](backgrounds/DAISY.txt) and [SLEEC](domains/DAISY.sleec)

### Repo layout
- `domains/` - SLEEC specs
- `backgrounds/` - natural-language context files
- `traces/` - SLEEC-TRAVERSE abstract plan (generated using existing LEGOS tool)
- `augments/` - augmentation outputs
- `extractions/` - context extraction outputs
- `LEGOs/` - vendored upstream LEGOs toolkit

### API keys
Set `OPENAI_API_KEY` or pass `--api-key` for scripts that call OpenAI.
Do not commit keys.

### Acknowledgement
This repository uses the existing state-of-the-art tool [LEGOs](https://github.com/NickF0211/LEGOs/tree/master) codebase.
