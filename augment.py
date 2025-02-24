from openai import OpenAI
import streamlit as st
import re
import subprocess
import os
import fal_client
import json
# for image generation
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import time

def save_to_files(original_lts, augmented_response, col2):
    # 保存原始LTS到l1.aut
    with open('l1.aut', 'w') as f:
        f.write(original_lts)
    
    # 从响应中提取增强的LTS部分
    augmented_lts = extract_augmented_lts(augmented_response)
    if augmented_lts:
        # 保存增强的LTS到l2.aut
      with open('l2.aut', 'w') as f:
            f.write(augmented_lts)
    else:
        st.error("Failed to extract augmented LTS from response")
        return
    
    # 从响应中提取mapping部分并保存到rename.ren
    mapping = extract_mapping(augmented_response)
    if mapping:
        with open('rename.ren', 'w') as f:
            f.write(mapping)
    else:
      st.error("Failed to extract mapping from response")
      return
    
    # 从响应中提取场景标签和时间信息
    scene_info = extract_scene_info(augmented_response)
    if scene_info:
        # 在保存之前验证提取的内容
        st.write("Extracted scene information:")
        st.write(scene_info)  # 用于调试
        
        with open('augment_image.txt', 'w') as f:
            f.write(scene_info)
        st.success("Scene information saved successfully")
    else:
        st.error("Failed to extract scene information from response")
        return

    # 在右侧列显示结果
    with col2:
        st.subheader("Generated Files")
        
        st.markdown("**l2.aut (Augmented LTS)**")
        with open('l2.aut', 'r') as f:
            st.text(f.read())
            
        st.markdown("**rename.ren (Mapping)**")
        with open('rename.ren', 'r') as f:
            st.text(f.read())
        
        st.markdown("**augment_image.txt (Scene Labels & Times)**")
        with open('augment_image.txt', 'r') as f:
            st.text(f.read())
        
        # 添加完整GPT响应的显示
        st.markdown("**Complete GPT Response**")
        st.text_area("GPT Response", value=augmented_response, height=400, disabled=True)

def extract_augmented_lts(response):
    # 寻找 "Augmented LTS:" 后面的内容，直到遇到Mapping:
    lts_pattern = r'Augmented LTS:\s*(des.*?)(?=\s*Mapping:|$)'
    lts_match = re.search(lts_pattern, response, re.DOTALL)
    
    if lts_match:
        return lts_match.group(1).strip()
    
    st.error("Failed to extract augmented LTS from response")
    return None

