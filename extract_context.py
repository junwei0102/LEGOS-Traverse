#!/usr/bin/env python3
"""
Script to extract system agent, interacting agent, user, time, and location cues from case study context.
Uses OpenAI API to analyze text and identify concise properties for later augmentation steps.
Outputs are intentionally general (role/domain level); include exactly one system agent (e.g., DAISY), plus interacting agents, users, locations, and time.
"""

import os
import sys
import json
import argparse
from typing import List, Dict, Any, Optional
import openai
from openai import OpenAI

# Initialize OpenAI client
client = None

def initialize_openai(api_key: Optional[str] = None):
    """Initialize OpenAI client using an explicit key or the OPENAI_API_KEY environment variable."""
    global client
    resolved_key = api_key or os.getenv('OPENAI_API_KEY')
    if not resolved_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    client = OpenAI(api_key=resolved_key)

def create_extraction_prompt(context: str) -> str:
    """Create the prompt for extracting system agent, interacting agent, user, location, and time properties."""
    prompt = f"""**Task**  
Given a case study describing a system, identify generalized **SystemAgent**, **InteractingAgent**, **User**, **Location**, and **Time** elements. Keep them broad (role/domain level) instead of situationally specific. Skip generic "environment" labels and ignore fine-grained subtypes of the same role.

The analysis should help clarify:
- **SystemAgent**: The primary robot/assistant. Provide exactly ONE system agent entry.
- **InteractingAgent**: Human or system roles that actively collaborate with or command the system (e.g., nurse, doctor, dispatcher).
- **User**: Beneficiaries or parties impacted by the system’s behaviour (e.g., patient, visitor).
- **Location**: Physical areas (e.g., triage station, waiting room).
- **Time**: Wall-clock cues relevant to the workflow. Express as HH:MM (approximate is fine) with a short label (e.g., "08:00 check-in"). Provide one or two plausible scenario starting times if none are explicit.

---

**Phrase to reuse**  
Replace only the bracketed text with your property:  
> [Property description] is a relevant [category] element.

**Example:**  
> [DAISY triage robot] is a relevant [SystemAgent] element.  
> [Nurses and doctors] is a relevant [InteractingAgent] element.  
> [Patients waiting for triage] is a relevant [User] element.  
> [The robot moves to the triage station] is a relevant [Location] element.  
> [08:00 morning intake] is a relevant [Time] element.

---

**Quality guidance**  
- Be specific and contextually grounded.
- Extract distinct entities and avoid multiple entries for the same role; keep one per role.
- Make descriptions short and general (role-level), not incident-level.
- For Time, provide wall-clock style markers (HH:MM) with a short label, not durations. Include up to two candidate start times that fit the context.
- Provide a short `term` that summarizes the description in one word (e.g., "patient", "triage", "0800").

---

## **Metadata to include for each instance**  

- `description`: the property or entity description (no brackets)  
 - `category`: one of `"system_agent"`, `"interacting_agent"`, `"user"`, `"location"`, `"time"`
 - `isDirect`: `true` if it is explicitly stated in the case study, `false` if inferred  
 - `term`: a single word or short token summarizing the description (lowercase preferred)

---

**Output template**  
{{
  "description": "<property>",
  "category": "<system_agent|interacting_agent|user|location|time>",
  "isDirect": <true|false>,
  "term": "<short_token>"
}}

---

**Case Study Context:**
{context}

---

**Instructions:**
1. Carefully read the case study context
2. Identify the system agent plus all relevant InteractingAgent, User, Location, and Time elements. Avoid vague environment labels. Only one SystemAgent entry.
3. For each identified property, create a JSON object following the output template. Keep users generalized (e.g., "Patients" not "patients in critical condition").
4. Return ONLY a JSON array containing all the property objects.
5. Do not include any explanation or text outside the JSON array.

Example output format:
[
  {{
    "description": "DAISY triage robot",
    "category": "system_agent",
    "isDirect": true,
    "term": "daisy"
  }},
  {{
    "description": "Nurses and doctors coordinating handoff",
    "category": "interacting_agent",
    "isDirect": true,
    "term": "nurse-doctor"
  }},
  {{
    "description": "Patients awaiting triage",
    "category": "user",
    "isDirect": true,
    "term": "patient"
  }},
  {{
    "description": "Triage station",
    "category": "location",
    "isDirect": true,
    "term": "triage"
  }},
  {{
    "description": "08:00 check-in",
    "category": "time",
    "isDirect": true,
    "term": "0800"
  }}
]
"""
    return prompt

