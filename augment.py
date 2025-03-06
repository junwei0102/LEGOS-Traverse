import streamlit as st
import os
import sys
from openai import OpenAI
import re
import subprocess
import fal_client
import json
import time  # 添加time模块
# for image generation
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import tempfile
import zipfile

# Set page config
st.set_page_config(
    page_title="LTS Augmentation",
    page_icon="",
    layout="wide",
    initial_sidebar_state="auto"
)

# 添加自定义CSS来优化滚动条和布局
st.markdown("""
    <style>
        .main .block-container {
            max-width: 95%;
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
            max-height: none !important;
        }
        div[data-testid="stVerticalBlock"] {
            gap: 0rem;
        }
        .stButton button {
            width: 100%;
        }
        .pagination-container {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 1rem;
            margin: 1rem 0;
        }
        .pagination-button {
            min-width: 100px;
        }
        .pagination-text {
            min-width: 200px;
            text-align: center;
            font-size: 1.2em;
            padding: 0.5rem;
            background-color: #f0f2f6;
            border-radius: 4px;
            margin: 0 1rem;
        }
    </style>
""", unsafe_allow_html=True)

# Check if we should run this page
if not os.path.exists('input_lts.aut'):
    st.error("No input LTS file found. Please generate a trace first.")
    st.stop()

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state['initialized'] = True
    st.session_state['current_page'] = 0
    st.session_state['character_scene_prompts'] = None
    st.session_state['character_image_url'] = None
    st.session_state['generated_scenes'] = None
    st.session_state['scene_evaluations'] = None
    st.session_state['api_choice'] = 'OpenAI'  # 默认使用 OpenAI
    st.session_state['page_key'] = 0  # 添加页面键以避免重复渲染

# 在文件开头的import部分后添加
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"

def get_translated_lts():
    """获取已转换的LTS内容"""
    try:
        if os.path.exists('input_lts.aut'):
            with open('input_lts.aut', 'r') as f:
                content = f.read()
                if content.strip():
                    return content
                else:
                    st.error("input_lts.aut is empty")
                    return ""
        else:
            st.error("input_lts.aut file not found. Please generate the trace first.")
            return ""
    except Exception as e:
        st.error(f"Error reading input_lts.aut: {str(e)}")
        return ""

def save_to_files(original_lts, augmented_response, col2):
    # Save augmented LTS to session state for reference
    st.session_state.current_augmented_lts = augmented_response
    
    # Extract augmented LTS
    augmented_lts = extract_augmented_lts(augmented_response)
    if not augmented_lts:
        st.error("Failed to extract augmented LTS from response")
        return
        
    # Save to files
    with open("l1.aut", "w") as f:
        f.write(original_lts)
    with open("l2.aut", "w") as f:
        f.write(augmented_lts)
        
    # Extract mapping and scene info
    mapping = extract_mapping(augmented_response)
    scene_info = extract_scene_info(augmented_response)
    
    # Save mapping
    if mapping:
        with open("rename.ren", "w") as f:
            f.write(mapping)
            
    # Save scene info
    if scene_info:
        with open("augment_image.txt", "w") as f:
            f.write(scene_info)
    
    # Display in UI
    with col2:
        st.subheader("Augmented LTS")
        st.text(augmented_lts)

def extract_augmented_lts(response):
    # Find content after "Augmented LTS:" until encountering "Mapping:"
    lts_pattern = r'Augmented LTS:\s*(des.*?)(?=\s*Mapping:|$)'
    lts_match = re.search(lts_pattern, response, re.DOTALL)
    
    if lts_match:
        return lts_match.group(1).strip()
    
    st.error("Failed to extract augmented LTS from response")
    return None

def extract_mapping(response):
    # Find content after "Mapping:" until encountering an empty line or end of file
    mapping_pattern = r'Mapping:\s*(.*?)(?=\s*\n\s*\n|$)'
    mapping_match = re.search(mapping_pattern, response, re.DOTALL)
    
    if mapping_match:
        # Extract all mapping lines and clean format
        mapping_text = mapping_match.group(1).strip()
        # Remove possible markdown markers
        mapping_text = re.sub(r'\*\*|```', '', mapping_text)
        # Split into lines and filter out empty lines
        lines = [line.strip() for line in mapping_text.split('\n') if line.strip()]
        if lines:
            return '\n'.join(lines)
    
    st.error("Failed to extract mapping from response")
    return None

def extract_scene_info(response):
    """从响应中提取场景标签和时间信息"""
    try:
        # 首先找到"Scene Label and Time:"部分
        scene_section_pattern = r'Scene Label and Time:(.*?)(?=\n\s*\n|Verification & Justification|$)'
        scene_section = re.search(scene_section_pattern, response, re.DOTALL)
        
        if not scene_section:
            st.error("Could not find Scene Label and Time section")
            return None
            
        # 提取所有场景信息
        scene_lines = scene_section.group(1).strip().split('\n')
        # 过滤并清理每一行
        scene_info = [line.strip() for line in scene_lines if line.strip() and line.strip().startswith('Scene')]
        
        if not scene_info:
            st.error("No valid scene information found")
            return None
            
        # 返回所有场景信息
        return '\n'.join(scene_info)
        
    except Exception as e:
        st.error(f"Error extracting scene info: {str(e)}")
        return None

