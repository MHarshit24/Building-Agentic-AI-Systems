# Travel Agent Frontend

A modern React-based chat interface for an AI-powered travel and trip planning assistant. This frontend provides an intuitive chat experience with **real-time streaming responses**, secure authentication, and role-based access control. Users interact with a travel gent to get personalized travel recommendations, itinerary suggestions, and trip planning assistance.

## Features

- **Secure Authentication**: Auth0 integration for secure login/logout with JWT token management
- **Role-Based Access Control**: Different UI views for admin and user roles
- **Modern Header Design**: Logo, title, and authentication buttons in a clean header layout
- **Interactive Chat Interface**: Clean, modern chat UI with real-time messaging
- **Real-Time Streaming**: Token-by-token streaming responses for immediate feedback
- **Markdown Support**: Rich text rendering for agent responses with full markdown formatting (headings, lists, code blocks, links, tables, etc.)
- **Session Management**: Unique session tracking for conversation continuity
- **JWT Token Integration**: All API calls authenticated with JWT tokens
- **Responsive Design**: Centered layout that works on all screen sizes
- **Loading Indicators**: Visual feedback during AI response generation
- **Auto-Scroll**: Automatically scrolls to latest messages
- **TypeScript**: Full type safety and better development experience
- **Modern UI**: Beautiful styling with hover effects and smooth interactions

## Tech Stack

- **React 19** - Modern React with hooks
- **TypeScript** - Type-safe JavaScript
- **Vite** - Fast build tool and development server
- **Auth0 React SDK** - Secure authentication and authorization
- **React Markdown** - Markdown rendering for rich text with custom styling
- **UUID** - Session ID generation
- **CSS3** - Modern styling with flexbox, animations, and markdown-specific styles

## Prerequisites

- Node.js (version 16 or higher)
- npm or yarn package manager
- Auth0 account with configured application and API
- Backend API running on `http://localhost:8000` (see backend README for setup)

---

## Configuration

### Environment Variables

Create a `.env` file in the `react-frontend` directory (same level as `package.json`) with the following variables:

```env
VITE_AUTH0_DOMAIN=your-domain.auth0.com
VITE_AUTH0_CLIENT_ID=your-client-id
VITE_AUTH0_AUDIENCE=your-api-audience
VITE_AUTH0_ROLE_NAMESPACE=https://stateful-agent.com/roles
```

**Important:**
- Replace all placeholder values with your actual Auth0 configuration
- `VITE_AUTH0_ROLE_NAMESPACE` must match the custom claim namespace used in your Auth0 configuration
- These variables are prefixed with `VITE_` to be accessible in the frontend code

---

## Installation & Setup

Before running the application, you need to:

1. **Install dependencies**
2. **Configure environment variables**
3. **Start the development server**

---

## Running the Application

### Linux/macOS

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend/react-frontend
   ```

2. **Install dependencies (if not already done):**
   ```bash
   npm install
   ```

3. **Create and configure `.env` file** (see Configuration section)

4. **Start the development server:**
   ```bash
   npm run dev
   ```

### Windows (PowerShell)

1. **Navigate to the frontend directory:**
   ```powershell
   cd frontend\react-frontend
   ```

2. **Install dependencies (if not already done):**
   ```powershell
   npm install
   ```

3. **Create and configure `.env` file** (see Configuration section)

4. **Start the development server:**
   ```powershell
   npm run dev
   ```

### Windows (Command Prompt)

1. **Navigate to the frontend directory:**
   ```cmd
   cd frontend\react-frontend
   ```

2. **Install dependencies (if not already done):**
   ```cmd
   npm install
   ```

3. **Create and configure `.env` file** (see Configuration section)

4. **Start the development server:**
   ```cmd
   npm run dev
   ```

## Usage

### Authentication Flow

1. **Landing Page:**
   - When you first open the application, you'll see a header with the app title and a "Log In" button
   - The main area displays: "Hi, Welcome to Trip and Travel Agent"

2. **Login:**
   - Click the "Log In" button in the header
   - Auth0 login popup will appear
   - Authenticate with your credentials

3. **After Login:**
   - **Admin Role**: You'll see a welcome message indicating you're logged in as an Admin. Admin users do not have access to the chat interface.
   - **Non-Admin Role**: You'll see the chat interface and can start interacting with the travel agent

4. **Logout:**
   - Click the "Log Out" button in the header to securely log out

### Starting a Conversation

**Prerequisites:** You must be logged in with a "non-admin" role to access the chat interface.

1. **Login** with a user account (not admin)
2. A unique session ID is automatically generated when the chat component loads
3. Type your travel question in the input field (e.g., "Where should I go for a beach vacation?")
4. Press Enter or click the "Send" button
5. The AI travel agent will respond with personalized recommendations, **streaming token-by-token in real-time**
6. The conversation history is maintained within the session, so you can ask follow-up questions

### Example Queries

- "I want to plan a 7-day trip to Europe"
- "What are the best beaches in Thailand?"
- "Suggest a budget-friendly vacation for a family of 4"
- "What should I pack for a winter trip to Japan?"
- "Create an itinerary for a 5-day adventure in New Zealand"

### Markdown Support

The AI responses support full markdown formatting:

- **Headings**: `# H1`, `## H2`, `### H3`
- **Bold and Italic**: `**bold**`, `*italic*`
- **Lists**: Ordered (`1. Item`) and unordered (`- Item`)
- **Code**: Inline `` `code` `` and code blocks
- **Links**: Automatic link rendering with new tab opening
- **Tables**: Full table support with styling
- **Blockquotes**: `> Quote text`
- **Horizontal Rules**: `---`

