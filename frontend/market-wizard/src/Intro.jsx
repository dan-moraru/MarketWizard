import React from "react";

function Intro() {
  return (
    <section
      style={{
        width: "100%",
        background: "#f8fafc",
        borderBottom: "1px solid #e5e7eb",
      }}
    >
      <div
        style={{
          maxWidth: "1200px",
          margin: "0 auto",
          padding: "20px 24px",
          boxSizing: "border-box",
          fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
        }}
      >
        <h2
          style={{
            margin: 0,
            marginBottom: "8px",
            fontSize: "20px",
            color: "#111827",
          }}
        >
          What is Market Wizard?
        </h2>

        <p
          style={{
            margin: 0,
            fontSize: "15px",
            lineHeight: "1.6",
            color: "#374151",
          }}
        >
          Market Wizard analyzes high-frequency bid/ask microstructure to detect
          hidden market regimes in real time. By classifying market behavior
          before price dislocations occur, it enables trading systems to adapt
          to instability instead of reacting too late.
        </p>

        <p
          style={{
            marginTop: "8px",
            fontSize: "14px",
            lineHeight: "1.6",
            color: "#4b5563",
          }}
        >
          We first logged and visualized raw market data to better understand the
          microstructure dynamics before building our machine learning models.
        </p>
      </div>
    </section>
  );
}

export default Intro;