def generate_prompt(input_lts):
    # 获取案例研究上下文（如果有）
    case_study_context = st.session_state.get('case_study_context', '')
    
    # 如果有上下文，添加到提示中
    context_section = ""
    if case_study_context:
        context_section = f"""
## Case Study Context:
{case_study_context}

"""
    
    return f"""
TASK: Augment the given Labelled Transition System (LTS) with Norm-Aware, Time-Sensitive, and Contextually Verified Transitions.

Input LTS:
{input_lts}
Context for case study for reference:
{context_section}
## Objective:
1. Enhance LTS with **explicit and realistic timing (e.g., 6:30am, 7:26pm), norm-based constraints, and contextual information**.
2. Ensure **safety properties** are maintained.
3. Ensure des (start state, transitions number, end state) aligns with the augmented LTS.
4. Preserve **behavioral equivalence** with the original LTS.
5. Provide **a direct and structured augmented LTS output**.
6. Provide mapping between original and augmented transitions.

### Critical Timing Requirement:
- **Choose a realistic starting time based on the context and nature of events** (e.g., medical procedures might start at 8:00am or 9:00am, not 6:30am unless specifically required).
- **All original transitions in the input LTS with the same pseudo time=X in the measures must have the same augmented time.**
    - For example, if two original transitions both have time=0 in the measures in input LTS, they must both be augmented with the same time, such as [CLOCK: 8:00am].
    - If an event has time=300, it must occur exactly 5 minutes after events with time=0.
    - This is **highly important** and must be strictly followed, even if state transition seems to not happen at the same time.
- **Use realistic waiting times between events** that reflect the actual time needed for such activities.

### Formal Requirements:
1. Timing Consistency:
   - Choose a contextually appropriate starting time based on the nature of the events and environment.
   - All state transitions must follow a non-decreasing temporal ordering. That is, the next transition must happen after the previous one or at the same time when they have the same pseudo time=X in the measures in original LTS.
   - Introduce contextual waiting times where appropriate that reflect realistic durations (e.g., time to dress before opening the window, time for a medical procedure).
   - Differentiate between simultaneous vs. sequential events.
   - Events with time=X must occur exactly X seconds after events with time=0.
   - New transitions must not add time=X in the measures. Maintaining non-decreasing temporal ordering is enough.
   - Time=X is only allowed in original transitions.
   - For augmented original transitions and new transitions, you must add [CLOCK: time] in the augmented transition label.
   - The [CLOCK: time] in the next transition must be later or equal to the [CLOCK: time] in the previous transition.
   - You should pick appropriate and realistic time for the augmented transition label, both starting time and duration tima and time difference between events.

2. Social Norm Adherence (NORMBANK Framework):
   - Assign each action one of the following norm labels:
     - expected: Commonly accepted behavior.
     - okay: Permissible but context-dependent.
     - unexpected: Forbidden or socially inappropriate.
   - Use SCENE constraints:
     - Setting (e.g., home, office, hospital)
     - Environment (e.g., morning, crowded, quiet)
     - Roles (e.g., user, robot, assistant)
     - Attributes (e.g., age, health condition, preferences)
     - Behaviors (e.g., requesting, waiting, interacting)
   - Ensure unexpected behaviors are justified or corrected via AI intervention.

3. Safety & Traceability:
   - State Invariants: Critical safety properties (e.g., dressing before opening the window) must hold.
   - Behavioral Equivalence: Augmented LTS must remain trace-equivalent to the original.
   - Explainability: Each transition must be logically justified and documented.

4. Rename Policy:
   - When augmenting existing transitions, you must keep the name of the transition the same.
   - You must write the exactly same augmented transition label and original transition label in the mapping section (i.e., space and case sensitive), or else the rename operation won't detect the mapping correctly.

5. Formatting Requirements:
   - To add realistic timing, you must add [CLOCK: time] in the augmented transition label. Remember to have space between CLOCK and time. This must also be followed in the mapping section.
   - To add norm-based constraints, you must add (norm_label) in the augmented transition label. This must also be followed in the mapping section.
   - Every measure must be split by a comma and space, i.e., measure1, measure2, measure3. This must also be followed in the mapping section.

6. The Criteria for Adding New Transitions:
   - A new transition should be added if it makes the LTS more realistic and norm-compliant.
   - A new transition should be added if it makes the LTS more trace-equivalent to the original LTS.
   - When adding new transitions with new events, ensure event name and meaures should be different and meaningful so it could help to make scenarios transition more realistic and norm-compliant, i.e. please pick appropriate event name and measures.

###Approach - CLOCK-BASED TIMING (Norm-Aware Augmentation)
Example1:
Input LTS:
des (0,3,4)
(0, "UserRequestMakingCoffee (kitchenLightOn=false, coffeeBeansAvailable=true, userPreferredTemp=75)",1)
(1, "TurnOnKitchenLight (kitchenLightOn=false, coffeeBeansAvailable=true, userPreferredTemp=75)",2)
(2, "MakeCoffee (kitchenLightOn=true, coffeeBeansAvailable=true, userPreferredTemp=75)",3)

Expected Output (Please strictly follow the format and ensure to add Augmented LTS: and Mapping: and Scene Label and Time: in the output so to parse them to three parts easily)
Augmented LTS:
des (0,6,7)
(0, "UserWokeUp (location=kitchen, userAwake=true, kitchenLightOn=false, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 8:00am] (expected)",1)
(1, "UserRequestMakingCoffee (location=kitchen, userAwake=true, kitchenLightOn=false, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 8:05am] (unexpected - user is in the dark)",2)
(2, "RobotSuggestTurningOnKitchenLight (location=kitchen, userAwake=true, kitchenLightOn=false, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 8:06am] (expected)",3)
(3, "UserAgreeToTurnOnKitchenLight (location=kitchen, userAwake=true, kitchenLightOn=false, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 8:07am] (okay)",4)
(4, "TurnOnKitchenLight (location=kitchen, userAwake=true, kitchenLightOn=true, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 8:08am] (expected)",5)
(5, "MakeCoffee (location=kitchen, userAwake=true, kitchenLightOn=true, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 8:15am] (expected)",6)

Mapping: (map augmented transitions to original transitions(must write the complete original transition label), map new transitions to i(invisible transitions))
"UserWokeUp (location=kitchen, userAwake=true, kitchenLightOn=false, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 8:00am] (expected)" -> "i"
"UserRequestMakingCoffee (location=kitchen, userAwake=true, kitchenLightOn=false, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 8:05am] (unexpected - user is in the dark)" -> "UserRequestMakingCoffee (kitchenLightOn=false,coffeeBeansAvailable=true,userPreferredTemp=75)"
"RobotSuggestTurningOnKitchenLight (location=kitchen, userAwake=true, kitchenLightOn=false, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 8:06am] (expected)" -> "i"
"UserAgreeToTurnOnKitchenLight (location=kitchen, userAwake=true, kitchenLightOn=false, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 8:07am] (okay)" -> "i"
"TurnOnKitchenLight (location=kitchen, userAwake=true, kitchenLightOn=true, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 8:08am] (expected)" -> "TurnOnKitchenLight (kitchenLightOn=true,coffeeBeansAvailable=true,userPreferredTemp=75)"
"MakeCoffee (location=kitchen, userAwake=true, kitchenLightOn=true, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 8:15am] (expected)" -> "MakeCoffee (kitchenLightOn=true,coffeeBeansAvailable=true,userPreferredTemp=75)"

Scene Label and Time:
Scene 1: UserWokeUp 8:00am
Scene 2: UserRequestMakingCoffee 8:05am
Scene 3: RobotSuggestTurningOnKitchenLight 8:06am
Scene 4: UserAgreeToTurnOnKitchenLight 8:07am
Scene 5: TurnOnKitchenLight 8:08am
Scene 6: MakeCoffee 8:15am

Example2: (Case when we have time=X in the measures for original transitions. Remember when adding new transitions, you must not add time=X in the measures; Remember added [CLOCK: time] for original transitions with same pseudo time=X in the measures must be the same in augmented LTS)
Input LTS:
des (0, 5, 6)
(0, "UserDriving(hearRateVariability=low, eyeMovements=low1, fullAttentionNeeded=False, properlyPlaced=False, informationImportant=False, health=False, hasLicense=False, substanceUse=False, commonLanguage=False, userUnderstands=False, sameCity=False, rulesFollowed=False, objectNearby=False, userNotice=False, blindSpot=True, obtainConsent=False, needsAccomodation=False, userImpaired=False, warningSignalOff=False, userGivesControl=False, decisionPoint=False, time=0)", 1)
(1, "TrackMetrics(hearRateVariability=low, eyeMovements=low1, fullAttentionNeeded=False, properlyPlaced=False, informationImportant=False, health=False, hasLicense=False, substanceUse=False, commonLanguage=False, userUnderstands=False, sameCity=False, rulesFollowed=False, objectNearby=False, userNotice=False, blindSpot=True, obtainConsent=False, needsAccomodation=False, userImpaired=False, warningSignalOff=False, userGivesControl=False, decisionPoint=False, time=0)", 2)
(2, "InformUser(time=1)", 3)
(3, "EnsureAlertness(time=1)", 4)
(4, "TrackVisionField(time=1)", 5)

Expected Output:
Augmented LTS:
des (0, 7, 8)
(0, "UserDriving(hearRateVariability=low, eyeMovements=low1, fullAttentionNeeded=False, properlyPlaced=False, informationImportant=False, health=False, hasLicense=False, substanceUse=False, commonLanguage=False, userUnderstands=False, sameCity=False, rulesFollowed=False, objectNearby=False, userNotice=False, blindSpot=True, obtainConsent=False, needsAccomodation=False, userImpaired=False, warningSignalOff=False, userGivesControl=False, decisionPoint=False, time=0) [CLOCK: 6:30am] (expected)", 1)
(1, "TrackMetrics(hearRateVariability=low, eyeMovements=low1, fullAttentionNeeded=False, properlyPlaced=False, informationImportant=False, health=False, hasLicense=False, substanceUse=False, commonLanguage=False, userUnderstands=False, sameCity=False, rulesFollowed=False, objectNearby=False, userNotice=False, blindSpot=True, obtainConsent=False, needsAccomodation=False, userImpaired=False, warningSignalOff=False, userGivesControl=False, decisionPoint=False, time=0) [CLOCK: 6:30am] (expected)", 2)
(2, "CheckUserAwareness [CLOCK: 6:31am] (expected)", 3)
(3, "InformUser(time=1) [CLOCK: 6:35am] (expected)", 4)
(4, "EnsureAlertness(time=1) [CLOCK: 6:35am] (expected)", 5)
(5, "TrackVisionField(time=1) [CLOCK: 6:35am] (expected)", 6)
(6, "ConfirmSafetyMeasures [CLOCK: 6:36am] (expected)", 7)

Mapping:
"UserDriving(hearRateVariability=low, eyeMovements=low1, fullAttentionNeeded=False, properlyPlaced=False, informationImportant=False, health=False, hasLicense=False, substanceUse=False, commonLanguage=False, userUnderstands=False, sameCity=False, rulesFollowed=False, objectNearby=False, userNotice=False, blindSpot=True, obtainConsent=False, needsAccomodation=False, userImpaired=False, warningSignalOff=False, userGivesControl=False, decisionPoint=False, time=0) [CLOCK: 6:30am] (expected)" -> "UserDriving(hearRateVariability=low, eyeMovements=low1, fullAttentionNeeded=False, properlyPlaced=False, informationImportant=False, health=False, hasLicense=False, substanceUse=False, commonLanguage=False, userUnderstands=False, sameCity=False, rulesFollowed=False, objectNearby=False, userNotice=False, blindSpot=True, obtainConsent=False, needsAccomodation=False, userImpaired=False, warningSignalOff=False, userGivesControl=False, decisionPoint=False, time=0)"
"TrackMetrics(hearRateVariability=low, eyeMovements=low1, fullAttentionNeeded=False, properlyPlaced=False, informationImportant=False, health=False, hasLicense=False, substanceUse=False, commonLanguage=False, userUnderstands=False, sameCity=False, rulesFollowed=False, objectNearby=False, userNotice=False, blindSpot=True, obtainConsent=False, needsAccomodation=False, userImpaired=False, warningSignalOff=False, userGivesControl=False, decisionPoint=False, time=0) [CLOCK: 6:30am] (expected)" -> "TrackMetrics(hearRateVariability=low, eyeMovements=low1, fullAttentionNeeded=False, properlyPlaced=False, informationImportant=False, health=False, hasLicense=False, substanceUse=False, commonLanguage=False, userUnderstands=False, sameCity=False, rulesFollowed=False, objectNearby=False, userNotice=False, blindSpot=True, obtainConsent=False, needsAccomodation=False, userImpaired=False, warningSignalOff=False, userGivesControl=False, decisionPoint=False, time=0)"
"CheckUserAwareness [CLOCK: 6:31am] (expected)" -> "i"
"InformUser(time=1) [CLOCK: 6:35am] (expected)" -> "InformUser(time=1)"
"EnsureAlertness(time=1) [CLOCK: 6:35am] (expected)" -> "EnsureAlertness(time=1)"
"TrackVisionField(time=1) [CLOCK: 6:35am] (expected)" -> "TrackVisionField(time=1)"
"ConfirmSafetyMeasures [CLOCK: 6:36am] (expected)" -> "i"

Scene Label and Time:
Scene 1: UserDriving 6:30am
Scene 2: TrackMetrics 6:30am
Scene 3: CheckUserAwareness 6:31am
Scene 4: InformUser 6:35am
Scene 5: EnsureAlertness 6:35am
Scene 6: TrackVisionField 6:35am
Scene 7: ConfirmSafetyMeasures 6:36am


Output Format: (Please strictly follow the format and ensure to add Augmented LTS: and Mapping: and Scene Label and Time: in the output so to parse them to three parts easily)
Start of Output. (This line is just for you to know where the output starts, don't include it in the output)
Augmented LTS:
...
Mapping:
...
Scene Label and Time:
...
End of Output. (This line is just for you to know where the output ends, don't include it in the output)

IMPORTANT:
- DO NOT RETURN JSON FORMAT.
- STRICTLY FOLLOW THE TEXT FORMAT PROVIDED ABOVE.

### Verification:
1. Norm Compliance & Correction:
   - Detect unexpected transitions and apply AI intervention.
   - Ensure AI suggestions align with real-world norms.

2. Constraint Satisfaction:
   - Time constraints:
     - Non-decreasing progression, the next transition time must be later or equal to the previous one.
     - The new transition must not have time=X in the measures. **Really important**
   - Safety constraints: No hazardous transitions.
   - Trace equivalence: Augmented LTS maintains original logic.

### Final Deliverables:
1. Augmented LTS with norm-aware and time-consistent enhancements.
2. Mapping between original and augmented transitions. Ensure to write the mapping in the same format as above so to directly use in rename.ren file for CADP rename operation.
3. Scene Label and Time. Ensure to write the scene label and time in the same format as above so to directly use in augment_image file for image augmentation.

### Last Check:
- You must keep non-decreasing temporal ordering in the augmented LTS for [CLOCK: time] in the augmented transition label.
- The [CLOCK: time] in the next transition must be later or equal to the [CLOCK: time] in the previous transition.
- The newly added transition must not have time=X in the measures.
- When adding new transitions, ensure event name and meaures should be different and meaningful so it could help to make scenarios transition more realistic and norm-compliant, i.e. please pick appropriate event name and measures.
- Use different event name for different newly added transitions. (Don't use the same event name for different newly added transitions, e.g. DisplayMessage is not clear enough)
"""