All markdown elements are beautifully styled to match the chat interface theme.

## Development

### Available Scripts

- `npm run dev` - Start development server with hot reload (runs on port 5173)


### Project Structure

```
src/
├── ChatComponent.tsx    # Main chat interface component with streaming support and JWT token integration
├── apiService.ts        # API communication layer with SSE streaming handling and JWT authentication
├── App.tsx              # Root application component with Auth0 integration and role-based routing
├── main.tsx             # Application entry point with Auth0Provider wrapper
├── assets/
│   └── react.svg        # Application logo (used in header)
├── App.css              # Global app styles
├── index.css            # Base styles and CSS reset
└── styles.css           # Chat component styles + markdown styling
```

### Key Components

#### App.tsx
The root application component that handles:
- Auth0 authentication state management
- Role extraction from JWT token claims
- Header UI with logo, title, and login/logout buttons
- Role-based UI rendering:
  - Unauthenticated: Welcome message
  - Admin: Welcome message (no chat access)
  - User: Chat component access
- Token retrieval for API calls

#### ChatComponent.tsx
The main chat interface that handles:
- Message state management with streaming updates
- User input handling
- JWT token retrieval via `getAccessTokenSilently`
- Real-time streaming API communication with authentication
- Session management with UUID
- Markdown rendering for AI responses
- Loading states and visual feedback
- Auto-scroll to latest messages

#### apiService.ts
Handles communication with the backend API:
- **JWT Authentication**: Includes `Authorization: Bearer <token>` header in all requests
- **Streaming Message Handling**: Reads Server-Sent Events (SSE) from backend
- **ReadableStream Processing**: Parses streaming chunks using Fetch API
- **Real-Time Updates**: Calls callback function for each received token
- **Error Handling**: Graceful error handling for network issues

## Streaming Implementation

The frontend implements **real-time streaming** using the Fetch API's ReadableStream:

1. **Request**: Sends POST request to `/chat` endpoint with user input and session ID
2. **Stream Reading**: Reads response body as a stream using `getReader()`
3. **Token Processing**: Decodes chunks and parses SSE format (`data: {content}`)
4. **UI Updates**: Updates message content in real-time as tokens arrive
5. **Completion**: Handles `[DONE]` marker to stop streaming



## Styling

The application uses a clean, modern design with comprehensive markdown styling:

### Header Design
- **Full-Width Header**: Spans the entire viewport width
- **Left Section**: Logo image and "Trip & Travel Agent" title
- **Right Section**: Login/Logout button
- **Background**: Light gray-blue (`#f3f7fa`) with subtle border
- **Layout**: Flexbox with space-between alignment

### Chat Interface
- **Centered Layout**: Chat container is centered on the page
- **Card-based Design**: Rounded corners and subtle shadows
- **Color-coded Messages**: 
  - User messages: Light blue background (`#e3f2fd`)
  - Agent messages: Light green background (`#f1f8e9`)
- **Responsive Input**: Flexible input area with send button
- **Loading States**: Animated loading indicator with bouncing dots

### Markdown Styling
- **Headings**: Blue colored headers with appropriate sizing
- **Code Blocks**: Gray background with border and padding
- **Inline Code**: Highlighted with pink color
- **Links**: Blue color with hover underline effect
- **Lists**: Proper indentation and spacing
- **Tables**: Bordered tables with header styling
- **Blockquotes**: Left border with italic text

