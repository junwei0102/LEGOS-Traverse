import streamlit as st
import re
import os
from collections import defaultdict

def extract_measures_from_def(rules_content):
    """从def_start和def_end之间提取所有measure定义"""
    measures_info = {}
    
    # 提取def部分
    def_match = re.search(r'def_start(.*?)def_end', rules_content, re.DOTALL)
    if def_match:
        def_content = def_match.group(1)
        print(f"Def content: {def_content}")  # 调试输出
        
        # 查找所有measure定义行
        measure_lines = re.finditer(r'^\s*measure\s+(\w+)\s*:\s*(boolean|numeric)\s*$', 
                                  def_content, 
                                  re.MULTILINE | re.IGNORECASE)
        
        for match in measure_lines:
            measure_name = match.group(1)
            measure_type = match.group(2).lower()
            measures_info[measure_name] = {
                'type': measure_type,
                'events': set()  # 存储使用这个measure的事件
            }
            print(f"Found measure: {measure_name} of type {measure_type}")  # 调试输出
    
    print(f"All measures found: {measures_info}")  # 调试输出
    return measures_info

def build_event_measure_map(rules_content):
    """构建事件和其相关measures的映射"""
    event_measure_map = defaultdict(lambda: {'bool': set(), 'not_bool': set(), 'numeric': set()})
    
    try:
        # 跳过注释行和空行
        valid_lines = []
        for line in rules_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('//'):
                valid_lines.append(line)
        
        rules_content = '\n'.join(valid_lines)
        print(f"Processed rules content:\n{rules_content}")  # 调试输出
        
        # 匹配规则模式：规则名 when 条件 then 响应 [unless 条件 then 响应]*
        rules = re.finditer(r'([^\s]+)\s+when\s+(.*?)\s+then\s+([^\n]*?)(?:\s+unless\s+(.*?)(?:\s+then\s+([^\n]*))?)?$',
                           rules_content,
                           re.MULTILINE)
        
        for rule in rules:
            rule_name = rule.group(1)
            condition = rule.group(2)
            unless_condition = rule.group(4)
            
            print(f"\nProcessing rule: {rule_name}")  # 调试输出
            print(f"Main condition: {condition}")  # 调试输出
            if unless_condition:
                print(f"Unless condition: {unless_condition}")  # 调试输出
            
            # 提取触发事件（在when之后的第一个词）
            event_match = re.search(r'([A-Z][a-zA-Z]+)', condition)
            if not event_match:
                continue
                
            trigger_event = event_match.group(1)
            
            def process_condition(condition_str, target_event=None):
                # 如果没有指定目标事件，使用触发事件
                if target_event is None:
                    target_event = trigger_event
                    
                # 首先处理否定布尔值，因为它们的模式最具体
                not_bool_matches = re.finditer(r'not\s+\{([^}]+)\}', condition_str)
                for match in not_bool_matches:
                    measure = match.group(1)
                    print(f"Found not_bool measure: {measure} for event {target_event}")  # 调试输出
                    event_measure_map[target_event]['not_bool'].add(measure)
                
                # 处理数值比较 - 修改正则表达式以匹配变量名作为值
                numeric_matches = re.finditer(r'\{([^}]+)\}\s*([<>=]+)\s*(\w+)', condition_str)
                for match in numeric_matches:
                    measure = match.group(1)
                    operator = match.group(2)
                    value = match.group(3)
                    print(f"Found numeric measure: {measure} {operator} {value} for event {target_event}")  # 调试输出
                    # 将度量和操作符添加到事件的numeric集合中
                    event_measure_map[target_event]['numeric'].add((measure, operator, value))
                
                # 最后处理普通布尔值
                # 获取所有measure引用
                all_measures = re.finditer(r'\{([^}]+)\}', condition_str)
                for match in all_measures:
                    measure = match.group(1)
                    # 检查这个measure是否已经被处理为not_bool或numeric
                    is_not_bool = f"not {{{measure}}}" in condition_str
                    is_numeric = re.search(rf'\{{{measure}\}}\s*[<>=]+\s*\w+', condition_str)
                    
                    if not is_not_bool and not is_numeric:
                        print(f"Found bool measure: {measure} for event {target_event}")  # 调试输出
                        event_measure_map[target_event]['bool'].add(measure)
            
            # 处理主条件
            process_condition(condition)
            
            # 处理unless条件 - 确保将触发事件传递给process_condition
            if unless_condition:
                process_condition(unless_condition, trigger_event)
            
            print(f"Current measures for {trigger_event}: {dict(event_measure_map[trigger_event])}")  # 调试输出
    
    except Exception as e:
        print(f"Error in build_event_measure_map: {str(e)}")
        raise
    
    print(f"\nFinal event_measure_map: {dict(event_measure_map)}")  # 调试输出
    return dict(event_measure_map)

