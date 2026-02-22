#!/usr/bin/env python3
"""
Minimal CLI utilities for extracting rule subsets from a SLEEC file.

Supported modes:
  - shared-responses: rules that share the same response event (then/unless-then)
  - shared-measures: rules that reference specific measures (by {measure} name)
  - mutual-exclusive: rules whose responses are declared mutuallyExclusive in the file
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


_RULE_START_RE = re.compile(r"^\s*(\S+)\s+when\b", re.IGNORECASE)
_MUTUAL_EXCLUSIVE_RE = re.compile(r"^\s*mutualExclusive\s+(\S+)\s+(\S+)\s*$", re.IGNORECASE)
_RESPONSE_RE = re.compile(r"\bthen\s+((?:not\s+)?[A-Za-z_]\w*)\b", re.IGNORECASE)
_MEASURE_REF_RE = re.compile(r"(?P<neg>\bnot\s*)?\{(?P<name>[^}]+)\}", re.IGNORECASE)
_DEFAULT_OUTPUT_ROOT = Path("rules")


@dataclass(frozen=True)
class Rule:
    rule_id: str
    text: str
    responses: Tuple[str, ...]
    measures: Tuple[str, ...]


@dataclass(frozen=True)
class SleecDocument:
    original_text: str
    def_block: str
    rules: Tuple[Rule, ...]
    mutual_exclusive_pairs: Tuple[Tuple[str, str], ...]


def _strip_comment_lines(text: str) -> str:
    lines: List[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("//"):
            continue
        lines.append(raw)
    return "\n".join(lines)


def _find_block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        return ""
    end = text.find(end_marker, start + len(start_marker))
    if end == -1:
        return ""
    return text[start : end + len(end_marker)]


def _extract_between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        return ""
    start += len(start_marker)
    end = text.find(end_marker, start)
    if end == -1:
        return ""
    return text[start:end]


def _extract_def_block(original_text: str) -> str:
    block = _find_block(original_text, "def_start", "def_end")
    if block:
        return block.strip() + "\n"
    return ""


def _extract_rule_region(original_text: str) -> str:
    region = _extract_between(original_text, "rule_start", "rule_end")
    if region:
        return region
    return original_text


def _extract_relation_region(original_text: str) -> str:
    region = _extract_between(original_text, "relation_start", "relation_end")
    return region


def _parse_mutual_exclusive_pairs(original_text: str) -> List[Tuple[str, str]]:
    region = _extract_relation_region(original_text)
    if not region.strip():
        return []

    pairs: List[Tuple[str, str]] = []
    for raw in region.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        match = _MUTUAL_EXCLUSIVE_RE.match(line)
        if not match:
            continue
        a, b = match.group(1).strip(), match.group(2).strip()
        if a and b:
            pairs.append((a, b))
    return pairs


def _parse_rules(original_text: str) -> List[Rule]:
    region = _extract_rule_region(original_text)
    lines = region.splitlines()

    rules: List[Rule] = []
    current_id: Optional[str] = None
    current_lines: List[str] = []

    def flush() -> None:
        nonlocal current_id, current_lines
        if not current_id:
            current_lines = []
            return
        rule_text = "\n".join(current_lines).strip()
        cleaned = _strip_comment_lines(rule_text)
        normalized = " ".join(cleaned.split())
        responses = tuple(dict.fromkeys(_RESPONSE_RE.findall(normalized)))
        measures_found: Set[str] = set()
        for match in _MEASURE_REF_RE.finditer(normalized):
            name = (match.group("name") or "").strip()
            if not name:
                continue
            is_negated = bool(match.group("neg"))
            token = f"not_{name}" if is_negated else name
            measures_found.add(token)
        measures = tuple(sorted(measures_found))
        rules.append(Rule(rule_id=current_id, text=rule_text + "\n", responses=responses, measures=measures))
        current_id = None
        current_lines = []

    for raw in lines:
        match = _RULE_START_RE.match(raw)
        if match:
            flush()
            current_id = match.group(1).strip()
            current_lines = [raw.rstrip()]
            continue

        if current_id is not None:
            current_lines.append(raw.rstrip())

    flush()
    return rules


def load_sleec(path: Path) -> SleecDocument:
    text = path.read_text(encoding="utf-8")
    return SleecDocument(
        original_text=text,
        def_block=_extract_def_block(text),
        rules=tuple(_parse_rules(text)),
        mutual_exclusive_pairs=tuple(_parse_mutual_exclusive_pairs(text)),
    )


def group_rules_by_response(rules: Sequence[Rule]) -> Dict[str, List[Rule]]:
    grouped: Dict[str, List[Rule]] = {}
    for rule in rules:
        for response in rule.responses:
            grouped.setdefault(response, []).append(rule)
    return grouped


def group_rules_by_measure(rules: Sequence[Rule]) -> Dict[str, List[Rule]]:
    grouped: Dict[str, List[Rule]] = {}
    for rule in rules:
        for measure in rule.measures:
            grouped.setdefault(measure, []).append(rule)
    return grouped


def filter_shared_responses(
    rules: Sequence[Rule],
    *,
    min_count: int = 2,
) -> Dict[str, List[Rule]]:
    grouped = group_rules_by_response(rules)
    return {resp: lst for resp, lst in grouped.items() if len(lst) >= min_count}


def filter_shared_measures(
    rules: Sequence[Rule],
    *,
    min_count: int = 2,
) -> Dict[str, List[Rule]]:
    grouped = group_rules_by_measure(rules)
    return {measure: lst for measure, lst in grouped.items() if len(lst) >= min_count}


def filter_rules_by_measures(
    rules: Sequence[Rule],
    target_measures: Sequence[str],
    *,
    match: str = "all",
) -> List[Rule]:
    targets = [m.strip() for m in target_measures if m.strip()]
    if not targets:
        raise ValueError("No measures provided.")

    match = match.lower()
    if match not in {"all", "any"}:
        raise ValueError("match must be 'all' or 'any'.")

    selected: List[Rule] = []
    target_set = {m.lower() for m in targets}
    for rule in rules:
        rule_measures = {m.lower() for m in rule.measures}
        if match == "all":
            ok = target_set.issubset(rule_measures)
        else:
            ok = bool(target_set.intersection(rule_measures))
        if ok:
            selected.append(rule)
    return selected


def extract_mutual_exclusive_groups(
    rules: Sequence[Rule],
    pairs: Sequence[Tuple[str, str]],
) -> List[Tuple[Tuple[str, str], List[Rule], List[Rule]]]:
    by_response = group_rules_by_response(rules)
    groups: List[Tuple[Tuple[str, str], List[Rule], List[Rule]]] = []
    for a, b in pairs:
        rules_a = list(by_response.get(a, []))
        rules_b = list(by_response.get(b, []))
        if not rules_a and not rules_b:
            continue

        a_ids = {r.rule_id for r in rules_a}
        b_ids = {r.rule_id for r in rules_b}
        overlap = a_ids.intersection(b_ids)
        if overlap:
            rules_a = [r for r in rules_a if r.rule_id not in overlap]
            rules_b = [r for r in rules_b if r.rule_id not in overlap]

        groups.append(((a, b), rules_a, rules_b))
    return groups


def _format_summary_json_shared_responses(groups: Dict[str, List[Rule]]) -> str:
    payload = {resp: [r.rule_id for r in rules] for resp, rules in sorted(groups.items())}
    return json.dumps(payload, indent=2, sort_keys=True)


def _format_summary_json_mutual_exclusive(
    groups: List[Tuple[Tuple[str, str], List[Rule], List[Rule]]],
) -> str:
    payload = []
    for (a, b), rules_a, rules_b in groups:
        payload.append(
            {
                "pair": [a, b],
                "rules": {a: [r.rule_id for r in rules_a], b: [r.rule_id for r in rules_b]},
            }
        )
    return json.dumps(payload, indent=2)


def _format_summary_json_shared_measures(
    rules: Sequence[Rule],
    targets: Sequence[str],
) -> str:
    target_set = {t.strip().lower() for t in targets if t.strip()}
    payload = []
    for rule in rules:
        rule_measures = {m.lower() for m in rule.measures}
        payload.append(
            {
                "rule_id": rule.rule_id,
                "matched_measures": sorted(rule_measures.intersection(target_set)),
                "all_measures": list(rule.measures),
            }
        )
    return json.dumps(payload, indent=2)


def write_sleec_subset(
    doc: SleecDocument,
    rules_to_keep: Iterable[Rule],
    output_path: Path,
    *,
    header_comments: Optional[Sequence[str]] = None,
    include_relation_block: bool = False,
    relation_pairs: Optional[Sequence[Tuple[str, str]]] = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rules_list = list(rules_to_keep)

    parts: List[str] = []
    if doc.def_block:
        parts.append(doc.def_block.rstrip("\n"))
    parts.append("rule_start")
    if header_comments:
        for line in header_comments:
            parts.append(f"// {line}".rstrip())
    for rule in rules_list:
        parts.append(rule.text.rstrip("\n"))
    parts.append("rule_end")

    if include_relation_block and relation_pairs:
        parts.append("")
        parts.append("relation_start")
        for a, b in relation_pairs:
            parts.append(f"mutualExclusive {a} {b}")
        parts.append("relation_end")

    output_path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")


def default_output_path(input_path: Path, label: str) -> Path:
    """Return the default output path under rules/."""
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", label.strip()) or "output"
    return _DEFAULT_OUTPUT_ROOT / f"{input_path.stem}_{safe}.sleec"


def write_shared_response_groups(
    doc: SleecDocument,
    groups: Dict[str, List[Rule]],
    output_path: Path,
    *,
    min_count: int,
) -> None:
    """Write a combined SLEEC file with response-group comment headers."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    parts: List[str] = []
    if doc.def_block:
        parts.append(doc.def_block.rstrip("\n"))
    parts.append("rule_start")
    parts.append(f"// Shared-responses extraction (min_count={min_count})")

    written: Set[str] = set()
    for response, rules_list in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        parts.append("")
        parts.append(f"// Shared response: {response} ({len(rules_list)} rules)")
        group_written: List[str] = []
        group_skipped: List[str] = []
        for rule in rules_list:
            if rule.rule_id in written:
                group_skipped.append(rule.rule_id)
                continue
            written.add(rule.rule_id)
            group_written.append(rule.rule_id)
            parts.append(rule.text.rstrip("\n"))
        if group_skipped:
            parts.append(f"// (already included above): {', '.join(group_skipped)}")
        if not group_written:
            parts.append("// (no new rules in this group)")

    parts.append("rule_end")
    output_path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")


