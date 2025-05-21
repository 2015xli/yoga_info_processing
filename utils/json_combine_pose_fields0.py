import json
import re

def clean_pose_data(input_file, output_file):
    # Load the converted JSON data
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Get all valid pose names for validation
    valid_poses = {pose['name'] for pose in data['pose']}
    invalid_entries = []
    
    # Define fields to merge into caution
    caution_fields = ['cautions', 'take_care', 'modifications_and_cautions']
    
    # Define fields to merge into practice_note
    practice_note_fields = ['position', 'what_to_do_while_youre_there']
    
    # Process each pose
    cleaned_poses = []
    for pose in data['pose']:
        # Create new cleaned pose structure
        cleaned = {
            'name': pose.get('name', ''),
            'challenge': pose.get('challenge', ''),
            'introduction': pose.get('introduction', ''),
            'steps': pose.get('steps', []),
            'attribute': pose.get('attribute', ''),
            'category': pose.get('category', ''),
            'build_up': [],
            'move_forward': [],
            'balance_out': [],
            'unwind': [],
            'modification': pose.get('modification', ''),
            'caution': '',
            'effects': pose.get('effects', ''),
            'practice_note': '',
            'how_to_come_out': pose.get('how_to_come_out', '')
        }

        # Process array fields with validation and error tracking
        for field in ['build_up', 'move_forward', 'balance_out', 'unwind']:
            if field in pose:
                raw_value = pose[field]
                items = []
                
                # Handle different input formats
                if isinstance(raw_value, str):
                    # Split by comma or semicolon
                    items = re.split(r'[,;]', raw_value)
                    items = [item.strip() for item in items if item.strip()]
                elif isinstance(raw_value, list):
                    items = raw_value
                
                # Validate each item
                validated = []
                for item in items:
                    if item in valid_poses:
                        validated.append(item)
                    else:
                        # Record invalid entries
                        invalid_entries.append({
                            'pose_name': pose['name'],
                            'field': field,
                            'invalid_item': item
                        })
                
                cleaned[field] = validated

        # Merge caution fields
        caution_parts = []
        for cf in caution_fields:
            if cf in pose and pose[cf]:
                caution_parts.append(pose[cf].strip())
        cleaned['caution'] = '\n'.join(caution_parts)

        # Merge practice note fields
        practice_parts = []
        for pnf in practice_note_fields:
            if pnf in pose and pose[pnf]:
                practice_parts.append(pose[pnf].strip())
        cleaned['practice_note'] = '\n'.join(practice_parts)

        cleaned_poses.append(cleaned)

    # Create final structure
    final_data = {'pose': cleaned_poses}
    
    # Write cleaned data
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)

    # Print validation report
    if invalid_entries:
        print("\nInvalid pose references found:")
        print("-----------------------------")
        for error in invalid_entries:
            print(f"• In pose '{error['pose_name']}', field '{error['field']}':")
            print(f"  Invalid reference: '{error['invalid_item']}'")
            print("  Possible causes: Typo, deprecated pose name, or missing pose definition")
            print()
    else:
        print("\nAll pose references are valid!")

    print(f"\nCleaning complete! Output saved to {output_file}")

if __name__ == '__main__':
    input_filename = 'converted_pose_in_array.json'
    output_filename = 'cleaned_pose_in_combined_fields.json'
    clean_pose_data(input_filename, output_filename)