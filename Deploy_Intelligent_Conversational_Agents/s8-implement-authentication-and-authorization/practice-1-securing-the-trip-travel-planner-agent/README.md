## Project Context

In earlier practice, you made your Trip & Travel Planner Agent interactive using **React**.  
However, it was still open to everyone — anyone with the URL could use it.  

In this practice, you will secure your agent using **Auth0**.  
You’ll configure user roles (admin, user), and protect your **FastAPI** backend so only authenticated and authorized users can access it.  
 

---

## Problem Statement

Implement secure authentication and authorization for your Travel Agent using **Auth0**, **React**, and **FastAPI**.  
You’ll complete three main tasks corresponding to the three learning objectives.

---

### **Task 1 — Configure Auth0 with Roles**

#### Goal  
Create and configure a secure identity layer in Auth0.

#### Requirements  
1. Create an API in Auth0.    
2. Create an application in Auth0.   
3. Create **admin** and **user** roles.
4. Create users and assign roles manually. 
5. Add one **Auth0 Actions**:  
   - `add-roles-to-tokens` → adds roles to JWT.  
6. Test login for different users and  roles.  

#### Implementation Details
The Auth0 tenant has been configured with a Single Page Application (SPA) for the React frontend and an API for the FastAPI backend. The API identifier is set to a unique URI that matches the audience configured in the application. Two roles have been created: 'admin' and 'user', with appropriate permissions. Users have been manually created and assigned to these roles. An Auth0 Action has been implemented to inject role information into the JWT access tokens, using the namespace for role claims. This setup ensures that user roles are available in the application for authorization decisions.

---

### **Task 2 — Integrate Auth0 SDK in React**

#### Goal  
Connect your React frontend to Auth0 for login/logout and role-based UI.

#### Requirements  
1. Install the SDK:  
   ```bash
   npm install @auth0/auth0-react ```

2. Create `.env` with required environment variable.

   ``` 
   VITE_AUTH0_DOMAIN=your-domain.auth0.com
   VITE_AUTH0_CLIENT_ID=your-client-id
   VITE_AUTH0_AUDIENCE=your-api-audience
   VITE_AUTH0_ROLE_NAMESPACE=https://stateful-agent.com  

   ```

3. In `main.tsx` wrap your <App> component with the Auth0 provider.

4. In `App.tsx`:  
   - Use `useAuth0()` hook to get the roles of the login user.  
   - Implement Log In and Log Out button.
   -  Based on role conditionally display the chat component for user and admin welcome message for admin.
    

**Expected Output:**  
- Non-authenticated users see “Please log in to access the chat.”  
- Authenticated users can chat.  
- Authenticated admins see the “Welcome Admin” message.#### Implementation Details
The React application has been integrated with Auth0 using the auth0-react SDK. The Auth0Provider component wraps the entire App component in main.tsx, configured with the domain, client ID, audience, and redirect URI. The App component uses the useAuth0 hook to manage authentication state, including login, logout, and user information. Login and logout buttons are implemented in the header, with conditional rendering based on authentication status. Role-based UI is implemented by extracting roles from the user object using the configured namespace, displaying the chat component for regular users and a welcome message for admins. The application handles loading states and provides appropriate user feedback throughout the authentication flow.
---

### **Task 3 — Protect FastAPI Backend with JWT Validation**

#### Goal  
Add a security middleware that validates Auth0 JWT tokens and permits only authorized users.

#### Requirements  
1. Install the required dependencies.  
   
2. Complete the security.py file to handle JWT authentication and authorization.
  
3. Protect the chat endpoint with JWT authentication.

#### Implementation Details
The FastAPI backend has been secured using JWT token validation. The security.py module implements JWT authentication by fetching Auth0's JSON Web Key Set (JWKS) to verify token signatures. The validate_token function uses OAuth2PasswordBearer to extract the Bearer token from the Authorization header, then decodes and validates the JWT against the configured audience and issuer. The chat endpoint is protected by adding the validate_token dependency, ensuring only authenticated users can access the chat functionality. Error handling provides appropriate HTTP status codes for various authentication failures, including expired tokens, invalid signatures, and missing or malformed tokens.

### **Task 4 - In the frontend include the token in API call**


**Expected Output:**  
- Authenticated users →  200 OK (chat response).  
- Admin → Welcome message
- Unauthorized user →  403 / 401 error.  

#### Implementation Details
The frontend automatically includes the JWT access token in all API requests to the backend. When a user sends a chat message, the ChatComponent calls the getAccessTokenSilently function from the Auth0 React SDK to obtain a fresh access token. This token is then included in the Authorization header as a Bearer token when making the POST request to the /chat endpoint. The apiService module handles the token inclusion, ensuring that every backend request is authenticated. This implementation provides seamless token management, automatically refreshing tokens as needed and maintaining secure communication between the frontend and backend.

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **Auth Protection**: Ensure the frontend is wrapped with `<Auth0Provider>` from `@auth0/auth0-react` library properly so that only authenticated users can access protected areas.
   
   *Implementation: The Auth0Provider is configured in main.tsx with all necessary parameters including domain, client ID, audience, and redirect URI. This ensures that authentication state is available throughout the React application.*

2. **Role Display**: Make sure the frontend correctly shows the chat component or the admin welcome message based on the user's assigned roles.
   
   *Implementation: The App component extracts user roles from the Auth0 user object using the configured namespace. Conditional rendering displays the ChatComponent for regular users and a special welcome message for admin users, providing role-based access control in the UI.*

3. **Token Forwarding**: Ensure the frontend includes the JWT token in every backend request for secure authentication by getting access token.
   
   *Implementation: The ChatComponent uses the getAccessTokenSilently hook to obtain fresh access tokens and passes them to the apiService. Every API call to the backend includes the Authorization header with the Bearer token, ensuring authenticated communication.*

4. **Token Validation**: Complete the security.py file to handle JWT authentication and authorization.
   
   *Implementation: The security module validates JWT tokens by fetching Auth0's JWKS, verifying the token signature, audience, and issuer. The validate_token function is used as a dependency on protected endpoints, returning the decoded token payload for successful authentication or raising appropriate HTTP exceptions for failures.*

## Implementation Summary

This practice implements a complete authentication and authorization system for the Trip & Travel Planner Agent using Auth0, React, and FastAPI. The solution includes:

- **Auth0 Configuration**: Tenant setup with SPA application, API, roles, and users
- **Frontend Integration**: React application with Auth0 SDK for login/logout and role-based UI
- **Backend Security**: FastAPI with JWT validation protecting the chat endpoint
- **Token Management**: Automatic token inclusion in API requests with silent refresh

The implementation ensures that only authenticated users can access the chat functionality, with role-based UI elements for different user types. The system provides secure communication between frontend and backend using JWT tokens validated against Auth0's public keys.

# Gemini API Configuration
```

GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
GEMINI_MODEL_NAME=gemini-2.5-flash
```
# Auth0 Configuration (for JWT authentication)
```
AUTH0_DOMAIN=your-auth0-domain.auth0.com
API_AUDIENCE=your-api-audience-identifier
ALGORITHMS=RS256
```
