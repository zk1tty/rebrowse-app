import React, { useState } from 'react';
import { Button } from '@/components/ui/button';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: { name: string | null; goal: string }) => void;
  isUploading: boolean;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  isUploading
}) => {
  const [workflowName, setWorkflowName] = useState('');
  const [userGoal, setUserGoal] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!userGoal.trim()) {
      alert('Please describe what you want to accomplish with this workflow.');
      return;
    }

    onSubmit({
      name: workflowName.trim() || null, // Let AI generate if empty
      goal: userGoal.trim()
    });

    // Reset form
    setWorkflowName('');
    setUserGoal('');
  };

  const handleClose = () => {
    if (!isUploading) {
      setWorkflowName('');
      setUserGoal('');
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <h2 className="text-xl font-semibold mb-4">🚀 Upload Your Recording</h2>
          
          <form onSubmit={handleSubmit}>
            {/* Workflow Name (Optional) */}
            <div className="mb-4">
              <label htmlFor="workflowName" className="block text-sm font-medium text-gray-700 mb-2">
                Workflow Name (Optional)
              </label>
              <input
                type="text"
                id="workflowName"
                value={workflowName}
                onChange={(e) => setWorkflowName(e.target.value)}
                placeholder="Leave empty for AI-generated name"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={isUploading}
              />
              <div className="text-xs text-gray-500 mt-1">
                💡 AI will generate a smart name based on your goal if left empty
              </div>
            </div>

            {/* User Goal (Required) */}
            <div className="mb-4">
              <label htmlFor="userGoal" className="block text-sm font-medium text-gray-700 mb-2">
                What are you trying to accomplish? *
              </label>
              <textarea
                id="userGoal"
                value={userGoal}
                onChange={(e) => setUserGoal(e.target.value)}
                placeholder="Describe what this workflow should do..."
                required
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                disabled={isUploading}
              />
              <div className="text-xs text-gray-500 mt-1">
                🎯 This helps AI create better workflows with smart optimizations
              </div>
            </div>

            {/* Examples */}
            <div className="bg-gray-50 p-4 rounded-md mb-6">
              <h4 className="text-sm font-medium text-gray-700 mb-2">💡 Good Goal Examples:</h4>
              <ul className="text-xs text-gray-600 space-y-1 list-disc list-inside">
                <li>"Search for JavaScript jobs on LinkedIn and save promising ones"</li>
                <li>"Update my GitHub profile with new project information"</li>
                <li>"Submit expense report in company portal for monthly reimbursement"</li>
                <li>"Create and share Google Doc for team meeting notes"</li>
                <li>"Order weekly groceries from online supermarket with my usual items"</li>
              </ul>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end space-x-3">
              <Button 
                type="button" 
                variant="outline" 
                onClick={handleClose}
                disabled={isUploading}
              >
                Cancel
              </Button>
              <Button 
                type="submit"
                disabled={isUploading || !userGoal.trim()}
                className="bg-blue-600 hover:bg-blue-700"
              >
                {isUploading ? (
                  <span className="flex items-center">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Processing...
                  </span>
                ) : (
                  '🚀 Process Recording'
                )}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}; 