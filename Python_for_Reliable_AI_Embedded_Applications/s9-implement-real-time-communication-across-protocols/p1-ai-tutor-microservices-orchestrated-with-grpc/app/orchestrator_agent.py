"""Orchestrator Agent - Central Coordination Hub

Coordinates all AI services:
- Prompt Manager (gRPC)
- Ollama Service (gRPC)
- Gemini API (HTTP)
"""

import logging
from typing import Dict, Any, Optional

import grpc
from openai import OpenAI

from app.proto import prompts_pb2, prompts_pb2_grpc
from app.proto import ollama_service_pb2, ollama_service_pb2_grpc
logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Coordinates all AI services and manages workflow."""
    def __init__(
        self,
        prompt_manager_address: str = "localhost:50051",
        ollama_service_address: str = "localhost:50052",
        gemini_client: Optional[OpenAI] = None,
        gemini_model: str = "gemini-2.0-flash",
    ):
        """Initialize connections to all services."""
        logger.info("Initializing Orchestrator Agent")

        self.gemini_client = gemini_client
        self.gemini_model = gemini_model

        # For this assignment, we strictly use the phi3:mini Ollama model.
        self.ollama_model = "phi3:mini"

        # Setup gRPC connections
        self.prompt_manager_channel = grpc.insecure_channel(prompt_manager_address)
        self.prompt_manager_stub = prompts_pb2_grpc.PromptManagerStub(
            self.prompt_manager_channel
        )

        self.ollama_channel = grpc.insecure_channel(ollama_service_address)
        self.ollama_stub = ollama_service_pb2_grpc.OllamaServiceStub(self.ollama_channel)

        logger.info(f"Connected to Prompt Manager: {prompt_manager_address}")
        logger.info(f"Connected to Ollama Service: {ollama_service_address}")

    def get_system_prompt(self, prompt_type: str = "personalize") -> str:
        """Fetch system prompt from Prompt Manager."""
        try:
            request = prompts_pb2.PromptRequest(topic=prompt_type)
            response = self.prompt_manager_stub.GetPrompt(request, timeout=5)
            return response.prompt or ""
        except grpc.RpcError as e:
            logger.error(
                "Prompt Manager gRPC error: %s - %s",
                e.code().name if hasattr(e, "code") else "UNKNOWN",
                e.details() if hasattr(e, "details") else str(e),
            )
            return ""
        except Exception as e:
            logger.error("Prompt Manager error: %s", e)
            return ""
    def call_gemini(self, user_query: str) -> Dict[str, Any]:
        """Call Gemini API."""
        result = {
            "model": self.gemini_model,
            "explanation": "",
            "success": False,
            "error_message": "",
        }

        if not self.gemini_client:
            result["error_message"] = "Gemini client not configured"
            return result
        try:
            logger.info("Calling Gemini API")
            messages = [{"role": "user", "content": user_query}]
            response = self.gemini_client.chat.completions.create(
                model=self.gemini_model,
                messages=messages,
            )
            result["explanation"] = response.choices[0].message.content
            result["success"] = True
            logger.info("Gemini response received")
        except Exception as e:
            result["error_message"] = str(e)
            logger.error("Gemini error: %s", e)

        return result
    def call_ollama(self, prompt: str) -> Dict[str, Any]:
        """Call Ollama Service via gRPC."""
        result = {
            "model": self.ollama_model,
            "explanation": "",
            "success": False,
            "error_message": "",
        }

        try:
            request = ollama_service_pb2.OllamaRequest(
                prompt=prompt,
                model=self.ollama_model,
            )
            response = self.ollama_stub.GenerateExplanation(request, timeout=20)

            result["model"] = response.model or self.ollama_model
            result["explanation"] = response.explanation or ""
            result["success"] = response.success
            result["error_message"] = response.error_message or ""

        except grpc.RpcError as e:
            result["error_message"] = (
                f"gRPC error: {e.code().name if hasattr(e, 'code') else 'UNKNOWN'} - "
                f"{e.details() if hasattr(e, 'details') else str(e)}"
            )
            logger.error("Ollama gRPC error: %s", result["error_message"])
        except Exception as e:
            result["error_message"] = str(e)
            logger.error("Ollama error: %s", e)

        return result

    def orchestrate_dual_explanation(self, concept: str) -> Dict[str, Any]:
        """Coordinate both Gemini and Ollama for dual response."""
        logger.info("Processing dual explanation: %s", concept)

        # Get a system prompt (used to guide the explanations)
        system_prompt = self.get_system_prompt("personalize")

        # Construct user query combining the system prompt + user's concept
        user_query = f"{system_prompt}\n\nExplain the following concept in simple terms: {concept}"

        # Call both models in turn (Gemini and Ollama)
        gemini_result = self.call_gemini(user_query)
        ollama_result = self.call_ollama(user_query)

        logger.info("Dual explanation completed for concept: %s", concept)

        return {
            "concept": concept,
            "gemini_response": gemini_result,
            "ollama_response": ollama_result,
        }

    def close(self):
        """Close all gRPC connections."""
        logger.info("Closing Orchestrator connections")
        try:
            if hasattr(self, "prompt_manager_channel") and self.prompt_manager_channel:
                self.prompt_manager_channel.close()
        except Exception:
            pass
        try:
            if hasattr(self, "ollama_channel") and self.ollama_channel:
                self.ollama_channel.close()
        except Exception:
            pass
