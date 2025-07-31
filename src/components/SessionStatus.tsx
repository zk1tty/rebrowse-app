import React, { useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { 
  User, 
  Shield, 
  ShieldCheck, 
  ShieldX, 
  LogOut, 
  Chrome,
  AlertCircle,
  CheckCircle,
  Clock,
  RefreshCw,
  LogIn,
  BarChart3
} from 'lucide-react';
import { 
  getStoredSessionToken, 
  hasValidSessionToken, 
  getAuthType, 
  clearStoredAuth 
} from '@/utils/authUtils';
import { detectExtensionContext } from '@/utils/extensionUtils';
import { useAppContext } from '@/contexts/AppContext';
import { useTheme } from '@/contexts/ThemeContext';
import { useSessionValidation } from '@/hooks/useSessionValidation';

interface SessionStatusProps {
  className?: string;
  showDetails?: boolean;
  compact?: boolean;
}

export const SessionStatus: React.FC<SessionStatusProps> = ({ 
  className = '', 
  showDetails = false,
  compact = false 
}) => {
  const { currentUserSessionToken, setCurrentUserSessionToken } = useAppContext();
  const { theme } = useTheme();
  const [authType, setAuthType] = useState<string | null>(null);
  const [fromExtension, setFromExtension] = useState(false);
  
  // Use the new session validation hook
  const { 
    isValid: isAuthenticated, 
    isChecking, 
    lastChecked, 
    error: sessionError, 
    checkSession,
    refreshSession 
  } = useSessionValidation(60000); // Check every minute

  // Refresh session status (for extension context and auth type)
  const refreshStatus = () => {
    const type = getAuthType();
    const extensionContext = detectExtensionContext();
    const fromExt = extensionContext.isExtension;
    
    setAuthType(type);
    setFromExtension(fromExt);
  };

  useEffect(() => {
    refreshStatus();
    
    // Refresh every 30 seconds for extension context
    const interval = setInterval(refreshStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = () => {
    clearStoredAuth();
    setCurrentUserSessionToken(null);
    refreshStatus();
  };

  const handleRefresh = async () => {
    refreshStatus();
    await refreshSession();
  };

  const isSessionAuth = authType === 'session';
  const sessionToken = getStoredSessionToken();

  if (compact) {
    return (
      <div className={`flex items-center space-x-2 ${className}`}>
        {isAuthenticated ? (
          <>
            <ShieldCheck className="h-4 w-4 text-green-600" />
            <Badge variant="secondary" className="bg-green-100 text-green-800">
              Authenticated
            </Badge>
            {fromExtension && (
              <Chrome className="h-3 w-3 text-blue-600" />
            )}
          </>
        ) : (
          <>
            <ShieldX className="h-4 w-4 text-gray-400" />
            <Badge variant="outline" className="text-gray-600">
              Not Authenticated
            </Badge>
          </>
        )}
      </div>
    );
  }

  return (
    <div className={`border rounded-lg p-4 ${
      theme === 'dark' 
        ? 'bg-gray-900 border-gray-700' 
        : 'bg-white border-gray-200'
    } ${className}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          {isAuthenticated ? (
            <ShieldCheck className="h-5 w-5 text-green-600" />
          ) : (
            <ShieldX className="h-5 w-5 text-gray-400" />
          )}
          
          <div>
            <div className="flex items-center space-x-2">
              <span className={`font-medium ${
                theme === 'dark' ? 'text-white' : 'text-gray-900'
              }`}>
                {isAuthenticated ? 'Authenticated' : 'Not Authenticated'}
              </span>
              
              {isAuthenticated && (
                <Badge 
                  variant="secondary" 
                  className={`${isSessionAuth ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'}`}
                >
                  {isSessionAuth ? 'Session' : 'Legacy'}
                </Badge>
              )}
              
              {fromExtension && (
                <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                  <Chrome className="h-3 w-3 mr-1" />
                  Extension
                </Badge>
              )}
            </div>
            
            {showDetails && (
              <p className={`text-sm mt-1 ${
                theme === 'dark' ? 'text-gray-300' : 'text-gray-600'
              }`}>
                {isAuthenticated 
                  ? `Session active • Last checked: ${lastChecked ? lastChecked.toLocaleTimeString() : 'Never'}`
                  : sessionError || 'Login through Chrome extension to edit workflows'
                }
                {isChecking && (
                  <span className="ml-2">
                    <RefreshCw className="h-3 w-3 inline animate-spin" />
                  </span>
                )}
              </p>
            )}
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          {showDetails && isAuthenticated && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                const event = new CustomEvent('openUserConsole');
                window.dispatchEvent(event);
              }}
              className={`${
                theme === 'dark' 
                  ? 'text-cyan-400 hover:text-cyan-300 hover:bg-gray-800' 
                  : 'text-purple-600 hover:text-purple-700 hover:bg-purple-50'
              }`}
            >
              <BarChart3 className="h-3 w-3 mr-1" />
              Console
            </Button>
          )}
          
          {showDetails && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRefresh}
              disabled={isChecking}
              className={`${
                theme === 'dark' 
                  ? 'text-gray-300 hover:text-white hover:bg-gray-800' 
                  : 'text-gray-600 hover:text-gray-800'
              }`}
            >
              {isChecking ? (
                <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
              ) : (
                <Clock className="h-3 w-3 mr-1" />
              )}
              Refresh
            </Button>
          )}
          
          {isAuthenticated && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="text-red-600 hover:text-red-800 hover:bg-red-50"
            >
              <LogIn className="h-3 w-3 mr-1" />
              Logout
            </Button>
          )}
        </div>
      </div>
      
      {showDetails && isAuthenticated && (
        <div className={`mt-3 pt-3 border-t ${
          theme === 'dark' ? 'border-gray-700' : 'border-gray-200'
        }`}>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className={`${
                theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
              }`}>Auth Type:</span>
              <span className={`ml-2 font-medium ${
                theme === 'dark' ? 'text-white' : 'text-black'
              }`}>
                {isSessionAuth ? 'Session Token' : 'Legacy JWT'}
              </span>
            </div>
            <div>
              <span className={`${
                theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
              }`}>Source:</span>
              <span className={`ml-2 font-medium ${
                theme === 'dark' ? 'text-white' : 'text-black'
              }`}>
                {fromExtension ? 'Chrome Extension' : 'Web Interface'}
              </span>
            </div>
            <div className="col-span-2">
              <span className={`${
                theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
              }`}>Token:</span>
              <span className={`ml-2 font-mono text-xs px-2 py-1 rounded ${
                theme === 'dark' 
                  ? 'bg-gray-800 text-gray-300' 
                  : 'bg-gray-100 text-black'
              }`}>
                {sessionToken ? `${sessionToken.slice(0, 8)}...${sessionToken.slice(-4)}` : 'None'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SessionStatus; 