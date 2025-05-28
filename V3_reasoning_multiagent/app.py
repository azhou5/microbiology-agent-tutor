import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env
import json
import logging
from datetime import datetime
from flask import Flask, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from tutor import MedicalMicrobiologyTutor # Assuming tutor.py is in the same directory
import config

# --- Use DB flag ---
use_db = config.USE_GLOBAL_DB or config.USE_LOCAL_DB

# --- Configuration ---
FEEDBACK_LOG_FILE = 'feedback.log'
CASE_FEEDBACK_LOG_FILE = 'case_feedback.log'  # New log file for case feedback
MODEL_STATE_FILE = 'model_state.json'  # File to store the selected model
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

def get_current_model():
    """Get the current model from the state file or default to config."""
    try:
        if os.path.exists(MODEL_STATE_FILE):
            with open(MODEL_STATE_FILE, 'r') as f:
                state = json.load(f)
                selected = state.get('model', config.API_MODEL_NAME)
                # Sync only when using the Azure backend
                if config.LLM_BACKEND == "azure":
                    config.API_MODEL_NAME = selected
                return selected
    except Exception as e:
        logging.error(f"Error reading model state: {e}")
    return config.API_MODEL_NAME

def save_current_model(model):
    """Save the current model to the state file."""
    try:
        with open(MODEL_STATE_FILE, 'w') as f:
            json.dump({'model': model}, f)
            # Keep config module in sync at runtime (only for Azure backend)
            if config.LLM_BACKEND == "azure":
                config.API_MODEL_NAME = model
    except Exception as e:
        logging.error(f"Error saving model state: {e}")

# Global model variable initialized from state file or config
CURRENT_MODEL = get_current_model()

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

# — Database setup —
db = None
if use_db:
    try:
        # Select the database URL based on environment/config flags
        if config.USE_GLOBAL_DB:
            db_uri = config.GLOBAL_DATABASE_URL
        elif config.USE_LOCAL_DB:
            db_uri = config.LOCAL_DATABASE_URL
        else:
            db_uri = None

        if db_uri:
            app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
            app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
            db = SQLAlchemy(app)
            # Test the connection
            with app.app_context():
                db.engine.connect()
            logging.info("Successfully connected to database")
        else:
            logging.warning("No database URI provided, falling back to file logging")
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        logging.warning("Falling back to file logging")
        db = None
else:
    logging.info("Database disabled, using file logging")

# — Models —
if db is not None:
    class FeedbackEntry(db.Model):
        __tablename__ = 'feedback'
        id = db.Column(db.Integer, primary_key=True)
        timestamp = db.Column(db.DateTime, nullable=False)
        organism = db.Column(db.String(128), nullable=True)
        rating = db.Column(db.String(2), nullable=False)
        rated_message = db.Column(db.Text, nullable=False)
        feedback_text = db.Column(db.Text, nullable=True)
        replacement_text = db.Column(db.Text, nullable=True)
        chat_history = db.Column(db.JSON, nullable=True)
        case_id = db.Column(db.String(128), nullable=True)

    class CaseFeedbackEntry(db.Model):
        __tablename__ = 'case_feedback'
        id = db.Column(db.Integer, primary_key=True)
        timestamp = db.Column(db.DateTime, nullable=False)
        organism = db.Column(db.String(128), nullable=True)
        detail_rating = db.Column(db.String(2), nullable=False)
        helpfulness_rating = db.Column(db.String(2), nullable=False)
        accuracy_rating = db.Column(db.String(2), nullable=False)
        comments = db.Column(db.Text, nullable=True)
        case_id = db.Column(db.String(128), nullable=False)

    # Create tables if they don't exist
    with app.app_context():
        try:
            # Check if tables exist and have correct columns
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            # Define expected columns for each table
            expected_columns = {
                'feedback': [
                    'id', 'timestamp', 'organism', 'rating', 'rated_message',
                    'feedback_text', 'replacement_text', 'chat_history', 'case_id'
                ],
                'case_feedback': [
                    'id', 'timestamp', 'organism', 'detail_rating',
                    'helpfulness_rating', 'accuracy_rating', 'comments', 'case_id'
                ]
            }
            
            # Check if tables need to be recreated
            need_recreate = False
            for table_name, expected_cols in expected_columns.items():
                if table_name not in existing_tables:
                    need_recreate = True
                    break
                
                # Check if all expected columns exist
                existing_cols = [col['name'] for col in inspector.get_columns(table_name)]
                if not all(col in existing_cols for col in expected_cols):
                    need_recreate = True
                    break
            
            if need_recreate:
                logging.info("Database schema mismatch detected. Recreating tables...")
                db.drop_all()  # Drop existing tables
                db.create_all()  # Create new tables with correct schema
                logging.info("Database tables recreated successfully.")
            else:
                logging.info("Database tables exist with correct schema.")
                
        except Exception as e:
            logging.error(f"Error checking/creating database tables: {e}")
            logging.info("Attempting to create tables from scratch...")
            db.create_all()
            logging.info("Database tables created successfully.")
else:
    # Define empty model classes for when db is None
    class FeedbackEntry:
        pass
    class CaseFeedbackEntry:
        pass

# --- Tutor Initialization ---
# Initialize tutor as None
tutor = None

def get_tutor(model_name=None):
    """Get or create a tutor instance with the specified model."""
    global tutor
    if tutor is None or (model_name and tutor.current_model != model_name):
        tutor = MedicalMicrobiologyTutor(
            output_tool_directly=config.OUTPUT_TOOL_DIRECTLY,
            run_with_faiss=config.USE_FAISS,
            reward_model_sampling=config.REWARD_MODEL_SAMPLING,
            model_name=model_name
        )
    return tutor

