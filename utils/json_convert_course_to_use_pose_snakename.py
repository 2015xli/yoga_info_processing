import json
import re
from typing import List, Tuple, Dict, Set

def load_ordered_patterns(pattern_file: str) -> List[Tuple[re.Pattern, str]]:
    """Load patterns while preserving original order (longest first)"""
    patterns = []
    with open(pattern_file, 'r') as f:
        for line in f:
            pattern_str, std_name = line.strip().split('|||')
            # Compile with word boundaries and case insensitivity
            patterns.append((
                re.compile(pattern_str, flags=re.IGNORECASE),
                std_name
            ))
    return patterns

def process_pose_string(original: str, patterns: List[Tuple[re.Pattern, str]]) -> str:
    """Replace all pose mentions in string using ordered patterns"""
    processed = original
    for pattern, std_name in patterns:
        processed = pattern.sub(std_name, processed)
    return processed

def split_pose_note(processed_str: str) -> Tuple[str, str]:
    """Split into pose and note using first separator"""
    # Split on first occurrence of common separators
    split_chars = ['–', ',','-', ':', ';', '(']
    for char in split_chars:
        if char in processed_str:
            parts = processed_str.split(char, 1)
            return parts[0].strip(), parts[1].strip()
    
    # Fallback to space-based split if no separators
    parts = re.split(r'\s+', processed_str, maxsplit=1)
    return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""

def process_courses(
    input_file: str,
    pose_pattern_file: str,
    output_file: str
) -> None:
    # Load patterns in original order (longest first)
    patterns = load_ordered_patterns(pose_pattern_file)
    valid_poses = {std_name for _, std_name in patterns}
    
    # Load course data
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    processed_courses = []
    validation_errors = []
    
    for course in data['course']:
        # Process course name
        std_course_name = re.sub(r'[^\w]+', '_', course['name']).lower().strip('_')
        
        # Process sequence items
        processed_sequence = []
        for item in course['sequence']:
            original_pose = item['pose']
            
            # Step 1: Replace all pose mentions in the string
            replaced_str = process_pose_string(original_pose, patterns)
            
            # Step 2: Split into pose and note
            main_pose, action_note = split_pose_note(replaced_str)
            
            # Step 3: Validate main pose
            is_valid = main_pose in valid_poses
            if not is_valid:
                validation_errors.append(
                    f"Course: {std_course_name} - Invalid pose: {original_pose} → {main_pose}"
                )
                action_note = f"[INVALID] {action_note}"
            
            processed_sequence.append({
                "pose": main_pose,
                "action_note": action_note,
                "duration_seconds": item['duration_seconds'],
                "repeat_times": item['repeat_times'],
                "transition_notes": process_pose_string(item['transition_notes'], patterns)
            })
        
        processed_courses.append({
            "name": std_course_name,
            "challenge": course['challenge'],
            "description": process_pose_string(course['description'], patterns),
            "total_duration": course['total_duration'],
            "sequence": processed_sequence
        })
    
    # Save results
    with open(output_file, 'w') as f:
        json.dump({"course": processed_courses}, f, indent=2)
    
    # Save validation report
    if validation_errors:
        with open('validation_errors.txt', 'w', encoding="utf-8") as f:
            f.write("\n".join(validation_errors))

if __name__ == '__main__':
    process_courses(
        input_file='knowledge_graph/array_course.json',
        pose_pattern_file='knowledge_graph/pattern_pose.txt',
        #pose_pattern_file='pattern_pose.txt',
        output_file='cleaned_courses.json'
    )