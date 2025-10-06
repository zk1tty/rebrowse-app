import React, {
  createContext,
  useContext,
  useState,
  ReactNode,
  useCallback,
  useRef,
  useEffect,
  useMemo,
} from 'react';
import { Workflow, EnhancedWorkflow, inputFieldSchema, ActiveExecution } from '../types/workflow-layout.types';
import { workflowService } from '@/services/workflowService';
import { createEnhancedWorkflowService } from '@/services/enhancedWorkflowService';
// import { fetchWorkflowLogs, cancelWorkflow } from '@/services/pollingService';
import { z } from 'zod';
import { useToast } from '@/hooks/use-toast';
import { hasValidSessionToken, getStoredSessionToken, storeAnonymousSessionToken } from '@/utils/authUtils';
import { API_ENDPOINTS } from '@/lib/constants';

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
  | 'starting'
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
  currentExecutionMode: 'cloud-run' | 'local-run' | null;
  currentExecutionInputs: any | null;
  currentLogPosition: number;
  sidebarStatus: SidebarStatus;
  editorStatus: EditorStatus;
  setEditorStatus: (status: EditorStatus) => void;
  // Allow external components (e.g., overlay wrapper) to set workflow status
  setWorkflowAppStatus: (status: WorkflowStatus) => void;
  currentWorkflowData: Workflow | null;
  isCurrentWorkflowPublic: boolean;
  currentUserSessionToken: string | null;
  isCurrentUserOwner: boolean;
  workflows: EnhancedWorkflow[];
  activeExecutions: Record<string, ActiveExecution>;
  // VIew Mode Overlay States
  visualOverlayActive: boolean;
  currentStreamingSession: string | null;
  overlayWorkflowInfo: {
    name: string;
    taskId: string;
    mode: string;
    hasStreamingSupport?: boolean;
  } | null;
  currentRunId: string | null;
  setCurrentRunId: (runId: string | null) => void;
  setVisualOverlayActive: (active: boolean) => void;
  setCurrentStreamingSession: (sessionId: string | null) => void;
  setOverlayWorkflowInfo: (info: { name: string; taskId: string; mode: string; hasStreamingSupport?: boolean } | null) => void;
  addWorkflow: (workflow: Workflow) => void;
  deleteWorkflow: (workflowId: string) => void;
  selectWorkflow: (workflowName: string) => void;
  activeDialog: DialogType;
  setActiveDialog: (dialog: DialogType) => void;
  executeWorkflow: (
    workflowId: string,
    inputFields: z.infer<typeof inputFieldSchema>[],
    mode?: 'cloud-run' | 'local-run',
    visual?: boolean
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
  refreshAuthenticationStatus: () => void;
  authRefreshTrigger: number;
  anonymousUserId: string | null;
  isAnonymousUser: boolean;
  isInitializingAnonymous: boolean;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

interface AppProviderProps {
  children: ReactNode;
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const { toast } = useToast();
  const [workflows, setWorkflows] = useState<EnhancedWorkflow[]>([]);
  const [activeExecutions, setActiveExecutions] = useState<Record<string, ActiveExecution>>({});
  const [displayMode, setDisplay] = useState<DisplayMode>('start');
  const [currentWorkflowData, setCurrentWorkflowDataState] =
    useState<Workflow | null>(null);
  const [isCurrentWorkflowPublic, setIsCurrentWorkflowPublic] = useState<boolean>(false);
  
  // Initialize with any existing session token from storage
  const [currentUserSessionToken, setCurrentUserSessionToken] = useState<string | null>(() => {
    try {
      const storedToken = getStoredSessionToken();
      if (storedToken) {
        return storedToken;
      }
      return null;
    } catch (error) {
      console.error('❌ [AppContext] Error loading initial session token:', error);
      return null;
    }
  });
  
  const [isCurrentUserOwner, setIsCurrentUserOwner] = useState<boolean>(false);
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus>('idle');
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [activeDialog, setActiveDialog] = useState<DialogType>(null);
  const [sidebarStatus, setSidebarStatus] = useState<SidebarStatus>('loading');
  const [editorStatus, setEditorStatus] = useState<EditorStatus>('saved');
  const [logData, setLogData] = useState<string[]>([]);
  const [logPosition, setLogPosition] = useState<number>(0);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [currentExecutionMode, setCurrentExecutionMode] = useState<'cloud-run' | 'local-run' | null>(null);
  const [currentExecutionInputs, setCurrentExecutionInputs] = useState<any | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const logsWsRef = useRef<WebSocket | null>(null);
  const [recordingStatus, setRecordingStatus] =
    useState<RecordingStatus>('idle');
  const [recordingData, setRecordingData] = useState<any>(null);
  const [authRefreshTrigger, setAuthRefreshTrigger] = useState<number>(0);

  // Anonymous user support
  const [anonymousUserId, setAnonymousUserId] = useState<string | null>(null);
  const [isAnonymousUser, setIsAnonymousUser] = useState<boolean>(false);
  const [isInitializingAnonymous, setIsInitializingAnonymous] = useState<boolean>(false);
  const anonymousInitPromiseRef = useRef<Promise<string | null> | null>(null);

  // View Mode Overlay States
  const [visualOverlayActive, setVisualOverlayActive] = useState(false);
  const [currentStreamingSession, setCurrentStreamingSession] = useState<string | null>(null);
  const [overlayWorkflowInfo, setOverlayWorkflowInfo] = useState<{
    name: string;
    taskId: string;
    mode: string;
    hasStreamingSupport?: boolean;
  } | null>(null);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);

  // Wrapper function to handle both workflow data and public flag
  const setCurrentWorkflowData = useCallback((workflow: Workflow | null, isPublic: boolean = false) => {
    setCurrentWorkflowDataState(workflow);
    setIsCurrentWorkflowPublic(isPublic);
  }, []);

  // Expose safe workflow status setter for external events (e.g., visual completion)
  const setWorkflowAppStatus = useCallback((status: WorkflowStatus) => {
    setWorkflowStatus(status);
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
      
      if (checkForUnsavedChanges()) {
        return;
      }
      
      const wf = workflows.find((w) => w.name === workflowName);
      
      if (wf) {
        setCurrentWorkflowData(wf, false); // Private workflows are not public
      } else {
        setCurrentWorkflowData(null, false); // fallback
      }
    },
    [workflows, checkForUnsavedChanges]
  );

  const addWorkflow = useCallback(async (workflow: Workflow) => {
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
  }, [toast]);

  const deleteWorkflow = useCallback(async (workflowName: string) => {
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
  }, [toast]);

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

  const closeLogsWebSocket = useCallback(() => {
    if (logsWsRef.current) {
      try {
        logsWsRef.current.close();
      } catch (e) {
        // noop
      }
      logsWsRef.current = null;
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
          
          // Only update logs if there are actually new logs
          if (data.logs?.length) {
            setLogData((prev) => {
              const newLogs = data.logs.filter((log) => !prev.includes(log));
              return newLogs.length > 0 ? [...prev, ...newLogs] : prev;
            });
          }
          
          // Only update log position if it actually changed
          if (data.log_position !== logPosition) {
            setLogPosition(data.log_position);
          }

          // Only update status if it actually changed
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

  const startLogsWebSocket = useCallback((executionId: string) => {
    // Always clean any existing connection
    closeLogsWebSocket();

    try {
      const wsUrl = API_ENDPOINTS.LOGS_STREAM_WS(executionId);
      console.log(`[Logs] Connecting WebSocket (execution_id=${executionId}):`, wsUrl);
      const ws = new WebSocket(wsUrl);
      logsWsRef.current = ws;

      // Clear logs when a fresh connection opens
      setLogData([]);

      ws.onopen = () => {
        console.log('[Logs] WebSocket connected');
      };

      ws.onmessage = (event: MessageEvent) => {
        const pushMessage = (msg: string) => {
          setLogData((prev) => [...prev, msg]);
        };
        const parseAndAppend = (text: string) => {
          try {
            const parsed = JSON.parse(text);
            const message = parsed?.message ?? parsed?.data?.message ?? null;
            if (message != null) {
              pushMessage(String(message));
            } else {
              // If no message field, append raw for visibility
              console.log('[Logs] no message field, raw:', text?.slice?.(0, 200));
              pushMessage(text);
            }
          } catch (e) {
            // Not JSON; append raw
            console.log('[Logs] non-JSON frame:', text?.slice?.(0, 200));
            pushMessage(text);
          }
        };

        const raw = event.data;
        if (typeof raw === 'string') {
          parseAndAppend(raw);
        } else if (raw instanceof Blob) {
          raw.text().then(parseAndAppend).catch(() => {
            console.warn('[Logs] failed to read Blob frame');
          });
        } else if (raw instanceof ArrayBuffer) {
          try {
            const text = new TextDecoder().decode(new Uint8Array(raw));
            parseAndAppend(text);
          } catch {
            console.warn('[Logs] failed to decode ArrayBuffer frame');
          }
        } else {
          console.warn('[Logs] unsupported WS frame type');
        }
      };

      ws.onerror = (err) => {
        console.error('[Logs] WebSocket error:', err);
        // Fallback to polling if WS fails
        closeLogsWebSocket();
        startPollingLogs(executionId);
      };

      ws.onclose = (evt: CloseEvent) => {
        console.log('[Logs] WebSocket closed:', evt.code, evt.reason);
        // If closed unexpectedly and workflow still running, fallback to polling
        const abnormal = evt.code !== 1000;
        if (abnormal && workflowStatus === 'running') {
          startPollingLogs(executionId);
        }
      };
    } catch {
      // If creation throws, fallback to polling
      startPollingLogs(executionId);
    }
  }, [closeLogsWebSocket, startPollingLogs, workflowStatus]);

  const cancelWorkflowExecution = useCallback(async (taskId: string) => {
    try {
      setWorkflowStatus('cancelling');
      await workflowService.cancelWorkflow(taskId);
      // Reflect cancellation immediately in UI
      setWorkflowStatus('cancelled');
      stopPollingLogs();
      closeLogsWebSocket();
    } catch (err) {
      console.error('Failed to cancel workflow:', err);
      setWorkflowError('Failed to cancel workflow');
      setWorkflowStatus('failed');
    }
  }, [stopPollingLogs, closeLogsWebSocket]);

  const executeWorkflow = useCallback(
    async (
      workflowId: string,
      inputFields: z.infer<typeof inputFieldSchema>[],
      mode: 'cloud-run' | 'local-run' = 'cloud-run',
      visual: boolean = false
    ) => {
      // Removed authentication check - always allow execution
      
      setWorkflowStatus('starting');
      setWorkflowError(null);
      setActiveDialog(null);
      setLogData([]);
      closeLogsWebSocket();

      try {
        // Show toast for visual mode
        if (visual) {
          toast({
            title: 'Visual Mode Enabled',
            description: `Starting ${mode === 'cloud-run' ? '☁️ cloud-run' : '🖥️ local-run'} execution with live browser view...`,
          });
        }
        
        // Ensure-on-demand: make sure we have a session token before executing
        const ensureAnonymousUser = async (): Promise<string | null> => {
          if (hasValidSessionToken(currentUserSessionToken)) {
            return currentUserSessionToken;
          }
          if (anonymousInitPromiseRef.current) {
            return anonymousInitPromiseRef.current;
          }
          // Start a single in-flight initialization to avoid parallel calls
          anonymousInitPromiseRef.current = (async () => {
            setIsInitializingAnonymous(true);
            try {
              // Try to use existing Supabase client
              let supabaseClient: any = null;
              try {
                const { supabase } = await import('@/lib/api');
                supabaseClient = supabase;
              } catch {
                supabaseClient = null;
              }

              // 1) Check for existing session
              if (supabaseClient) {
                const { data: { session } } = await supabaseClient.auth.getSession();
                if (session?.access_token) {
                  setCurrentUserSessionToken(session.access_token);
                  return session.access_token;
                }
                // 2) Attempt anonymous sign-in
                try {
                  console.info('[Auth] Attempting anonymous sign-in...');
                  const { data, error } = await supabaseClient.auth.signInAnonymously();

                  if (!error && data?.session?.access_token) {
                    console.info('[Auth] Anonymous sign-in succeeded. User is anonymous:', data.user?.is_anonymous === true);
                    setAnonymousUserId(data.user?.id ?? null);
                    setIsAnonymousUser(true);
                    setCurrentUserSessionToken(data.session.access_token);
                    // Persist anonymous session token for page reload/navigation
                    storeAnonymousSessionToken(data.session.access_token);
                    return data.session.access_token;
                  }
                  if (error) {
                    // Log detailed error information to diagnose 401s
                    console.error('[Auth] Anonymous sign-in failed:', {
                      name: (error as any)?.name,
                      message: (error as any)?.message,
                      status: (error as any)?.status,
                      code: (error as any)?.code,
                    });
                  }
                } catch {
                  // ignore; we'll fall back to race guard
                }
              }

              // 3) Race-condition guard: wait up to 10s for token to appear
              const maxAttempts = 100;
              let attempts = 0;
              while (attempts < maxAttempts) {
                // Try to read a fresh session directly from Supabase in case state lags
                try {
                  if (supabaseClient) {
                    const { data: { session } } = await supabaseClient.auth.getSession();
                    if (session?.access_token) {
                      setCurrentUserSessionToken(session.access_token);
                      return session.access_token;
                    }
                  }
                } catch {
                  // ignore and retry
                }
                // Fallback to state if already set
                if (hasValidSessionToken(currentUserSessionToken)) {
                  return currentUserSessionToken;
                }
                await new Promise(resolve => setTimeout(resolve, 100));
                attempts++;
              }
              return null;
            } finally {
              setIsInitializingAnonymous(false);
            }
          })();
          try {
            return await anonymousInitPromiseRef.current;
          } finally {
            anonymousInitPromiseRef.current = null;
          }
        };

        // Non-blocking app start: we only ensure right before execution
        const ensuredToken = await ensureAnonymousUser();
        console.log('Anonymous token:', ensuredToken);
        console.log('Current user session token:', currentUserSessionToken);

        const result = await workflowService.executeWorkflow(
          workflowId,
          inputFields,
          (ensuredToken || currentUserSessionToken) || undefined, // Pass undefined instead of null
          mode,
          visual
        );
        
        setCurrentTaskId(result.task_id);
        setCurrentExecutionMode(mode);
        setCurrentExecutionInputs(inputFields);
        setLogPosition(result.log_position);
        setWorkflowStatus('running');
        
        // Store execution parameters in sessionStorage for DevTools execution trigger
        if (visual && result.task_id) {
          const executionParams = {
            workflowId: workflowId,
            inputs: inputFields,
            sessionToken: currentUserSessionToken,
            mode: mode,
            visual: true,
            timestamp: Date.now(),
          };
          sessionStorage.setItem(`execution_params_${result.task_id}`, JSON.stringify(executionParams));
        }
        
        // Handle visual mode - redirect to appropriate viewer based on streaming capability
        if (visual) {
          if (result.visual_streaming_enabled && result.session_id) {
            // Visual streaming mode - use RRWebVisualizer
            setCurrentStreamingSession(result.session_id);
            setOverlayWorkflowInfo({
              name: result.workflow,
              taskId: result.task_id,
              mode: result.mode,
              hasStreamingSupport: true,
            });
            setVisualOverlayActive(true);
            setDisplayMode('canvas');
          } else if (result.visual_enabled && result.devtools_url) {
            // Traditional visual mode - use DevTools iframe
            setDisplayMode('canvas');
            // DevTools will handle the execution
          } else {
            // Fallback to traditional execution
            setDisplayMode('canvas');
          }
        } else {
          // Non-visual mode
          setDisplayMode('canvas');
        }
        
        // Start live logs via WebSocket using execution_id only
        const executionId = (result as any).execution_id as string | undefined;
        console.log('[Logs] execution_id from executeWorkflow:', executionId);
        if (executionId) {
          startLogsWebSocket(executionId);
        } else {
          console.warn('[Logs] No execution_id returned in execute response; skipping WS logs.');
        }
        // Capture runId for step event stream when available
        const runId = (result as any).execution_id as string | undefined;
        if (runId) {
          setCurrentRunId(runId);
        }
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
        closeLogsWebSocket();
      }
    },
    [startLogsWebSocket, stopPollingLogs, setDisplayMode, currentUserSessionToken, closeLogsWebSocket]
  );

  // Uncomment for debugging
  // useEffect(() => {
  //   const logInterval = setInterval(() => {
  //     console.log('Current workflows:', workflows);
  //     console.log('Current workflow data:', currentWorkflowData);
  //   }, 2000); // Log every 10 seconds

  //   return () => clearInterval(logInterval);
  // }, [workflows, currentWorkflowData]);

  // Enhanced workflow service instance - memoized to prevent recreation
  const enhancedWorkflowService = useMemo(() => 
    createEnhancedWorkflowService(currentUserSessionToken), 
    [currentUserSessionToken]
  );

  // Fetch workflows with execution statistics
  const fetchWorkflows = useCallback(async () => {
    try {
      setSidebarStatus('loading');
      
      // Try to fetch enhanced workflows with stats if session token exists
      if (hasValidSessionToken(currentUserSessionToken)) {
        try {
          const enhancedWorkflows = await enhancedWorkflowService.getAllWorkflowsWithStats();
          setWorkflows(enhancedWorkflows);
          setSidebarStatus('ready');
          return;
        } catch (error) {
          console.warn('[fetchWorkflows] Failed to fetch enhanced workflows, falling back to basic:', error);
        }
      }
      
      // Fallback to basic workflows
      const response = await workflowService.getWorkflows();
      const basicWorkflows: EnhancedWorkflow[] = response.map(workflow => ({
        ...workflow,
        execution_stats: undefined,
        recent_executions: undefined,
        performance: undefined
      }));
      setWorkflows(basicWorkflows);
      setSidebarStatus('ready');
    } catch (err) {
      console.error('Failed to fetch workflows:', err);
      setSidebarStatus('error');
    }
  }, [currentUserSessionToken, enhancedWorkflowService]);

  // Poll for active executions
  const pollActiveExecutions = useCallback(async () => {
    if (!hasValidSessionToken(currentUserSessionToken)) {
      setActiveExecutions(prev => Object.keys(prev).length === 0 ? prev : {});
      return;
    }

    try {
      const active = await enhancedWorkflowService.getActiveExecutions();
      
      // Only update if active executions actually changed
      setActiveExecutions(prev => {
        const prevKeys = Object.keys(prev).sort();
        const activeKeys = Object.keys(active).sort();
        
        // Quick check if keys are different
        if (prevKeys.length !== activeKeys.length || 
            prevKeys.some((key, index) => key !== activeKeys[index])) {
          return active;
        }
        
        // Check if any execution details changed
        const hasChanges = activeKeys.some(key => 
          JSON.stringify(prev[key]) !== JSON.stringify(active[key])
        );
        
        return hasChanges ? active : prev;
      });
    } catch (error) {
      console.warn('Failed to poll active executions:', error);
    }
  }, [currentUserSessionToken, enhancedWorkflowService]);

  const refreshAuthenticationStatus = useCallback(() => {
    setAuthRefreshTrigger(prev => prev + 1);
  }, []);

  // Removed initializeAnonymousUser; handled on-demand in executeWorkflow

  // Poll for active executions every 5 seconds when authenticated
  useEffect(() => {
    if (!hasValidSessionToken(currentUserSessionToken)) {
      return;
    }

    // Initial poll
    pollActiveExecutions();

    // Set up polling interval - reduced frequency to minimize re-renders
    const interval = setInterval(pollActiveExecutions, 10000);
    
    return () => clearInterval(interval);
  }, [currentUserSessionToken, pollActiveExecutions]); // Added pollActiveExecutions to dependencies

  // Removed eager anonymous initialization on app load; handled on-demand

  // Update enhanced service when session token changes
  useEffect(() => {
    enhancedWorkflowService.updateSessionToken(currentUserSessionToken);
  }, [currentUserSessionToken]);

  // Fetch workflows on app start
  useEffect(() => {
    fetchWorkflows();
  }, []);

  // Close the logs WebSocket when workflow finishes or is cancelled
  useEffect(() => {
    if (['completed', 'failed', 'cancelled'].includes(workflowStatus)) {
      closeLogsWebSocket();
      stopPollingLogs();
    }
  }, [workflowStatus, closeLogsWebSocket, stopPollingLogs]);

  // Memoize context value to prevent unnecessary re-renders
  const contextValue = useMemo(() => ({
    selectWorkflow,
    displayMode,
    setDisplayMode,
    workflowStatus,
    workflowError,
    currentTaskId,
    currentExecutionMode,
    currentExecutionInputs,
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
    setWorkflowAppStatus,
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
    setIsCurrentUserOwner,
    refreshAuthenticationStatus,
    authRefreshTrigger,
    activeExecutions,
    visualOverlayActive,
    currentStreamingSession,
    overlayWorkflowInfo,
    currentRunId,
    setCurrentRunId,
    setVisualOverlayActive,
    setCurrentStreamingSession,
    setOverlayWorkflowInfo,
    anonymousUserId,
    isAnonymousUser,
    isInitializingAnonymous
  }), [
    selectWorkflow,
    displayMode,
    setDisplayMode,
    workflowStatus,
    workflowError,
    currentTaskId,
    currentExecutionMode,
    currentExecutionInputs,
    logPosition,
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
    setWorkflowAppStatus,
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
    setIsCurrentUserOwner,
    refreshAuthenticationStatus,
    authRefreshTrigger,
    activeExecutions,
    visualOverlayActive,
    currentStreamingSession,
    overlayWorkflowInfo,
    currentRunId,
    setCurrentRunId,
    setVisualOverlayActive,
    setCurrentStreamingSession,
    setOverlayWorkflowInfo,
    anonymousUserId,
    isAnonymousUser,
    isInitializingAnonymous
  ]);

  return (
    <AppContext.Provider value={contextValue}>
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
