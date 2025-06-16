import React from "react";
import ReactDOM from "react-dom/client";

// import vite tailwind css
import "@/assets/tailwind.css";

import { ErrorView } from "./components/error-view";
import { InitialView } from "./components/initial-view";
import { LoadingView } from "./components/loading-view";
import { RecordingView } from "./components/recording-view";
import { StoppedView } from "./components/stopped-view";
import { WorkflowProvider, useWorkflow } from "./context/workflow-provider";
import { AuthProvider, useAuth } from "./context/auth-provider";

const AppContent: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const { recordingStatus, isLoading, error } = useWorkflow();

  /* wait until both async flags have resolved */
  if (isAuthenticated === null || isLoading) return <LoadingView />;
  if (error) return <ErrorView />;

  /* not signed-in → always show the initial view */
  if (!isAuthenticated) return <InitialView />;

  /* signed-in → fall through to recorder states */
  switch (recordingStatus) {
    case "recording":
      return <RecordingView />;
    case "stopped":
      return <StoppedView />;
    default:
      return <InitialView />; // idle
  }
};

const SidepanelApp: React.FC = () => {
  return (
    <React.StrictMode>
      <AuthProvider>
        <WorkflowProvider>
          <div className="h-screen flex flex-col">
            <main className="flex-grow overflow-auto">
              <AppContent />
            </main>
          </div>
        </WorkflowProvider>
      </AuthProvider>
    </React.StrictMode>
  );
};

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element not found");
}

const root = ReactDOM.createRoot(rootElement);
root.render(<SidepanelApp />);
