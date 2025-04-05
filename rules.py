import streamlit as st
import re
from itertools import combinations

def extract_responses(sleec_content):
    """extract all rules and their responses, including responses in unless clauses"""
    rules_dict = {}
    rule_responses = {}
    rules_full_text = {}  # store full text of rules
    
    # first split content by line and filter out comment lines
    valid_lines = []
    for line in sleec_content.split('\n'):
        line = line.strip()
        if line and not line.startswith('//'):
            valid_lines.append(line)
    
    # recombine valid lines
    valid_content = '\n'.join(valid_lines)
    
    # modify pattern to match any rule name (the word before when)
    pattern = r'([^\s]+)\s+when\s+.*?then\s+(.*?)(?=(?:[^\s]+\s+when|rule_end|$))'
    rules = re.finditer(pattern, valid_content, re.DOTALL)
    
    for rule in rules:
        rule_text = rule.group(0)
        rule_name = rule.group(1)
        response_text = rule.group(2).strip()
        
        # store full rule text
        rules_full_text[rule_name] = rule_text.strip()
        rule_responses[rule_name] = []
        
        # extract main response (including not prefix)
        main_response_match = re.search(r'^\s*((?:not\s+)?\w+)', response_text)
        if main_response_match:
            main_response = main_response_match.group(1).strip()
            if main_response.lower() not in ['and', 'or', 'unless']:
                if main_response not in rules_dict:
                    rules_dict[main_response] = []
                rules_dict[main_response].append(rule_name)
                rule_responses[rule_name].append(main_response)
        
        # extract responses in unless clauses (including not prefix)
        unless_responses = re.finditer(r'unless.*?then\s+((?:not\s+)?\w+)', response_text)
        for unless_match in unless_responses:
            unless_response = unless_match.group(1).strip()
            if unless_response.lower() not in ['and', 'or', 'unless']:
                if unless_response not in rules_dict:
                    rules_dict[unless_response] = []
                rules_dict[unless_response].append(f"{rule_name} (unless)")
                rule_responses[rule_name].append(unless_response)
    
    return rules_dict, rule_responses, rules_full_text

def find_mutually_exclusive_rules(rules_dict, rule_responses, mutual_exclusive_pairs):
    """find groups of rules with mutually exclusive responses, exclude responses from the same rule, consider complete constraint information of measures"""
    exclusive_groups = []
    processed_responses = set()
    
    # process explicitly declared mutually exclusive pairs
    for response1, response2 in mutual_exclusive_pairs:
        response1, response2 = response1.strip(), response2.strip()
        if response1 in rules_dict and response2 in rules_dict:
            # filter out responses from the same rule
            rules1 = set(rules_dict[response1])
            rules2 = set(rules_dict[response2])
            
            # remove rules containing both responses
            filtered_rules1 = {rule for rule in rules1 
                             if rule.split()[0] not in 
                             [r.split()[0] for r in rules2]}
            filtered_rules2 = {rule for rule in rules2 
                             if rule.split()[0] not in 
                             [r.split()[0] for r in filtered_rules1]}
            
            if filtered_rules1 and filtered_rules2:
                group = {
                    response1: list(filtered_rules1),
                    response2: list(filtered_rules2)
                }
                exclusive_groups.append(group)
                processed_responses.add(response1)
                processed_responses.add(response2)
    
    return exclusive_groups

