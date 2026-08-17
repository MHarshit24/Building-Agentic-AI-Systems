"""
Prompt templates for RAG query pipeline.

TODO: Complete the implementation of create_production_prompt() function.
This function creates a production-ready prompt template with hallucination prevention.
"""

# TODO: Import necessary modules
# Verify these imports are correct for your implementation:
from langchain_core.prompts import ChatPromptTemplate
from ..config import logger


def create_production_prompt() -> ChatPromptTemplate:
    """
    Create a production-ready RAG prompt template that:
    - Combines system instructions, retrieved context, and user questions
    - Explicitly prevents hallucinations
    - Handles cases where context is insufficient

    This function creates a ChatPromptTemplate with two message roles:
    1. System message: Contains instructions for the LLM and a placeholder for context
    2. Human message: Contains a placeholder for the user's question

    Returns:
        ChatPromptTemplate instance with hallucination prevention instructions

    Hints:
        1. Use ChatPromptTemplate.from_messages() to create the template
        2. Pass a list of tuples, where each tuple contains:
           - Role name: "system" or "human"
           - Message content: String with placeholders like {context} and {question}
        3. System message should include:
           - Introduction: "You are AutoMind Motors' technical support assistant..."
           - CRITICAL INSTRUCTIONS section with:
             * Answer ONLY using provided context
             * Fallback message for insufficient information
             * No assumptions or external knowledge
             * Source citation requirements
             * Technical precision guidance
             * Multiple source synthesis
             * Safety-critical question handling
           - Context placeholder: "Context:\n{context}"
        4. Human message should contain: "{question}"
        5. Return the template
    """

    # TODO: Step 1 - Create ChatPromptTemplate using from_messages()
    # Use ChatPromptTemplate.from_messages() with a list of message tuples
    # Each tuple should be: (role, message_content)

    # TODO: Step 2 - Define system message
    # Create system message with:
    #   - Introduction: "You are AutoMind Motors' technical support assistant. You help customers with vehicle maintenance, troubleshooting, and technical questions."
    #   - CRITICAL INSTRUCTIONS section:
    #     * "Answer ONLY using the provided context below"
    #     * Fallback message: "If the context doesn't contain enough information to answer the question, respond: 'I don't have enough information in the knowledge base to answer this question accurately. Please contact AutoMind Motors support at support@automind.com or call 1-800-AUTO-MIND.'"
    #     * "Never make assumptions or use external knowledge not present in the context"
    #     * "Always cite the source document when providing answers (use the [Source: ...] tags from context)"
    #     * "Be precise and technical when context allows"
    #     * "If multiple sources provide relevant information, synthesize them coherently"
    #     * "For safety-critical questions, be extra cautious and recommend professional inspection if uncertain"
    #   - Context placeholder: "Context:\n{context}"

    system_message = """
You are AutoMind Motors' technical support assistant.
You help customers with vehicle maintenance,
troubleshooting, and technical questions.

CRITICAL INSTRUCTIONS:

1. Answer ONLY using the provided context below.

2. If the context doesn't contain enough information
to answer the question, respond EXACTLY:

"I don't have enough information in the knowledge base
to answer this question accurately. Please contact
AutoMind Motors support at support@automind.com
or call 1-800-AUTO-MIND."

3. Never make assumptions or use external knowledge
not present in the context.

4. Always cite the source document when providing
answers (use the [Source: ...] tags from context).

5. Be precise and technical when context allows.

6. If multiple sources provide relevant information,
synthesize them coherently.

7. For safety-critical questions, be extra cautious
and recommend professional inspection if uncertain.

Context:
{context}
""".strip()

    # TODO: Step 3 - Define human message
    # Create human message with: "{question}"

    human_message = "{question}"

    # TODO: Step 4 - Combine messages in from_messages()
    # Pass list of tuples: [("system", system_message), ("human", human_message)]

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_message),
            ("human", human_message)
        ]
    )

    logger.info(
        "Production prompt template initialized"
    )

    # TODO: Step 5 - Return the template

    return prompt