import { useState } from 'react';
import { Lock } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../lib/api';

interface LoginProps {
    onLogin: (password: string) => void;
}

export function Login({ onLogin }: LoginProps) {
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        
        try {
            await api.discover(password);
            toast.success("Access Granted");
            onLogin(password);
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e);
            if (msg.includes("Access Denied")) {
                toast.error("Invalid password", {
                    className: "!bg-red-950/50 !border-red-500 !text-red-200 !shadow-[0_0_30px_rgba(220,38,38,0.5)]"
                });
            } else {
                toast.error("Login failed: " + msg, {
                    className: "!bg-red-950/50 !border-red-500 !text-red-200 !shadow-[0_0_30px_rgba(220,38,38,0.5)]"
                });
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex min-h-screen items-center justify-center bg-black text-white">
            <div className="w-full max-w-sm p-8 space-y-6 bg-zinc-900 border border-zinc-800 rounded-xl shadow-2xl">
                <div className="flex flex-col items-center space-y-2">
                    <div className="p-3 bg-zinc-800 rounded-full">
                        <Lock className="w-6 h-6 text-white" />
                    </div>
                    <h1 className="text-2xl font-bold tracking-tight">Registry Access</h1>
                    <p className="text-sm text-zinc-400">Enter master password to continue</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="space-y-2">
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="Master Password"
                            className="w-full px-4 py-2 bg-black border border-zinc-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-white/20 transition-all text-sm"
                            autoFocus
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={!password || loading}
                        className="w-full py-2 bg-white text-black font-medium rounded-lg hover:bg-zinc-200 hover:text-black transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? "Verifying..." : "Access Dashboard"}
                    </button>
                </form>
            </div>
        </div>
    );
}
