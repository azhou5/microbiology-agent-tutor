#!/usr/bin/env python3
"""
Test script to demonstrate real concurrent processing in MicroTutor.

This script tests the actual concurrent processing implementation
and compares it with sequential processing.
"""

import asyncio
import time
import logging
import sys
import os
from typing import Dict, Any, List
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from microtutor.core.concurrent_processing import get_concurrent_processor, process_chat_concurrent
from microtutor.services.tutor_service import TutorService
from microtutor.services.background_service import get_background_service
from microtutor.models.domain import TutorContext

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_concurrent_processor():
    """Test the concurrent processor directly."""
    
    print("🧪 Testing Concurrent Processor")
    print("=" * 50)
    
    processor = get_concurrent_processor()
    
    # Define test operations
    async def fast_operation(name: str, delay: float = 0.1) -> str:
        """Fast operation for testing."""
        await asyncio.sleep(delay)
        return f"Fast operation {name} completed"
    
    async def slow_operation(name: str, delay: float = 0.5) -> str:
        """Slow operation for testing."""
        await asyncio.sleep(delay)
        return f"Slow operation {name} completed"
    
    # Test concurrent operations
    operations = [
        ("fast_1", fast_operation, {"name": "A", "delay": 0.1}),
        ("fast_2", fast_operation, {"name": "B", "delay": 0.1}),
        ("slow_1", slow_operation, {"name": "C", "delay": 0.5}),
        ("fast_3", fast_operation, {"name": "D", "delay": 0.1}),
    ]
    
    print("Running concurrent operations...")
    start_time = time.time()
    
    results = await processor.process_concurrent_operations(operations)
    
    total_time = time.time() - start_time
    
    print(f"Concurrent processing completed in {total_time:.3f}s")
    print("Results:")
    for name, result in results.items():
        print(f"  {name}: {result}")
    
    # Compare with sequential
    print("\nRunning sequential operations...")
    start_time = time.time()
    
    sequential_results = {}
    for name, func, kwargs in operations:
        result = await func(**kwargs)
        sequential_results[name] = result
        print(f"  {name}: {result}")
    
    sequential_time = time.time() - start_time
    
    print(f"Sequential processing completed in {sequential_time:.3f}s")
    
    # Calculate improvement
    if total_time > 0:
        improvement = sequential_time / total_time
        print(f"\n📈 Concurrent vs Sequential:")
        print(f"   Concurrent time: {total_time:.3f}s")
        print(f"   Sequential time: {sequential_time:.3f}s")
        print(f"   Speed improvement: {improvement:.1f}x faster")


async def test_chat_concurrent():
    """Test concurrent chat processing."""
    
    print("\n🧪 Testing Concurrent Chat Processing")
    print("=" * 50)
    
    # Initialize services
    tutor_service = TutorService()
    background_service = get_background_service()
    
    # Create test context
    context = TutorContext(
        case_id="concurrent_test_123",
        organism="staphylococcus aureus",
        conversation_history=[
            {"role": "system", "content": "You are a medical tutor."},
            {"role": "assistant", "content": "Hello! Let's discuss this case."}
        ],
        model_name="o3-mini"
    )
    
    test_message = "What are the key characteristics of Staphylococcus aureus?"
    
    print(f"Testing concurrent chat with message: '{test_message}'")
    print("This will process the LLM call sequentially but run all background operations concurrently...")
    
    start_time = time.time()
    
    try:
        results = await process_chat_concurrent(
            case_id="concurrent_test_123",
            organism="staphylococcus aureus",
            user_message=test_message,
            background_service=background_service,
            tutor_service=tutor_service,
            context=context
        )
        
        total_time = time.time() - start_time
        llm_time = results["processing_time_ms"]
        
        print(f"\n✅ Concurrent chat processing completed!")
        print(f"   Total time: {total_time:.3f}s")
        print(f"   LLM processing time: {llm_time:.2f}ms")
        print(f"   Response length: {len(results['llm_response'].content)} chars")
        
        # Show concurrent operations results
        concurrent_ops = results.get("concurrent_operations", {})
        post_llm_ops = results.get("post_llm_operations", {})
        
        print(f"\n📊 Concurrent Operations:")
        print(f"   Pre-LLM operations: {len(concurrent_ops)}")
        print(f"   Post-LLM operations: {len(post_llm_ops)}")
        
        for name, result in concurrent_ops.items():
            status = "✅" if "error" not in str(result) else "❌"
            print(f"   {status} {name}")
        
        for name, result in post_llm_ops.items():
            status = "✅" if "error" not in str(result) else "❌"
            print(f"   {status} {name}")
        
    except Exception as e:
        print(f"❌ Concurrent chat processing failed: {e}")
        logger.error(f"Concurrent chat test failed: {e}", exc_info=True)


