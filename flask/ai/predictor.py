from google import genai
from dotenv import load_dotenv
import os
import re
import requests
import json

from . import utils


class Predictor:

    client = None
    image_path = None

    def __init__(self, image_path):
        load_dotenv()
        self.client = genai.Client(api_key=os.getenv("GEMINI_KEY"))
        self.image_path = image_path

    def get_foods(self):
        file = utils.upload_file_to_gemini(self.image_path, self.client)
        prompt = ("You are given an image of some food that may be uneaten or partially eaten. "
                  "Your task is to figure out all the different foods in the image and name them in JSON format. "
                  "The JSON should have one key called 'foods' that holds an array of food names (strings). "
                  "Show your thought process, and when you're done, wrap the JSON output in a JSON html tag. For parsing purposes, only include the JSON html tag in your response when you are returning the JSON."
                  "To figure out the foods, follow these steps:\n"
                  "1. Isolate the foods if multiple foods exist in the image."
                  "2. Use your knowledge base to categorize each food\n"
                  "Here is an example JSON response that I expect from you: \n"
                  "<json>{foods: ['apple', 'orange', 'chicken']}</json>")
        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, file])
        foods = self.parse_food_json(response.text)
        return foods

    def get_volume(self, foods):
        file = utils.upload_file_to_gemini(self.image_path, self.client)
        prompt2 = ("You are given an image of some food that may be uneaten or partially eaten. "
                   "Your task is to figure out the volume of the foods (in Liters) in the image. "
                   "The foods in the images are: " + foods + "\n\n"
                   "Rules to follow in your response:\n"
                   "1. Show your thought process\n"
                   "2. After showing your thought process, format your response in JSON. Wrap this JSON in a ‘json’ html tag so that "
                   "I can parse it easily. Your JSON response should have a key for each food and "
                   "the value of each key should be the volume of that food (as a float).\n\n"
                   "Format your response like this:\n"
                   "<json>{\"rice\": 0.25, \"fried tofu\": 0.33, \"fried garlic\": 0.03}</json>")
        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt2, file])
        # print("VOLUME RESPONSE")
        # print(response.text)
        map = self.parse_volume_json(response.text)
        return response.text, map

    def get_weight(self, food_map):
        prompt2 = ("You are given this JSON string representing a dish where each key is a food and its value is its volume:\n\n"
                   f"{food_map}\n\n"
                   "Given the volume of the food, find its density by multiplying it, "
                   "mathematically not programmatically, by its volume"
                   " (volume is given in the JSON string in Liters) to get the weight of the food.\n\n"
                   "Rules to follow in your response:\n"
                   "1. Show your thought process\n"
                   "2. After showing your thought process, format your response in JSON. Wrap this JSON in a ‘json’ html tag so that "
                   "I can parse it easily. Your JSON response should have a key for each food and"
                   " the value of each key should be the weight (as a float in grams)\n\n"
                   "Format your JSON response like this:\n"
                   "<json>{\"rice\": 100, \"fried tofu\": 120, \"fried garlic\": 80}</json>")
        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt2])
        # print("WEIGHT RESPONSE")
        # print(response.text)
        map = self.parse_volume_json(response.text)
        return response.text, map

    def get_description(self):
        file = utils.upload_file_to_gemini(self.image_path, self.client)
        prompt = ("You are given an image of some food. Your goal is to analyze the food contents and "
                  "create a suitable name for the dish as well as a brief description of the dish. In the"
                  " description, include details, like a percentage, about how much of the dish has been "
                  "wasted.\n\n"
                  "Rules to follow in your response:\n"
                  "1. Show your thought process\n"
                  "2. After showing your thought process, format your response in JSON. "
                  "Wrap this JSON in a ‘json’ html tag so that I can parse it easily. "
                  "Your JSON response should have two keys. One key called ‘name’ with the name of "
                  "the dish as the value and one key called ‘description’ with the description of "
                  "the dish as the value.\n\n"
                  "Format your JSON response like this:\n"
                  "<json>{\”name\”: \“Dish name\”, \”description\”: \“Dish description\”}</json>")

        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, file])

        map = self.parse_description_json(response.text)

        return map

    def parse_food_json(self, input_string):
        # Regular expression to find the content inside <json> tags
        json_pattern = re.compile(r'<json>(.*?)</json>', re.DOTALL)

        # Search for the JSON content within the <json> tags
        match = json_pattern.search(input_string)

        if not match:
            raise ValueError("No <json> tag found in the input string.")

        json_content = match.group(1).strip()

        try:
            # Parse the JSON content
            parsed_json = json.loads(json_content)

            # Assuming the JSON contains only one key which maps to an array
            if not isinstance(parsed_json, dict) or len(parsed_json) != 1:
                raise ValueError("The JSON should contain exactly one key mapping to an array.")

            # Extract the array from the JSON
            array = next(iter(parsed_json.values()))

            if not isinstance(array, list):
                raise ValueError("The value associated with the key should be an array.")

            regular_string = ', '.join(array)
            return regular_string

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON content: {e}")

    def parse_volume_json(self, input_string):
        # Regular expression to find the content inside <json> tags
        json_pattern = re.compile(r'<json>(.*?)</json>', re.DOTALL)

        # Search for the JSON content within the <json> tags
        match = json_pattern.search(input_string)

        if not match:
            raise ValueError("No <json> tag found in the input string.")

        json_content = match.group(1).strip()

        try:
            # Parse the JSON content
            parsed_json = json.loads(json_content)

            # Ensure the parsed JSON is a dictionary
            if not isinstance(parsed_json, dict):
                raise ValueError("The JSON content must be a dictionary.")

            # Validate that all values are integers
            for key, value in parsed_json.items():
                if not isinstance(value, float):
                    raise ValueError(f"The value for key '{key}' is not an float.")

            # Return the dictionary
            return parsed_json

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON content: {e}")

    def parse_description_json(self, input_string):
        # Regular expression to find content inside <json> tags
        json_pattern = re.compile(r'<json>\s*({.*?})\s*</json>', re.DOTALL)

        # Search for the JSON content
        match = json_pattern.search(input_string)

        if match:
            json_content = match.group(1)
            try:
                # Parse the JSON content into a dictionary
                parsed_json = json.loads(json_content)
                return parsed_json
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                return None
        else:
            print("No <json> tag found in the input string.")
            return None