import React from "react";

function ProjectHeader() {
  return (
    <div
    style={{
      background: "#c8102e", // Red gradient
      color: "white", // White text
      padding: "0.1vh 5vh 0.1vh 5vh",
      width: "90vw",
      boxShadow: "0 8px 24px rgba(0,0,0,0.25)", // Keep subtle shadow
      alignItems: "center",
      fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif", // Corporate font
    }}
    >  
      {/* LEFT: Project Overview */}
      <div>
        <h1 style={{ marginBottom: "12px" }}>Market Regime Visualizer</h1>

        <p style={{ fontSize: "18px", lineHeight: "1.5" }}>
          We logged high-frequency market data to analyze price microstructure and better understand regime behavior across different market conditions.

        </p>
      </div>
    </div>
  );
}

export default ProjectHeader;