def generate_sleec_file(groups, rules_full_text, is_shared=True, original_content=""):
    """generate SLEEC file based on rule groups, keep complete constraint information of measures, and add mutually exclusive relation declaration"""
    # extract def part from original file
    def_content = ""
    if original_content:
        def_match = re.search(r'def_start(.*?)def_end', original_content, re.DOTALL)
        if def_match:
            def_content = def_match.group(1)
    
    # if no def part is extracted, use default def content
    if not def_content:
        def_content = """
// define measures
measure userPayingAttention: boolean
measure userDataInformed: boolean
measure userSensoryNeedsMet: boolean
measure urgentNeed: boolean
measure severityOfState: numeric
measure stablePsychologicalState: boolean
measure timeElapsed: numeric
measure informationAvailable: boolean
measure informationDisclosureNotPermitted: boolean
measure languagePreferenceAvailable: boolean
measure directlyToUser: boolean
measure userConsentAvalaible: boolean
measure guardianConsentAvalaible: boolean
measure medicalEmergency: boolean
measure culturalIndicatorA: boolean
measure genderTypeB: boolean
measure userNameUnknown: boolean
measure userDirectsOtherwise: boolean
measure instructionRepeat: numeric
measure bodyPartInvolvedInExam: boolean
measure behaviorAggressive: boolean
measure dataNoiseConsidered: boolean
measure dataRelevantToContext: boolean
measure dataUnnecessary: boolean
measure trainingDataRepresentative: boolean
measure patientComfortable: boolean
measure patientAgeConsidered: boolean
measure patientXReligion: boolean
measure stablePhysicalState: boolean
measure UserUnableToConsent: boolean
measure UserAge: numeric
"""
    
    # build SLEEC file content
    sleec_content = "def_start\n" + def_content.strip() + "\ndef_end\n\nrule_start\n"
    
    # list for collecting mutually exclusive pairs
    mutual_exclusive_pairs = []
    
    # process different types of input
    if isinstance(groups, list):
        # if groups is a list, check its element type
        if groups and isinstance(groups[0], dict):
            # process list of dictionaries (mutually exclusive rule groups)
            for group_idx, group in enumerate(groups):
                sleec_content += f"// Group {group_idx + 1}\n"
                
                # collect mutually exclusive pairs
                responses = list(group.keys())
                if len(responses) == 2:  # ensure two responses
                    mutual_exclusive_pairs.append((responses[0], responses[1]))
                
                # process each response and its rules
                for response, rules in group.items():
                    for rule in rules:
                        # find matching rule in full rule text
                        rule_name = rule.split()[0]
                        if isinstance(rules_full_text, dict) and rule_name in rules_full_text:
                            # if rules_full_text is a dictionary, directly get rule content
                            sleec_content += rules_full_text[rule_name] + "\n\n"
                        else:
                            # if no matching rule is found, use simplified version
                            sleec_content += f"{rule}\n\n"
                
                sleec_content += "\n"
        else:
            # process list of strings (rule list)
            for rule in groups:
                sleec_content += rule + "\n\n"
    elif isinstance(groups, dict):
        # process dictionary (rules with shared responses)
        for response, rules in groups.items():
            sleec_content += f"// Response: {response}\n"
            for rule in rules:
                # find matching rule in full rule text
                rule_name = rule.split()[0]
                if isinstance(rules_full_text, dict) and rule_name in rules_full_text:
                    # if rules_full_text is a dictionary, directly get rule content
                    sleec_content += rules_full_text[rule_name] + "\n\n"
                else:
                    # if no matching rule is found, use simplified version
                    sleec_content += f"{rule}\n\n"
            
            sleec_content += "\n"
    else:
        # process string (single rule or content)
        sleec_content += str(groups) + "\n\n"
    
    sleec_content += "rule_end\n\n"
    
    # add mutually exclusive relation declaration
    if mutual_exclusive_pairs:
        sleec_content += "relation_start\n"
        for response1, response2 in mutual_exclusive_pairs:
            sleec_content += f"mutualExclusive {response1} {response2}\n"
        sleec_content += "relation_end\n"
    
    # determine file name
    file_name = "shared_rules.sleec" if is_shared else "exclusive_rules.sleec"
    
    # write to file
    with open(file_name, 'w') as f:
        f.write(sleec_content)
    
    return sleec_content  # return content instead of file name, so it can be used directly

def extract_measures_from_def(sleec_content):
    """extract all measures from def part"""
    measures = []
    
    # extract def part content
    def_match = re.search(r'def_start(.*?)def_end', sleec_content, re.DOTALL)
    if def_match:
        def_content = def_match.group(1)
        # match measure definition line, ignore comment lines
        for line in def_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('//'):
                # match measure definition - including boolean, numeric and scale types
                match = re.match(r'measure\s+(\w+)\s*:\s*(boolean|numeric|scale\([^)]+\))', line)
                if match:
                    measure_name = match.group(1)
                    measure_type = match.group(2)
                    measures.append((measure_name, measure_type))
    
    return measures

