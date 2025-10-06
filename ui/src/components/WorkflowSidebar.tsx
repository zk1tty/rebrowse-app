import { useState, useMemo, useEffect, useRef } from 'react';
import { Globe, Search, Video, Loader, Workflow, HelpCircle, MessageCircle, MessageSquare } from 'lucide-react';
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  useSidebar,
} from '@/components/ui/sidebar';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { DeleteWorkflowDialog } from '@/components/DeleteWorkflowDialog';
import { useAppContext } from '@/contexts/AppContext';
import { useTheme } from '@/contexts/ThemeContext';
import { workflowService } from '@/services/workflowService';
import { useToast } from '@/hooks/use-toast';
import { EditRecordingDialog } from './EditRecordingDialog';
import { RecordingInProgressDialog } from './RecordingInProgressDialog';
import SessionStatus from '@/components/SessionStatus';
import SessionLoginModal from '@/components/SessionLoginModal';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export function WorkflowSidebar() {
  const [searchTerm, setSearchTerm] = useState('');
  const [deleteWorkflowId, setDeleteWorkflowId] = useState<string | null>(null);
  const [showHelpDialog, setShowHelpDialog] = useState(false);
  const [showSessionLoginModal, setShowSessionLoginModal] = useState(false);
  const { toast } = useToast();
  const { theme } = useTheme();
  const { state } = useSidebar();
  const {
    workflows,
    deleteWorkflow,
    sidebarStatus,
    checkForUnsavedChanges,
    recordingStatus,
    setRecordingStatus,
    recordingData,
    setRecordingData,
    activeDialog,
    setActiveDialog,
    currentWorkflowData,
    selectWorkflow,
    displayMode,
    setDisplayMode,
  } = useAppContext();

  // Important, this ref keeps track of the recording status
  const recordingStatusRef = useRef(recordingStatus);

  useEffect(() => {
    recordingStatusRef.current = recordingStatus;
    console.log('Recording status change:', recordingStatusRef.current);
  }, [recordingStatus]);

  const filteredWorkflows = useMemo(() => {
    if (!searchTerm) return workflows;
    return workflows.filter(
      (workflow) =>
        workflow.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        workflow.description.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [searchTerm, workflows]);

  const handleRecordNewWorkflow = async () => {
    if (checkForUnsavedChanges()) {
      return;
    }
    setRecordingStatus('recording');
    try {
      const response = await workflowService.recordWorkflow();
      const refStatus = recordingStatusRef.current;
      if (refStatus === 'cancelling') {
        setActiveDialog(null);
        setRecordingData(null);
        setRecordingStatus('idle');
        return;
      }
      if (response?.success) {
        setRecordingData(response);
        setRecordingStatus('building');
        setActiveDialog('editRecording');
      } else {
        console.error('Recording failed:', response?.error);
        throw new Error(response?.error || 'Recording failed');
      }
    } catch (error) {
      console.error('Failed to record workflow:', error);
      setRecordingStatus('failed');
      toast({
        title: 'Recording Failed',
        description: 'Failed to record workflow. Please try again.',
        variant: 'destructive',
      });
    }
  };

  // const handleDeleteWorkflow = (workflowId: string) => {
  //   if (checkForUnsavedChanges()) {
  //     return;
  //   }
  //   setDeleteWorkflowId(workflowId);
  // };

  const confirmDeleteWorkflow = async (workflowId: string) => {
    if (!workflowId) return;
    try {
      await deleteWorkflow(workflowId);
    } catch (error) {
      console.error('Failed to delete workflow:', error);
    } finally {
      setDeleteWorkflowId(null);
    }
  };

  const handleCancelRecording = async () => {
    try {
      setRecordingStatus('cancelling');
      const response = await workflowService.stopRecording();
      if (response?.success) {
        setRecordingData(null);
        toast({
          title: '🎥 Recording Cancelled',
          description: 'The workflow recording has been cancelled.',
        });
      } else {
        throw new Error(response?.error || 'Failed to cancel recording');
      }
    } catch (error) {
      console.error('Failed to cancel recording:', error);
      setRecordingStatus('recording');
      toast({
        title: '⚠️ Error',
        description: 'Failed to cancel the recording. Please try again.',
      });
    }
  };

  const handleContinueRecording = () => {
    setActiveDialog(null);
  };

  const handleTelegramClick = () => {
    window.open('https://t.me/rebrowser', '_blank');
    setShowHelpDialog(false);
    toast({
      title: 'Opening Telegram',
      description: 'Redirecting to Telegram chat...',
    });
  };

  const renderSidebarContent = () => {
    if (sidebarStatus === 'loading') {
      return (
        <div className="flex flex-col items-center justify-center p-8 space-y-4">
          <Globe className="w-8 h-8 text-purple-600 animate-bounce" />
          <p className="text-gray-600 animate-pulse">Loading workflows...</p>
        </div>
      );
    }

    if (sidebarStatus === 'error') {
      return (
        <div className="p-6 text-center text-red-500 bg-white shadow-md rounded-lg">
          <p className="text-base font-semibold text-black">
            Failed to load workflows. Try again by refreshing the page.
          </p>
          <p className="text-base font-semibold text-black">
            Make sure the server is running.
          </p>
        </div>
      );
    }

    // Filter out invalid workflows (those without proper name/description)
    const validWorkflows = filteredWorkflows.filter(workflow => 
      workflow.name && 
      workflow.name.trim() !== '' && 
      workflow.name !== 'undefined'
    );

    // For now, show a clean placeholder until we implement execution history
    if (validWorkflows.length === 0) {
      return (
        <div className="p-6 text-center space-y-4">
          <div className={`w-16 h-16 mx-auto rounded-full flex items-center justify-center ${
            theme === 'dark' 
              ? 'bg-gray-800 border-2 border-gray-700' 
              : 'bg-gray-100 border-2 border-gray-200'
          }`}>
            <Workflow className={`w-8 h-8 ${
              theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
            }`} />
          </div>
          <div className="space-y-2">
            <h3 className={`font-medium ${
              theme === 'dark' ? 'text-gray-200' : 'text-gray-700'
            }`}>
              No workflows yet
            </h3>
            <p className={`text-sm ${
              theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
            }`}>
              Start by recording or importing a workflow
            </p>
          </div>
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => setShowSessionLoginModal(true)}
            className={`${
              theme === 'dark' 
                ? 'border-gray-600 text-gray-300 hover:bg-gray-800' 
                : 'border-gray-300 text-gray-600 hover:bg-gray-50'
            }`}
          >
            <Video className="w-4 h-4 mr-2" />
            Record Workflow
          </Button>
        </div>
      );
    }

    return (
      <>
        {/* 
        TODO: FUTURE FEATURE - Recent Execution History
        Add a section here to show:
        - Recently executed workflows
        - Execution status (running, completed, failed)
        - Quick re-run buttons
        - Execution timestamps
        */}
        
        <div className="px-4 py-2">
          <div className="flex items-center w-full">
            <div className={`h-px flex-1 ${
              theme === 'dark' ? 'bg-gray-700' : 'bg-gray-200'
            }`} />
            <span className={`px-3 text-xs font-medium ${
              theme === 'dark' 
                ? 'text-gray-400 bg-gray-900' 
                : 'text-gray-500 bg-white'
            }`}>
              Available Workflows
            </span>
            <div className={`h-px flex-1 ${
              theme === 'dark' ? 'bg-gray-700' : 'bg-gray-200'
            }`} />
          </div>
        </div>

        {/* Show valid workflows in a simple list for now */}
        {validWorkflows.slice(0, 5).map((workflow, index) => (
          <div
            key={`${workflow.name}-${workflow.version || index}`}
            className={`mx-2 p-3 rounded-lg cursor-pointer transition-colors ${
              theme === 'dark' 
                ? 'hover:bg-gray-800 border border-gray-700' 
                : 'hover:bg-gray-50 border border-gray-200'
            } ${
              currentWorkflowData?.name === workflow.name &&
              (theme === 'dark' 
                ? 'bg-cyan-900 border-cyan-400' 
                : 'bg-purple-50 border-purple-300')
            }`}
            onClick={() => {
              selectWorkflow(workflow.name);
              if (displayMode === 'start') {
                setDisplayMode('canvas');
              }
            }}
          >
            <div className="flex items-start gap-3">
              <div className={`w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0 ${
                theme === 'dark' ? 'bg-gray-700' : 'bg-gray-100'
              }`}>
                <Workflow className={`w-4 h-4 ${
                  theme === 'dark' ? 'text-cyan-400' : 'text-purple-600'
                }`} />
              </div>
              <div className="flex-1 min-w-0">
                <h4 className={`font-medium text-sm truncate ${
                  theme === 'dark' ? 'text-white' : 'text-gray-900'
                }`}>
                  {workflow.name}
                </h4>
                <p className={`text-xs truncate ${
                  theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
                }`}>
                  {workflow.description || 'No description'}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <span className={`text-xs ${
                    theme === 'dark' ? 'text-gray-500' : 'text-gray-400'
                  }`}>
                    {workflow.steps?.length || 0} steps
                  </span>
                </div>
              </div>
            </div>
          </div>
        ))}

        {validWorkflows.length > 5 && (
          <div className={`px-4 py-2 text-center text-xs ${
            theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
          }`}>
            +{validWorkflows.length - 5} more workflows
          </div>
        )}
      </>
    );
  };

  return (
    <>
      <Sidebar collapsible="offcanvas" className={`${
        theme === 'dark' ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'
      } border-r`}>
        <SidebarHeader className={`${
          theme === 'dark' ? 'border-gray-700' : 'border-gray-200'
        } border-b p-4`}>
          <div className={`flex items-center ${state === 'collapsed' ? 'justify-center' : 'gap-3'}`}>
            <div className={`flex items-center justify-center bg-gradient-to-br from-purple-500 to-blue-600 rounded-lg ${
              state === 'collapsed' ? 'w-10 h-10' : 'w-10 h-10'
            }`}>
              <Globe className={`text-white ${state === 'collapsed' ? 'w-4 h-4' : 'w-6 h-6'}`} />
            </div>
            {state !== 'collapsed' && (
              <div>
                <h1 className={`text-lg font-semibold ${
                  theme === 'dark' ? 'text-cyan-300 drop-shadow' : 'text-gray-900'
                }`}>
                  Rebrowse
                </h1>
                <p className={`text-sm ${
                  theme === 'dark' ? 'text-cyan-200' : 'text-gray-500'
                }`}>Canvas</p>
              </div>
            )}
          </div>

          {/* Session Status in Sidebar - hide when collapsed */}
          {state !== 'collapsed' && (
            <SessionStatus compact={true} className="mt-3" />
          )}

          {/* Search input - hide when collapsed */}
          {state !== 'collapsed' && (
            <div className="mt-4 relative">
              <Input
                placeholder="Search workflows..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className={`w-full pl-8 ${
                  theme === 'dark' 
                    ? 'bg-gray-800 border-gray-600 text-white placeholder-gray-400' 
                    : ''
                }`}
              />
              <Search className={`absolute left-2 top-1/2 transform -translate-y-1/2 h-4 w-4 ${
                theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
              }`} />
            </div>
          )}

          {/* Record button - show icon only when collapsed */}
          <div className={`mt-4 ${state === 'collapsed' ? 'flex justify-center' : ''}`}>
            <Button
              onClick={handleRecordNewWorkflow}
              disabled={recordingStatus === 'recording'}
              className={`text-white ${
                state === 'collapsed' ? 'w-10 h-10 p-0 rounded-lg' : 'w-full'
              } ${
                theme === 'dark' 
                  ? 'bg-cyan-600 hover:bg-cyan-700' 
                  : 'bg-purple-600 hover:bg-purple-700'
              }`}
              title={state === 'collapsed' ? 'Prompt Workflow' : ''}
            >
              {recordingStatus === 'recording' ? (
                <>
                  <Loader className={`${state === 'collapsed' ? 'w-5 h-5' : 'w-4 h-4'} ${state !== 'collapsed' ? 'mr-2' : ''} animate-spin`} />
                  {state !== 'collapsed' && 'Recording...'}
                </>
              ) : (
                <>
                  <MessageSquare className={`${state === 'collapsed' ? 'w-5 h-5' : 'w-4 h-4'} ${state !== 'collapsed' ? 'mr-2' : ''}`} />
                  {state !== 'collapsed' && 'Prompt Workflow'}
                </>
              )}
            </Button>
          </div>
        </SidebarHeader>

        <SidebarContent className="flex flex-col">
          <SidebarGroup className="flex-1">
            <SidebarGroupContent>
              <SidebarMenu className="space-y-1">
                {state !== 'collapsed' ? (
                  renderSidebarContent()
                ) : (
                  // Show minimal workflow icons when collapsed
                  <div className="flex flex-col items-center space-y-3 pt-4">
                    {workflows.slice(0, 3).map((workflow) => (
                      <div
                        key={workflow.name}
                        className={`w-10 h-10 rounded-lg flex items-center justify-center cursor-pointer ${
                          theme === 'dark' 
                            ? 'bg-gray-800 hover:bg-gray-700' 
                            : 'bg-gray-100 hover:bg-gray-200'
                        }`}
                        title={workflow.name}
                        onClick={() => {
                          // Handle workflow selection if needed
                        }}
                      >
                        <Workflow className={`w-5 h-5 ${
                          theme === 'dark' ? 'text-cyan-400' : 'text-purple-600'
                        }`} />
                      </div>
                    ))}
                    {workflows.length > 3 && (
                      <div className={`text-xs ${
                        theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
                      }`}>
                        +{workflows.length - 3}
                      </div>
                    )}
                  </div>
                )}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>

          {/* Help Button at Bottom */}
          <div className={`p-4 border-t ${
            theme === 'dark' ? 'border-gray-700' : 'border-gray-200'
          }`}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowHelpDialog(true)}
              className={`${
                state === 'collapsed' ? 'w-10 h-10 p-0 mx-auto' : 'w-full'
              } ${
                theme === 'dark' 
                  ? 'text-gray-400 hover:text-cyan-300 hover:bg-gray-800' 
                  : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
              }`}
              title={state === 'collapsed' ? 'Get Help' : ''}
            >
              <HelpCircle className={`${state === 'collapsed' ? 'w-5 h-5' : 'w-4 h-4'} ${state !== 'collapsed' ? 'mr-2' : ''}`} />
              {state !== 'collapsed' && 'Help?'}
            </Button>
          </div>
        </SidebarContent>
      </Sidebar>

      <DeleteWorkflowDialog
        workflowId={deleteWorkflowId}
        onConfirm={confirmDeleteWorkflow}
        onCancel={() => setDeleteWorkflowId(null)}
      />

      {activeDialog === 'editRecording' && recordingData && (
        <EditRecordingDialog
          isOpen={true}
          onClose={() => {
            setActiveDialog(null);
            setRecordingData(null);
          }}
          recordingData={recordingData}
        />
      )}

      {activeDialog === 'recordingInProgress' && (
        <RecordingInProgressDialog
          onCancel={handleCancelRecording}
          onContinue={handleContinueRecording}
          recordingStatus={recordingStatus}
        />
      )}

      <SessionLoginModal
        open={showSessionLoginModal}
        onOpenChange={setShowSessionLoginModal}
      />

      {/* Help Dialog */}
      <Dialog open={showHelpDialog} onOpenChange={setShowHelpDialog}>
        <DialogContent className={`sm:max-w-md ${
          theme === 'dark' ? 'bg-gray-900 border-gray-700' : 'bg-white'
        }`}>
          <DialogHeader>
            <DialogTitle className={`flex items-center gap-2 ${
              theme === 'dark' ? 'text-white' : 'text-gray-900'
            }`}>
              <HelpCircle className="w-5 h-5" />
              Need help?
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
              
              <Button
                onClick={handleTelegramClick}
                className={`w-full ${
                  theme === 'dark' 
                    ? 'bg-cyan-600 hover:bg-cyan-700' 
                    : 'bg-blue-600 hover:bg-blue-700'
                } text-white`}
              >
                Open Telegram
                <MessageCircle className="w-5 h-5 mr-2" />
              </Button>

            <div className={`text-center text-xs ${
              theme === 'dark' ? 'text-gray-500' : 'text-gray-400'
            }`}>
              <p>Rebrowse Support Telegram</p>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