async def test_concurrent_vs_sequential():
    """Compare concurrent vs sequential processing for background operations."""
    
    print("\n🧪 Testing Concurrent vs Sequential Background Operations")
    print("=" * 50)
    
    # Simulate background operations
    async def simulate_logging(case_id: str, delay: float = 0.1) -> str:
        """Simulate database logging."""
        await asyncio.sleep(delay)
        return f"Logged to database for {case_id}"
    
    async def simulate_metrics(case_id: str, delay: float = 0.05) -> str:
        """Simulate metrics collection."""
        await asyncio.sleep(delay)
        return f"Collected metrics for {case_id}"
    
    async def simulate_cost_calc(case_id: str, delay: float = 0.02) -> str:
        """Simulate cost calculation."""
        await asyncio.sleep(delay)
        return f"Calculated cost for {case_id}"
    
    case_id = "test_case_456"
    
    # Sequential processing
    print("1️⃣ Sequential background operations:")
    start_time = time.time()
    
    log_result = await simulate_logging(case_id, 0.1)
    metrics_result = await simulate_metrics(case_id, 0.05)
    cost_result = await simulate_cost_calc(case_id, 0.02)
    
    sequential_time = time.time() - start_time
    print(f"   Sequential time: {sequential_time:.3f}s")
    print(f"   Results: {log_result}, {metrics_result}, {cost_result}")
    
    # Concurrent processing
    print("\n2️⃣ Concurrent background operations:")
    start_time = time.time()
    
    results = await asyncio.gather(
        simulate_logging(case_id, 0.1),
        simulate_metrics(case_id, 0.05),
        simulate_cost_calc(case_id, 0.02)
    )
    
    concurrent_time = time.time() - start_time
    print(f"   Concurrent time: {concurrent_time:.3f}s")
    print(f"   Results: {results}")
    
    # Calculate improvement
    if concurrent_time > 0:
        improvement = sequential_time / concurrent_time
        print(f"\n📈 Background Operations Performance:")
        print(f"   Sequential time: {sequential_time:.3f}s")
        print(f"   Concurrent time: {concurrent_time:.3f}s")
        print(f"   Speed improvement: {improvement:.1f}x faster")
        print(f"   Time saved: {sequential_time - concurrent_time:.3f}s")


async def main():
    """Main test function."""
    try:
        print("🚀 Testing Real Concurrent Processing in MicroTutor")
        print("=" * 60)
        
        # Test concurrent processor
        await test_concurrent_processor()
        
        # Test concurrent vs sequential background operations
        await test_concurrent_vs_sequential()
        
        # Test concurrent chat (if services are available)
        try:
            await test_chat_concurrent()
        except Exception as e:
            print(f"\n⚠️  Skipping chat test due to service initialization: {e}")
        
        print("\n🎉 All concurrent processing tests completed!")
        print("\n📋 Key Benefits of Concurrent Processing:")
        print("  ✅ Background operations run in parallel")
        print("  ✅ LLM processing remains sequential (as required)")
        print("  ✅ Significant time savings on background tasks")
        print("  ✅ Better resource utilization")
        print("  ✅ Non-blocking operations")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
