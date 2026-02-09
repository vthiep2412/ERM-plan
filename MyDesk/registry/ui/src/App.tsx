import { useState } from 'react';
import { Login } from './components/Login';
import { Dashboard } from './components/Dashboard';
import { Toaster, toast } from 'sonner';


function App() {
  const [password, setPassword] = useState<string | null>(() => {
    // Check session storage instead of local storage for better security
    return sessionStorage.getItem('registry_token');
  });

  const handleLogin = (pwd: string) => {
    setPassword(pwd);
    sessionStorage.setItem('registry_token', pwd);
    toast.success("Logged in!");
  };

  const handleLogout = () => {
    setPassword(null);
    sessionStorage.removeItem('registry_token');
    toast.info("Logged out");
  };

  return (
    <div className="min-h-screen bg-black text-white selection:bg-white/20 flex flex-col">
      <div className="flex-1 flex flex-col">
        <main className="flex-1 flex flex-col">
          {password === null ? (
            <Login onLogin={handleLogin} />
          ) : (
            <Dashboard password={password} onLogout={handleLogout} />
          )}
        </main>
      </div>
      <Toaster position="bottom-right" theme="dark" />
    </div>
  );
}

export default App;
