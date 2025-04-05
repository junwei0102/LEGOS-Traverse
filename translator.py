import streamlit as st
import re
import os
from collections import defaultdict

def extract_measures_from_def(rules_content):
    """extract all measure definitions between def_start and def_end"""
    measures_info = {}
    
    # extract def part
    def_match = re.search(r'def_start(.*?)def_end', rules_content, re.DOTALL)
    if def_match:
        def_content = def_match.group(1)
        print(f"Def content: {def_content}")  # debug output
        
        # find all measure definition lines
        measure_lines = re.finditer(r'^\s*measure\s+(\w+)\s*:\s*(boolean|numeric)\s*$', 
                                  def_content, 
                                  re.MULTILINE | re.IGNORECASE)
        
        for match in measure_lines:
            measure_name = match.group(1)
            measure_type = match.group(2).lower()
            measures_info[measure_name] = {
                'type': measure_type,
                'events': set()  # store events using this measure
            }
            print(f"Found measure: {measure_name} of type {measure_type}")  # debug output
    
    print(f"All measures found: {measures_info}")  # debug output
    return measures_info

def build_event_measure_map(rules_content):
    """build mapping between events and their related measures"""
    event_measure_map = defaultdict(lambda: {'bool': set(), 'not_bool': set(), 'numeric': set()})
    
    try:
        # skip comment lines and empty lines
        valid_lines = []
        for line in rules_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('//'):
                valid_lines.append(line)
        
        rules_content = '\n'.join(valid_lines)
        print(f"Processed rules content:\n{rules_content}")  # debug output
        
        # match rule pattern: rule name when condition then response [unless condition then response]*
        rules = re.finditer(r'([^\s]+)\s+when\s+(.*?)\s+then\s+([^\n]*?)(?:\s+unless\s+(.*?)(?:\s+then\s+([^\n]*))?)?$',
                           rules_content,
                           re.MULTILINE)
        
        for rule in rules:
            rule_name = rule.group(1)
            condition = rule.group(2)
            unless_condition = rule.group(4)
            
            print(f"\nProcessing rule: {rule_name}")  # debug output
            print(f"Main condition: {condition}")  # debug output
            if unless_condition:
                print(f"Unless condition: {unless_condition}")  # debug output
            
            # extract trigger event (the first word after when)
            event_match = re.search(r'([A-Z][a-zA-Z]+)', condition)
            if not event_match:
                continue
                
            trigger_event = event_match.group(1)
            
            def process_condition(condition_str, target_event=None):
                # if no target event is specified, use trigger event
                if target_event is None:
                    target_event = trigger_event
                    
                # first process not bool, because its pattern is most specific
                not_bool_matches = re.finditer(r'not\s+\{([^}]+)\}', condition_str)
                for match in not_bool_matches:
                    measure = match.group(1)
                    print(f"Found not_bool measure: {measure} for event {target_event}")  # debug output
                    event_measure_map[target_event]['not_bool'].add(measure)
                
                # process numeric comparison - modify regex to match variable name as value
                numeric_matches = re.finditer(r'\{([^}]+)\}\s*([<>=]+)\s*(\w+)', condition_str)
                for match in numeric_matches:
                    measure = match.group(1)
                    operator = match.group(2)
                    value = match.group(3)
                    print(f"Found numeric measure: {measure} {operator} {value} for event {target_event}")  # debug output
                    # add measure and operator to event's numeric set
                    event_measure_map[target_event]['numeric'].add((measure, operator, value))
                
                # finally process normal bool
                # get all measure references
                all_measures = re.finditer(r'\{([^}]+)\}', condition_str)
                for match in all_measures:
                    measure = match.group(1)
                    # check if this measure has been processed as not_bool or numeric
                    is_not_bool = f"not {{{measure}}}" in condition_str
                    is_numeric = re.search(rf'\{{{measure}\}}\s*[<>=]+\s*\w+', condition_str)
                    
                    if not is_not_bool and not is_numeric:
                        print(f"Found bool measure: {measure} for event {target_event}")  # debug output
                        event_measure_map[target_event]['bool'].add(measure)
            
            # process main condition
            process_condition(condition)
            
            # process unless condition - ensure to pass trigger event to process_condition
            if unless_condition:
                process_condition(unless_condition, trigger_event)
            
            print(f"Current measures for {trigger_event}: {dict(event_measure_map[trigger_event])}")  # debug output
    
    except Exception as e:
        print(f"Error in build_event_measure_map: {str(e)}")
        raise
    
    print(f"\nFinal event_measure_map: {dict(event_measure_map)}")  # debug output
    return dict(event_measure_map)