def generate_svl_file(rename_content):
    # Read renaming rules from rename.ren
    rename_rules = []
    for line in rename_content.split('\n'):
        if '->' in line:
            old, new = line.split('->')
            # Remove all quotes and commas, then re-add quotes
            old = old.strip().strip('"').strip(',')
            new = new.strip().strip('"').strip(',')
            
            # Only escape square brackets
            old_escaped = old.replace('[', '\[').replace(']', '\]')
            new_escaped = new  # New label doesn't need escaping
            
            # Use correct format, ensuring each rule is on a separate line
            rename_rules.append(f'    "{old_escaped}" -> "{new_escaped}"')
    
    # Generate SVL content, using standard format
    svl_content = f'''property RENAME_RULES
    "Rename transitions to their abstract form"
is
    "renamed.bcg" = total rename
{",\n".join(rename_rules)}
    in "l2.bcg";
    % bcg_io "renamed.bcg" "renamed.aut"
end property'''
    
    # Save SVL file
    with open('rename.svl', 'w') as f:
        f.write(svl_content)
    
    # st.write("Debug - Generated SVL content:", svl_content)  

def run_equivalence_check():
    try:
        # Check if files exist
        if not os.path.exists('l1.aut'):
            st.error("l1.aut file does not exist")
            return False, "l1.aut file missing"
            
        if not os.path.exists('l2.aut'):
            st.error("l2.aut file does not exist")
            return False, "l2.aut file missing"
            
        # Check file content
        with open('l1.aut', 'r') as f:
            l1_content = f.read()
            if not l1_content.strip():
                st.error("l1.aut is empty")
                return False, "l1.aut is empty"
        
        # Conversion and checking process
        st.write("Converting l1.aut to l1.bcg...")
        subprocess.run(['bcg_io', 'l1.aut', 'l1.bcg'], check=True)
        
        st.write("Converting l2.aut to l2.bcg...")
        subprocess.run(['bcg_io', 'l2.aut', 'l2.bcg'], check=True)
        
        # Running rename operation
        st.write("Running rename operation...")
        rename_result = subprocess.run(['svl', 'rename.svl'], 
                                     capture_output=True, 
                                     text=True,
                                     check=True)
        st.write("Rename output:", rename_result.stdout)
        
        # Running equivalence check, using weak bisimulation
        st.write("Running equivalence check...")
        result = subprocess.run(
            ['bcg_open', 'l1.bcg', 'bisimulator', '-weaktrace', 'renamed.bcg'],  # Changed to -weak parameter
            capture_output=True,
            text=True,
            check=True
        )
        
        return 'TRUE' in result.stdout.upper(), result.stdout
        
    except subprocess.CalledProcessError as e:
        error_msg = f"Command failed: {e.cmd}\nOutput: {e.output if hasattr(e, 'output') else 'No output'}"
        st.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        st.error(f"Error during verification: {str(e)}")
        raise

def generate_scene_prompts(lts_content):
    # 获取案例研究上下文（如果有）
    case_study_context = st.session_state.get('case_study_context', '')
    
    # 如果有上下文，添加到提示中
    context_section = ""
    if case_study_context:
        context_section = f"""
## Case Study Context:
{case_study_context}

This context should guide your scene generation to align with the actual system behavior.
"""
    
    prompt = f"""
Based on the following augmented LTS transitions, generate realistic visual prompts for image generation.
LTS Content:
{lts_content}
Focus on creating scenes that clearly illustrate the state transitions and measures involved, while maintaining realism according to the context.
{context_section}
IMPORTANT CLARIFICATION:
- The notation 'time=X' is a PSEUDO TIME indicating relative timing from the initial event (e.g., 'time=300' means 5 minutes after 'time=0').
- DO NOT interpret 'time=X' as a countdown or any other meaning. For the event with same pseudo time=X, the time should be approximately the same, you can choose time that is realistic.  
- Ensure the generated REAL TIME (e.g., 8:40am) strictly matches the relative relationship indicated by the pseudo time.
- Use REALISTIC starting times based on the context (e.g., medical procedures typically start at 8:00am or 9:00am, not 6:30am).
- Ensure waiting times between events are realistic and reflect the actual time needed for such activities.

SCENE DESCRIPTIONS REQUIREMENTS:
For each transition, create a REALISTIC visual scene that:
- Clearly identifies the ROBOT as the primary agent performing actions, but in a realistic manner.
- ROBOT APPEARANCE: The robot must have a SCREEN as its FACE/HEAD that displays content related to the current scene/action. The screen should show icons, information, or expressions relevant to the event.
- ROBOT COUNT: Ensure there is only one robot in the scene. Specify this in scene description.
- SCREEN CONTENT: The screen MUST display CLEAR, LEGIBLE TEXT related to the current action (e.g., "EXAMINING PATIENT", "ADMINISTERING MEDICATION"). The text must be large enough to be easily read and should be the focal point of the robot's face.
- Clearly shows the state transition event and related measures (put in parentheses after the event).
- Makes the measures visually identifiable through appropriate visual elements.
- IMPORTANT: All measures must clearly apply to the correct subject (HUMAN or ENVIRONMENT), never the robot.
- Scene name must explicitly include the EVENT NAME, MEASURES in parentheses, and REAL TIME (e.g., ExaminingPatient (behaviorAggressive=True) 8:40am).
- Scene times must be NON-DECREASING from start to end.
- Uses appropriate visual cues that relate to each measure without being overly dramatic.
- Maintains CLEAR READABILITY of the scene while being realistic.
- Include human or environment in the scene description if the measures apply to them or event is related to them. 
- Only add human related to events or measures, do not add human if the event is not related to them so to keep clearness of the scene.
- Only add one human for each job or identity, do not add multiple humans for the same job or identity.
- For measures in parentheses, use appropriate visual cues to indicate the measure. If measure is not really clear like behaviorAggressive=True, use a detailed visual behavior like human yelling to show the measure.

Style requirements for ALL images:
- Photorealistic rendering with natural lighting and composition.
- Balanced lighting that highlights key elements without being theatrical.
- Clear composition with identifiable focal points.
- Visual indicators for each measure that are noticeable but not exaggerated.
- Realistic backgrounds that provide context without distraction.
- Natural facial expressions and body language.
- High quality, detailed rendering.
- Realistic textures and proportions.
- The robot must have a screen/display panel as its face, showing relevant information or expressions related to the current task.
- The text on the robot's screen must be LARGE, CLEAR, and LEGIBLE, with high contrast against the screen background.

Negative prompt for ALL scenes:
- Avoid: overly dramatic or exaggerated representations.
- Avoid: unrealistic lighting or composition.
- Avoid: cartoonish or stylized elements.
- Avoid: overly symbolic or metaphorical representations.
- Avoid: scenes that look staged or artificial.
- Avoid: robots with human-like faces or expressions; the robot must have a screen/display as its face and show relevant information or expressions related to the current task.
- Avoid: blurry, illegible, or tiny text on the robot's screen.

Format your response exactly as:
Start of Output. (This line is just for you to know where the output starts, don't include it in the output)
SCENE DESCRIPTIONS:
1. [first scene description with REALISTIC visual elements that clearly show the event and measures, this must be one paragraph]
2. [second scene description with REALISTIC visual elements that clearly show the event and measures, this must be one paragraph]
(etc.)
End of Output. (This line is just for you to know where the output ends, don't include it in the output)

Remember:
- ROBOT is always the primary agent performing actions.
- ROBOT must have a SCREEN as its FACE that displays content related to the current scene/action.
- The SCREEN must display CLEAR, LEGIBLE TEXT that is easily readable.
- Measures clearly apply to HUMAN or ENVIRONMENT, never the robot.
- Include human or environment in the scene description if the measures apply to them or event is related to them. (e.g. event is meetingpatient, include patient in the scene description)
- Correctly decide what kind of human or environment should be included in the scene description in such medical situation. If the human status is not clear, include the most possible status.(e.g. user is not clearly stated, but user in medical situation should be patient in common language, you need to do this kind of decision when vague)
- Ensure correct interaction between robot and human or environment.
- Scene name must explicitly include EVENT NAME, MEASURES in parentheses, and REAL TIME.
- Scene times must be NON-DECREASING from start to end.
- Scene times need to be realistic and reasonable according to the event and measures depending on how long the event takes.
- Create REALISTIC scenes while ensuring key elements are clearly visible.
- Create a scene for EVERY transition in the LTS, including those with measures like behaviorAggressive=True.
"""
    return prompt

