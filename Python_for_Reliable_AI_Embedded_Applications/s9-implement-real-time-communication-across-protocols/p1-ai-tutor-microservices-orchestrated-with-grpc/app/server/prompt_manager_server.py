"""
gRPC Server - AI Tutor Prompt Manager
======================================

This microservice manages system prompts for the AI Tutor using gRPC protocol.
It provides prompts for different AI tasks (explain, personalize, tutor).

What is gRPC?
- gRPC = Google Remote Procedure Call
- High-performance RPC framework
- Uses binary protocol (Protocol Buffers) instead of JSON
- 10x faster than REST for service-to-service communication
- Perfect for microservices architecture

Why use gRPC for prompts?
- Centralized prompt management
- Fast communication between services
- Type-safe API (defined in .proto file)
- Easy to update prompts without changing code

How to use this server:
1. Generate Python code from .proto file:
   python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. prompts.proto
2. Run this server: python grpc_server.py
3. Server listens on port 50051
4. Main app can fetch prompts via gRPC
"""


from concurrent import futures
import logging
import grpc
from app.proto import prompts_pb2, prompts_pb2_grpc

# ============================================================================
# CONFIGURATION & SETUP
# ============================================================================

# 1. Setup logging to track gRPC server activity
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# SYSTEM PROMPTS DATABASE
# ============================================================================

# 2. System prompts that guide AI behavior for each task
# These can be updated without restarting the main API
PROMPTS = {
    "explain": """You are an expert AI tutor specializing in Agentic AI concepts.
Your role is to explain complex AI concepts clearly and concisely for beginners.
Use simple language, provide examples, and break down technical terms.""",

    "personalize": """You are a creative AI storyteller and educator.
Your role is to transform technical concepts into engaging stories and analogies.
Make learning fun by creating memorable, relatable examples that stick in the mind.
Keep your stories concise (4-5 sentences).""",

    "tutor": """You are a patient, supportive AI teacher.
Your role is to guide learners through concepts step-by-step.
Encourage questions, provide clear examples, and adapt explanations to the learner's level.""",
}

# ============================================================================
# GRPC SERVICE IMPLEMENTATION
# ============================================================================

class PromptManagerServicer(prompts_pb2_grpc.PromptManagerServicer):
    """
    gRPC Service Implementation for Prompt Management.
    
    This class implements the PromptManager service defined in prompts.proto.
    Think of this as the "backend logic" for our gRPC microservice.
    
    When a client (main API) requests a prompt, this class handles:
    1. Receives prompt_name from client
    2. Looks up prompt in database
    3. Returns prompt text to client
    """
    
    # Implement the GetPrompt RPC method
    def GetPrompt(self, request, context):
        """
        Handle GetPrompt RPC requests from clients.
        
        This is the main method that clients call to fetch prompts.
        It's defined in prompts.proto as:
            rpc GetPrompt(PromptRequest) returns (PromptResponse) {}
        
        Args:
            request: PromptRequest object containing prompt_name
            context: gRPC context (for error handling, metadata, etc.)
            
        Returns:
            PromptResponse object with prompt_text
        """
        # Extract prompt name from request
        topic = request.topic.strip() if request.topic else ""
        
        # Look up the prompt in our database
        prompt_text = PROMPTS.get(topic)
        
        if not prompt_text:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Prompt not found for topic: '{topic}'")
            return prompts_pb2.PromptResponse(prompt="")
        
        # Create and return the response
        return prompts_pb2.PromptResponse(prompt=prompt_text)

# ============================================================================
# SERVER STARTUP
# ============================================================================


def serve(port: int = 50051):
    """
    Start the gRPC server and keep it running.
    
    This function:
    1. Creates a gRPC server with thread pool
    2. Registers our PromptManager service
    3. Binds to port 50051
    4. Starts accepting requests
    5. Waits for termination (Ctrl+C)
    """
    # Step 1: Create a gRPC server with thread pool
    # max_workers=10 means it can handle 10 concurrent requests
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Step 2: Register our service implementation with the server
    prompts_pb2_grpc.add_PromptManagerServicer_to_server(
        PromptManagerServicer(), server
    )
    
    # Step 3: Bind to port 50051 (standard gRPC port)
    # [::]:50051 means listen on all network interfaces
    server.add_insecure_port(f"[::]:{port}")
    
    # Step 4: Start the server
    server.start()
    # Print startup information
    logger.info("=" * 60)
    logger.info("AI TUTOR GRPC SERVER STARTED")
    logger.info("=" * 60)
    logger.info("Server Configuration:")
    logger.info("  - Protocol: gRPC (binary, high-performance)")
    logger.info(f"  - Address: localhost:{port}")
    logger.info("  - Max Workers: 10 concurrent requests")
    logger.info("-" * 60)
    logger.info("Available Prompts:")
    for prompt_name in PROMPTS.keys():
        logger.info(f"   - {prompt_name}")
    logger.info("=" * 60)
    logger.info("Waiting for requests... (Press Ctrl+C to stop)")
    logger.info("=" * 60)
    # Step 5: Keep the server running until interrupted
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("\nShutting down Prompt Manager gRPC server...")
        server.stop(0)
        logger.info("Server stopped. Goodbye!")

if __name__ == '__main__':
    serve()
