import React from 'react';
import { usePublicWorkflows } from '@/hooks/usePublicWorkflows';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Globe, Clock, User, Loader2, Footprints, Brain, BarChart3, Heart, Eye, Play } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAppContext } from '@/contexts/AppContext';
import { useTheme } from '@/contexts/ThemeContext';
import { checkWorkflowOwnership, hasValidSessionToken } from '@/utils/authUtils';
import EnhancedWorkflowDashboard from '@/components/EnhancedWorkflowDashboard';
import '@/styles/brainAnimation.css';

export const PublicWorkflowsGallery = () => {
  const { rows: workflows, loading, error } = usePublicWorkflows();
  const { currentUserSessionToken, workflows: userWorkflows, activeExecutions } = useAppContext();
  const { theme } = useTheme();
  const [ownershipStatus, setOwnershipStatus] = React.useState<{[key: string]: boolean}>({});

  const hasSessionToken = hasValidSessionToken(currentUserSessionToken);

  // Helper function to get thumbnail image
  const getThumbnailImage = (workflow: any) => {
    // You can customize this logic based on your workflow data structure
    // For now, using a placeholder or workflow-specific image
    if (workflow.thumbnail_url) {
      return workflow.thumbnail_url;
    }
    
    // Return null to use CSS placeholder instead of external service
    return null;
  };

  // Helper function to get placeholder color, text, and emoji
  const getPlaceholderStyle = (workflow: any) => {
    const workflowName = workflow.name || 'workflow';
    const colors = [
      { bg: 'bg-blue-500', text: 'text-white' },
      { bg: 'bg-purple-500', text: 'text-white' },
      { bg: 'bg-green-500', text: 'text-white' },
      { bg: 'bg-red-500', text: 'text-white' },
      { bg: 'bg-yellow-500', text: 'text-black' },
      { bg: 'bg-indigo-500', text: 'text-white' }
    ];
    
    // Random emojis for different workflow types
    const emojis = [
      '🤖', '⚡', '🔧', '🚀', '💡', '🎯', '📊', '🎨', '📝',
      '🔍', '⚙️', '🌟', '💻', '📱', '🌐', '🔗', '📈', '🎪', '🎭',
      '🧠', '💎', '🔥', '❄️', '🌈', '🎵', '🎮', '📚', '🏆', '🎉'
    ];
    
    const colorIndex = workflowName.length % colors.length;
    const emojiIndex = (workflowName.length + workflowName.charCodeAt(0)) % emojis.length;
    
    return {
      ...colors[colorIndex] || colors[0],
      emoji: emojis[emojiIndex] || '🤖'
    };
  };

  // Helper function to get workflow stats
  const getWorkflowStats = (workflow: any) => {
    return {
      likes: workflow.likes_count || Math.floor(Math.random() * 50) + 1, // Placeholder data
      views: workflow.views_count || Math.floor(Math.random() * 200) + 10,
      runs: workflow.runs_count || Math.floor(Math.random() * 30) + 1,
      steps: workflow.steps?.length || 0
    };
  };

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
        {/* App Logo */}
        <div className="flex justify-center mb-6">
          <Brain className={`w-16 h-16 brain-animation ${
            theme === 'dark' ? 'text-cyan-400' : 'text-purple-600'
          }`} />
        </div>

        {/* App Title */}
        <h1 className={`text-2xl font-bold mb-6 ${
          theme === 'dark' ? 'text-white' : 'text-gray-900'
        }`}>
          Workflow Gallery
        </h1>

        {/* Loading Spinner and Text */}
        <div className="flex items-center space-x-3">
          <Loader2 className={`w-5 h-5 animate-spin ${
            theme === 'dark' ? 'text-cyan-400' : 'text-purple-600'
          }`} />
          <p className={`text-lg ${
            theme === 'dark' ? 'text-cyan-300' : 'text-gray-600'
          }`}>
            Loading public workflows...
          </p>
        </div>

        {/* Loading Progress Indicator */}
        <div className="mt-8 flex space-x-1">
          <div className={`w-2 h-2 rounded-full animate-bounce ${
            theme === 'dark' ? 'bg-cyan-400' : 'bg-purple-600'
          }`} style={{ animationDelay: '0ms' }} />
          <div className={`w-2 h-2 rounded-full animate-bounce ${
            theme === 'dark' ? 'bg-cyan-400' : 'bg-purple-600'
          }`} style={{ animationDelay: '150ms' }} />
          <div className={`w-2 h-2 rounded-full animate-bounce ${
            theme === 'dark' ? 'bg-cyan-400' : 'bg-purple-600'
          }`} style={{ animationDelay: '300ms' }} />
        </div>
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
            <Brain className={`inline-block w-10 h-10 mr-3 ${
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

        {/* Global User Dashboard - Only show if user has workflows */}
        {hasSessionToken && userWorkflows && userWorkflows.length > 0 && (
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4">
              <h2 className={`text-2xl font-semibold ${
                theme === 'dark' ? 'text-cyan-300' : 'text-gray-900'
              }`}>
                Your Workflow Analytics
              </h2>
              <Button 
                variant="outline"
                onClick={() => {
                  // We'll use a simple approach - open in new tab or modal
                  const event = new CustomEvent('openUserConsole');
                  window.dispatchEvent(event);
                }}
                className={`flex items-center gap-2 ${
                  theme === 'dark' 
                    ? 'text-cyan-400 hover:text-cyan-300 hover:bg-gray-800 border-gray-600' 
                    : 'text-purple-600 hover:text-purple-700 hover:bg-purple-50'
                }`}
              >
                <BarChart3 className="w-4 h-4" />
                </Button>
            </div>
            <EnhancedWorkflowDashboard 
              workflows={userWorkflows} 
              activeExecutions={activeExecutions}
            />
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {workflows.map((workflow) => {
            const isOwner = workflow.id ? ownershipStatus[workflow.id] : false;
            const stats = getWorkflowStats(workflow);
            const thumbnailUrl = getThumbnailImage(workflow);
            const placeholderStyle = getPlaceholderStyle(workflow);
            
            return (
              <Card key={workflow.id} className={`hover:shadow-lg transition-shadow cursor-pointer overflow-hidden ${
                theme === 'dark' ? 'bg-gray-900 border-gray-700' : ''
              }`}>
                {/* Card Thumbnail Image or Placeholder */}
                <div className="relative h-48 w-full overflow-hidden group cursor-pointer" onClick={() => {
                  // Navigate to workflow detail page
                  window.location.href = `/wf/${workflow.id}`;
                }}>
                  {thumbnailUrl ? (
                    <img 
                      src={thumbnailUrl}
                      alt={workflow.name || 'Workflow thumbnail'}
                      className="w-full h-full object-cover transition-transform group-hover:scale-105"
                    />
                  ) : (
                    <div className={`w-full h-full flex items-center justify-center transition-transform group-hover:scale-105 ${placeholderStyle?.bg || 'bg-blue-500'}`}>
                      <div className="text-center px-4">
                        <div className={`text-6xl mb-4 ${placeholderStyle?.text || 'text-white'}`}>
                          {placeholderStyle?.emoji || '🌱'}
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {/* Hover Overlay */}
                  <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center">
                    <div className="flex items-center space-x-2 text-white">
                      <Eye className="w-6 h-6" />
                      <span className="text-lg font-semibold">View</span>
                    </div>
                  </div>
                  
                  {/* Overlay with Public badge */}
                  <div className="absolute top-3 right-3">
                    <Badge variant="secondary" className="bg-black/70 text-white border-0">
                      <Globe className="w-3 h-3 mr-1" />
                      Public
                    </Badge>
                  </div>
                  
                  {/* Steps count skeleton button - bottom right */}
                  <div className="absolute bottom-3 right-3">
                    <div className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-semibold ${
                      theme === 'dark' 
                        ? 'bg-gray-800/80 text-gray-300 border border-gray-600' 
                        : 'bg-gray-100/80 text-gray-600 border border-gray-300'
                    }`}>
                      <Footprints className="w-6 h-6" />
                      <span>{stats.steps}</span>
                    </div>
                  </div>
                </div>

                <CardHeader className="pb-3">
                  <div className="space-y-2">
                    <CardTitle className={`text-lg font-semibold line-clamp-1 ${
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
                </CardHeader>
                
                <CardContent className="pt-0">
                  <div className="space-y-4">
                    {/* Author and Date */}
                    <div className={`flex items-center justify-between text-sm ${
                      theme === 'dark' ? 'text-gray-300' : 'text-gray-500'
                    }`}>
                      <div className="flex items-center">
                        <User className="w-4 h-4 mr-1" />
                        <span>
                          {isOwner ? 'You' : 'Community'}
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

                    {/* Stats Grid */}
                    <div className="flex items-center space-x-6">
                      {/* Views */}
                      <div className={`flex items-center space-x-2 text-base ${
                        theme === 'dark' ? 'text-white' : 'text-gray-600'
                      }`}>
                        <Eye className="w-6 h-6" />
                        <span className="font-semibold">{stats.views}</span>
                      </div>
                      
                      {/* Likes */}
                      <div className={`flex items-center space-x-2 text-base ${
                        theme === 'dark' ? 'text-white' : 'text-gray-600'
                      }`}>
                        <Heart className="w-6 h-6" />
                        <span className="font-semibold">{stats.likes}</span>
                      </div>

                      {/* Runs */}
                      <div className={`flex items-center space-x-2 text-base ${
                        theme === 'dark' ? 'text-white' : 'text-gray-600'
                      }`}>
                        <Play className="w-6 h-6" />
                        <span className="font-semibold">{stats.runs}</span>
                      </div>
                    </div>

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