import os
import asyncio
from typing import Literal
from crewai.flow.flow import Flow, start, listen, router
from crewai import Agent, Task, Crew, LLM
from dotenv import load_dotenv
from pathlib import Path
from models import ResumeFlowState

# Load root .env first, then project .env (preserving shared Azure credentials)
_root_env = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_root_env, override=False)

# Preserve Azure credentials from root .env before any override
_azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
_azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
_azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
_azure_llm_deployment = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT")

# Load project-level .env if present
_project_env = Path(__file__).resolve().parent / ".env"
if _project_env.exists():
    load_dotenv(dotenv_path=_project_env, override=True)

# Restore root Azure credentials so they are always available
if _azure_api_key:
    os.environ["AZURE_OPENAI_API_KEY"] = _azure_api_key
if _azure_endpoint:
    os.environ["AZURE_OPENAI_ENDPOINT"] = _azure_endpoint
if _azure_api_version:
    os.environ["AZURE_OPENAI_API_VERSION"] = _azure_api_version
if _azure_llm_deployment:
    os.environ["AZURE_OPENAI_LLM_DEPLOYMENT"] = _azure_llm_deployment

def _build_azure_llm() -> "LLM":
    """
    Build and return a configured Azure OpenAI LLM instance.

    TODOs:
    1. Read required Azure OpenAI configuration from environment variables.
    2. Validate that required values are present and raise ValueError if any are missing.
    3. Construct and return a CrewAI LLM configured for the Azure OpenAI provider.
    """
    # TODO: Step 1 - Read Azure OpenAI settings from environment
    # Hint: Use os.getenv for AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT_NAME.
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    # Use personal env var name as primary, README-specified name as fallback
    deployment_name = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT") or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

    # TODO: Step 2 - Validate required configuration
    # Hint: Ensure API key, endpoint, and deployment name are not empty before proceeding.
    missing = [
        name for name, val in [
            ("AZURE_OPENAI_API_KEY", api_key),
            ("AZURE_OPENAI_ENDPOINT", endpoint),
            ("AZURE_OPENAI_LLM_DEPLOYMENT", deployment_name),
        ] if not val
    ]
    if missing:
        raise ValueError(f"Missing required Azure OpenAI environment variables: {', '.join(missing)}")

    # TODO: Step 3 - Create and return the LLM instance
    # Hint: Use the LLM class from CrewAI with provider set to "azure_openai".
    return LLM(
        model=f"azure/{deployment_name}",
        api_key=api_key,
        base_url=endpoint,
        api_version=api_version or "2024-02-15-preview",
    )


