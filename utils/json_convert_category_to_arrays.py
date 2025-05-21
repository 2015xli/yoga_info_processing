import sys
import json

# Load the original JSON data
with open(sys.argv[1], 'r', encoding="utf-8") as file:
    original_data = json.load(file)

# Prepare the new structure
new_category = []

# Iterate through each category in the original data
for category_name, category_info in original_data['category'].items():
    # Case-insensitive check for "guidelines" key
    guidelines = []
    for key in category_info.keys():
        if key.lower() == "guidelines":
            guidelines = category_info[key]
            break  # Use the first matching key

    # Build the transformed entry
    entry = {
        "name": category_name,
        "introduction": category_info.get("introduction", ""),
        "guidelines": guidelines
    }
    new_category.append(entry)

# Create the final transformed data
transformed_data = {
    "category": new_category
}

# Save the transformed data to a new JSON file
with open('transformed_category.json', 'w', encoding="utf-8", newline='\u000A') as file:
    json.dump(transformed_data, file, indent=2, ensure_ascii=False)

print("Conversion completed successfully!")