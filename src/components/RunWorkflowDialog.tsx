import { useState, useEffect } from 'react';
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { useAppContext } from '@/contexts/AppContext';
import { Loader2, Cloud, Monitor, Copy, Check, Eye } from 'lucide-react';
// Removed: hasValidSessionToken, isAnonymousUser (anonymous ensured on-demand)
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
    // currentUserSessionToken,
    // isCurrentWorkflowPublic
  } = useAppContext();
  const [inputs, setInputs] = useState<WorkflowInput[]>([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [executionMode, setExecutionMode] = useState<'cloud-run' | 'local-run'>('cloud-run');
  const [copied, setCopied] = useState(false);
  const [visualMode, setVisualMode] = useState(true);
  
  // Authentication is ensured on-demand before execution

  // Removed anonymous status check; session ensured on-demand

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

  const copyInstallCommand = async () => {
    const command = 'curl -LsSf https://script.rebrowse.me/install.sh | sh';
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000); // Reset after 2 seconds
    } catch (err) {
      console.error('Failed to copy command:', err);
    }
  };

  const execute = async () => {
    if (!validateInputs()) return;
    
    // Removed authentication check - always allow execution
    
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

      // Use workflow ID if available, otherwise fallback to name
      const workflowId = currentWorkflowData!.id || currentWorkflowData!.name;
      if (!workflowId) {
        throw new Error('Workflow ID or name not available');
      }
      
      // Execute workflow with parameters
      
      await executeWorkflow(workflowId, inputFields, executionMode, visualMode);
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
          
          {/* Removed authentication warning banner */}
          
          {/* Execution Mode Selection */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">Execution Mode</Label>
            <Select value={executionMode} onValueChange={(value: 'cloud-run' | 'local-run') => setExecutionMode(value)}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select execution mode" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="cloud-run">
                  <div className="flex items-center space-x-2">
                    <Cloud className="h-4 w-4 text-blue-500" />
                    <span>Cloud Run</span>
                    <span className="text-xs text-gray-500 ml-2">(on Rebrowse Cloud)</span>
                  </div>
                </SelectItem>
                <SelectItem value="local-run">
                  <div className="flex items-center space-x-2">
                    <Monitor className="h-4 w-4 text-green-500" />
                    <span>Local Run</span>
                    <span className="text-xs text-gray-500 ml-2">(on Your Local Machine)</span>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
            <div className="text-xs text-gray-500">
              {executionMode === 'local-run' && (
                <div className="space-y-2">
                  <p>🖥️ Runs on your local machine - requires set-up.</p>
                  <div className="bg-gray-200 border border-gray-200 rounded-lg p-3 mt-2">
                    <p className="text-gray-800 font-medium text-sm mb-2">📋 Local Setup</p>
                    <p className="text-gray-700 text-xs mb-2">Open terminal and run this command:</p>
                    <div className="relative">
                      <div className="bg-gray-900 text-green-400 p-2 pr-12 rounded font-mono text-xs overflow-x-auto">
                        <code>curl -LsSf https://script.rebrowse.me/install.sh | sh</code>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={copyInstallCommand}
                        className="absolute right-1 top-1 h-8 w-8 p-0 hover:bg-gray-700"
                        title="Copy command"
                      >
                        {copied ? (
                          <Check className="h-3 w-3 text-green-400" />
                        ) : (
                          <Copy className="h-3 w-3 text-gray-400 hover:text-white" />
                        )}
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
           </div>

           {/* Visual Mode Toggle */}
           <div className="flex items-center justify-between p-3 border rounded-lg bg-gray-50">
             <div className="flex items-center space-x-2">
               <Eye className="h-4 w-4 text-gray-700" />
               <div>
                 <Label className="text-sm text-gray-900 font-medium">View Mode</Label>
                 <p className="text-xs text-gray-600">Watch AI browsing in realtime</p>
               </div>
             </div>
             <Switch
               checked={visualMode}
               onCheckedChange={setVisualMode}
               disabled={isExecuting}
             />
           </div>
           
           <p className="text-gray-600">
             Configure the input variables:
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
            disabled={isExecuting || workflowStatus === 'running'}
            className={`${
              visualMode
                ? 'bg-purple-600 hover:bg-purple-700'
                : executionMode === 'cloud-run' 
                  ? 'bg-blue-600 hover:bg-blue-700' 
                  : 'bg-green-600 hover:bg-green-700'
            } text-white flex items-center gap-2 disabled:opacity-50`}
          >
            {isExecuting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Executing...
              </>
            ) : (
              <>
                {visualMode ? (
                  <Eye className="w-4 h-4" />
                ) : executionMode === 'cloud-run' ? (
                  <Cloud className="w-4 h-4" />
                ) : (
                  <Monitor className="w-4 h-4" />
                )}
                {executionMode === 'cloud-run' ? 'Cloud Run' : 'Local Run'}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