def extract_properties(context: str) -> List[Dict[str, Any]]:
    """Extract properties from the given context using OpenAI."""
    if not client:
        initialize_openai()
    
    prompt = create_extraction_prompt(context)
    
    try:
        response = client.chat.completions.create(
            model="gpt-5.1-2025-11-13",
            messages=[
                {"role": "system", "content": "You are an expert at analyzing case studies and extracting structured information about system agents, interacting agents, users, locations, and time-related constraints."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_completion_tokens=2000
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Parse JSON response
        try:
            properties = json.loads(result_text)
            if not isinstance(properties, list):
                raise ValueError("Response is not a JSON array")
            properties = _dedupe_system_agent(properties)
            return properties
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {e}", file=sys.stderr)
            print(f"Raw response: {result_text}", file=sys.stderr)
            return []
            
    except Exception as e:
        print(f"Error calling OpenAI API: {e}", file=sys.stderr)
        return []


def _dedupe_system_agent(properties: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure only one system agent entry is kept (first wins)."""
    seen_system = False
    deduped: List[Dict[str, Any]] = []
    for prop in properties:
        if prop.get("category") == "system_agent":
            if seen_system:
                continue
            seen_system = True
        deduped.append(prop)
    return deduped

def validate_property(prop: Dict[str, Any]) -> bool:
    """Validate that a property object has the correct structure and values."""
    required_fields = ["description", "category", "isDirect", "term"]
    
    # Check required fields
    for field in required_fields:
        if field not in prop:
            return False
    
    # Validate types
    if not isinstance(prop["description"], str):
        return False
    if not isinstance(prop["category"], str):
        return False
    if not isinstance(prop["isDirect"], bool):
        return False
    if not isinstance(prop["term"], str) or not prop["term"].strip():
        return False
    
    # Validate category values
    valid_categories = ["system_agent", "interacting_agent", "user", "location", "time"]
    
    if prop["category"] not in valid_categories:
        return False

    # Encourage compact term (one to three tokens)
    token_count = len(prop["term"].strip().split())
    if token_count == 0 or token_count > 3:
        return False

    # Keep descriptions general (not empty, not excessively long)
    if len(prop["description"].split()) > 12:
        return False

    # Time entries should include a wall-clock marker (HH:MM)
    if prop["category"] == "time" and ":" not in prop["description"]:
        return False
    
    return True

def format_output(properties: List[Dict[str, Any]], format_type: str = "json") -> str:
    """Format the extracted properties for output."""
    if format_type == "json":
        return json.dumps(properties, indent=2)
    elif format_type == "readable":
        output = []
        
        categories = ["system_agent", "interacting_agent", "user", "location", "time"]
        
        for category in categories:
            category_props = [p for p in properties if p["category"] == category]
            if category_props:
                heading = category.replace("_", " ").title()
                output.append(f"## {heading}\n")
                for prop in category_props:
                    direct = "Explicitly stated" if prop["isDirect"] else "Inferred"
                    output.append(f"- [{prop['description']}] (term: {prop.get('term', '').strip() or 'n/a'})")
                    output.append(f"  {direct}\n")
        
        return "\n".join(output)
    else:
        return json.dumps(properties, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description='Extract system agent, interacting agent, user, location, and time properties from case study context'
    )
    parser.add_argument('input', help='Input file containing the case study context (use "-" for stdin)')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)', default='-')
    parser.add_argument('--format', '-f', choices=['json', 'readable'], default='json',
                       help='Output format (default: json)')
    parser.add_argument('--validate', action='store_true', help='Validate extracted properties')
    parser.add_argument('--api-key', help='OpenAI API key (optional, defaults to OPENAI_API_KEY env var)')
    
    args = parser.parse_args()
    
    # Initialize OpenAI
    try:
        initialize_openai(args.api_key)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Read input
    if args.input == '-':
        context = sys.stdin.read()
    else:
        try:
            with open(args.input, 'r') as f:
                context = f.read()
        except IOError as e:
            print(f"Error reading input file: {e}", file=sys.stderr)
            sys.exit(1)
    
    if not context.strip():
        print("Error: Empty input context", file=sys.stderr)
        sys.exit(1)
    
    # Extract properties
    print("Extracting properties from context...", file=sys.stderr)
    properties = extract_properties(context)
    
    if not properties:
        print("No properties extracted", file=sys.stderr)
        sys.exit(1)
    
    # Validate if requested
    if args.validate:
        valid_props = []
        for prop in properties:
            if validate_property(prop):
                valid_props.append(prop)
            else:
                print(f"Warning: Invalid property skipped: {prop}", file=sys.stderr)
        properties = valid_props
    
    # Format output
    output = format_output(properties, args.format)
    
    # Write output
    if args.output == '-':
        print(output)
    else:
        try:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"Output written to {args.output}", file=sys.stderr)
        except IOError as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
