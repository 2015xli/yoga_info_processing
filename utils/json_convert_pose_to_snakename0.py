import json
import re

def standardize_name(name):
    """Convert pose names to lowercase snake_case."""
    name = re.sub(r"['’-]", "", name)  # Remove apostrophes/dashes
    name = re.sub(r'[^\w]+', '_', name)  # Replace non-word chars with underscores
    return name.strip('_').lower()

def create_pose_regex(original_name):
    """Create a regex pattern to match variations of a pose name in text."""
    parts = re.split(r'[\s–\-]+', original_name.strip())  # Split by spaces, hyphens, en-dashes
    escaped_parts = [re.escape(part) for part in parts]  # Escape regex special characters
    pattern = r'[\s–\-]+'.join(escaped_parts)  # Match any separator between parts
    return re.compile(rf'\b{pattern}\b', flags=re.IGNORECASE)

# Load data
with open('knowledge_graph/original_pose.json', 'r') as f:
    data = json.load(f)

# Create pose mapping and precompile regex patterns
poses = data['pose']
pose_mapping = {original: standardize_name(original) for original in poses.keys()}
sorted_original_poses = sorted(poses.keys(), key=lambda x: len(x), reverse=True)  # Longest first
pose_patterns = [(create_pose_regex(original), pose_mapping[original]) for original in sorted_original_poses]

def replace_mentions(text):
    """Replace all pose mentions in text with standardized names."""
    for pattern, standardized in pose_patterns:
        text = pattern.sub(standardized, text)
    return text

# Process data
cleaned_poses = {}
for original_name, pose_data in poses.items():
    standardized_name = standardize_name(original_name)
    cleaned_data = {}
    
    for key, value in pose_data.items():
        # Standardize keys
        new_key = standardize_name(key)
        
        # Standardize values (strings or lists)
        if isinstance(value, str):
            cleaned_value = replace_mentions(value)
        elif isinstance(value, list):
            cleaned_value = [replace_mentions(item) if isinstance(item, str) else item for item in value]
        else:
            cleaned_value = value
        
        cleaned_data[new_key] = cleaned_value
    
    # Convert reference fields to lists of standardized names
    for ref_field in ['balance_out', 'move_forward', 'unwind']:
        if ref_field in cleaned_data:
            refs = cleaned_data[ref_field]
            if isinstance(refs, str):
                refs = [r.strip() for r in refs.split(',')]
            cleaned_data[ref_field] = [standardize_name(r) for r in refs]
    
    cleaned_poses[standardized_name] = cleaned_data


# Save cleaned data
with open('keymapping_pose.txt', 'w') as f:
    for item in pose_patterns:
        f.write(str(item) + '\n')    
        
# Save cleaned data
with open('unique_name_conversion_pose.json', 'w') as f:
    json.dump({'pose': cleaned_poses}, f, indent=2)