def extract_measures(sleec_content):
    """extract all measures from all rules, including measures in unless clauses and combined measures, keep complete constraint information"""
    measures_dict = {}  # store measures for each rule
    
    # first extract all scale type measures and their possible values
    scale_measures = {}
    def_match = re.search(r'def_start(.*?)def_end', sleec_content, re.DOTALL)
    if def_match:
        def_content = def_match.group(1)
        scale_pattern = r'measure\s+(\w+)\s*:\s*scale\(([^)]+)\)'
        scale_matches = re.finditer(scale_pattern, def_content)
        for scale_match in scale_matches:
            measure_name = scale_match.group(1)
            scale_values = [val.strip() for val in scale_match.group(2).split(',')]
            scale_measures[measure_name] = scale_values
    
    # modify pattern to match any rule starting with when
    pattern = r'([^\s]+)\s+when\s+(.*?)(?=(?:[^\s]+\s+when|rule_end|$))'
    matches = re.finditer(pattern, sleec_content, re.DOTALL)
    
    for match in matches:
        rule_name = match.group(1)  # use identifier before when as rule name
        rule_content = match.group(2).strip()
        
        measures = set()
        
        # process scale comparison with not - for example (not {riskLevel} = high)
        # first process format with parentheses: (not {measure} = value)
        not_scale_comp_pattern1 = r'\(not\s*\{([^}]+)\}\s*([<>]=?|=|≤|≥)\s*(\w+)\)'
        not_scale_comp_matches1 = re.finditer(not_scale_comp_pattern1, rule_content)
        for not_comp_match in not_scale_comp_matches1:
            measure = not_comp_match.group(1).strip()
            operator = not_comp_match.group(2)
            value = not_comp_match.group(3)
            
            # normalize operator
            if operator == '<=':
                operator = '≤'
            elif operator == '>=':
                operator = '≥'
            
            # add comparison information with not
            not_measure_value = f"not_{measure}{operator}{value}"
            measures.add(not_measure_value)
            print(f"Rule {rule_name}: Added not scale comparison: {not_measure_value}")
            
            # if it is a scale type measure, add basic information
            if measure in scale_measures:
                measures.add(f"scale_{measure}")
        
        # then process format without parentheses: not {measure} = value
        not_scale_comp_pattern2 = r'not\s*\{([^}]+)\}\s*([<>]=?|=|≤|≥)\s*(\w+)'
        not_scale_comp_matches2 = re.finditer(not_scale_comp_pattern2, rule_content)
        for not_comp_match in not_scale_comp_matches2:
            measure = not_comp_match.group(1).strip()
            operator = not_comp_match.group(2)
            value = not_comp_match.group(3)
            
            # normalize operator
            if operator == '<=':
                operator = '≤'
            elif operator == '>=':
                operator = '≥'
            
            # add comparison information with not
            not_measure_value = f"not_{measure}{operator}{value}"
            measures.add(not_measure_value)
            print(f"Rule {rule_name}: Added not scale comparison: {not_measure_value}")
            
            # if it is a scale type measure, add basic information
            if measure in scale_measures:
                measures.add(f"scale_{measure}")
        
        # process not measures (keep complete not semantic)
        not_measures_pattern = r'not\s*\{([^}]+)\}'
        not_measures_matches = re.finditer(not_measures_pattern, rule_content)
        for not_match in not_measures_matches:
            measure = not_match.group(1).strip()
            
            # check if this measure has been processed as comparison
            full_match = f"not {{{measure}}}"
            is_comp = re.search(re.escape(full_match) + r'\s*([<>]=?|=|≤|≥)', rule_content)
            
            # if it is not a comparison measure, add as a normal not measure
            if not is_comp:
                not_measure = f"not_{measure}"
                measures.add(not_measure)
                print(f"Rule {rule_name}: Added not measure: {not_measure}")
                
                # if it is a scale type measure, add basic information
                if measure in scale_measures:
                    measures.add(f"scale_{measure}")
        
        # process measures with comparison operators (keep complete comparison information)
        # match various comparison operators, including <, >, =, <=, >=, ≤, ≥
        comp_pattern = r'\{([^}]+)\}\s*([<>]=?|=|≤|≥)\s*(\w+)'
        comp_matches = re.finditer(comp_pattern, rule_content)
        for comp_match in comp_matches:
            measure = comp_match.group(1).strip()
            operator = comp_match.group(2)
            value = comp_match.group(3)
            
            # normalize operator
            if operator == '<=':
                operator = '≤'
            elif operator == '>=':
                operator = '≥'
                
            # use format: measure_operator_value, for example: UserAge_<_legalAge
            # note: do not use underscore to separate, to match user input format
            measure_value = f"{measure}{operator}{value}"
            measures.add(measure_value)
            print(f"Rule {rule_name}: Added scale comparison: {measure_value}")
            
            # if it is a scale type measure, add basic information
            if measure in scale_measures:
                measures.add(f"scale_{measure}")
        
        # process normal boolean measures - use two-step matching instead of look-behind
        # first get all content in curly braces
        all_measures = re.finditer(r'\{([^}]+)\}', rule_content)
        for measure_match in all_measures:
            measure = measure_match.group(1).strip()
            full_match = f"{{{measure}}}"
            
            # check if this measure is a not measure (前面有not)
            is_not_measure = re.search(r'not\s*' + re.escape(full_match), rule_content)
            
            # check if this measure is a comparison measure (后面有比较运算符)
            is_comp_measure = re.search(re.escape(full_match) + r'\s*([<>]=?|=|≤|≥)\s*\w+', rule_content)
            
            # if it is neither a not measure nor a comparison measure, it is a normal boolean measure
            if not is_not_measure and not is_comp_measure:
                bool_measure = f"bool_{measure}"
                measures.add(bool_measure)
                print(f"Rule {rule_name}: Added boolean measure: {bool_measure}")
                
            # if it is a scale type measure, add basic information
            if measure in scale_measures:
                measures.add(f"scale_{measure}")
        
        # process combined measures (process content in parentheses)
        combined_pattern = r'\((.*?)\)'
        combined_matches = re.finditer(combined_pattern, rule_content)
        for combined_match in combined_matches:
            combined_content = combined_match.group(1)
            
            # process scale comparison with not in combined content
            not_scale_comp_in_combined1 = re.finditer(not_scale_comp_pattern1, combined_content)
            for not_comp_match in not_scale_comp_in_combined1:
                measure = not_comp_match.group(1).strip()
                operator = not_comp_match.group(2)
                value = not_comp_match.group(3)
                
                # normalize operator
                if operator == '<=':
                    operator = '≤'
                elif operator == '>=':
                    operator = '≥'
                
                # add comparison information with not
                not_measure_value = f"not_{measure}{operator}{value}"
                measures.add(not_measure_value)
                print(f"Rule {rule_name}: Added not scale comparison from combined: {not_measure_value}")
                
                # if it is a scale type measure, add basic information
                if measure in scale_measures:
                    measures.add(f"scale_{measure}")
            
            not_scale_comp_in_combined2 = re.finditer(not_scale_comp_pattern2, combined_content)
            for not_comp_match in not_scale_comp_in_combined2:
                measure = not_comp_match.group(1).strip()
                operator = not_comp_match.group(2)
                value = not_comp_match.group(3)
                
                # normalize operator
                if operator == '<=':
                    operator = '≤'
                elif operator == '>=':
                    operator = '≥'
                
                # add comparison information with not
                not_measure_value = f"not_{measure}{operator}{value}"
                measures.add(not_measure_value)
                print(f"Rule {rule_name}: Added not scale comparison from combined: {not_measure_value}")
                
                # if it is a scale type measure, add basic information
                if measure in scale_measures:
                    measures.add(f"scale_{measure}")
            
            # process not measures in combined content
            not_in_combined = re.finditer(not_measures_pattern, combined_content)
            for not_match in not_in_combined:
                measure = not_match.group(1).strip()
                
                # check if this measure has been processed as comparison
                full_match = f"not {{{measure}}}"
                is_comp = re.search(re.escape(full_match) + r'\s*([<>]=?|=|≤|≥)', combined_content)
                
                # if it is not a comparison measure, add as a normal not measure
                if not is_comp:
                    not_measure = f"not_{measure}"
                    measures.add(not_measure)
                    print(f"Rule {rule_name}: Added not measure from combined: {not_measure}")
                    
                    # if it is a scale type measure, add basic information
                    if measure in scale_measures:
                        measures.add(f"scale_{measure}")
            
            # process measures with comparison operators in combined content
            comp_in_combined = re.finditer(comp_pattern, combined_content)
            for comp_match in comp_in_combined:
                measure = comp_match.group(1).strip()
                operator = comp_match.group(2)
                value = comp_match.group(3)
                
                # normalize operator
                if operator == '<=':
                    operator = '≤'
                elif operator == '>=':
                    operator = '≥'
                    
                # use the same format as above
                measure_value = f"{measure}{operator}{value}"
                measures.add(measure_value)
                print(f"Rule {rule_name}: Added scale comparison from combined: {measure_value}")
                
                # if it is a scale type measure, add basic information
                if measure in scale_measures:
                    measures.add(f"scale_{measure}")
            
            # process normal boolean measures in combined content - use two-step matching
            all_in_combined = re.finditer(r'\{([^}]+)\}', combined_content)
            for measure_match in all_in_combined:
                measure = measure_match.group(1).strip()
                full_match = f"{{{measure}}}"
                
                # check if this measure is a not measure
                is_not_measure = re.search(r'not\s*' + re.escape(full_match), combined_content)
                
                # check if this measure is a comparison measure
                is_comp_measure = re.search(re.escape(full_match) + r'\s*([<>]=?|=|≤|≥)\s*\w+', combined_content)
                
                # if it is neither a not measure nor a comparison measure, it is a normal boolean measure
                if not is_not_measure and not is_comp_measure:
                    bool_measure = f"bool_{measure}"
                    measures.add(bool_measure)
                    print(f"Rule {rule_name}: Added boolean measure from combined: {bool_measure}")
                    
                # if it is a scale type measure, add basic information
                if measure in scale_measures:
                    measures.add(f"scale_{measure}")
        
        # clean measures (remove empty values and duplicates)
        measures = {m for m in measures if m}
        measures_dict[rule_name] = measures
        print(f"Rule {rule_name}: Final measures: {measures}")
    
    return measures_dict

