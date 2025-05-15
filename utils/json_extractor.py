import json
def extract_json_from_text(text, aggressive=False):
    """
    Extract JSON content from text that might have markdown formatting or explanatory text.
    
    Args:
        text: The text that contains JSON
        aggressive: If True, use more aggressive methods to find JSON
        
    Returns:
        str: Extracted JSON string or None if not found
    """
    import re
    
    # As response format from LLMs are not always stable, lets help him with robust extraction patterns.
    if not text or not isinstance(text, str):
        return None
    
    # Case 1: Perfect scenario - the entire text is already valid JSON
    try:
        json.loads(text)
        return text.strip()
    except:
        pass
    
    # Case 2: Extract content from markdown code blocks with json
    json_block_match = re.search(r'```(?:json)?\s*\n([\s\S]*?)\n\s*```', text)
    if json_block_match:
        try:
            json_content = json_block_match.group(1).strip()
            json.loads(json_content) 
            return json_content
        except:
            pass
    
    # Case 3: Extract JSON array between square brackets (with or without leading/trailing text)
    array_pattern = r'(\[\s*\{\s*"[^"]+"\s*:.*?\]\s*)'
    array_matches = re.findall(array_pattern, text, re.DOTALL)
    for match in array_matches:
        try:
            json.loads(match)  
            return match.strip()
        except:
            continue
    
    # Case 4: Find any content between square brackets that might be JSON
    if '[' in text and ']' in text:
        start = text.find('[')
        end = text.rfind(']') + 1
        if start < end:
            potential_json = text[start:end]
            try:
                json.loads(potential_json)
                return potential_json
            except:
                pass
    
    # Case 5: If aggressive, try to find any balanced JSON structure
    if aggressive:
        for pattern in [r'\[\s*\{', r'\{\s*"']:
            start_match = re.search(pattern, text)
            if start_match:
                start_pos = start_match.start()
                start_char = text[start_pos]
                
                if start_char == '{' and '[' not in text[:start_pos]:
                    target_structure = 'object'
                else:
                    target_structure = 'array'
                
                stack = []
                for i in range(start_pos, len(text)):
                    if text[i] == '[' or text[i] == '{':
                        stack.append(text[i])
                    elif text[i] == ']' and stack and stack[-1] == '[':
                        stack.pop()
                    elif text[i] == '}' and stack and stack[-1] == '{':
                        stack.pop()
                    
                    if not stack and ((target_structure == 'array' and text[i] == ']') or 
                                     (target_structure == 'object' and text[i] == '}')):
                        potential_json = text[start_pos:i+1]
                        try:
                            json.loads(potential_json)
                            return potential_json
                        except:
                            fixed = potential_json
                            fixed = re.sub(r"'([^']+)':", r'"\1":', fixed)
                            if fixed.startswith('{') and fixed.endswith('}') and 'type' in fixed:
                                fixed = f'[{fixed}]'
                            
                            try:
                                json.loads(fixed)
                                return fixed
                            except:
                                pass
        
        for pattern in [r'\[\s*\{.*?\}\s*\]', r'\{\s*".*?"\s*:.*?\}']:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    potential_json = match.group(0)
                    json.loads(potential_json)
                    return potential_json
                except:
                    pass
    
    return None