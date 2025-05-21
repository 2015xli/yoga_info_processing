import json
import re
import argparse
from typing import Dict, List, Tuple

def standardize_name(name: str) -> str:
    """Convert names to snake_case with consistent separators."""
    name = re.sub(r"['’]", "", name)
    name = re.sub(r'[\s–\-]+', '_', name)
    name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
    name = re.sub(r'_+', '_', name).strip('_')
    return name

def load_patterns(filename: str) -> List[Tuple[re.Pattern, str]]:
    """Load patterns from file."""
    patterns = []
    with open(filename, 'r') as f:
        for line in f:
            pattern_str, standardized = line.strip().split('|||')
            patterns.append((re.compile(pattern_str), standardized))
    return patterns

def split_pose_and_note(pose_str: str, patterns: List[Tuple[re.Pattern, str]]) -> Tuple[str, str]:
    """Split pose name and action note, standardizing the pose name."""
    # Split on common separators
    parts = re.split(r'\s*[–\-:]\s*|\s+each\s+', pose_str, 1)
    main_pose = parts[0].strip()
    note = parts[1].strip() if len(parts) > 1 else ""
    
    # Standardize main pose name using patterns
    for pattern, std_name in patterns:
        if pattern.search(main_pose):
            return std_name, note
    return standardize_name(main_pose), note

def process_courses(input_file: str, pose_patterns: List[Tuple[re.Pattern, str]], 
                  course_pattern_file: str, debug: bool = False):
    # Load original data
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    course_patterns = []
    processed_courses = []
    
    for course in data['course']:
        # Process course name
        original_name = course['name']
        std_course_name = standardize_name(original_name)
        course_patterns.append((original_name, std_course_name))
        
        # Process sequence items
        processed_sequence = []
        for item in course['sequence']:
            # Split pose name and action note
            std_pose, action_note = split_pose_and_note(item['pose'], pose_patterns)
            
            # Create new sequence item
            new_item = {
                "pose": std_pose,
                "action_note": action_note,
                "duration_seconds": item['duration_seconds'],
                "repeat_times": item['repeat_times'],
                "transition_notes": item['transition_notes']
            }
            processed_sequence.append(new_item)
        
        # Replace pose mentions in all text fields
        processed_course = {
            "name": std_course_name,
            "challenge": course['challenge'],
            "description": replace_mentions(course['description'], pose_patterns),
            "total_duration": course['total_duration'],
            "sequence": processed_sequence
        }
        processed_courses.append(processed_course)
    
    # Save course patterns
    with open(course_pattern_file, 'w') as f:
        for orig, std in course_patterns:
            f.write(f"{re.escape(orig)}|||{std}\n")
    
    return {"course": processed_courses}

def replace_mentions(text: str, patterns: List[Tuple[re.Pattern, str]]) -> str:
    """Replace pose mentions in text fields."""
    for pattern, std_name in patterns:
        text = pattern.sub(std_name, text)
    return text

def main():
    parser = argparse.ArgumentParser(description='Process yoga course data')
    parser.add_argument('--input', default='knowledge_graph/array_course.json', help='Input JSON file')
    parser.add_argument('--output', default='array_courses_in_snakename.json', help='Output JSON file')
    parser.add_argument('--pose_patterns', default='pattern_pose.txt', help='Pose patterns file')
    parser.add_argument('--course_patterns', default='pattern_course.txt', help='Output course patterns file')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    # Load pose patterns
    pose_patterns = load_patterns(args.pose_patterns)
    
    # Process courses
    processed_data = process_courses(
        args.input,
        pose_patterns,
        args.course_patterns,
        args.debug
    )
    
    # Save processed data
    with open(args.output, 'w') as f:
        json.dump(processed_data, f, indent=2)

if __name__ == '__main__':
    main()