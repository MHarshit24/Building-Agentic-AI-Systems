"""
Ollama gRPC Service - Minimal Implementation
============================================
Wraps Ollama HTTP API and exposes it via gRPC for microservices communication.
"""

from concurrent import futures
import logging
import grpc
import requests
from app.proto import ollama_service_pb2
from app.proto import ollama_service_pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OllamaServiceServicer(ollama_service_pb2_grpc.OllamaServiceServicer):
    """Ollama gRPC Service Implementation."""
    def __init__(self, ollama_url="http://localhost:11434", default_model="phi3:mini"):
        self.ollama_url = ollama_url
        self.default_model = default_model

    # Implement the GenerateExplanation RPC method    
    def GenerateExplanation(self, request, context):
        """Generate explanation using Ollama."""
        # Use the requested model if provided; otherwise use the server's default
        model = request.model or self.default_model

        try:
            url = f"{self.ollama_url}/api/generate"
            payload = {
                "model": model,
                "prompt": request.prompt,
                "stream": False,
            }

            response = requests.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            explanation = data.get("response", "")

            # return the response
            return ollama_service_pb2.OllamaResponse(
                model=model,
                explanation=explanation,
                success=True,
                error_message="",
            )

        # Handle exceptions and return failure response
        except Exception as e:
            logger.error(f"Ollama error: {str(e)}")
            return ollama_service_pb2.OllamaResponse(
                model=model,
                explanation="",
                success=False,
                error_message=str(e),
            )
 
def serve(port=50052):
    """Start the Ollama gRPC server."""
    # Step 1: Create a gRPC server with thread pool
    # max_workers=10 means it can handle 10 concurrent requests
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
  
    # Step 2: Register our service implementation with the server
    ollama_service_pb2_grpc.add_OllamaServiceServicer_to_server(
        OllamaServiceServicer(), server
    )
    
    # Step 3: Bind to port 50052
    # [::]:50052 means listen on all network interfaces
    server.add_insecure_port(f'[::]:{port}')
   
    
    # Step 4: Start the server
    server.start()
    
    logger.info("=" * 60)
    logger.info("OLLAMA GRPC SERVICE STARTED")
    logger.info("=" * 60)
    logger.info(f"  Address: localhost:{port}")
    logger.info(f"  Ollama Backend: http://localhost:11434")
    logger.info("=" * 60)
    logger.info("Press Ctrl+C to stop")
    
    # Step 5: Keep the server running until interrupted
    # Step 5: Keep the server running until interrupted
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("\nShutting down Ollama gRPC server...")
        server.stop(0)
        logger.info("Server stopped. Goodbye!")

if __name__ == '__main__':
    serve()

