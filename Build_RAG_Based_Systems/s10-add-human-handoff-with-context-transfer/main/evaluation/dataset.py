"""
Evaluation Dataset Creation Module
Creates and manages evaluation datasets in Langfuse.
"""

import os
from dotenv import load_dotenv
from langfuse import Langfuse

# Load environment variables
load_dotenv()


def get_langfuse_client() -> Langfuse:
    """Initialize Langfuse client using env vars."""
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not secret_key or not public_key:
        raise RuntimeError(
            "LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY must be set in environment."
        )

    return Langfuse(
        secret_key=secret_key,
        public_key=public_key,
        host=host,
    )


def create_dataset(langfuse: Langfuse, dataset_name: str):
    """
    Create an evaluation dataset for the RAG system.
    
    Creates:
    - A named dataset
    - With metadata for tracking
    """
    print(f"Creating dataset '{dataset_name}' if it does not exist...")

    langfuse.create_dataset(
        name=dataset_name,
        description="Sprint 9 Practice: Evaluation dataset for product manual RAG system",
        metadata={
            "sprint": "C3-S09",
            "type": "product_manual_qa",
            "version": "1.0",
            "knowledge_base": "product_manual",
        },
    )
    print("✓ Dataset created (or already exists).")


def add_items(langfuse: Langfuse, dataset_name: str):
    """
    Add test cases to the dataset.
    
    Creates:
    - 10 test questions total
    - 3 easy factual questions
    - 4 medium procedural questions
    - 3 hard edge-case questions
    
    All questions are based on the CloudSync Pro product manual.
    """
    
    test_cases = [
        # Easy factual questions (3)
        {
            "input": "How much storage does the free plan include?",
            "expected": "The free plan includes 5GB of cloud storage.",
            "category": "storage",
            "difficulty": "easy",
            "manual_section": "storage_plans",
        },
        {
            "input": "What encryption standard does CloudSync Pro use for end-to-end encryption?",
            "expected": "CloudSync Pro uses AES-256 encryption for end-to-end encryption.",
            "category": "security",
            "difficulty": "easy",
            "manual_section": "security",
        },
        {
            "input": "How many days of version history are available on the free plan?",
            "expected": "Free plan users have access to 30 days of version history.",
            "category": "features",
            "difficulty": "easy",
            "manual_section": "storage_plans",
        },
        # Medium procedural questions (4)
        {
            "input": "How do users set up two-factor authentication?",
            "expected": "Users can set up 2FA by scanning a QR code with an authenticator app like Google Authenticator, Microsoft Authenticator, or Authy, and then entering a verification code.",
            "category": "security",
            "difficulty": "medium",
            "manual_section": "authentication",
        },
        {
            "input": "What is the minimum internet speed required for optimal CloudSync Pro performance?",
            "expected": "CloudSync Pro requires at least 5 Mbps download and 2 Mbps upload speeds for optimal performance.",
            "category": "requirements",
            "difficulty": "medium",
            "manual_section": "installation",
        },
        {
            "input": "How can users configure bandwidth limits for synchronization?",
            "expected": "Users can configure bandwidth limits by setting maximum speeds, scheduling bandwidth limits for specific times of day, or pausing synchronization during certain hours.",
            "category": "configuration",
            "difficulty": "medium",
            "manual_section": "synchronization",
        },
        {
            "input": "What happens when the same file is modified on multiple devices simultaneously?",
            "expected": "CloudSync Pro automatically creates conflict copies with timestamps and device names appended, and users receive notifications to choose which version to keep.",
            "category": "synchronization",
            "difficulty": "medium",
            "manual_section": "synchronization",
        },
        # Hard edge-case questions (3)
        {
            "input": "If a user reaches 100% of their storage limit, what happens to new file uploads?",
            "expected": "The manual states that users receive email notifications when they reach 80%, 90%, and 100% of their storage limit, but it does not explicitly state what happens to new uploads at 100% capacity. This would likely prevent new uploads, but users should contact support for clarification.",
            "category": "storage",
            "difficulty": "hard",
            "manual_section": "storage_plans",
            "edge_case": "storage_limit_behavior",
        },
        {
            "input": "Can a user access files that are not synced locally on their device?",
            "expected": "Yes, files that are not synced locally remain accessible through the web interface or mobile app, even though they are not stored on the local device.",
            "category": "synchronization",
            "difficulty": "hard",
            "manual_section": "synchronization",
            "edge_case": "selective_sync_access",
        },
        {
            "input": "What happens to end-to-end encrypted files if a user loses their encryption key?",
            "expected": "The manual states that only users with the encryption key can decrypt E2EE-protected files, and even CloudSync Pro administrators cannot access them. If the encryption key is lost, the files would be inaccessible, but the manual does not specify recovery options. Users should contact support for assistance.",
            "category": "security",
            "difficulty": "hard",
            "manual_section": "security",
            "edge_case": "key_recovery",
        },
    ]

    print(f"Adding {len(test_cases)} items to dataset '{dataset_name}'...")

    for idx, case in enumerate(test_cases, start=1):
        # Build metadata dict with all available fields
        metadata = {
            "category": case["category"],
            "difficulty": case["difficulty"],
            "manual_section": case.get("manual_section", "general"),
            "source": "product_manual",
        }
        # Add edge_case field if present
        if "edge_case" in case:
            metadata["edge_case"] = case["edge_case"]
        
        langfuse.create_dataset_item(
            dataset_name=dataset_name,
            input={"question": case["input"]},
            expected_output=case["expected"],
            metadata=metadata,
        )
        print(f"  ✓ Added item {idx} ({case['difficulty']}): {case['input']}")

    print("✓ All items added to dataset.")


def main():
    """Main function to create the evaluation dataset."""
    DATASET_NAME = "product_manual"

    langfuse = get_langfuse_client()
    create_dataset(langfuse, DATASET_NAME)
    add_items(langfuse, DATASET_NAME)

    print("\n" + "="*60)
    print("Dataset setup completed.")
    print("="*60)
    print(f"Dataset: '{DATASET_NAME}'")
    print("Total questions: 10")
    print("  - Easy factual: 3")
    print("  - Medium procedural: 4")
    print("  - Hard edge-case: 3")
    print(f"\nYou can now see dataset '{DATASET_NAME}' in the Langfuse dashboard under 'Datasets'.")
    print("="*60)


if __name__ == "__main__":
    main()