def extract_measures_from_selected_rules():
    """从selected_rules.txt中提取每个事件需要的measures"""
    event_measures_dict = defaultdict(lambda: {'bool': set(), 'not_bool': set(), 'numeric': set()})
    
    try:
        # 首先从generated_rules.sleec中获取所有已定义的measures
        with open('generated_rules.sleec', 'r') as f:
            rules_content = f.read()
            all_measures = extract_measures_from_def(rules_content)
            print(f"All defined measures: {all_measures}")  # 调试输出
        
        # 从selected_rules.txt中读取规则
        with open('selected_rules.txt', 'r') as f:
            rules = f.readlines()
        
        for rule in rules:
            rule = rule.strip()
            if not rule:
                continue
            
            # 更新规则匹配模式以包含unless条件
            match = re.match(r'([^\s]+)\s+when\s+(.*?)\s+then\s+([^u\n]*?)(?:\s+unless\s+(.*?)(?:\s+then\s+([^\n]*)))?$', rule)
            if not match:
                continue
            
            rule_name, condition, response = match.group(1), match.group(2), match.group(3)
            unless_condition = match.group(4) if match.group(4) else None
            unless_response = match.group(5) if match.group(5) else None
            
            # 处理主条件中的measures
            process_condition_measures(condition, event_measures_dict, all_measures)
            
            # 处理unless条件中的measures（如果存在）
            if unless_condition:
                process_condition_measures(unless_condition, event_measures_dict, all_measures)
            
            print(f"Processing rule: {rule_name}")  # 调试输出
            print(f"Main condition: {condition}")
            if unless_condition:
                print(f"Unless condition: {unless_condition}")
    
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return {}
    
    return dict(event_measures_dict)

def process_condition_measures(condition, event_measures_dict, all_measures):
    """处理条件中的measures并更新event_measures_dict"""
    # 处理布尔measures
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
    
    # 处理数值measures - 修改正则表达式以匹配变量名作为值
    numeric_matches = re.finditer(r'\{([^}]+)\}\s*([<>=!]+)\s*(\w+)', condition)
    for match in numeric_matches:
        measure = match.group(1)
        operator = match.group(2)
        value = match.group(3)
        
        # 检查值是否是数字或变量名
        try:
            value = int(value)
        except ValueError:
            # 如果不是数字，保留为字符串（变量名）
            pass
            
        if measure in all_measures:
            for event in all_measures[measure]['events']:
                event_measures_dict[event]['numeric'].add((measure, operator, value))

def check_measure_condition(measure_value, operator, target_value):
    """检查measure值是否满足条件"""
    try:
        value = int(measure_value)
        
        # 如果target_value是字符串且不是数字，可能是变量名（如legalAge）
        # 在这种情况下，我们需要查找该变量的值
        if isinstance(target_value, str) and not target_value.isdigit():
            # 这里假设legalAge = 18，你可以根据实际情况修改
            if target_value == 'legalAge':
                target_value = 18
            else:
                # 对于其他变量，可以添加更多的映射
                print(f"Warning: Unknown variable {target_value}, using default comparison")
                return True  # 默认返回True以包含该度量
        else:
            # 确保target_value是整数
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
        # 如果measure_value不是数字，默认返回True以包含该度量
        print(f"Warning: Non-numeric measure value {measure_value}, using default comparison")
        return True

def filter_measures(measures_str, required_measures):
    """只保留规则中需要的measures"""
    if not measures_str or not required_measures:
        return ""
    
    # 将measures字符串拆分成键值对
    measures_dict = {}
    for pair in measures_str.split(', '):
        if '=' in pair:
            key, value = pair.split('=', 1)
            measures_dict[key.strip()] = value.strip()
    
    filtered_pairs = []
    
    # 处理布尔值measures
    for measure in required_measures['bool']:
        if measure in measures_dict:
            filtered_pairs.append(f"{measure}={measures_dict[measure]}")
    
    # 处理带not的布尔measures
    for measure in required_measures.get('not_bool', set()):
        if measure in measures_dict:
            value = measures_dict[measure].lower()
            # 如果原始值为False，则这个not条件满足
            if value == 'false':
                filtered_pairs.append(f"{measure}={value}")
    
    # 处理数值比较measures
    for measure_tuple in required_measures['numeric']:
        if len(measure_tuple) == 3:
            measure_name, operator, target_value = measure_tuple
            if measure_name in measures_dict:
                value = measures_dict[measure_name]
                # 始终包含数值比较的度量，无论它是否满足条件
                # 这确保了像UserAge这样的重要度量总是被包含在事件参数中
                filtered_pairs.append(f"{measure_name}={value}")
    
    return ", ".join(filtered_pairs)

