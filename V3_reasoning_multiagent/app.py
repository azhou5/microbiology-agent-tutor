import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env
import json
import logging
from datetime import datetime
from flask import Flask, request, render_template, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from tutor import MedicalMicrobiologyTutor
from agents.case import get_case
import config
import secrets

# --- Flask App Initialization ---
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))

# --- Use DB flag ---
use_db = config.USE_GLOBAL_DB or config.USE_LOCAL_DB

# --- Configuration ---
FEEDBACK_LOG_FILE = 'feedback.log'
CASE_FEEDBACK_LOG_FILE = 'case_feedback.log'
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
file_handler = logging.FileHandler(FEEDBACK_LOG_FILE)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
feedback_logger = logging.getLogger('feedback')
feedback_logger.addHandler(file_handler)
feedback_logger.setLevel(logging.INFO)
feedback_logger.propagate = False

case_feedback_handler = logging.FileHandler(CASE_FEEDBACK_LOG_FILE)
case_feedback_handler.setFormatter(logging.Formatter(LOG_FORMAT))
case_feedback_logger = logging.getLogger('case_feedback')
case_feedback_logger.addHandler(case_feedback_handler)
case_feedback_logger.setLevel(logging.INFO)
case_feedback_logger.propagate = False

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

# --- Models ---
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
    # Define model classes for when db is None
    class FeedbackEntry:
        def __init__(self, timestamp=None, organism=None, rating=None, rated_message=None, 
                     feedback_text=None, replacement_text=None, chat_history=None, case_id=None):
            self.timestamp = timestamp
            self.organism = organism
            self.rating = rating
            self.rated_message = rated_message
            self.feedback_text = feedback_text
            self.replacement_text = replacement_text
            self.chat_history = chat_history
            self.case_id = case_id

    class CaseFeedbackEntry:
        def __init__(self, timestamp=None, organism=None, detail_rating=None, 
                     helpfulness_rating=None, accuracy_rating=None, comments=None, case_id=None):
            self.timestamp = timestamp
            self.organism = organism
            self.detail_rating = detail_rating
            self.helpfulness_rating = helpfulness_rating
            self.accuracy_rating = accuracy_rating
            self.comments = comments
            self.case_id = case_id

# --- Session-based Tutor Management ---

def get_tutor_from_session():
    """
    Retrieves or creates a MedicalMicrobiologyTutor instance based on session data.
    Initializes a new tutor if no session data is found.
    """
    model_name_from_session = session.get('tutor_model_name', 'o3-mini') # Default to o3-mini

    tutor = MedicalMicrobiologyTutor(
        output_tool_directly=config.OUTPUT_TOOL_DIRECTLY,
        run_with_faiss=config.USE_FAISS,
        reward_model_sampling=config.REWARD_MODEL_SAMPLING,
        model_name=model_name_from_session
    )

    tutor.messages = session.get('tutor_messages', [{"role": "system", "content": "Initializing..."}])
    tutor.current_organism = session.get('tutor_current_organism', None)
    tutor.case_description = session.get('tutor_case_description', None)
    
    if tutor.case_description and tutor.messages and tutor.messages[0]['content'] == "Initializing...":
        tutor._update_system_message()
        session['tutor_messages'] = tutor.messages
    elif not tutor.messages: # Ensure messages list always exists
        tutor.messages = [{"role": "system", "content": "Initializing..."}]
        session['tutor_messages'] = tutor.messages

    return tutor

def save_tutor_to_session(tutor):
    """Saves the tutor's state to the current session."""
    session['tutor_messages'] = tutor.messages
    session['tutor_current_organism'] = tutor.current_organism
    session['tutor_case_description'] = tutor.case_description
    session['tutor_model_name'] = tutor.current_model
    session.modified = True

# --- Routes ---
@app.route('/')
def index():
    """Serves the main HTML page."""
    tutor = get_tutor_from_session()
    return render_template('index.html', current_model=tutor.current_model or 'o3-mini')

