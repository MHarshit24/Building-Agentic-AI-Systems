import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LoginPage from "./routes/LoginPage";
import SignUpPage from "./routes/SignUpPage";
import ForgotPasswordPage from "./routes/ForgotPasswordPage";
import ResetPasswordPage from "./routes/ResetPasswordPage";
import AppShell from "./routes/AppShell";
import ChatPage from "./routes/ChatPage";
import CustomersPage from "./routes/CustomersPage";
import DocumentsPage from "./routes/DocumentsPage";
import MetricsPage from "./routes/MetricsPage";
import UsersPage from "./routes/UsersPage";
import { ProtectedRoute } from "./components/layout/ProtectedRoute";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignUpPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />

          <Route element={<ProtectedRoute allowedRoles={["support_agent", "admin"]} />}>
            <Route element={<AppShell />}>
              <Route index element={<ChatPage />} />
              <Route path="/chat/:conversationId" element={<ChatPage />} />
              <Route path="/metrics" element={<MetricsPage />} />
              <Route path="/customers" element={<CustomersPage />} />

              <Route element={<ProtectedRoute allowedRoles={["admin"]} />}>
                <Route path="/documents" element={<DocumentsPage />} />
                <Route path="/users" element={<UsersPage />} />
              </Route>
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