def extract_measures_from_selected_rules():
    """extract measures needed for each event from selected_rules.txt"""
    event_measures_dict = defaultdict(lambda: {'bool': set(), 'not_bool': set(), 'numeric': set()})
    
    try:
        # first get all defined measures from generated_rules.sleec
        with open('generated_rules.sleec', 'r') as f:
            rules_content = f.read()
            all_measures = extract_measures_from_def(rules_content)
            print(f"All defined measures: {all_measures}")  # debug output
        
        # read rules from selected_rules.txt
        with open('selected_rules.txt', 'r') as f:
            rules = f.readlines()
        
        for rule in rules:
            rule = rule.strip()
            if not rule:
                continue
            
            # update rule matching pattern to include unless condition
            match = re.match(r'([^\s]+)\s+when\s+(.*?)\s+then\s+([^u\n]*?)(?:\s+unless\s+(.*?)(?:\s+then\s+([^\n]*)))?$', rule)
            if not match:
                continue
            
            rule_name, condition, response = match.group(1), match.group(2), match.group(3)
            unless_condition = match.group(4) if match.group(4) else None
            unless_response = match.group(5) if match.group(5) else None
            
            # process measures in main condition
            process_condition_measures(condition, event_measures_dict, all_measures)
            
            # process measures in unless condition (if exists)
            if unless_condition:
                process_condition_measures(unless_condition, event_measures_dict, all_measures)
            
            print(f"Processing rule: {rule_name}")  # debug output
            print(f"Main condition: {condition}")
            if unless_condition:
                print(f"Unless condition: {unless_condition}")
    
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return {}
    
    return dict(event_measures_dict)

def process_condition_measures(condition, event_measures_dict, all_measures):
    """process measures in condition and update event_measures_dict"""
    # process bool measures
    bool_matches = re.finditer(r'\{([^}]+)\}', condition)
    for match in bool_matches:
        measure = match.group(1)
        if measure.startswith('not '):
            measure = measure[4:].strip()
            if measure in all_measures:
                for event in all_measures[measure]['events']:
                    event_measures_dict[event]['not_bool'].add(measure)
        else:
            if measure in all_measures:
                for event in all_measures[measure]['events']:
                    event_measures_dict[event]['bool'].add(measure)
    
    # process numeric measures - modify regex to match variable name as value
    numeric_matches = re.finditer(r'\{([^}]+)\}\s*([<>=!]+)\s*(\w+)', condition)
    for match in numeric_matches:
        measure = match.group(1)
        operator = match.group(2)
        value = match.group(3)
        
        # check if value is a number or variable name
        try:
            value = int(value)
        except ValueError:
            # if not a number, keep as string (variable name)
            pass
            
        if measure in all_measures:
            for event in all_measures[measure]['events']:
                event_measures_dict[event]['numeric'].add((measure, operator, value))

def check_measure_condition(measure_value, operator, target_value):
    """check if measure value satisfies condition"""
    try:
        value = int(measure_value)
        
        # if target_value is a string and not a number, it might be a variable name (e.g. legalAge)
        # in this case, we need to find the value of this variable
        if isinstance(target_value, str) and not target_value.isdigit():
            # here we assume legalAge = 18, you can modify it according to actual situation
            if target_value == 'legalAge':
                target_value = 18
            else:
                # for other variables, you can add more mappings
                print(f"Warning: Unknown variable {target_value}, using default comparison")
                return True  # default return True to include this measure
        else:
            # ensure target_value is an integer
            target_value = int(target_value)
            
        if operator == '>=':
            return value >= target_value
        elif operator == '>':
            return value > target_value
        elif operator == '<=':
            return value <= target_value
        elif operator == '<':
            return value < target_value
        elif operator == '=':
            return value == target_value
    except ValueError:
        # if measure_value is not a number, default return True to include this measure
        print(f"Warning: Non-numeric measure value {measure_value}, using default comparison")
        return True

def filter_measures(measures_str, required_measures):
    """only keep measures needed in rules"""
    if not measures_str or not required_measures:
        return ""
    
    # split measures string into key-value pairs
    measures_dict = {}
    for pair in measures_str.split(', '):
        if '=' in pair:
            key, value = pair.split('=', 1)
            measures_dict[key.strip()] = value.strip()
    
    filtered_pairs = []
    
    # process bool measures
    for measure in required_measures['bool']:
        if measure in measures_dict:
            filtered_pairs.append(f"{measure}={measures_dict[measure]}")
    
    # process bool measures with not
    for measure in required_measures.get('not_bool', set()):
        if measure in measures_dict:
            value = measures_dict[measure].lower()
            # if original value is False, then this not condition is satisfied
            if value == 'false':
                filtered_pairs.append(f"{measure}={value}")
    
    # process numeric comparison measures
    for measure_tuple in required_measures['numeric']:
        if len(measure_tuple) == 3:
            measure_name, operator, target_value = measure_tuple
            if measure_name in measures_dict:
                value = measures_dict[measure_name]
                # always include numeric comparison measures, whether they are satisfied or not
                # this ensures important measures like UserAge are always included in event parameters
                filtered_pairs.append(f"{measure_name}={value}")
    
    return ", ".join(filtered_pairs)

