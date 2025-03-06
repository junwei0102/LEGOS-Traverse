import streamlit as st
import subprocess
import sys
import os
import json
import time

# 设置页面配置
st.set_page_config(
    page_title="SLEEC Rules Analysis Pipeline",
    layout="wide",  # 使用宽布局
    initial_sidebar_state="auto",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# 添加自定义CSS来优化滚动条和布局
st.markdown("""
    <style>
        .main .block-container {
            max-width: 95%;  # 增加内容区域宽度
            padding-top: 1rem;
            padding-bottom: 1rem;
        }
        .stApp {
            overflow-x: auto;
            overflow-y: auto;
        }
        .element-container {
            overflow: auto;
            max-height: none !important;
        }
        .streamlit-expanderContent {
            overflow: auto;
            max-height: 500px;  # 设置展开内容的最大高度
        }
    </style>
""", unsafe_allow_html=True)

# Add LEGOs directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
legos_dir = os.path.join(current_dir, "LEGOs")
analyzer_dir = os.path.join(legos_dir, "Analyzer")
sys.path.append(legos_dir)
sys.path.append(analyzer_dir)

from translator import parse_trace
from rules import extract_responses, extract_measures, find_mutually_exclusive_rules, find_rules_with_measures, generate_sleec_file, extract_measures_from_def
from legos_integration import generate_lts_from_sleec
from LEGOs.Analyzer.analyzer import check_property_refining, clear_all, log_fol_formula

def run_pipeline():
    st.title("SLEEC Rules Analysis and LTS Generation Pipeline")
    
    # Step 1: SLEEC Rules Analysis under Coverage Criteria
    st.header("Step 1: SLEEC Rules Analysis under Coverage Criteria")
    input_method = st.radio(
        "Choose Input Method",
        ["Upload SLEEC File", "Enter SLEEC Content"]
    )
    
    sleec_content = ""
    sleec_file_path = None
    if input_method == "Upload SLEEC File":
        uploaded_file = st.file_uploader("Upload SLEEC File", type=['sleec', 'txt'])
        if uploaded_file:
            sleec_content = uploaded_file.getvalue().decode()
            # Save uploaded file
            sleec_file_path = "temp_rules.sleec"
            with open(sleec_file_path, "w") as f:
                f.write(sleec_content)
    else:
        sleec_content = st.text_area(
            "Enter SLEEC Rules:",
            height=300,
            placeholder="Rule1 when ... then ...\nRule2 when ... then ..."
        )
        if sleec_content:
            # Save input content
            sleec_file_path = "temp_rules.sleec"
            with open(sleec_file_path, "w") as f:
                f.write(sleec_content)
    
    if sleec_content:
        # Analysis type selection
        analysis_type = st.radio(
            "Choose Coverage Criteria",
            ["Shared Responses", "Mutually Exclusive Responses", "Shared Measures"]
        )
        
        # Analyze rules
        rules_by_response, rule_responses, rules_full_text = extract_responses(sleec_content)
        
        # 显示原始内容
        with st.expander("Show Original SLEEC Content"):
            st.code(sleec_content)
        
        if analysis_type == "Shared Responses":
            # Display rules with shared responses
            st.subheader("Rules Grouped by Shared Response")
            shared_groups = {resp: rules for resp, rules in rules_by_response.items() 
                           if len(rules) > 1}
            
            # 添加用户选择部分
            selected_groups = {}
            for response, rules in shared_groups.items():
                with st.expander(f"Response: {response} ({len(rules)} rules)"):
                    # 分别显示主要响应和unless子句中的响应
                    main_rules = [r for r in rules if " (unless)" not in r]
                    unless_rules = [r.replace(" (unless)", "") for r in rules if " (unless)" in r]
                    
                    if main_rules:
                        st.write("Main Response Rules:", ", ".join(main_rules))
                        st.write("Full Rule Content (Main Response):")
                        for rule in main_rules:
                            if rule in rules_full_text:
                                st.code(rules_full_text[rule])
                    
                    if unless_rules:
                        st.write("\nUnless Clause Rules:", ", ".join(unless_rules))
                        st.write("Full Rule Content (Unless Clause):")
                        for rule in unless_rules:
                            if rule in rules_full_text:
                                st.code(rules_full_text[rule])
                    
                    # 添加复选框让用户选择是否包含这组规则，默认选中
                    if st.checkbox(f"Include rules with response '{response}'", value=True, key=f"include_{response}"):
                        selected_groups[response] = rules
            
            # Save analysis result to session state
            if selected_groups:  # 使用用户选择的组而不是所有组
                st.session_state['analysis_result'] = {
                    'type': 'shared_responses',
                    'groups': selected_groups,  # 使用选中的组
                    'rules_full_text': rules_full_text
                }
                # 显示生成的SLEEC文件内容
                sleec_output = generate_sleec_file(selected_groups, rules_full_text, True, sleec_content)
                with st.expander("Show Generated SLEEC File Content"):
                    st.code(sleec_output)
                # 保存生成的文件
                with open("generated_rules.sleec", "w") as f:
                    f.write(sleec_output)
                st.success("Generated SLEEC file saved as 'generated_rules.sleec'")
        
        elif analysis_type == "Mutually Exclusive Responses":
            # Mutually exclusive response analysis
            st.subheader("Define Mutually Exclusive Responses")
            
            num_pairs = st.number_input("Number of Mutually Exclusive Pairs", min_value=1, value=1)
            
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
                                    st.write("Full Rule Content:")
                                    for rule in rules:
                                        rule_name = rule.split()[0]
                                        if rule_name in rules_full_text:
                                            st.code(rules_full_text[rule_name])
                    
                    # Save analysis result to session state
                    st.session_state['analysis_result'] = {
                        'type': 'mutually_exclusive',
                        'groups': exclusive_groups,
                        'rules_full_text': rules_full_text
                    }
                    # 显示生成的SLEEC文件内容
                    sleec_output = generate_sleec_file(exclusive_groups, rules_full_text, False, sleec_content)
                    with st.expander("Show Generated SLEEC File Content"):
                        st.code(sleec_output)
                    # 保存生成的文件
                    with open("generated_rules.sleec", "w") as f:
                        f.write(sleec_output)
                    st.success("Generated SLEEC file saved as 'generated_rules.sleec'")
                else:
                    st.info("No valid mutually exclusive rules found")
        
        elif analysis_type == "Shared Measures":
            # Extract measures from definitions
            defined_measures = extract_measures_from_def(sleec_content)
            
            # Extract measures from rules
            measures_dict = extract_measures(sleec_content)
            all_measures_in_rules = set()
            for measures in measures_dict.values():
                all_measures_in_rules.update(measures)
            
            st.subheader("Available Measures")
            if defined_measures:
                st.write("Measures found in definitions:")
                for measure_name, measure_type in defined_measures:
                    st.write(f"- {measure_name} ({measure_type})")
            else:
                st.write("No measures found in definitions")
            
            with st.expander("Measures used in rules"):
                st.write(", ".join(sorted(all_measures_in_rules)))
                st.markdown("""
                ### Search Instructions:
                - Boolean measures: Enter the measure name directly, e.g., `informationAvailable`
                - Negated boolean measures: Use the `not_` prefix, e.g., `not_informationAvailable`
                - Numeric comparison measures: Use comparison operators, e.g., `UserAge<legalAge` or `severityOfState>StateThreshold`
                
                You can copy measure names directly from the "Measures used in rules" list above for searching.
                """)
            
            measure_input = st.text_area(
                "Enter measures to search (one per line):",
                placeholder="userPayingAttention\nnot_informationAvailable\nUserAge<legalAge\nseverityOfState>StateThreshold"
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
                    
                    # Save analysis result to session state
                    st.session_state['analysis_result'] = {
                        'type': 'shared_measures',
                        'matching_rules': matching_rules,
                        'target_measures': target_measures,
                        'rules_full_text': rules_full_text
                    }
                    
                    # 生成SLEEC文件内容
                    content = []
                    content.append("// Rules sharing specified measures:")
                    for measure in target_measures:
                        content.append(f"// {measure}")
                    for rule in matching_rules:
                        if rule in rules_full_text:
                            content.append(rules_full_text[rule])
                    
                    # 保存生成的文件
                    sleec_output = generate_sleec_file(content, rules_full_text, True, sleec_content)
                    
                    with st.expander("Show Generated SLEEC File Content"):
                        st.code(sleec_output)
                    with open("generated_rules.sleec", "w") as f:
                        f.write(sleec_output)
                    st.success(f"Generated SLEEC file saved as 'generated_rules.sleec'")
                else:
                    st.info("No rules found with the specified measures")
        
        # Step 2: Trace Generation
        if 'analysis_result' in st.session_state:
            st.header("Step 2: Trace Generation")
            
            # Set time window
            time_window = st.number_input(
                "Set Time Window (seconds)",
                min_value=1,
                value=15,
                help="Set the time window for trace generation"
            )
            
            if st.button("Generate Trace"):
                with st.spinner("Generating trace..."):
                    try:
                        # Use LEGOS to generate trace
                        if generate_lts_from_sleec("generated_rules.sleec", time_window):
                            st.success("Successfully generated trace!")
                            
                            # Display SLEEC format trace
                            with st.expander("View SLEEC Format Trace"):
                                try:
                                    with open('parser_output.txt', 'r') as f:
                                        trace_content = f.read()
                                    st.text(trace_content)
                                except Exception as e:
                                    st.error(f"Error reading trace file: {str(e)}")
                            
                            # Use translator to convert trace to LTS
                            try:
                                with open('parser_output.txt', 'r') as f:
                                    trace_content = f.read()
                                lts = parse_trace(trace_content)
                            except Exception as e:
                                st.error(f"Error converting trace to LTS: {str(e)}")
                                return
                                
                            # Save trace content to session state
                            st.session_state['trace_content'] = trace_content
                            st.session_state['lts'] = lts
                            st.session_state['trace_generated'] = True
                            
                            # Display generated LTS
                            st.subheader("Generated LTS")
                            st.code(lts)
                            
                            # Save LTS to file for augment.py
                            try:
                                with open('input_lts.aut', 'w') as f:
                                    f.write(lts)
                                st.success("LTS saved to input_lts.aut")
                                
                                # Directly run augment.py
                                st.success("Starting LTS Augmentation...")
                                subprocess.run(["streamlit", "run", "augment.py"])
                                
                            except Exception as e:
                                st.error(f"Error saving LTS to file: {str(e)}")
                                return
                            
                        else:
                            st.error("Failed to generate trace.")
                            
                    except Exception as e:
                        st.error(f"Error in trace generation: {str(e)}")
                        print(f"Detailed error: {str(e)}")

            # Clean up temporary files
            if os.path.exists(sleec_file_path):
                os.remove(sleec_file_path)

if __name__ == "__main__":
    run_pipeline() 