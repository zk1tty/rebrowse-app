import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Chrome, 
  LogIn,
  Key, 
  AlertCircle, 
  CheckCircle, 
  Download
} from 'lucide-react';
import { useAppContext } from '@/contexts/AppContext';
import { 
  initializeSessionFromExtension,
  validateSessionToken 
} from '@/utils/authUtils';
import { useToast } from '@/hooks/use-toast';
import { useTheme } from '@/contexts/ThemeContext';

interface SessionLoginModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export const SessionLoginModal: React.FC<SessionLoginModalProps> = ({
  open,
  onOpenChange
}) => {
  const { setCurrentUserSessionToken, refreshAuthenticationStatus } = useAppContext();
  const { toast } = useToast();
  const { theme } = useTheme();
  const [sessionToken, setSessionToken] = useState('');
  const [isValidating, setIsValidating] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSessionTokenSubmit = async () => {
    if (!sessionToken.trim()) {
      setValidationError('Please enter a session token');
      return;
    }

    setIsValidating(true);
    setValidationError(null);

    try {
      // Basic validation - check if it looks like a valid token
      if (sessionToken.length < 10) {
        throw new Error('Session token appears to be too short');
      }

      // Validate with backend before storing
      const isValid = await validateSessionToken(sessionToken);
      
      if (!isValid) {
        throw new Error('Session token is invalid or expired. Please get a new one from the Chrome extension.');
      }

      // Store the session token
      initializeSessionFromExtension(sessionToken);
      setCurrentUserSessionToken(sessionToken);

      // Close modal and reset form
      onOpenChange(false);
      setSessionToken('');
      setValidationError(null);

      // NEW: Trigger authentication refresh across all components
      refreshAuthenticationStatus();

      toast({
        title: 'Login Successful! ✅',
        description: 'You are now authenticated and can edit workflows.',
      });
      
    } catch (error) {
      console.error('❌ [SessionLoginModal] Session token validation failed:', error);
      setValidationError(
        error instanceof Error ? error.message : 'Invalid session token'
      );
    } finally {
      setIsValidating(false);
    }
  };

  const handleOpenChromeExtensions = (event: React.MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    const url = 'chrome://extensions';
    const newWindow = window.open(url, '_blank', 'noopener,noreferrer');
    if (!newWindow) {
      toast({
        title: 'Popup blocked',
        description: 'Please open chrome://extensions manually from your browser.',
        variant: 'destructive',
      });
    }
  };

  const handleGetExtension = () => {
    // Try multiple approaches for downloading the extension
    try {
      // First try: Direct download from public directory
      const link = document.createElement('a');
      link.href = '/chrome-extension.zip';
      link.download = 'chrome-extension.zip';
      link.target = '_blank';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      toast({
        title: 'Download Started',
        description: 'Chrome extension zip file is being downloaded.',
      });
    } catch (error) {
      // Fallback: Show instructions or redirect to GitHub releases
      toast({
        title: 'Download Issue',
        description: 'Please contact support for the Chrome extension download.',
        variant: 'destructive',
      });
      console.error('Download failed:', error);
    }
  };

  // const copyExtensionUrl = () => {
  //   navigator.clipboard.writeText('/chrome-extension.zip');
  //   toast({
  //     title: 'Copied!',
  //     description: 'Extension download path copied to clipboard',
  //   });
  // };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className={`flex items-center space-x-2 ${
            theme === 'dark' ? 'text-white' : 'text-black'
          }`}>
            <LogIn className={`h-5 w-5 ${
              theme === 'dark' ? 'text-blue-400' : 'text-blue-600'
            }`} />
            <span>Login to Record Workflows</span>
          </DialogTitle>
          <DialogDescription className={
            theme === 'dark' ? 'text-gray-300' : 'text-gray-600'
          }>
            Login from Recorder - Chrome extension.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Extension Installation Guide */}
          <Alert className={`border ${
            theme === 'dark' 
              ? 'border-gray-600 bg-black' 
              : 'border-blue-200 bg-blue-50'
          }`}>
            <Chrome className={`h-4 w-4 ${
              theme === 'dark' ? 'text-blue-400' : 'text-blue-600'
            }`} />
            <AlertDescription>
              <div className="space-y-2">
                <p className={`font-medium ${
                  theme === 'dark' ? 'text-blue-300' : 'text-blue-800'
                }`}>Don't have the extension yet?</p>
                <div className="flex items-center space-x-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleGetExtension}
                    className={`${
                      theme === 'dark' 
                        ? 'border-gray-600 text-blue-400 hover:bg-gray-800 bg-gray-900' 
                        : 'border-blue-300 text-blue-700 hover:bg-blue-100'
                    }`}
                  >
                    <Download className="h-3 w-3 mr-1" />
                    Install
                  </Button>
                  {/* <Button
                    variant="ghost"
                    size="sm"
                    onClick={copyExtensionUrl}
                    className={`${
                      theme === 'dark' 
                        ? 'text-blue-400 hover:text-blue-300 hover:bg-gray-800' 
                        : 'text-blue-600 hover:text-blue-800'
                    }`}
                  >
                    <Copy className="h-3 w-3 mr-1" />
                    Copy URL
                  </Button> */}
                </div>
              </div>
            </AlertDescription>
          </Alert>

          {/* Session Token Input */}
          <div className="space-y-2">
            <Label htmlFor="sessionToken" className={`flex items-center space-x-2 ${
              theme === 'dark' ? 'text-white' : 'text-black'
            }`}>
              <Key className={`h-4 w-4 ${
                theme === 'dark' ? 'text-gray-300' : 'text-gray-600'
              }`} />
              <span>Session Token</span>
            </Label>
            <Input
              id="sessionToken"
              type="password"
              placeholder="Paste your session token"
              value={sessionToken}
              onChange={(e) => {
                setSessionToken(e.target.value);
                setValidationError(null);
              }}
              className={`font-mono text-sm ${
                theme === 'dark' 
                  ? 'bg-gray-900 border-gray-600 text-white placeholder-gray-400' 
                  : 'bg-white border-gray-300 text-black'
              }`}
              disabled={isValidating}
            />
            <p className={`text-xs ${
              theme === 'dark' ? 'text-gray-400' : 'text-gray-600'
            }`}>
              Extract your session token from the popup.
            </p>
          </div>

          {/* Validation Error */}
          {validationError && (
            <Alert className={`border ${
              theme === 'dark' 
                ? 'border-red-600 bg-red-900/20' 
                : 'border-red-200 bg-red-50'
            }`}>
              <AlertCircle className={`h-4 w-4 ${
                theme === 'dark' ? 'text-red-400' : 'text-red-600'
              }`} />
              <AlertDescription className={
                theme === 'dark' ? 'text-red-300' : 'text-red-800'
              }>
                {validationError}
              </AlertDescription>
            </Alert>
          )}

          {/* Instructions */}
          <div className={`rounded-lg p-3 ${
            theme === 'dark' ? 'bg-gray-800 border border-gray-600' : 'bg-gray-50'
          }`}>
            <h4 className={`font-medium mb-2 ${
              theme === 'dark' ? 'text-white' : 'text-gray-900'
            }`}>How to Login:</h4>
            <ol className={`text-sm space-y-1 list-decimal list-inside ${
              theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
            }`}>
              <li>Click Install buttton above.</li>
              <li>
                Go to <a href="chrome://extensions" target="_blank" rel="noopener noreferrer" onClick={handleOpenChromeExtensions} className={theme === 'dark' ? 'text-blue-400 underline underline-offset-2' : 'text-blue-600 underline underline-offset-2 hover:text-blue-800'}>chrome://extensions</a>
              </li>
              <li>Go to "Load unpacked"</li>
              <li>Select the folder where you downloaded.</li>
              <li>Go to Login app</li>
            </ol>
          </div>
        </div>

        <DialogFooter className="flex items-center justify-between">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isValidating}
            className={
              theme === 'dark' 
                ? 'border-gray-600 text-white hover:bg-gray-800' 
                : ''
            }
          >
            Cancel
          </Button>
          <Button
            onClick={handleSessionTokenSubmit}
            disabled={!sessionToken.trim() || isValidating}
            className={`text-white ${
              theme === 'dark' 
                ? 'bg-blue-600 hover:bg-blue-700' 
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            {isValidating ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                Validating...
              </>
            ) : (
              <>
                <CheckCircle className="h-4 w-4 mr-2" />
                Login
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default SessionLoginModal; 