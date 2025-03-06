import os
import json
from typing import Dict, List, Tuple
import sys

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)  # 添加当前目录（项目根目录）

from LEGOs.Sleec.sleecParser import parse_sleec, check_input_red, check_input_conflict, check_input_concerns, parse_and_max_trace

def run_sleec_parser(sleec_file: str, time_window: int = 15) -> Tuple[List[str], List[Dict]]:
    """
    运行LEGOS的sleecParser来获取触发最多规则的trace
    
    Args:
        sleec_file: SLEEC文件的路径
        time_window: 时间窗口大小（默认15）
        
    Returns:
        Tuple[List[str], List[Dict]]: 返回(触发的规则列表, 最终的trace)
    """
    try:
        # 直接调用parse_and_max_trace函数
        output = parse_and_max_trace(sleec_file, tracetime=time_window)
        
        # 保存完整输出到文件
        with open('parser_output.txt', 'w') as f:
            f.write(output)
            
        # 读取文件并解析trace
        trace = []
        with open('parser_output.txt', 'r') as f:
            for line in f:
                if line.startswith("at time"):
                    # 解析时间和事件
                    time_str, event = line.split(": ", 1)
                    time = int(time_str.replace("at time ", ""))
                    
                    # 解析事件和参数
                    if "(" in event:
                        event_name = event.split("(")[0]
                        params_str = event[event.find("(")+1:event.find(")")]
                        params = {}
                        if params_str:
                            for param in params_str.split(", "):
                                if "=" in param:
                                    key, value = param.split("=")
                                    # 转换布尔值和数字
                                    if value.lower() == "true":
                                        value = True
                                    elif value.lower() == "false":
                                        value = False
                                    else:
                                        try:
                                            value = int(value)
                                        except ValueError:
                                            value = value
                                    params[key] = value
                    else:
                        event_name = event.strip()
                        params = {}
                    
                    trace.append({
                        "time": time,
                        "event": event_name,
                        "params": params
                    })
        
        return ["Trace generated"], trace  # 简单起见，我们不解析具体的规则了
        
    except Exception as e:
        print(f"Error running LEGOS parser: {str(e)}")
        return [], []

def convert_trace_to_lts(trace: List[Dict]) -> str:
    """
    将LEGOS生成的trace转换为LTS格式
    
    Args:
        trace: LEGOS生成的trace列表
        
    Returns:
        str: LTS格式的字符串
    """
    # 计算转换数量
    transitions = len(trace)
    
    # 构建LTS字符串
    lts = [f"des (0,{transitions},{transitions})"]
    
    # 添加每个转换
    for i, event in enumerate(trace):
        # 构建参数字符串
        params = []
        for key, value in event["params"].items():
            params.append(f"{key}={value}")
        params_str = ", ".join(params)
        
        # 构建完整的转换标签
        if params:
            label = f'{event["event"]}({params_str}, time={event["time"]})'
        else:
            label = f'{event["event"]}(time={event["time"]})'
            
        # 添加转换
        lts.append(f'({i}, "{label}", {i+1})')
    
    return "\n".join(lts)

def generate_lts_from_sleec(sleec_file: str, time_window: int = 15) -> bool:
    """
    从SLEEC文件生成trace
    
    Args:
        sleec_file: SLEEC文件的路径
        time_window: 时间窗口大小
        
    Returns:
        bool: 是否成功生成trace
    """
    try:
        # 运行LEGOS解析器生成trace
        output = parse_and_max_trace(sleec_file, tracetime=time_window)
        
        # 保存完整输出到文件
        with open('parser_output.txt', 'w') as f:
            f.write(output)
            
        return True
            
    except Exception as e:
        print(f"Error running LEGOS parser: {str(e)}")
        return False 