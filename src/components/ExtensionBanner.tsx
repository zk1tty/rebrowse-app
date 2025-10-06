import React, { useEffect, useState } from 'react';
import { detectExtensionContext, isFromExtension, type ExtensionContext } from '@/utils/extensionUtils';
import { getStoredSessionToken } from '@/utils/authUtils';
import { Chrome } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { useAppContext } from '@/contexts/AppContext';

// Compact version for navigation bar
interface CompactExtensionIndicatorProps {
  className?: string;
}

export const CompactExtensionIndicator: React.FC<CompactExtensionIndicatorProps> = ({ 
  className = '' 
  }) => {
    const { theme } = useTheme();
    const { currentUserSessionToken, authRefreshTrigger, isAnonymousUser } = useAppContext();
  const [context, setContext] = useState<ExtensionContext | null>(null);
  const [fromExtension, setFromExtension] = useState(false);

  // Refresh function to update extension context
  const refreshExtensionStatus = () => {
    const extensionContext = detectExtensionContext();
    const isFromExt = isFromExtension();
    
    setContext(extensionContext);
    setFromExtension(isFromExt);
  };

  useEffect(() => {
    refreshExtensionStatus();
  }, []);

  // Refresh when authentication status changes
  useEffect(() => {
    refreshExtensionStatus();
  }, [currentUserSessionToken]);

  // Refresh when authentication refresh is triggered
  useEffect(() => {
    refreshExtensionStatus();
  }, [authRefreshTrigger]);

  // Only show if user came from extension or is in extension context
  if (!fromExtension && !context?.isExtension) {
    return null;
  }

  const storedToken = getStoredSessionToken();
  const isAnonymous = Boolean(isAnonymousUser || (currentUserSessionToken && !storedToken));

  const handleLoginAsYou = () => {
    try {
      window.dispatchEvent(new CustomEvent('openLoginModal'));
    } catch {
      // no-op
    }
  };

  return (
    <div className={`flex items-center space-x-2 p-2 rounded-lg border ${
      theme === 'dark' 
        ? 'bg-cyan-900/30 border-cyan-400 shadow-lg shadow-cyan-400/20' 
        : 'bg-blue-50 border-blue-200'
    } ${className}`}>
      <Chrome className={`h-4 w-4 ${
        theme === 'dark' ? 'text-cyan-400' : 'text-blue-600'
      }`} />
      {isAnonymous ? (
        <button
          type="button"
          onClick={handleLoginAsYou}
          className={`${
            theme === 'dark'
              ? 'text-cyan-200 hover:text-cyan-100'
              : 'text-blue-800 hover:text-blue-900'
          } text-sm font-medium underline-offset-2 hover:underline`}
          title="Login as you via Chrome extension"
        >
          Login as you
        </button>
      ) : (
        <span className={`text-sm font-medium ${
          theme === 'dark' ? 'text-cyan-300' : 'text-blue-900'
        }`}>
          Chrome Extension
        </span>
      )}
      <div 
        className={`w-2 h-2 rounded-full ${
          theme === 'dark' ? 'bg-cyan-400 shadow-lg shadow-cyan-400/50' : 'bg-green-500'
        }`}
        title={context?.isExtension ? 'Active' : 'Connected'}
      />
    </div>
  );
}; 