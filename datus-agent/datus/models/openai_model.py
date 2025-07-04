import json
import os
from typing import Any, Dict

from openai import OpenAI

from datus.configuration.agent_config import ModelConfig
from datus.models.base import LLMBaseModel


class OpenAIModel(LLMBaseModel):
    """
    Implementation of the BaseModel for OpenAI's API.
    """

    def __init__(self, model_config: ModelConfig, **kwargs):
        """
        Initialize the OpenAI model.

        Args:
            model_name: The specific OpenAI model to use (e.g., 'gpt-4o', 'gpt-3.5-turbo')
            api_key: OpenAI API key. If not provided, will look for OPENAI_API_KEY env variable
            **kwargs: Additional parameters for the OpenAI API
        """
        super().__init__(model_config, **kwargs)

        # Use provided API key or get from environment
        self.api_key = model_config.api_key or os.environ.get("OPENAI_API_KEY")
        self.model_name = model_config.model
        if not self.api_key:
            raise ValueError("OpenAI API key must be provided or set as OPENAI_API_KEY environment variable")

        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key)

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate a response from the OpenAI model.

        Args:
            prompt: The input prompt to send to the model
            **kwargs: Additional generation parameters

        Returns:
            The generated text response
        """
        # Merge default parameters with any provided kwargs
        params = {
            "model": self.model_name,
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 1.0,
            **kwargs,
        }

        # Create messages format expected by OpenAI
        messages = [{"role": "user", "content": prompt}]

        # Call the OpenAI API
        response = self.client.chat.completions.create(messages=messages, **params)

        # Extract and return the generated text
        return response.choices[0].message.content

    def generate_with_json_output(self, prompt: Any, json_schema: Dict, **kwargs) -> Dict:
        """
        Generate a response and ensure it conforms to the provided JSON schema.

        Args:
            prompt: The input prompt to send to the model
            json_schema: The JSON schema that the output should conform to
            **kwargs: Additional generation parameters

        Returns:
            A dictionary representing the JSON response
        """
        # Add instructions to format the response as JSON according to the schema
        json_prompt = (
            f"{prompt}\n\nRespond with a JSON object that conforms to the following schema:\n"
            f"{json.dumps(json_schema, indent=2)}"
        )

        # Set response format to JSON
        params = {**kwargs, "response_format": {"type": "json_object"}}

        # Generate the response
        response_text = self.generate(json_prompt, **params)

        # Parse the JSON response
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # If parsing fails, try to extract JSON from the response
            import re

            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass

            # Return a basic error response if all parsing attempts fail
            return {
                "error": "Failed to parse JSON response",
                "raw_response": response_text,
            }

    def set_context(self, workflow=None, current_node=None):
        pass
