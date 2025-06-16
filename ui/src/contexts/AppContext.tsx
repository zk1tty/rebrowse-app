import React, {
  createContext,
  useContext,
  useState,
  ReactNode,
  useCallback,
  useRef,
  useEffect,
} from 'react';
import { Workflow, inputFieldSchema } from '../types/workflow-layout.types';
import { workflowService } from '@/services/workflowService';
// import { fetchWorkflowLogs, cancelWorkflow } from '@/services/pollingService';
import { z } from 'zod';
import { useToast } from '@/hooks/use-toast';
import { hasValidSessionToken } from '@/utils/authUtils';

export type DisplayMode = 'canvas' | 'editor' | 'start';
export type DialogType =
  | 'run'
  | 'runAsTool'
  | 'unsavedChanges'
  | 'editRecording'
  | 'recordingInProgress'
  | null;
export type SidebarStatus = 'loading' | 'ready' | 'error';
export type EditorStatus = 'saved' | 'unsaved';
export type WorkflowStatus =
  | 'idle'
  | 'running'
  | 'failed'
  | 'cancelling'
  | 'cancelled'
  | 'completed';
export type RecordingStatus =
  | 'idle'
  | 'recording'
  | 'building'
  | 'failed'
  | 'cancelling';

interface AppContextType {
  displayMode: DisplayMode;
  setDisplayMode: (mode: DisplayMode) => void;
  workflowStatus: WorkflowStatus;
  workflowError: string | null;
  currentTaskId: string | null;
  currentLogPosition: number;
  sidebarStatus: SidebarStatus;
  editorStatus: EditorStatus;
  setEditorStatus: (status: EditorStatus) => void;
  currentWorkflowData: Workflow | null;
  isCurrentWorkflowPublic: boolean;
  currentUserSessionToken: string | null;
  isCurrentUserOwner: boolean;
  workflows: Workflow[];
  addWorkflow: (workflow: Workflow) => void;
  deleteWorkflow: (workflowId: string) => void;
  selectWorkflow: (workflowName: string) => void;
  activeDialog: DialogType;
  setActiveDialog: (dialog: DialogType) => void;
  executeWorkflow: (
    workflowId: string,
    inputFields: z.infer<typeof inputFieldSchema>[]
  ) => Promise<void>;
  updateWorkflowUI: (oldWorkflow: Workflow, newWorkflow: Workflow) => void;
  startPollingLogs: (taskId: string) => void;
  stopPollingLogs: () => void;
  logData: string[];
  cancelWorkflowExecution: (taskId: string) => Promise<void>;
  checkForUnsavedChanges: () => boolean;
  recordingStatus: RecordingStatus;
  setRecordingStatus: (status: RecordingStatus) => void;
  recordingData: any;
  setRecordingData: (data: any) => void;
  fetchWorkflows: () => Promise<void>;
  setWorkflows: (workflows: Workflow[]) => void;
  setSidebarStatus: (status: SidebarStatus) => void;
  setCurrentWorkflowData: (workflow: Workflow | null, isPublic?: boolean) => void;
  setCurrentUserSessionToken: (sessionToken: string | null) => void;
  setIsCurrentUserOwner: (isOwner: boolean) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

interface AppProviderProps {
  children: ReactNode;
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const { toast } = useToast();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [displayMode, setDisplay] = useState<DisplayMode>('start');
  const [currentWorkflowData, setCurrentWorkflowDataState] =
    useState<Workflow | null>(null);
  const [isCurrentWorkflowPublic, setIsCurrentWorkflowPublic] = useState<boolean>(false);
  const [currentUserSessionToken, setCurrentUserSessionToken] = useState<string | null>(null);
  const [isCurrentUserOwner, setIsCurrentUserOwner] = useState<boolean>(false);
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus>('idle');
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [activeDialog, setActiveDialog] = useState<DialogType>(null);
  const [sidebarStatus, setSidebarStatus] = useState<SidebarStatus>('loading');
  const [editorStatus, setEditorStatus] = useState<EditorStatus>('saved');
  const [logData, setLogData] = useState<string[]>([]);
  const [logPosition, setLogPosition] = useState<number>(0);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const [recordingStatus, setRecordingStatus] =
    useState<RecordingStatus>('idle');
  const [recordingData, setRecordingData] = useState<any>(null);

  // Wrapper function to handle both workflow data and public flag
  const setCurrentWorkflowData = useCallback((workflow: Workflow | null, isPublic: boolean = false) => {
    setCurrentWorkflowDataState(workflow);
    setIsCurrentWorkflowPublic(isPublic);
  }, []);



