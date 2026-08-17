"""
Evaluation Dataset Creation Module
Creates and manages evaluation datasets in Langfuse.

TODO: Implement the functions below to create evaluation datasets in Langfuse.
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from langfuse import Langfuse

logger = logging.getLogger(__name__)

# Load environment variables


def _load_env():
    """
    Load environment variables preserving secrets from root .env,
    then loading project .env with override.
    """
    # Skip loading .env when tests intentionally clear environment
    if "pytest" in sys.modules:
        return

    # Locate root .env (Building_Agentic_AI_Systems/.env)
    # This file: <project>/main/evaluation/dataset.py -> parents[4] = root
    base_dir = Path(__file__).resolve().parents[4]
    base_env_path = base_dir / ".env"

    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
    else:
        load_dotenv()

    # Preserve secrets before loading project .env
    langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")

    # Locate project .env (s9 project root/.env)
    # This file: <project>/main/evaluation/dataset.py -> parents[2] = project root
    proj_dir = Path(__file__).resolve().parents[2]
    proj_env_path = proj_dir / ".env"

    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
    else:
        load_dotenv()

    # Restore preserved secrets
    if langfuse_secret_key:
        os.environ["LANGFUSE_SECRET_KEY"] = langfuse_secret_key
    if langfuse_public_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = langfuse_public_key


_load_env()


def get_langfuse_client() -> Langfuse:
    """
    Initialize Langfuse client using environment variables.
    
    TODO: Get LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, and LANGFUSE_HOST from environment.
    Validate keys are present, then return Langfuse client initialized with these credentials.
    """
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not secret_key:
        raise ValueError("LANGFUSE_SECRET_KEY is not set in environment")
    if not public_key:
        raise ValueError("LANGFUSE_PUBLIC_KEY is not set in environment")

    return Langfuse(
        secret_key=secret_key,
        public_key=public_key,
        host=host
    )


def create_dataset(langfuse: Langfuse, dataset_name: str):
    """
    Create an evaluation dataset for the RAG system.
    
    TODO: Call langfuse.create_dataset() with name, description, and metadata.
    Metadata should include: sprint="C3-S09", type="product_manual_qa", version="1.0", knowledge_base="product_manual"
    """
    langfuse.create_dataset(
        name=dataset_name,
        description="Evaluation dataset for Product Manual RAG System with questions across easy, medium, and hard difficulty levels",
        metadata={
            "sprint": "C3-S09",
            "type": "product_manual_qa",
            "version": "1.0",
            "knowledge_base": "product_manual"
        }
    )
    logger.info(f"✓ Dataset '{dataset_name}' created in Langfuse")


def add_items(langfuse: Langfuse, dataset_name: str):
    """
    Add test cases to the dataset.
    
    TODO: 
    1. Create a list of 10 test cases (3 easy, 4 medium, 3 hard) based on product manual document.
    2. Each test case should have: input (question), expected (answer), category, difficulty, manual_section.
    3. For hard questions, add edge_case field.
    4. Loop through test cases and call langfuse.create_dataset_item() for each.
    5. Build metadata dict with category, difficulty, manual_section, source="product_manual", and edge_case if present.
    """
    # TODO: Add 10 test cases (3 easy, 4 medium, 3 hard)
    test_cases = [
        # Easy questions (3)
        {
            "input": "What is CloudSync Pro?",
            "expected": "CloudSync Pro is a cloud synchronization software that allows users to sync files and folders across multiple devices and platforms, providing real-time synchronization, secure storage, and collaboration features.",
            "category": "product_overview",
            "difficulty": "easy",
            "manual_section": "Introduction"
        },
        {
            "input": "What are the minimum system requirements for installing CloudSync Pro?",
            "expected": "CloudSync Pro requires a compatible operating system (Windows 10 or later, macOS 10.14 or later, or a supported Linux distribution), at least 2GB of RAM, 500MB of free disk space for installation, and an internet connection.",
            "category": "installation",
            "difficulty": "easy",
            "manual_section": "System Requirements"
        },
        {
            "input": "How do I log in to CloudSync Pro?",
            "expected": "To log in to CloudSync Pro, open the application, enter your registered email address and password on the login screen, then click the Sign In button. You can also use single sign-on (SSO) if your organization has configured it.",
            "category": "getting_started",
            "difficulty": "easy",
            "manual_section": "Getting Started"
        },
        # Medium questions (4)
        {
            "input": "How do I configure selective sync in CloudSync Pro?",
            "expected": "To configure selective sync, go to Settings, select the Sync tab, then choose Selective Sync. You can then check or uncheck folders you want to sync to your local device. Unchecked folders remain in the cloud but are not downloaded locally.",
            "category": "configuration",
            "difficulty": "medium",
            "manual_section": "Sync Settings"
        },
        {
            "input": "How does CloudSync Pro handle file conflicts when two users edit the same file simultaneously?",
            "expected": "CloudSync Pro detects file conflicts when two users edit the same file simultaneously. It preserves both versions by creating a conflict copy with the original filename plus the conflicting user's name and timestamp. Users are notified of the conflict and can manually review and merge the files.",
            "category": "collaboration",
            "difficulty": "medium",
            "manual_section": "Conflict Resolution"
        },
        {
            "input": "What are the steps to share a folder with external users in CloudSync Pro?",
            "expected": "To share a folder with external users, right-click the folder in CloudSync Pro, select Share, enter the recipient's email address, choose their permission level (view or edit), and click Send Invitation. External users will receive an email with a link to access the shared folder.",
            "category": "collaboration",
            "difficulty": "medium",
            "manual_section": "Sharing and Collaboration"
        },
        {
            "input": "How can I recover a deleted file in CloudSync Pro?",
            "expected": "To recover a deleted file, open the CloudSync Pro web portal or desktop app, navigate to the Trash or Deleted Files section, locate the file you want to restore, and click Restore. Files remain in the Trash for a retention period defined by your plan before being permanently deleted.",
            "category": "file_management",
            "difficulty": "medium",
            "manual_section": "File Recovery"
        },
        # Hard questions (3)
        {
            "input": "How do I configure CloudSync Pro to work behind a corporate proxy with SSL inspection enabled?",
            "expected": "To configure CloudSync Pro behind a corporate proxy with SSL inspection, go to Settings, select Network, and enter the proxy server address, port, and credentials. For SSL inspection, you must import your organization's root CA certificate into CloudSync Pro's trusted certificate store under Settings > Security > Certificates. You may also need to disable certificate pinning if your proxy intercepts HTTPS traffic.",
            "category": "network_configuration",
            "difficulty": "hard",
            "manual_section": "Advanced Network Settings",
            "edge_case": "corporate_proxy_ssl_inspection"
        },
        {
            "input": "What happens to CloudSync Pro's sync behavior when storage quota is exceeded and how can an administrator manage quota allocation across team members?",
            "expected": "When storage quota is exceeded, CloudSync Pro pauses new uploads and displays a quota exceeded warning. Existing synced files remain accessible but no new files can be uploaded until space is freed or quota is increased. Administrators can manage quota allocation through the Admin Console under Team Settings > Storage Management, where they can set per-user limits, view usage reports, and purchase additional storage.",
            "category": "administration",
            "difficulty": "hard",
            "manual_section": "Storage Management",
            "edge_case": "quota_exceeded_admin_management"
        },
        {
            "input": "How does CloudSync Pro's version history work and what are the limitations when restoring a file that has been moved or renamed multiple times?",
            "expected": "CloudSync Pro maintains version history for all synced files, allowing users to restore previous versions from the file's context menu under Version History. The number of versions retained depends on your subscription plan. When restoring a file that has been moved or renamed multiple times, CloudSync Pro tracks the file by its unique internal ID rather than its name or path, so version history is preserved across moves and renames. However, restoring an old version restores it to the file's current location with its current name, not its original path.",
            "category": "file_management",
            "difficulty": "hard",
            "manual_section": "Version History",
            "edge_case": "version_history_moved_renamed_files"
        }
    ]

    # TODO: Loop through test_cases and add each to Langfuse dataset
    for i, test_case in enumerate(test_cases, 1):
        metadata = {
            "category": test_case["category"],
            "difficulty": test_case["difficulty"],
            "manual_section": test_case["manual_section"],
            "source": "product_manual"
        }
        if "edge_case" in test_case:
            metadata["edge_case"] = test_case["edge_case"]

        langfuse.create_dataset_item(
            dataset_name=dataset_name,
            input={"question": test_case["input"]},
            expected_output=test_case["expected"],
            metadata=metadata
        )
        logger.info(f"  Added item {i}/10: [{test_case['difficulty']}] {test_case['input'][:60]}...")

    logger.info(f"✓ All 10 test cases added to dataset '{dataset_name}'")


def main():
    """
    Main function to create the evaluation dataset.
    
    TODO: 
    1. Set DATASET_NAME = "product_manual"
    2. Get Langfuse client, create dataset, add items
    3. Print summary with dataset name, total questions, and breakdown
    """
    DATASET_NAME = "product_manual"

    print(f"\n{'='*50}")
    print("Creating Evaluation Dataset in Langfuse")
    print(f"{'='*50}")

    langfuse = get_langfuse_client()
    print(f"✓ Langfuse client initialized")

    create_dataset(langfuse, DATASET_NAME)
    print(f"✓ Dataset '{DATASET_NAME}' created")

    add_items(langfuse, DATASET_NAME)

    print(f"\n{'='*50}")
    print("Dataset Creation Summary")
    print(f"{'='*50}")
    print(f"Dataset Name  : {DATASET_NAME}")
    print(f"Total Questions: 10")
    print(f"  - Easy      : 3")
    print(f"  - Medium    : 4")
    print(f"  - Hard      : 3")
    print(f"{'='*50}\n")

    langfuse.flush()


if __name__ == "__main__":
    main()