@app.route('/start_case', methods=['POST'])
def start_case():
    """Starts a new case with the selected organism, managed in session."""
    try:
        data = request.get_json()
        organism = data.get('organism')
        model_name = 'o3-mini'  # Always use o3-mini for new cases as per current logic

        logging.info(f"Starting new case with organism: {organism} and model: {model_name} (Session new: {session.new})")
        
        tutor = MedicalMicrobiologyTutor(
            output_tool_directly=config.OUTPUT_TOOL_DIRECTLY,
            run_with_faiss=config.USE_FAISS,
            reward_model_sampling=config.REWARD_MODEL_SAMPLING,
            model_name=model_name
        )
            
        initial_message = tutor.start_new_case(organism=organism)
        save_tutor_to_session(tutor)
        
        return jsonify({
            "initial_message": initial_message,
            "history": tutor.messages
        })
    except Exception as e:
        logging.error(f"Error starting case for organism {organism}: {e} (Session new: {session.new})", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    """Handles incoming chat messages from the user, using session-based tutor."""
    try:
        data = request.get_json()
        message_text = data.get('message')
        client_history = data.get('history')
        client_organism_key = data.get('organism_key')

        tutor = get_tutor_from_session()

        if not tutor.case_description and client_history and len(client_history) > 0:
            logging.warning(f"Chat attempt with empty session case. Client history length: {len(client_history)}. Attempting recovery. (Session new: {session.new})")
            
            recovered_organism_key_for_get_case = None

            if client_organism_key:
                logging.info(f"Using organism_key '{client_organism_key}' directly from client request for recovery. (Session new: {session.new})")
                recovered_organism_key_for_get_case = client_organism_key
            else:
                logging.info(f"client_organism_key not provided. Attempting to parse from system message. (Session new: {session.new})")
                system_message_from_client = next((msg for msg in client_history if msg.get("role") == "system" and "Initializing..." not in msg.get("content","") ), None)
                if system_message_from_client:
                    content_lines = system_message_from_client.get("content", "").split('\n')
                    if content_lines:
                        first_line = content_lines[0].strip()
                        if first_line.startswith("# CLINICAL CASE:") and "INFECTION" in first_line.upper():
                            try:
                                organism_name_part = first_line.split(":")[1].replace("INFECTION", "", 1).strip()
                                temp_key = organism_name_part.lower().replace(" ", "_")
                                if "(malaria)" in temp_key:
                                    temp_key = temp_key.replace("(malaria)","").strip()
                                recovered_organism_key_for_get_case = temp_key
                                logging.info(f"Tentatively recovered organism key '{recovered_organism_key_for_get_case}' from system message. (Session new: {session.new})")
                            except IndexError:
                                logging.warning(f"Could not parse organism from system message line: {first_line}. (Session new: {session.new})")
            
            if recovered_organism_key_for_get_case:
                canonical_case_description = get_case(recovered_organism_key_for_get_case)
                if canonical_case_description:
                    logging.info(f"Successfully fetched canonical case for '{recovered_organism_key_for_get_case}'. (Session new: {session.new})")
                    tutor.current_organism = recovered_organism_key_for_get_case 
                    tutor.case_description = canonical_case_description
                    tutor.messages = client_history
                    tutor._update_system_message() 
                    save_tutor_to_session(tutor)
                    logging.info(f"Tutor state successfully recovered and saved. (Session new: {session.new})")
                else:
                    logging.error(f"Failed to fetch canonical case for '{recovered_organism_key_for_get_case}'. Aborting recovery. (Session new: {session.new})")
                    return jsonify({"error": "Could not fully restore session. Please start a new case.", "needs_new_case": True}), 400
            else:
                logging.warning(f"Could not determine organism for recovery. (Session new: {session.new})")
                return jsonify({"error": "No active case. Please start a new case.", "needs_new_case": True}), 400
        
        elif not tutor.case_description: 
             logging.warning(f"Chat attempt without active case. (Session new: {session.new})")
             return jsonify({"error": "No active case. Please start a new case.", "needs_new_case": True}), 400

        logging.info(f"Received user message: {message_text} (Session new: {session.new})")
        response_content = tutor(message_text)
        save_tutor_to_session(tutor)
        logging.info(f"Sending tutor response for organism {tutor.current_organism} (Session new: {session.new})")

        return jsonify({
            "response": response_content,
            "history": tutor.messages
        })
    except Exception as e:
        logging.error(f"Error during chat processing: {e} (Session new: {session.new})", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/feedback', methods=['POST'])
def feedback():
    """Receives and logs feedback, associating with session's organism if available."""
    try:
        data = request.get_json()
        rating = data.get('rating')
        message_content = data.get('message') # The specific assistant message being rated
        history_from_client = data.get('history')
        feedback_text = data.get('feedback_text', '')
        replacement_text = data.get('replacement_text', '')
        case_id_from_client = data.get('case_id') # case_id is client-generated

        if not rating or not message_content or history_from_client is None:
             return jsonify({"error": "Missing feedback data (rating, message, or history)"}), 400

        visible_history = []
        if isinstance(history_from_client, list):
            for msg in history_from_client:
                if isinstance(msg, dict) and msg.get('role') in ['user', 'assistant']:
                    visible_history.append({
                        "role": msg.get('role'),
                        "content": msg.get('content', '')
                    })
        else:
            logging.warning("Received history is not a list, logging as is.")
            visible_history = history_from_client

        tutor = get_tutor_from_session() # Get tutor to access current_organism

        if use_db:
            entry = FeedbackEntry(
                timestamp=datetime.utcnow(),
                organism=tutor.current_organism, # From session
                rating=rating,
                rated_message=message_content,
                feedback_text=feedback_text,
                replacement_text=replacement_text,
                chat_history=visible_history, # Log client's view of history at feedback time
                case_id=case_id_from_client
            )
            db.session.add(entry)
            db.session.commit()
        else:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "organism": tutor.current_organism, # From session
                "rating": rating,
                "rated_message": message_content,
                "feedback_text": feedback_text,
                "replacement_text": replacement_text,
                "case_id": case_id_from_client,
                "visible_chat_history": visible_history,
                "session_is_new": session.new
            }
            feedback_logger.info(json.dumps(log_entry, indent=2))

        logging.info(f"Received feedback: {rating}/5 for message snippet: '{message_content[:50]}...' (Organism: {tutor.current_organism}, Session new: {session.new})")
        # If replacement text is provided, the client already appends it and the next /chat call will sync the history
        return jsonify({"status": "Feedback received"}), 200
    except Exception as e:
        logging.error(f"Error processing feedback: {e} (Session new: {session.new})", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/case_feedback', methods=['POST'])
def case_feedback():
    """Receives and logs overall case feedback, associating with session's organism."""
    try:
        data = request.get_json()
        detail_rating = data.get('detail')
        helpfulness_rating = data.get('helpfulness')
        accuracy_rating = data.get('accuracy')
        comments = data.get('comments', '')
        case_id_from_client = data.get('case_id')
        
        if not all([detail_rating, helpfulness_rating, accuracy_rating]):
            return jsonify({"error": "Missing required feedback ratings"}), 400
            
        tutor = get_tutor_from_session()
        current_organism_for_log = tutor.current_organism or "Unknown"

        if use_db:
            entry = CaseFeedbackEntry(
                timestamp=datetime.utcnow(),
                organism=current_organism_for_log, # From session
                detail_rating=detail_rating,
                helpfulness_rating=helpfulness_rating,
                accuracy_rating=accuracy_rating,
                comments=comments,
                case_id=case_id_from_client
            )
            db.session.add(entry)
            db.session.commit()
        else:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "organism": current_organism_for_log, # From session
                "detail_rating": detail_rating,
                "helpfulness_rating": helpfulness_rating,
                "accuracy_rating": accuracy_rating,
                "comments": comments,
                "case_id": case_id_from_client,
                "session_is_new": session.new
            }
            case_feedback_logger.info(json.dumps(log_entry, indent=2))
        
        logging.info(f"Received case feedback for {current_organism_for_log} case - Detail: {detail_rating}/5, Helpfulness: {helpfulness_rating}/5, Accuracy: {accuracy_rating}/5 (Session new: {session.new})")
        # After case feedback, typically the session might be cleared or reset for a new case.
        # For now, let's just clear the tutor related parts of the session.
        session.pop('tutor_messages', None)
        session.pop('tutor_current_organism', None)
        session.pop('tutor_case_description', None)
        session.pop('tutor_model_name', None)
        logging.info(f"Tutor state cleared from session after case feedback. (Session new: {session.new})")

        return jsonify({"status": "Case feedback received"}), 200
    except Exception as e:
        logging.error(f"Error processing case feedback: {e} (Session new: {session.new})", exc_info=True)
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