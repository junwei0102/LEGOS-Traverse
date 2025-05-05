import sys
from translator import build_event_measure_map, parse_trace

def test_build_event_measure_map():
    with open('test_rules.sleec', 'r') as f:
        rules_content = f.read()
    
    event_map = build_event_measure_map(rules_content)
    print("\nEvent measure map:")
    for event, measures in event_map.items():
        print(f"{event}: {measures}")
    
    # 验证映射是否正确
    expected_map = {
        'InstructionFail': {
            'numeric': {('instructionRepeat', '>=', 3), ('timeElapsed', '>', 20)},
            'bool': set(),
            'not_bool': set()
        },
        'MeetingUser': {
            'numeric': set(),
            'bool': set(),
            'not_bool': {'trainingDataRepresentative'}
        },
        'ExaminingPatient': {
            'numeric': set(),
            'bool': {'behaviorAggressive'},
            'not_bool': set()
        }
    }
    
    assert event_map == expected_map, f"Expected {expected_map}, but got {event_map}"
    print("Event measure map test passed!")

def test_parse_trace():
    with open('test_trace.txt', 'r') as f:
        trace_content = f.read()
    
    lts_output = parse_trace(trace_content)
    print("\nGenerated LTS:")
    print(lts_output)
    
    expected_output = '''des (0, 5, 6)
(0, "CallSupport(time=0)", 1)
(1, "InstructionFail(timeElapsed=21, time=1)", 2)
(2, "CallSupport(time=1)", 3)
(3, "MeetingUser(trainingDataRepresentative=False, time=1)", 4)
(4, "ExaminingPatient(behaviorAggressive=True, time=1)", 5)'''
    
    assert lts_output.strip() == expected_output.strip(), \
        f"Expected:\n{expected_output}\n\nBut got:\n{lts_output}"
    print("Parse trace test passed!")

if __name__ == "__main__":
    print("Testing build_event_measure_map...")
    test_build_event_measure_map()
    
    print("\nTesting parse_trace...")
    test_parse_trace() 