def parse_measure(measure_line):
    """解析Measure行中的参数"""
    match = re.search(r'Measure\((.*?)\)', measure_line)
    if match:
        return match.group(1)
    return ""

def parse_trace(trace_content):
    """解析trace内容并转换为LTS格式"""
    try:
        # 从规则文件中构建事件-measure映射
        with open('generated_rules.sleec', 'r') as f:
            rules_content = f.read()
            event_measure_map = build_event_measure_map(rules_content)
            print(f"Event-measure map: {event_measure_map}")
        
        current_state = 0
        next_state = 1
        transitions = []
        measures_by_time = {}
        events_by_time = {}
        
        # 解析trace中的事件和measures
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
            
            # 处理Measure行
            if action.startswith('Measure'):
                measure_match = re.search(r'Measure\((.*?)\)', action)
                if measure_match:
                    measure_pairs = measure_match.group(1).split(', ')
                    current_measures.clear()  # 清除之前的measures
                    for pair in measure_pairs:
                        if '=' in pair:
                            key, value = pair.split('=')
                            current_measures[key.strip()] = value.strip()
                    measures_by_time[time] = current_measures.copy()
                    print(f"Time {time} measures: {current_measures}")
            # 处理事件
            elif not action.startswith('blocked_'):
                if action.endswith('()'):
                    action = action[:-2]
                events_by_time[time].append(action)
        
        # 生成LTS转换
        for time in sorted(events_by_time.keys(), key=int):
            current_measures = measures_by_time.get(time, measures_by_time.get(str(int(time)-1), {}))
            print(f"\nProcessing time {time} with measures: {current_measures}")
            
            for event in events_by_time[time]:
                event_name = event.split('(')[0]
                needed_measures = []
                
                # 检查是否是触发事件（在event_measure_map中）
                if event_name in event_measure_map:
                    print(f"Processing event {event_name} with map: {event_measure_map[event_name]}")
                    
                    # 处理布尔measures
                    for measure in event_measure_map[event_name]['bool']:
                        if measure in current_measures and current_measures[measure].lower() == 'true':
                            needed_measures.append(f"{measure}={current_measures[measure]}")
                            print(f"Added bool measure: {measure}={current_measures[measure]}")
                    
                    # 处理否定布尔measures
                    for measure in event_measure_map[event_name]['not_bool']:
                        if measure in current_measures and current_measures[measure].lower() == 'false':
                            needed_measures.append(f"{measure}={current_measures[measure]}")
                            print(f"Added not_bool measure: {measure}={current_measures[measure]}")
                    
                    # 处理数值measures
                    for measure_name, operator, target_value in event_measure_map[event_name]['numeric']:
                        if measure_name in current_measures:
                            current_value = current_measures[measure_name]
                            if check_measure_condition(current_value, operator, target_value):
                                needed_measures.append(f"{measure_name}={current_value}")
                                print(f"Added numeric measure: {measure_name}={current_value}")
                
                # 构建事件字符串
                measures_str = ', '.join(sorted(needed_measures)) if needed_measures else ''
                if measures_str:
                    action = f"{event}({measures_str}, time={time})"
                else:
                    action = f"{event}(time={time})"
                
                print(f"Final action: {action}")
                transitions.append((current_state, action, next_state))
                current_state = next_state
                next_state += 1
        
        # 生成LTS描述
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
    
    # 检查是否存在parser_output.txt和generated_rules.sleec
    if not os.path.exists('parser_output.txt'):
        st.error("parser_output.txt not found. Please generate the trace first.")
        return
        
    try:
        with open('parser_output.txt', 'r') as f:
            trace_content = f.read()
            
        # 转换trace
        lts_content = parse_trace(trace_content)
        
        # 显示结果
        st.subheader("Generated LTS")
        st.code(lts_content)
        
        # 添加下载按钮
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
