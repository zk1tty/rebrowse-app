import React from 'react';
import { usePublicWorkflows } from '@/hooks/usePublicWorkflows';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Globe, Clock, User, Loader2, Palette} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAppContext } from '@/contexts/AppContext';
import { useTheme } from '@/contexts/ThemeContext';
import { checkWorkflowOwnership, hasValidSessionToken } from '@/utils/authUtils';

export const PublicWorkflowsGallery = () => {
  const { rows: workflows, loading, error } = usePublicWorkflows();
  const { currentUserSessionToken } = useAppContext();
  const { theme } = useTheme();
  const [ownershipStatus, setOwnershipStatus] = React.useState<{[key: string]: boolean}>({});

  const hasSessionToken = hasValidSessionToken(currentUserSessionToken);

  // Check ownership for each workflow if user is logged in
  React.useEffect(() => {
    if (!hasSessionToken || !workflows || workflows.length === 0) {
      return;
    }

    const checkOwnerships = async () => {
      const ownershipChecks: {[key: string]: boolean} = {};
      
      for (const workflow of workflows) {
        if (workflow.id && currentUserSessionToken) {
          try {
            const isOwner = await checkWorkflowOwnership(currentUserSessionToken, workflow.id);
            ownershipChecks[workflow.id] = isOwner;
          } catch (error) {
            console.error('Failed to check ownership for workflow:', workflow.id, error);
            ownershipChecks[workflow.id] = false;
          }
        }
      }
      
      setOwnershipStatus(ownershipChecks);
    };

    checkOwnerships();
  }, [workflows, currentUserSessionToken, hasSessionToken]);

  if (loading) {
    return (
      <div className={`flex flex-col items-center justify-center min-h-screen p-8 ${theme === 'dark' ? 'bg-black' : 'bg-white'}`}>
        <Loader2 className={`w-8 h-8 animate-spin mb-4 ${
          theme === 'dark' ? 'text-cyan-400' : 'text-purple-600'
        }`} />
        <p className={`text-lg ${
          theme === 'dark' ? 'text-cyan-300' : 'text-gray-600'
        }`}>
          Loading public workflows...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`flex flex-col items-center justify-center h-full p-8 ${theme === 'dark' ? 'bg-black' : 'bg-white'}`}>
        <div className={`p-6 rounded-xl border-2 ${
          theme === 'dark' 
            ? 'bg-gray-900 border-cyan-400 shadow-lg shadow-cyan-400/20' 
            : 'bg-red-50 border-red-200'
        }`}>
          <Globe className={`w-8 h-8 mx-auto mb-3 ${
            theme === 'dark' ? 'text-cyan-400' : 'text-red-500'
          }`} />
          <p className={`text-lg font-semibold text-center mb-2 ${
            theme === 'dark' ? 'text-cyan-300' : 'text-red-700'
          }`}>
            Failed to load workflows
          </p>
          <p className={`text-sm text-center ${
            theme === 'dark' ? 'text-cyan-200' : 'text-red-600'
          }`}>
            {error}
          </p>
        </div>
      </div>
    );
  }

  if (!workflows || workflows.length === 0) {
    return (
      <div className={`flex flex-col items-center justify-center h-full p-8 ${theme === 'dark' ? 'bg-black' : 'bg-white'}`}>
        <Globe className={`w-12 h-12 mb-4 ${
          theme === 'dark' ? 'text-cyan-400' : 'text-gray-400'
        }`} />
        <h2 className={`text-2xl font-bold mb-2 ${
          theme === 'dark' ? 'text-cyan-300' : 'text-gray-800'
        }`}>
          No Public Workflows Yet
        </h2>
        <p className={`text-center max-w-md ${
          theme === 'dark' ? 'text-cyan-200' : 'text-gray-600'
        }`}>
          Be the first to create and share a workflow! Public workflows will appear here for everyone to discover and use.
        </p>
      </div>
    );
  }

  return (
    <div className={`h-full overflow-auto p-6 ${theme === 'dark' ? 'bg-black' : 'bg-white'}`}>
      <div className="max-w-6xl mx-auto">
        <div className="mb-8 text-center">
          <h1 className={`text-4xl font-bold mb-4 ${
            theme === 'dark' ? 'text-cyan-300' : 'text-gray-800'
          }`}>
            <Palette className={`inline-block w-10 h-10 mr-3 ${
              theme === 'dark' ? 'text-cyan-400' : 'text-purple-600'
            }`} />
            Workflow Gallery
          </h1>
          <p className={`text-lg max-w-2xl mx-auto ${
            theme === 'dark' ? 'text-cyan-200' : 'text-gray-600'
          }`}>
            Discover workflows created by the community.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {workflows.map((workflow) => {
            const isOwner = workflow.id ? ownershipStatus[workflow.id] : false;
            
            return (
              <Card key={workflow.id} className={`hover:shadow-lg transition-shadow cursor-pointer ${
                theme === 'dark' ? 'bg-gray-900 border-gray-700' : ''
              }`}>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className={`text-lg font-semibold mb-2 ${
                        theme === 'dark' ? 'text-white' : 'text-gray-800'
                      }`}>
                        {workflow.name || 'Untitled Workflow'}
                      </CardTitle>
                      <CardDescription className={`text-sm line-clamp-2 ${
                        theme === 'dark' ? 'text-gray-300' : 'text-gray-600'
                      }`}>
                        {workflow.description || 'No description available'}
                      </CardDescription>
                    </div>
                    <Badge variant="secondary" className="ml-2">
                      <Globe className="w-3 h-3 mr-1" />
                      Public
                    </Badge>
                  </div>
                </CardHeader>
                
                <CardContent>
                  <div className="space-y-3">
                    {/* Workflow Stats */}
                    <div className={`flex items-center justify-between text-sm ${
                      theme === 'dark' ? 'text-gray-300' : 'text-gray-500'
                    }`}>
                      <div className="flex items-center">
                        <User className="w-4 h-4 mr-1" />
                        <span>
                          {isOwner ? 'You' : 'Anonymous'}
                        </span>
                      </div>
                      <div className="flex items-center">
                        <Clock className="w-4 h-4 mr-1" />
                        <span>
                          {workflow.created_at 
                            ? new Date(workflow.created_at).toLocaleDateString()
                            : 'Unknown'
                          }
                        </span>
                      </div>
                    </div>

                    {/* Steps Count */}
                    {workflow.steps && (
                      <div className={`text-sm ${
                        theme === 'dark' ? 'text-white' : 'text-gray-600'
                      }`}>
                        <span className="font-medium">{workflow.steps.length}</span> steps
                      </div>
                    )}

                    {/* Action Button */}
                    <Button 
                      className={`w-full mt-4 ${
                        theme === 'dark' ? 'text-white border-gray-600 hover:bg-gray-800' : ''
                      }`}
                      variant="outline"
                      onClick={() => {
                        // TODO: Navigate to workflow detail page
                        window.location.href = `/wf/${workflow.id}`;
                      }}
                    >
                      View Workflow
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}; 