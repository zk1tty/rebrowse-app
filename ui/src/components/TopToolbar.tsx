import { Play, Settings, Edit3, Blocks, SidebarOpen, Terminal, Palette, LogIn, Moon, Sun, Link, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SidebarTrigger } from '@/components/ui/sidebar';
import { useAppContext } from '@/contexts/AppContext';
import { useTheme } from '@/contexts/ThemeContext';
import { useEffect, useState } from 'react';
import { hasValidSessionToken, canEditWorkflow } from '@/utils/authUtils';
import SessionLoginModal from '@/components/SessionLoginModal';
import SessionStatus from '@/components/SessionStatus';
import { CompactExtensionIndicator } from '@/components/ExtensionBanner';
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
    isCurrentWorkflowPublic
  } = useAppContext();
  
  const { theme, toggleTheme } = useTheme();
  const { toast } = useToast();
  const [showLoginModal, setShowLoginModal] = useState(false);
  
  const hasSessionToken = hasValidSessionToken(currentUserSessionToken);
  const isLegacyWorkflow = currentWorkflowData?.owner_id === null;
  const canEdit = canEditWorkflow(
    currentUserSessionToken, 
    isCurrentUserOwner, 
    isCurrentWorkflowPublic, 
    isLegacyWorkflow
  );
  const canExecute = hasSessionToken || isCurrentWorkflowPublic;

  // 🔍 Debug logging for authentication state
  console.log('🔍 [TopToolbar] Auth Debug:', {
    currentUserSessionToken: currentUserSessionToken ? `${currentUserSessionToken.slice(0,8)}...` : null,
    hasSessionToken,
    isCurrentUserOwner,
    isCurrentWorkflowPublic,
    isLegacyWorkflow,
    canEdit,
    canExecute,
    workflowName: currentWorkflowData?.name,
    workflowOwnerId: currentWorkflowData?.owner_id
  });

  // Debug log to see if currentWorkflowData is updating
  console.log("TopToolbar: currentWorkflowData:", currentWorkflowData?.name || "null");

  // Track changes to currentWorkflowData
  useEffect(() => {
    console.log("TopToolbar: currentWorkflowData changed to:", currentWorkflowData?.name || "null");
  }, [currentWorkflowData]);

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

  const handleRunAsTool = () => {
    if (!canExecute) {
      setShowLoginModal(true);
      return;
    }
    if (checkForUnsavedChanges()) {
      return;
    }
    console.log('Running workflow as tool:', currentWorkflowData?.name);
    setActiveDialog('runAsTool');
  };

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
    
    // Generate the workflow URL
    const workflowUrl = isCurrentWorkflowPublic 
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
            
            {!hasSessionToken && (
              <Button
                variant="outline"
                size="lg"
                onClick={() => setShowLoginModal(true)}
                className="flex items-center gap-2 text-blue-600 hover:text-blue-700 hover:bg-blue-50 text-base px-6 py-3"
              >
                <LogIn className="w-5 h-5" />
                Login
              </Button>
            )}

            <Button
              variant="outline"
              size="lg"
              onClick={handleRunWithInputs}
              disabled={!currentWorkflowData || workflowStatus === 'running' || !canExecute}
              className={`flex items-center gap-2 text-base px-6 py-3 disabled:opacity-50 ${
                theme === 'dark' 
                  ? 'text-white border-gray-600 hover:bg-gray-800' 
                  : 'text-white'
              }`}
              title={!canExecute ? 'Login required to execute workflows' : ''}
            >
              <Play className="w-5 h-5" />
              {!canExecute ? 'Login to Run' : 'Run with Inputs'}
            </Button>

            {/* tempolary disabled
            <Button
              variant="outline"
              size="lg"
              onClick={handleRunAsTool}
              disabled={!currentWorkflowData || workflowStatus === 'running' || !canExecute}
              className="flex items-center gap-2 text-base px-6 py-3 disabled:opacity-50"
              title={!canExecute ? 'Login required to execute workflows' : ''}
            >
              <Settings className="w-5 h-5" />
              {!canExecute ? 'Login to Run' : 'Run as Tool'}
            </Button> */}

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
    </>
  );
}