def extract_mapping(response):
    # 寻找 "Mapping:" 后面的内容，直到遇到空行或文件结束
    mapping_pattern = r'Mapping:\s*(.*?)(?=\s*\n\s*\n|$)'
    mapping_match = re.search(mapping_pattern, response, re.DOTALL)
    
    if mapping_match:
        # 提取所有mapping行并清理格式
        mapping_text = mapping_match.group(1).strip()
        # 移除可能的markdown标记
        mapping_text = re.sub(r'\*\*|```', '', mapping_text)
        # 分割成行并过滤空行
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
    return f"""
TASK: Augment the given Labelled Transition System (LTS) with Norm-Aware, Time-Sensitive, and Contextually Verified Transitions.

Input LTS:
{input_lts}

## OBJECTIVE:
1. Enhance LTS with **explicit timing, norm-based constraints, and contextual information**.
2. Ensure **safety properties** are maintained.
3. Preserve **behavioral equivalence** with the original LTS.
4. Provide **a direct and structured augmented LTS output**.
5. Provide mapping between original and augmented transitions.

Formal Requirements:
1. Timing Consistency:
   - All state transitions must follow a monotonic temporal ordering.
   - Introduce contextual waiting times where appropriate (e.g., time to dress before opening the window).
   - Differentiate between simultaneous vs. sequential events.

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

Approach - CLOCK-BASED TIMING (Norm-Aware Augmentation)
Input LTS:
des (0,3,4)
(0,"UserRequestMakingCoffee (kitchenLightOn=false,coffeeBeansAvailable=true,userPreferredTemp=75)",1)
(1,"TurnOnKitchenLight(kitchenLightOn=false,coffeeBeansAvailable=true,userPreferredTemp=75)",2)
(2,"MakeCoffee(kitchenLightOn=true,coffeeBeansAvailable=true,userPreferredTemp=75)",3)

Expected Output (Please strictly follow the format and ensure to add Augmented LTS: and Mapping: and Scene Label and Time: in the output so to parse them to three parts easily)
Augmented LTS:
des (0,6,7)
(0, "UserWokeUp (location=kitchen, userAwake=true, kitchenLightOn=false, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 6:30am] (expected)",1)
(1, "UserRequestMakingCoffee (location=kitchen, userAwake=true, kitchenLightOn=false, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 6:35am] (unexpected - user is in the dark)",2)
(2, "RobotSuggestTurningOnKitchenLight (location=kitchen, userAwake=true, kitchenLightOn=false, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 6:36am] (expected)",3)
(3, "UserAgreeToTurnOnKitchenLight (location=kitchen, userAwake=true, kitchenLightOn=false, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 6:37am] (okay)",4)
(4, "TurnOnKitchenLight (location=kitchen, userAwake=true, kitchenLightOn=true, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 6:38am] (expected)",5)
(5, "MakeCoffee (location=kitchen, userAwake=true, kitchenLightOn=true, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 6:45am] (expected)",6)

Mapping: (Only include the transitions that are originally included in the input LTS)
"UserRequestMakingCoffee (location=kitchen, userAwake=true, kitchenLightOn=false, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 6:35am] (unexpected - user is in the dark)" -> "UserRequestMakingCoffee (kitchenLightOn=false,coffeeBeansAvailable=true,userPreferredTemp=75)"
"TurnOnKitchenLight (location=kitchen, userAwake=true, kitchenLightOn=true, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 6:38am] (expected)" -> "TurnOnKitchenLight (kitchenLightOn=true,coffeeBeansAvailable=true,userPreferredTemp=75)"
"MakeCoffee (location=kitchen, userAwake=true, kitchenLightOn=true, coffeeBeansAvailable=true, userPreferredTemp=75) [CLOCK: 6:45am] (expected)" -> "MakeCoffee (kitchenLightOn=true,coffeeBeansAvailable=true,userPreferredTemp=75)"

Scene Label and Time:
Scene 1: UserWokeUp 6:30am
Scene 2: UserRequestMakingCoffee 6:35am
Scene 3: RobotSuggestTurningOnKitchenLight 6:36am
Scene 4: UserAgreeToTurnOnKitchenLight 6:37am
Scene 5: TurnOnKitchenLight 6:38am
Scene 6: MakeCoffee 6:45am

Verification & Justification
1. Norm Compliance & Correction:
   - Detect unexpected transitions and apply AI intervention.
   - Ensure AI suggestions align with real-world norms.

2. Constraint Satisfaction:
   - Time constraints: Monotonic progression.
   - Safety constraints: No hazardous transitions.
   - Trace equivalence: Augmented LTS maintains original logic.

Final Deliverables:
1. Augmented LTS with norm-aware enhancements.
2. Mapping between original and augmented transitions. Ensure to write the mapping in the same format as above so to directly use in rename.ren file for CADP rename operation.
3. Scene Label and Time. Ensure to write the scene label and time in the same format as above so to directly use in augment_image file for image augmentation.
"""

def generate_svl_file(rename_content):
    # 从rename.ren中读取重命名规则
    rename_rules = []
    for line in rename_content.split('\n'):
        if '->' in line:
            old, new = line.split('->')
            # 移除所有引号和逗号，然后重新添加引号
            old = old.strip().strip('"').strip(',')
            new = new.strip().strip('"').strip(',')
            
            # 只转义方括号
            old_escaped = old.replace('[', '\[').replace(']', '\]')
            new_escaped = new  # 新的标签不需要转义
            
            # 使用正确的格式，确保每个规则都是独立的一行
            rename_rules.append(f'    "{old_escaped}" -> "{new_escaped}"')
    
    # 生成SVL内容，使用标准格式
    svl_content = f'''property RENAME_RULES
    "Rename transitions to their abstract form"
is
    "renamed.bcg" = total rename
{",\n".join(rename_rules)}
    in "l2.bcg";
    % bcg_io "renamed.bcg" "renamed.aut"
end property'''
    
    # 保存SVL文件
    with open('rename.svl', 'w') as f:
        f.write(svl_content)
    
    st.write("Debug - Generated SVL content:", svl_content)  # 调试信息

