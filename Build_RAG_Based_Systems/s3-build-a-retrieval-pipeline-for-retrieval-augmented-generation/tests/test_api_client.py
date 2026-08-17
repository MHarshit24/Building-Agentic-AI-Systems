"""
AutoMind RAG API - Test Client

Example Python client demonstrating how to interact with the RAG API.
"""

import pytest
import requests
from typing import Dict, Any
import socket


class AutoMindRAGClient:
    """Client for interacting with AutoMind RAG API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize the API client
        
        Args:
            base_url: Base URL of the API server
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check API health status
        
        Returns:
            Health check response
        """
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get API metrics and statistics
        
        Returns:
            Metrics response
        """
        response = self.session.get(f"{self.base_url}/metrics")
        response.raise_for_status()
        return response.json()
    
    def query(
        self,
        question: str,
        top_k: int = None,
        include_sources: bool = True
    ) -> Dict[str, Any]:
        """
        Execute RAG query with full pipeline
        
        Args:
            question: User question
            top_k: Number of chunks to retrieve (optional)
            include_sources: Include source documents in response
            
        Returns:
            Query response with answer and sources
        """
        payload = {
            "question": question,
            "include_sources": include_sources
        }
        
        if top_k is not None:
            payload["top_k"] = top_k
        
        response = self.session.post(
            f"{self.base_url}/query",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def retrieve(self, query: str, top_k: int = None) -> Dict[str, Any]:
        """
        Retrieve relevant chunks without LLM generation
        
        Args:
            query: Search query
            top_k: Number of chunks to retrieve (optional)
            
        Returns:
            Retrieval response with chunks
        """
        payload = {"query": query}
        
        if top_k is not None:
            payload["top_k"] = top_k
        
        response = self.session.post(
            f"{self.base_url}/retrieve",
            json=payload
        )
        response.raise_for_status()
        return response.json()


def print_separator(char="=", length=80):
    """Print a separator line"""
    print(char * length)


def is_server_running(host="localhost", port=8000):
    """Check if the API server is running"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


@pytest.fixture
def client():
    """Create a test client instance"""
    return AutoMindRAGClient(base_url="http://localhost:8000")


# Skip all API client tests if server is not running
pytestmark = pytest.mark.skipif(
    not is_server_running(),
    reason="API server is not running on localhost:8000"
)


def test_health_check(client: AutoMindRAGClient):
    """Test health check endpoint"""
    result = client.health_check()
    
    # Assertions
    assert 'status' in result
    assert 'database_connected' in result
    assert 'embedding_model_loaded' in result
    assert 'llm_loaded' in result
    assert 'timestamp' in result
    assert result['status'] in ['healthy', 'degraded']


def test_metrics(client: AutoMindRAGClient):
    """Test metrics endpoint"""
    result = client.get_metrics()
    
    # Assertions
    assert 'total_queries' in result
    assert 'successful_queries' in result
    assert 'failed_queries' in result
    assert 'average_chunks_retrieved' in result
    assert 'uptime_seconds' in result
    assert isinstance(result['total_queries'], int)
    assert isinstance(result['successful_queries'], int)
    assert isinstance(result['failed_queries'], int)
    assert result['uptime_seconds'] >= 0


def test_retrieval(client: AutoMindRAGClient):
    """Test retrieval endpoint"""
    query = "brake system maintenance"
    top_k = 3
    
    result = client.retrieve(query, top_k=top_k)
    
    # Assertions
    assert 'query' in result
    assert 'chunks' in result
    assert 'count' in result
    assert 'timestamp' in result
    assert result['query'] == query
    assert isinstance(result['chunks'], list)
    assert result['count'] == len(result['chunks'])
    assert result['count'] <= top_k
    
    # If chunks are returned, verify structure
    if result['chunks']:
        chunk = result['chunks'][0]
        assert 'source' in chunk
        assert 'chunk_id' in chunk
        assert 'content' in chunk


def test_rag_query(client: AutoMindRAGClient):
    """Test full RAG query endpoint"""
    question = "What are the benefits of EV Model?"
    
    result = client.query(question, top_k=5, include_sources=True)
    
    # Assertions
    assert 'question' in result
    assert 'answer' in result
    assert 'sources' in result
    assert 'metadata' in result
    assert 'timestamp' in result
    assert result['question'] == question
    assert isinstance(result['answer'], str)
    assert len(result['answer']) > 0
    assert isinstance(result['sources'], list)
    assert isinstance(result['metadata'], dict)
    
    # Verify metadata structure
    assert 'chunks_retrieved' in result['metadata']
    assert 'model' in result['metadata']
    assert 'has_sources' in result['metadata']


def test_error_handling(client: AutoMindRAGClient):
    """Test error handling with invalid requests"""
    # Test 1: Empty question should be rejected
    with pytest.raises(requests.exceptions.HTTPError) as exc_info:
        client.query("")
    assert exc_info.value.response.status_code in [400, 422]
    
    # Test 2: Very short question (2 chars) should be rejected
    with pytest.raises(requests.exceptions.HTTPError) as exc_info:
        client.query("ab")
    assert exc_info.value.response.status_code in [400, 422]
    
    # Test 3: Invalid top_k (too high) should be rejected
    with pytest.raises(requests.exceptions.HTTPError) as exc_info:
        client.query("test question", top_k=100)
    assert exc_info.value.response.status_code in [400, 422]


def run_comprehensive_tests():
    """Run all API tests"""
    print("\n" + "=" * 80)
    print("🚗 AutoMind RAG API - Comprehensive Test Suite")
    print("=" * 80)
    
    # Initialize client
    client = AutoMindRAGClient(base_url="http://localhost:8000")
    
    # Run tests
    test_health_check(client)
    test_metrics(client)
    test_retrieval(client)
    test_rag_query(client)
    test_error_handling(client)
    
    # Final metrics
    print("\n" + "=" * 80)
    print("📊 Final Metrics")
    print("=" * 80)
    test_metrics(client)
    
    print("\n" + "=" * 80)
    print("✅ Test Suite Complete!")
    print("=" * 80)


def interactive_mode():
    """Interactive query mode"""
    print("\n" + "=" * 80)
    print("💬 Interactive Mode - AutoMind RAG API Client")
    print("=" * 80)
    print("Type your questions (or 'exit' to quit)\n")
    
    client = AutoMindRAGClient(base_url="http://localhost:8000")
    
    while True:
        try:
            question = input("❓ Your Question: ").strip()
            
            if question.lower() in ['exit', 'quit', 'q']:
                print("\n👋 Goodbye!")
                break
            
            if not question:
                continue
            
            print("\n🔍 Processing...")
            result = client.query(question, include_sources=True)
            
            print(f"\n💡 Answer:\n{result['answer']}\n")
            
            if result['sources']:
                print(f"📚 Sources: {len(result['sources'])} chunks retrieved")
                for i, source in enumerate(result['sources'][:2], 1):
                    print(f"  {i}. {source['source']}")
            
            print("\n" + "-" * 80 + "\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        interactive_mode()
    else:
        run_comprehensive_tests()
        
        # Offer interactive mode
        print("\n" + "=" * 80)
        response = input("\n💬 Enter interactive mode? (y/n): ").strip().lower()
        if response == 'y':
            interactive_mode()
