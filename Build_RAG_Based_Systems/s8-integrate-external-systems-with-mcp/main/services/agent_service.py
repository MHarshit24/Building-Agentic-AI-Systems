import logging
import re
from typing import Dict, Any, Optional, List
from main.services.mcp_client import HuggingFaceMCPService
from main.services.agent_factory import create_agent
from main.tools.custom_tools import custom_inference_tool
from llama_index.core.workflow import Context
from main.routes.routes import SentimentLabel

logger = logging.getLogger(__name__)


class AgentService:
    """Service to manage agent lifecycle and execute product review sentiment analysis"""
    
    def __init__(self):
        self.agent = None
        self.tools = []
        self._initialized = False
        self._mcp_connected = False
        self._mcp_tool_names = []
    
    async def initialize(self):
        """
        Initialize MCP connection and agent.
        
        TODO: Implement the following steps:
        1. Check if already initialized (return early if so)
        2. Initialize MCP Service
        3. Load MCP tools
        4. Add custom inference tool
        5. Create agent with tools
        6. Set initialization flags
        7. Handle exceptions appropriately
        """
        # TODO: Step 1 - Check if already initialized
        # Hint: Check if self._initialized is True
        # If true, log "Agent already initialized" and return early
        if self._initialized:
            logger.info("Agent already initialized")
            return
        
        try:
            # TODO: Step 2 - Initialize MCP Service
            # Hint: Create an instance of HuggingFaceMCPService()
            # Store it in a variable named mcp_service
            mcp_service = HuggingFaceMCPService()
            
            # TODO: Step 3 - Load MCP tools
            # Hint: Call await mcp_service.load_tools(allowed_tools=None)
            # Store the result in self.tools
            # Log the number of tools loaded
            self.tools = await mcp_service.load_tools(allowed_tools=None)
            logger.info(f"Loaded {len(self.tools)} tools from MCP server")
            self._mcp_tool_names = [t.metadata.name for t in self.tools]
            logger.info(f"Available MCP tool names: {self._mcp_tool_names}")
            
            # TODO: Step 4 - Add custom inference tool
            # Hint: Append custom_inference_tool to self.tools list
            # Log that the hf_inference tool was added
            self.tools.append(custom_inference_tool)
            logger.info("Added hf_inference custom tool to tool list")
            
            # TODO: Step 5 - Create agent
            # Hint: Call create_agent(self.tools, verbose=False)
            # Store the result in self.agent
            self.agent = create_agent(self.tools, verbose=False)
            
            # TODO: Step 6 - Set initialization flags
            # Hint: Set self._initialized = True
            # Set self._mcp_connected = True
            # Log successful initialization
            self._initialized = True
            self._mcp_connected = True
            logger.info("Agent service initialized successfully")
        
        # TODO: Step 7 - Handle exceptions
        # Hint: Wrap steps 2-6 in a try-except block
        # On exception, log the error with traceback and re-raise
        except Exception as e:
            logger.error(f"Failed to initialize agent service: {e}", exc_info=True)
            raise
    
    def is_initialized(self) -> bool:
        """Check if agent is initialized"""
        return self._initialized and self.agent is not None
    
    def is_mcp_connected(self) -> bool:
        """Check if MCP server is connected"""
        return self._mcp_connected
    
    def get_tools_count(self) -> int:
        """Get number of loaded tools"""
        return len(self.tools)
    
    async def analyze_review_sentiment(
        self, 
        review_text: str, 
        product_id: Optional[str] = None,
        product_name: Optional[str] = None,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze sentiment of a product review using MCP workflow.
        
        Args:
            review_text: Product review text to analyze
            product_id: Optional product identifier
            product_name: Optional product name for context
            verbose: Show detailed agent reasoning
            
        Returns:
            Dict with sentiment, confidence, model_used, aspects, and success status
        
        TODO: Implement the following steps:
        1. Check if agent is initialized (raise RuntimeError if not)
        2. Build product context string from product_name and product_id
        3. Create a prompt for the agent with instructions
        4. Create a Context and run the agent with the prompt
        5. Parse the agent response using _parse_response helper method
        6. Handle success and error cases appropriately
        """
        # TODO: Step 1 - Check if agent is initialized
        # Hint: Use self.is_initialized() method
        # If not initialized, raise RuntimeError with message "Agent service not initialized"
        if not self.is_initialized():
            raise RuntimeError("Agent service not initialized")
        
        try:
            # TODO: Step 2 - Build product context
            # Hint: Create an empty string for product_context
            # If product_name is provided, append " for product: {product_name}" to product_context
            # If product_id is provided, append " (ID: {product_id})" to product_context
            product_context = ""
            if product_name:
                product_context += f" for product: {product_name}"
            if product_id:
                product_context += f" (ID: {product_id})"
            
            # TODO: Step 3 - Create prompt
            # Hint: Create a multi-line prompt string (f-string) that includes:
            # - The review text with product context
            # - Instructions for the agent to use 'model_search' MCP tool
            # - Instructions to use 'hf_inference' tool
            # - Instructions to extract aspects
            # - Format requirements for the response (Sentiment, Confidence, Model, Aspects)
            mcp_tool_names = self._mcp_tool_names
            prompt = f"""Analyze the sentiment of the following product review{product_context}:

Review: {review_text}

You have these tools available: {mcp_tool_names + ['hf_inference']}

Instructions:
1. Use one of the MCP tools (e.g. {mcp_tool_names[0] if mcp_tool_names else 'model_search'}) to find a suitable text-classification sentiment analysis model on Hugging Face Hub.
2. Use the 'hf_inference' tool with the discovered model ID and the review text to run inference.
3. Extract key aspects mentioned in the review (e.g. price, quality, delivery, packaging, customer service).
4. If a model fails, search for an alternative model and retry with hf_inference.

You MUST end your response in EXACTLY this format (no extra text after):
Sentiment: <POSITIVE|NEGATIVE|NEUTRAL|MIXED>
Confidence: <float between 0.0 and 1.0>
Model: <model_id used for inference>
Aspects: <comma-separated list of aspects, or None>
"""
            
            # TODO: Step 4 - Run the agent
            # Hint: Create a Context object with self.agent
            # Use self.agent.run(prompt, ctx=ctx) to get a handler
            # Await the handler to get the response
            # Convert the response to string and store in response_text
            ctx = Context(self.agent)
            handler = self.agent.run(
                prompt,
                ctx=ctx,
                max_iterations=50,
                early_stopping_method="generate"
            )
            response = await handler
            response_text = str(response)
            logger.info(f"Raw agent response:\n{response_text}")
            
            # TODO: Step 5 - Parse the response
            # Hint: Call self._parse_response() with response_text, review_text, product_id, product_name
            # Store the result in a variable
            result = self._parse_response(response_text, review_text, product_id, product_name)
            
            # TODO: Step 6 - Handle results
            # Hint: If result is truthy, set result["success"] = True and return it
            # If result is None/falsy, return a dictionary with:
            #   - sentiment: SentimentLabel.NEUTRAL
            #   - confidence: 0.0
            #   - model_used: "parsing_failed"
            #   - aspects: []
            #   - success: False
            #   - error: "Failed to parse agent response"
            #   - raw_response: response_text
            if result:
                result["success"] = True
                return result
            else:
                return {
                    "sentiment": SentimentLabel.NEUTRAL,
                    "confidence": 0.0,
                    "model_used": "parsing_failed",
                    "aspects": [],
                    "success": False,
                    "error": "Failed to parse agent response",
                    "raw_response": response_text
                }
        
        except Exception as e:
            logger.error(f"Error during sentiment analysis: {e}", exc_info=True)
            return {
                "sentiment": SentimentLabel.NEUTRAL,
                "confidence": 0.0,
                "model_used": "error",
                "aspects": [],
                "success": False,
                "error": str(e)
            }
    
    
    
    def _parse_response(self, response: str, review_text: str, product_id: Optional[str], product_name: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Parse agent response to extract sentiment, confidence, model, and aspects.
        
        Note: The underscore prefix (_) indicates this is a private/internal method.
        It's not part of the public API and should only be called from within this class.
        
        TODO: Implement the following steps:
        1. Use regex to extract sentiment, confidence, model, and aspects from the response
        2. Map sentiment string to SentimentLabel enum
        3. Parse confidence score and model name
        4. Parse aspects list from comma-separated string
        5. Return a dictionary with all extracted information
        """
        # TODO: Step 1 - Extract information using regex
        # Hint: Use re.search() to find patterns in the response string
        # Search for "Sentiment: [value]" pattern (case-insensitive)
        # Search for "Confidence: [value]" pattern (case-insensitive)
        # Search for "Model: [value]" pattern (case-insensitive)
        # Search for "Aspects: [value]" pattern (case-insensitive)
        # Store matches in variables (sentiment_match, confidence_match, model_match, aspects_match)
        try:
            # Strip markdown bold markers before matching so **Sentiment:** and Sentiment: both work
            clean_response = re.sub(r"\*+", "", response)
            
            sentiment_match = re.search(r"Sentiment:\s*(\S+)", clean_response, re.IGNORECASE)
            confidence_match = re.search(r"Confidence:\s*([0-9.]+)", clean_response, re.IGNORECASE)
            model_match = re.search(r"Model:\s*(\S+)", clean_response, re.IGNORECASE)
            aspects_match = re.search(r"Aspects:\s*(.+)", clean_response, re.IGNORECASE)
            
            # TODO: Step 2 - Map sentiment to enum
            # Hint: If sentiment_match found, extract the matched group and convert to uppercase
            # Try to create SentimentLabel enum from the string
            # If ValueError, map common variations:
            #   - "POS" or "GOOD" -> SentimentLabel.POSITIVE
            #   - "NEG" or "BAD" -> SentimentLabel.NEGATIVE
            #   - "MIX" -> SentimentLabel.MIXED
            #   - Otherwise -> SentimentLabel.NEUTRAL
            if sentiment_match:
                sentiment_str = sentiment_match.group(1).upper()
                try:
                    sentiment = SentimentLabel(sentiment_str)
                except ValueError:
                    if "POS" in sentiment_str or "GOOD" in sentiment_str:
                        sentiment = SentimentLabel.POSITIVE
                    elif "NEG" in sentiment_str or "BAD" in sentiment_str:
                        sentiment = SentimentLabel.NEGATIVE
                    elif "MIX" in sentiment_str:
                        sentiment = SentimentLabel.MIXED
                    else:
                        sentiment = SentimentLabel.NEUTRAL
            
            # TODO: Step 3 - Parse confidence and model
            # Hint: Extract confidence from confidence_match.group(1) and convert to float
            # Use 0.0 as default if confidence_match is None
            # Extract model from model_match.group(1) or use "unknown" as default
            confidence = float(confidence_match.group(1)) if confidence_match else 0.0
            model_used = model_match.group(1) if model_match else "unknown"
            
            # TODO: Step 4 - Parse aspects
            # Hint: If aspects_match found, extract the matched group and strip whitespace
            # Check if the string is not "none" (case-insensitive) and not empty
            # Split by comma, strip each aspect, and filter out empty strings
            # Store in a list
            aspects = []
            if aspects_match:
                aspects_str = aspects_match.group(1).strip()
                if aspects_str.lower() != "none" and aspects_str:
                    aspects = [a.strip() for a in aspects_str.split(",") if a.strip()]
            
            # TODO: Step 5 - Return dictionary
            # Hint: If sentiment_match was found, return a dictionary with:
            #   - sentiment: SentimentLabel enum value
            #   - confidence: float value
            #   - model_used: string value
            #   - aspects: list of strings
            #   - review_text: review_text parameter
            #   - product_id: product_id parameter
            #   - product_name: product_name parameter
            # If sentiment_match not found, return None
            # Wrap in try-except to handle errors and return None on exception
            if sentiment_match:
                return {
                    "sentiment": sentiment,
                    "confidence": confidence,
                    "model_used": model_used,
                    "aspects": aspects,
                    "review_text": review_text,
                    "product_id": product_id,
                    "product_name": product_name
                }
            
            # Fallback: keyword scan of raw response when structured format not found
            logger.warning("Structured format not found, attempting keyword fallback on raw response")
            response_upper = response.upper()
            if "NEGATIVE" in response_upper or "NEG" in response_upper:
                fallback_sentiment = SentimentLabel.NEGATIVE
            elif "POSITIVE" in response_upper or "POS" in response_upper:
                fallback_sentiment = SentimentLabel.POSITIVE
            elif "MIXED" in response_upper or "MIX" in response_upper:
                fallback_sentiment = SentimentLabel.MIXED
            else:
                fallback_sentiment = SentimentLabel.NEUTRAL
            
            # Try to extract model from response even without structured format
            model_fallback_match = re.search(r"([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)", response)
            fallback_model = model_fallback_match.group(1) if model_fallback_match else "unknown"
            
            logger.info(f"Keyword fallback result: sentiment={fallback_sentiment}, model={fallback_model}")
            return {
                "sentiment": fallback_sentiment,
                "confidence": 0.5,
                "model_used": fallback_model,
                "aspects": [],
                "review_text": review_text,
                "product_id": product_id,
                "product_name": product_name
            }
        
        except Exception as e:
            logger.error(f"Error parsing agent response: {e}", exc_info=True)
            return None