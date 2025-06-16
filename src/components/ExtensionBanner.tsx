import React, { useEffect, useState } from 'react';
import { detectExtensionContext, isFromExtension, type ExtensionContext } from '@/utils/extensionUtils';
import { Chrome } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';

// Compact version for navigation bar
interface CompactExtensionIndicatorProps {
  className?: string;
}

export const CompactExtensionIndicator: React.FC<CompactExtensionIndicatorProps> = ({ 
  className = '' 
}) => {
  const { theme } = useTheme();
  const [context, setContext] = useState<ExtensionContext | null>(null);
  const [fromExtension, setFromExtension] = useState(false);

  useEffect(() => {
    const extensionContext = detectExtensionContext();
    const isFromExt = isFromExtension();
    
    setContext(extensionContext);
    setFromExtension(isFromExt);
  }, []);

  // Only show if user came from extension or is in extension context
  if (!fromExtension && !context?.isExtension) {
    return null;
  }

  return (
    <div className={`flex items-center space-x-2 p-2 rounded-lg border ${
      theme === 'dark' 
        ? 'bg-cyan-900/30 border-cyan-400 shadow-lg shadow-cyan-400/20' 
        : 'bg-blue-50 border-blue-200'
    } ${className}`}>
      <Chrome className={`h-4 w-4 ${
        theme === 'dark' ? 'text-cyan-400' : 'text-blue-600'
      }`} />
      <span className={`text-sm font-medium ${
        theme === 'dark' ? 'text-cyan-300' : 'text-blue-900'
      }`}>
        Chrome Extension
      </span>
      <div 
        className={`w-2 h-2 rounded-full ${
          theme === 'dark' ? 'bg-cyan-400 shadow-lg shadow-cyan-400/50' : 'bg-red-500'
        }`}
        title={context?.isExtension ? 'Active' : 'Connected'}
      />
    </div>
  );
}; 