def build_prompt(code, language, experience_level, task="analyze"):
    
    # Customize instructions based on experience level
    if experience_level.lower() == "beginner":
        tone_instruction = """
Explain everything in simple terms. Avoid jargon. Use analogies and step-by-step explanations.
Focus on basic concepts and fundamental understanding. Assume the user is learning programming.
"""
    elif experience_level.lower() == "expert":
        tone_instruction = """
Use technical terminology and advanced concepts. Focus on optimization patterns, performance implications,
and architectural considerations. Assume deep understanding of programming concepts.
"""
    else:  # intermediate
        tone_instruction = """
Use moderate technical language. Explain concepts clearly but include some technical details.
Focus on practical implementation and common patterns. Assume some programming experience.
"""

    if task == "analyze":

        instruction = f"""
Return JSON in this format:

{{
 "code_summary": "Brief summary of what the code does",
 "detected_issues": ["list any bugs or issues"],
 "improvements": ["suggest improvements"],
 "best_practices": ["recommended best practices"]
}}

{tone_instruction}
"""

    elif task == "explain":

        instruction = f"""
Explain the code clearly for the developer.
Focus on readability and understanding.
Return JSON in this format:

{{
 "explanation": "Detailed explanation of how the code works",
 "complexity_level": "beginner/intermediate/advanced",
 "key_concepts": ["important concepts used in the code"]
}}

{tone_instruction}
"""

    elif task == "improve":

        instruction = f"""
Suggest improvements and optimized implementation.
Return JSON in this format:

{{
 "current_code_summary": "What the code currently does",
 "suggested_improvements": ["list of specific improvements"],
 "optimized_code": "improved version of the code (optional)",
 "performance_gain": "expected performance improvement (optional)"
}}

{tone_instruction}
"""

    elif task == "review":

        instruction = f"""
Perform a comprehensive code review with scoring.
Return JSON in this format:

{{
 "overall_score": 1-10,
 "explanation": "Explain what the code does",
 "detected_issues": ["bugs, inefficiencies, or code smells"],
 "improvements": ["ways to improve the implementation"],
 "best_practices": ["recommended coding standards"],
 "security_concerns": ["potential security issues"],
 "maintainability_score": 1-10
}}

{tone_instruction}
"""

    prompt = f"""
You are an expert software engineer.

Analyze the following {language} code for a {experience_level} developer.

{instruction}

Code:
{code}

Return only valid JSON.
"""
    

    return prompt