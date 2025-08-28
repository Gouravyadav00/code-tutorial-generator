import React, { useState, useEffect, useCallback, useRef } from "react";

const API_BASE = "http://localhost:8000"; // Change this to your backend URL

// Utility to make API calls with optional token and JSON body
async function apiCall(path, method = "GET", token = null, body = null) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(API_BASE + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let errorMsg = res.statusText;

    try {
      const contentType = res.headers.get("Content-Type") || "";
      if (contentType.includes("application/json")) {
        const data = await res.json();
        if (data.detail) {
          errorMsg = data.detail;
        } else if (typeof data === "string") {
          errorMsg = data;
        } else {
          // Get first key error message if present (for validation)
          const firstKey = Object.keys(data)[0];
          errorMsg = data[firstKey];
        }
      } else {
        const text = await res.text();
        if (text) errorMsg = text;
      }
    } catch (e) {
      // Ignore parse errors, keep default errorMsg
    }

    throw new Error(errorMsg || "Unknown error");
  }

  // If 204 No Content or empty response
  if (res.status === 204) return null;

  const contentType = res.headers.get("Content-Type") || "";
  if (contentType.includes("application/json")) {
    return await res.json();
  } else {
    return await res.text();
  }
}

export default function App() {
  // Authentication and user
  const [token, setToken] = useState(localStorage.getItem("token"));
  const [userEmail, setUserEmail] = useState(null);

  // UI State
  const [view, setView] = useState("login"); // "login", "register", "dashboard"

  // Form fields
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");

  const [repoUrl, setRepoUrl] = useState("");
  const [language, setLanguage] = useState("english");

  // Job info
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);

  // Error message display
  const [error, setError] = useState(null);

  // Reference for autoscroll in logs
  const logsEndRef = useRef(null);

  // Reset errors when changing views or inputs
  useEffect(() => { setError(null); }, [view]);
  useEffect(() => { if (error) setError(null); }, [email, fullName, password, repoUrl]);

  // On login success, fetch user info or set email directly
  useEffect(() => {
    if (!token) {
      setUserEmail(null);
      return;
    }
    // We can decode email from token or fetch /auth/me
    // For simplicity, set from stored email after login/register
    // Alternative: fetch('/auth/me') here if needed
    if (userEmail) return;
    // Just keep existing email or leave null
  }, [token, userEmail]);

  // Login handler
  const onLogin = useCallback(async () => {
    setError(null);
    if (!email || !password) {
      setError("Please enter both email and password.");
      return;
    }
    try {
      const data = await apiCall("/auth/login", "POST", null, { email, password });
      setToken(data.access_token);
      localStorage.setItem("token", data.access_token);
      setUserEmail(email);
      setView("dashboard");
    } catch (e) {
      setError(e.message || "Login failed.");
    }
  }, [email, password]);

  // Register handler
  const onRegister = useCallback(async () => {
    setError(null);
    if (!email || !password || !fullName) {
      setError("Please fill all fields (email, name, password).");
      return;
    }
    try {
      const data = await apiCall("/auth/register", "POST", null, { email, password, full_name: fullName });
      setToken(data.access_token);
      localStorage.setItem("token", data.access_token);
      setUserEmail(email);
      setView("dashboard");
    } catch (e) {
      setError(e.message || "Registration failed.");
    }
  }, [email, password, fullName]);

  // Logout handler
  const onLogout = () => {
    setToken(null);
    localStorage.removeItem("token");
    setUserEmail(null);
    setEmail("");
    setFullName("");
    setPassword("");
    setRepoUrl("");
    setLanguage("english");
    setJobId(null);
    setJobStatus(null);
    setError(null);
    setView("login");
  };

  // Submit tutorial generation job
  const onGenerate = useCallback(async () => {
    setError(null);
    setJobStatus(null);
    setJobId(null);
    if (!repoUrl.trim()) {
      setError("Please enter a GitHub repository URL or local directory path.");
      return;
    }
    try {
      const config = {
        repo_url: repoUrl.trim(),
        language,
        use_cache: true,
        max_abstractions: 10,
      };
      const data = await apiCall("/generate", "POST", token, config);
      setJobId(data.job_id);
    } catch (e) {
      setError(e.message || "Failed to start tutorial generation.");
    }
  }, [repoUrl, language, token]);

  // Poll job status every 3 seconds if jobId set and logged in
  useEffect(() => {
    if (!token || !jobId) return;
    let canceled = false;

    async function poll() {
      try {
        const status = await apiCall(`/status/${jobId}`, "GET", token);
        if (canceled) return;
        setJobStatus(status);
        if (status.status === "completed" || status.status === "failed") return; // stop polling
        setTimeout(poll, 3000);
      } catch {
        // If error fetching status, stop polling
      }
    }
    poll();
    return () => { canceled = true; };
  }, [jobId, token]);

  // Scroll logs to bottom when they update
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [jobStatus?.logs]);

  // Download tutorial HTML file from backend
  const downloadTutorial = async () => {
    if (!jobId || !token) return alert("No tutorial to download.");
    try {
      const res = await fetch(`${API_BASE}/jobs/${jobId}/download/html`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Failed to download tutorial HTML.");
      }
      const html = await res.text();
      const blob = new Blob([html], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `tutorial_${jobId}.html`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(e.message || "Download failed.");
    }
  };

  // Handlers for form input and pressing Enter
  const handleKeyDownAuth = e => {
    if (e.key === "Enter") {
      e.preventDefault();
      view === "login" ? onLogin() : onRegister();
    }
  };

  const handleKeyDownGenerate = e => {
    if (e.key === "Enter") {
      e.preventDefault();
      onGenerate();
    }
  };

  // UI Rendering
  if (!token) {
    return (
      <div className="auth-container">
        <h1>{view === "login" ? "Login" : "Register"}</h1>
        <form
          onSubmit={e => {
            e.preventDefault();
            view === "login" ? onLogin() : onRegister();
          }}
          className="auth-form"
        >
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => { setEmail(e.target.value); if(error) setError(null); }}
            required
            onKeyDown={handleKeyDownAuth}
            autoComplete="username"
          />
          {view === "register" && (
            <input
              type="text"
              placeholder="Full Name"
              value={fullName}
              onChange={e => { setFullName(e.target.value); if(error) setError(null); }}
              required
              onKeyDown={handleKeyDownAuth}
            />
          )}
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => { setPassword(e.target.value); if(error) setError(null); }}
            required
            onKeyDown={handleKeyDownAuth}
            autoComplete={view === "login" ? "current-password" : "new-password"}
          />
          <button type="submit">{view === "login" ? "Login" : "Register"}</button>
        </form>
        {error && <div className="error">{error}</div>}
        <p className="toggle-link">
          {view === "login" ? "Don't have an account?" : "Already have an account?"}{" "}
          <button
            className="link-button"
            onClick={() => {
              setView(view === "login" ? "register" : "login");
              setError(null);
              setEmail("");
              setPassword("");
              setFullName("");
            }}
          >
            {view === "login" ? "Register" : "Login"}
          </button>
        </p>
        <style>{`
          body {
            margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
              Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
            background: #eef6fb;
            color: #222;
          }
          .auth-container {
            max-width: 400px;
            margin: 80px auto;
            padding: 30px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 0 12px rgba(0,0,0,0.1);
            text-align: center;
          }
          h1 {
            margin-bottom: 24px;
            color: #007acc;
          }
          .auth-form input {
            width: 100%;
            padding: 12px;
            margin-bottom: 15px;
            font-size: 1rem;
            border-radius: 4px;
            border: 1px solid #ccc;
            box-sizing: border-box;
            outline-offset: 2px;
          }
          .auth-form input:focus {
            border-color: #007acc;
            outline: 2px solid #80bdff;
          }
          .auth-form button {
            width: 100%;
            padding: 12px;
            font-size: 1.1rem;
            background-color: #007acc;
            border: none;
            border-radius: 4px;
            color: white;
            cursor: pointer;
            transition: background-color 0.25s ease-in-out;
          }
          .auth-form button:hover {
            background-color: #005a99;
          }
          .error {
            margin-top: 10px;
            color: #d93025;
            font-weight: 600;
          }
          .toggle-link {
            margin-top: 20px;
          }
          .link-button {
            background: none;
            border: none;
            color: #007acc;
            cursor: pointer;
            font-size: 1rem;
            text-decoration: underline;
            padding: 0;
          }
          .link-button:hover {
            color: #005a99;
          }
        `}</style>
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      <header>
        <h1>Tutorial Generator Dashboard</h1>
        <div>
          <strong>{userEmail}</strong>
          <button className="logout-btn" onClick={onLogout}>
            Logout
          </button>
        </div>
      </header>

      <section className="generate-section">
        <h2>Generate Tutorial</h2>
        <input
          type="text"
          placeholder="GitHub repo URL or local directory path"
          value={repoUrl}
          onChange={e => { setRepoUrl(e.target.value); if(error) setError(null); }}
          onKeyDown={handleKeyDownGenerate}
        />
        <select value={language} onChange={e => setLanguage(e.target.value)}>
          <option value="english">English</option>
          {/* add more if supported */}
        </select>
        <button onClick={onGenerate}>Start Generation</button>
        {error && <div className="error">{error}</div>}
      </section>

      {jobId && (
        <section className="status-section">
          <h2>Job Status (ID: {jobId})</h2>
          {jobStatus ? (
            <>
              <p>
                Status: <strong>{jobStatus.status}</strong>
              </p>
              <p>
                Progress: <strong>{jobStatus.progress}%</strong>
              </p>
              <p>
                Current Step: <em>{jobStatus.current_step || "N/A"}</em>
              </p>
              {jobStatus.error && <p className="error">Error: {jobStatus.error}</p>}

              <div className="logs-container">
                <h3>Logs</h3>
                <div className="logs" aria-live="polite" aria-atomic="false">
                  {jobStatus.logs && jobStatus.logs.length > 0 ? (
                    jobStatus.logs.map((entry, idx) => (
                      <div
                        key={idx}
                        className={`log-entry log-${entry.level?.toLowerCase() || "info"}`}
                      >
                        <span className="timestamp">
                          [{new Date(entry.timestamp).toLocaleTimeString()}]
                        </span>{" "}
                        {entry.message}
                      </div>
                    ))
                  ) : (
                    <p>No logs yet.</p>
                  )}
                  <div ref={logsEndRef}></div>
                </div>
              </div>

              {jobStatus.status === "completed" && (
                <>
                  <p className="success">Generation completed successfully</p>
                  <button className="download-btn" onClick={downloadTutorial}>
                    Download Tutorial HTML
                  </button>
                </>
              )}

              {jobStatus.status === "failed" && (
                <p className="error">
                  Generation failed. Please try again or contact support.
                </p>
              )}
            </>
          ) : (
            <p>Loading job status...</p>
          )}
        </section>
      )}

      <style>{`
        .dashboard-container {
          max-width: 800px;
          margin: 40px auto;
          padding: 20px;
          background: #f9fbfc;
          border-radius: 10px;
          box-shadow: 0 0 12px rgba(0,0,0,0.1);
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
            Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
          color: #222;
        }
        header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
        }
        header h1 {
          color: #007acc;
          margin: 0;
          font-weight: 700;
        }
        header > div {
          font-weight: 600;
          font-size: 0.9rem;
          color: #444;
        }
        .logout-btn {
          margin-left: 15px;
          background-color: #d93025;
          color: white;
          border: none;
          border-radius: 5px;
          padding: 8px 18px;
          font-weight: 700;
          cursor: pointer;
          transition: background-color 0.3s ease;
        }
        .logout-btn:hover {
          background-color: #b1271b;
        }
        .generate-section {
          margin-bottom: 36px;
        }
        .generate-section input,
        .generate-section select,
        .generate-section button {
          width: 100%;
          max-width: 400px;
          padding: 10px 14px;
          font-size: 1rem;
          border-radius: 5px;
          border: 1px solid #ccc;
          margin-bottom: 12px;
          box-sizing: border-box;
        }
        .generate-section input:focus,
        .generate-section select:focus {
          outline: 2px solid #007acc;
          border-color: #007acc;
        }
        .generate-section button {
          background-color: #007acc;
          color: white;
          cursor: pointer;
          font-weight: 700;
          border: none;
          transition: background-color 0.3s ease;
        }
        .generate-section button:hover {
          background-color: #005fa0;
        }
        .status-section {
          background: white;
          border-radius: 10px;
          padding: 20px;
          box-shadow: inset 0 0 12px rgba(0,0,0,0.06);
        }
        .logs-container {
          margin-top: 16px;
          max-height: 240px;
          overflow-y: auto;
          border: 1px solid #ccc;
          border-radius: 6px;
          background-color: #f5f7fa;
          font-family: monospace;
          padding: 12px;
          font-size: 0.9rem;
          color: #333;
        }
        .log-entry {
          margin-bottom: 8px;
          white-space: pre-wrap;
        }
        .log-info {
          color: #2185d0;
        }
        .log-warning {
          color: #ff851b;
        }
        .log-error {
          color: #db2828;
          font-weight: 700;
        }
        .timestamp {
          color: #888;
          margin-right: 6px;
          font-weight: 600;
        }
        .error {
          color: #d93025;
          font-weight: 600;
          margin-top: 10px;
        }
        .success {
          color: #28a745;
          font-weight: 600;
          margin-top: 10px;
        }
        .download-btn {
          margin-top: 14px;
          background-color: #28a745;
          color: white;
          border: none;
          border-radius: 6px;
          padding: 10px 18px;
          font-weight: 700;
          cursor: pointer;
          transition: background-color 0.3s ease;
        }
        .download-btn:hover {
          background-color: #218838;
        }
      `}</style>
    </div>
  );
}