def generate_user_friendly_descriptions(api_key, lts_content, api_choice='OpenAI', base_url=None):
    """生成用户友好的场景描述，专注于用户和系统之间的交互，而不是详细的场景描述"""
    # 获取案例研究上下文（如果有）
    case_study_context = st.session_state.get('case_study_context', '')
    
    # 如果有上下文，添加到提示中
    context_section = ""
    if case_study_context:
        context_section = f"""
## Case Study Context:
{case_study_context}

This context should guide your descriptions to align with the actual system behavior.
"""
    
    prompt = f"""
Based on the following augmented LTS transitions, generate concise, user-friendly descriptions that focus on the interaction between the user and the system.
{context_section}
DESCRIPTION REQUIREMENTS:
- Focus on the INTERACTION between the user and system described by the event
- Describe the environment based on the measures mentioned
- Keep descriptions BRIEF and CLEAR (1-2 sentences maximum)
- Include the event name and time in a standardized format
- Avoid detailed visual descriptions that would be used for image generation

LTS Content:
{lts_content}

Format your response exactly as:
Start of Output.
USER FRIENDLY DESCRIPTIONS:
1. EventName (Time, Location) – Brief description of interaction.
2. EventName (Time, Location) – Brief description of interaction.
(etc.)
End of Output.

Example:
CheckUserReadiness (8:30am, Clinical Examination Room) – Robot scans patient.

Remember:
- Focus on the INTERACTION, not visual details
- Keep descriptions BRIEF (1-2 sentences)
- Include event name, time, and location in a standardized format
"""
    
    response = call_llm_api(api_key, prompt, api_choice, base_url)
    return parse_user_friendly_descriptions(response)

def parse_user_friendly_descriptions(response):
    """解析用户友好的描述"""
    try:
        # 获取描述部分
        parts = response.split('USER FRIENDLY DESCRIPTIONS:')
        if len(parts) != 2:
            raise Exception("Invalid response format: missing USER FRIENDLY DESCRIPTIONS section")
            
        desc_text = parts[1].strip()
        
        # 使用正则表达式匹配描述
        desc_pattern = r'(\d+)\.\s+([^–]+)–\s*(.+?)(?=\d+\.\s+|$)'
        descriptions = re.findall(desc_pattern, desc_text, re.DOTALL)
        
        parsed_descriptions = []
        for desc_num, header, description in descriptions:
            # 清理描述
            header = header.strip()
            description = description.strip()
            
            # 从头部提取事件名称、时间和位置
            header_match = re.search(r'([^\(]+)\s*\(([^,]+),\s*([^\)]+)\)', header)
            if header_match:
                event_name = header_match.group(1).strip()
                event_time = header_match.group(2).strip()
                location = header_match.group(3).strip()
            else:
                event_name = header
                event_time = "unknown"
                location = "unknown"
            
            parsed_descriptions.append({
                'number': desc_num,
                'event_name': event_name,
                'time': event_time,
                'location': location,
                'description': description,
                'full_description': f"{event_name} ({event_time}, {location}) – {description}"
            })
        
        if not parsed_descriptions:
            raise Exception("Could not parse any descriptions from the text")
            
        return parsed_descriptions
            
    except Exception as e:
        st.error(f"Error parsing user-friendly descriptions: {str(e)}")
        return []

def parse_scene_descriptions(prompts):
    """解析场景描述，直接使用场景编号和星号之间的内容作为标签"""
    try:
        # 直接获取场景描述部分
        parts = prompts.split('SCENE DESCRIPTIONS:')
        if len(parts) != 2:
            raise Exception("Invalid prompt format: missing SCENE DESCRIPTIONS section")
            
        scene_text = parts[1].strip()
        
        # 使用简单的正则表达式匹配场景编号和星号之间的内容
        # 格式: "1. **EventName 6:30am**: Description"
        scene_pattern = r'(\d+)\.\s+\*\*([^*]+)\*\*:\s*(.+?)(?=\d+\.\s+\*\*|$)'
        scenes = re.findall(scene_pattern, scene_text, re.DOTALL)
        
        parsed_scenes = []
        for scene_num, scene_label, scene_desc in scenes:
            # 清理场景标签和描述
            scene_label = scene_label.strip()
            scene_desc = scene_desc.strip()
            
            # 从场景标签中提取时间
            time_match = re.search(r'(\d+:\d+[ap]m)', scene_label)
            scene_time = time_match.group(1) if time_match else "unknown"
            
            # 将场景标签和时间作为场景名称
            scene_name = scene_label
            
            parsed_scenes.append((scene_name, scene_time, scene_desc))
            
            # 调试输出
            st.write(f"Scene {scene_num}:")
            st.write(f"  Name: {scene_name}")
            st.write(f"  Time: {scene_time}")
            st.write(f"  Description length: {len(scene_desc)} characters")
        
        if not parsed_scenes:
            raise Exception("Could not parse any scenes from the text")
            
        return parsed_scenes
            
    except Exception as e:
        st.error(f"Error parsing scene descriptions: {str(e)}")
        # Debug输出原始文本
        st.write("Debug - Original scene text:")
        st.text(scene_text)
        return []

def generate_flux_pro(api_key, prompt, image_size="landscape_16_9"):
    try:
        # 设置环境变量
        os.environ['FAL_KEY'] = api_key
        
        # 添加机器人外观描述
        enhanced_prompt = f"""
{prompt}

IMPORTANT: The robot must have a SCREEN as its FACE/HEAD that displays content related to the current scene/action. The screen should show icons, information, or expressions relevant to the task being performed.

SCREEN CONTENT: The screen MUST display CLEAR, LEGIBLE TEXT related to the current action. The text must be LARGE, with HIGH CONTRAST against the screen background (e.g., white or bright text on dark background, or dark text on light background), and should be the focal point of the robot's face.
"""
        
        # 调用API
        result = fal_client.subscribe(
            "fal-ai/flux-pro/v1.1-ultra",
            arguments={
                "prompt": enhanced_prompt,
                "image_size": image_size,  # 使用预定义的尺寸
                "num_images": 1,
                "output_format": "jpeg",
                "negative_prompt": "cartoon, anime, illustration, painting, artistic, stylized, unnatural colors, oversaturated, low quality, blurry, deformed, human-like robot face, robot with human features, blurry text, illegible text, small text"
            }
        )
        
        return result['images'][0]['url'] if result and 'images' in result else None
            
    except Exception as e:
        raise Exception(f"Flux Pro API error: {str(e)}")

