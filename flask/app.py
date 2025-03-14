# app.py

from flask import Flask, jsonify, request
from datetime import datetime
from services.density_service import density
import logging

from ai.predictor import Predictor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Register the blueprint
app.register_blueprint(density, url_prefix='/density')

# Basic error handling
class APIError(Exception):
    """Base class for API errors"""
    def __init__(self, message, status_code=400):
        super().__init__()
        self.message = message
        self.status_code = status_code

@app.errorhandler(APIError)
def handle_api_error(error):
    response = jsonify({'error': error.message})
    response.status_code = error.status_code
    return response

# Routes
@app.route('/')
def home():
    return jsonify({
        'message': 'Welcome to the Flask API for Food Density Service.',
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/echo', methods=['POST'])
def echo():
    if not request.is_json:
        raise APIError('Content-Type must be application/json')
    
    data = request.get_json()
    return jsonify({
        'message': 'Echo response',
        'data': data,
        'timestamp': datetime.now().isoformat()
    })

# Health check endpoint
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'Healthy: TreeHacks 2025',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/predict', methods=['POST'])
def predict():
    if not request.is_json:
        raise APIError('Content-Type must be application/json')

    data = request.get_json()
    image = data['image']

    predictor = Predictor(image)

    food_prediction = predictor.get_foods()
    volume_prediction, map = predictor.get_volume(food_prediction)
    weight_prediction, map = predictor.get_weight(map)

    return jsonify({
        'response': map,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/description', methods=['POST'])
def fullness():
    if not request.is_json:
        raise APIError('Content-Type must be application/json')

    data = request.get_json()
    image = data['image']

    predictor = Predictor(image)

    map = predictor.get_description()

    return jsonify({
        'response': map,
        'timestamp': datetime.now().isoformat()
    })


if __name__ == '__main__':
    # Enable hot reloading and run on localhost
    app.run(host='0.0.0.0', port=5001, debug=True)