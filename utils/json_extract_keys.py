import json
import sys

def truncate_string(s, max_len):
    if len(s) <= max_len:
        return s
    if max_len <= 3:
        return s[:max_len]
    return s[:max_len-3] + "..."

def process_data(data, max_len):
    if isinstance(data, dict):
        return {k: process_data(v, max_len) for k, v in data.items()}
    elif isinstance(data, list):
        return [process_data(item, max_len) for item in data]
    elif isinstance(data, str):
        return truncate_string(data, max_len)
    else:
        return data

def main():
    if len(sys.argv) < 3:
        print("Usage: python truncate_json.py <input_file.json> <max_length>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    try:
        max_length = int(sys.argv[2])
    except ValueError:
        print("Error: Max length must be an integer")
        sys.exit(1)
    
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: Invalid JSON format")
        sys.exit(1)
    
    processed_data = process_data(data, max_length)
    
    if len(sys.argv) < 4:
        print(json.dumps(processed_data, indent=2, ensure_ascii=False))
    else:
        with open(sys.argv[3], 'w', encoding="utf-8", newline='\u000A') as f:
            json.dump(processed_data, f, indent=2, ensure_ascii=False)  # Preserve Unicode chars
    

if __name__ == "__main__":
    main()