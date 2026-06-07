#!/usr/bin/env python3
"""
Test Script for Large Repository Handling

This script tests the batch processing functionality for large repositories.
Run this to verify that the large repo handling works correctly.

Usage:
    python test_large_repo.py
"""

import asyncio
import logging
from doc_generation_agent import doc_agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def create_mock_chunks(num_chunks: int = 1500):
    """Create mock chunks to simulate a large repository"""
    chunks = []
    
    for i in range(num_chunks):
        chunk = {
            "file_path": f"src/module_{i // 10}/file_{i}.py",
            "content": f"""
# File {i}
class Component{i}:
    def __init__(self):
        self.name = "Component {i}"
        self.id = {i}
    
    def process(self):
        '''Process data for component {i}'''
        result = self.id * 2
        return result
    
    def validate(self):
        '''Validate component {i}'''
        return self.id > 0

# Constants
MAX_VALUE = {i * 100}
MIN_VALUE = {i}
""",
            "type": "code",
            "chunk_id": f"chunk_{i}",
            "chunk_index": i
        }
        chunks.append(chunk)
    
    return chunks


async def test_small_repo():
    """Test with a small repository (should use single batch)"""
    logger.info("\n" + "="*80)
    logger.info("TEST 1: Small Repository (150 chunks)")
    logger.info("="*80)
    
    chunks = await create_mock_chunks(150)
    
    try:
        documentation = await doc_agent.generate_documentation(
            repo_id="test_small",
            repo_name="Small Test Repository",
            chunks=chunks,
            provider="azure_openai",
            model="gpt-4o"
        )
        
        logger.info("✅ Small repo test PASSED")
        logger.info(f"Documentation length: {len(documentation)} characters")
        return True
    except Exception as e:
        logger.error(f"❌ Small repo test FAILED: {e}")
        return False


async def test_large_repo():
    """Test with a large repository (should use batch processing)"""
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Large Repository (1544 chunks - like shopbook)")
    logger.info("="*80)
    
    chunks = await create_mock_chunks(1544)
    
    try:
        documentation = await doc_agent.generate_documentation(
            repo_id="test_large",
            repo_name="Large Test Repository (shopbook simulation)",
            chunks=chunks,
            provider="azure_openai",
            model="gpt-4o"
        )
        
        logger.info("✅ Large repo test PASSED")
        logger.info(f"Documentation length: {len(documentation)} characters")
        
        # Verify documentation contains key sections
        required_sections = [
            "Project Overview",
            "Architecture",
            "Setup",
            "Usage"
        ]
        
        missing_sections = []
        for section in required_sections:
            if section.lower() not in documentation.lower():
                missing_sections.append(section)
        
        if missing_sections:
            logger.warning(f"⚠️  Missing sections: {missing_sections}")
        else:
            logger.info("✅ All required sections present")
        
        return True
    except Exception as e:
        logger.error(f"❌ Large repo test FAILED: {e}")
        return False


async def test_token_estimation():
    """Test token estimation accuracy"""
    logger.info("\n" + "="*80)
    logger.info("TEST 3: Token Estimation")
    logger.info("="*80)
    
    test_text = "Hello world! " * 1000
    estimated = doc_agent._estimate_tokens(test_text)
    
    # For "Hello world! " (13 chars) * 1000 = 13000 chars
    # Estimated tokens: 13000 / 4 = 3250
    expected_range = (3000, 3500)
    
    if expected_range[0] <= estimated <= expected_range[1]:
        logger.info(f"✅ Token estimation test PASSED: {estimated} tokens")
        return True
    else:
        logger.error(f"❌ Token estimation test FAILED: {estimated} tokens (expected {expected_range})")
        return False


async def test_batch_creation():
    """Test chunk batching logic"""
    logger.info("\n" + "="*80)
    logger.info("TEST 4: Batch Creation")
    logger.info("="*80)
    
    chunks = await create_mock_chunks(1000)
    max_tokens = 80000
    
    batches = doc_agent._create_chunk_batches(chunks, max_tokens)
    
    logger.info(f"Created {len(batches)} batches from {len(chunks)} chunks")
    
    for i, batch in enumerate(batches, 1):
        logger.info(f"  Batch {i}: {len(batch)} chunks")
    
    # Verify all chunks are included
    total_chunks_in_batches = sum(len(batch) for batch in batches)
    
    if total_chunks_in_batches == len(chunks):
        logger.info("✅ Batch creation test PASSED: All chunks included")
        return True
    else:
        logger.error(f"❌ Batch creation test FAILED: {total_chunks_in_batches} != {len(chunks)}")
        return False


async def test_chat_sampling():
    """Test chat sampling for large repos"""
    logger.info("\n" + "="*80)
    logger.info("TEST 5: Chat Sampling for Large Repos")
    logger.info("="*80)
    
    chunks = await create_mock_chunks(2000)
    
    try:
        answer = await doc_agent.chat_about_repository(
            repo_id="test_large_chat",
            repo_name="Large Chat Test Repository",
            chunks=chunks,
            user_question="What is the main purpose of this repository?",
            provider="azure_openai",
            model="gpt-4o"
        )
        
        logger.info("✅ Chat sampling test PASSED")
        logger.info(f"Answer length: {len(answer)} characters")
        return True
    except Exception as e:
        logger.error(f"❌ Chat sampling test FAILED: {e}")
        return False


async def run_all_tests():
    """Run all tests"""
    logger.info("\n" + "#"*80)
    logger.info("# LARGE REPOSITORY HANDLING - TEST SUITE")
    logger.info("#"*80)
    
    tests = [
        ("Token Estimation", test_token_estimation),
        ("Batch Creation", test_batch_creation),
        ("Small Repository", test_small_repo),
        ("Large Repository (shopbook simulation)", test_large_repo),
        ("Chat Sampling", test_chat_sampling)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("="*80)
    logger.info(f"Results: {passed}/{total} tests passed")
    logger.info("="*80)
    
    if passed == total:
        logger.info("\n🎉 ALL TESTS PASSED! Large repository handling is working correctly.")
        return 0
    else:
        logger.error(f"\n❌ {total - passed} test(s) failed. Please check the logs above.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(run_all_tests())
        exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\nTests interrupted by user")
        exit(130)
    except Exception as e:
        logger.error(f"Test suite crashed: {e}")
        exit(1)

