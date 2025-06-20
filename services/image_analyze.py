from google.genai import types
from openai import OpenAI
import base64
import json
from google import genai
import logging
from utils.json_extractor import extract_json_from_text
from config import config

logger = logging.getLogger(__name__)

openai_api_key = config.openai_api_key
google_api_key = config.google_api_key
groq_api_key = config.groq_api_key


def analyze_image(image_path: str, model: str, api_key=None) -> list:
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()

    base64_image = base64.b64encode(image_data).decode("utf-8")

    image_dict = {
        "type": "image_url",
        "image_url": {
            "url": f"data:image/jpeg;base64,{base64_image}"
        }
    }

    messages = [
        {"role": "system", "content": "You are an expert system that extracts character asset metadata from images for game development. Return ONLY valid JSON."},
        {"role": "user", "content": [
            image_dict,
            {
                "type": "text",
                "text": PROMPT_TEMPLATE
            }
        ]}
    ]

    try:
        if model == "openai":
            client = OpenAI(openai_api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=3800,  # Increased token limit
                response_format={"type": "json_object"}  # Force JSON response when possible
            )
        elif model == "groq":
            client = OpenAI(
                api_key=api_key or groq_api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=messages,
                max_tokens=1800,  # Increased token limit
            )
        else:
            logger.error(f"Unknown model: {model}")
            return []

        logger.info(f"{model.upper()} response received")
    
        output = response.choices[0].message.content
        
        if output and ('finish_reason' in response and response.finish_reason == 'length'):
            logger.warning(f"{model} response was truncated, attempting to fix JSON")
            if output.count('[') > output.count(']'):
                output += ']' * (output.count('[') - output.count(']'))
            if output.count('{') > output.count('}'):
                output += '}' * (output.count('{') - output.count('}'))
                
        json_content = extract_json_from_text(output, aggressive=True)
        
        if json_content:
            try:
                result = json.loads(json_content)
                if isinstance(result, list):
                    return result
                elif isinstance(result, dict):
                    if any(key in result for key in ["description", "type", "name"]):
                        return [result]
                    elif "results" in result and isinstance(result["results"], list):
                        return result["results"]
                    else:
                        for value in result.values():
                            if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                                if any(key in value[0] for key in ["description", "type", "name"]):
                                    return value
                
                logger.error(f"Couldn't extract valid asset list from {model} output")
                return []
                
            except Exception as json_error:
                logger.error(f"Error parsing JSON from {model}: {json_error}")
        logger.error(f"Couldn't extract valid JSON from {model} output")
        return []
        
    except Exception as e:
        logger.error(f"Error processing {model} response: {str(e)}")
        return []


def analyze_with_gemini(image_path: str, api_key=None) -> list:
    client = genai.Client(api_key=google_api_key)
    files = [
        client.files.upload(file=image_path),
    ]
    model = "gemini-1.5-flash"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_uri(
                    file_uri=files[0].uri,
                    mime_type=files[0].mime_type,
                ),
                types.Part.from_text(text="""Analyze following file"""),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        system_instruction=[
            types.Part.from_text(text=PROMPT_TEMPLATE),
        ],
    )
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config,
    )
    logger.info("Gemini response: %s", response)
    try:
        raw_text = response.candidates[0].content.parts[0].text
        json_content = extract_json_from_text(raw_text)
        
        if json_content:
            result = json.loads(json_content)
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                return [result]
        
        logger.error("Couldn't extract valid JSON from Gemini output")
        return []
    except Exception as e:
        logger.error("Error parsing Gemini response: %s", e)
        print("Error:", e)
        print("Response text:", response.text)
        
        try:
            if hasattr(response, 'text'):
                json_content = extract_json_from_text(response.text, aggressive=True)
                if json_content:
                    result = json.loads(json_content)
                    if isinstance(result, list):
                        return result
                    elif isinstance(result, dict):
                        return [result]
        except:
            pass
            
        return []


PROMPT_TEMPLATE = (
    "You are an expert system that extracts character asset metadata from images for game development.\n\n"
    "TASK: Analyze the visual elements in this image and identify distinct character assets.\n\n"
    "OUTPUT REQUIREMENTS:\n"
    "- Respond ONLY with a valid JSON array.\n"
    "- Do NOT include any explanations, notes, or text outside the JSON structure.\n"
    "- Each asset should be a separate object in the array.\n"
    "- If you find no assets, return exactly '[]' without any additional text.\n\n"
    "SCHEMA: Each asset object must include EXACTLY these fields:\n"
    "- 'description': A human-readable summary of the asset's visual features (50-100 characters).\n"
    "- 'gen': A short, complete prompt for image generation (MAX 50 characters). Use format: 'item, style, material' with key visual descriptors only.\n"
    "- 'type': One of the following EXACT top-level categories (choose the best match):\n"
    "  Body, Equipment, Clothing, Background\n"
    "- 'subcategory': MUST be one of the following based on the 'type':\n"
    "  For Body: Hairstyle, Facial Hair, Tattoo, Scar, Body Modifications\n"
    "  For Equipment: Weapons, Shields & Armor, Tools & Gadgets, Wearable Tech / Enhancements, Carried Items\n"
    "  For Clothing: Upper Wear, Lower Wear, Footwear, Headwear, Accessories\n"
    "  For Background: Setting, Time of Day, Weather Effects, Structures & Objects, Visual Effects\n"
    "- 'name': A brief name (2-5 words) that captures the essence of the asset.\n\n"
    "GEN FIELD GUIDELINES:\n"
    "- Maximum 50 characters total\n"
    "- Format: 'item, style, material'\n"
    "- Use essential descriptors only\n"
    "- Include key color, basic style, main material\n"
    "- Be concise but complete\n\n"
    "EXAMPLE RESPONSE FORMAT:\n"
    "[\n"
    "  {\n"
    "    \"description\": \"Elegant dark red silk necktie with subtle pattern\",\n"
    "    \"gen\": \"Red silk tie, elegant, smooth texture.\",\n"
    "    \"type\": \"Clothing\",\n"
    "    \"subcategory\": \"Accessories\",\n"
    "    \"name\": \"Crimson Silk Tie\",\n"
    "  },\n"
    "  {\n"
    "    \"description\": \"Tailored navy blue wool suit jacket with notched lapels\",\n"
    "    \"gen\": \"Navy blazer, tailored, wool fabric\",\n"
    "    \"type\": \"Clothing\",\n"
    "    \"subcategory\": \"Upper Wear\",\n"
    "    \"name\": \"Navy Wool Blazer\",\n"
    "  },\n"
    "  {\n"
    "    \"description\": \"Ornate silver fantasy sword with runic engravings\",\n"
    "    \"gen\": \"Silver sword, fantasy, runic engravings\",\n"
    "    \"type\": \"Equipment\",\n"
    "    \"subcategory\": \"Weapons\",\n"
    "    \"name\": \"Runic Silver Blade\",\n"
    "  }\n"
    "]\n\n"
    "COMBINATION GUIDELINES:\n"
    "- Primary assets (weight 8-10): Main clothing, weapons, or defining features\n"
    "- Secondary assets (weight 4-7): Supporting clothing, accessories, or equipment\n"
    "- Detail assets (weight 1-3): Small accessories, minor decorations, or subtle features\n\n"
    "IMPORTANT: Ensure your response contains ONLY the JSON array. Begin with '[' and end with ']' – no other text."
)
