import json

def convert_pose_structure(input_file, output_file):
    # Read the original JSON file
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Extract the poses dictionary
    poses_dict = data.get('pose', {})
    
    # Convert to array format with "name" field
    poses_array = []
    for name, details in poses_dict.items():
        pose_entry = {'name': name}
        pose_entry.update(details)
        poses_array.append(pose_entry)
    
    # Create new structure
    new_data = {'pose': poses_array}
    
    # Write the converted data to a new JSON file
    with open(output_file, 'w') as f:
        json.dump(new_data, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    input_filename = 'knowledge_graph/original_pose.json'
    output_filename = 'converted_pose_in_array.json'
    convert_pose_structure(input_filename, output_filename)
    print(f"Conversion complete! Output saved to {output_filename}")