import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from './ui/dialog';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { workflowService } from '@/services/workflowService';
import { Workflow } from '@/types/workflow-layout.types';
import { useAppContext } from '@/contexts/AppContext';
import { toast } from './ui/use-toast';
import { Clock, ListChecks, Activity, Loader2 } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';

interface WorkflowRecordResponse {
  success: boolean;
  workflow?: Workflow;
  error?: string;
}

interface EditRecordingDialogProps {
  isOpen: boolean;
  onClose: () => void;
  recordingData: WorkflowRecordResponse;
}

interface ConfirmCloseDialogProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const ConfirmCloseDialog: React.FC<ConfirmCloseDialogProps> = ({
  isOpen,
  onConfirm,
  onCancel,
}) => {
  return (
    <Dialog open={isOpen} onOpenChange={onCancel}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Confirm Close</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-gray-500">
          Are you sure you want to close the workflow editor? Any unsaved
          changes will be lost.
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Continue Editing
          </Button>
          <Button variant="destructive" onClick={onConfirm}>
            Close Without Saving
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export function EditRecordingDialog({
  isOpen,
  onClose,
  recordingData,
}: EditRecordingDialogProps) {
  const [editedData, setEditedData] = useState<Workflow>({
    name: '',
    steps: [],
    description: '',
    version: '',
    workflow_analysis: '',
    input_schema: [],
  });
  const [isBuilding, setIsBuilding] = useState(false);
  const [userPrompt, setUserPrompt] = useState('');
  const [showConfirmClose, setShowConfirmClose] = useState(false);
  const { recordingStatus, setRecordingStatus, fetchWorkflows } =
    useAppContext();
  const { theme } = useTheme();

  // Update editedData when recordingData changes
  useEffect(() => {
    if (recordingData?.workflow) {
      setEditedData({
        name: '',
        steps: recordingData.workflow.steps || [],
        description: recordingData.workflow.description || '',
        version: recordingData.workflow.version || '',
        workflow_analysis: recordingData.workflow.workflow_analysis,
        input_schema: recordingData.workflow.input_schema || [],
      });
    }
  }, [recordingData]);

  const [recordingStartTime] = useState(() =>
    new Date().toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  );

  const handleSave = async () => {
    try {
      setIsBuilding(true);
      
      // Validate required fields before sending
      if (!editedData.steps || editedData.steps.length === 0) {
        toast({
          title: '❌ Invalid Workflow Data',
          description: 'No recorded steps found. Please record some actions first.',
        });
        return;
      }
      
      // Prepare workflow data with proper defaults
      const workflowData = {
        ...editedData,
        name: editedData.name || 'Untitled Workflow',
        description: editedData.description || userPrompt || 'Auto-generated workflow',
        version: editedData.version || '1.0.0',
      };
      
      const response = await workflowService.buildWorkflow(
        editedData.name,
        userPrompt,
        workflowData
      );
      if (response.success) {
        await fetchWorkflows();
        onClose();
        setRecordingStatus('idle');
        toast({
          title: '✨ Workflow Built Successfully',
          description: 'Your workflow has been created and is ready to use.',
        });
      } else {
        console.error('Failed to build workflow:', response.error);
        toast({
          title: '❌ Failed to Build Workflow',
          description:
            response.error || 'An error occurred while building the workflow.',
        });
      }
    } catch (error) {
      console.error('Error building workflow:', error);
      toast({
        title: '❌ Failed to Build Workflow',
        description:
          'An unexpected error occurred while building the workflow.',
      });
    } finally {
      setIsBuilding(false);
      setRecordingStatus('idle');
    }
  };

  const handleCloseAttempt = () => {
    setShowConfirmClose(true);
  };

  const handleConfirmClose = () => {
    setShowConfirmClose(false);
    onClose();
    if (recordingStatus !== 'cancelling') {
      setRecordingStatus('idle');
    }
  };

  const handleCancelClose = () => {
    setShowConfirmClose(false);
  };

  const getStepTypeCount = () => {
    const counts: Record<string, number> = {};
    editedData.steps?.forEach((step: any) => {
      counts[step.type] = (counts[step.type] || 0) + 1;
    });
    return counts;
  };

  return (
    <>
      <Dialog
        open={isOpen}
        onOpenChange={(open) => {
          if (!open) {
            handleCloseAttempt();
          }
        }}
      >
        <DialogContent className="sm:max-w-7xl max-h-[90vh] p-10">
          <DialogHeader>
            <DialogTitle className={`text-2xl font-bold ${
              theme === 'dark' ? 'text-white' : 'text-black'
            }`}>
              Edit Recorded Workflow
            </DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-8 h-full overflow-hidden">
            {/* Left side - Prompt and Workflow Info */}
            <div className="flex flex-col gap-4 h-full overflow-y-auto flex-1 min-h-0">
              <div className="grid gap-4 p-4">
                <div className="grid gap-2">
                  <h3 className={`text-lg font-semibold ${
                    theme === 'dark' ? 'text-white' : 'text-black'
                  }`}>Workflow Name</h3>
                  <input
                    id="name"
                    value={editedData.name}
                    onChange={(e) =>
                      setEditedData({ ...editedData, name: e.target.value })
                    }
                    className={`border rounded-md p-5 text-lg ${
                      theme === 'dark' 
                        ? 'bg-gray-900 border-gray-600 text-white placeholder-gray-400' 
                        : 'bg-white border-gray-300 text-black'
                    }`}
                    placeholder="Leave empty for automatic name generation"
                  />
                </div>

                <div className="grid gap-2">
                  <h3 className={`text-lg font-semibold ${
                    theme === 'dark' ? 'text-white' : 'text-black'
                  }`}>
                    Describe what this workflow should do
                  </h3>
                  <Textarea
                    id="prompt"
                    value={userPrompt}
                    onChange={(e) => setUserPrompt(e.target.value)}
                    placeholder="Describe the purpose and behavior of this workflow. The AI will use this to optimize the steps..."
                    className={`min-h-[300px] text-lg ml-1 p-5 ${
                      theme === 'dark' 
                        ? 'bg-gray-900 border-gray-600 text-white placeholder-gray-400 focus:outline-cyan-400 focus:outline-2' 
                        : 'bg-white border-gray-300 text-black focus:outline-black focus:outline-2'
                    }`}
                  />
                </div>
              </div>
            </div>

            {/* Right side - Statistics Summary */}
            <div className="flex flex-col gap-6">
              <div className="grid grid-cols-3 gap-4">
                <div className={`p-6 rounded-xl border ${
                  theme === 'dark' 
                    ? 'bg-black border-gray-600' 
                    : 'bg-purple-50 border-purple-100'
                }`}>
                  <div className="flex items-center gap-3">
                    <ListChecks className={`h-6 w-6 ${
                      theme === 'dark' ? 'text-purple-400' : 'text-purple-600'
                    }`} />
                    <div>
                      <p className={`text-sm font-medium ${
                        theme === 'dark' ? 'text-purple-300' : 'text-purple-600'
                      }`}>
                        Total Steps
                      </p>
                      <p className={`text-2xl font-bold ${
                        theme === 'dark' ? 'text-white' : 'text-black'
                      }`}>
                        {editedData.steps?.length || 0}
                      </p>
                    </div>
                  </div>
                </div>
                <div className={`p-6 rounded-xl border ${
                  theme === 'dark' 
                    ? 'bg-black border-gray-600' 
                    : 'bg-blue-50 border-blue-100'
                }`}>
                  <div className="flex items-center gap-3">
                    <Activity className={`h-6 w-6 ${
                      theme === 'dark' ? 'text-blue-400' : 'text-blue-600'
                    }`} />
                    <div>
                      <p className={`text-sm font-medium ${
                        theme === 'dark' ? 'text-blue-300' : 'text-blue-600'
                      }`}>
                        Step Types
                      </p>
                      <p className={`text-2xl font-bold ${
                        theme === 'dark' ? 'text-white' : 'text-black'
                      }`}>
                        {Object.keys(getStepTypeCount()).length}
                      </p>
                    </div>
                  </div>
                </div>
                <div className={`p-6 rounded-xl border ${
                  theme === 'dark' 
                    ? 'bg-black border-gray-600' 
                    : 'bg-green-50 border-green-100'
                }`}>
                  <div className="flex items-center gap-3">
                    <Clock className={`h-6 w-6 ${
                      theme === 'dark' ? 'text-green-400' : 'text-green-600'
                    }`} />
                    <div>
                      <p className={`text-sm font-medium ${
                        theme === 'dark' ? 'text-green-300' : 'text-green-600'
                      }`}>
                        Recording Time
                      </p>
                      <p className={`text-2xl font-bold ${
                        theme === 'dark' ? 'text-white' : 'text-black'
                      }`}>{recordingStartTime}</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className={`p-6 rounded-xl border ${
                theme === 'dark' 
                  ? 'bg-black border-gray-600' 
                  : 'bg-white border-gray-300'
              }`}>
                <h3 className={`text-lg font-semibold mb-4 ${
                  theme === 'dark' ? 'text-white' : 'text-black'
                }`}>
                  Step Type Distribution
                </h3>
                <div className="space-y-3">
                  {Object.entries(getStepTypeCount()).map(([type, count]) => (
                    <div
                      key={type}
                      className="flex items-center justify-between"
                    >
                      <span className={`${
                        theme === 'dark' ? 'text-gray-300' : 'text-gray-600'
                      }`}>{type}</span>
                      <span className={`font-medium ${
                        theme === 'dark' ? 'text-white' : 'text-black'
                      }`}>{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <DialogFooter className="mt-6">
            <Button
              variant="outline"
              onClick={handleCloseAttempt}
              disabled={showConfirmClose}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={isBuilding || !userPrompt.trim()}
              className="bg-purple-600 hover:bg-purple-700"
            >
              {isBuilding ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Building...
                </>
              ) : (
                'Coming Soon 🚀'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmCloseDialog
        isOpen={showConfirmClose}
        onConfirm={handleConfirmClose}
        onCancel={handleCancelClose}
      />
    </>
  );
}