class ResumeScreeningFlow(Flow[ResumeFlowState]):

    def __init__(self):
        super().__init__()
        # TODO: Initialize LLM
        # Hint: usage self.llm = _build_azure_llm()
        self.llm = _build_azure_llm()

    @start()
    def classify_resume(self):
        """
        Entry point: Classify the role based on resume content.
        
        TODOs:
        1. Access resume_text from self.state.
        2. Analyze keywords to determine the role (Data Analyst, HR Manager, Sales Executive, or General).
        3. Update self.state.classified_role.
        4. Return the track name for routing.
        """
        # TODO: Step 1 - Analyze resume text
        # Hint: Check for keywords like 'sql', 'python', 'recruitment', 'sales', etc.
        resume_lower = self.state.resume_text.lower()

        data_analyst_keywords = ["sql", "python", "tableau", "power bi", "data analysis",
                                  "machine learning", "statistics", "pandas", "numpy", "etl",
                                  "data pipeline", "r programming", "data scientist", "analytics"]
        hr_keywords = ["recruitment", "hiring", "onboarding", "hr", "human resources",
                       "talent acquisition", "payroll", "employee relations", "compliance",
                       "performance management", "workforce", "hris"]
        sales_keywords = ["sales", "quota", "crm", "revenue", "b2b", "b2c", "account executive",
                          "business development", "lead generation", "salesforce", "pipeline",
                          "closing deals", "cold calling", "client acquisition"]

        data_score = sum(1 for kw in data_analyst_keywords if kw in resume_lower)
        hr_score = sum(1 for kw in hr_keywords if kw in resume_lower)
        sales_score = sum(1 for kw in sales_keywords if kw in resume_lower)

        # TODO: Step 2 - Set classified role in state
        if data_score >= hr_score and data_score >= sales_score and data_score > 0:
            self.state.classified_role = "Data Analyst"
            track = "data_analyst_track"
        elif hr_score >= data_score and hr_score >= sales_score and hr_score > 0:
            self.state.classified_role = "HR Manager"
            track = "hr_track"
        elif sales_score > 0:
            self.state.classified_role = "Sales Executive"
            track = "sales_track"
        else:
            self.state.classified_role = "General"
            track = "general_track"

        # TODO: Step 3 - Return routing track
        # Hint: Return 'data_analyst_track', 'hr_track', etc.
        return track

    @router(classify_resume)
    def route_application(self, track: str):
        """
        Route to appropriate evaluator crew.
        
        TODOs:
        1. Validate the track.
        2. Return the track to trigger the correct @listen method.
        """
        # TODO: Return the track
        valid_tracks = {"data_analyst_track", "hr_track", "sales_track", "general_track"}
        if track not in valid_tracks:
            return "general_track"
        return track

    def _run_evaluator(self, role_name: str, goal: str, criteria: str, evaluator_type: str):
        """
        Helper to run a specialized evaluator crew.
        
        TODOs:
        1. Create an Agent with the specific role and goal.
        2. Create a Task to evaluate the resume against criteria.
        3. Create a Crew with the agent and task.
        4. Kickoff the crew and update state with the result (text feedback).
        """
        # TODO: Step 1 - Create Agent
        agent = Agent(
            role=role_name,
            goal=goal,
            backstory=(
                f"You are an experienced {role_name} with deep expertise in evaluating candidates. "
                f"You provide thorough, honest, and constructive assessments based on industry standards."
            ),
            llm=self.llm,
            verbose=False,
        )

        # TODO: Step 2 - Create Task
        # Hint: Description should ask for detailed text justification (no JSON).
        task = Task(
            description=(
                f"Evaluate the following resume for the candidate '{self.state.candidate_name}' "
                f"who is applying for: {self.state.applying_for}.\n\n"
                f"RESUME:\n{self.state.resume_text}\n\n"
                f"Evaluate against these criteria: {criteria}\n\n"
                f"Provide a detailed text assessment covering: strengths, weaknesses, "
                f"overall fit for the role, and a hiring recommendation. "
                f"Do NOT respond in JSON format — write your evaluation as clear, structured prose."
            ),
            expected_output=(
                "A detailed prose evaluation of the candidate including: "
                "1) Key strengths observed, "
                "2) Areas of concern or gaps, "
                "3) Overall suitability for the role, "
                "4) A clear hiring recommendation (Recommended / Not Recommended / Needs Further Review)."
            ),
            agent=agent,
        )

        # TODO: Step 3 - Run Crew
        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=False,
        )
        result = crew.kickoff()

        # TODO: Step 4 - Update State
        # Hint: Store result.raw in self.state.justification
        self.state.justification = result.raw
        self.state.evaluator_role = role_name

    @listen("data_analyst_track")
    def run_data_analyst_crew(self):
        """
        Listener for Data Analyst track.
        """
        # TODO: Call _run_evaluator
        # Hint: Role='Lead Data Scientist', Criteria='SQL, Python, Tableau...'
        self._run_evaluator(
            role_name="Lead Data Scientist",
            goal="Evaluate candidates for data analyst and data science roles with rigorous technical assessment.",
            criteria="SQL, Python, Tableau, Power BI, statistical analysis, machine learning, ETL pipelines, data visualization, problem-solving ability, and experience with large datasets.",
            evaluator_type="data_analyst",
        )

    @listen("hr_track")
    def run_hr_crew(self):
        """
        Listener for HR track.
        """
        # TODO: Call _run_evaluator
        # Hint: Role='HR Director', Criteria='Recruitment, Compliance...'
        self._run_evaluator(
            role_name="HR Director",
            goal="Evaluate candidates for HR and talent management roles with focus on people skills and compliance knowledge.",
            criteria="Recruitment, talent acquisition, compliance, employee relations, HRIS systems, onboarding, payroll management, performance management, and interpersonal communication skills.",
            evaluator_type="hr",
        )

    @listen("sales_track")
    def run_sales_crew(self):
        """
        Listener for Sales track.
        """
        # TODO: Call _run_evaluator
        # Hint: Role='VP of Sales', Criteria='Quota, CRM...'
        self._run_evaluator(
            role_name="VP of Sales",
            goal="Evaluate candidates for sales roles with focus on revenue generation, quota attainment, and client relationship skills.",
            criteria="Quota attainment, CRM proficiency (Salesforce etc.), B2B/B2C sales experience, lead generation, pipeline management, cold calling, client acquisition, negotiation skills, and revenue growth track record.",
            evaluator_type="sales",
        )
    
    @listen("general_track")
    def run_general_crew(self):
         """
         Listener for General track.
         """
         # TODO: Call _run_evaluator
         # Hint: Role='General Recruiter', Criteria='Employability...'
         self._run_evaluator(
             role_name="General Recruiter",
             goal="Evaluate candidates for general roles with focus on overall employability and transferable skills.",
             criteria="Employability, communication skills, work ethic, adaptability, problem-solving, educational background, transferable skills, teamwork, and overall professional presentation.",
             evaluator_type="general",
         )

async def process_resume(candidate_name: str, resume_text: str, applying_for: str):
    """
    Process a resume through the multi-crew flow.
    
    TODOs:
    1. Initialize ResumeScreeningFlow.
    2. Set initial state (candidate_name, resume_text, applying_for).
    3. Run the flow asynchronously using run_in_executor.
    4. Return the flow instance and final result.
    """
    # TODO: Step 1 - Initialize and set state
    flow = ResumeScreeningFlow()
    flow.state.candidate_name = candidate_name
    flow.state.resume_text = resume_text
    flow.state.applying_for = applying_for

    # TODO: Step 2 - Execute flow
    # Hint: await loop.run_in_executor(None, flow.kickoff)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, flow.kickoff)

    return flow, result