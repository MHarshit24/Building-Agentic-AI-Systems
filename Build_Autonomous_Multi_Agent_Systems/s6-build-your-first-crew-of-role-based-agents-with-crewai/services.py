import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dotenv import load_dotenv

from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool

# Load environment variables from the root .env (Building_Agentic_AI_Systems/)
BASE_DIR = Path(__file__).resolve().parents[2]
base_env_path = BASE_DIR / ".env"
if base_env_path.exists():
    load_dotenv(dotenv_path=base_env_path)
else:
    load_dotenv()


def create_review_analysis_crew(product: str):
    """
    Create and execute a product review analysis crew for the given product.
    """
    
    # ------------------------------------------------------------------
    # Azure OpenAI configuration (STRICT)
    # ------------------------------------------------------------------
    # TODO: Load Azure OpenAI environment variables, validate them, and initialize LLM
    # Hint: Use os.getenv() to retrieve AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, 
    # AZURE_OPENAI_DEPLOYMENT_NAME, and AZURE_OPENAI_API_VERSION (default: "2024-02-15-preview")
    # Validate all required variables are present, raise ValueError if missing
    # Initialize LLM with model, provider="azure_openai", azure_endpoint, api_key, 
    # api_version, and temperature=0.3
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment_name = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT", os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"))
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

    if not api_key:
        raise ValueError("Missing required environment variable: AZURE_OPENAI_API_KEY")
    if not azure_endpoint:
        raise ValueError("Missing required environment variable: AZURE_OPENAI_ENDPOINT")
    if not deployment_name:
        raise ValueError("Missing required environment variable: AZURE_OPENAI_LLM_DEPLOYMENT / AZURE_OPENAI_DEPLOYMENT_NAME")

    llm = LLM(
        model=deployment_name,
        provider="azure_openai",
        api_key=api_key,
        api_base=azure_endpoint,
        api_version=api_version,
        temperature=0.3,
    )
    
    # ------------------------------------------------------------------
    # Initialize web search tool for review research
    # ------------------------------------------------------------------
    # TODO: Initialize SerperDevTool for web search
    # Hint: Use SerperDevTool() and store in search_tool variable
    search_tool = SerperDevTool()
    
    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------
    # TODO: Create three agents:
    # 1. Review Researcher: role="Product Review Analyst", goal="Find and compile recent product reviews from multiple sources",
    #    appropriate backstory about finding authentic reviews, tools=[search_tool], llm, verbose=True, allow_delegation=False
    # 2. Sentiment Analyzer: role="Customer Sentiment Specialist", goal="Analyze review sentiment and extract key themes",
    #    appropriate backstory about reading between the lines, llm, verbose=True, allow_delegation=False
    # 3. Insights Reporter: role="Business Insights Writer", goal="Transform analysis into actionable business recommendations",
    #    appropriate backstory about translating data to insights, llm, verbose=True, allow_delegation=False
    review_researcher = Agent(
        role="Product Review Analyst",
        goal="Find and compile recent product reviews from multiple sources",
        backstory=(
            "You are an expert at discovering authentic customer reviews across the web. "
            "You know how to find the most relevant, detailed, and trustworthy reviews "
            "from retailers, forums, and review platforms, ensuring a comprehensive view of the product."
        ),
        tools=[search_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    sentiment_analyzer = Agent(
        role="Customer Sentiment Specialist",
        goal="Analyze review sentiment and extract key themes",
        backstory=(
            "You have a sharp eye for reading between the lines of customer feedback. "
            "You excel at identifying emotional tone, recurring praise, and hidden frustrations, "
            "turning raw review data into structured sentiment intelligence."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    insights_reporter = Agent(
        role="Business Insights Writer",
        goal="Transform analysis into actionable business recommendations",
        backstory=(
            "You are a seasoned business analyst who specializes in translating customer data "
            "into clear, executive-ready reports. You craft concise summaries that highlight "
            "opportunities and risks, empowering stakeholders to make informed decisions."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )
    
    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------
    # TODO: Create three tasks:
    # 1. Research Task: description to search for reviews of {product}, find 3-5 detailed reviews covering different aspects,
    #    expected_output describing compilation of 3-5 reviews with source references, agent=review_researcher, tools=[search_tool]
    # 2. Analyze Task: description to analyze sentiment, praised features, complaints, and recurring themes,
    #    expected_output describing structured analysis with sentiment scores and categorized themes, 
    #    agent=sentiment_analyzer, context=[research_task]
    # 3. Report Task: description to create executive summary with sentiment overview, key strengths, weaknesses, and recommendations,
    #    expected_output describing professional report (300-400 words) with actionable recommendations,
    #    agent=insights_reporter, context=[analyze_task], output_file="product_insights.md"
    research_task = Task(
        description=(
            "Search for recent customer reviews of {product}. "
            "Find 3-5 detailed reviews covering different aspects such as quality, performance, "
            "value for money, and customer support. Use multiple sources including retailer sites, "
            "review platforms, and consumer forums."
        ),
        expected_output=(
            "A compilation of 3-5 detailed customer reviews for {product}, each including "
            "the review source URL or platform name, reviewer rating, and full review text."
        ),
        agent=review_researcher,
        tools=[search_tool],
    )

    analyze_task = Task(
        description=(
            "Analyze the compiled reviews for {product}. "
            "Determine the overall sentiment (positive, negative, neutral) and assign a sentiment score. "
            "Identify the most praised features, common complaints, and any recurring themes "
            "across multiple reviews."
        ),
        expected_output=(
            "A structured sentiment analysis report containing: overall sentiment score (0-10), "
            "list of praised features with frequency counts, list of complaints with frequency counts, "
            "and categorized recurring themes."
        ),
        agent=sentiment_analyzer,
        context=[research_task],
    )

    report_task = Task(
        description=(
            "Create an executive summary report for {product} based on the sentiment analysis. "
            "The report should include a sentiment overview, key product strengths, identified weaknesses, "
            "and concrete actionable recommendations for product improvement or marketing strategy."
        ),
        expected_output=(
            "A professional executive report of 300-400 words covering: sentiment overview, "
            "top 3 strengths, top 3 weaknesses, and at least 3 actionable business recommendations."
        ),
        agent=insights_reporter,
        context=[analyze_task],
        output_file="product_insights.md",
    )
    
    # ------------------------------------------------------------------
    # Crew
    # ------------------------------------------------------------------
    # TODO: Create and return Crew
    # Hint: Use Crew() with agents list, tasks list, process=Process.sequential, verbose=True, tracing=True
    # Return crew.kickoff(inputs={"product": product})
    crew = Crew(
        agents=[review_researcher, sentiment_analyzer, insights_reporter],
        tasks=[research_task, analyze_task, report_task],
        process=Process.sequential,
        verbose=True,
        tracing=True,
    )

    # Run crew.kickoff in a separate thread to avoid event loop conflicts with FastAPI
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(crew.kickoff, {"product": product})
        return future.result()