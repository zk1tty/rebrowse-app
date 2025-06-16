import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAppContext } from '@/contexts/AppContext';
import { Play, Loader2, ShieldCheck, AlertTriangle } from 'lucide-react';
import { hasValidSessionToken } from '@/utils/authUtils';
import SessionStatus from '@/components/SessionStatus';

interface WorkflowInput {
  id: string;
  name: string;
  type: 'string' | 'number' | 'boolean';
  required: boolean;
  value: any;
}

export function RunWorkflowDialog() {
  const {
    executeWorkflow,
    activeDialog,
    setActiveDialog,
    currentWorkflowData,
    workflowStatus,
    currentUserSessionToken,
    isCurrentWorkflowPublic
  } = useAppContext();
  const [inputs, setInputs] = useState<WorkflowInput[]>([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  
  const hasSessionToken = hasValidSessionToken(currentUserSessionToken);
  const canExecute = hasSessionToken || isCurrentWorkflowPublic; // Can execute if authenticated OR if it's a public workflow

  useEffect(() => {
    if (currentWorkflowData && activeDialog === 'run') {
      // Use input_schema from the workflow
      const schemaInputs: WorkflowInput[] =
        currentWorkflowData.input_schema.map((input) => ({
          id: input.name,
          name: input.name,
          type: input.type,
          required: input.required,
          value: '',
        }));
      setInputs(schemaInputs);
      setValidationError(null);
    }
  }, [currentWorkflowData, activeDialog]);

  const updateInput = (id: string, value: string) => {
    setInputs(
      inputs.map((input) => (input.id === id ? { ...input, value } : input))
    );
    setValidationError(null);
  };

  const validateInputs = () => {
    const missingInputs = inputs.filter(
      (input) => input.required && !input.value
    );
    if (missingInputs.length > 0) {
      setValidationError(
        `Missing required inputs: ${missingInputs
          .map((f) => f.name)
          .join(', ')}`
      );
      return false;
    }
    return true;
  };

  const execute = async () => {
    if (!validateInputs()) return;
    
    if (!canExecute) {
      setValidationError('Authentication required to execute workflows. Please login through the Chrome extension.');
      return;
    }

    setIsExecuting(true);
    setValidationError(null);

    try {
      // Map the input values to their corresponding places in the workflow
      const inputFields = inputs.map((input) => ({
        name: input.name,
        type: input.type,
        required: input.required,
        value: input.value,
      }));

      const workflowId = currentWorkflowData!.id;
      if (!workflowId) {
        throw new Error('Workflow ID not available');
      }
      await executeWorkflow(workflowId, inputFields);
      setActiveDialog(null);
    } catch (error) {
      console.error('Failed to execute workflow:', error);
      
      // Provide user-friendly error messages
      let errorMessage = 'Failed to execute workflow';
      
      if (error instanceof Error) {
        const errorText = error.message.toLowerCase();
        
        // Handle authentication-related errors
        if (errorText.includes('jwt') || errorText.includes('session authentication') || errorText.includes('unauthorized')) {
          errorMessage = 'Please login through the Chrome extension to execute workflows.';
        } else if (errorText.includes('session token') || errorText.includes('invalid token')) {
          errorMessage = 'Your session has expired. Please login again through the Chrome extension.';
        } else if (errorText.includes('not found') || errorText.includes('404')) {
          errorMessage = 'Workflow not found. Please refresh the page and try again.';
        } else {
          // Use the original error message for other cases
          errorMessage = error.message;
        }
      }
      
      setValidationError(errorMessage);
    } finally {
      setIsExecuting(false);
    }
  };

  if (!currentWorkflowData) return null;

  return (
    <Dialog
      open={activeDialog === 'run'}
      onOpenChange={(open) => {
        if (!open && !isExecuting) {
          setActiveDialog(null);
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold">
            Run Workflow: {currentWorkflowData.name}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Session Status for Execution */}
          <SessionStatus compact={true} className="mb-4" />
          
          {!canExecute && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-4">
              <div className="flex items-center space-x-2">
                <AlertTriangle className="h-4 w-4 text-yellow-600" />
                <span className="text-yellow-800 font-medium">Authentication Required</span>
              </div>
              <p className="text-yellow-700 text-sm mt-1">
                Please login through the Chrome extension to execute workflows.
              </p>
            </div>
          )}
          
          <p className="text-gray-600">
            Configure the input values for this workflow execution:
          </p>

          <div className="space-y-4">
            {inputs.map((input) => (
              <div key={input.id} className="space-y-2">
                <Label htmlFor={input.id} className="text-sm font-medium">
                  {input.name}{' '}
                  {input.required && <span className="text-red-500">*</span>}
                </Label>
                <Input
                  id={input.id}
                  value={input.value}
                  onChange={(e) => updateInput(input.id, e.target.value)}
                  placeholder={`Enter ${input.name}`}
                  className="w-full"
                  required={input.required}
                  disabled={isExecuting}
                />
              </div>
            ))}

            {inputs.length === 0 && (
              <p className="text-gray-500 text-center py-8">
                This workflow doesn't require any input parameters.
              </p>
            )}
          </div>

          {validationError && (
            <div className="p-2 rounded bg-[#fff2f0] text-[#ff4d4f] border border-[#ffccc7]">
              <strong>Error:</strong> {validationError}
            </div>
          )}

          <p className="text-gray-500 text-sm">
            Fields marked with <span className="text-red-500">*</span> are
            required.
          </p>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setActiveDialog(null)}
            disabled={isExecuting}
          >
            Cancel
          </Button>
          <Button
            onClick={execute}
            disabled={isExecuting || workflowStatus === 'running' || !canExecute}
            className="bg-purple-600 hover:bg-purple-700 text-white flex items-center gap-2 disabled:opacity-50"
          >
            {isExecuting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Executing...
              </>
            ) : !canExecute ? (
              <>
                <AlertTriangle className="w-4 h-4" />
                Login Required
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Execute Workflow
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
