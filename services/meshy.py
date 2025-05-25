import requests
import base64
import os
import logging

logger = logging.getLogger(__name__)


def generate_3d_asset_from_image(image_input, api_key, use_base64=False):
    """
    Generate a 3D asset from an image using the Meshy Image to 3D API.

    Parameters:
    - image_input (str): URL to the image or path to the local image file.
    - api_key (str): Your Meshy API key.
    - use_base64 (bool): If True, the image_input is treated as a local file path and encoded in base64.
                         If False, the image_input is treated as a URL.

    Returns:
    - dict: The JSON response from the Meshy API.
    """
    url = "https://api.meshy.ai/openapi/v1/image-to-3d"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    if use_base64:
        if not os.path.isfile(image_input):
            raise FileNotFoundError(f"The file {image_input} does not exist.")

        ext = os.path.splitext(image_input)[1].lower()
        mime_type = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png'
        }.get(ext)

        if mime_type is None:
            raise ValueError(
                "Unsupported image format. Supported formats: .jpg, .jpeg, .png")

        with open(image_input, "rb") as image_file:
            encoded_string = base64.b64encode(
                image_file.read()).decode('utf-8')
            image_data_uri = f"data:{mime_type};base64,{encoded_string}"
            payload = {
                "image_url": image_data_uri,
                "ai_model": "meshy-5"
            }
    else:
        payload = {
            "image_url": image_input,
            "ai_model": "meshy-5"
        }
    logger.info(f"Sending request to Meshy API with payload: {payload}")

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 400 or response.status_code == 422 or response.status_code == 500:
        raise Exception(
            f"API request failed with status code {response.status_code}: {response.text}")

    return response.json()


def get_image_to_3d_task_status(task_id, api_key):
    """
    Retrieve the status of an Image to 3D task from the Meshy API.

    Parameters:
    - task_id (str): The unique identifier of the task.
    - api_key (str): Your Meshy API key.

    Returns:
    - dict: The JSON response containing task details.
    Raises:
    - Exception: If the API request fails or returns an error.
    """
    url = f"https://api.meshy.ai/openapi/v1/image-to-3d/{task_id}"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(
            f"API request failed with status code {response.status_code}: {response.text}")

    return response.json()
