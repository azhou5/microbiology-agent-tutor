"""
Background task service for async processing of non-critical operations.

This service handles database logging, file logging, analytics, and other
operations that don't need to block the main LLM response.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import pytz
from dataclasses import dataclass
from enum import Enum
import json
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of background tasks."""
    DATABASE_LOG = "database_log"
    FILE_LOG = "file_log"
    FEEDBACK_PROCESSING = "feedback_processing"
    CASE_FEEDBACK_PROCESSING = "case_feedback_processing"
    ANALYTICS = "analytics"
    COST_CALCULATION = "cost_calculation"
    METRICS_COLLECTION = "metrics_collection"
    FAISS_INDEX_UPDATE = "faiss_index_update"


@dataclass
class BackgroundTask:
    """Represents a background task to be processed."""
    task_type: TaskType
    data: Dict[str, Any]
    priority: int = 0  # Higher number = higher priority
    created_at: datetime = None
    retry_count: int = 0
    max_retries: int = 10
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(pytz.timezone('America/New_York'))
    
    def __lt__(self, other):
        """Less than comparison for priority queue ordering."""
        if not isinstance(other, BackgroundTask):
            return NotImplemented
        # Higher priority first, then by creation time
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.created_at < other.created_at
    
    def __eq__(self, other):
        """Equality comparison."""
        if not isinstance(other, BackgroundTask):
            return NotImplemented
        return (self.task_type == other.task_type and 
                self.priority == other.priority and 
                self.created_at == other.created_at)


