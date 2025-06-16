import React, { useEffect, useState } from 'react';
import { z } from 'zod';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Plus, Loader2, CheckCircle2 } from 'lucide-react';
import { useAppContext } from '@/contexts/AppContext';
import { workflowSchema, stepSchema } from '@/types/workflow-layout.types';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { toast } from 'sonner';
import { SortableStep } from './SortableStep';
import { UnsavedChangesDialog } from './UnsavedChangesDialog';
import { workflowService } from '@/services/workflowService';
import { canEditWorkflow } from '@/utils/authUtils';
import AuthBanner from '@/components/AuthBanner';
import SessionStatus from '@/components/SessionStatus';
import { useTheme } from '@/contexts/ThemeContext';

type Workflow = z.infer<typeof workflowSchema>;
type Step = z.infer<typeof stepSchema>;

export function WorkflowEditor() {
  const {
    currentWorkflowData,
    isCurrentWorkflowPublic,
    currentUserSessionToken,
    isCurrentUserOwner,
    updateWorkflowUI,
    setEditorStatus,
    editorStatus,
    activeDialog,
    setActiveDialog,
    setDisplayMode,
  } = useAppContext();
  const { theme } = useTheme();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [oldWorkflow, setOldWorkflow] = useState<Workflow | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Calculate permissions using simplified auth utilities
  const isLegacyWorkflow = workflow?.owner_id === null; // NULL owner_id = legacy workflow
  const canEdit = canEditWorkflow(currentUserSessionToken, isCurrentUserOwner, isCurrentWorkflowPublic, isLegacyWorkflow);
  const hasSessionToken = !!currentUserSessionToken;
  const showLoginPrompt = !hasSessionToken;
  const showForkButton = isCurrentWorkflowPublic && !isCurrentUserOwner && hasSessionToken;

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  useEffect(() => {
    if (currentWorkflowData) {
      console.log('🔍 [WorkflowEditor] currentWorkflowData:', currentWorkflowData);
      console.log('🔍 [WorkflowEditor] currentWorkflowData.name:', currentWorkflowData.name);
      console.log('🔍 [WorkflowEditor] currentWorkflowData.id:', currentWorkflowData.id);
      console.log('🔍 [WorkflowEditor] currentWorkflowData keys:', Object.keys(currentWorkflowData));
      
      const safeWorkflow = workflowSchema.safeParse(currentWorkflowData);
      if (safeWorkflow.success) {
        console.log('🔍 [WorkflowEditor] safeWorkflow.data.name:', safeWorkflow.data.name);
        setWorkflow(safeWorkflow.data);
        setOldWorkflow(safeWorkflow.data);
        setEditorStatus('saved');
      } else {
        console.error('Invalid workflow data', safeWorkflow.error);
        console.error('🔍 [WorkflowEditor] Failed to parse workflow:', currentWorkflowData);
      }
    }
  }, [currentWorkflowData, setEditorStatus]);

  // Track changes and update editor status
  useEffect(() => {
    if (workflow && oldWorkflow) {
      const hasChanges =
        JSON.stringify(workflow) !== JSON.stringify(oldWorkflow);
      setEditorStatus(hasChanges ? 'unsaved' : 'saved');
    }
  }, [workflow, oldWorkflow, setEditorStatus]);

  const updateField = (key: keyof Workflow, value: any) => {
    setWorkflow((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const updateStepField = (index: number, key: keyof Step, value: any) => {
    if (!workflow) return;
    const newSteps = [...workflow.steps];
    const updatedStep = { ...newSteps[index], [key]: value } as Step;
    newSteps[index] = updatedStep;
    setWorkflow({ ...workflow, steps: newSteps });
    console.log(`Step at index ${index} updated:`, updatedStep);
  };

  const addStep = () => {
    if (!workflow) return;
    const newStep = stepSchema.parse({
      description: 'New step',
      type: 'click',
      timestamp: null as number | null,
      tabId: null as number | null,
      output: null,
      url: null,
      cssSelector: null,
      xpath: null,
      elementTag: null,
      elementText: null,
      selectedText: null,
      value: null,
      task: null,
    });
    setWorkflow({ ...workflow, steps: [...workflow.steps, newStep] });
  };

  const deleteStep = (index: number) => {
    if (!workflow) return;
    const updated = workflow.steps.filter((_, i) => i !== index);
    setWorkflow({ ...workflow, steps: updated });
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!workflow || !over || active.id === over.id || !canEdit) return;

    const oldIndex = workflow.steps.findIndex((_, i) => i === active.id);
    const newIndex = workflow.steps.findIndex((_, i) => i === over.id);

    setWorkflow({
      ...workflow,
      steps: arrayMove(workflow.steps, oldIndex, newIndex),
    });
  };

  const saveChanges = async () => {
    if (!workflow || !oldWorkflow) return;

    console.log('🔍 [WorkflowEditor] saveChanges called');
    console.log('🔍 [WorkflowEditor] oldWorkflow:', oldWorkflow);
    console.log('🔍 [WorkflowEditor] oldWorkflow.name:', oldWorkflow.name);
    console.log('🔍 [WorkflowEditor] workflow:', workflow);
    console.log('🔍 [WorkflowEditor] workflow.name:', workflow.name);

    // Check permissions using simplified auth utilities
    if (!canEdit) {
      const message = !hasSessionToken 
        ? 'Please login through the Chrome extension to edit workflows.'
        : 'You do not have permission to edit this workflow. Try forking it to your collection.';
      
      toast.error(message, {
        duration: 4000,
        style: { fontSize: '1.25rem', padding: '16px' },
      });
      return;
    }

    const validation = workflowSchema.safeParse(workflow);
    if (!validation.success) {
      const errorMessage = 'Invalid workflow data';
      setSaveError(errorMessage);
      toast.error(saveError, {
        duration: 4000,
        style: { fontSize: '1.25rem', padding: '16px' },
      });
      return;
    }

    setIsSaving(true);
    setSaveError(null);

    try {
      const newWorkflow = validation.data;
      
      // QUICK FIX: Get workflow ID from oldWorkflow or currentWorkflowData
      const workflowId = oldWorkflow.id || currentWorkflowData?.id;
      if (!workflowId) {
        throw new Error('Workflow ID not available. Cannot save changes to this workflow.');
      }

      console.log('🔍 [WorkflowEditor] Using workflow ID for save:', workflowId);

      // QUICK FIX: Single full workflow update instead of individual step operations
      const updateResponse = await workflowService.updateWorkflow(
        workflowId, 
        newWorkflow, 
        currentUserSessionToken || undefined
      );

      if (updateResponse.success) {
        // Update UI state
        updateWorkflowUI(oldWorkflow, newWorkflow);
        setOldWorkflow(newWorkflow);
        setEditorStatus('saved');
        toast.success('Changes saved successfully', {
          icon: <CheckCircle2 className="w-4 h-4 text-green-500" />,
          duration: 2000,
          style: { fontSize: '1.25rem', padding: '16px' },
        });
      } else {
        const errorMessage = updateResponse.error || 'Failed to save workflow';
        setSaveError(errorMessage);
        toast.error(errorMessage, {
          duration: 4000,
          style: { fontSize: '1.25rem', padding: '16px' },
        });
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unexpected error occurred';
      setSaveError(errorMessage);
      toast.error(saveError, {
        duration: 4000,
        style: { fontSize: '1.25rem', padding: '16px' },
      });
    } finally {
      setIsSaving(false);
      setActiveDialog(null);
    }
  };

  const handleDiscardChanges = () => {
    if (oldWorkflow) {
      setWorkflow(oldWorkflow);
      setEditorStatus('saved');
      setDisplayMode('editor');
      setActiveDialog(null);
    }
  };

  const handleCancel = () => {
    setDisplayMode('editor');
    setActiveDialog(null);
  };

  const handleGetExtension = () => {
    toast.info('Install our Chrome extension to login and manage workflows.', {
      duration: 4000,
      style: { fontSize: '1.25rem', padding: '16px' },
    });
  };

  const handleForkWorkflow = () => {
    toast.info('Fork functionality coming in Phase 2!', {
      duration: 3000,
      style: { fontSize: '1.25rem', padding: '16px' },
    });
  };

  if (!workflow)
    return <div className="p-8 text-gray-500">No workflow loaded</div>;

  return (
    <div className={`relative min-h-screen ${theme === 'dark' ? 'bg-black' : 'bg-white'}`}>
      {activeDialog === 'unsavedChanges' && (
        <UnsavedChangesDialog
          onSave={saveChanges}
          onDiscard={handleDiscardChanges}
          onCancel={handleCancel}
          isSaving={isSaving}
        />
      )}
      <div className="p-6 max-w-4xl mx-auto space-y-6 pb-24">
        {/* Session Status */}
        <SessionStatus 
          showDetails={true} 
          className="mb-4" 
        />

        {/* Enhanced Authentication & Permission Banner */}
        <AuthBanner 
          className="mb-6"
          onGetExtension={handleGetExtension}
          onForkWorkflow={handleForkWorkflow}
        />
        <div className="space-y-2">
          <h2 className={`text-xl font-semibold mb-3 ${
            theme === 'dark' ? 'text-white' : 'text-black'
          }`}>Workflow Details</h2>
          <Label className={theme === 'dark' ? 'text-white' : ''}>Workflow Name</Label>
          <Input
            value={workflow.name}
            onChange={(e) => updateField('name', e.target.value)}
            disabled={!canEdit}
          />
          <Label className={theme === 'dark' ? 'text-white' : ''}>Description</Label>
          <Textarea
            value={workflow.description}
            onChange={(e) => updateField('description', e.target.value)}
            className="min-h-[100px] resize-y"
            disabled={!canEdit}
          />
          <Label className={theme === 'dark' ? 'text-white' : ''}>Analysis</Label>
          <Textarea
            value={workflow.workflow_analysis}
            onChange={(e) => updateField('workflow_analysis', e.target.value)}
            className="min-h-[150px] resize-y"
            disabled={!canEdit}
          />
        </div>

        <div className="flex justify-between items-center">
          <h2 className={`text-xl font-semibold ${
            theme === 'dark' ? 'text-white' : 'text-black'
          }`}>Steps</h2>
          <Button 
            onClick={addStep} 
            disabled={!canEdit}
            className={`${
              theme === 'dark' 
                ? 'bg-cyan-600 hover:bg-cyan-700 text-white border-cyan-500' 
                : 'bg-primary hover:bg-primary/90 text-primary-foreground'
            }`}
          >
            <Plus className="w-4 h-4 mr-1" />
            Add Step
          </Button>
        </div>

        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={workflow.steps.map((_, index) => index)}
            strategy={verticalListSortingStrategy}
          >
            <div className="space-y-4">
              {workflow.steps.map((step, index) => (
                <SortableStep
                  key={index}
                  step={step}
                  index={index}
                  onDelete={deleteStep}
                  onUpdate={updateStepField}
                  disabled={!canEdit}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      </div>

      <div className={`fixed bottom-0 left-0 right-0 ml-40 border-t p-4 ${
        theme === 'dark' ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'
      }`}>
        <div className="max-w-4xl mx-auto space-y-2">
          <Button
            className="w-full ml-10 bg-purple-600 text-white disabled:opacity-50"
            onClick={saveChanges}
            disabled={isSaving || editorStatus === 'saved' || !canEdit}
          >
            {isSaving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving Changes...
              </>
            ) : !hasSessionToken ? (
              'Login Required to Edit'
            ) : !canEdit ? (
              'Read-Only (No Edit Permission)'
            ) : (
              'Confirm Changes'
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
