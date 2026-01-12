import React, { useState, useEffect } from 'react';
import './styles.css';

const App = () => {
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState('');
  const [error, setError] = useState('');
  const [useLocalInference, setUseLocalInference] = useState(false);

  // Need to comment out chrome storage code in dev environment

  // Load saved state from chrome storage when the popup is opened
  useEffect(() => {
    chrome.storage.local.get(['loading', 'summary', 'error', 'useLocalInference'], (result) => {
      if (result.loading !== undefined) setLoading(result.loading);
      if (result.summary) setSummary(result.summary);
      if (result.error) setError(result.error);
      if (result.useLocalInference !== undefined) setUseLocalInference(result.useLocalInference);
    });
  }, []);

  // Save state to chrome storage whenever it changes
  useEffect(() => {
    chrome.storage.local.set({ loading, summary, error, useLocalInference });
  }, [loading, summary, error, useLocalInference]);

  // Button function to generate summary of YouTube video
  const handleSummarize = async () => {
    setLoading(true);
    setError('');
    setSummary('');

    try {
      const videoUrl = await getCurrentTabUrl();
      console.log("Retrieved video URL:", videoUrl);

      const response = await fetch('http://localhost:8000/summarize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video_url: videoUrl,
          use_local: useLocalInference
        }),
      });

      if (!response.body) {
        throw new Error("Streaming not supported in this browser.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        const chunk = decoder.decode(value);
        setSummary((prev) => prev + chunk);
      }
    } catch (err) {
      console.error("Error during streaming summarization:", err);
      setError('Error summarizing video. Please try again.');
    } finally {
      setLoading(false);
      console.log("Summarization process complete.");
    }
  };

  // Button function to clear summary area
  const handleReset = () => {
    setSummary('');
    setError('');
    setLoading(false);
  };

  // Function to identify open tab
  const getCurrentTabUrl = async () => {
    return new Promise((resolve, reject) => {
      try {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
          if (tabs && tabs.length > 0) {
            console.log("Active tab found:", tabs[0].url);
            resolve(tabs[0].url);
          } else {
            console.log("No active tab found.");
            reject('No active tab found');
          }
        });
      } catch (error) {
        console.error("Error retrieving current tab URL:", error);
        reject(error);
      }
    });
  };

  // Helper function to render bold text within a string
  const renderBoldText = (text) => {
    const parts = text.split(/(\*\*.*?\*\*)/g);

    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <b key={i}>{part.slice(2, -2)}</b>;
      }

      return part;
    });
  };

  // Function to format summary into JSX
  const renderSummary = () => {
    const cleaned = summary.replace(/<think>.*?<\/think>\s*\n?/gs, "");
    const lines = cleaned.split(/\r?\n/);

    const elements = [];
    let listBuffer = [];

    const flushList = (keyBase) => {
      if (!listBuffer.length) return;
      const items = listBuffer;
      listBuffer = [];
      elements.push(
        <ul key={`ul-${keyBase}`} className="summary-list">
          {items.map((text, i) => (
            <li key={`li-${keyBase}-${i}`}>{renderBoldText(text)}</li>
          ))}
        </ul>
      );
    };

    lines.forEach((rawLine, index) => {
      let line = rawLine;

      // If a structural line is wrapped in **...**, unwrap it to avoid double-formatting
      if (line.startsWith("**") && line.endsWith("**")) {
        const inner = line.slice(2, -2).trim();

        if (
          inner.startsWith("# ") ||
          inner.startsWith("## ") ||
          inner.startsWith("### ") ||
          inner.startsWith("•") ||
          inner.startsWith("-") ||
          inner.startsWith("+") ||
          inner.startsWith("*")
        ) {
          line = inner;
        }
      }

      // Headings
      if (line.startsWith("# ")) {
        flushList(index);
        elements.push(<h2 key={`h2-${index}`}>{renderBoldText(line.substring(2))}</h2>);
        return;
      }

      if (line.startsWith("## ")) {
        flushList(index);
        elements.push(<h3 key={`h3-${index}`}>{renderBoldText(line.substring(3))}</h3>);
        return;
      }

      if (line.startsWith("### ")) {
        flushList(index);
        elements.push(<h4 key={`h4-${index}`}>{renderBoldText(line.substring(4))}</h4>);
        return;
      }

      // Bullets: •, -, +, *
      const bulletMatch = line.match(/^\s*([•*+-])\s+(.*)$/);
      if (bulletMatch) {
        const marker = bulletMatch[1];
        const content = (bulletMatch[2] || "").trim();

        // Some models emit multiple sub-bullets on one line
        if (marker === "+" && /\s\+\s/.test(content)) {
          const segments = content.split(/\s+\+\s+/).map((s) => s.trim()).filter(Boolean);
          const colonSegments = segments.filter((s) => /^[A-Z0-9][^:]{0,70}:/.test(s)).length;

          if (segments.length >= 2 && colonSegments >= 2) {
            segments.forEach((s) => listBuffer.push(s));
            return;
          }
        }

        listBuffer.push(content);
        return;
      }

      // Normal lines / spacing
      flushList(index);
      if (!line.trim()) {
        elements.push(<div key={`sp-${index}`} className="summary-spacer" />);
        return;
      }

      elements.push(
        <div key={`ln-${index}`} className="summary-line">
          {renderBoldText(line)}
        </div>
      );
    });

    flushList("end");
    return elements;
  };

  return (
    <div className="popup-container">
      <h1>YouTube Insights Analyzer</h1>
      <div className="toggle-container">
        <label className="toggle-switch">
          <input
            type="checkbox"
            checked={useLocalInference}
            onChange={(e) => {
              setUseLocalInference(e.target.checked);
              console.log("Local:", e.target.checked);
            }}
          />
          <span className="slider"></span>
          <span className="labels" data-on="Local" data-off="Remote"></span>
        </label>
      </div>
      <br />
      <div className="button-container">
        <button onClick={handleSummarize} disabled={loading}>
          {loading ? 'Summarizing...' : 'Summarize Video'}
        </button>
        <button onClick={handleReset} className="reset-btn">
          Reset Summary
        </button>
      </div>
      {loading && !useLocalInference && <div className="spinner"></div>}
      {summary && (
        <div className="summary">
          <div>{renderSummary()}</div>
        </div>
      )}
      {error && <div className="error">{error}</div>}
    </div>
  );
};

export default App;
