# SLEEC Rules Analysis Pipeline

A pipeline for analyzing SLEEC rules and generating traces that trigger rules.

## Directory Structure

The project has been organized into the following structure:

```
.
├── data/
│   ├── rules/           # SLEEC rule files
│   ├── examples/        # Example SLEEC files
│   └── output/
│       ├── traces/      # Generated traces
│       └── lts/         # LTS (Labeled Transition System) files
├── LEGOs/               # LEGOS library
├── src/                 # Source code
│   ├── pipeline.py      # Main Streamlit application
│   ├── translator.py    # Trace to LTS translator
│   ├── rules.py         # Rules extraction and analysis
│   ├── legos_integration.py # Integration with LEGOs
│   ├── augment.py       # Augmentation tool
│   └── test_translator.py # Tests
└── run_app.py           # Script to run the application
```

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/sleec-rules-pipeline.git
   cd sleec-rules-pipeline
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

Run the application with:
```
./run_app.py
```
or
```
python run_app.py
```

This will start the Streamlit web interface where you can:
1. Upload or enter SLEEC rules
2. Analyze rules by different criteria (shared responses, mutually exclusive responses, shared measures)
3. Generate traces that trigger selected rules
4. Convert traces to LTS format

## Running the Trace Generator

The tool can generate traces that trigger specific rules with the command:

```
python -m src.legos_integration <sleec_file> <time_window> [rule_ids...]
```

Example:
```
python -m src.legos_integration data/rules/example.sleec 15 r2_1 r1_prime
```

This will generate a trace that triggers rules with IDs r2_1 and r1_prime within 15 seconds.

## Features
- **Rule Analysis**: Supports analysis of shared responses, mutually exclusive responses, and shared measures.
- **LTS Generation**: Generates LTS format transitions from SLEEC files.
- **Image Augmentation**: Processes images and scene labels through `augment.py`.

## API Requirements
- **OpenAI API**: Required for generating user-friendly descriptions and other functionalities.
- **DeepSeek API**: Utilized for specific data processing tasks.
- **FAL Model API**: Used for scene generation and evaluation.

## Dependencies
- **LEGOs Repository**: This project depends on the LEGOs library. Please refer to the [LEGOs GitHub repository](https://github.com/NickF0211/LEGOs) for more information and setup instructions.

## Contribution
Contributions are welcome! Please submit a Pull Request or report issues.

## License
This project is licensed under the MIT License.

## Contact
For any questions, please contact junwei.quan@mail.utoronto.ca
