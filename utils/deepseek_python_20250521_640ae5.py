import json
import re
from typing import List, Tuple, Dict, Set

def strict_standardize_name(name: str) -> str:
    """Convert to snake_case without creating new names"""
    name = re.sub(r"['’]", "", name)
    name = re.sub(r'[\s–\-]+', '_', name)
    return name.lower().strip('_')

def load_pose_patterns(pattern_file: str) -> Tuple[Dict[str, str], List[re.Pattern]]:
    """Load patterns and create quick lookup dict"""
    patterns = []
    lookup = {}
    with open(pattern_file, 'r') as f:
        for line in f:
            pattern_str, std_name = line.strip().split('|||')
            compiled = re.compile(pattern_str, flags=re.IGNORECASE)
            #compiled = re.compile(rf'(?i)\b{pattern_str}\b')
            patterns.append(compiled)
            lookup[std_name] = compiled
    return lookup, patterns

def extract_pose_and_note(original_pose: str, patterns: Dict[str, re.Pattern]) -> Tuple[str, str]:
    """Find exact match from pattern_pose.txt without generating new names"""
    # Try full original pose match first
    for std_name, pattern in patterns.items():
        if pattern.fullmatch(original_pose):
            return std_name, ""
    
    # Try common variations without splitting
    cleaned = strict_standardize_name(original_pose)
    if cleaned in patterns:
        return cleaned, ""
    
    # If no match found, return original with error flag
    return original_pose, "[INVALID_POSE]"

def process_courses(input_file: str, pose_pattern_file: str, output_file: str) -> None:
    # Load pose patterns
    pose_lookup, pose_patterns = load_pose_patterns(pose_pattern_file)
    valid_poses = set(pose_lookup.keys())
    
    # Load original data
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    processed = []
    validation_errors = []
    
    for course in data['course']:
        # Process course name
        std_course_name = strict_standardize_name(course['name'])
        
        # Process sequence
        seq = []
        for item in course['sequence']:
            original_pose = item['pose']
            pose_name, note = extract_pose_and_note(original_pose, pose_lookup)
            
            # Validate
            if pose_name not in valid_poses:
                validation_errors.append(
                    f"Course: {std_course_name} - Invalid pose: {original_pose}"
                )
                note = f"[INVALID] {note}"
            
            seq.append({
                "pose": pose_name,
                "action_note": note,
                "duration_seconds": item['duration_seconds'],
                "repeat_times": item['repeat_times'],
                "transition_notes": item['transition_notes']
            })
        
        processed.append({
            "name": std_course_name,
            "challenge": course['challenge'],
            "description": course['description'],
            "total_duration": course['total_duration'],
            "sequence": seq
        })
    
    # Save results
    with open(output_file, 'w') as f:
        json.dump({"course": processed}, f, indent=2)
    
    # Save errors
    if validation_errors:
        with open('validation_errors.txt', 'w') as f:
            f.write("\n".join(validation_errors))

if __name__ == '__main__':
    process_courses(
        input_file='array_course.json',
        pose_pattern_file='pattern_pose.txt',
        output_file='cleaned_courses.json'
    )