  const checkForUnsavedChanges = useCallback(() => {
    if (recordingStatus === 'recording') {
      setActiveDialog('recordingInProgress');
      return true;
    }
    if (editorStatus === 'unsaved') {
      setActiveDialog('unsavedChanges');
      return true;
    }
    return false;
  }, [editorStatus, recordingStatus, setActiveDialog]);

  const setDisplayMode = useCallback(
    (mode: DisplayMode) => {
      if (checkForUnsavedChanges()) {
        return;
      }
      setDisplay(mode);
    },
    [checkForUnsavedChanges]
  );

  const selectWorkflow = useCallback(
    (workflowName: string) => {
      console.log("[selectWf] wfname:", workflowName);
      if (checkForUnsavedChanges()) {
        return;
      }
      console.log("[selectWf] workflows:", workflows);
      console.log("[selectWf] obj:", Object.keys(workflows));
      const wf = workflows.find((w) => w.name === workflowName);
      console.log("[selectWf] wf:", wf);
      if (wf) {
        setCurrentWorkflowData(wf, false); // Private workflows are not public
      } else {
        setCurrentWorkflowData(null, false); // fallback
      }
    },
    [workflows, checkForUnsavedChanges]
  );

  const addWorkflow = async (workflow: Workflow) => {
    try {
      await workflowService.addWorkflow(
        workflow.name,
        JSON.stringify(workflow)
      );
      setWorkflows((prev) => [workflow, ...prev]);
      toast({
        title: 'Workflow added! ✅',
        description: 'The workflow has been successfully added!',
      });
    } catch (err) {
      toast({
        title: 'Error ❌',
        description: `Failed to add the workflow. ${err}`,
      });
    }
  };

  const deleteWorkflow = async (workflowName: string) => {
    try {
      await workflowService.deleteWorkflow(workflowName);
      setWorkflows((prev) => prev.filter((wf) => wf.name !== workflowName));
      toast({
        title: 'Workflow deleted! ✅',
        description: 'The workflow has been successfully deleted!',
      });
    } catch (err) {
      toast({
        title: 'Error ❌',
        description: `Failed to delete the workflow. ${err}`,
      });
    }
  };

  const updateWorkflowUI = useCallback(
    (oldWorkflow: Workflow, newWorkflow: Workflow) => {
      setWorkflows((prev) =>
        prev.map((wf) => (wf.name === oldWorkflow.name ? newWorkflow : wf))
      );
      if (currentWorkflowData?.name === oldWorkflow.name) {
        setCurrentWorkflowData(newWorkflow, isCurrentWorkflowPublic);
      }
    },
    [currentWorkflowData, isCurrentWorkflowPublic, setCurrentWorkflowData]
  );

  const stopPollingLogs = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const startPollingLogs = useCallback(
    (taskId: string) => {
      stopPollingLogs();

      const poll = async () => {
        try {
          const data = await workflowService.fetchWorkflowLogs(
            taskId,
            logPosition
          );
          if (data.logs?.length) {
            setLogData((prev) => {
              const newLogs = data.logs.filter((log) => !prev.includes(log));
              return [...prev, ...newLogs];
            });
          }
          setLogPosition(data.log_position);

          if (data.status && data.status !== workflowStatus) {
            setWorkflowStatus(data.status as WorkflowStatus);
            if (data.status === 'failed' && data.error) {
              setWorkflowError(data.error);
              setWorkflowStatus('failed');
              stopPollingLogs();
            } else if (
              data.status === 'completed' ||
              data.status === 'cancelled'
            ) {
              stopPollingLogs();
            }
          }

          if (['failed', 'cancelled', 'completed'].includes(workflowStatus)) {
            stopPollingLogs();
            if (workflowStatus === 'failed' && data.error) {
              setWorkflowError(data.error);
            }
          }
        } catch (err) {
          console.error('Polling error:', err);
          setWorkflowError('Failed to fetch workflow logs');
          stopPollingLogs();
          setWorkflowStatus('failed');
        }
      };

      poll();
      pollingRef.current = setInterval(poll, 2000);
    },
    [logPosition, workflowStatus, stopPollingLogs]
  );

  const cancelWorkflowExecution = async (taskId: string) => {
    try {
      setWorkflowStatus('cancelling');
      await workflowService.cancelWorkflow(taskId);
    } catch (err) {
      console.error('Failed to cancel workflow:', err);
      setWorkflowError('Failed to cancel workflow');
      setWorkflowStatus('failed');
    }
  };

