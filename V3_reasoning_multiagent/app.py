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
from agents.case_generator_rag import CaseGeneratorRAGAgent

# --- Flask App Initialization ---
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))

# --- Use DB flag ---
use_db = config.USE_GLOBAL_DB or config.USE_LOCAL_DB

# --- Configuration ---
FEEDBACK_LOG_FILE = 'feedback.log'
CASE_FEEDBACK_LOG_FILE = 'case_feedback.log'
DEBUG_LOG_FILE = 'debug_log.log'
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# --- Logging Setup ---
# This configures the root logger to send logs to both a file and the console.
logging.basicConfig(
    level=logging.INFO, 
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(DEBUG_LOG_FILE),
        logging.StreamHandler()
    ])

# The specific feedback loggers will still write to their own files
# and will NOT propagate messages to the root logger's handlers.
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

    class ConversationLog(db.Model):
        __tablename__ = 'conversation_log'
        id = db.Column(db.Integer, primary_key=True)
        case_id = db.Column(db.String(128), nullable=False, index=True)
        timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        role = db.Column(db.String(50), nullable=False)  # 'user', 'assistant', 'system'
        content = db.Column(db.Text, nullable=False)

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
                ],
                'conversation_log': [
                    'id', 'case_id', 'timestamp', 'role', 'content'
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

    class ConversationLog:
        def __init__(self, case_id=None, timestamp=None, role=None, content=None):
            self.case_id = case_id
            self.timestamp = timestamp
            self.role = role
            self.content = content

# --- Session-based Tutor Management ---

def get_tutor_from_session():
    """
    Retrieves or creates a MedicalMicrobiologyTutor instance based on session data.
    Initializes a new tutor if no session data is found.
    """
    model_name_from_session = session.get('tutor_model_name', config.API_MODEL_NAME) # Default to configured model
    current_organism_from_session = session.get('tutor_current_organism', None)

    tutor = MedicalMicrobiologyTutor(
        output_tool_directly=config.OUTPUT_TOOL_DIRECTLY,
        run_with_faiss=config.USE_FAISS,
        reward_model_sampling=config.REWARD_MODEL_SAMPLING,
        model_name=model_name_from_session
    )

    # Messages and case_description are no longer loaded from session here.
    # They will be populated by the route handlers (e.g., /chat, /start_case)
    # based on client data or by fetching anew.
    tutor.current_organism = current_organism_from_session
    # Ensure messages list always exists for the tutor object, even if minimal
    if not tutor.messages:
        tutor.messages = [{"role": "system", "content": "Initializing..."}]


    return tutor

def save_tutor_to_session(tutor):
    """Saves the tutor's essential state to the current session."""
    # Only save minimal, essential data to keep cookie size small
    session['tutor_current_organism'] = tutor.current_organism
    session['tutor_model_name'] = tutor.current_model
    # Do NOT save tutor.messages or tutor.case_description to the session
    session.modified = True

# --- Routes ---
@app.route('/')
def index():
    """Serves the main HTML page."""
    tutor = get_tutor_from_session()
    return render_template('index.html', 
                           current_model=tutor.current_model or config.API_MODEL_NAME,
                           in_context_learning=config.IN_CONTEXT_LEARNING)

@app.route('/start_case', methods=['POST'])
def start_case():
    """Starts a new case with the selected organism, managed in session."""
    logging.info("[BACKEND_START_CASE] >>> Received request to /start_case.")
    try:
        data = request.get_json()
        organism = data.get('organism')
        model_name = config.API_MODEL_NAME  # Use configured model for new cases
        client_case_id = data.get('case_id') # Added to receive case_id
        logging.info(f"[BACKEND_START_CASE] 1. Parsed request data: organism='{organism}', case_id='{client_case_id}'")

        logging.info(f"Starting new case with organism: {organism} and model: {model_name} (Session new: {session.new}, Case ID: {client_case_id})")
        
        if not client_case_id:
            logging.error(f"Case ID missing in start_case request for organism {organism}. (Session new: {session.new})")
            return jsonify({"error": "Case ID is missing. Cannot start case."}), 400

        logging.info("[BACKEND_START_CASE] 2. Initializing MedicalMicrobiologyTutor.")
        tutor = MedicalMicrobiologyTutor(
            output_tool_directly=config.OUTPUT_TOOL_DIRECTLY,
            run_with_faiss=config.USE_FAISS,
            reward_model_sampling=config.REWARD_MODEL_SAMPLING,
            model_name=model_name
        )
            
        logging.info(f"[BACKEND_START_CASE] 3. Calling tutor.start_new_case with organism: '{organism}'.")
        initial_message = tutor.start_new_case(organism=organism)
        logging.info("[BACKEND_START_CASE] 6. Storing case_id in session and saving tutor state.")
        session['current_case_id'] = client_case_id # Store case_id in session
        save_tutor_to_session(tutor)

        if db and db is not None:
            try:
                # Log system message
                logging.info("[BACKEND_START_CASE] 7. Logging initial messages to database.")
                if tutor.messages and tutor.messages[0]['role'] == 'system':
                    system_log_entry = ConversationLog(
                        case_id=client_case_id,
                        role='system',
                        content=tutor.messages[0]['content'],
                        timestamp=datetime.utcnow()
                    )
                    db.session.add(system_log_entry)
                
                # Log initial assistant message
                assistant_log_entry = ConversationLog(
                    case_id=client_case_id,
                    role='assistant',
                    content=initial_message,
                    timestamp=datetime.utcnow()
                )
                db.session.add(assistant_log_entry)
                db.session.commit()
                logging.info(f"Initial messages logged to DB for case_id: {client_case_id}")
            except Exception as e:
                db.session.rollback()
                logging.error(f"Error logging initial messages to DB for case_id {client_case_id}: {e}", exc_info=True)
        
        logging.info("[BACKEND_START_CASE] 8. Preparing and sending final JSON response.")
        return jsonify({
            "initial_message": initial_message,
            "history": tutor.messages
        })
    except Exception as e:
        logging.error(f"[BACKEND_START_CASE] <<< Error during /start_case processing: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    chat_start_time = datetime.now()
    logging.info(f"[CHAT_PERF] /chat route started at {chat_start_time}")
    try:
        data = request.get_json()
        message_text = data.get('message')
        client_history = data.get('history')
        client_organism_key = data.get('organism_key')
        client_case_id = data.get('case_id') # Added to receive case_id

        get_tutor_start_time = datetime.now()
        tutor = get_tutor_from_session() # Gets model_name, and potentially stale current_organism
        logging.info(f"[CHAT_PERF] get_tutor_from_session took: {datetime.now() - get_tutor_start_time}")
        
        active_case_id = client_case_id or session.get('current_case_id')
        if not active_case_id:
            logging.warning(f"Chat attempt without active case_id. (Session new: {session.new})")
            return jsonify({"error": "No active case ID. Please start a new case.", "needs_new_case": True}), 400

        if client_organism_key:
            tutor.current_organism = client_organism_key
        elif not tutor.current_organism:
            logging.warning(f"Chat attempt without any organism key. (Session new: {session.new})")
            return jsonify({"error": "No active case. Organism key missing. Please start a new case.", "needs_new_case": True}), 400
        
        case_load_start_time = datetime.now()
        if tutor.current_organism and not tutor.case_description:
            tutor.case_description = get_case(tutor.current_organism)
            if not tutor.case_description:
                logging.error(f"Failed to fetch canonical case for '{tutor.current_organism}' during chat. (Session new: {session.new})")
                return jsonify({"error": f"Could not load case details for {tutor.current_organism}. Please try starting a new case.", "needs_new_case": True}), 400
        elif not tutor.case_description:
             logging.warning(f"Chat attempt without active case (case description missing for organism '{tutor.current_organism}'). (Session new: {session.new})")
             return jsonify({"error": "No active case. Please start a new case.", "needs_new_case": True}), 400
        logging.info(f"[CHAT_PERF] Case description loading/check took: {datetime.now() - case_load_start_time}")

        if client_history and isinstance(client_history, list):
            tutor.messages = client_history
        else:
            logging.warning(f"Client history not provided or invalid in /chat for organism {tutor.current_organism}. Re-initializing messages. (Session new: {session.new})")
            tutor.messages = [{"role": "system", "content": "Initializing..."}]

        update_system_msg_start_time = datetime.now()
        tutor._update_system_message()
        logging.info(f"[CHAT_PERF] _update_system_message took: {datetime.now() - update_system_msg_start_time}")

        logging.info(f"Received user message: {message_text} for organism {tutor.current_organism} (Session new: {session.new}, Case ID: {active_case_id})")
        
        db_log_user_start_time = datetime.now()
        if db and db is not None:
            try:
                user_log_entry = ConversationLog(
                    case_id=active_case_id,
                    role='user',
                    content=message_text,
                    timestamp=datetime.utcnow()
                )
                db.session.add(user_log_entry)
                db.session.commit() # Commit here or after assistant response
            except Exception as e:
                db.session.rollback()
                logging.error(f"Error logging user message to DB for case_id {active_case_id}: {e}", exc_info=True)
        logging.info(f"[CHAT_PERF] DB log (user) took: {datetime.now() - db_log_user_start_time}")

        tutor_call_start_time = datetime.now()
        response_content = tutor(message_text)
        logging.info(f"[CHAT_PERF] tutor(message_text) full call took: {datetime.now() - tutor_call_start_time}")
        
        db_log_assistant_start_time = datetime.now()
        if db and db is not None:
            try:
                assistant_log_entry = ConversationLog(
                    case_id=active_case_id,
                    role='assistant',
                    content=response_content,
                    timestamp=datetime.utcnow()
                )
                db.session.add(assistant_log_entry)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logging.error(f"Error logging assistant message to DB for case_id {active_case_id}: {e}", exc_info=True)
        logging.info(f"[CHAT_PERF] DB log (assistant) took: {datetime.now() - db_log_assistant_start_time}")

        save_session_start_time = datetime.now()
        save_tutor_to_session(tutor)
        logging.info(f"[CHAT_PERF] save_tutor_to_session took: {datetime.now() - save_session_start_time}")
        
        logging.info(f"Sending tutor response for organism {tutor.current_organism} (Session new: {session.new}, Case ID: {active_case_id})")
        logging.info(f"[CHAT_PERF] /chat route completed in: {datetime.now() - chat_start_time}")

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

        if use_db and db is not None:
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

        if use_db and db is not None:
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
        session.pop('current_case_id', None) # Clear case_id from session
        logging.info(f"Tutor state cleared from session after case feedback. (Session new: {session.new})")

        return jsonify({"status": "Case feedback received"}), 200
    except Exception as e:
        logging.error(f"Error processing case feedback: {e} (Session new: {session.new})", exc_info=True)
        return jsonify({"error": str(e)}), 500

# --- Admin Feedback Route ---
@app.route('/admin/feedback')
def admin_feedback():
    """Simple HTML view of feedback entries."""
    if not db:
        return "Database is not configured.", 500
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

@app.route('/admin/live_chats')
def admin_live_chats():
    """Displays live chat conversations from the database."""
    if not db:
        return "Database is not configured.", 500

    try:
        # Query all conversation logs, ordered by case_id and then by timestamp
        logs = ConversationLog.query.order_by(ConversationLog.case_id, ConversationLog.timestamp).all()
        
        # Group logs by case_id
        conversations = {}
        for log_entry in logs:
            if log_entry.case_id not in conversations:
                conversations[log_entry.case_id] = []
            conversations[log_entry.case_id].append({
                'role': log_entry.role,
                'content': log_entry.content,
                'timestamp': log_entry.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            })
        
        # Sort conversations by the timestamp of the first message in each case, descending (most recent first)
        sorted_conversations = sorted(conversations.items(), 
                                      key=lambda item: datetime.strptime(item[1][0]['timestamp'], "%Y-%m-%d %H:%M:%S UTC") if item[1] else datetime.min, 
                                      reverse=True)
        
        return render_template('admin_live_chats.html', conversations=sorted_conversations)
    except Exception as e:
        logging.error(f"Error fetching live chats: {e}", exc_info=True)
        return f"Error fetching live chats: {e}", 500

@app.route('/get_cached_organisms', methods=['GET'])
def get_cached_organisms():
    """Returns a list of organisms that have pre-generated cases in the cache."""
    try:
        # It's okay to create a temporary agent just to access the cache.
        case_generator = CaseGeneratorRAGAgent()
        organisms = case_generator.get_cached_organisms()
        return jsonify(organisms)
    except Exception as e:
        logging.error(f"Error getting cached organisms: {e}", exc_info=True)
        return jsonify({"error": "Could not retrieve cached organisms"}), 500

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