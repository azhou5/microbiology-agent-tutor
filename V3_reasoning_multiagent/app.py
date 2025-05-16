from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env

import os
import json
import logging
from datetime import datetime
from flask import Flask, request, render_template, jsonify
from tutor import MedicalMicrobiologyTutor # Assuming tutor.py is in the same directory

# --- Configuration ---
FEEDBACK_LOG_FILE = 'feedback.log'
CASE_FEEDBACK_LOG_FILE = 'case_feedback.log'  # New log file for case feedback
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
file_handler = logging.FileHandler(FEEDBACK_LOG_FILE)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
# Use a distinct logger name for feedback to avoid conflicts if tutor.py also uses logging
feedback_logger = logging.getLogger('feedback')
feedback_logger.addHandler(file_handler)
feedback_logger.setLevel(logging.INFO)
feedback_logger.propagate = False # Prevent feedback logs from appearing in the main console log

# Setup case feedback logger
case_feedback_handler = logging.FileHandler(CASE_FEEDBACK_LOG_FILE)
case_feedback_handler.setFormatter(logging.Formatter(LOG_FORMAT))
case_feedback_logger = logging.getLogger('case_feedback')
case_feedback_logger.addHandler(case_feedback_handler)
case_feedback_logger.setLevel(logging.INFO)
case_feedback_logger.propagate = False

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Tutor Initialization ---
# Instantiate the tutor globally or manage sessions if needed
# For simplicity, using a single global instance here.
# Be aware of concurrency issues if multiple users access this simultaneously without session management.
tutor = MedicalMicrobiologyTutor(
  output_tool_directly=True,
  run_with_faiss=False,
  reward_model_sampling=True
)


# --- Routes ---
@app.route('/')
def index():
    """Serves the main HTML page."""
    # Reset tutor state when the main page is loaded (for a fresh start)
    # In a multi-user scenario, you'd handle sessions differently.
    tutor.reset()
    return render_template('index.html')

@app.route('/start_case', methods=['POST'])
def start_case():
    """Starts a new case with the selected organism."""
    try:
        data = request.get_json()
        organism = data.get('organism', 'staphylococcus aureus') # Default if not provided
        logging.info(f"Starting new case with organism: {organism}")
        initial_message = tutor.start_new_case(organism=organism)
        # The tutor's messages list now contains the system prompt and the first assistant message
        return jsonify({
            "initial_message": initial_message,
            "history": tutor.messages # Send initial history
        })
    except Exception as e:
        logging.error(f"Error starting case: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    """Handles incoming chat messages from the user."""
    try:
        data = request.get_json()
        user_message = data.get('message')
        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        logging.info(f"Received user message: {user_message}")

        # The tutor.__call__ method updates its internal message list
        tutor_response = tutor(user_message)

        logging.info(f"Sending tutor response: {tutor_response}")

        # Return the latest response and the updated history
        return jsonify({
            "response": tutor_response,
            "history": tutor.messages # Send the full updated history
            })
    except Exception as e:
        logging.error(f"Error during chat processing: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/feedback', methods=['POST'])
def feedback():
    """Receives and logs feedback from the user."""
    try:
        data = request.get_json()
        rating = data.get('rating') # '1'-'5'
        message = data.get('message') # The specific assistant message being rated
        history_from_client = data.get('history') # Full chat history [{role: ..., content: ...}, ...] from client at time of feedback
        feedback_text = data.get('feedback_text', '') # Optional text
        replacement_text = data.get('replacement_text', '') # New: user's preferred response

        if not rating or not message or history_from_client is None: # Check history presence
             return jsonify({"error": "Missing feedback data (rating, message, or history)"}), 400

        # --- Filter the history ---
        # Keep only the content of user and assistant messages for logging clarity
        visible_history = []
        if isinstance(history_from_client, list):
            for msg in history_from_client:
                # Include only user messages and final assistant responses in the log
                # Exclude system prompts, observations, etc.
                if isinstance(msg, dict) and msg.get('role') in ['user', 'assistant']:
                    visible_history.append({
                        "role": msg.get('role'),
                        "content": msg.get('content', '')
                    })
        else:
            logging.warning("Received history is not a list, logging as is.")
            visible_history = history_from_client # Log whatever was sent if not a list

        # --- Get current organism ---
        current_organism = tutor.current_organism or "Unknown" # Get from tutor instance

        # --- Prepare log entry ---
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "organism": current_organism, # Add the organism
            "rating": rating,
            "rated_message": message, # Rename for clarity
            "feedback_text": feedback_text,
            "replacement_text": replacement_text,
            "visible_chat_history": visible_history, # Log the filtered history
        }

        # Log the feedback entry as a JSON string
        feedback_logger.info(json.dumps(log_entry, indent=2)) # Use indent for readability in the log file

        logging.info(f"Received feedback: {rating}/5 for message snippet: '{message[:50]}...' (Organism: {current_organism})")
        return jsonify({"status": "Feedback received"}), 200
    except Exception as e:
        logging.error(f"Error processing feedback: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/case_feedback', methods=['POST'])
def case_feedback():
    """Receives and logs overall case feedback from the user."""
    try:
        data = request.get_json()
        detail_rating = data.get('detail')
        helpfulness_rating = data.get('helpfulness')
        accuracy_rating = data.get('accuracy')
        comments = data.get('comments', '')
        
        if not all([detail_rating, helpfulness_rating, accuracy_rating]):
            return jsonify({"error": "Missing required feedback ratings"}), 400
            
        # Get current organism
        current_organism = tutor.current_organism or "Unknown"
        
        # Prepare log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "organism": current_organism,
            "detail_rating": detail_rating,
            "helpfulness_rating": helpfulness_rating,
            "accuracy_rating": accuracy_rating,
            "comments": comments
        }
        
        # Log the feedback entry as a JSON string
        case_feedback_logger.info(json.dumps(log_entry, indent=2))
        
        logging.info(f"Received case feedback for {current_organism} case - Detail: {detail_rating}/5, Helpfulness: {helpfulness_rating}/5, Accuracy: {accuracy_rating}/5")
        return jsonify({"status": "Case feedback received"}), 200
    except Exception as e:
        logging.error(f"Error processing case feedback: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# --- Main Execution ---
if __name__ == '__main__':
    import config
    if not config.TERMINAL_MODE:
        # Make sure the templates and static folders exist relative to app.py
        app.run(debug=True) # debug=True for development, set to False for production
    else:
        print("App is in TERMINAL_MODE. Run 'python run_terminal.py' or './run_terminal.sh' instead.")