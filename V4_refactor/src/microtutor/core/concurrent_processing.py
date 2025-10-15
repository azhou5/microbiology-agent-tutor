"""
Concurrent processing utilities for MicroTutor.

This module provides concurrent processing capabilities for operations
that can run in parallel, while keeping sequential operations sequential.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Tuple
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class ConcurrentProcessor:
    """Handles concurrent processing of independent operations."""
    
    def __init__(self):
        """Initialize concurrent processor."""
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.completed_tasks: Dict[str, Any] = {}
    
    async def process_concurrent_operations(
        self,
        operations: List[Tuple[str, Callable, Dict[str, Any]]],
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Process multiple operations concurrently.
        
        Args:
            operations: List of (name, coroutine_function, kwargs) tuples
            timeout: Optional timeout for all operations
            
        Returns:
            Dictionary mapping operation names to results
        """
        if not operations:
            return {}
        
        logger.info(f"Starting {len(operations)} concurrent operations")
        start_time = time.time()
        
        # Create tasks for all operations
        tasks = {}
        for name, coro_func, kwargs in operations:
            try:
                task = asyncio.create_task(coro_func(**kwargs))
                tasks[name] = task
                self.active_tasks[name] = task
            except Exception as e:
                logger.error(f"Failed to create task for {name}: {e}")
                self.completed_tasks[name] = {"error": str(e)}
        
        # Wait for all tasks to complete
        try:
            if timeout:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks.values(), return_exceptions=True),
                    timeout=timeout
                )
            else:
                results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            
            # Map results back to operation names
            operation_names = list(tasks.keys())
            for i, result in enumerate(results):
                name = operation_names[i]
                if isinstance(result, Exception):
                    self.completed_tasks[name] = {"error": str(result)}
                    logger.error(f"Operation {name} failed: {result}")
                else:
                    self.completed_tasks[name] = result
                    logger.debug(f"Operation {name} completed successfully")
            
        except asyncio.TimeoutError:
            logger.warning(f"Concurrent operations timed out after {timeout}s")
            # Cancel remaining tasks
            for task in tasks.values():
                if not task.done():
                    task.cancel()
        
        # Clean up active tasks
        for name in list(tasks.keys()):
            if name in self.active_tasks:
                del self.active_tasks[name]
        
        processing_time = time.time() - start_time
        logger.info(f"Concurrent operations completed in {processing_time:.3f}s")
        
        return self.completed_tasks.copy()
    
    async def process_with_fallback(
        self,
        primary_operations: List[Tuple[str, Callable, Dict[str, Any]]],
        fallback_operations: List[Tuple[str, Callable, Dict[str, Any]]],
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Process operations with fallback on failure.
        
        Args:
            primary_operations: Primary operations to try first
            fallback_operations: Fallback operations if primary fails
            timeout: Optional timeout
            
        Returns:
            Dictionary with results from successful operations
        """
        results = {}
        
        # Try primary operations first
        try:
            primary_results = await self.process_concurrent_operations(
                primary_operations, timeout
            )
            results.update(primary_results)
        except Exception as e:
            logger.warning(f"Primary operations failed: {e}")
        
        # Try fallback operations for any failed primary operations
        failed_operations = [
            op for op in fallback_operations 
            if op[0] not in results or "error" in results.get(op[0], {})
        ]
        
        if failed_operations:
            try:
                fallback_results = await self.process_concurrent_operations(
                    failed_operations, timeout
                )
                results.update(fallback_results)
            except Exception as e:
                logger.error(f"Fallback operations also failed: {e}")
        
        return results


# Global concurrent processor instance
_concurrent_processor: Optional[ConcurrentProcessor] = None


def get_concurrent_processor() -> ConcurrentProcessor:
    """Get the global concurrent processor instance."""
    global _concurrent_processor
    if _concurrent_processor is None:
        _concurrent_processor = ConcurrentProcessor()
    return _concurrent_processor


async def process_chat_concurrent(
    case_id: str,
    organism: str,
    user_message: str,
    background_service,
    tutor_service,
    context
) -> Dict[str, Any]:
    """Process chat with concurrent background operations.
    
    This function demonstrates how to process chat with concurrent
    background operations while keeping the main LLM flow sequential.
    
    Args:
        case_id: Case identifier
        organism: Organism being studied
        user_message: User's message
        background_service: Background service for async operations
        tutor_service: Tutor service for LLM processing
        context: Tutor context
        
    Returns:
        Dictionary with processing results
    """
    processor = get_concurrent_processor()
    
    # Define concurrent operations that can run in parallel
    async def log_user_message_async():
        return background_service.log_conversation_async(
            case_id=case_id,
            role="user", 
            content=user_message,
            metadata={"organism": organism}
        )
    
    async def collect_user_metrics_async():
        return background_service.collect_metrics_async(
            event_type="user_message",
            case_id=case_id,
            processing_time_ms=0.0,
            model=context.model_name,
            metadata={"organism": organism, "message_length": len(user_message)}
        )
    
    async def calculate_user_cost_async():
        return background_service.calculate_cost_async(
            model=context.model_name,
            prompt_tokens=int(len(user_message.split()) * 1.3),  # Rough estimate
            completion_tokens=0,
            case_id=case_id,
            request_type="user_message"
        )
    
    concurrent_operations = [
        ("log_user_message", log_user_message_async, {}),
        ("collect_user_metrics", collect_user_metrics_async, {}),
        ("calculate_user_cost", calculate_user_cost_async, {})
    ]
    
    # Start concurrent operations (non-blocking)
    concurrent_task = asyncio.create_task(
        processor.process_concurrent_operations(concurrent_operations)
    )
    
    # Main LLM processing (sequential - this is the bottleneck)
    start_time = time.time()
    
    try:
        # This is the sequential part that can't be parallelized
        response = await tutor_service.process_message(
            message=user_message,
            context=context,
            feedback_enabled=True,
            feedback_threshold=0.7
        )
        
        llm_processing_time = (time.time() - start_time) * 1000
        
        # More concurrent operations after LLM response
        async def log_assistant_response_async():
            return background_service.log_conversation_async(
                case_id=case_id,
                role="assistant",
                content=response.content,
                metadata={
                    "tools_used": response.tools_used,
                    "organism": organism,
                    "processing_time_ms": llm_processing_time
                }
            )
        
        async def collect_completion_metrics_async():
            return background_service.collect_metrics_async(
                event_type="chat_completion",
                case_id=case_id,
                processing_time_ms=llm_processing_time,
                model=context.model_name,
                metadata={
                    "organism": organism,
                    "tools_used": response.tools_used,
                    "response_length": len(response.content)
                }
            )
        
        async def calculate_response_cost_async():
            return background_service.calculate_cost_async(
                model=context.model_name,
                prompt_tokens=int(len(user_message.split()) * 1.3),
                completion_tokens=int(len(response.content.split()) * 1.3),
                case_id=case_id,
                request_type="chat_completion"
            )
        
        post_llm_operations = [
            ("log_assistant_response", log_assistant_response_async, {}),
            ("collect_completion_metrics", collect_completion_metrics_async, {}),
            ("calculate_response_cost", calculate_response_cost_async, {})
        ]
        
        # Process post-LLM operations concurrently
        post_llm_task = asyncio.create_task(
            processor.process_concurrent_operations(post_llm_operations)
        )
        
        # Wait for all concurrent operations to complete
        concurrent_results, post_llm_results = await asyncio.gather(
            concurrent_task,
            post_llm_task,
            return_exceptions=True
        )
        
        # Combine results
        all_results = {
            "llm_response": response,
            "processing_time_ms": llm_processing_time,
            "concurrent_operations": concurrent_results if not isinstance(concurrent_results, Exception) else {},
            "post_llm_operations": post_llm_results if not isinstance(post_llm_results, Exception) else {}
        }
        
        logger.info(f"Chat processing completed with concurrent operations in {llm_processing_time:.2f}ms")
        return all_results
        
    except Exception as e:
        logger.error(f"Chat processing failed: {e}")
        # Still wait for concurrent operations to complete
        try:
            await concurrent_task
        except:
            pass
        raise


async def process_start_case_concurrent(
    organism: str,
    case_id: str,
    background_service,
    tutor_service,
    model_name: str = "o3-mini",
    use_hpi_only: bool = False
) -> Dict[str, Any]:
    """Process case start with concurrent operations.
    
    Args:
        organism: Organism name
        case_id: Case identifier
        background_service: Background service
        tutor_service: Tutor service
        model_name: Model to use
        use_hpi_only: Whether to use HPI only
        
    Returns:
        Dictionary with processing results
    """
    processor = get_concurrent_processor()
    
    # Concurrent operations that can run in parallel
    concurrent_operations = [
        (
            "log_case_start",
            background_service.log_conversation_async,
            {
                "case_id": case_id,
                "role": "system",
                "content": f"Case started: {organism}",
                "metadata": {"organism": organism, "model": model_name}
            }
        ),
        (
            "collect_start_metrics",
            background_service.collect_metrics_async,
            {
                "event_type": "case_start",
                "case_id": case_id,
                "processing_time_ms": 0.0,
                "model": model_name,
                "metadata": {"organism": organism, "use_hpi_only": use_hpi_only}
            }
        )
    ]
    
    # Start concurrent operations
    concurrent_task = asyncio.create_task(
        processor.process_concurrent_operations(concurrent_operations)
    )
    
    # Main LLM processing (sequential)
    start_time = time.time()
    
    try:
        response = await tutor_service.start_case(
            organism=organism,
            case_id=case_id,
            model_name=model_name,
            use_hpi_only=use_hpi_only
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        # Post-LLM concurrent operations
        post_llm_operations = [
            (
                "log_assistant_response",
                background_service.log_conversation_async,
                {
                    "case_id": case_id,
                    "role": "assistant",
                    "content": response.content,
                    "metadata": {
                        "tools_used": response.tools_used,
                        "organism": organism,
                        "processing_time_ms": processing_time
                    }
                }
            ),
            (
                "collect_completion_metrics",
                background_service.collect_metrics_async,
                {
                    "event_type": "case_start_completion",
                    "case_id": case_id,
                    "processing_time_ms": processing_time,
                    "model": model_name,
                    "metadata": {
                        "organism": organism,
                        "response_length": len(response.content)
                    }
                }
            )
        ]
        
        post_llm_task = asyncio.create_task(
            processor.process_concurrent_operations(post_llm_operations)
        )
        
        # Wait for all operations
        concurrent_results, post_llm_results = await asyncio.gather(
            concurrent_task,
            post_llm_task,
            return_exceptions=True
        )
        
        return {
            "llm_response": response,
            "processing_time_ms": processing_time,
            "concurrent_operations": concurrent_results if not isinstance(concurrent_results, Exception) else {},
            "post_llm_operations": post_llm_results if not isinstance(post_llm_results, Exception) else {}
        }
        
    except Exception as e:
        logger.error(f"Case start processing failed: {e}")
        try:
            await concurrent_task
        except:
            pass
        raise
