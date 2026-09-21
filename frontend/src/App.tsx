import { useAuth } from "./context/AuthContext";
import AuthPage from "./pages/AuthPage";
import ChatPage from "./pages/ChatPage";

export default function App() {
  const { session } = useAuth();

  // Gate: unauthenticated users see login/register; authenticated users chat.
  if (!session) return <AuthPage />;
  return <ChatPage session={session} />;
}
