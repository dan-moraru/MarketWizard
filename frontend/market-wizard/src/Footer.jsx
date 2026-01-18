import React from "react";

function Footer() {
  return (
    <div
    style={{
      background: "#c8102e", // Red gradient
      color: "white", // White text
      width: "95vw",
      boxShadow: "0 8px 24px rgba(0,0,0,0.25)", // Keep subtle shadow
      alignItems: "center",
      fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif", // Corporate font
      padding: "10px"
    }}
    >  
      <div>
        <h3 style={{margin:0}}>Contributors</h3>
        <p style={{margin:0}}>Dan Moraru, Carter Cameron, Samuel Beaudoin, Shuya Liu</p>
      </div>
    </div>
  );
}

export default Footer;
