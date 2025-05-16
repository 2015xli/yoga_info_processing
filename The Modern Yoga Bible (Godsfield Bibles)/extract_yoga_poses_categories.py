import re
import json
import argparse
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract
from PyPDF2 import PdfReader

def process_spaced_text(text):
    """Process text with spaces between letters into normal words while preserving word boundaries."""
    # Split into potential words using two or more spaces
    words = re.split(r'\s{2,}', text.strip())
    
    for i, word in enumerate(words):
        if bool(re.fullmatch(r'(.\s)*.', word.strip())):
            words[i] = word.replace(' ', '')
        else:
            break

    return ' '.join(words)
    
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

def parse_categories(lines):
    categories = {}

    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            continue
        
        processed_line = process_spaced_text(stripped_line)
        
        # Check for chapter heading
        chapter_match = re.match(r'^(\d+)\.\s+(.*)$', processed_line)
        if chapter_match:
            current_chapter = chapter_match.group(1).strip()
            if int(current_chapter) in list(range(1, 20)):
                category = categories.get(current_chapter, None)
                if not category:
                    categories[current_chapter] = chapter_match.group(2).strip()
        
                if int(current_chapter) == 20:
                    break

    return categories

def parse_yoga_poses(text_content):
    """Parse yoga poses and category introductions from text content"""
    lines = text_content.split('\n')
    poses = {}
    categories = parse_categories(lines[0:500])
    category_introductions = {}  # Maps category numbers to their intro data

    current_attribute = None
    current_category_num = None
    current_category = None
    current_intro_lines = []
    pose_sections = []

    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            continue
        
        processed_line = process_spaced_text(stripped_line)
        
        # Check for part heading
        if processed_line.lower().startswith('part '):
            part_match = re.match(r'^part\s+(\d+)$', processed_line.lower())
            if part_match:
                part_num = part_match.group(1)
                if part_num == '2':
                    current_attribute = 'Yang'
                elif part_num == '3':
                    current_attribute = 'Yin'
                elif part_num == '4':
                    current_attribute = 'Mind'
                else:
                    current_attribute = None  # Part 1 or others not relevant
        
        # Check for chapter heading
        chapter_match = re.match(r'^(\d+)\.$', processed_line)
        if chapter_match:           
            current_category_num = chapter_match.group(1).strip()
            current_category = categories.get(current_category_num, None)
            # Skip adding the title line to intro
            continue
        
        # Check if current line is a pose start
        if stripped_line.startswith('☆'):
            # If collecting intro, save it
            if current_category_num is not None and current_intro_lines:
                intro_text = ' '.join(current_intro_lines).strip()
                category_introductions[current_category_num] = {
                    'title': categories.get(current_category_num, ''),
                    'introduction': intro_text
                }
                current_category_num = None
                current_intro_lines = []
            
            # Proceed to process pose
            pose_sections.append({
                'lines': [stripped_line],
                'attribute': current_attribute,
                'category': current_category
            })
            continue
        
        # If currently in a category intro, collect lines
        if current_category_num is not None:
            current_intro_lines.append(processed_line)
            continue
        
        # Existing pose processing when not in intro
        if pose_sections:
            pose_sections[-1]['lines'].append(stripped_line)
    
    note_headings = {
        'build up', 'move forward', 'balance out', 'unwind', 'take care',
        'effects', 'position', 'modification', 'what to do while you’re there',
        'how to come out', 'modifications and cautions', 'modification', 'cautions'
    }
    
    for section in pose_sections:
        if not section['lines']:
            continue
        
        # Extract title and stars from the first line
        title_line = section['lines'][0]
        stars = title_line.count('☆')
        title = re.sub(r'^(☆\s*)+', '', title_line)
        title = process_spaced_text(title).lower()
        
        if not title:
            continue
        
        content_lines = [process_spaced_text(line) for line in section['lines'][1:]]
        
        introduction = []
        steps = []
        notes = {}
        
        step_pattern = re.compile(r'^(\d+)\s*\.\s*(.*)')
        current_part = 'introduction'
        current_note = None
        
        for line in content_lines:
            if not line.strip():
                continue
            
            processed_line = line  # Already processed
            
            # Check for step
            step_match = step_pattern.match(processed_line)
            if step_match and current_part in ['introduction', 'steps']:
                current_part = 'steps'
                step_num = step_match.group(1)
                step_text = step_match.group(2).strip()
                steps.append(step_text)
                continue
            
            # Check for note heading
            normalized_line = processed_line.lower()
            if normalized_line in note_headings:
                current_part = 'notes'
                current_note = normalized_line
                notes[current_note] = []
                continue
            
            if current_part == 'introduction':
                introduction.append(processed_line)
            elif current_part == 'steps':
                if steps:
                    steps[-1] += ' ' + processed_line
                else:
                    steps.append(processed_line)
            elif current_part == 'notes' and current_note:
                notes[current_note].append(processed_line)
        
        # Clean introduction and steps
        introduction_text = ' '.join(introduction)
        steps = [step.strip() for step in steps]
        
        # Process notes
        for key in notes:
            notes[key] = ' '.join(notes[key]).strip()
        
        # Create pose data structure
        pose_data = {
            "challenge": str(stars),
            "introduction": introduction_text,
            "steps": steps,
            "attribute": section.get('attribute'),
            "category": section.get('category')
        }
        
        # Add valid notes
        for key in note_headings:
            if key in notes and notes[key]:
                pose_data[key] = notes[key]
        
        poses[title] = pose_data
    
    return {
        "pose": poses,
        "category": {elem['title']: {"introduction": elem['introduction']} for num, elem in category_introductions.items()}
    }

def main():
    parser = argparse.ArgumentParser(description='Process yoga book PDF into JSON structure')
    parser.add_argument('book_path', type=Path, help='Path to the PDF book file')
    parser.add_argument('--scanned', action='store_true', 
                      help='Flag for scanned PDFs requiring OCR processing')
    parser.add_argument('--use_temp', action='store_true',
                      help='Use the existing temp text file instead of processing the PDF')
    parser.add_argument('-o', '--output', type=Path, default=None,
                      help='Output JSON file path (default: <input_base>.json)')
    
    args = parser.parse_args()

    if args.output is None:
        args.output = args.book_path.with_suffix('.json')
        
    temp_text = args.book_path.with_suffix('.temp.txt')

    if args.use_temp:
        with open(temp_text, 'r', encoding='utf-8') as f:
            text_content = f.read()
    else:
        text_content = extract_text_from_pdf(args.book_path, args.scanned, temp_text)
    
    yoga_data = parse_yoga_poses(text_content)
    
    with open(args.output, 'w', encoding="utf-8", newline='\u000A') as f:
        json.dump(yoga_data, f, indent=2, ensure_ascii=False)  # Preserve Unicode chars
    
    print(f"Successfully generated {args.output}")

if __name__ == "__main__":
    main()