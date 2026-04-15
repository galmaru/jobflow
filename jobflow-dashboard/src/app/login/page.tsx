"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [token,  setToken]  = useState("");
  const [error,  setError]  = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    const res = await fetch("/api/jobs", {
      headers: { Authorization: `Bearer ${token}` },
    });

    setLoading(false);

    if (res.ok) {
      localStorage.setItem("jobflow_token", token);
      router.push("/");
    } else {
      setError("토큰이 올바르지 않습니다.");
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-sm">
        <h1 className="text-2xl font-bold text-gray-800 mb-1">JobFlow</h1>
        <p className="text-sm text-gray-500 mb-6">대시보드에 접속하려면 토큰을 입력하세요.</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="token" className="block text-sm font-medium text-gray-700 mb-1">
              Bearer Token
            </label>
            <input
              id="token"
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="xxxxxxxxxxxxxxxx"
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={loading || !token}
            className="w-full bg-blue-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "확인 중…" : "접속"}
          </button>
        </form>
      </div>
    </main>
  );
}
