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
    return summary
      .replace(/<think>.*?<\/think>\s*\n?/gs, "")
      .split("\n")
      .map((line, index) => {

        // To prevent double formatting with **
        let trimmedLine = line.slice(2, -2).trim();
        let doubleFormatted = false;

        if (line.startsWith("**") && line.endsWith("**") && (trimmedLine.startsWith("# ") || trimmedLine.startsWith("## ") || trimmedLine.startsWith("### ") || line.startsWith("•") || line.startsWith("-"))) {
          doubleFormatted = true;
        }

        if (!doubleFormatted) {

          // Check for a title (lines starting with #)
          if (line.startsWith("# ")) {
            return <h2 key={index}>{renderBoldText(line.substring(2))}</h2>;
          }

          // Check for a heading (lines starting with ## )
          else if (line.startsWith("## ")) {
            return <h3 key={index}>{renderBoldText(line.substring(2))}</h3>;
          }

          // Check for a heading (lines starting with ### )
          else if (line.startsWith("### ")) {
            return <h4 key={index}>{renderBoldText(line.substring(2))}</h4>;
          }

          // Check for bullet points (lines starting with • or -)
          else if (line.startsWith("•") || line.startsWith("-")) {
            return (
              <ul key={index}>
                <li>{renderBoldText(line.substring(2))}</li>
              </ul>
            );
          }
        }

        // Render line
        return (
          <span key={index}>
            {renderBoldText(line)}
          </span>
        );
      });
  };

  return (
    <div className="popup-container">
      <h1>YouTube Video Summarizer</h1>
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