def find_rules_with_measures(measures_dict, target_measures):
    """找到包含指定measures的规则，考虑度量的完整约束信息"""
    matching_rules = {}
    conflicting_measures = {}  # store conflicting measures
    
    # convert target measures to lowercase for case-insensitive comparison
    target_measures_lower = [m.lower() for m in target_measures]
    print(f"Target measures: {target_measures_lower}")
    
    # first check if there are conflicting scale values in target measures
    for i, target1 in enumerate(target_measures_lower):
        for target2 in target_measures_lower[i+1:]:
            # check if it is the same measure's value and its negation
            if target1.startswith("not_") and target2 == target1[4:]:
                conflicting_measures[(target1, target2)] = f"Measure and its negation: {target2}"
            elif target2.startswith("not_") and target1 == target2[4:]:
                conflicting_measures[(target1, target2)] = f"Measure and its negation: {target1}"
            
            # check if it is a scale measure's comparison and its negation
            # for example: riskLevel=high and not_riskLevel=high
            if "=" in target1 and "=" in target2:
                # process not_measure=value and measure=value cases
                if target1.startswith("not_") and "=" in target1[4:]:
                    measure1 = target1[4:].split("=")[0]  # remove "not_" prefix
                    value1 = target1[4:].split("=")[1]
                    measure2 = target2.split("=")[0]
                    value2 = target2.split("=")[1]
                    
                    if measure1 == measure2 and value1 == value2:
                        conflicting_measures[(target1, target2)] = f"Scale value and its negation: {measure2}={value2}"
                elif target2.startswith("not_") and "=" in target2[4:]:
                    measure1 = target1.split("=")[0]
                    value1 = target1.split("=")[1]
                    measure2 = target2[4:].split("=")[0]  # remove "not_" prefix
                    value2 = target2[4:].split("=")[1]
                    
                    if measure1 == measure2 and value1 == value2:
                        conflicting_measures[(target1, target2)] = f"Scale value and its negation: {measure1}={value1}"
                # process measure=value1 and measure=value2 cases (different values)
                elif not (target1.startswith("not_") or target2.startswith("not_")):
                    measure1 = target1.split("=")[0]
                    value1 = target1.split("=")[1]
                    measure2 = target2.split("=")[0]
                    value2 = target2.split("=")[1]
                    
                    if measure1 == measure2 and value1 != value2:
                        conflicting_measures[(target1, target2)] = f"Conflicting scale values: {measure1}={value1} vs {measure2}={value2}"
    
    # if conflicting measures are found, return conflict information
    if conflicting_measures:
        return {"conflicting_measures": conflicting_measures}
    
    # split target measures into positive and negative groups
    positive_targets = []
    negative_targets = []
    
    for target in target_measures_lower:
        if target.startswith("not_"):
            negative_targets.append(target)
        else:
            positive_targets.append(target)
    
    print(f"Positive targets: {positive_targets}")
    print(f"Negative targets: {negative_targets}")
    
    # process positive and negative target measures separately
    positive_matching_rules = {}
    negative_matching_rules = {}
    
    # process positive target measures
    if positive_targets:
        for rule, measures in measures_dict.items():
            # convert rule measures to lowercase
            rule_measures_lower = {m.lower() for m in measures}
            print(f"Rule {rule} measures: {rule_measures_lower}")
            
            # filter out measures with "not_" prefix, only keep positive measures
            positive_rule_measures = {m for m in rule_measures_lower if not m.startswith("not_")}
            
            # check if each positive target measure is in the rule's positive measures
            matching_measures = []
            for target in positive_targets:
                # check if it is a complete constraint search (contains prefix or operator)
                is_exact_search = (
                    target.startswith("bool_") or 
                    target.startswith("scale_") or  # add support for scale type
                    any(op in target for op in ["<", ">", "=", "≤", "≥"])
                )
                
                if is_exact_search:
                    # for complete constraint search, try to normalize operator and find match
                    normalized_target = target
                    
                    # normalize operator
                    if "<=" in target:
                        normalized_target = target.replace("<=", "≤")
                    elif ">=" in target:
                        normalized_target = target.replace(">=", "≥")
                    
                    # process possible format differences
                    if "_<_" in normalized_target:
                        alt_target = normalized_target.replace("_<_", "<")
                    elif "_>_" in normalized_target:
                        alt_target = normalized_target.replace("_>_", ">")
                    elif "_=_" in normalized_target:
                        alt_target = normalized_target.replace("_=_", "=")
                    elif "_≤_" in normalized_target:
                        alt_target = normalized_target.replace("_≤_", "≤")
                    elif "_≥_" in normalized_target:
                        alt_target = normalized_target.replace("_≥_", "≥")
                    else:
                        alt_target = normalized_target
                    
                    # check if the original target, normalized target or alternative format matches
                    if (target in positive_rule_measures or 
                        normalized_target in positive_rule_measures or 
                        alt_target in positive_rule_measures):
                        # find the matching actual measure (keep original case)
                        for measure in measures:
                            measure_lower = measure.lower()
                            if (not measure_lower.startswith("not_")) and measure_lower in [target, normalized_target, alt_target]:
                                matching_measures.append(measure)
                                print(f"Rule {rule} matched positive target {target} with measure {measure}")
                                break
                        else:
                            # if no exact match is found, add target measure
                            matching_measures.append(target)
                            print(f"Rule {rule} matched positive target {target} (no exact match)")
                else:
                    # for simple search, find measures containing target
                    for measure_lower in positive_rule_measures:
                        # check if measure contains target (consider various prefixes and operators)
                        base_measure = measure_lower
                        if measure_lower.startswith("bool_"):
                            base_measure = measure_lower[5:]  # remove "bool_" prefix
                        elif measure_lower.startswith("scale_"):  # add support for scale type
                            base_measure = measure_lower[6:]  # remove "scale_" prefix
                        else:
                            # process measures with operators
                            for op in ["<", ">", "=", "≤", "≥"]:
                                if op in measure_lower:
                                    base_measure = measure_lower.split(op)[0]
                                    break
                        
                        if target == base_measure:
                            # find the matching actual measure (keep original case)
                            for measure in measures:
                                measure_lower = measure.lower()
                                if (not measure_lower.startswith("not_")) and measure_lower == measure_lower:
                                    matching_measures.append(measure)
                                    print(f"Rule {rule} matched positive target {target} with measure {measure} (base match)")
                                    break
            
            # check if there are conflicting measures in the rule
            has_conflicting_measures = False
            
            # for each positive target measure, check if there is a corresponding negative measure in the rule
            for target in positive_targets:
                # if it is a scale comparison, check if there is a corresponding negative comparison
                if "=" in target:
                    measure_name = target.split("=")[0]
                    value = target.split("=")[1]
                    negated_measure = f"not_{measure_name}={value}".lower()
                    
                    # check if there is this negated measure in the rule
                    for rule_measure in rule_measures_lower:
                        if rule_measure == negated_measure:
                            has_conflicting_measures = True
                            print(f"Rule {rule} has conflicting measure: {negated_measure}")
                            break
                
                # if it is a normal measure, check if there is a corresponding negative measure
                else:
                    negated_measure = f"not_{target}".lower()
                    
                    # check if there is this negated measure in the rule
                    for rule_measure in rule_measures_lower:
                        if rule_measure == negated_measure:
                            has_conflicting_measures = True
                            print(f"Rule {rule} has conflicting measure: {negated_measure}")
                            break
                
                if has_conflicting_measures:
                    break
            
            # only add to matching results when there are no conflicting measures
            if matching_measures and not has_conflicting_measures:
                positive_matching_rules[rule] = matching_measures
                print(f"Added rule {rule} to positive matching rules with measures: {matching_measures}")
    
    # process negative target measures
    if negative_targets:
        for rule, measures in measures_dict.items():
            # convert rule measures to lowercase
            rule_measures_lower = {m.lower() for m in measures}
            print(f"Rule {rule} measures for negative targets: {rule_measures_lower}")
            
            # check if each negative target measure is in the rule's measures
            matching_measures = []
            for target in negative_targets:
                # check if there is a matching measure in the rule
                found_match = False
                
                # 1. first check if there is an exact match in the rule
                if target.lower() in rule_measures_lower:
                    # find the matching actual measure (keep original case)
                    for measure in measures:
                        if measure.lower() == target.lower():
                            matching_measures.append(measure)
                            found_match = True
                            print(f"Rule {rule} matched negative target {target} with exact measure {measure}")
                            break
                
                # 2. if there is no exact match, check if there is a measure containing "not" in the rule
                if not found_match and target.startswith("not_"):
                    # decompose target measure
                    if "=" in target[4:]:  # process not_measure=value format
                        measure_name = target[4:].split("=")[0]  # remove "not_" prefix
                        value = target[4:].split("=")[1]
                        
                        # first check if there is an exact match (not_measure=value)
                        for rule_measure in rule_measures_lower:
                            if rule_measure == target.lower():
                                # find the matching actual measure (keep original case)
                                for measure in measures:
                                    if measure.lower() == rule_measure:
                                        matching_measures.append(measure)
                                        found_match = True
                                        print(f"Rule {rule} matched negative target {target} with exact extracted measure {measure}")
                                        break
                                if found_match:
                                    break
                        
                        # if there is no exact match, check if there is a matching negative scale comparison in the rule
                        if not found_match:
                            for rule_measure in rule_measures_lower:
                                # check if it is not_measure=value format
                                if rule_measure.startswith("not_") and "=" in rule_measure[4:]:
                                    rule_measure_name = rule_measure[4:].split("=")[0]
                                    rule_value = rule_measure[4:].split("=")[1]
                                    
                                    if rule_measure_name == measure_name and rule_value == value:
                                        # find the matching actual measure (keep original case)
                                        for measure in measures:
                                            if measure.lower() == rule_measure:
                                                matching_measures.append(measure)
                                                found_match = True
                                                print(f"Rule {rule} matched negative target {target} with measure {measure} (not_measure=value format)")
                                                break
                                        if found_match:
                                            break
                        
                        # if there is still no match, try to find the negated condition in the original SLEEC format
                        if not found_match:
                            for measure in measures:
                                measure_lower = measure.lower()
                                # more precise matching pattern, find "not {measure_name} = value" or "(not {measure_name} = value)" format
                                if (("not" in measure_lower and 
                                     "{" + measure_name.lower() + "}" in measure_lower and 
                                     "=" in measure_lower and 
                                     value.lower() in measure_lower) or
                                    # check the format in parentheses
                                    ("(not" in measure_lower and 
                                     "{" + measure_name.lower() + "}" in measure_lower and 
                                     "=" in measure_lower and 
                                     value.lower() in measure_lower)):
                                    matching_measures.append(measure)
                                    found_match = True
                                    print(f"Rule {rule} matched negative target {target} with measure {measure} (contains not, {measure_name}, {value})")
                                    break
                    else:  # process normal not_measure format
                        measure_name = target[4:]  # remove "not_" prefix
                        
                        # first check if there is an exact match (not_measure)
                        for rule_measure in rule_measures_lower:
                            if rule_measure == target.lower():
                                # find the matching actual measure (keep original case)
                                for measure in measures:
                                    if measure.lower() == rule_measure:
                                        matching_measures.append(measure)
                                        found_match = True
                                        print(f"Rule {rule} matched negative target {target} with exact extracted measure {measure}")
                                        break
                                if found_match:
                                    break
                        
                        # if there is still no match, try to find the negated condition in the original SLEEC format
                        if not found_match:
                            for rule_measure in rule_measures_lower:
                                if rule_measure.startswith("not_") and rule_measure[4:] == measure_name:
                                    # find the matching actual measure (keep original case)
                                    for measure in measures:
                                        if measure.lower() == rule_measure:
                                            matching_measures.append(measure)
                                            found_match = True
                                            print(f"Rule {rule} matched negative target {target} with measure {measure} (not_measure format)")
                                            break
                                    if found_match:
                                        break
                        
                        # if there is still no match, try to find the negated condition in the original SLEEC format
                        if not found_match:
                            for measure in measures:
                                measure_lower = measure.lower()
                                # more precise matching pattern, find "not {measure}" or "(not {measure})" format
                                if (("not" in measure_lower and 
                                     "{" + measure_name.lower() + "}" in measure_lower and 
                                     "=" not in measure_lower) or
                                    # check the format in parentheses
                                    ("(not" in measure_lower and 
                                     "{" + measure_name.lower() + "}" in measure_lower and 
                                     "=" not in measure_lower)):
                                    matching_measures.append(measure)
                                    found_match = True
                                    print(f"Rule {rule} matched negative target {target} with measure {measure} (contains not and {measure_name})")
                                    break
            
            # check if there is a measure conflicting with the target
            has_conflicting_measures = False
            
            # for each negative target measure, check if there is a corresponding positive measure in the rule
            for target in negative_targets:
                if target.startswith("not_") and "=" in target[4:]:
                    # if it is a negative scale comparison, check if there is a corresponding positive comparison
                    measure_name = target[4:].split("=")[0]  # remove "not_" prefix
                    value = target[4:].split("=")[1]
                    positive_measure = f"{measure_name}={value}".lower()
                    
                    # check if there is this positive measure in the rule
                    has_positive = False
                    has_negative = False
                    
                    for rule_measure in rule_measures_lower:
                        if rule_measure == positive_measure:
                            has_positive = True
                        if rule_measure == target.lower():
                            has_negative = True
                    
                    # only when there is a positive form but no negative form, it is considered a conflict
                    # if the rule contains both positive and negative forms, it may be due to special cases in the extraction process, and should not be considered a conflict
                    if has_positive and not has_negative:
                        has_conflicting_measures = True
                        print(f"Rule {rule} has conflicting measure for negative target: {positive_measure}")
                elif target.startswith("not_"):
                    # if it is a normal negative measure, check if there is a corresponding positive measure
                    positive_measure = target[4:].lower()  # remove "not_" prefix
                    
                    # also check if both positive and negative forms are included
                    has_positive = False
                    has_negative = False
                    
                    for rule_measure in rule_measures_lower:
                        if rule_measure == positive_measure or rule_measure.startswith(f"bool_{positive_measure}"):
                            has_positive = True
                        if rule_measure == target.lower():
                            has_negative = True
                    
                    # only when there is a positive form but no negative form, it is considered a conflict
                    if has_positive and not has_negative:
                        has_conflicting_measures = True
                        print(f"Rule {rule} has conflicting measure for negative target: {positive_measure}")
                
                if has_conflicting_measures:
                    break
            
            # only when there is no conflicting measure in the rule, add to matching results
            if matching_measures and not has_conflicting_measures:
                negative_matching_rules[rule] = matching_measures
                print(f"Added rule {rule} to negative matching rules with measures: {matching_measures}")
    
    # merge results, but keep positive and negative measures separate
    for rule, pos_measures in positive_matching_rules.items():
        matching_rules[rule] = {"positive": pos_measures}
    
    for rule, neg_measures in negative_matching_rules.items():
        if rule in matching_rules:
            matching_rules[rule]["negative"] = neg_measures
        else:
            matching_rules[rule] = {"negative": neg_measures}
    
    print(f"Final matching rules: {matching_rules}")
    return matching_rules

