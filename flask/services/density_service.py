from flask import Blueprint, jsonify, request
from openai import OpenAI
from dotenv import load_dotenv
import os
import logging
from typing import Optional, Dict, List, Union, Tuple
from functools import lru_cache
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Create blueprint for density service
density = Blueprint('density', __name__)

# Initialize Perplexity client
client = OpenAI(
    api_key=os.getenv('PERPLEXITY_API_KEY'),
    base_url="https://api.perplexity.ai"
)

@lru_cache(maxsize=1)
def load_reference_file() -> Tuple[Optional[Dict[str, float]], Optional[str]]:
    """
    Load the reference CSV file containing food density values.
    Returns a tuple of (density_dict, reference_text).
    density_dict maps food names to their density values.
    reference_text is the formatted text to be used in the API prompt.
    """
    try:
        # Use relative path from the Flask app root
        csv_path = 'data/food_density_reference.csv'
        logger.info(f"Attempting to load CSV from relative path: {csv_path}")
        
        df = pd.read_csv(csv_path)
        logger.info(f"Successfully loaded CSV with {len(df)} rows")
        logger.info(f"CSV columns: {df.columns.tolist()}")
        logger.info("First few rows of DataFrame:")
        logger.info(df.head())
        
        # Process the CSV data to create a dictionary and reference text
        density_dict = {}
        reference_lines = []
        
        for _, row in df.iterrows():
            # Skip empty rows or headers
            if pd.isna(row['Food name']) or pd.isna(row['Density']):
                continue
                
            # Get the food name and clean it
            food_name = str(row['Food name']).strip().strip('"').lower()
            density_str = str(row['Density']).strip()
            
            # Skip category headers and empty food names
            if not food_name or food_name.endswith(',') or pd.isna(density_str):
                continue
                
            try:
                # Handle range values (e.g., "0.56-0.72")
                if '-' in density_str:
                    low, high = map(float, density_str.split('-'))
                    density_value = (low + high) / 2
                else:
                    density_value = float(density_str)
                
                density_dict[food_name] = density_value
                reference_lines.append(f"{food_name}: {density_value} g/ml")
                logger.debug(f"Added density for {food_name}: {density_value}")
            except (ValueError, TypeError) as e:
                logger.debug(f"Failed to parse density for {food_name}: {str(e)}")
                continue
                
        logger.info(f"Successfully loaded {len(density_dict)} reference density values")
        if density_dict:
            # Log some sample entries
            sample_entries = list(density_dict.items())[:5]
            logger.info("Sample entries from parsed data:")
            for food, density in sample_entries:
                logger.info(f"  {food}: {density} g/ml")
                
        reference_text = "\n".join(reference_lines)
        return density_dict, reference_text
        
    except Exception as e:
        logger.error(f"Failed to load reference file: {str(e)}")
        return None, None
    
def get_density(food_name: str) -> Tuple[Optional[float], str]:
    """
    Get food density by first checking the reference CSV, then falling back to Perplexity API.
    Returns a tuple of (density_value, source) where source is either "reference" or "api"
    """
    # Load reference data
    density_dict, reference_text = load_reference_file()
    
    # Check for exact match in reference data
    if density_dict and food_name.lower() in density_dict:
        density = density_dict[food_name.lower()]
        logger.info(f"Found exact match in reference data for {food_name}: {density}")
        return round(density, 3), "reference"
    
    # # Check for contains match in reference data
    # if density_dict:
    #     # Get all matching foods that contain the search term
    #     matches = [(name, value) for name, value in density_dict.items() 
    #               if food_name.lower() in name]
        
    #     # If we found matches, use the first one
    #     if matches:
    #         food_name, density = matches[0]
    #         logger.info(f"Found contains match in reference data for {food_name}: {density}")
    #         return round(density, 3)

    # If no exact match, query Perplexity API with reference data
    system_content = (
        "You are a precise scientific assistant specializing in food science and density measurements. "
        "Your responses must follow these rules:\n"
        "1. Provide only a single numerical value in g/ml (grams per milliliter)\n"
        "2. Round all values to 3 decimal places\n"
        "3. If a food has multiple forms (e.g., raw vs cooked), assume its most common consumed form\n"
        "4. If uncertain, provide your best estimate based on similar foods\n"
        "5. Do not include units, explanations, or any other text\n"
        "6. If the query is invalid or non-food, respond with '0.000'"
    )
    
    if reference_text:
        system_content += f"\n\nRefer to the following reference densities for guidance:\n\n{reference_text}"

    messages = [
        {
            "role": "system",
            "content": system_content
        },
        {
            "role": "user",
            "content": f"What is the density of {food_name}?"
        }
    ]

    try:
        response = client.chat.completions.create(
            model="sonar-pro",
            messages=messages,
        )
        
        density_str = response.choices[0].message.content.strip()
        try:
            density = round(float(density_str), 3)
            logger.info(f"Successfully got density from API for {food_name}: {density}")
            return density, "api"
        except ValueError:
            logger.error(f"Invalid density value '{density_str}' for {food_name}")
            return None, "api"
            
    except Exception as e:
        logger.error(f"Perplexity API error for {food_name}: {str(e)}")
        return None, "api"

@density.route('/process-foods', methods=['POST'])
def process_foods() -> tuple[Dict[str, Union[str, List[Dict[str, Union[str, float]]]]], int]:
    """
    Process a list of foods to get their densities.
    First checks reference CSV for exact matches, then falls back to Perplexity API.
    
    Expected request format:
    {
        "foods": [
            {"name": "apple"},
            {"name": "banana"}
        ]
    }
    
    Returns:
        Tuple containing response dict and status code
    """
    if not request.is_json:
        return jsonify({
            'error': 'Content-Type must be application/json',
            'foods': []
        }), 400
    
    try:
        data = request.get_json()
    except Exception as e:
        logger.error(f"Failed to parse JSON: {str(e)}")
        return jsonify({
            'error': 'Invalid JSON format',
            'foods': []
        }), 400
    
    if not isinstance(data, dict) or 'foods' not in data:
        return jsonify({
            'error': 'Request must include a "foods" list',
            'foods': []
        }), 400
    
    foods = data['foods']
    if not isinstance(foods, list):
        return jsonify({
            'error': 'Foods must be a list',
            'foods': []
        }), 400
        
    processed_foods = []
    for food in foods:
        if not isinstance(food, dict) or 'name' not in food:
            logger.warning(f"Skipping invalid food item: {food}")
            continue
            
        density_value, source = get_density(food['name'])
        
        processed_foods.append({
            "food_name": food['name'],
            "density": density_value if density_value is not None else 0.000,
            "source": source
        })
    
    return jsonify({
        'foods': processed_foods
    }), 200