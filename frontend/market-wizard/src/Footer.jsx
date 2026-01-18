import React from "react";

function Footer() {
  return (
    <div
      style={{
        background: "#c8102e",
        color: "white",
        width: "97.35%",
        boxShadow: "0 -4px 12px rgba(0,0,0,0.2)",
        fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
        padding: "12px 20px",
        position: "sticky",
        bottom: 0,
        zIndex: 1000,
      }}
    >
      <div style={{ textAlign: "center" }}>
        <h3 style={{ margin: 0 }}>Contributors</h3>
        <p style={{ margin: 0 }}>
          Dan Moraru, Carter Cameron, Samuel Beaudoin, Shuya Liu
        </p>
      </div>
    </div>
  );
}

export default Footer;
