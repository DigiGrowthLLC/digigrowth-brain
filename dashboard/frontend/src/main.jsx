import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import App from "./App.jsx";
import TeamSOPs from "./pages/TeamSOPs.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <BrowserRouter>
    <Routes>
      <Route path="/team" element={<TeamSOPs />} />
      <Route path="/*" element={<App />} />
    </Routes>
  </BrowserRouter>
);
