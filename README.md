# Project Name

## Introduction
This project aims to analyze and process rules using the SLEEC rules analysis and LTS generation pipeline. It includes multiple modules and functionalities to support rule parsing, analysis, defining mutual exclusivity, and generating LTS format transitions.

## Directory Structure
- `augment.py`: Handles image augmentation and scene label processing.
- `rules.py`: Provides functions for extracting and analyzing rules.
- `translator.py`: Extracts measures and event mappings from rules.
- `pipeline.py`: Implements the SLEEC rules analysis and LTS generation pipeline.
- `legos_integration.py`: Integrates the LEGOs library to parse SLEEC files and generate traces.
- `LEGOs/`: Contains related files and modules for the LEGOs library.

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/junwei0102/LEGOS-Traverse.git
   cd LEGOS-Traverse
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
1. Start the Streamlit application:
   ```bash
   streamlit run pipeline.py
   ```

2. Open the Streamlit app in your browser, choose the input method, and perform rule analysis.

3. The generated LTS file will be saved as `input_lts.aut`.

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
For any questions, please contact [your email].
