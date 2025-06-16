import React from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  ShieldCheck, 
  ShieldX, 
  Chrome, 
  AlertTriangle, 
  Info, 
  Lock,
  Unlock,
  GitFork,
  Crown
} from 'lucide-react';
import { useAppContext } from '@/contexts/AppContext';
import { 
  hasValidSessionToken, 
  canEditWorkflow, 
  getAuthType 
} from '@/utils/authUtils';
import { detectExtensionContext } from '@/utils/extensionUtils';
import { useTheme } from '@/contexts/ThemeContext';

interface AuthBannerProps {
  className?: string;
  onGetExtension?: () => void;
  onForkWorkflow?: () => void;
}

export const AuthBanner: React.FC<AuthBannerProps> = ({ 
  className = '',
  onGetExtension,
  onForkWorkflow
}) => {
  const {
    currentUserSessionToken,
    isCurrentUserOwner,
    isCurrentWorkflowPublic,
    currentWorkflowData
  } = useAppContext();
  const { theme } = useTheme();

  const hasSessionToken = hasValidSessionToken(currentUserSessionToken);
  const authType = getAuthType();
  const extensionContext = detectExtensionContext();
  const fromExtension = extensionContext.isExtension;
  const isLegacyWorkflow = currentWorkflowData?.owner_id === null;
  
  const canEdit = canEditWorkflow(
    currentUserSessionToken, 
    isCurrentUserOwner, 
    isCurrentWorkflowPublic, 
    isLegacyWorkflow
  );

  // Don't show banner if user is authenticated and has edit permissions
  if (hasSessionToken && canEdit && !isCurrentWorkflowPublic) {
    return null;
  }

  // Not authenticated - show login prompt
  if (!hasSessionToken) {
    return (
      <Alert className={`border-yellow-200 bg-yellow-50 ${className}`}>
        <Chrome className="h-4 w-4 text-yellow-600" />
        <AlertDescription className="flex items-center justify-between">
          <div>
            <span className="font-medium text-yellow-800">Chrome Extension Login Required</span>
            <p className="text-yellow-700 text-sm mt-1">
              To edit workflows, upload recordings, and manage your collection, please login through our Chrome extension.
            </p>
          </div>
          <Button 
            variant="outline" 
            size="sm"
            className="border-yellow-300 text-yellow-700 hover:bg-yellow-100 ml-4"
            onClick={onGetExtension}
          >
            <Chrome className="h-3 w-3 mr-1" />
            Get Extension
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  // Authenticated but viewing public workflow
  if (hasSessionToken && isCurrentWorkflowPublic) {
    return (
      <Alert className={`${
        theme === 'dark' 
          ? 'border-cyan-400 bg-gray-800' 
          : 'border-blue-200 bg-blue-50'
      } ${className}`}>
        <Info className={`h-4 w-4 ${
          theme === 'dark' ? 'text-cyan-400' : 'text-blue-600'
        }`} />
        <AlertDescription className="flex items-center justify-between">
          <div className="flex-1">
            <div className="flex items-center space-x-2 mb-1">
              <span className={`font-medium ${
                theme === 'dark' ? 'text-cyan-300' : 'text-blue-800'
              }`}>
                {isCurrentUserOwner ? 'Your Public Workflow' : 'Public Workflow'}
              </span>
              
              {isCurrentUserOwner && (
                <Badge variant="secondary" className={`${
                  theme === 'dark' 
                    ? 'bg-cyan-800 text-cyan-200' 
                    : 'bg-blue-100 text-blue-700'
                }`}>
                  <Crown className="h-3 w-3 mr-1" />
                  Owner
                </Badge>
              )}
              
              {isLegacyWorkflow && (
                <Badge variant="outline" className={`${
                  theme === 'dark'
                    ? 'border-orange-400 text-orange-300'
                    : 'border-orange-300 text-orange-700'
                }`}>
                  Legacy
                </Badge>
              )}
              
              {fromExtension && (
                <Badge variant="outline" className={`${
                  theme === 'dark'
                    ? 'bg-gray-700 text-cyan-300 border-cyan-400'
                    : 'bg-blue-50 text-blue-700 border-blue-200'
                }`}>
                  <Chrome className="h-3 w-3 mr-1" />
                  Extension
                </Badge>
              )}
            </div>
            
            <p className={`text-sm ${
              theme === 'dark' ? 'text-cyan-200' : 'text-blue-700'
            }`}>
              {isCurrentUserOwner 
                ? 'This is your public workflow. You can edit it or change its visibility.'
                : isLegacyWorkflow
                ? 'This is a legacy workflow. Anyone with login can edit it.'
                : 'This is a public workflow owned by another user. You can view and execute it, or fork it to make changes.'
              }
            </p>
          </div>
          
          {!isCurrentUserOwner && !isLegacyWorkflow && (
            <Button 
              variant="outline" 
              size="sm"
              className="border-blue-300 text-blue-700 hover:bg-blue-100 ml-4"
              onClick={onForkWorkflow}
            >
              <GitFork className="h-3 w-3 mr-1" />
              Fork to Edit
            </Button>
          )}
        </AlertDescription>
      </Alert>
    );
  }

  // Authenticated but no edit permissions
  if (hasSessionToken && !canEdit) {
    return (
      <Alert className={`border-orange-200 bg-orange-50 ${className}`}>
        <Lock className="h-4 w-4 text-orange-600" />
        <AlertDescription>
          <div className="flex items-center justify-between">
            <div>
              <span className="font-medium text-orange-800">Read-Only Access</span>
              <p className="text-orange-700 text-sm mt-1">
                You don't have permission to edit this workflow. Contact the owner or fork it to your collection.
              </p>
            </div>
            
            {isCurrentWorkflowPublic && (
              <Button 
                variant="outline" 
                size="sm"
                className="border-orange-300 text-orange-700 hover:bg-orange-100 ml-4"
                onClick={onForkWorkflow}
              >
                <GitFork className="h-3 w-3 mr-1" />
                Fork Workflow
              </Button>
            )}
          </div>
        </AlertDescription>
      </Alert>
    );
  }

  return null;
};

export default AuthBanner; 