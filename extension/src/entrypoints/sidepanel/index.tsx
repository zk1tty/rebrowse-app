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
  const { recordingStatus, isLoading, error, activeView, routeOverride } = useWorkflow();

  /* wait until both async flags have resolved */
  if (isAuthenticated === null || isLoading) return <LoadingView />;
  if (error) return <ErrorView />;

  /* not signed-in → always show the initial view */
  if (!isAuthenticated) return <InitialView />;

  /* temporary route override (e.g., back button from stopped view) */
  if (routeOverride === 'initial') {
    return <InitialView />;
  }

  /* signed-in → route by activeView first, then recorder states */
  if (activeView === "sync") {
    const SyncBrowserView = React.lazy(() => import("./components/sync-browser-view.tsx"));
    return (
      <React.Suspense fallback={<LoadingView />}>
        <SyncBrowserView />
      </React.Suspense>
    );
  }

  if (activeView === "session") {
    // Reuse the session token panel from StoppedView, but as a standalone lightweight view
    const SessionTokenPanel = React.lazy(() => import("./components/session-token-view.tsx"));
    return (
      <React.Suspense fallback={<LoadingView />}>
        <SessionTokenPanel />
      </React.Suspense>
    );
  }

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
