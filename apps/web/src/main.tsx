import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ConfirmWizardProvider } from "./components/ConfirmWizard";
import { ToastProvider } from "./components/ToastProvider";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ConfirmWizardProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </ConfirmWizardProvider>
  </StrictMode>,
);
