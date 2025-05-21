import json
import re
import argparse
from typing import Dict, List, Tuple

def standardize_name(name: str) -> str:
    """Convert pose names to lowercase snake_case, treating hyphens as separators."""
    # Remove apostrophes and unwanted characters
    name = re.sub(r"['’]", "", name)
    # Replace hyphens, en-dashes, and spaces with underscores
    name = re.sub(r'[\s–\-]+', '_', name)
    # Handle CamelCase and clean up
    name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
    name = re.sub(r'_+', '_', name).strip('_')
    return name

def create_pose_pattern(original_name: str) -> Tuple[re.Pattern, str]:
    """Create regex pattern with optional pluralization on the last word."""
    standardized = standardize_name(original_name)
    parts = re.split(r'[\s–\-_]+', original_name.strip())
    
    if not parts:
        return re.compile(''), standardized
    
    escaped_parts = []
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            # Match singular or plural (s/es endings)
            escaped = f'{re.escape(part)}(?:s|es)?'
        else:
            escaped = re.escape(part)
        escaped_parts.append(escaped)
    
    pattern = r'[\s–\-_]+'.join(escaped_parts)
    return re.compile(rf'(?i)\b{pattern}\b'), standardized

def create_pose_pattern_exact(original_name: str) -> Tuple[re.Pattern, str]:
    """Create regex pattern for matching pose name variations."""
    standardized = standardize_name(original_name)
    # Split into parts using all possible separators
    parts = re.split(r'[\s–\-_]+', original_name.strip())
    escaped_parts = [re.escape(part) for part in parts if part]
    # Match any combination of separators
    pattern = r'[\s_–\-]+'.join(escaped_parts)
    return re.compile(rf'(?i)\b{pattern}\b'), standardized  # Case-insensitive

def generate_pose_patterns(poses: Dict, output_file: str) -> None:
    """Generate and save pose patterns to file."""
    sorted_poses = sorted(poses.keys(), key=lambda x: len(x), reverse=True)
    patterns = [create_pose_pattern(pose) for pose in sorted_poses]
    
    with open(output_file, 'w') as f:
        for pattern, standardized in patterns:
            f.write(f"{pattern.pattern}|||{standardized}\n")

def load_pose_patterns(input_file: str) -> List[Tuple[re.Pattern, str]]:
    """Load pose patterns from file."""
    patterns = []
    with open(input_file, 'r') as f:
        for line in f:
            pattern_str, standardized = line.strip().split('|||')
            patterns.append((re.compile(pattern_str), standardized))
    return patterns

def process_data(poses: Dict, pose_patterns: List[Tuple[re.Pattern, str]], 
                debug: bool = False) -> Tuple[Dict, List[Tuple[str, str]]]:
    """Process pose data with standardization and validation."""
    cleaned_poses = {}
    all_standardized = set()
    debug_log = []
    
    # First pass: Standardize all pose names
    for orig_name, data in poses.items():
        cleaned_poses[standardize_name(orig_name)] = data
    all_standardized.update(cleaned_poses.keys())

    # Second pass: Process fields
    validation_errors = []
    for standardized_name, pose_data in cleaned_poses.items():
        processed = {}
        
        for key, value in pose_data.items():
            new_key = standardize_name(key)
            
            # Process text fields
            if isinstance(value, str):
                new_value, replacements = replace_mentions(value, pose_patterns, debug)
                debug_log.extend(replacements)
                processed[new_key] = new_value
            elif isinstance(value, list):
                new_list = []
                for item in value:
                    if isinstance(item, str):
                        new_item, replacements = replace_mentions(item, pose_patterns, debug)
                        debug_log.extend(replacements)
                        new_list.append(new_item)
                    else:
                        new_list.append(item)
                processed[new_key] = new_list
            else:
                processed[new_key] = value
            
            # Validate reference fields
            if new_key in ['balance_out', 'move_forward', 'unwind', 'build_up']:
                refs = processed[new_key]
                if isinstance(refs, str):
                    #refs = [r.strip() for r in refs.split(r'[,;]')]
                    refs = [r.strip() for r in re.split(r'[,;]', refs)]
                
                valid_refs = []
                for ref in refs:
                    # Assume ref is already standardized from substitution
                    if ref in all_standardized:
                        valid_refs.append(ref)
                    else:
                        validation_errors.append( f"Pose '{standardized_name}': Field '{new_key}' contains invalid reference '{ref}'" )
        
                processed[new_key] = valid_refs

        cleaned_poses[standardized_name] = processed

    return {'pose': cleaned_poses}, validation_errors, debug_log

def replace_mentions(text: str, patterns: List[Tuple[re.Pattern, str]], 
                    debug: bool) -> Tuple[str, List[Tuple[str, str]]]:
    """Replace pose mentions in text and track replacements."""
    replacements = []
    
    def replacer(match):
        original = match.group()
        standardized = next((std for pat, std in patterns if pat.match(original)), None)
        if standardized:
            if debug:
                replacements.append((original, standardized))
            return standardized
        return original
    
    for pattern, standardized in patterns:
        text = pattern.sub(replacer, text)
    
    return text, replacements

def main():
    parser = argparse.ArgumentParser(description='Process yoga pose data')
    parser.add_argument('--generate_pose_patterns', action='store_true',
                       help='Generate pose patterns file')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging of replacements')
    parser.add_argument('-i', '--input', default='knowledge_graph/The Modern Yoga Bible (Godsfield Bibles).json',
                       help='Input JSON file')
    parser.add_argument('-o', '--output', default='cleaned_pose_keys_to_snake.json',
                       help='Output JSON file')
    args = parser.parse_args()

    with open(args.input, 'r') as f:
        data = json.load(f)['pose']

    if args.generate_pose_patterns:
        generate_pose_patterns(data, 'pattern_pose.txt')
        print("Generated pose patterns file")
        #return

    try:
        pose_patterns = load_pose_patterns('pattern_pose.txt')
    except FileNotFoundError:
        raise SystemExit("Error: pattern_pose.txt not found. Generate it first with --generate_pose_patterns")

    processed_data, validation_errors, debug_log = process_data(data, pose_patterns, args.debug)
    
    # Save cleaned data
    with open(args.output, 'w') as f:
        json.dump(processed_data, f, indent=2, ensure_ascii=False)
    
    # Save validation report
    if validation_errors:
        with open('validation_errors.txt', 'w') as f:
            f.write('\n'.join(validation_errors))
    
    # Save debug log
    if args.debug and debug_log:
        with open('replacements.log', 'w') as f:
            for original, replaced in debug_log:
                f.write(f"Original: {original} → Replaced: {replaced}\n")

if __name__ == '__main__':
    main()
