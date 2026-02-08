import { useState } from 'react';
import { Login } from './components/Login';
import { Dashboard } from './components/Dashboard';
import { Toaster } from 'sonner';

function App() {
  const [password, setPassword] = useState<string | null>(() => {
    return localStorage.getItem('registry_pwd');
  });

  const handleLogin = (pwd: string) => {
    setPassword(pwd);
    localStorage.setItem('registry_pwd', pwd);
  };

  const handleLogout = () => {
    setPassword(null);
    localStorage.removeItem('registry_pwd');
  };

  return (
    <>
      <Toaster position="top-right" theme="dark" richColors />
      {!password ? (
        <Login onLogin={handleLogin} />
      ) : (
        <Dashboard password={password} onLogout={handleLogout} />
      )}
    </>
  );
}

export default App;