def run_equivalence_check():
    try:
        # 检查文件是否存在
        if not os.path.exists('l1.aut'):
            st.error("l1.aut file does not exist")
            return False, "l1.aut file missing"
            
        if not os.path.exists('l2.aut'):
            st.error("l2.aut file does not exist")
            return False, "l2.aut file missing"
            
        # 检查文件内容
        with open('l1.aut', 'r') as f:
            l1_content = f.read()
            if not l1_content.strip():
                st.error("l1.aut is empty")
                return False, "l1.aut is empty"
        
        # 转换和检查过程
        st.write("Converting l1.aut to l1.bcg...")
        subprocess.run(['bcg_io', 'l1.aut', 'l1.bcg'], check=True)
        
        st.write("Converting l2.aut to l2.bcg...")
        subprocess.run(['bcg_io', 'l2.aut', 'l2.bcg'], check=True)
        
        # 运行 rename 操作
        st.write("Running rename operation...")
        rename_result = subprocess.run(['svl', 'rename.svl'], 
                                     capture_output=True, 
                                     text=True,
                                     check=True)
        st.write("Rename output:", rename_result.stdout)
        
        # 运行等价性检查，使用weak bisimulation
        st.write("Running equivalence check...")
        result = subprocess.run(
            ['bcg_open', 'l1.bcg', 'bisimulator', '-weaktrace', 'renamed.bcg'],  # 改用-weak参数
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

def generate_character_scene_prompts(lts_content):
    prompt = f"""
Based on the following augmented LTS transitions, generate concise but detailed prompts for image generation.
Focus on visual elements that can be clearly depicted in images.

1. CHARACTER DESCRIPTION:
Create a consistent character description including:
- Age range and gender
- Basic appearance (height, build)
- Clothing style (casual/sleepwear for morning routine)
- General expression

2. SCENE DESCRIPTIONS:
For each transition, describe the key visual elements:
- Environment (kitchen setting)
- Lighting conditions
- Character's action/pose
- Important objects
- Time of day indicators

LTS Content:
{lts_content}

Format your response exactly as:
CHARACTER DESCRIPTION:
[single paragraph character description]

SCENE DESCRIPTIONS:
1. [first scene description]
2. [second scene description]
(etc.)

Keep descriptions focused on visual elements that can be clearly depicted in images.
"""
    return prompt

def generate_flux_pro_prompt(character_desc):
    # 为Flux Pro模型格式化character描述
    flux_pro_prompt = f"""
A highly detailed character portrait:
{character_desc}
Style: Photorealistic, detailed, high quality, 8k
"""
    return flux_pro_prompt

def call_flux_pro(api_key, prompt):
    try:
        # 设置环境变量
        os.environ['FAL_KEY'] = api_key
        
        # 调用API
        result = fal_client.subscribe(
            "fal-ai/flux-pro/v1.1-ultra",
            arguments={
                "prompt": prompt,
                "image_size": "landscape_16_9",  # 使用预定义的尺寸
                "num_images": 1,
                "output_format": "jpeg"
            }
        )
        
        return result['images'][0]['url'] if result and 'images' in result else None
            
    except Exception as e:
        raise Exception(f"Flux Pro API error: {str(e)}")

def call_pulid_flux(api_key, scene_prompt, character_image_url):
    if not scene_prompt or not character_image_url:
        st.error("Missing scene prompt or character image URL")
        return None
    
    # 定义不同的参数组合
    parameter_sets = [
        {
            "image_size": "landscape_16_9",
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
            "face_strength": 0.8,
            "style_strength": 0.6,
        },
        {
            "image_size": "square_hd",
            "num_inference_steps": 40,
            "guidance_scale": 8.5,
            "face_strength": 1.0,
            "style_strength": 0.8,
        },
        {
            "image_size": "portrait_9_16",
            "num_inference_steps": 35,
            "guidance_scale": 7.0,
            "face_strength": 0.9,
            "style_strength": 0.7,
        }
    ]
    
    for i, params in enumerate(parameter_sets):
        try:
            st.write(f"Trying parameter set {i + 1}...")
            
            # 设置环境变量
            os.environ['FAL_KEY'] = api_key
            
            # 构建API参数
            api_params = {
                "prompt": scene_prompt,
                "reference_image_url": character_image_url,
                "negative_prompt": "bad quality, worst quality, blurry, distorted face, bad face, bad eyes, bad anatomy",
                "seed": -1,
                **params
            }
            
            # 调用API
            result = fal_client.subscribe(
                "fal-ai/flux-pulid",
                arguments=api_params
            )
            
            if result and 'images' in result and result['images']:
                image_url = result['images'][0].get('url')
                if image_url:
                    st.success(f"Successfully generated image with parameter set {i + 1}")
                    return image_url
            
            st.warning(f"No valid image from parameter set {i + 1}, trying next set...")
            
        except Exception as e:
            st.warning(f"Parameter set {i + 1} failed: {str(e)}")
            continue
    
    st.error("All parameter sets failed to generate image")
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
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a JSON-only response evaluator. Always respond with valid JSON in the exact format specified."},
            {"role": "user", "content": evaluation_prompt}
        ],
        max_tokens=1500
    )
    
    return response.choices[0].message.content.strip()

