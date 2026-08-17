# Azure AI Foundry – Hands-On Lab

## Overview

In this lab, you will work with Azure AI Foundry to:

- Access the Azure AI environment  
- Deploy and interact with a chat model  
- Upload and analyze documents  
- Configure and use function calling  

This lab is designed to help you understand both standard chat interaction and document-grounded reasoning using Azure AI.

---
> **Note:** If you encounter an error while deploying the model (for example, capacity limits or temporary service issues), wait for a few minutes and try again.


## Task 1: Login to Cloud Lab – Azure AI

### Objective  
Access the Azure AI environment through Cloud Lab.

### Instructions
1. Log in to the Cloud Lab portal.  
2. Navigate to **Azure AI Foundry**.

---

## Task 2: Set Up Project and Deploy Chat Model

### Objective  
Create a project, deploy a chat model, and interact with it using the Chat Playground.

### Instructions
1. Create a new Azure AI Project.  
2. Deploy a chat-capable model.  
3. Open the **Chat Playground**.  
4. Interact with the model using custom prompts.  
5. Modify system prompts, temperature, and output format as needed.

---

## Task 3: Upload and Analyze Documents in Assistant Playground

### Objective  
Use the Assistant Playground to upload the Goa Travel Guide PDF and analyze it with the deployed model.

### Instructions
1. Open the **Assistant Playground**.  
2. Create a new Assistant.  
3. Attach the deployed model.  
4. Upload the Goa Travel Guide PDF.  
5. Ask document-based questions and analyze the responses.

---

## Task 4: Configure and Use Functions in Assistant Playground

### Objective  
Define and use Functions as a tool within the Assistant Playground for Goa trip planning.

### Instructions
1. Add the following function schema in the Assistant configuration.  
2. Enable function calling.  
3. Ask the assistant to plan a trip to Goa and observe the function invocation.

### Example Function Schema

```json
{
  "name": "plan_goa_trip",
  "description": "Generate a structured travel plan for Goa",
  "parameters": {
    "type": "object",
    "properties": {
      "days": {
        "type": "integer",
        "description": "Number of days for the Goa trip"
      },
      "travel_style": {
        "type": "string",
        "description": "Preferred travel style",
        "enum": ["relaxed", "adventure", "family", "romantic", "cultural"]
      }
    },
    "required": ["days","travel_style"]
  }
}
```
### Expected Outcome
By completing this lab, you will be able to:
1. Work within Azure AI Foundry
2. Deploy and test chat models
3. Perform document-grounded analysis
4. Integrate function calling in assistant workflows