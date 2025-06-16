import React from "react";
import { useWorkflow } from "../context/workflow-provider";
import { Button } from "@/components/ui/button";

export const ErrorView: React.FC = () => {
  const { error, fetchWorkflowData, startRecording } = useWorkflow();

  const handleRetry = () => {
    // Try fetching data again
    fetchWorkflowData();
  };

  const handleStartNew = () => {
    // Reset state and start recording
    startRecording();
  };

  return (
    <div className="flex flex-col items-center justify-center h-full space-y-4 p-4 text-center">
      <h2 className="text-lg font-semibold text-destructive">
        An Error Occurred
      </h2>
      <p className="text-sm text-muted-foreground">
        {error || "An unexpected error occurred."}
      </p>
      <div className="flex space-x-2">
        <Button variant="outline" onClick={handleRetry}>
          Retry Load
        </Button>
        <Button variant="secondary" onClick={handleStartNew}>
          Start New Recording
        </Button>
      </div>
    </div>
  );
};
