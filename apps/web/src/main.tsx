import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ConfirmWizardProvider } from "./components/ConfirmWizard";
import { ToastProvider } from "./components/ToastProvider";
import { I18nProvider } from "./utils/i18nContext";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider>
      <ConfirmWizardProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </ConfirmWizardProvider>
    </I18nProvider>
  </StrictMode>,
);
