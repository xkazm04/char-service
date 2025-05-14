from openai import OpenAI
from PIL import Image
import base64
import json
import io
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv
import os
load_dotenv()

open_api_key = os.getenv("OPENAI_API_KEY")
google_api_key = os.getenv("GOOGLE_API_KEY")
groq_api_key = os.getenv("GROQ_API_KEY")

client = OpenAI()

# TBD test groq inference for open sourced models

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
        model="gpt-4-vision-preview",
        messages=messages,
        max_tokens=500
    )

    # Parse and return JSON from LLM
    try:
        output = response.choices[0].message.content
        return json.loads(output)
    except Exception as e:
        print("Error parsing LLM output:", e)
        print("Raw output:", response.choices[0].message.content)
        return {}



def analyze_with_gemini(image_path: str) -> dict:
    genai.configure(api_key="YOUR_API_KEY")
    model = genai.GenerativeModel("gemini-pro-vision")
    image = Image.open(image_path)
    response = model.generate_content([PROMPT_TEMPLATE, image])
    try:
        return json.loads(response.text)
    except Exception as e:
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