def write_shared_measure_groups(
    doc: SleecDocument,
    groups: Dict[str, List[Rule]],
    output_path: Path,
    *,
    min_count: int,
) -> None:
    """Write a combined SLEEC file with measure-group comment headers (rules may repeat across groups)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    parts: List[str] = []
    if doc.def_block:
        parts.append(doc.def_block.rstrip("\n"))
    parts.append("rule_start")
    parts.append(f"// Shared-measures extraction (min_count={min_count})")

    for measure, rules_list in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        parts.append("")
        parts.append(f"// Shared measure: {measure} ({len(rules_list)} rules)")
        for rule in rules_list:
            parts.append(rule.text.rstrip("\n"))

    parts.append("rule_end")
    output_path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract rule subsets from a SLEEC file.")
    parser.add_argument("sleec", type=Path, help="Path to input .sleec file.")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Summary output format.")
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Do not write any output files (print summaries only).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    shared = subparsers.add_parser("shared-responses", help="Find rules sharing the same response event.")
    shared.add_argument("--min-count", type=int, default=2, help="Minimum rules per shared-response group.")
    shared.add_argument("--output", type=Path, help="Write selected rules to a new .sleec file.")
    shared.add_argument("--output-dir", type=Path, help="Write one .sleec per response into this directory.")

    measures = subparsers.add_parser("shared-measures", help="Find rules referencing specified measures.")
    measures.add_argument(
        "--measures",
        nargs="+",
        help="Measure names to match (without braces). If omitted, prints all measures shared by >=2 rules.",
    )
    measures.add_argument("--match", choices=["all", "any"], default="all", help="Match rule measures by all/any.")
    measures.add_argument(
        "--min-count",
        type=int,
        default=2,
        help="Minimum rules per shared-measure group (grouping mode only).",
    )
    measures.add_argument("--output", type=Path, help="Write selected rules to a new .sleec file.")
    measures.add_argument("--output-dir", type=Path, help="Write one .sleec per measure into this directory.")

    excl = subparsers.add_parser(
        "mutual-exclusive",
        help="Extract rules participating in mutualExclusive response pairs declared in the file.",
    )
    excl.add_argument("--output", type=Path, help="Write selected rules to a new .sleec file.")
    excl.add_argument("--relations", action=argparse.BooleanOptionalAction, default=True)
    excl.add_argument(
        "--require-both",
        action="store_true",
        help="Only keep pairs where both response groups have at least one rule.",
    )

    return parser.parse_args()


def _print_text_shared_responses(groups: Dict[str, List[Rule]]) -> None:
    if not groups:
        print("(no shared responses found)")
        return
    for resp, rules in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        rule_ids = ", ".join(r.rule_id for r in rules)
        print(f"{resp} ({len(rules)}): {rule_ids}")


def _print_text_shared_measures_groups(groups: Dict[str, List[Rule]]) -> None:
    if not groups:
        print("(no shared measures found)")
        return
    for measure, rules_list in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        rule_ids = ", ".join(r.rule_id for r in rules_list)
        print(f"{measure} ({len(rules_list)}): {rule_ids}")


def _print_text_shared_measures(selected: Sequence[Rule], targets: Sequence[str]) -> None:
    if not selected:
        print("(no matching rules found)")
        return
    target_set = {t.strip().lower() for t in targets if t.strip()}
    for rule in selected:
        matched = [m for m in rule.measures if m.lower() in target_set]
        matched_str = ", ".join(matched) if matched else "(none)"
        print(f"{rule.rule_id}: matched {matched_str}")


def _print_text_mutual_exclusive(groups: List[Tuple[Tuple[str, str], List[Rule], List[Rule]]]) -> None:
    if not groups:
        print("(no mutualExclusive relations found)")
        return
    for (a, b), rules_a, rules_b in groups:
        a_ids = ", ".join(r.rule_id for r in rules_a) if rules_a else "(none)"
        b_ids = ", ".join(r.rule_id for r in rules_b) if rules_b else "(none)"
        print(f"{a} ⟂ {b}")
        print(f"  {a}: {a_ids}")
        print(f"  {b}: {b_ids}")


def main() -> None:
    args = _parse_args()
    doc = load_sleec(args.sleec)

    if args.command == "shared-responses":
        groups = filter_shared_responses(doc.rules, min_count=args.min_count)
        if args.format == "json":
            print(_format_summary_json_shared_responses(groups))
        else:
            _print_text_shared_responses(groups)

        output_path = args.output
        if output_path is None and not args.no_write:
            output_path = default_output_path(args.sleec, "shared_responses")
        if output_path and not args.no_write:
            if groups:
                write_shared_response_groups(doc, groups, output_path, min_count=args.min_count)
            else:
                print("(no matching rules; no file written)")

        if args.output_dir:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            for response, rules in sorted(groups.items()):
                safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", response)
                out_path = args.output_dir / f"shared_response_{safe}.sleec"
                write_sleec_subset(
                    doc,
                    rules,
                    out_path,
                    header_comments=[f"Shared response: {response}", f"rule_count={len(rules)}"],
                )

        return

    if args.command == "shared-measures":
        if args.measures:
            selected = filter_rules_by_measures(doc.rules, args.measures, match=args.match)
            if args.format == "json":
                print(_format_summary_json_shared_measures(selected, args.measures))
            else:
                _print_text_shared_measures(selected, args.measures)

            output_path = args.output
            if output_path is None and not args.no_write:
                output_path = default_output_path(args.sleec, "shared_measures")
            if output_path and not args.no_write:
                if selected:
                    write_sleec_subset(doc, selected, output_path)
                else:
                    print("(no matching rules; no file written)")
            return

        groups = filter_shared_measures(doc.rules, min_count=args.min_count)
        if args.format == "json":
            payload = {m: [r.rule_id for r in lst] for m, lst in sorted(groups.items())}
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            _print_text_shared_measures_groups(groups)

        output_path = args.output
        if output_path is None and not args.no_write:
            output_path = default_output_path(args.sleec, "shared_measures_groups")
        if output_path and not args.no_write:
            if groups:
                write_shared_measure_groups(doc, groups, output_path, min_count=args.min_count)
            else:
                print("(no matching measures; no file written)")

        if args.output_dir:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            for measure, rules_list in sorted(groups.items()):
                safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", measure)
                out_path = args.output_dir / f"shared_measure_{safe}.sleec"
                write_sleec_subset(
                    doc,
                    rules_list,
                    out_path,
                    header_comments=[f"Shared measure: {measure}", f"rule_count={len(rules_list)}"],
                )
        return

    if args.command == "mutual-exclusive":
        groups = extract_mutual_exclusive_groups(doc.rules, doc.mutual_exclusive_pairs)
        if args.require_both:
            groups = [group for group in groups if group[1] and group[2]]
        if args.format == "json":
            print(_format_summary_json_mutual_exclusive(groups))
        else:
            _print_text_mutual_exclusive(groups)

        selected_rules: List[Rule] = []
        seen: Set[str] = set()
        for _, rules_a, rules_b in groups:
            for rule in [*rules_a, *rules_b]:
                if rule.rule_id not in seen:
                    seen.add(rule.rule_id)
                    selected_rules.append(rule)

        output_path = args.output
        if output_path is None and not args.no_write:
            output_path = default_output_path(args.sleec, "mutual_exclusive")
        if output_path and not args.no_write:
            if selected_rules:
                write_sleec_subset(
                    doc,
                    selected_rules,
                    output_path,
                    include_relation_block=args.relations,
                    relation_pairs=doc.mutual_exclusive_pairs if args.relations else None,
                )
            else:
                print("(no matching rules; no file written)")
        return

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
