# Building and Extending AI Assistants in Azure

This project demonstrates how to build, deploy, and extend AI Assistants
using Azure OpenAI and Azure AI Foundry.

It walks through three major capabilities:

-   Deploying a Chat Model
-   Creating a File-Based Assistant with Vector Search
-   Extending an Assistant using Function Calling

------------------------------------------------------------------------

# Task 1: Deploying a Chat Model

## Objective

Activate a base chat model inside Azure so it can power AI applications.

## Steps

1.  Create an Azure OpenAI Resource

    -   Region: East US2
    -   Pricing Tier: Standard S0
    -   Resource Group: ChatResource

2.  Open Azure AI Foundry

3.  Navigate to:
    Shared Resources → Deployments

4.  Click:

    -   Deploy Model → Deploy Base Model

5.  Select:
    gpt-4o-mini

6.  Click Deploy

7.  Open in Playground and test the model.

------------------------------------------------------------------------

# Task 2: Deploying a File-Based Assistant (RAG)

## Objective

Create an assistant that answers questions strictly from an uploaded
document using vector search.

## Steps

1.  Go to Assistants (Preview)
2.  Click New Assistant
3.  Name it: File Based Assistant
4.  Enable File Search
5.  Click Add Vector Store
6.  Upload a PDF file(Python style Guide is provided for the same) [click_here](Style_Guide_for_Python_Code.pdf) for the file

### Restriction Prompt

You are a file-based assistant.
Answer questions strictly based only on the content of the attached file
in the vector store. If a question is not related to the file or the information is not
present in the file, respond with: "I can only answer questions based on the uploaded file."

------------------------------------------------------------------------

# Task 3: Extending Assistant with Function Calling

## Objective

Enable the assistant to execute structured functions instead of only
generating text.

## Use Case: Code Converter

Steps:

1.  Click New Assistant
2.  Name it: Coding Assistant
3.  Scroll to Functions → Add Function
4.  Paste your function schema (convert_code)
5.  Click Save
6.  Enter a request like: Convert this Java code to Python
7.  Click Play to execute the function

------------------------------------------------------------------------
[Click here](function_schema.txt) for function schema.
# Key Concepts Demonstrated

-   Azure OpenAI Resource Management
-   Model Deployment
-   Vector Store Integration
-   Restriction Prompting
-   Function Calling
-   Tool-Enabled AI Assistants

------------------------------------------------------------------------

# Prerequisites

-   Azure Subscription
-   Azure OpenAI Resource
-   Access to Azure AI Foundry
-   Deployed Chat Model

------------------------------------------------------------------------

This project is intended for educational and demonstration purposes.