  const executeWorkflow = useCallback(
    async (workflowId: string, inputFields: z.infer<typeof inputFieldSchema>[]) => {
      if (!workflowId) return;
      const missingInputs = inputFields.filter(
        (field) => field.required && !field.value
      );
      if (missingInputs.length > 0) {
        setWorkflowError(
          `Missing required inputs: ${missingInputs
            .map((f) => f.name)
            .join(', ')}`
        );
        return;
      }

      // Check authentication before attempting execution
      if (!hasValidSessionToken(currentUserSessionToken)) {
        setWorkflowError('Please login through the Chrome extension to execute workflows.');
        setWorkflowStatus('failed');
        return;
      }

      setWorkflowError(null);
      setCurrentTaskId(null);
      setLogPosition(0);
      setWorkflowStatus('idle');

      try {
        // Use session token for execution
        const result = await workflowService.executeWorkflow(
          workflowId, 
          inputFields, 
          currentUserSessionToken!  // We've already validated it's not null above
        );
        setCurrentTaskId(result.task_id);
        setLogPosition(result.log_position);
        setWorkflowStatus('running');
        setDisplayMode('canvas');
        startPollingLogs(result.task_id);
      } catch (err) {
        console.error('Workflow execution failed:', err);
        
        // Provide user-friendly error messages
        let errorMessage = 'An error occurred while executing the workflow';
        
        if (err instanceof Error) {
          const errorText = err.message.toLowerCase();
          
          // Handle authentication-related errors
          if (errorText.includes('jwt') || errorText.includes('session authentication') || errorText.includes('unauthorized')) {
            errorMessage = 'Please login through the Chrome extension to execute workflows.';
          } else if (errorText.includes('session token') || errorText.includes('invalid token')) {
            errorMessage = 'Your session has expired. Please login again through the Chrome extension.';
          } else if (errorText.includes('not found') || errorText.includes('404')) {
            errorMessage = 'Workflow not found. Please refresh the page and try again.';
          } else {
            // Use the original error message for other cases
            errorMessage = err.message;
          }
        }
        
        setWorkflowError(errorMessage);
        setWorkflowStatus('failed');
        stopPollingLogs();
      }
    },
    [startPollingLogs, stopPollingLogs, setDisplayMode, currentUserSessionToken]
  );

  // Uncomment for debugging
  // useEffect(() => {
  //   const logInterval = setInterval(() => {
  //     console.log('Current workflows:', workflows);
  //     console.log('Current workflow data:', currentWorkflowData);
  //   }, 2000); // Log every 10 seconds

  //   return () => clearInterval(logInterval);
  // }, [workflows, currentWorkflowData]);

  // Fetch workflows on mount(everytime the page is called)
  const fetchWorkflows = async () => {
    try {
      setSidebarStatus('loading');
      const response = await workflowService.getWorkflows();
      const parsedWorkflows = response.map((wf: any) => JSON.parse(wf));
      console.log("[fetchWorkflows] parsedWorkflows:", parsedWorkflows);
      setWorkflows(parsedWorkflows);
      setSidebarStatus('ready');
    } catch (err) {
      console.error('Failed to fetch workflows:', err);
      setSidebarStatus('error');
    }
  };

  useEffect(() => {
    fetchWorkflows();
  }, []);

  return (
    <AppContext.Provider
      value={{
        selectWorkflow,
        displayMode,
        setDisplayMode,
        workflowStatus,
        workflowError,
        currentTaskId,
        currentLogPosition: logPosition,
        currentWorkflowData,
        isCurrentWorkflowPublic,
        currentUserSessionToken,
        isCurrentUserOwner,
        workflows,
        addWorkflow,
        deleteWorkflow,
        activeDialog,
        setActiveDialog,
        executeWorkflow,
        updateWorkflowUI,
        startPollingLogs,
        stopPollingLogs,
        logData,
        cancelWorkflowExecution,
        sidebarStatus,
        editorStatus,
        setEditorStatus,
        checkForUnsavedChanges,
        recordingStatus,
        setRecordingStatus,
        recordingData,
        setRecordingData,
        fetchWorkflows,
        setWorkflows,
        setSidebarStatus,
        setCurrentWorkflowData,
        setCurrentUserSessionToken,
        setIsCurrentUserOwner
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
};