def display_measures_used_in_rules(measures_dict):
    """show all measures used in rules"""
    all_measures = set()
    for rule, measures in measures_dict.items():
        for measure in measures:
            # filter out scale type measures without specific values
            if not measure.startswith("scale_"):
                all_measures.add(measure)
    
    # sort by alphabet
    sorted_measures = sorted(list(all_measures))
    
    st.subheader("Measures Used in Rules")
    for measure in sorted_measures:
        st.write(f"- {measure}")
    
    return sorted_measures

def main():
    st.title("SLEEC Rules Response Analyzer")
    
    # file upload or text input
    input_method = st.radio(
        "Choose input method:",
        ["Upload SLEEC file", "Enter SLEEC content"]
    )
    
    sleec_content = ""
    
    if input_method == "Upload SLEEC file":
        uploaded_file = st.file_uploader("Upload your SLEEC file", type=['sleec', 'txt'])
        if uploaded_file:
            sleec_content = uploaded_file.getvalue().decode()
    else:
        sleec_content = st.text_area(
            "Enter your SLEEC rules:",
            height=300,
            placeholder="Rule1 when ... then ...\nRule2 when ... then ..."
        )
    
    if sleec_content:
        # analysis type selection
        analysis_type = st.radio(
            "Choose analysis type:",
            ["Shared Responses", "Mutually Exclusive Responses", "Shared Measures"]
        )
        
        # analyze rules
        rules_by_response, rule_responses, rules_full_text = extract_responses(sleec_content)
        
        if analysis_type == "Shared Responses":
            # show rules grouped by shared response
            st.subheader("Rules Grouped by Shared Response")
            shared_groups = {resp: rules for resp, rules in rules_by_response.items() 
                           if len(rules) > 1}
            
            for response, rules in shared_groups.items():
                with st.expander(f"Response: {response} ({len(rules)} rules)"):
                    st.write("Rules:", ", ".join(rules))
            
            # add export button
            if shared_groups:
                sleec_content_output = generate_sleec_file(shared_groups, rules_full_text, True, sleec_content)
                st.download_button(
                    "Download SLEEC file with shared responses",
                    sleec_content_output,
                    "shared_responses.sleec",
                    "text/plain"
                )
        
        elif analysis_type == "Mutually Exclusive Responses":
            # analyze mutually exclusive responses
            st.subheader("Define Mutually Exclusive Responses")
            
            num_pairs = st.number_input("Number of mutually exclusive pairs", 
                                      min_value=1, value=1)
            
            mutual_exclusive_pairs = []
            for i in range(num_pairs):
                col1, col2, col3 = st.columns([2,1,2])
                with col1:
                    response1 = st.text_input(f"Response {i+1} A", key=f"resp1_{i}")
                with col2:
                    st.markdown("### mutually<br>exclusive", unsafe_allow_html=True)
                with col3:
                    response2 = st.text_input(f"Response {i+1} B", key=f"resp2_{i}")
                
                if response1 and response2:
                    mutual_exclusive_pairs.append((response1, response2))
            
            if mutual_exclusive_pairs:
                exclusive_groups = find_mutually_exclusive_rules(
                    rules_by_response, 
                    rule_responses,
                    mutual_exclusive_pairs
                )
                
                if exclusive_groups:
                    st.subheader("Rules with Mutually Exclusive Responses")
                    for i, group in enumerate(exclusive_groups, 1):
                        with st.expander(f"Mutually Exclusive Group {i}"):
                            for response, rules in group.items():
                                if rules:
                                    st.write(f"Response '{response}':")
                                    st.write("Rules:", ", ".join(rules))
                    
                    # add export button
                    sleec_content_output = generate_sleec_file(exclusive_groups, rules_full_text, False, sleec_content)
                    st.download_button(
                        "Download SLEEC file with mutually exclusive responses",
                        sleec_content_output,
                        "mutually_exclusive_responses.sleec",
                        "text/plain"
                    )
                else:
                    st.info("No valid mutually exclusive rules found")
        
        elif analysis_type == "Shared Measures":
            # extract all measures directly from the def section
            def_match = re.search(r'def_start(.*?)def_end', sleec_content, re.DOTALL)
            all_measures = []  # use list instead of set to keep order
            
            if def_match:
                def_content = def_match.group(1)
                # match measure definition lines, ignore comment lines
                for line in def_content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('//'):
                        # match measure definition
                        match = re.match(r'measure\s+(\w+)\s*:\s*(boolean|numeric)', line)
                        if match:
                            measure_name = match.group(1)
                            measure_type = match.group(2)
                            all_measures.append(measure_name)
            
            st.subheader("Available Measures")
            if all_measures:
                st.write("All measures found in definitions:", ", ".join(sorted(all_measures)))
            else:
                st.write("No measures found in definitions")
            
            # extract measures from rules for search
            measures_dict = extract_measures(sleec_content)
            
            # use new function to show all measures, filter out scale type measures without specific values
            all_measures_in_rules = display_measures_used_in_rules(measures_dict)
            
            measure_input = st.text_area(
                "Enter measures to search (one per line):",
                placeholder="userPayingAttention\nUserAge < legalAge"
            )
            
            if measure_input:
                target_measures = [m.strip() for m in measure_input.split('\n') if m.strip()]
                matching_rules = find_rules_with_measures(measures_dict, target_measures)
                
                if matching_rules:
                    st.subheader("Rules with Matching Measures")
                    for rule, measures in matching_rules.items():
                        with st.expander(f"{rule} - Matching Measures"):
                            st.write("Measures found:", ", ".join(measures))
                            if rule in rules_full_text:
                                st.write("Rule content:")
                                st.code(rules_full_text[rule])
                    
                    # add export button
                    content = ["rule_start"]
                    content.append("\n// Rules sharing specified measures:")
                    content.extend(f"// {measure}" for measure in target_measures)
                    for rule in matching_rules:
                        if rule in rules_full_text:
                            content.append(rules_full_text[rule])
                    content.append("\nrule_end")
                    
                    st.download_button(
                        "Download SLEEC file with shared measures",
                        "\n".join(content),
                        "shared_measures.sleec",
                        "text/plain"
                    )
                else:
                    st.info("No rules found with the specified measures")

if __name__ == "__main__":
    main() 