class BackgroundTaskService:
    """Service for processing background tasks asynchronously."""
    
    def __init__(self, max_workers: int = 4, queue_size: int = 1000):
        """Initialize the background task service.
        
        Args:
            max_workers: Maximum number of worker threads
            queue_size: Maximum queue size before dropping tasks
        """
        self.max_workers = max_workers
        self.queue_size = queue_size
        self.task_queue = queue.PriorityQueue(maxsize=queue_size)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running = False
        self.workers: List[threading.Thread] = []
        
        # Database connection pool for async operations
        self._db_engine = None
        self._db_pool_size = 5
        
        # FAISS re-indexing status tracking
        self._faiss_status = {
            "is_reindexing": False,
            "last_reindex_start": None,
            "last_reindex_complete": None,
            "last_reindex_duration": None,
            "reindex_count": 0,
            "last_error": None
        }
        self._faiss_status_lock = threading.Lock()
        
        logger.info(f"BackgroundTaskService initialized with {max_workers} workers")
    
    def start(self) -> None:
        """Start the background task service."""
        if self.running:
            logger.warning("BackgroundTaskService is already running")
            return
        
        self.running = True
        
        # Start worker threads
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"BackgroundWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Started {self.max_workers} background workers")
    
    def stop(self) -> None:
        """Stop the background task service."""
        if not self.running:
            return
        
        self.running = False
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=5.0)
        
        self.executor.shutdown(wait=True)
        logger.info("BackgroundTaskService stopped")
    
    def _worker_loop(self) -> None:
        """Main worker loop for processing tasks."""
        while self.running:
            try:
                # Get task from queue (blocking with timeout)
                priority, task = self.task_queue.get(timeout=1.0)
                
                try:
                    self._process_task(task)
                except Exception as e:
                    logger.error(f"Error processing task {task.task_type}: {e}")
                    self._handle_task_failure(task, e)
                finally:
                    self.task_queue.task_done()
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    def _process_task(self, task: BackgroundTask) -> None:
        """Process a single background task."""
        logger.debug(f"Processing {task.task_type} task")
        
        if task.task_type == TaskType.DATABASE_LOG:
            self._process_database_log(task.data)
        elif task.task_type == TaskType.FILE_LOG:
            self._process_file_log(task.data)
        elif task.task_type == TaskType.FEEDBACK_PROCESSING:
            self._process_feedback(task.data)
        elif task.task_type == TaskType.CASE_FEEDBACK_PROCESSING:
            self._process_case_feedback(task.data)
        elif task.task_type == TaskType.ANALYTICS:
            self._process_analytics(task.data)
        elif task.task_type == TaskType.COST_CALCULATION:
            self._process_cost_calculation(task.data)
        elif task.task_type == TaskType.METRICS_COLLECTION:
            self._process_metrics(task.data)
        elif task.task_type == TaskType.FAISS_INDEX_UPDATE:
            self._process_faiss_index_update(task.data)
        else:
            logger.warning(f"Unknown task type: {task.task_type}")
    
    def _handle_task_failure(self, task: BackgroundTask, error: Exception) -> None:
        """Handle task failure with retry logic."""
        task.retry_count += 1
        
        if task.retry_count <= task.max_retries:
            logger.warning(f"Retrying task {task.task_type} (attempt {task.retry_count})")
            # Re-queue with higher priority
            self.submit_task(task, priority=task.priority + 1)
        else:
            logger.error(f"Task {task.task_type} failed after {task.max_retries} retries: {error}")
    
    def submit_task(
        self, 
        task: BackgroundTask, 
        priority: Optional[int] = None
    ) -> bool:
        """Submit a task for background processing.
        
        Args:
            task: The task to process
            priority: Optional priority override
            
        Returns:
            True if task was queued, False if queue is full
        """
        if not self.running:
            logger.warning("BackgroundTaskService is not running")
            return False
        
        try:
            task_priority = priority if priority is not None else task.priority
            self.task_queue.put((task_priority, task), block=False)
            logger.debug(f"Queued {task.task_type} task with priority {task_priority}")
            return True
        except queue.Full:
            logger.warning(f"Task queue is full, dropping {task.task_type} task")
            return False
    
    def _process_database_log(self, data: Dict[str, Any]) -> None:
        """Process database logging task."""
        try:
            if self._db_engine is None:
                self._init_database_pool()
            
            if self._db_engine is None:
                logger.warning("Database not available, falling back to file logging")
                self._process_file_log(data)
                return
            
            with self._db_engine.connect() as conn:
                # Use raw SQL for better performance
                conn.execute(text("""
                    INSERT INTO conversation_logs (case_id, timestamp, role, content)
                    VALUES (:case_id, :timestamp, :role, :content)
                """), data)
                conn.commit()
                
        except Exception as e:
            logger.error(f"Database logging failed: {e}")
            # Fall back to file logging
            self._process_file_log(data)
    
    def _process_file_log(self, data: Dict[str, Any]) -> None:
        """Process file logging task."""
        try:
            # This would integrate with your existing file logging system
            from microtutor.core.logging_config import get_logger
            mt_logger = get_logger()
            
            # Log based on role
            if data.get('role') == 'user':
                mt_logger.log_conversation_turn(
                    data['case_id'],
                    'user',
                    data['content'],
                    metadata=data.get('metadata', {})
                )
            elif data.get('role') == 'assistant':
                mt_logger.log_conversation_turn(
                    data['case_id'],
                    'assistant',
                    data['content'],
                    metadata=data.get('metadata', {})
                )
            elif data.get('role') == 'feedback':
                mt_logger.log_feedback(
                    case_id=data['case_id'],
                    rating=data.get('rating', 0),
                    message=data.get('message', ''),
                    feedback_text=data.get('feedback_text', ''),
                    replacement_text=data.get('replacement_text', ''),
                    organism=data.get('organism', '')
                )
                
        except Exception as e:
            logger.error(f"File logging failed: {e}")
    
    def _process_feedback(self, data: Dict[str, Any]) -> None:
        """Process feedback analysis and storage."""
        try:
            logger.info(f"Processing feedback for case {data.get('case_id')}")
            
            if self._db_engine is None:
                self._init_database_pool()
            
            if self._db_engine is None:
                logger.warning("Database not available for feedback, falling back to file logging")
                self._process_file_log({**data, 'role': 'feedback'})
                return
            
            # Save feedback to database
            with self._db_engine.connect() as conn:
                # Insert into feedback table
                conn.execute(text("""
                    INSERT INTO feedback (
                        timestamp, organism, rating, rated_message, 
                        feedback_text, replacement_text, case_id
                    ) VALUES (
                        :timestamp, :organism, :rating, :message, 
                        :feedback_text, :replacement_text, :case_id
                    )
                """), {
                    'timestamp': data.get('timestamp', datetime.now(pytz.timezone('America/New_York'))),
                    'organism': data.get('organism', ''),
                    'rating': str(data.get('rating', '0')),
                    'message': data.get('message', ''),
                    'feedback_text': data.get('feedback_text', ''),
                    'replacement_text': data.get('replacement_text', ''),
                    'case_id': data.get('case_id', '')
                })
                conn.commit()
                
            logger.info(f"Feedback saved to database for case {data.get('case_id')}")
            
            # Trigger FAISS index update (low priority)
            self.update_faiss_indices_async(force_update=False)
            
        except Exception as e:
            logger.error(f"Feedback processing failed: {e}")
            # Fall back to file logging
            self._process_file_log({**data, 'role': 'feedback'})
    
    def _process_case_feedback(self, data: Dict[str, Any]) -> None:
        """Process case feedback storage."""
        try:
            logger.info(f"Processing case feedback for case {data.get('case_id')}")
            
            if self._db_engine is None:
                self._init_database_pool()
            
            if self._db_engine is None:
                logger.warning("Database not available for case feedback, falling back to file logging")
                self._process_file_log({**data, 'role': 'case_feedback'})
                return
            
            # Save case feedback to database
            with self._db_engine.connect() as conn:
                # Insert into case_feedback table
                conn.execute(text("""
                    INSERT INTO case_feedback (
                        timestamp, organism, detail_rating, helpfulness_rating, 
                        accuracy_rating, comments, case_id
                    ) VALUES (
                        :timestamp, :organism, :detail_rating, :helpfulness_rating, 
                        :accuracy_rating, :comments, :case_id
                    )
                """), {
                    'timestamp': data.get('timestamp', datetime.now(pytz.timezone('America/New_York'))),
                    'organism': data.get('organism', ''),
                    'detail_rating': str(data.get('detail_rating', '0')),
                    'helpfulness_rating': str(data.get('helpfulness_rating', '0')),
                    'accuracy_rating': str(data.get('accuracy_rating', '0')),
                    'comments': data.get('comments', ''),
                    'case_id': data.get('case_id', '')
                })
                conn.commit()
                
            logger.info(f"Case feedback saved to database for case {data.get('case_id')}")
            
            # Trigger FAISS index update (low priority)
            self.update_faiss_indices_async(force_update=False)
            
        except Exception as e:
            logger.error(f"Case feedback processing failed: {e}")
            # Fall back to file logging
            self._process_file_log({**data, 'role': 'case_feedback'})
    
    def _process_analytics(self, data: Dict[str, Any]) -> None:
        """Process analytics and metrics collection."""
        try:
            logger.info(f"Processing analytics: {data.get('event_type')}")
            # Add your analytics processing logic here
            
        except Exception as e:
            logger.error(f"Analytics processing failed: {e}")
    
    def _process_cost_calculation(self, data: Dict[str, Any]) -> None:
        """Process cost calculation for LLM usage."""
        try:
            from microtutor.services.cost_service import calculate_cost_async
            
            cost_info = calculate_cost_async(
                model=data.get('model', 'unknown'),
                prompt_tokens=data.get('prompt_tokens', 0),
                completion_tokens=data.get('completion_tokens', 0),
                case_id=data.get('case_id'),
                request_type=data.get('request_type')
            )
            
            logger.info(f"Cost calculated: {cost_info.model} - ${cost_info.cost_usd:.6f}")
            
        except Exception as e:
            logger.error(f"Cost calculation failed: {e}")
    
    def _process_metrics(self, data: Dict[str, Any]) -> None:
        """Process metrics collection."""
        try:
            logger.info(f"Collecting metrics: {data.get('metric_type')}")
            # Add your metrics collection logic here
            
        except Exception as e:
            logger.error(f"Metrics collection failed: {e}")
    
    def _process_faiss_index_update(self, data: Dict[str, Any]) -> None:
        """Process FAISS index update."""
        start_time = datetime.now(pytz.timezone('America/New_York'))
        
        # Update status to indicate re-indexing has started
        with self._faiss_status_lock:
            self._faiss_status.update({
                "is_reindexing": True,
                "last_reindex_start": start_time,
                "last_error": None
            })
        
        try:
            logger.info("Updating FAISS indices from database feedback...")
            
            try:
                from microtutor.feedback.auto_faiss_generator import get_auto_faiss_generator
            except ImportError:
                def get_auto_faiss_generator(*args, **kwargs):
                    return None
            
            generator = get_auto_faiss_generator()
            force_update = data.get('force_update', False)
            
            result = generator.generate_indices(force_update=force_update)
            
            end_time = datetime.now(pytz.timezone('America/New_York'))
            duration = (end_time - start_time).total_seconds()
            
            # Update status based on result
            with self._faiss_status_lock:
                if result['status'] == 'success':
                    self._faiss_status.update({
                        "is_reindexing": False,
                        "last_reindex_complete": end_time,
                        "last_reindex_duration": duration,
                        "reindex_count": self._faiss_status["reindex_count"] + 1,
                        "last_error": None
                    })
                    logger.info(f"Successfully updated FAISS indices: {result['metadata']}")
                elif result['status'] == 'skipped':
                    self._faiss_status.update({
                        "is_reindexing": False,
                        "last_reindex_complete": end_time,
                        "last_reindex_duration": duration,
                        "last_error": None
                    })
                    logger.info(f"FAISS index update skipped: {result['reason']}")
                else:
                    self._faiss_status.update({
                        "is_reindexing": False,
                        "last_error": result['reason']
                    })
                    logger.error(f"FAISS index update failed: {result['reason']}")
                
        except Exception as e:
            end_time = datetime.now(pytz.timezone('America/New_York'))
            with self._faiss_status_lock:
                self._faiss_status.update({
                    "is_reindexing": False,
                    "last_error": str(e)
                })
            logger.error(f"FAISS index update failed: {e}")
    
    def _init_database_pool(self) -> None:
        """Initialize database connection pool."""
        try:
            from config.config import config
            database_url = getattr(config, 'database_url', None)
            
            if database_url:
                # Add SSL parameter to the URL for Render PostgreSQL
                db_url_with_ssl = database_url + "?sslmode=require"
                self._db_engine = create_engine(
                    db_url_with_ssl,
                    pool_size=self._db_pool_size,
                    max_overflow=10,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                )
                logger.info("Database pool initialized with SSL")
            else:
                logger.warning("No database URL configured")
                
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
    
    # Convenience methods for common tasks
    def log_conversation_async(
        self, 
        case_id: str, 
        role: str, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Log conversation asynchronously."""
        task = BackgroundTask(
            task_type=TaskType.DATABASE_LOG,
            data={
                'case_id': case_id,
                'role': role,
                'content': content,
                'timestamp': datetime.now(pytz.timezone('America/New_York')),
                'metadata': metadata or {}
            },
            priority=1
        )
        return self.submit_task(task)
    
    def log_feedback_async(
        self,
        case_id: str,
        rating: int,
        message: str,
        feedback_text: str = "",
        replacement_text: str = "",
        organism: str = ""
    ) -> bool:
        """Log feedback asynchronously."""
        task = BackgroundTask(
            task_type=TaskType.FEEDBACK_PROCESSING,
            data={
                'case_id': case_id,
                'rating': rating,
                'message': message,
                'feedback_text': feedback_text,
                'replacement_text': replacement_text,
                'organism': organism,
                'timestamp': datetime.now(pytz.timezone('America/New_York'))
            },
            priority=2
        )
        return self.submit_task(task)
    
    def log_case_feedback_async(
        self,
        case_id: str,
        detail_rating: int,
        helpfulness_rating: int,
        accuracy_rating: int,
        comments: str = "",
        organism: str = ""
    ) -> bool:
        """Log case feedback asynchronously."""
        task = BackgroundTask(
            task_type=TaskType.CASE_FEEDBACK_PROCESSING,
            data={
                'case_id': case_id,
                'detail_rating': detail_rating,
                'helpfulness_rating': helpfulness_rating,
                'accuracy_rating': accuracy_rating,
                'comments': comments,
                'organism': organism,
                'timestamp': datetime.now(pytz.timezone('America/New_York'))
            },
            priority=2
        )
        return self.submit_task(task)
    
    def update_faiss_indices_async(self, force_update: bool = False) -> bool:
        """Update FAISS indices asynchronously."""
        task = BackgroundTask(
            task_type=TaskType.FAISS_INDEX_UPDATE,
            data={
                'force_update': force_update,
                'timestamp': datetime.now(pytz.timezone('America/New_York'))
            },
            priority=1  # Lower priority than feedback processing
        )
        return self.submit_task(task)
    
    def collect_metrics_async(
        self,
        event_type: str,
        case_id: str,
        processing_time_ms: float,
        model: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Collect metrics asynchronously."""
        task = BackgroundTask(
            task_type=TaskType.METRICS_COLLECTION,
            data={
                'event_type': event_type,
                'case_id': case_id,
                'processing_time_ms': processing_time_ms,
                'model': model,
                'timestamp': datetime.now(pytz.timezone('America/New_York')),
                'metadata': metadata or {}
            },
            priority=0
        )
        return self.submit_task(task)
    
    def calculate_cost_async(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        case_id: Optional[str] = None,
        request_type: Optional[str] = None
    ) -> bool:
        """Calculate cost asynchronously."""
        task = BackgroundTask(
            task_type=TaskType.COST_CALCULATION,
            data={
                'model': model,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'case_id': case_id,
                'request_type': request_type,
                'timestamp': datetime.now(pytz.timezone('America/New_York'))
            },
            priority=1
        )
        return self.submit_task(task)
    
    def get_faiss_status(self) -> Dict[str, Any]:
        """Get current FAISS re-indexing status.
        
        Returns:
            Dictionary containing FAISS status information
        """
        with self._faiss_status_lock:
            status = self._faiss_status.copy()
            
            # Format timestamps for frontend
            if status["last_reindex_start"]:
                status["last_reindex_start"] = status["last_reindex_start"].isoformat()
            if status["last_reindex_complete"]:
                status["last_reindex_complete"] = status["last_reindex_complete"].isoformat()
            
            # Calculate duration if currently re-indexing
            if status["is_reindexing"] and status["last_reindex_start"]:
                start_time = datetime.fromisoformat(status["last_reindex_start"].replace('Z', '+00:00'))
                current_time = datetime.now(pytz.timezone('America/New_York'))
                status["current_duration"] = (current_time - start_time).total_seconds()
            else:
                status["current_duration"] = None
                
            return status


# Global background service instance
_background_service: Optional[BackgroundTaskService] = None


def get_background_service() -> BackgroundTaskService:
    """Get the global background service instance."""
    global _background_service
    if _background_service is None:
        _background_service = BackgroundTaskService()
        _background_service.start()
    return _background_service


def shutdown_background_service() -> None:
    """Shutdown the global background service."""
    global _background_service
    if _background_service is not None:
        _background_service.stop()
        _background_service = None