### CSS Architecture

- `index.css` - Global styles and CSS reset
- `App.css` - Root container and global components
- `styles.css` - Chat-specific styling, markdown styles, and animations

## Authentication & Authorization

### Auth0 Integration

- **Login/Logout**: Handled by Auth0 React SDK with `loginWithRedirect()` and `logout()`
- **Token Management**: Automatic token refresh and silent authentication via `getAccessTokenSilently()`
- **Role Extraction**: Roles extracted from custom claims in JWT token using the configured namespace
- **Protected Routes**: Chat component only accessible to users with "user" role

### Role-Based Access Control

- **Unauthenticated**: Welcome message and login button
- **Admin Role**: Welcome message indicating admin status (no chat access)
- **User Role**: Full access to chat interface with streaming responses

### Security Features

- **JWT Token Validation**: All API calls include valid JWT tokens in Authorization header
- **Automatic Token Refresh**: Auth0 SDK handles token renewal automatically
- **Role-Based UI**: Components render based on user roles from JWT claims
- **Secure API Communication**: Authorization headers included in all streaming requests

---

## API Integration

The frontend communicates with a backend API through the `apiService.ts` module using **Server-Sent Events (SSE)** with JWT authentication:

```typescript
// Get JWT token and stream chat message
const token = await getAccessTokenSilently();
await streamChatMessage(userInput, sessionId, token, (chunk) => {
  // Handle each token as it arrives
  updateMessage(chunk);
});
```

**All API requests include:**
- `Authorization: Bearer <jwt_token>` header
- `Content-Type: application/json` header
- Request body with `input` and `session_id`

## Features in Detail

### Real-Time Streaming
- Tokens appear as they're generated by the AI
- No waiting for complete response
- Better user experience with immediate feedback

### Session Persistence
- Each browser session gets a unique UUID
- Conversation history maintained across messages
- Context-aware responses from the AI

### Error Handling
- Network errors display user-friendly messages
- Streaming interruptions are handled gracefully
- Input validation prevents empty messages

### Responsive Design
- Works on desktop and mobile devices
- Scrollable message area for long conversations
- Adaptive input area



### Build Configuration

The Vite configuration is in `vite.config.ts`. For production, you may want to:
- Set base path if deploying to a subdirectory
- Configure proxy for API calls during development
- Optimize build output

## Troubleshooting

### Common Issues

1. **Authentication Errors**:
   - Verify all Auth0 environment variables are set correctly in `.env` file
   - Ensure `VITE_AUTH0_DOMAIN`, `VITE_AUTH0_CLIENT_ID`, and `VITE_AUTH0_AUDIENCE` are configured
   - Check that Auth0 application is set up as a Single Page Application (SPA)
   - Verify Auth0 API audience matches the backend configuration

2. **Cannot Access Chat Interface**:
   - Ensure your user account has the "user" role assigned in Auth0
   - Check that `VITE_AUTH0_ROLE_NAMESPACE` matches the custom claim namespace in Auth0
   - Verify roles are included in the ID token (not just access token)

3. **JWT Token Errors**:
   - Check browser console for token validation errors
   - Ensure tokens are not expired
   - Verify API audience matches between frontend and backend

4. **Streaming Not Working**: 
   - Ensure backend is running on port 8000
   - Check browser console for CORS errors
   - Verify backend has streaming enabled
   - Ensure JWT token is being sent in Authorization header

5. **Markdown Not Rendering**: 
   - Ensure `react-markdown` is installed
   - Check that CSS styles are imported
   - Verify message content is being passed correctly

6. **Session Not Persisting**: 
   - Session IDs are stored in component state
   - Refreshing the page will create a new session
   - This is expected behavior for in-memory sessions

7. **CORS Errors**: 
   - Ensure backend CORS middleware includes `http://localhost:5173`
   - Check that backend is running and accessible
   - Verify JWT token is being sent correctly

8. **Port Already in Use**: 
   - Vite uses port 5173 by default
   - Use `npm run dev -- --port 3000` to use a different port

9. **Module Not Found Errors**:
   - Run `npm install` to ensure all dependencies are installed
   - Verify `@auth0/auth0-react` is in `package.json` dependencies
   - Clear `node_modules` and reinstall if needed: `rm -rf node_modules package-lock.json && npm install`