def parse_measure(measure_line):
    """parse parameters in Measure line"""
    match = re.search(r'Measure\((.*?)\)', measure_line)
    if match:
        return match.group(1)
    return ""

def parse_trace(trace_content):
    """parse trace content and convert to LTS format"""
    try:
        # build event-measure map from rule file
        with open('generated_rules.sleec', 'r') as f:
            rules_content = f.read()
            event_measure_map = build_event_measure_map(rules_content)
            print(f"Event-measure map: {event_measure_map}")
        
        current_state = 0
        next_state = 1
        transitions = []
        measures_by_time = {}
        events_by_time = {}
        
        # parse events and measures in trace
        lines = trace_content.split('\n')
        current_measures = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            match = re.match(r'at time (\d+): (.+)', line)
            if not match:
                continue
            
            time = match.group(1).strip()
            action = match.group(2).strip()
            
            if time not in events_by_time:
                events_by_time[time] = []
            
            # process Measure line
            if action.startswith('Measure'):
                measure_match = re.search(r'Measure\((.*?)\)', action)
                if measure_match:
                    measure_pairs = measure_match.group(1).split(', ')
                    current_measures.clear()  # clear previous measures
                    for pair in measure_pairs:
                        if '=' in pair:
                            key, value = pair.split('=')
                            current_measures[key.strip()] = value.strip()
                    measures_by_time[time] = current_measures.copy()
                    print(f"Time {time} measures: {current_measures}")
            # process event
            elif not action.startswith('blocked_'):
                if action.endswith('()'):
                    action = action[:-2]
                events_by_time[time].append(action)
        
        # generate LTS conversion
        for time in sorted(events_by_time.keys(), key=int):
            current_measures = measures_by_time.get(time, measures_by_time.get(str(int(time)-1), {}))
            print(f"\nProcessing time {time} with measures: {current_measures}")
            
            for event in events_by_time[time]:
                event_name = event.split('(')[0]
                needed_measures = []
                
                # check if it is a trigger event (in event_measure_map)
                if event_name in event_measure_map:
                    print(f"Processing event {event_name} with map: {event_measure_map[event_name]}")
                    
                    # process bool measures
                    for measure in event_measure_map[event_name]['bool']:
                        if measure in current_measures and current_measures[measure].lower() == 'true':
                            needed_measures.append(f"{measure}={current_measures[measure]}")
                            print(f"Added bool measure: {measure}={current_measures[measure]}")
                    
                    # process not bool measures
                    for measure in event_measure_map[event_name]['not_bool']:
                        if measure in current_measures and current_measures[measure].lower() == 'false':
                            needed_measures.append(f"{measure}={current_measures[measure]}")
                            print(f"Added not_bool measure: {measure}={current_measures[measure]}")
                    
                    # process numeric measures
                    for measure_name, operator, target_value in event_measure_map[event_name]['numeric']:
                        if measure_name in current_measures:
                            current_value = current_measures[measure_name]
                            if check_measure_condition(current_value, operator, target_value):
                                needed_measures.append(f"{measure_name}={current_value}")
                                print(f"Added numeric measure: {measure_name}={current_value}")
                
                # build event string
                measures_str = ', '.join(sorted(needed_measures)) if needed_measures else ''
                if measures_str:
                    action = f"{event}({measures_str}, time={time})"
                else:
                    action = f"{event}(time={time})"
                
                print(f"Final action: {action}")
                transitions.append((current_state, action, next_state))
                current_state = next_state
                next_state += 1
        
        # generate LTS description
        num_states = next_state
        num_transitions = len(transitions)
        
        lts = [f"des (0, {num_transitions}, {num_states})"]
        for from_state, action, to_state in transitions:
            lts.append(f'({from_state}, "{action}", {to_state})')
        
        return "\n".join(lts)
        
    except Exception as e:
        print(f"Error in parse_trace: {str(e)}")
        raise

def main():
    st.title("Trace to LTS Converter")
    
    # check if parser_output.txt and generated_rules.sleec exist
    if not os.path.exists('parser_output.txt'):
        st.error("parser_output.txt not found. Please generate the trace first.")
        return
        
    try:
        with open('parser_output.txt', 'r') as f:
            trace_content = f.read()
            
        # convert trace
        lts_content = parse_trace(trace_content)
        
        # show result
        st.subheader("Generated LTS")
        st.code(lts_content)
        
        # add download button
        st.download_button(
            "Download LTS file",
            lts_content,
            "input_lts.aut",
            "text/plain"
        )
    except Exception as e:
        st.error(f"Error processing trace: {str(e)}")

if __name__ == "__main__":
    main()
