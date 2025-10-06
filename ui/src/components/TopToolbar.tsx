import { 
  Play, 
  Edit3, 
  Blocks, 
  SidebarOpen, 
  Palette, 
  LogIn, 
  Moon, 
  Sun, 
  ExternalLink,
  AlertTriangle,
  Loader2,
  BarChart3,
  Cookie
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SidebarTrigger } from '@/components/ui/sidebar';
import { useAppContext } from '@/contexts/AppContext';
import { useTheme } from '@/contexts/ThemeContext';
import { useEffect, useState } from 'react';
import { hasValidSessionToken, canEditWorkflow, getStoredSessionToken, getAuthType } from '@/utils/authUtils';
import { detectExtensionContext, sendMessageToExtension } from '@/utils/extensionUtils';
import { useSessionValidation } from '@/hooks/useSessionValidation';
import SessionLoginModal from '@/components/SessionLoginModal';
import SessionStatus from '@/components/SessionStatus';
import { CompactExtensionIndicator } from '@/components/ExtensionBanner';
import UserConsole from '@/components/UserConsole';
import { useToast } from '@/hooks/use-toast';

export function TopToolbar() {
  const {
    setDisplayMode,
    displayMode,
    currentWorkflowData,
    setActiveDialog,
    checkForUnsavedChanges,
    workflowStatus,
    currentUserSessionToken,
    isCurrentUserOwner,
    isCurrentWorkflowPublic,
    // authRefreshTrigger,
    // setCurrentUserSessionToken
  } = useAppContext();
  
  const { theme, toggleTheme } = useTheme();
  const { toast } = useToast();
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [showUserConsole, setShowUserConsole] = useState(false);
  
  // Use the new session validation hook for real-time authentication status
  const { isValid: hasValidSession, isChecking: isValidatingSession } = useSessionValidation(30000);
  
  // For backward compatibility, also check the stored token
  const hasSessionToken = hasValidSessionToken(currentUserSessionToken) && hasValidSession;
  const isLegacyWorkflow = currentWorkflowData?.owner_id === null;
  const canEdit = canEditWorkflow(
    currentUserSessionToken, 
    isCurrentUserOwner, 
    isCurrentWorkflowPublic, 
    isLegacyWorkflow
  );
  const canExecute = hasSessionToken || isCurrentWorkflowPublic;

  // Determine anonymous state
  // Prefer explicit auth type flag, fallback to heuristic (context token without stored token)
  const storedToken = getStoredSessionToken();
  const authType = getAuthType();
  const isAnonymous = Boolean(authType === 'anonymous' || (currentUserSessionToken && !storedToken));

  // Handle logout
  // const handleLogout = () => {
  //   clearStoredAuth();
  //   setCurrentUserSessionToken(null);
  //   toast({
  //     title: 'Logged Out',
  //     description: 'You have been successfully logged out.',
  //   });
  // };

  // Dynamic Login Banner Component
  const LoginStatusBanner = () => {
    const handleLoginAsYouClick = async () => {
      try {
        const context = detectExtensionContext();
        if (context.isExtension) {
          await sendMessageToExtension({ type: 'OPEN_AUTH_POPUP' });
          return;
        }
        // Fallback: open in-app login modal when not in extension context
        setShowLoginModal(true);
      } catch {
        setShowLoginModal(true);
      }
    };
    // Case 1: No session token at all
    if (!currentUserSessionToken) {
      return (
        <Button
          variant="outline"
          size="lg"
          onClick={() => setShowLoginModal(true)}
          className="flex items-center gap-2 text-blue-600 hover:text-blue-700 hover:bg-blue-50 text-base px-6 py-3 border-blue-200"
        >
          <LogIn className="w-5 h-5" />
          Login
        </Button>
      );
    }

    // Case 2: Session is being validated
    if (isValidatingSession) {
      return (
        <Button
          variant="outline"
          size="lg"
          disabled
          className="flex items-center gap-2 text-yellow-600 border-yellow-200 bg-yellow-50 text-base px-6 py-3"
        >
          <Loader2 className="w-5 h-5 animate-spin" />
          Checking...
        </Button>
      );
    }

    // Case 3: Anonymous session active -> prompt to login as real user via extension
    if (isAnonymous) {
      return (
        <Button
          variant="outline"
          size="lg"
          onClick={handleLoginAsYouClick}
          className="flex items-center gap-2 text-blue-600 hover:text-blue-700 hover:bg-blue-50 text-base px-6 py-3 border-blue-200"
        >
          <Cookie className="w-5 h-5" />
          Login as you
        </Button>
      );
    }

    // Case 4: Session is valid and authenticated - show nothing
    if (hasValidSession && hasSessionToken) {
      return null;
    }

    // Case 5: Session token exists but is invalid/expired
    if (currentUserSessionToken && !hasValidSession) {
      return (
        <Button
          variant="outline"
          size="lg"
          onClick={() => setShowLoginModal(true)}
          className="flex items-center gap-2 text-orange-600 hover:text-orange-700 hover:bg-orange-50 border-orange-200 bg-orange-50 text-base px-6 py-3"
        >
          <AlertTriangle className="w-5 h-5" />
          Session Expired
        </Button>
      );
    }

    // Fallback
    return (
      <Button
        variant="outline"
        size="lg"
        onClick={() => setShowLoginModal(true)}
        className="flex items-center gap-2 text-blue-600 hover:text-blue-700 hover:bg-blue-50 text-base px-6 py-3"
      >
        <LogIn className="w-5 h-5" />
        Login
      </Button>
    );
  };



  // Listen for custom event to open user console
  useEffect(() => {
    const handleOpenUserConsole = () => {
      setShowUserConsole(true);
    };
    const handleOpenLoginModal = () => {
      setShowLoginModal(true);
    };
    
    window.addEventListener('openUserConsole', handleOpenUserConsole);
    window.addEventListener('openLoginModal', handleOpenLoginModal);
    return () => {
      window.removeEventListener('openUserConsole', handleOpenUserConsole);
      window.removeEventListener('openLoginModal', handleOpenLoginModal);
    };
  }, []);

  const handleRunWithInputs = () => {
    if (!canExecute) {
      setShowLoginModal(true);
      return;
    }
    if (checkForUnsavedChanges()) {
      return;
    }
    console.log('Running workflow with inputs:', currentWorkflowData?.name);
    setActiveDialog('run');
  };

  // const handleRunAsTool = () => {
  //   if (!canExecute) {
  //     setShowLoginModal(true);
  //     return;
  //   }
  //   if (checkForUnsavedChanges()) {
  //     return;
  //   }
  //   console.log('Running workflow as tool:', currentWorkflowData?.name);
  //   setActiveDialog('runAsTool');
  // };

  const handleToggleMode = () => {
    if (displayMode === 'canvas' && !canEdit) {
      setShowLoginModal(true);
      return;
    }
    if (displayMode === 'canvas') {
      console.log('Editing workflow:', currentWorkflowData?.name);
      setDisplayMode('editor');
    } else {
      console.log('Switching to canvas:', currentWorkflowData?.name);
      setDisplayMode('canvas');
    }
  };

  const handleNavigateToGallery = () => {
    if (checkForUnsavedChanges()) {
      return;
    }
    console.log('Navigating to gallery');
    setDisplayMode('start');
  };

  const handleShareWorkflow = async () => {
    if (!currentWorkflowData) return;
    
    // Prefer modern /wf/{id} route for both public and private workflows when ID is available
    // Fall back to legacy /workflows/{name} only for private workflows without IDs
    const workflowUrl = currentWorkflowData.id 
      ? `${window.location.origin}/wf/${currentWorkflowData.id}`
      : `${window.location.origin}/workflows/${currentWorkflowData.name}`;
    
    try {
      await navigator.clipboard.writeText(workflowUrl);
      toast({
        title: 'Link Copied! 🔗',
        description: 'Workflow link has been copied to your clipboard.',
      });
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
      toast({
        title: 'Copy Failed',
        description: 'Unable to copy link to clipboard. Please try again.',
        variant: 'destructive',
      });
    }
  };

  return (
    <>
      <div className={`border-b px-6 py-4 ${
        theme === 'dark' 
          ? 'bg-black border-gray-700' 
          : 'bg-background border-border'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <SidebarTrigger className={`p-2 hover:bg-gray-100 rounded-md ${
              theme === 'dark' 
                ? 'text-cyan-300 hover:bg-gray-800 hover:text-cyan-200' 
                : 'text-gray-600 hover:text-gray-800'
            }`}>
              <SidebarOpen className="w-4 h-4" />
            </SidebarTrigger>
            
            <Button
              variant="outline"
              size="sm"
              onClick={handleNavigateToGallery}
              className={`flex items-center gap-2 ${
                theme === 'dark' 
                  ? 'text-cyan-400 hover:text-cyan-300 hover:bg-gray-800 border-gray-600' 
                  : 'text-purple-600 hover:text-purple-700 hover:bg-purple-50'
              }`}
              title="Back to Gallery"
            >
              <Palette className="w-5 h-5" />
              <span className="hidden sm:inline">Gallery</span>
            </Button>

            {/* Session Status in Toolbar */}
            <SessionStatus compact={true} />
          </div>

          <div className="flex items-center gap-3">
            {/* Chrome Extension Indicator */}
            <CompactExtensionIndicator />
            
            {/* User Console Button - Only show if logged in */}
            {hasSessionToken && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowUserConsole(true)}
                className={`flex items-center gap-2 ${
                  theme === 'dark' 
                    ? 'text-cyan-400 hover:text-cyan-300 hover:bg-gray-800 border-gray-600' 
                    : 'text-purple-600 hover:text-purple-700 hover:bg-purple-50'
                }`}
                title="Open Analytics"
              >
                <BarChart3 className="w-4 h-4" />
              </Button>
            )}

            {/* Dark Mode Toggle */}
            <Button
              variant="outline"
              size="sm"
              onClick={toggleTheme}
              className="flex items-center gap-2"
              title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
            >
              {theme === 'light' ? (
                <Moon className="w-4 h-4" />
              ) : (
                <Sun className="w-4 h-4" />
              )}
            </Button>
            
            <LoginStatusBanner />

            <Button
              variant="outline"
              size="lg"
              onClick={handleRunWithInputs}
              disabled={!currentWorkflowData || workflowStatus === 'running' || !canExecute}
              className={`flex items-center gap-2 text-base px-6 py-3 disabled:opacity-50 ${
                theme === 'dark' 
                  ? 'text-white border-gray-600 hover:bg-gray-800' 
                  : 'text-blue-600 hover:text-blue-700 hover:bg-blue-50 border-blue-200'
              }`}
              title={!canExecute ? 'Login required to execute workflows' : ''}
            >
              <Play className="w-5 h-5" />
              {!canExecute ? 'Run' : 'Run'}
            </Button>

            <Button
              variant="default"
              size="lg"
              onClick={handleToggleMode}
              disabled={!currentWorkflowData || (displayMode === 'canvas' && !canEdit)}
              className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white text-base px-6 py-3 disabled:opacity-50"
              title={displayMode === 'canvas' && !canEdit ? 'Login required to edit workflows' : ''}
            >
              {displayMode === 'editor' 
                ? <>
                    <Blocks className="w-5 h-5" />
                    Canvas
                  </>
                : <>
                    <Edit3 className="w-5 h-5" />
                    Edit
                  </>}
            </Button>

            <Button
              variant="outline"
              size="lg"
              onClick={handleShareWorkflow}
              disabled={!currentWorkflowData}
              className={`flex items-center gap-2 text-base px-6 py-3 disabled:opacity-50 ${
                theme === 'dark' 
                  ? 'text-cyan-400 hover:text-cyan-300 hover:bg-gray-800 border-gray-600' 
                  : 'text-gray-600 hover:text-gray-800 hover:bg-gray-50'
              }`}
              title="Share workflow link"
            >
              <ExternalLink className="w-5 h-5" />
              Share
            </Button>
          </div>
        </div>
      </div>
      
      {/* Session Login Modal */}
      <SessionLoginModal 
        open={showLoginModal} 
        onOpenChange={setShowLoginModal} 
      />

      {/* User Console Modal */}
      {showUserConsole && (
        <div className="fixed inset-0 z-50 bg-black bg-opacity-50 flex items-center justify-center p-4">
          <div className="w-full h-full max-w-none bg-white dark:bg-gray-900 rounded-lg overflow-hidden">
            <UserConsole onClose={() => setShowUserConsole(false)} />
          </div>
        </div>
      )}
    </>
  );
}
