import argparse
import re
from pathlib import Path


RULE_START_PATTERN = re.compile(r"^\s*(\S+)\s+when\b")


def measures_for_rules(sleec_text: str, targets: set[str]) -> set[str]:
    """
    Return measure names referenced by the selected rules.

    Rules are identified by the token immediately preceding the `when` keyword,
    e.g. `Rule1 when ...` or `R3 when ...`.
    """
    captured: dict[str, list[str]] = {rule: [] for rule in targets}
    current: str | None = None

    for line in sleec_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        match = RULE_START_PATTERN.match(line)
        if match:
            name = match.group(1)
            current = name if name in captured else None
            if current:
                captured[current] = [line]
            continue

        if current:
            # Continue capturing until the next rule begins.
            captured[current].append(line)

    missing = [rule for rule, lines in captured.items() if not lines]
    if missing:
        raise ValueError(f"missing rule(s): {', '.join(missing)}")

    pattern = re.compile(r"\{([^}]+)\}")
    measures: set[str] = set()
    for lines in captured.values():
        measures.update(pattern.findall(" ".join(lines)))
    return measures


def main():
    parser = argparse.ArgumentParser(description="Keep only measures used by selected rules.")
    parser.add_argument("traces")
    parser.add_argument("sleec")
    parser.add_argument("--rules", nargs="+", required=True)
    args = parser.parse_args()

    targets = {rule for rule in args.rules}
    try:
        measures = measures_for_rules(Path(args.sleec).read_text(), targets)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    trace_path = Path(args.traces)
    output_path = trace_path.with_name(f"clean_{trace_path.name}")
    lines_out = []
    for line in trace_path.read_text().splitlines():
        if "Measure(" not in line:
            lines_out.append(line)
            continue
        prefix, rest = line.split("Measure(", 1)
        body, suffix = rest.split(")", 1)
        kept = []
        for chunk in body.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            name = chunk.split("=", 1)[0].strip()
            if name in measures:
                kept.append(chunk)
        lines_out.append(f"{prefix}Measure({', '.join(kept)}){suffix}")

    output_path.write_text("\n".join(lines_out) + "\n")
    print(f"clean trace written to {output_path}")


if __name__ == "__main__":
    main()
