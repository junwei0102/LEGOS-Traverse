import streamlit as st
import re
from itertools import combinations

def extract_responses(sleec_content):
    """提取所有规则及其响应，包括unless子句中的响应"""
    rules_dict = {}
    rule_responses = {}
    rules_full_text = {}  # 存储规则的完整文本
    
    # 首先按行分割内容并过滤掉注释行
    valid_lines = []
    for line in sleec_content.split('\n'):
        line = line.strip()
        if line and not line.startswith('//'):
            valid_lines.append(line)
    
    # 重新组合有效行
    valid_content = '\n'.join(valid_lines)
    
    # 修改pattern以匹配任何规则名（在when之前的单词）
    pattern = r'([^\s]+)\s+when\s+.*?then\s+(.*?)(?=(?:[^\s]+\s+when|rule_end|$))'
    rules = re.finditer(pattern, valid_content, re.DOTALL)
    
    for rule in rules:
        rule_text = rule.group(0)
        rule_name = rule.group(1)
        response_text = rule.group(2).strip()
        
        # 存储完整规则文本
        rules_full_text[rule_name] = rule_text.strip()
        rule_responses[rule_name] = []
        
        # 提取主要响应（包括not前缀）
        main_response_match = re.search(r'^\s*((?:not\s+)?\w+)', response_text)
        if main_response_match:
            main_response = main_response_match.group(1).strip()
            if main_response.lower() not in ['and', 'or', 'unless']:
                if main_response not in rules_dict:
                    rules_dict[main_response] = []
                rules_dict[main_response].append(rule_name)
                rule_responses[rule_name].append(main_response)
        
        # 提取unless子句中的响应（包括not前缀）
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
    """找出具有互斥响应的规则组，排除同一规则的响应，考虑度量的完整约束信息"""
    exclusive_groups = []
    processed_responses = set()
    
    # 处理显式声明的互斥对
    for response1, response2 in mutual_exclusive_pairs:
        response1, response2 = response1.strip(), response2.strip()
        if response1 in rules_dict and response2 in rules_dict:
            # 过滤掉来自同一规则的响应
            rules1 = set(rules_dict[response1])
            rules2 = set(rules_dict[response2])
            
            # 移除包含两个响应的规则
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
    """根据规则组生成SLEEC文件，保留度量的完整约束信息，并添加互斥关系声明"""
    # 提取原始文件的def部分
    def_content = ""
    if original_content:
        def_match = re.search(r'def_start(.*?)def_end', original_content, re.DOTALL)
        if def_match:
            def_content = def_match.group(1)
    
    # 如果没有提取到def部分，使用默认的def内容
    if not def_content:
        def_content = """
// 定义measures
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
    
    # 构建SLEEC文件内容
    sleec_content = "def_start\n" + def_content.strip() + "\ndef_end\n\nrule_start\n"
    
    # 用于收集互斥关系的列表
    mutual_exclusive_pairs = []
    
    # 处理不同类型的输入
    if isinstance(groups, list):
        # 如果groups是列表，检查它的元素类型
        if groups and isinstance(groups[0], dict):
            # 处理字典列表（互斥规则组）
            for group_idx, group in enumerate(groups):
                sleec_content += f"// Group {group_idx + 1}\n"
                
                # 收集互斥关系
                responses = list(group.keys())
                if len(responses) == 2:  # 确保有两个响应
                    mutual_exclusive_pairs.append((responses[0], responses[1]))
                
                # 处理每个响应及其规则
                for response, rules in group.items():
                    for rule in rules:
                        # 从完整规则文本中查找匹配的规则
                        rule_name = rule.split()[0]
                        if isinstance(rules_full_text, dict) and rule_name in rules_full_text:
                            # 如果rules_full_text是字典，直接获取规则内容
                            sleec_content += rules_full_text[rule_name] + "\n\n"
                        else:
                            # 如果找不到匹配的规则，使用简化版本
                            sleec_content += f"{rule}\n\n"
                
                sleec_content += "\n"
        else:
            # 处理字符串列表（规则列表）
            for rule in groups:
                sleec_content += rule + "\n\n"
    elif isinstance(groups, dict):
        # 处理字典（共享响应的规则）
        for response, rules in groups.items():
            sleec_content += f"// Response: {response}\n"
            for rule in rules:
                # 从完整规则文本中查找匹配的规则
                rule_name = rule.split()[0]
                if isinstance(rules_full_text, dict) and rule_name in rules_full_text:
                    # 如果rules_full_text是字典，直接获取规则内容
                    sleec_content += rules_full_text[rule_name] + "\n\n"
                else:
                    # 如果找不到匹配的规则，使用简化版本
                    sleec_content += f"{rule}\n\n"
            
            sleec_content += "\n"
    else:
        # 处理字符串（单个规则或内容）
        sleec_content += str(groups) + "\n\n"
    
    sleec_content += "rule_end\n\n"
    
    # 添加互斥关系声明
    if mutual_exclusive_pairs:
        sleec_content += "relation_start\n"
        for response1, response2 in mutual_exclusive_pairs:
            sleec_content += f"mutualExclusive {response1} {response2}\n"
        sleec_content += "relation_end\n"
    
    # 确定文件名
    file_name = "shared_rules.sleec" if is_shared else "exclusive_rules.sleec"
    
    # 写入文件
    with open(file_name, 'w') as f:
        f.write(sleec_content)
    
    return sleec_content  # 返回内容而不是文件名，以便直接使用

def extract_measures_from_def(sleec_content):
    """从定义部分提取所有measures"""
    measures = []
    
    # 提取def部分的内容
    def_match = re.search(r'def_start(.*?)def_end', sleec_content, re.DOTALL)
    if def_match:
        def_content = def_match.group(1)
        # 匹配measure定义行，忽略注释行
        for line in def_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('//'):
                # 匹配measure定义
                match = re.match(r'measure\s+(\w+)\s*:\s*(boolean|numeric)', line)
                if match:
                    measure_name = match.group(1)
                    measure_type = match.group(2)
                    measures.append((measure_name, measure_type))
    
    return measures

def extract_measures(sleec_content):
    """提取所有规则中的measures，包括unless子句中的measures和组合measures，保留完整约束信息"""
    measures_dict = {}  # 存储每个规则的measures
    
    # 修改匹配模式以匹配任何以when开头的规则
    pattern = r'([^\s]+)\s+when\s+(.*?)(?=(?:[^\s]+\s+when|rule_end|$))'
    matches = re.finditer(pattern, sleec_content, re.DOTALL)
    
    for match in matches:
        rule_name = match.group(1)  # 直接使用when前面的标识符作为规则名
        rule_content = match.group(2).strip()
        
        measures = set()
        
        # 处理带not的measures（保留完整的not语义）
        not_measures_matches = re.finditer(r'not\s*\{([^}]+)\}', rule_content)
        for not_match in not_measures_matches:
            measure = not_match.group(1).strip()
            measures.add(f"not_{measure}")  # 添加前缀以区分
        
        # 处理带比较运算符的measures（保留完整的比较信息）
        # 匹配各种比较运算符，包括<, >, =, <=, >=, ≤, ≥
        comp_pattern = r'\{([^}]+)\}\s*([<>]=?|=|≤|≥)\s*(\w+)'
        comp_matches = re.finditer(comp_pattern, rule_content)
        for comp_match in comp_matches:
            measure = comp_match.group(1).strip()
            operator = comp_match.group(2)
            value = comp_match.group(3)
            
            # 标准化操作符
            if operator == '<=':
                operator = '≤'
            elif operator == '>=':
                operator = '≥'
                
            # 使用格式：measure_operator_value，例如：UserAge_<_legalAge
            # 注意：不使用下划线分隔，以便与用户输入格式匹配
            measures.add(f"{measure}{operator}{value}")
        
        # 处理普通布尔measures - 使用两步匹配代替look-behind
        # 首先获取所有花括号中的内容
        all_measures = re.finditer(r'\{([^}]+)\}', rule_content)
        for measure_match in all_measures:
            measure = measure_match.group(1).strip()
            full_match = f"{{{measure}}}"
            
            # 检查这个measure是否是not measure（前面有not）
            is_not_measure = re.search(r'not\s*' + re.escape(full_match), rule_content)
            
            # 检查这个measure是否是比较measure（后面有比较运算符）
            is_comp_measure = re.search(re.escape(full_match) + r'\s*([<>]=?|=|≤|≥)\s*\w+', rule_content)
            
            # 如果既不是not measure也不是比较measure，则是普通布尔measure
            if not is_not_measure and not is_comp_measure:
                measures.add(f"bool_{measure}")
        
        # 处理组合measures（处理括号中的and/or组合）
        combined_pattern = r'\((.*?)\)'
        combined_matches = re.finditer(combined_pattern, rule_content)
        for combined_match in combined_matches:
            combined_content = combined_match.group(1)
            
            # 在组合内容中处理带not的measures
            not_in_combined = re.finditer(r'not\s*\{([^}]+)\}', combined_content)
            for not_match in not_in_combined:
                measure = not_match.group(1).strip()
                measures.add(f"not_{measure}")
            
            # 在组合内容中处理带比较运算符的measures
            comp_in_combined = re.finditer(comp_pattern, combined_content)
            for comp_match in comp_in_combined:
                measure = comp_match.group(1).strip()
                operator = comp_match.group(2)
                value = comp_match.group(3)
                
                # 标准化操作符
                if operator == '<=':
                    operator = '≤'
                elif operator == '>=':
                    operator = '≥'
                    
                # 使用与上面相同的格式
                measures.add(f"{measure}{operator}{value}")
            
            # 在组合内容中处理普通布尔measures - 使用两步匹配
            all_in_combined = re.finditer(r'\{([^}]+)\}', combined_content)
            for measure_match in all_in_combined:
                measure = measure_match.group(1).strip()
                full_match = f"{{{measure}}}"
                
                # 检查这个measure是否是not measure
                is_not_measure = re.search(r'not\s*' + re.escape(full_match), combined_content)
                
                # 检查这个measure是否是比较measure
                is_comp_measure = re.search(re.escape(full_match) + r'\s*([<>]=?|=|≤|≥)\s*\w+', combined_content)
                
                # 如果既不是not measure也不是比较measure，则是普通布尔measure
                if not is_not_measure and not is_comp_measure:
                    measures.add(f"bool_{measure}")
        
        # 清理measures（移除空值和重复项）
        measures = {m for m in measures if m}
        measures_dict[rule_name] = measures
    
    return measures_dict

def find_rules_with_measures(measures_dict, target_measures):
    """找到包含指定measures的规则，考虑度量的完整约束信息"""
    matching_rules = {}
    
    # 将目标measures转换为小写以进行不区分大小写的比较
    target_measures_lower = [m.lower() for m in target_measures]
    
    for rule, measures in measures_dict.items():
        # 将规则的measures转换为小写
        rule_measures_lower = {m.lower() for m in measures}
        
        # 检查每个目标measure是否在规则的measures中，考虑约束信息
        matching_measures = []
        for target in target_measures_lower:
            # 检查是否是完整的约束搜索（包含前缀或操作符）
            is_exact_search = (
                target.startswith("bool_") or 
                target.startswith("not_") or 
                any(op in target for op in ["<", ">", "=", "≤", "≥"])
            )
            
            if is_exact_search:
                # 对于完整约束搜索，尝试标准化操作符并查找匹配
                normalized_target = target
                
                # 标准化操作符
                if "<=" in target:
                    normalized_target = target.replace("<=", "≤")
                elif ">=" in target:
                    normalized_target = target.replace(">=", "≥")
                
                # 处理可能的格式差异（用户可能输入UserAge_<_legalAge或UserAge<legalAge）
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
                
                # 检查原始目标、标准化目标或替代格式是否匹配
                if (target in rule_measures_lower or 
                    normalized_target in rule_measures_lower or 
                    alt_target in rule_measures_lower):
                    # 找到匹配的实际度量（保持原始大小写）
                    for measure in measures:
                        if measure.lower() in [target, normalized_target, alt_target]:
                            matching_measures.append(measure)
                            break
                    else:
                        matching_measures.append(target)  # 如果没找到原始度量，使用目标度量
                continue
                
            # 提取度量的基本名称（不包括约束信息）
            target_base = target.lower()
            
            # 对于基本搜索（没有约束信息），只匹配相同基本名称且约束类型相同的度量
            # 例如：搜索"informationAvailable"只匹配"bool_informationAvailable"，不匹配"not_informationAvailable"
            for measure in rule_measures_lower:
                if measure.startswith("bool_") and measure[5:] == target_base:
                    # 找到匹配的实际度量（保持原始大小写）
                    for orig_measure in measures:
                        if orig_measure.lower() == measure:
                            matching_measures.append(orig_measure)
                            break
                    else:
                        matching_measures.append(f"bool_{target}")
                # 不匹配带not_前缀或数值比较的度量
        
        if matching_measures:
            matching_rules[rule] = matching_measures
    
    return matching_rules

def main():
    st.title("SLEEC Rules Response Analyzer")
    
    # 文件上传或文本输入
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
        # 分析类型选择
        analysis_type = st.radio(
            "Choose analysis type:",
            ["Shared Responses", "Mutually Exclusive Responses", "Shared Measures"]
        )
        
        # 分析规则
        rules_by_response, rule_responses, rules_full_text = extract_responses(sleec_content)
        
        if analysis_type == "Shared Responses":
            # 显示共享响应的规则
            st.subheader("Rules Grouped by Shared Response")
            shared_groups = {resp: rules for resp, rules in rules_by_response.items() 
                           if len(rules) > 1}
            
            for response, rules in shared_groups.items():
                with st.expander(f"Response: {response} ({len(rules)} rules)"):
                    st.write("Rules:", ", ".join(rules))
            
            # 添加导出按钮
            if shared_groups:
                sleec_content_output = generate_sleec_file(shared_groups, rules_full_text, True, sleec_content)
                st.download_button(
                    "Download SLEEC file with shared responses",
                    sleec_content_output,
                    "shared_responses.sleec",
                    "text/plain"
                )
        
        elif analysis_type == "Mutually Exclusive Responses":
            # 互斥响应分析
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
                    
                    # 添加导出按钮
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
            # 直接从def部分提取所有measures
            def_match = re.search(r'def_start(.*?)def_end', sleec_content, re.DOTALL)
            all_measures = []  # 使用列表而不是集合以保持顺序
            
            if def_match:
                def_content = def_match.group(1)
                # 匹配measure定义行，忽略注释行
                for line in def_content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('//'):
                        # 匹配measure定义
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
            
            # 提取规则中的measures用于搜索
            measures_dict = extract_measures(sleec_content)
            
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
                    
                    # 添加导出按钮
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