# --- Routes ---
@app.route('/')
def index():
    """Serves the main HTML page."""
    # Initialize tutor with default model if not already initialized
    global tutor
    if tutor is None:
        tutor = get_tutor(CURRENT_MODEL)
    else:
        tutor.reset()
    return render_template('index.html', current_model=CURRENT_MODEL)

@app.route('/start_case', methods=['POST'])
def start_case():
    """Starts a new case with the selected organism."""
    global CURRENT_MODEL, tutor
    try:
        data = request.get_json()
        organism = data.get('organism')
        model_name = data.get('model', CURRENT_MODEL)
        
        logging.info(f"Starting new case with organism: {organism} and model: {model_name}")
        
        if model_name != CURRENT_MODEL:
            CURRENT_MODEL = model_name
            save_current_model(CURRENT_MODEL)
            if config.LLM_BACKEND == "azure":
                config.API_MODEL_NAME = CURRENT_MODEL  # keep config in sync
        
        # Get or create tutor instance with the specified model
        tutor = get_tutor(CURRENT_MODEL)
            
        initial_message = tutor.start_new_case(organism=organism)
        # The tutor's messages list now contains the system prompt and the first assistant message
        return jsonify({
            "initial_message": initial_message,
            "history": tutor.messages  # Send initial history
        })
    except Exception as e:
        logging.error(f"Error starting case: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    """Handles incoming chat messages from the user."""
    global tutor
    try:
        data = request.get_json()
        message = data.get('message')
        model_name = data.get('model', CURRENT_MODEL)
        
        logging.info(f"Received user message: {message}")

        # Get or create tutor instance with the specified model
        tutor = get_tutor(model_name)

        # The tutor.__call__ method updates its internal message list
        response = tutor(message)

        logging.info(f"Sending tutor response: {response}")

        return jsonify({
            "response": response,
            "history": tutor.messages  # Send the full updated history
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
        current_organism = tutor.current_organism or "Unknown"
        case_id = data.get('case_id')

        if use_db:
            entry = FeedbackEntry(
                timestamp=datetime.utcnow(),
                organism=current_organism,
                rating=rating,
                rated_message=message,
                feedback_text=feedback_text,
                replacement_text=replacement_text,
                chat_history=visible_history,
                case_id=case_id
            )
            db.session.add(entry)
            db.session.commit()
        else:
            # Fallback to file logging
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "organism": current_organism,
                "rating": rating,
                "rated_message": message,
                "feedback_text": feedback_text,
                "replacement_text": replacement_text,
                "case_id": case_id,
                "visible_chat_history": visible_history,
            }
            feedback_logger.info(json.dumps(log_entry, indent=2))

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
        case_id = data.get('case_id')
        
        if not all([detail_rating, helpfulness_rating, accuracy_rating]):
            return jsonify({"error": "Missing required feedback ratings"}), 400
            
        # Get current organism
        current_organism = tutor.current_organism or "Unknown"

        if use_db:
            entry = CaseFeedbackEntry(
                timestamp=datetime.utcnow(),
                organism=current_organism,
                detail_rating=detail_rating,
                helpfulness_rating=helpfulness_rating,
                accuracy_rating=accuracy_rating,
                comments=comments,
                case_id=case_id
            )
            db.session.add(entry)
            db.session.commit()
        else:
            # Fallback to file logging
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "organism": current_organism,
                "detail_rating": detail_rating,
                "helpfulness_rating": helpfulness_rating,
                "accuracy_rating": accuracy_rating,
                "comments": comments,
                "case_id": case_id
            }
            case_feedback_logger.info(json.dumps(log_entry, indent=2))
        
        logging.info(f"Received case feedback for {current_organism} case - Detail: {detail_rating}/5, Helpfulness: {helpfulness_rating}/5, Accuracy: {accuracy_rating}/5")
        return jsonify({"status": "Case feedback received"}), 200
    except Exception as e:
        logging.error(f"Error processing case feedback: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500



# --- Admin Feedback Route ---
@app.route('/admin/feedback')
def admin_feedback():
    """Simple HTML view of feedback entries."""
    entries = FeedbackEntry.query.order_by(FeedbackEntry.timestamp.desc()).all()
    # Build a simple HTML table
    rows = ""
    for e in entries:
        rows += (
            f"<tr>"
            f"<td>{e.id}</td>"
            f"<td>{e.timestamp}</td>"
            f"<td>{e.organism or ''}</td>"
            f"<td>{e.rating}</td>"
            f"<td>{e.feedback_text or ''}</td>"
            f"<td>{e.replacement_text or ''}</td>"
            f"</tr>"
        )
    html = (
        "<html><head><title>Feedback Admin</title></head>"
        "<body>"
        "<h1>Feedback Entries</h1>"
        "<table border='1' cellpadding='5' cellspacing='0'>"
        "<thead>"
        "<tr><th>ID</th><th>Timestamp</th><th>Organism</th>"
        "<th>Rating</th><th>Feedback Text</th><th>Replacement Text</th></tr>"
        "</thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
        "</body></html>"
    )
    return html


@app.cli.command("shell")
def shell():
    """Run a Flask interactive shell with app context."""
    import code
    code.interact(local=dict(globals(), **locals()))


if __name__ == '__main__':
    import config
    if not config.TERMINAL_MODE:
        # Make sure the templates and static folders exist relative to app.py
        app.run(host='0.0.0.0',port=5001, debug=True)  # listen on all interfaces so localhost/127.0.0.1 both work
    else:
        print("App is in TERMINAL_MODE. Run 'python run_terminal.py' or './run_terminal.sh' instead.")