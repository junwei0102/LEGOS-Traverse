import os
import sys
import argparse
from pathlib import Path
from typing import List, Optional

_PARSE_AND_MAX_TRACE = None


def _load_legos_parser():
    """
    Import LEGOs' sleecParser lazily.

    This keeps `import legos_integration` working in environments that haven't
    installed LEGOs' heavier dependencies (e.g., pysmt), while still providing
    a clear error when the CLI is used without them.
    """
    global _PARSE_AND_MAX_TRACE
    if _PARSE_AND_MAX_TRACE is not None:
        return _PARSE_AND_MAX_TRACE

    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.append(current_dir)

    analyzer_path = os.path.join(current_dir, "LEGOs", "Analyzer")
    sleec_path = os.path.join(current_dir, "LEGOs", "Sleec")
    for path in (analyzer_path, sleec_path):
        if path not in sys.path:
            sys.path.append(path)

    _original_cwd = os.getcwd()
    try:
        os.chdir(sleec_path)
        try:
            from LEGOs.Sleec.sleecParser import parse_and_max_trace  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "LEGOs dependencies are not installed (missing module). "
                "Use the provided conda/venv environment for LEGOs to run this script."
            ) from exc
    finally:
        os.chdir(_original_cwd)

    _PARSE_AND_MAX_TRACE = parse_and_max_trace
    return _PARSE_AND_MAX_TRACE

def run_sleec_parser(
    sleec_file: str,
    time_window: int = 600,
    rule_ids: Optional[List[str]] = None,
) -> str:
    """
    Run LEGOs' SLEEC parser to generate a raw trace string.
    
    Args:
        sleec_file: path of SLEEC file
        time_window: time window size (seconds)
        rule_ids: optional subset of rule IDs to target
        
    Returns:
        Raw trace string (lines like `at time X: Event()` and `Measure(...)`).
    """
    try:
        target_rules = rule_ids if rule_ids is not None else []
        parse_and_max_trace = _load_legos_parser()
        output = parse_and_max_trace(sleec_file, target_rules, tracetime=time_window)
        if not isinstance(output, str):
            raise TypeError(f"Expected trace string from LEGOs, got {type(output).__name__}")
        return output
        
    except Exception as e:
        print(f"Error running LEGOS parser: {str(e)}")
        return ""


def main():
    parser = argparse.ArgumentParser(description="Generate raw traces from SLEEC files using LEGOs.")
    parser.add_argument("--sleec", required=True, help="Path to the SLEEC file (e.g., examples/DAISY.sleec).")
    parser.add_argument("--time-window", type=int, default=15, help="Trace time window (default: 15).")
    parser.add_argument(
        "--rules",
        nargs="+",
        help="Optional list of rule IDs to target; defaults to letting LEGOs decide.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Path to save the generated trace (default: traces/<domain>_<rules>_<time>.txt). "
            "Note: LEGOs may also save its own copy under traces/."
        ),
    )
    args = parser.parse_args()

    print(f"[LEGOs] Generating trace for {args.sleec} (time window={args.time_window})...")
    trace_text = run_sleec_parser(args.sleec, args.time_window, args.rules)
    if not trace_text.strip():
        raise SystemExit("Failed to generate trace via LEGOs parser.")

    output_path = args.output
    if output_path is None:
        domain = Path(args.sleec).stem or Path(args.sleec).name
        rule_part = "-".join(args.rules) if args.rules else "ALL"
        output_path = Path("traces") / f"{domain}_{rule_part}_{args.time_window}.txt"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(trace_text, encoding="utf-8")

    print(f"[LEGOs] Trace saved to {output_path}")


if __name__ == "__main__":
    main()