def generate_scene_with_fal(api_key, scene_desc, event_name, measures):
    """use fal api to generate scene image"""
    try:
        enhanced_prompt = f"""
Here is the detailed scene description:
{scene_desc}

REALISTIC and CLEARLY IDENTIFIABLE scene showing a medical robot performing the action '{event_name}'.

The scene must include:
- Only one robot with a SCREEN as its upper body, displaying content related to '{event_name}'.
- The screen should show LARGE, LEGIBLE TEXT with HIGH CONTRAST, focusing on the action (e.g., "{event_name.upper()}").
- The robot's actions should be natural and directly related to '{event_name}'.
- Each measure ({measures}) should be visually explicit and integrated into the scene, either through the environment or human behavior.
- If human is specifically mentioned in the scene description, ensure there is a clear interaction between the robot and human, reflecting the measures and event.
- Include only one human for each job or identity, do not add multiple humans for the same job or identity.

Style: photorealistic, high quality, natural lighting, realistic textures, clear focal points, and explicit visual cues for measures and event.

Negative prompt:
- Avoid unclear or ambiguous elements.
- Avoid unrealistic lighting or cartoonish styles.
- Avoid robots with human-like faces; the robot must have a screen/display as its face.
- Avoid blurry or illegible text on the robot's screen.
- Avoid multiple humans with the same job or identity in the scene. (i.e. avoid multiple nurses, doctors, patients in the scene, etc.)
- Avoid multiple robots in the scene. (Only one robot is allowed in the scene)
- Avoid including human without any measures or event in the scene.
"""
        
        # set fal key
        os.environ['FAL_KEY'] = api_key
        
        # call fal api
        result = fal_client.subscribe(
            "fal-ai/flux-pro/v1.1-ultra",
            arguments={
                "prompt": enhanced_prompt,
                "image_size": "landscape_16_9",
                "num_images": 1,
                "output_format": "jpeg",
                "negative_prompt": "exaggerated, unrealistic, dramatic, cartoonish, overly stylized, theatrical lighting, unnatural colors, distorted proportions, surreal, fantasy elements, overly dramatic poses, human-like robot face, robot with human features, blurry text, illegible text, small text",
                "guidance_scale": 10.0,  # balcrea vreitivity and prompt adherencyadherence
                "num_inference_steps": 50  # high quality quality
            }
        )
        
        return result['images'][0]['url'] if result and 'images' in result else None
    
    except Exception as e:
        st.error(f"Scene generation error: {str(e)}")
        return None

def get_evaluation(client, character_image, scene_images, character_desc, scene_desc):
    evaluation_prompt = f"""
You must respond ONLY with a valid JSON object in exactly this format, no other text:
{{
    "evaluations": [
        {{
            "image_index": 0,
            "character_consistency": {{
                "consistent": "yes/no",
                "justification": "explanation"
            }},
            "scene_accuracy": {{
                "accurate": "yes/no",
                "justification": "explanation"
            }}
        }},
        // ... repeat for each image
    ],
    "best_image": "index of best image (0-2) or -1 if none are suitable",
    "selection_reason": "explanation of why this image was selected or why none were suitable"
}}

Based on these inputs, evaluate each image and select the best one:

CHARACTER DESCRIPTION:
{character_desc}
Character reference image: {character_image}

SCENE DESCRIPTION:
{scene_desc}

SCENE IMAGES:
Image 1: {scene_images[0]}
Image 2: {scene_images[1]}
Image 3: {scene_images[2]}

Remember: Respond ONLY with the JSON object, no other text.
"""
    
    api_choice = st.session_state.get('api_choice', 'OpenAI')
    base_url = st.session_state.get('base_url')  # get base url from session state
    
    if api_choice == 'DeepSeek' and not base_url:
        raise Exception("Base URL is required for DeepSeek API")
    
    response = call_llm_api(client.api_key, evaluation_prompt, api_choice, base_url)
    if not response:
        raise Exception("Failed to get evaluation response from API")
        
    # clean response and parse json
    try:
        # remove possible prefix and suffix text, only keep json part
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            # validate json format
            json.loads(json_str)  # test if valid json
            return json_str
        else:
            raise Exception("No valid JSON found in response")
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON format in API response: {str(e)}")
        st.write("Debug - Raw response:", response)
        raise Exception("Invalid JSON format in evaluation response")
    except Exception as e:
        st.error(f"Error processing evaluation response: {str(e)}")
        st.write("Debug - Raw response:", response)
        raise

def evaluate_and_select_best_image(api_key, character_image, scene_images, character_desc, scene_desc):
    try:
        api_choice = st.session_state.get('api_choice', 'OpenAI')
        base_url = st.session_state.get('base_url')  # get base url from session state
        
        if api_choice == 'DeepSeek':
            if not base_url:
                raise Exception("Base URL is required for DeepSeek API")
            client = OpenAI(api_key=api_key, base_url=base_url)
        else:  # OpenAI
            client = OpenAI(api_key=api_key)
            
        evaluation_result = get_evaluation(
            client,
            character_image,
            scene_images,
            character_desc,
            scene_desc
        )
        if not evaluation_result:
            raise Exception("Failed to get evaluation result")
            
        eval_json = json.loads(evaluation_result)
        
        # check if all images pass two evaluation standards
        best_image_index = -1
        for eval in eval_json['evaluations']:
            if (eval['character_consistency']['consistent'].lower() == 'yes' and 
                eval['scene_accuracy']['accurate'].lower() == 'yes'):
                best_image_index = eval['image_index']
                break
        
        eval_json['best_image'] = best_image_index
        return json.dumps(eval_json)
        
    except Exception as e:
        st.error(f"Evaluation error: {str(e)}")
        return None

