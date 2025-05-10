import re
import json
import os
from pathlib import Path
import argparse
from pdf2image import convert_from_path
import pytesseract
from PyPDF2 import PdfReader

def extract_text_from_pdf(pdf_path, is_scanned=False, temp_text=None):
    """Extract text from PDF, handling both text-based and scanned PDFs"""
    text = ""
    
    if is_scanned:
        images = convert_from_path(pdf_path)       
        if temp_text is not None:
            with temp_text.open("w", encoding="utf-8", newline='\u000A') as f:
                for image in images:
                    temp = pytesseract.image_to_string(image) + "\n"
                    text += temp
                    f.write(temp)
                    f.flush()

    else:
        with open(pdf_path, 'rb') as f:
            reader = PdfReader(f)
            if temp_text is not None:
                with temp_text.open("w", encoding="utf-8", newline='\u000A') as f:
                    for page in reader.pages:
                        temp = page.extract_text() + "\n"
                        text += temp
                        f.write(temp)
                        f.flush()

    return text

def parse_yoga_poses(text_content):
    """Parse yoga poses from text content"""
    lines = text_content.split('\n')
    poses = {}
    current_pose = None
    current_section = None

    # Use the correct star symbol: ☆ (U+2606) instead of ✰ (U+2730)
    pose_pattern = re.compile(r'^([☆]+)\s+(.+)$')
    step_pattern = re.compile(r'^(\d+)\s*\.\s')
    section_mapping = {
        'buildup': 'build up',
        'moveforward': 'move forward',
        'balanceout': 'balance out',
        'unwind': 'unwind',
        'takecare': 'take care'
    }

    for line in lines:
        pose_match = pose_pattern.match(line)
        if pose_match:
            stars = len(pose_match.group(1))
            pose_line = pose_match.group(2).strip()
            # Split into words by multiple spaces and process each word
            words = re.split(r'\s{2,}', pose_line)
            pose_name_parts = [word.replace(' ', '') for word in words]
            pose_name = ' '.join(pose_name_parts).lower()
            current_pose = {
                "challenge": str(stars),
                "introduction": [],
                "steps": [],
                "build up": "",
                "move forward": "",
                "balance out": "",
                "unwind": "",
                "take care": ""
            }
            poses[pose_name] = current_pose
            current_section = 'introduction'
            continue
        
        line_stripped = line.strip().lower()
        line_clean = re.sub(r'\s+', '', line_stripped)
        if line_clean in section_mapping:
            current_section = section_mapping[line_clean]
            continue
        
        step_match = step_pattern.match(line)
        if step_match and current_pose:
            current_section = 'steps'
            step_text = line.strip()
            step_text_clean = re.sub(r'^\d+\s*\.\s*', '', step_text)
            current_pose['steps'].append(step_text_clean)
            continue
        
        if current_pose:
            line_clean = line.strip()
            if not line_clean:
                continue
                
            if current_section == 'introduction':
                current_pose['introduction'].append(line_clean)
            elif current_section == 'steps':
                if current_pose['steps']:
                    current_pose['steps'][-1] += ' ' + line_clean
            elif current_section in current_pose:
                if current_pose[current_section]:
                    current_pose[current_section] += ' ' + line_clean
                else:
                    current_pose[current_section] = line_clean

    for pose_name, pose_data in poses.items():
        pose_data['introduction'] = ' '.join(pose_data['introduction'])
        pose_data['steps'] = [re.sub(r'^\d+\.\s*', '', step) for step in pose_data['steps']]
        for section in ['build up', 'move forward', 'balance out', 'unwind', 'take care']:
            if not pose_data.get(section):
                pose_data.pop(section, None)

    return {"pose": poses}

def main():
    parser = argparse.ArgumentParser(description='Process yoga book PDF into JSON structure')
    parser.add_argument('book_path', type=Path, help='Path to the PDF book file')
    parser.add_argument('--scanned', action='store_true', 
                      help='Flag for scanned PDFs requiring OCR processing')
    parser.add_argument('-o', '--output', type=Path, default=None,
                      help='Output JSON file path (default: <input_base>.json)')
    
    args = parser.parse_args()

    if args.output is None:
        args.output = args.book_path.with_suffix('.json')
        
    temp_text = args.book_path.with_suffix('.temp.txt')

    text_content = extract_text_from_pdf(args.book_path, args.scanned, temp_text)
    yoga_data = parse_yoga_poses(text_content)
    
    with open(args.output, 'w', encoding="utf-8", newline='\u000A') as f:
        json.dump(yoga_data, f, indent=2)
    
    print(f"Successfully generated {args.output}")

if __name__ == "__main__":
    main()