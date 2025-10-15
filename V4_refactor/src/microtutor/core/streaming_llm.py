"""
Streaming LLM interface for faster perceived performance.

This module provides streaming capabilities for LLM responses,
allowing users to see responses as they're generated rather than
waiting for the complete response.
"""

import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class StreamingChunk:
    """Represents a chunk of streaming response."""
    content: str
    is_final: bool = False
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class StreamingLLMClient:
    """Client for streaming LLM responses."""
    
    def __init__(self, model: str = None):
        """Initialize streaming LLM client.
        
        Args:
            model: Model name to use for streaming (defaults to config)
        """
        from microtutor.core.config_helper import config
        
        # Use config model if not provided
        if model is None:
            model = config.API_MODEL_NAME
        
        self.model = model
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize the underlying LLM client."""
        try:
            from microtutor.core.llm_router import get_llm_client
            self.client = get_llm_client()
            logger.info(f"Streaming LLM client initialized for model: {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize streaming LLM client: {e}")
            raise
    
    async def stream_chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[StreamingChunk, None]:
        """Stream chat completion response.
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            tools: Optional tools for function calling
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Yields:
            StreamingChunk objects with partial responses
        """
        try:
            # For now, simulate streaming by chunking the response
            # In production, this would use actual streaming APIs
            response = await self._get_complete_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tools=tools,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            # Simulate streaming by yielding chunks
            chunk_size = 50  # Characters per chunk
            for i in range(0, len(response), chunk_size):
                chunk_content = response[i:i + chunk_size]
                is_final = i + chunk_size >= len(response)
                
                chunk = StreamingChunk(
                    content=chunk_content,
                    is_final=is_final,
                    metadata={
                        "model": self.model,
                        "chunk_index": i // chunk_size,
                        "total_chunks": (len(response) + chunk_size - 1) // chunk_size
                    }
                )
                
                yield chunk
                
                # Small delay to simulate real streaming
                if not is_final:
                    await asyncio.sleep(0.05)  # 50ms delay between chunks
                    
        except Exception as e:
            logger.error(f"Error in streaming chat completion: {e}")
            # Yield error chunk
            error_chunk = StreamingChunk(
                content=f"Error: {str(e)}",
                is_final=True,
                metadata={"error": True}
            )
            yield error_chunk
    
    async def _get_complete_response(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7
    ) -> str:
        """Get complete response (fallback for non-streaming)."""
        try:
            from microtutor.core.llm_router import chat_complete
            return chat_complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=self.model,
                tools=tools
            )
        except Exception as e:
            logger.error(f"Error getting complete response: {e}")
            return f"Error generating response: {str(e)}"


class StreamingTutorService:
    """Tutor service with streaming capabilities."""
    
    def __init__(self, base_tutor_service):
        """Initialize streaming tutor service.
        
        Args:
            base_tutor_service: Base TutorService instance
        """
        self.base_service = base_tutor_service
        self.streaming_client = StreamingLLMClient()
    
    async def stream_start_case(
        self,
        organism: str,
        case_id: str,
        model_name: Optional[str] = None,
        use_hpi_only: bool = False
    ) -> AsyncGenerator[StreamingChunk, None]:
        """Stream case start response.
        
        Args:
            organism: The microorganism name
            case_id: Unique case identifier
            model_name: Optional LLM model to use
            use_hpi_only: If True, use shorter HPI version
            
        Yields:
            StreamingChunk objects with the case introduction
        """
        try:
            # Load case
            from microtutor.agents.case import get_case
            case_description = get_case(organism, use_hpi_only=use_hpi_only)
            if not case_description:
                error_chunk = StreamingChunk(
                    content=f"Error: Could not load case for organism: {organism}",
                    is_final=True,
                    metadata={"error": True}
                )
                yield error_chunk
                return
            
            # Build system message
            from microtutor.core.tutor_prompt import get_system_message_template
            system_message_template = get_system_message_template()
            system_message = system_message_template.format(
                case=case_description,
                Examples_of_Good_and_Bad_Responses=""
            )
            
            # Generate initial prompt
            initial_prompt = (
                "Welcome the student and introduce the case. "
                "Present the initial chief complaint and basic demographics."
            )
            
            # Stream the response
            async for chunk in self.streaming_client.stream_chat_completion(
                system_prompt=system_message,
                user_prompt=initial_prompt,
                tools=self.base_service.tool_schemas
            ):
                # Add metadata
                chunk.metadata = chunk.metadata or {}
                chunk.metadata.update({
                    "case_id": case_id,
                    "organism": organism,
                    "response_type": "start_case"
                })
                yield chunk
                
        except Exception as e:
            logger.error(f"Error in stream_start_case: {e}")
            error_chunk = StreamingChunk(
                content=f"Error starting case: {str(e)}",
                is_final=True,
                metadata={"error": True, "case_id": case_id}
            )
            yield error_chunk
    
    async def stream_process_message(
        self,
        message: str,
        context,
        feedback_enabled: Optional[bool] = None,
        feedback_threshold: Optional[float] = None
    ) -> AsyncGenerator[StreamingChunk, None]:
        """Stream message processing response.
        
        Args:
            message: User message
            context: TutorContext
            feedback_enabled: Whether feedback is enabled
            feedback_threshold: Feedback similarity threshold
            
        Yields:
            StreamingChunk objects with the tutor response
        """
        try:
            # Load case if needed
            if not context.case_description:
                from microtutor.agents.case import get_case
                context.case_description = get_case(context.organism)
                if not context.case_description:
                    error_chunk = StreamingChunk(
                        content=f"Error: Could not load case for organism: {context.organism}",
                        is_final=True,
                        metadata={"error": True}
                    )
                    yield error_chunk
                    return
            
            # Get feedback examples (async)
            enhanced_message = message
            if feedback_enabled and self.base_service.feedback_retriever:
                try:
                    try:
                        from microtutor.feedback import get_feedback_examples_for_tool
                    except ImportError:
                        def get_feedback_examples_for_tool(*args, **kwargs):
                            return ""
                    feedback_examples = get_feedback_examples_for_tool(
                        user_input=message,
                        conversation_history=context.conversation_history,
                        tool_name="tutor",
                        feedback_retriever=self.base_service.feedback_retriever,
                        include_feedback=True
                    )
                    if feedback_examples:
                        enhanced_message = f"{message}\n\n{feedback_examples}"
                except Exception as e:
                    logger.warning(f"Feedback processing failed: {e}")
            
            # Ensure system message is set
            if not context.conversation_history or context.conversation_history[0]["role"] != "system":
                from microtutor.core.tutor_prompt import get_system_message_template
                system_message_template = get_system_message_template()
                system_message = system_message_template.format(
                    case=context.case_description
                )
                context.conversation_history.insert(0, {"role": "system", "content": system_message})
            
            # Add user message
            context.conversation_history.append({"role": "user", "content": enhanced_message})
            
            # Stream the response
            system_msg = context.conversation_history[0]["content"]
            user_msg = context.conversation_history[-1]["content"]
            
            async for chunk in self.streaming_client.stream_chat_completion(
                system_prompt=system_msg,
                user_prompt=user_msg,
                tools=self.base_service.tool_schemas
            ):
                # Add metadata
                chunk.metadata = chunk.metadata or {}
                chunk.metadata.update({
                    "case_id": context.case_id,
                    "organism": context.organism,
                    "response_type": "process_message"
                })
                yield chunk
            
            # Add assistant response to context
            full_response = ""
            # Note: In a real implementation, you'd collect the full response
            # from the streaming chunks and add it to context
            
        except Exception as e:
            logger.error(f"Error in stream_process_message: {e}")
            error_chunk = StreamingChunk(
                content=f"Error processing message: {str(e)}",
                is_final=True,
                metadata={"error": True, "case_id": context.case_id}
            )
            yield error_chunk


def get_streaming_tutor_service(base_tutor_service) -> StreamingTutorService:
    """Get streaming tutor service wrapper.
    
    Args:
        base_tutor_service: Base TutorService instance
        
    Returns:
        StreamingTutorService instance
    """
    return StreamingTutorService(base_tutor_service)