def generate_scene_images(fal_api_key, scene_desc, character_image_url):
    if not fal_api_key or not scene_desc or not character_image_url:
        st.error("Missing required parameters for scene generation")
        return None
    
    scene_images = []
    max_retries = 5  # increase retry times
    
    for i in range(3):  # generate 3 images
        retry_count = 0
        while retry_count < max_retries:
            try:
                st.write(f"Generating image {i+1}/3 (attempt {retry_count+1}/{max_retries})...")
                image_url = generate_flux_pro(fal_api_key, scene_desc)
                
                if image_url:
                    scene_images.append(image_url)
                    st.success(f"Successfully generated image {i+1}")
                    break  # success, continue to next image
                
                retry_count += 1
                if retry_count < max_retries:
                    st.warning(f"Retrying image {i+1} generation...")
                    time.sleep(3)  # increase delay time
                
            except Exception as e:
                st.error(f"Error in attempt {retry_count+1}: {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    st.warning("Retrying...")
                    time.sleep(3)
        
        if retry_count >= max_retries:
            st.error(f"Failed to generate image {i+1} after {max_retries} attempts")
            return None
    
    # ensure all 3 images are generated
    if len(scene_images) == 3:
        return scene_images
    
    st.error(f"Only generated {len(scene_images)}/3 images")
    return None

def display_evaluation_results(evaluations, col2, col3):
    # initialize session state
    if 'initialized' not in st.session_state:
        st.session_state['initialized'] = True
        st.session_state['current_page'] = 0
        st.session_state['page_key'] = 0
    
    total_pages = len(evaluations)
    current_page = st.session_state['current_page']
    
    # Ensure page number is within valid range
    current_page = max(0, min(current_page, total_pages - 1))
    
    with col2:
        st.subheader("Scene Details")
        
        # Create pagination controls
        cols = st.columns([1, 2, 1])
        
        with cols[0]:
            if current_page > 0:
                if st.button("⬅️ Previous", key=f"prev_{st.session_state['page_key']}"):
                    st.session_state['current_page'] -= 1
                    st.session_state['page_key'] += 1
        
        with cols[1]:
            st.markdown(f"<div class='pagination-text'>Scene {current_page + 1} of {total_pages}</div>", unsafe_allow_html=True)
        
        with cols[2]:
            if current_page < total_pages - 1:
                if st.button("Next ➡️", key=f"next_{st.session_state['page_key']}"):
                    st.session_state['current_page'] += 1
                    st.session_state['page_key'] += 1
        
        # Display detailed information about the current scene
        if evaluations and current_page < len(evaluations):
            eval_data = evaluations[current_page]
            
            # 使用用户友好的描述（如果有）
            if 'user_friendly_desc' in eval_data and eval_data['user_friendly_desc']:
                st.markdown(f"### {eval_data['user_friendly_desc']}")
            else:
                st.markdown(f"### Scene {eval_data['scene_number']}: {eval_data['event_name']}")
            
            st.markdown(f"**Time:** {eval_data['scene_time']}")
            st.markdown(f"**Measures:** {eval_data['measures']}")
            
            # 显示详细的图像生成提示（隐藏在可展开部分）
            with st.expander("Show detailed image generation prompt"):
                st.markdown("**Detailed Description:**")
                st.markdown(f"*{eval_data['scene_desc']}*")
            
            # Display image
            if eval_data.get('image_url'):
                st.image(eval_data['image_url'])
            else:
                st.warning("No image available for this scene")
            
            # Add button to regenerate this scene
            if st.button("Regenerate This Scene", key=f"regen_{st.session_state['page_key']}"):
                regenerate_scene(current_page, eval_data['scene_number'], eval_data['scene_desc'], 
                                eval_data['event_name'], eval_data['measures'], eval_data['scene_time'])

def display_final_results(col3, generated_scenes):
    with col3:
        st.subheader("Final Results")
        
        # Get scene labels and time information
        scene_info = get_scene_labels()
        
        # 获取场景评估数据（包含用户友好的描述）
        scene_evaluations = st.session_state.get('scene_evaluations', [])
        
        # Display images (automatically add labels)
        for i, (desc, url) in enumerate(generated_scenes):
            scene_num = i + 1
            
            # 尝试从场景评估数据中获取用户友好的描述
            user_friendly_desc = None
            if scene_evaluations and i < len(scene_evaluations):
                user_friendly_desc = scene_evaluations[i].get('user_friendly_desc')
            
            if user_friendly_desc:
                st.markdown(f"**Scene {scene_num}: {user_friendly_desc}**")
            elif scene_num in scene_info:
                event_label = scene_info[scene_num]['label']
                time_str = scene_info[scene_num]['time']
                st.markdown(f"**Scene {scene_num}: {event_label}**")
                st.markdown(f"*Time: {time_str}*")
            else:
                st.markdown(f"**Scene {scene_num}**")
            
            # 显示详细描述（隐藏在可展开部分）
            with st.expander("Show detailed description"):
                st.markdown(f"*{desc}*")
            
            if url:
                if scene_num in scene_info:
                    # Automatically add labels and timestamp
                    augmented_img = augment_image_with_label(
                        url,
                        scene_info[scene_num]['label'],
                        scene_info[scene_num]['time']
                    )
                    
                    if augmented_img:
                        st.image(augmented_img)
                    else:
                        st.warning(f"Failed to add labels to scene {scene_num}")
                        st.image(url)
                else:
                    st.warning(f"No label information found for scene {scene_num}")
                    st.image(url)
            else:
                st.warning("No suitable image was found for this scene")
                
        # Add download button
        if generated_scenes:
            st.markdown("---")
            st.subheader("Download Images")
            
            # Create a temporary directory to store images
            import tempfile
            import zipfile
            import os
            
            with tempfile.TemporaryDirectory() as tmpdirname:
                # Save all images to temporary directory
                for i, (desc, url) in enumerate(generated_scenes):
                    if url:
                        scene_num = i + 1
                        if scene_num in scene_info:
                            try:
                                # Download image
                                response = requests.get(url)
                                img = Image.open(BytesIO(response.content))
                                
                                # Add labels
                                draw = ImageDraw.Draw(img)
                                font_size = 48
                                try:
                                    font = ImageFont.truetype("Arial.ttf", font_size)
                                except:
                                    try:
                                        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
                                    except:
                                        font = ImageFont.load_default()
                                
                                # Prepare text
                                label = scene_info[scene_num]['label']
                                timestamp = scene_info[scene_num]['time']
                                
                                # 使用用户友好的描述（如果有）
                                if scene_evaluations and i < len(scene_evaluations) and scene_evaluations[i].get('user_friendly_desc'):
                                    label = scene_evaluations[i]['user_friendly_desc']
                                
                                text = f"Event: {label}\nTime: {timestamp}"
                                
                                # Add semi-transparent background
                                x, y = 20, 20
                                text_bbox = draw.textbbox((x, y), text, font=font)
                                padding = 15
                                background_bbox = (
                                    text_bbox[0] - padding,
                                    text_bbox[1] - padding,
                                    text_bbox[2] + padding,
                                    text_bbox[3] + padding
                                )
                                
                                # Create new image and draw background
                                if img.mode != 'RGBA':
                                    img = img.convert('RGBA')
                                overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
                                overlay_draw = ImageDraw.Draw(overlay)
                                overlay_draw.rectangle(background_bbox, fill=(0, 0, 0, 160))
                                img = Image.alpha_composite(img, overlay)
                                
                                # Draw text
                                draw = ImageDraw.Draw(img)
                                border = 3
                                for dx in range(-border, border+1):
                                    for dy in range(-border, border+1):
                                        if dx != 0 or dy != 0:
                                            draw.text((x+dx, y+dy), text, font=font, fill='black')
                                draw.text((x, y), text, font=font, fill='white')
                                
                                # Save image
                                img = img.convert('RGB')
                                img_path = os.path.join(tmpdirname, f"scene_{scene_num}.jpg")
                                img.save(img_path, "JPEG", quality=95)
                            except Exception as e:
                                st.error(f"Error saving image for scene {scene_num}: {str(e)}")
                
                # Create ZIP file
                zip_path = os.path.join(tmpdirname, "scene_images.zip")
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file in os.listdir(tmpdirname):
                        if file.endswith('.jpg'):
                            zipf.write(os.path.join(tmpdirname, file), file)
                
                # Read ZIP file and provide download
                with open(zip_path, "rb") as f:
                    zip_data = f.read()
                    st.download_button(
                        label="Download All Images",
                        data=zip_data,
                        file_name="scene_images.zip",
                        mime="application/zip"
                    )

def regenerate_scene(current_page, scene_num, scene_desc, event_name, measures, scene_time):
    """重新生成特定场景的图像"""
    try:
        # 获取API密钥
        fal_api_key = st.session_state.get('fal_api_key')
        if not fal_api_key:
            st.error("FAL API key not found. Please re-enter your API key.")
            return False
        
        # 获取当前场景的用户友好描述（如果有）
        user_friendly_desc = None
        if 'scene_evaluations' in st.session_state and st.session_state['scene_evaluations']:
            evaluations = st.session_state['scene_evaluations']
            if current_page < len(evaluations):
                user_friendly_desc = evaluations[current_page].get('user_friendly_desc')
        
        with st.spinner(f"Regenerating scene {scene_num}..."):
            # 构建完整的标签，确保包含事件和度量
            full_label = f"{event_name}"
            if measures:
                full_label += f" ({measures})"
            
            # 直接使用FAL生成场景图像
            image_url = generate_scene_with_fal(fal_api_key, scene_desc, event_name, measures)
            
            if image_url:
                # 为图像添加标签（事件名称和时间）
                augmented_img = augment_image_with_label(image_url, full_label, scene_time)
                
                # 更新session state中的场景评估数据
                if 'scene_evaluations' in st.session_state and st.session_state['scene_evaluations']:
                    evaluations = st.session_state['scene_evaluations']
                    if current_page < len(evaluations):
                        evaluations[current_page]['image_url'] = image_url
                
                # 更新session state中的生成场景数据
                if 'generated_scenes' in st.session_state and st.session_state['generated_scenes']:
                    generated_scenes = st.session_state['generated_scenes']
                    if current_page < len(generated_scenes):
                        generated_scenes[current_page] = (scene_desc, image_url)
                
                # 显示生成的图像
                with st.spinner("Updating display..."):
                    # 使用用户友好的描述（如果有）
                    display_label = user_friendly_desc if user_friendly_desc else full_label
                    
                    st.success(f"Successfully regenerated scene {scene_num}")
                    st.subheader(f"Scene {scene_num}: {display_label}")
                    st.markdown(f"*Time: {scene_time}*")
                    
                    if augmented_img:
                        st.image(augmented_img)
                    else:
                        st.image(image_url)
                        st.warning(f"Failed to add labels to scene {scene_num}")
                
                # 刷新页面以显示更新后的图像
                st.rerun()
                
                return True
            else:
                st.error(f"Failed to regenerate image for scene {scene_num}")
                return False
                
    except Exception as e:
        st.error(f"Error regenerating scene: {str(e)}")
        return False

def generate_timetable(api_key, lts_content):
    # 获取案例研究上下文（如果有）
    case_study_context = st.session_state.get('case_study_context', '')
    
    # 如果有上下文，添加到提示中
    context_section = ""
    if case_study_context:
        context_section = f"""
## Case Study Context:
{case_study_context}

This context should guide your understanding of the transitions.
"""
    
    prompt = f"""
Extract a timetable from the following LTS content. 
{context_section}
IMPORTANT: Use REALISTIC times for medical procedures (typically starting around 8:00am or 9:00am, not 6:30am) and ensure waiting times between events reflect the actual time needed for such activities.

Return ONLY a JSON object with the following format:
{{
    "transitions": [
        {{
            "label": "transition name",
            "time": "HH:MM",
            "state": "state number"
        }}
    ]
}}

LTS Content:
{lts_content}
"""
    
    api_choice = st.session_state.get('api_choice', 'OpenAI')
    base_url = st.session_state.get('base_url') if api_choice == 'DeepSeek' else None
    
    response = call_llm_api(api_key, prompt, api_choice, base_url)
    return json.loads(response)

def extract_timestamp(transition_label):
    """从转换标签中提取时间戳"""
    time_match = re.search(r'time=(\d+:\d+[ap]m)', transition_label, re.IGNORECASE)
    if time_match:
        return time_match.group(1)
    return None

def extract_transition_info(lts_content):
    """从LTS内容中提取转换信息"""
    transitions = []
    # 匹配转换行: (state,"label",next_state)
    pattern = r'\((\d+),"([^"]+)",(\d+)\)'
    matches = re.findall(pattern, lts_content)
    
    for match in matches:
        state, label, next_state = match
        timestamp = extract_timestamp(label)
        if timestamp:
            # 提取转换名称和度量信息
            event_match = re.search(r'([^\(]+)\s*(?:\(([^\)]+)\))?', label)
            if event_match:
                name = event_match.group(1).strip()
                measures = event_match.group(2).strip() if event_match.group(2) else ""
            else:
                name = label.split('(')[0].strip()
                measures = ""
                
            transitions.append({
                'label': name,
                'measures': measures,
                'time': timestamp,
                'state': state,
                'full_label': label
            })
    
    return {'transitions': transitions}

def augment_image_with_label(image_url, label, timestamp):
    """为图片添加标签和时间戳，确保标签包含事件和度量信息"""
    try:
        # 下载图片
        response = requests.get(image_url)
        img = Image.open(BytesIO(response.content))
        
        # 创建绘图对象
        draw = ImageDraw.Draw(img)
        
        # 设置字体（如果没有Arial则使用默认字体）
        font_size = 48  # 增加字体大小
        try:
            font = ImageFont.truetype("Arial.ttf", font_size)
        except:
            try:
                # 尝试使用系统默认字体
                font = ImageFont.truetype("DejaVuSans.ttf", font_size)
            except:
                font = ImageFont.load_default()
        
        # 确保标签包含事件和度量信息
        if '(' not in label and ')' not in label:
            # 如果标签中没有括号，尝试提取事件名称
            event_name = label.strip()
            label = f"{event_name} (no measures)"
        
        # 准备文本
        text = f"Event: {label}\nTime: {timestamp}"
        
        # 添加文本（白色文字带黑色边框）
        x, y = 20, 20  # 文本位置，稍微远离边缘
        border = 3  # 增加边框粗细
        
        # 添加半透明背景以增强可读性
        text_bbox = draw.textbbox((x, y), text, font=font)
        padding = 15
        background_bbox = (
            text_bbox[0] - padding,
            text_bbox[1] - padding,
            text_bbox[2] + padding,
            text_bbox[3] + padding
        )
        
        # 在文本下方创建半透明黑色背景
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle(background_bbox, fill=(0, 0, 0, 160))  # 更不透明的黑色背景
        
        # 将原图转换为RGBA模式（如果不是）
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # 合并图层
        img = Image.alpha_composite(img, overlay)
        
        # 重新绘制文本（因为合并图层后原来的文本可能被覆盖）
        draw = ImageDraw.Draw(img)
        # 绘制黑色边框
        for dx in range(-border, border+1):
            for dy in range(-border, border+1):
                if dx != 0 or dy != 0:
                    draw.text((x+dx, y+dy), text, font=font, fill='black')
        # 绘制白色文本
        draw.text((x, y), text, font=font, fill='white')
        
        # 转换为字节流
        img_byte_arr = BytesIO()
        img = img.convert('RGB')  # 转换回RGB模式以保存为JPEG
        img.save(img_byte_arr, format='JPEG', quality=95)
        img_byte_arr.seek(0)
        
        return img_byte_arr
    
    except Exception as e:
        st.error(f"Error augmenting image: {str(e)}")
        st.error(f"Error details: {type(e).__name__}: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return None

def get_scene_labels():
    """从augment_image.txt读取场景标签和时间信息"""
    try:
        if not os.path.exists('augment_image.txt'):
            st.error("augment_image.txt file not found")
            return {}
            
        with open('augment_image.txt', 'r') as f:
            content = f.read()
            # st.write("Debug - Scene Labels Content:", content)  # 调试信息
        
        # 直接从文件中解析场景标签
        scene_info = {}
        # 分割场景
        scene_pattern = r'Scene\s+(\d+):\s*(.*?)(?=Scene\s+\d+:|$)'
        scenes = re.findall(scene_pattern, content, re.DOTALL)
        
        for scene_num_str, scene_content in scenes:
            try:
                # 提取场景编号和内容
                scene_num = int(scene_num_str)
                scene_label = scene_content.strip()
                
                # 从场景标签中提取时间
                time_match = re.search(r'(\d+:\d+[ap]m)', scene_label)
                time = time_match.group(1) if time_match else "unknown"
                
                scene_info[scene_num] = {
                    'label': scene_label,
                    'time': time
                }
                # st.write(f"Debug - Parsed Scene {scene_num}:", 
                #        f"Label: {scene_label}, Time: {time}")  # 调试信息
            except Exception as e:
                st.error(f"Error parsing scene {scene_content.strip()}: {str(e)}")
                continue
        
        # st.write("Debug - All Scene Info:", scene_info)  # 调试信息
        return scene_info
        
    except Exception as e:
        st.error(f"Error reading scene labels: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return {}

def call_llm_api(api_key, prompt, api_choice='OpenAI', base_url=None):
    """统一的 LLM API 调用函数"""
    try:
        # 如果没有提供base_url，尝试从session state获取
        if api_choice == 'DeepSeek' and not base_url:
            base_url = st.session_state.get('base_url')
            if not base_url:
                raise ValueError("Base URL is required for DeepSeek API")

        if api_choice == 'OpenAI':
            client = OpenAI(api_key=api_key)
            model = "gpt-4"
        else:  # DeepSeek
            client = OpenAI(api_key=api_key, base_url=base_url)
            model = "deepseek-chat"

        try:
            # 添加更明确的系统提示
            system_prompt = "You are an expert in formal process modeling and image generation prompts. Always respond in the exact format requested, especially when JSON format is required."
            if "JSON" in prompt:
                system_prompt += " Your response must be a valid JSON object with no additional text before or after."
                
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2048,
                temperature=0.2,
                top_p=0.9,
                stream=False
            )
            
            content = response.choices[0].message.content
            if not content:
                raise Exception("Empty response from API")
                
            return content
            
        except Exception as e:
            if 'invalid_api_key' in str(e):
                if api_choice == 'DeepSeek':
                    raise Exception(f"Invalid DeepSeek API key or base URL. Please check your credentials.")
                else:
                    raise Exception(f"Invalid OpenAI API key. Please check your credentials.")
            else:
                raise Exception(f"API call failed: {str(e)}")
        
    except Exception as e:
        st.error(f"Error calling {api_choice} API: {str(e)}")
        return None

def change_page(delta):
    st.session_state['current_page'] += delta
    st.session_state['page_key'] += 1  # 更新页面键

def main():
    st.title("LTS Augmentation Tool")
    st.markdown("---")
    
    # 获取已转换的LTS内容
    initial_lts = get_translated_lts()
    
    # 创建三列布局
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Original LTS")
        # 使用获取到的LTS内容作为初始值
        lts_content = st.text_area(
            "Input LTS in .aut format:",
            value=initial_lts,
            height=300
        )
        
        # 添加案例研究上下文输入区域
        st.subheader("Case Study Context (Optional)")
        case_study_context = st.text_area(
            "Enter context about the system being modeled (e.g., robot description, environment, etc.):",
            value=st.session_state.get('case_study_context', ''),
            height=200,
            help="This context will be used to guide the generation of augmented LTS and image prompts."
        )
        # 保存到session state
        st.session_state['case_study_context'] = case_study_context
        
        # API 选择和配置区域
        st.subheader("API Configuration")
        
        # API 选择
        api_choice = st.radio(
            "Choose API Provider:",
            ["OpenAI", "DeepSeek"],
            key="api_choice"
        )
        
        # API 密钥输入
        api_key = st.text_input(
            "API Key:",
            type="password",
            help="Enter your API key"
        )
        
        # 如果选择DeepSeek，显示base URL输入，使用默认值
        if api_choice == "DeepSeek":
            base_url = st.text_input(
                "Base URL:",
                value=st.session_state.get('base_url', DEFAULT_DEEPSEEK_BASE_URL),
                help="Enter the base URL for DeepSeek API"
            )
            st.session_state['base_url'] = base_url
        
        # FAL API 密钥输入
        fal_api_key = st.text_input(
            "FAL API Key:",
            type="password",
            help="Enter your FAL API key for image generation"
        )
        
        # 按钮区域
        st.subheader("Operations")
        
        # 创建两行按钮
        button_row1_col1, button_row1_col2 = st.columns(2)
        button_row2_col1, button_row2_col2 = st.columns(2)
        
        with button_row1_col1:
            # Augment LTS按钮
            if st.button("Generate Augmented LTS", type="primary"):
                if not api_key:
                    st.error(f"Please enter your {api_choice} API key.")
                    return
                
                if not lts_content:
                    st.error("Please enter your LTS.")
                    return
                
                try:
                    prompt = generate_prompt(lts_content)
                    
                    # 保存生成的prompt到文件
                    with open('generated_prompt.txt', 'w') as f:
                        f.write(prompt)
                    
                    with st.spinner("Generating augmented LTS..."):
                        response = call_llm_api(api_key, prompt, api_choice, st.session_state.get('base_url'))
                        
                        if not response:
                            st.error("Failed to generate response")
                            return
                        
                        # 保存GPT的响应到session state以供后续使用
                        st.session_state.augmented_response = response
                        
                        # 分块保存GPT的响应到文件
                        try:
                            with open('gpt_response.txt', 'w', encoding='utf-8') as f:
                                f.write(response)
                            st.success("Response saved to gpt_response.txt")
                        except Exception as e:
                            st.error(f"Error saving response: {str(e)}")
                        
                        # 保存文件并显示结果，传入col2
                        save_to_files(lts_content, response, col2)
                        
                        st.success("Files generated successfully!")
                        
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    st.markdown("**Generated Prompt (also saved to generated_prompt.txt)**")
                    st.text_area("Generated Prompt", value=prompt, height=400, disabled=True)
        
        with button_row1_col2:
            # Verify Equivalence按钮
            if st.button("Verify Equivalence"):
                try:
                    # 检查必要文件是否存在
                    required_files = ['l1.aut', 'l2.aut', 'rename.ren']
                    missing_files = [f for f in required_files if not os.path.exists(f)]
                    
                    if missing_files:
                        st.error(f"Missing required files: {', '.join(missing_files)}")
                        return
                    
                    # 读取 rename.ren 内容
                    with open('rename.ren', 'r') as f:
                        rename_content = f.read().strip()
                    
                    # 生成 rename.svl 文件
                    generate_svl_file(rename_content)
                    
                    with st.spinner("Checking equivalence..."):
                        is_equivalent, output = run_equivalence_check()
                        
                        if is_equivalent:
                            st.success("The augmented LTS is equivalent to the original LTS!")
                        else:
                            st.error("The augmented LTS is NOT equivalent to the original LTS!")
                        
                        # 显示详细输出
                        st.text_area("Verification Output", output, height=200)
                        
                except Exception as e:
                    st.error(f"An error occurred during verification: {str(e)}")
        
        with button_row2_col1:
            # Generate Scenes按钮
            if st.button("Generate Scenes"):
                if not api_key or not fal_api_key:
                    st.error("Please enter both API keys.")
                    return
                
                # 检查并保存API选择和base URL
                api_choice = st.session_state.get('api_choice', 'OpenAI')
                if api_choice == 'DeepSeek':
                    if not base_url:
                        st.error("Base URL is required for DeepSeek API")
                        return
                    # 保存base URL到session state
                    st.session_state['base_url'] = base_url
                
                # 保存API keys到session state
                st.session_state['fal_api_key'] = fal_api_key
                st.session_state['openai_api_key'] = api_key
                
                try:
                    # 检查是否已经生成了增强的LTS
                    if not os.path.exists('gpt_response.txt'):
                        st.error("Please generate augmented LTS first")
                        return
                        
                    with open('gpt_response.txt', 'r') as f:
                        gpt_response = f.read()
                    
                    # 清除之前的结果
                    st.session_state['scene_evaluations'] = None
                    st.session_state['generated_scenes'] = None
                    st.session_state['current_page'] = 0
                    
                    # 1. 生成场景提示
                    with st.spinner("Generating scene prompts..."):
                        # 提取转换信息
                        transitions = extract_transition_info(lts_content)
                        
                        # 生成场景提示
                        prompts = call_llm_api(
                            api_key,
                            generate_scene_prompts(gpt_response),
                            api_choice,
                            st.session_state.get('base_url')
                        )
                        
                        if not prompts:
                            st.error("Failed to generate prompts")
                            return
                        
                        if "SCENE DESCRIPTIONS:" not in prompts:
                            st.error("Generated prompts are not in the correct format")
                            return
                        
                        # 解析场景描述
                        scenes = parse_scene_descriptions(prompts)
                        if not scenes:
                            st.error("Failed to parse scene descriptions")
                            return
                        
                        # 保存场景提示到session state
                        st.session_state['scene_prompts'] = prompts
                        
                        # 显示生成的提示
                        with col2:
                            st.subheader("Generated Prompts")
                        st.text_area("Scene Prompts", prompts, height=400)
                        st.write(f"Found {len(scenes)} scenes")
                        
                        st.success("Successfully generated scene prompts!")
                        
                    # 2. 生成场景图片
                    with st.spinner("Generating scenes..."):
                        generated_scenes = []
                        scene_evaluations = []
                        
                        # 解析场景描述
                        scenes = parse_scene_descriptions(st.session_state['scene_prompts'])
                        if not scenes:
                            st.error("Failed to parse scene descriptions")
                            return
                            
                        # 生成用户友好的描述
                        user_friendly_descriptions = generate_user_friendly_descriptions(
                            api_key, 
                            gpt_response, 
                            api_choice, 
                            st.session_state.get('base_url')
                        )
                        
                        # 创建一个映射，将场景编号映射到用户友好的描述
                        user_desc_map = {int(desc['number']): desc for desc in user_friendly_descriptions}
                            
                        total_scenes = len(scenes)
                        
                        for i, (scene_name, scene_time, scene_desc) in enumerate(scenes):
                            scene_num = i + 1
                            st.write(f"Generating scene {scene_num}/{total_scenes}: {scene_name}")
                            
                            # 从场景名称中提取事件和度量
                            # 例如: "ExaminingPatient 6:40am (behaviorAggressive=True)"
                            # 提取事件名称
                            event_match = re.search(r'([^\s\(]+)', scene_name)
                            event_name = event_match.group(1).strip() if event_match else scene_name
                            
                            # 提取度量信息
                            measures_match = re.search(r'\(([^\)]+)\)', scene_name)
                            measures = measures_match.group(1).strip() if measures_match else ""
                            
                            # 构建完整的标签
                            full_label = scene_name
                            
                            # 获取用户友好的描述（如果有）
                            user_friendly_desc = user_desc_map.get(scene_num, {}).get('full_description', '')
                            if not user_friendly_desc:
                                # 如果没有找到对应的用户友好描述，使用默认格式
                                user_friendly_desc = f"{event_name} ({scene_time}) – Event description."
                            
                            # 直接使用FAL生成场景图像
                            image_url = generate_scene_with_fal(fal_api_key, scene_desc, event_name, measures)
                            
                            if image_url:
                                # 为图像添加标签（事件名称和时间）
                                augmented_img = augment_image_with_label(image_url, full_label, scene_time)
                                
                                # 保存生成的场景
                                generated_scenes.append((scene_desc, image_url))
                                scene_evaluations.append({
                                    'scene_number': scene_num,
                                    'scene_name': event_name,
                                    'scene_time': scene_time,
                                    'scene_desc': scene_desc,
                                    'event_name': event_name,
                                    'measures': measures,
                                    'full_label': full_label,
                                    'image_url': image_url,
                                    'user_friendly_desc': user_friendly_desc
                                })
                                
                                # 显示生成的图像
                                with col3:
                                    st.subheader(f"Scene {scene_num}: {user_friendly_desc}")
                                    st.markdown(f"*Time: {scene_time}*")
                                    if augmented_img:
                                        st.image(augmented_img)
                                    else:
                                        st.image(image_url)
                                        st.warning(f"Failed to add labels to scene {scene_num}")
                            else:
                                st.error(f"Failed to generate image for scene {scene_num}")
                                generated_scenes.append((scene_desc, None))
                                scene_evaluations.append({
                                    'scene_number': scene_num,
                                    'scene_name': event_name,
                                    'scene_time': scene_time,
                                    'scene_desc': scene_desc,
                                    'event_name': event_name,
                                    'measures': measures,
                                    'full_label': full_label,
                                    'image_url': None,
                                    'user_friendly_desc': user_friendly_desc
                                })
                        
                        # 保存生成的场景到session state
                        st.session_state['generated_scenes'] = generated_scenes
                        st.session_state['scene_evaluations'] = scene_evaluations
                        
                        # 生成场景标签文件
                        with open('augment_image.txt', 'w') as f:
                            for i, eval_data in enumerate(scene_evaluations):
                                scene_num = i + 1
                                f.write(f"Scene {scene_num}: {eval_data['full_label']}\n")
                        
                        st.success(f"Successfully generated {len(generated_scenes)} scenes")
                
                except Exception as e:
                    st.error(f"Error in scene generation: {str(e)}")
    
    # 如果已经生成了场景，显示分页控制和结果
    if 'scene_evaluations' in st.session_state and st.session_state['scene_evaluations']:
        display_evaluation_results(st.session_state['scene_evaluations'], col2, col3)
    
    # 如果已经生成了场景，显示最终结果
    if 'generated_scenes' in st.session_state and st.session_state['generated_scenes']:
        display_final_results(col3, st.session_state['generated_scenes'])

if __name__ == "__main__":
    main()