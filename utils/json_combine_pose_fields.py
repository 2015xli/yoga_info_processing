import json
import re

def clean_pose_data(input_file, output_file):
    # Load the converted JSON data
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Define expected fields (original + cleaned)
    known_fields = {
        "name", "challenge", "introduction", "steps", "attribute", "category",
        "build_up", "move_forward", "balance_out", "unwind", "modification",
        "cautions", "take_care", "modifications_and_cautions", "effects",
        "position", "what_to_do_while_youre_there", "how_to_come_out"
    }
    
    valid_poses = {pose['name'] for pose in data['pose']}
    invalid_entries = []
    unexpected_fields = []
    field_report = set()

    # Process each pose
    cleaned_poses = []
    for pose in data['pose']:
        # Field validation check
        for key in pose.keys():
            if key not in known_fields:
                unexpected_fields.append({
                    'pose_name': pose['name'],
                    'unexpected_field': key
                })
                field_report.add(key)

        # Rest of the processing...
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

        # Array field processing...
        for field in ['build_up', 'move_forward', 'balance_out', 'unwind']:
            if field in pose:
                raw_value = pose[field]
                items = []
                
                if isinstance(raw_value, str):
                    items = re.split(r'[,;]', raw_value)
                    items = [item.strip() for item in items if item.strip()]
                elif isinstance(raw_value, list):
                    items = raw_value
                
                validated = []
                for item in items:
                    if item in valid_poses:
                        validated.append(item)
                    else:
                        invalid_entries.append({
                            'pose_name': pose['name'],
                            'field': field,
                            'invalid_item': item
                        })
                
                cleaned[field] = validated

        # Field merging...
        caution_parts = []
        for cf in ['cautions', 'take_care', 'modifications_and_cautions']:
            if cf in pose and pose[cf]:
                caution_parts.append(pose[cf].strip())
        cleaned['caution'] = '\n'.join(caution_parts)

        practice_parts = []
        for pnf in ['position', 'what_to_do_while_youre_there']:
            if pnf in pose and pose[pnf]:
                practice_parts.append(pose[pnf].strip())
        cleaned['practice_note'] = '\n'.join(practice_parts)

        cleaned_poses.append(cleaned)

    # Create final structure
    final_data = {'pose': cleaned_poses}
    
    # Write cleaned data
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)

    # Validation reports
    print("\nValidation Report:")
    print("==================")
    
    # Unexpected fields report
    if unexpected_fields:
        print("\nUnexpected Fields Found:")
        print("-----------------------")
        seen = set()
        for entry in unexpected_fields:
            key = (entry['pose_name'], entry['unexpected_field'])
            if key not in seen:
                seen.add(key)
                print(f"• In pose '{entry['pose_name']}':")
                print(f"  Found unexpected field: '{entry['unexpected_field']}'")
                print(f"  Expected fields: {', '.join(sorted(known_fields))}")
        print(f"\nTotal unexpected field types: {len(field_report)}")
        print(f"Total unexpected field occurrences: {len(unexpected_fields)}")
    else:
        print("\nAll fields are valid and expected!")

    # Invalid pose references report
    if invalid_entries:
        print("\nInvalid Pose References:")
        print("-----------------------")
        seen = set()
        for error in invalid_entries:
            key = (error['pose_name'], error['field'], error['invalid_item'])
            if key not in seen:
                seen.add(key)
                print(f"• In pose '{error['pose_name']}', field '{error['field']}':")
                print(f"  Invalid reference: '{error['invalid_item']}'")
        print(f"\nTotal invalid references: {len(seen)}")
    else:
        print("\nAll pose references are valid!")

    print(f"\nCleaning complete! Output saved to {output_file}")

if __name__ == '__main__':
    input_filename = 'knowledge_graph/original_pose_in_array.json'
    output_filename = 'cleaned_pose.json'
    clean_pose_data(input_filename, output_filename)