def evaluate_and_select_best_image(api_key, character_image, scene_images, character_desc, scene_desc):
    try:
        client = OpenAI(api_key=api_key)
        evaluation_result = get_evaluation(client, character_image, scene_images, character_desc, scene_desc)
        eval_json = json.loads(evaluation_result)
        
        # 检查是否所有图片都通过两个评估标准
        best_image_index = -1
        for eval in eval_json['evaluations']:
            if (eval['character_consistency']['consistent'].lower() == 'yes' and 
                eval['scene_accuracy']['accurate'].lower() == 'yes'):
                best_image_index = eval['image_index']
                break
        
        eval_json['best_image'] = best_image_index
        return json.dumps(eval_json)
        
    except Exception as e:
        raise Exception(f"Evaluation error: {str(e)}")

def generate_scene_images(fal_api_key, scene_desc, character_image_url):
    if not fal_api_key or not scene_desc or not character_image_url:
        st.error("Missing required parameters for scene generation")
        return None
    
    scene_images = []
    max_retries = 5  # 增加重试次数
    
    for i in range(3):  # 生成3张图片
        retry_count = 0
        while retry_count < max_retries:
            try:
                st.write(f"Generating image {i+1}/3 (attempt {retry_count+1}/{max_retries})...")
                image_url = call_pulid_flux(fal_api_key, scene_desc, character_image_url)
                
                if image_url:
                    scene_images.append(image_url)
                    st.success(f"Successfully generated image {i+1}")
                    break  # 成功生成，继续下一张图片
                
                retry_count += 1
                if retry_count < max_retries:
                    st.warning(f"Retrying image {i+1} generation...")
                    time.sleep(3)  # 增加延迟时间
                
            except Exception as e:
                st.error(f"Error in attempt {retry_count+1}: {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    st.warning("Retrying...")
                    time.sleep(3)
        
        if retry_count >= max_retries:
            st.error(f"Failed to generate image {i+1} after {max_retries} attempts")
            return None
    
    # 确保生成了所有3张图片
    if len(scene_images) == 3:
        return scene_images
    
    st.error(f"Only generated {len(scene_images)}/3 images")
    return None

def display_evaluation_results(evaluations, col2, col3):
    # 初始化session state
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 0
    if 'evaluations' not in st.session_state:
        st.session_state['evaluations'] = evaluations
    
    total_pages = len(evaluations)
    
    with col2:
        st.subheader("Generation Results")
        
        # 添加分页控制
        cols = st.columns([1, 2, 1])  # 调整列宽比例
        
        # 为每个页面生成唯一的按钮key
        page_id = st.session_state.get('current_page', 0)
        
        # Previous按钮
        if cols[0].button("⬅️ Previous", 
                         disabled=st.session_state['current_page'] <= 0,
                         key=f"prev_button_{page_id}"):  # 添加页码到key
            st.session_state['current_page'] -= 1
            st.rerun()
        
        # 页码显示
        cols[1].markdown(f"<h4 style='text-align: center'>Scene {st.session_state['current_page'] + 1}/{total_pages}</h4>", 
                        unsafe_allow_html=True)
        
        # Next按钮
        if cols[2].button("Next ➡️", 
                         disabled=st.session_state['current_page'] >= total_pages - 1,
                         key=f"next_button_{page_id}"):  # 添加页码到key
            st.session_state['current_page'] += 1
            st.rerun()
        
        # 确保页码在有效范围内
        st.session_state['current_page'] = max(0, min(st.session_state['current_page'], total_pages - 1))
        
        # 显示当前页的评估结果
        if evaluations and 0 <= st.session_state['current_page'] < len(evaluations):
            eval = evaluations[st.session_state['current_page']]
            scene_num = eval['scene_number']
            
            # 显示场景描述
            st.markdown(f"### Scene {scene_num}")
            st.markdown(f"*{eval['scene_desc']}*")
            
            # 显示图片选项
            image_cols = st.columns(3)
            for idx, img_url in enumerate(eval['all_images']):
                with image_cols[idx]:
                    st.image(img_url, caption=f"Option {idx + 1}")
            
            # 显示评估结果
            with st.expander("Show Evaluation Details", expanded=True):
                st.json(eval['evaluation'])
                
                # Regenerate按钮
                try:
                    eval_json = json.loads(eval['evaluation'])
                    if eval_json['best_image'] == -1:
                        # 获取角色描述
                        character_desc = st.session_state.get('character_scene_prompts', '').split('SCENE DESCRIPTIONS:')[0].replace('CHARACTER DESCRIPTION:', '').strip()
                        
                        if st.button(f"Regenerate Scene {scene_num}", 
                                   key=f"regen_scene_{scene_num}_{st.session_state['current_page']}"):
                            if not all([
                                st.session_state.get('fal_api_key'),
                                st.session_state.get('openai_api_key'),
                                st.session_state.get('character_image_url'),
                                character_desc
                            ]):
                                st.error("Missing required parameters. Please ensure all API keys and character information are available.")
                                return
                                
                            regenerate_single_scene(
                                scene_num,
                                eval['scene_desc'],
                                st.session_state['fal_api_key'],
                                st.session_state['openai_api_key'],
                                st.session_state['character_image_url'],
                                character_desc
                            )
                except json.JSONDecodeError:
                    st.error(f"Invalid evaluation result format for Scene {scene_num}")

def regenerate_single_scene(scene_num, scene_desc, fal_api_key, openai_api_key, character_image_url, character_desc):
    try:
        if not all([scene_num, scene_desc, fal_api_key, openai_api_key, character_image_url, character_desc]):
            st.error("Missing required parameters for regeneration")
            return False
            
        with st.spinner(f"Regenerating scene {scene_num}..."):
            # 生成新的3张图片
            scene_images = generate_scene_images(fal_api_key, scene_desc, character_image_url)
            
            if scene_images and len(scene_images) == 3:
                # 评估并选择最佳图片
                evaluation_result = evaluate_and_select_best_image(
                    openai_api_key,
                    character_image_url,
                    scene_images,
                    character_desc,
                    scene_desc
                )
                
                # 更新session state中的数据
                eval_json = json.loads(evaluation_result)
                best_image_index = int(eval_json['best_image'])
                
                # 更新评估结果
                st.session_state['scene_evaluations'][scene_num - 1] = {
                    'scene_number': scene_num,
                    'evaluation': evaluation_result,
                    'all_images': scene_images,
                    'scene_desc': scene_desc
                }
                
                # 更新选中的图片
                if best_image_index >= 0:
                    st.session_state['generated_scenes'][scene_num - 1] = (scene_desc, scene_images[best_image_index])
                else:
                    st.session_state['generated_scenes'][scene_num - 1] = (scene_desc, None)
                
                st.success(f"Successfully regenerated scene {scene_num}")
                st.rerun()
                return True
            
            st.error(f"Failed to generate all images for scene {scene_num}")
            return False
            
    except Exception as e:
        st.error(f"Error regenerating scene: {str(e)}")
        return False

def generate_timetable(api_key, lts_content):
    prompt = f"""
Extract a timetable from the following LTS content. 
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
    
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a JSON-only response generator."},
            {"role": "user", "content": prompt}
        ]
    )
    
    return json.loads(response.choices[0].message.content)

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
            # 提取转换名称（去掉参数部分）
            name = label.split('(')[0].strip()
            transitions.append({
                'label': name,
                'time': timestamp,
                'state': state
            })
    
    return {'transitions': transitions}

def augment_image_with_label(image_url, label, timestamp):
    """为图片添加标签和时间戳"""
    try:
        # 下载图片
        response = requests.get(image_url)
        img = Image.open(BytesIO(response.content))
        
        # 创建绘图对象
        draw = ImageDraw.Draw(img)
        
        # 设置字体（如果没有Arial则使用默认字体）
        try:
            font = ImageFont.truetype("Arial.ttf", 36)
        except:
            font = ImageFont.load_default()
        
        # 准备文本
        text = f"{label}\n{timestamp}"
        
        # 添加文本（白色文字带黑色边框）
        x, y = 10, 10  # 文本位置
        # 绘制黑色边框
        draw.text((x-2, y-2), text, font=font, fill='black')
        draw.text((x+2, y-2), text, font=font, fill='black')
        draw.text((x-2, y+2), text, font=font, fill='black')
        draw.text((x+2, y+2), text, font=font, fill='black')
        # 绘制白色文本
        draw.text((x, y), text, font=font, fill='white')
        
        # 转换为字节流
        img_byte_arr = BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return img_byte_arr
    
    except Exception as e:
        st.error(f"Error augmenting image: {str(e)}")
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
            
        scene_info = {}
        # 清理内容：移除多余的空格和换行
        content = ' '.join(content.split())
        # 分割场景
        scenes = content.split('Scene')[1:]  # 跳过第一个空字符串
        
        for scene in scenes:
            try:
                # 提取场景编号和内容
                match = re.match(r'(\d+):\s*(.*?)\s+(\d+:\d+[ap]m)', scene.strip())
                if match:
                    scene_num = int(match.group(1))
                    label = match.group(2).strip()
                    time = match.group(3).strip()
                    
                    scene_info[scene_num] = {
                        'label': label,
                        'time': time
                    }
                    # st.write(f"Debug - Parsed Scene {scene_num}:", 
                    #        f"Label: {label}, Time: {time}")  # 调试信息
            except Exception as e:
                st.error(f"Error parsing scene: {scene.strip()}: {str(e)}")
                continue
        
        # st.write("Debug - All Scene Info:", scene_info)  # 调试信息
        return scene_info
        
    except Exception as e:
        st.error(f"Error reading scene labels: {str(e)}")
        return {}

def display_final_results(col3, generated_scenes):
    with col3:
        st.subheader("Final Results")
        
        # 获取场景标签和时间信息
        scene_info = get_scene_labels()
        
        # 显示图片（自动添加标签）
        for i, (desc, url) in enumerate(generated_scenes):
            scene_num = i + 1
            st.markdown(f"**Scene {scene_num}**")
            st.markdown(f"*{desc}*")
            
            if url:
                if scene_num in scene_info:
                    # st.write(f"Debug - Adding labels for scene {scene_num}")  # 调试信息
                    # 自动添加标签和时间戳
                    augmented_img = augment_image_with_label(
                        url,
                        scene_info[scene_num]['label'],
                        scene_info[scene_num]['time']
                    )
                    
                    if augmented_img:
                        st.image(augmented_img)
                    else:
                        st.image(url)
                        st.warning(f"Failed to add labels to scene {scene_num}")
                else:
                    st.image(url)
                    st.warning(f"No label information found for scene {scene_num}")
            else:
                st.warning("No suitable image was found for this scene")

def main():
    st.set_page_config(page_title="LTS Augmentation Tool", layout="wide")
    
    st.title("LTS Augmentation Tool")
    st.markdown("---")
    
    # 创建三列布局
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Input")
        # LTS输入区域
        input_lts = st.text_area(
            "Enter your LTS in CADP format:",
                               height=200,
            placeholder="des (0,3,4)\n(0,\"Action1\",1)\n...",
            help="Enter your LTS in CADP format"
        )
        
        # API Keys 输入区域
        st.subheader("API Keys")
        openai_api_key = st.text_input(
            "OpenAI API Key:",
            type="password",
            help="Enter your OpenAI API key for LTS augmentation"
        )
        
        fal_api_key = st.text_input(
            "FAL API Key:",
            type="password",
            help="Enter your FAL API key for image generation"
        )
        
        # 按钮区域
        st.subheader("Operations")
        
        # 创建两行按钮
        button_row1_col1, button_row1_col2 = st.columns(2)
        button_row2_col1 = st.columns(1)[0]  # 只需要一个按钮了
        
        with button_row1_col1:
            # Augment LTS按钮
            if st.button("Generate Augmented LTS", type="primary"):
                if not openai_api_key:
                    st.error("Please enter your OpenAI API key.")
                    return
                
                if not input_lts:
                    st.error("Please enter your LTS.")
                    return
                
                try:
                    client = OpenAI(api_key=openai_api_key)
                    prompt = generate_prompt(input_lts)
                    
                    with st.spinner("Generating augmented LTS..."):
                        completion = client.chat.completions.create(
                            model="gpt-4",
                            messages=[
                                {"role": "system", "content": "You are an assistant for formal process modeling."},
                                {"role": "user", "content": prompt}
                            ]
                        )
                        
                        response = completion.choices[0].message.content
                        
                        # 保存文件并显示结果，传入col2
                        save_to_files(input_lts, response, col2)
                        
                        st.success("Files generated successfully!")
                        
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    st.markdown("**Generated Prompt**")
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
                if not openai_api_key or not fal_api_key:
                    st.error("Please enter both OpenAI and FAL API keys.")
                    return
                
                # 保存API keys到session state
                st.session_state['fal_api_key'] = fal_api_key
                st.session_state['openai_api_key'] = openai_api_key
                
                try:
                    # 1. 生成图片提示
                    if not os.path.exists('l2.aut'):
                        st.error("Please generate augmented LTS first")
                        return
                        
                    with open('l2.aut', 'r') as f:
                        lts_content = f.read()
                    
                    with st.spinner("Generating image prompts..."):
                        try:
                            # 调用GPT-4生成prompts
                            client = OpenAI(api_key=openai_api_key)
                            response = client.chat.completions.create(
                                model="gpt-4",
                                messages=[
                                    {"role": "system", "content": "You are an expert in generating clear, specific image prompts."},
                                    {"role": "user", "content": generate_character_scene_prompts(lts_content)}
                                ],
                                max_tokens=2000,  # 增加token限制
                                temperature=0.7    # 适当增加创造性
                            )
                            
                            prompts = response.choices[0].message.content
                            
                            # 验证prompts格式
                            if "CHARACTER DESCRIPTION:" not in prompts or "SCENE DESCRIPTIONS:" not in prompts:
                                raise Exception("Generated prompts are not in the correct format")
                            
                            st.session_state['character_scene_prompts'] = prompts
                            
                            # 显示生成的prompts
                            with col2:
                                st.subheader("Generated Prompts")
                                st.text_area("Character & Scene Prompts", prompts, height=400)
                                
                            st.success("Successfully generated image prompts!")
                            
                        except Exception as e:
                            st.error(f"Error generating prompts: {str(e)}")
                            st.error("Please try again or check your OpenAI API key")
                            return
                    
                    # 2. 生成角色图片
                    with st.spinner("Generating character..."):
                        character_desc = prompts.split('SCENE DESCRIPTIONS:')[0].replace('CHARACTER DESCRIPTION:', '').strip()
                        flux_pro_prompt = generate_flux_pro_prompt(character_desc)
                        
                        character_image_url = call_flux_pro(fal_api_key, flux_pro_prompt)
                        if character_image_url:
                            st.session_state['character_image_url'] = character_image_url
                            
                            # 显示角色图片
                            with col3:
                                st.subheader("Generated Character")
                                st.markdown(f"*{character_desc}*")
                                st.image(character_image_url)
                        else:
                            st.error("Failed to generate character image")
                            return
                    
                    # 3. 生成场景图片
                    scene_descriptions = prompts.split('SCENE DESCRIPTIONS:')[1].strip().split('\n')
                    scene_descriptions = [desc.strip() for desc in scene_descriptions if desc.strip()]
                    scene_descriptions = [desc[desc.find('.') + 1:].strip() if desc[0].isdigit() else desc for desc in scene_descriptions]
                    
                    with st.spinner("Generating and evaluating scenes..."):
                        generated_scenes = []
                        evaluations = []
                        
                        # 显示进度条
                        progress_bar = st.progress(0)
                        
                        for i, scene_desc in enumerate(scene_descriptions):
                            progress = (i + 1) / len(scene_descriptions)
                            progress_bar.progress(progress)
                            
                            st.write(f"Generating scene {i + 1}/{len(scene_descriptions)}...")
                            
                            # 为每个场景生成3张图片
                            scene_images = generate_scene_images(fal_api_key, scene_desc, character_image_url)
                            
                            if len(scene_images) == 3:
                                # 评估并选择最佳图片
                                evaluation_result = evaluate_and_select_best_image(
                                    openai_api_key,
                                    character_image_url,
                                    scene_images,
                                    character_desc,
                                    scene_desc
                                )
                                
                                try:
                                    eval_json = json.loads(evaluation_result)
                                    best_image_index = int(eval_json['best_image'])
                                    
                                    evaluations.append({
                                        'scene_number': i + 1,
                                        'evaluation': evaluation_result,
                                        'all_images': scene_images,
                                        'scene_desc': scene_desc
                                    })
                                    
                                    if best_image_index >= 0:
                                        generated_scenes.append((scene_desc, scene_images[best_image_index]))
                                    else:
                                        generated_scenes.append((scene_desc, None))
                                
                                except json.JSONDecodeError:
                                    st.error(f"Invalid evaluation result format for Scene {i + 1}")
                            else:
                                st.error(f"Failed to generate all images for Scene {i + 1}")
                        
                        # 保存结果到session state
                        st.session_state['generated_scenes'] = generated_scenes
                        st.session_state['scene_evaluations'] = evaluations
                        
                        # 显示结果
                        display_evaluation_results(evaluations, col2, col3)
                        
                        # 显示最终结果（使用新的display_final_results函数）
                        display_final_results(col3, generated_scenes)
                
                except Exception as e:
                    st.error(f"Error in scene generation: {str(e)}")
    
    # 初始化session state
    if 'initialized' not in st.session_state:
        st.session_state['initialized'] = True
        st.session_state['current_page'] = 0
        st.session_state['character_scene_prompts'] = None
        st.session_state['character_image_url'] = None
        st.session_state['generated_scenes'] = None
        st.session_state['scene_evaluations'] = None

    # 在生成场景后显示结果
    if st.session_state.get('scene_evaluations') and st.session_state.get('generated_scenes'):
        # 显示角色图片（如果存在）
        if st.session_state.get('character_image_url'):
            with col3:
                st.subheader("Generated Character")
                st.image(st.session_state['character_image_url'])
        
        # 显示评估结果
        display_evaluation_results(
            st.session_state['scene_evaluations'],
            col2,
            col3
        )
        
        # 显示最终结果（使用新的display_final_results函数）
        display_final_results(col3, st.session_state['generated_scenes'])

if __name__ == "__main__":
    main()