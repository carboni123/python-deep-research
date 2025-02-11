# api/google_api.py
import json
from api import extract_json
from api.api import API
from api import register_api
from google import genai
from google.genai import types
from google.genai.types import Content, Part


MODEL = "models/gemini-2.0-flash-thinking-exp"


@register_api("google")
class GoogleAPI(API):
    """
    Concrete class for interactions with the Google API.
    """

    MODEL_NAME = MODEL
    # MODEL_NAME = "models/gemini-2.0-pro-exp"

    def __init__(self, api_key=None):
        """
        Initializes the GoogleAPI object.

        :param api_key: Can be either an actual API key string or a path to a file containing the API key.
        """
        super().__init__(api_key, api_env="GOOGLEAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No valid GoogleAI API key found. Provide it as a string, file path, "
                "or set GOOGLEAI_API_KEY in the environment."
            )
        self.client = genai.Client(api_key=self.api_key)

    def set_model(self, model_name):
        self.MODEL_NAME = model_name

    async def generate_text(self, prompt, timeout=10, **kwargs):
        """
        Generates text using the Google API.

        Args:
            prompt (str): The input prompt for text generation.
            timeout (int): Timeout in seconds for the API call.
            **kwargs: Additional keyword arguments for the API call.

        Returns:
            str: The generated text.

        Raises:
             NotImplementedError: This method is not yet implemented for Google API.
        """
        contents = []
        if isinstance(prompt, list):
            for message in prompt:
                role = message.get("role")
                content = message.get("content")
                # Convert "assistant" to "model" because Google GenAI expects 'model'
                if role == "system" or role == "assistant":
                    role = "model"
                contents.append(Content(parts=[Part(text=content)], role=role))
        else:
            contents.append(prompt)

        try:
            raw_response = self.client.models.generate_content(
                model=self.MODEL_NAME,
                contents=contents,
                # config={
                #     "response_mime_type": "application/json",
                # },
            )
            response = extract_json(raw_response.text)
            parsed = json.loads(response)
            if "reasoning" in parsed:
                return response.get("question")
            else:
                return response
        except Exception as e:
            print(f"Error generating text with Google API: {e}")
            raise

    def get_model_info(self, model: str):
        model_info = genai.get_model(model)
        print(model_info)


if __name__ == "__main__":
    api = GoogleAPI()
    api.list_models()
