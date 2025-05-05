# SLEEC Rules Analysis Pipeline

A pipeline for analyzing SLEEC rules, extracting insights, and generating traces that trigger specific rules.

## Directory Structure

```
.
├── data/                  # Data directory
│   ├── rules/             # SLEEC rule files
│   └── output/            # Output directory
│       ├── traces/        # Generated trace files
│       └── lts/           # LTS (Labeled Transition System) files
├── src/                   # Source code
│   ├── pipeline.py        # Main Streamlit application
│   ├── translator.py      # Trace to LTS translator
│   ├── rules.py           # Rule extraction and analysis
│   └── legos_integration.py  # Integration with LEGOs
├── LEGOs/                 # LEGOs library (submodule)
├── requirements.txt       # Project dependencies
└── run_app.py             # Entry point to run the application
```

## Installation

1. Clone the repository with submodules:
   ```
   git clone --recursive <repository-url>
   cd <repository-directory>
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

Run the application:
```
python run_app.py
```

This will start the Streamlit web interface where you can:
1. Upload or enter SLEEC rules
2. Analyze rules based on different criteria:
   - Shared responses
   - Mutually exclusive responses
   - Shared measures
3. Generate traces that trigger selected rules
4. View and download generated traces and LTS files

## Generating Traces for Specific Rules

You can generate traces that trigger specific rules using the command line:

```
python -m src.legos_integration --filename data/rules/your_rules.sleec --analysis max --tracetime 15 --IDs rule1_id rule2_id
```

Where:
- `your_rules.sleec` is your SLEEC rules file
- `15` is the time window in seconds
- `rule1_id rule2_id` are the IDs of the rules you want to trigger

## License

This project is licensed under the MIT License - see the LICENSE file for details. 