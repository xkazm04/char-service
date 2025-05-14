from google.genai import types
from openai import OpenAI
from PIL import Image
import base64
import json
import io
from google import genai
from PIL import Image
from dotenv import load_dotenv
import os
import logging
load_dotenv()

logger = logging.getLogger(__name__)

open_api_key = os.getenv("OPENAI_API_KEY")
google_api_key = os.getenv("GOOGLE_API_KEY")
groq_api_key = os.getenv("GROQ_API_KEY")

client = OpenAI()

# TBD test groq inference for open sourced models - meta-llama/llama-4-maverick-17b-128e-instruct


def analyze_image(image_path: str) -> dict:
    # Load image and encode to base64
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()

    base64_image = base64.b64encode(image_data).decode("utf-8")

    # Prepare image for GPT-4 vision
    image_dict = {
        "type": "image_url",
        "image_url": {
            "url": f"data:image/jpeg;base64,{base64_image}"
        }
    }

    # System + user prompt to extract metadata
    messages = [
        {"role": "system", "content": "You are an assistant that extracts character asset metadata from images for game development."},
        {"role": "user", "content": [
            image_dict,
            {
                "type": "text",
                "text": PROMPT_TEMPLATE
            }
        ]}
    ]

    # Call OpenAI API with GPT-4 Vision
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages,
        max_tokens=500
    )
    
    logger.info("OpenAI response: %s", response)

    # Parse and return JSON from LLM
    try:
        output = response.choices[0].message.content
        return json.loads(output)
    except Exception as e:
        logger.error("Error parsing LLM output: %s", e)
        print("Error parsing LLM output:", e)
        print("Raw output:", response.choices[0].message.content)
        return {}


def analyze_with_gemini(image_path: str) -> dict:
    client = genai.Client(api_key=google_api_key)
    files = [
        # Please ensure that the file is available in local system working direrctory or change the file path.
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
        return json.loads(response.text)
    except Exception as e:
        logger.error("Error parsing Gemini response: %s", e)
        print("Error:", e)
        print("Response text:", response.text)
        return {}


PROMPT_TEMPLATE = (
    "You are an assistant that extracts character asset metadata from images for game development.\n"
    "Analyze the visual assets of this character and extract the following:\n"
    "- 'description': A human-readable summary of the asset's visual features.\n"
    "- 'gen': A version of the description optimized for image generation tools like DALL-E or Midjourney (focus on concise, vivid, style-rich keywords).\n"
    "- 'category': Classify the asset into one of these categories: "
    "Hairstyle, Body, Head, Accessories, Equipment, Face, Background, Clothing. "
    "Return only one category per asset, and use the exact spelling from the list.\n"
    "- 'name': A short name summarizing the most iconic asset style.\n"
    "Respond in this JSON format:\n"
    "{ \"description\": string, \"gen\": string, \"category\": string, \"name\": string }"
)
