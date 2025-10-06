import React, { useState } from 'react';
import { z } from 'zod';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import { GripVertical, Trash2 } from 'lucide-react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { stepSchema } from '@/types/workflow-layout.types';
import { useTheme } from '@/contexts/ThemeContext';

type Step = z.infer<typeof stepSchema>;
type StepType = z.infer<typeof stepSchema>['type'];

// Get the step types used in the dropdowns from the schema
const stepTypes = stepSchema.shape.type.options as StepType[];

interface SortableStepProps {
  step: Step;
  index: number;
  onDelete: (index: number) => void;
  onUpdate: (index: number, key: keyof Step, value: unknown) => void;
  disabled?: boolean;
}

export function SortableStep({
  step,
  index,
  onDelete,
  onUpdate,
  disabled = false,
}: SortableStepProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { theme } = useTheme();
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: index });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    position: 'relative' as const,
    zIndex: isDragging ? 1 : 0,
    touchAction: 'none',
  };

  return (
    <Card
      ref={setNodeRef}
      style={style}
      className={`${
        theme === 'dark' ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'
      } ${isDragging ? 'shadow-lg' : ''}`}
    >
      <CardHeader className="pb-2">
        <CardTitle className={`flex justify-between items-center ${
          theme === 'dark' ? 'text-white' : 'text-black'
        }`}>
          <span className="flex gap-2 items-center">
            <GripVertical
              className={`w-4 h-4 ${disabled ? 'text-gray-300 cursor-not-allowed' : 'text-gray-400 cursor-grab'}`}
              {...(disabled ? {} : attributes)}
              {...(disabled ? {} : listeners)}
            />
            Step {index + 1}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(index)}
            className="text-red-600 hover:text-red-700"
            disabled={disabled}
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="space-y-2">
          <div>
            <Label className={`capitalize ${theme === 'dark' ? 'text-white' : ''}`}>type</Label>
            <Select
              value={step.type}
              onValueChange={(val) => onUpdate(index, 'type', val)}
              disabled={disabled}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {stepTypes.map((type) => (
                  <SelectItem key={type} value={type}>
                    {type}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className={`capitalize ${theme === 'dark' ? 'text-white' : ''}`}>description</Label>
            <Input
              value={step.description ?? ''}
              onChange={(e) => onUpdate(index, 'description', e.target.value)}
              disabled={disabled}
            />
          </div>
        </div>

        <div
          className={`overflow-hidden transition-all duration-200 ${
            isExpanded ? 'max-h-[500px] opacity-100' : 'max-h-0 opacity-0'
          }`}
        >
          <div className="space-y-2">
            {/* Show commonly edited fields explicitly when present */}
            {/* clipboard_paste uses 'content' instead of 'output' */}
            {step.type === 'clipboard_paste' && (
              <div>
                <Label className={`capitalize ${theme === 'dark' ? 'text-white' : ''}`}>content</Label>
                <Input
                  value={(step as any).content ?? ''}
                  onChange={(e) => onUpdate(index, 'content' as keyof Step, e.target.value)}
                  disabled={disabled}
                />
              </div>
            )}
            {step.type !== 'clipboard_paste' && typeof (step as any).output !== 'undefined' && (
              <div>
                <Label className={`capitalize ${theme === 'dark' ? 'text-white' : ''}`}>output</Label>
                <Input
                  value={(step as any).output ?? ''}
                  onChange={(e) => onUpdate(index, 'output', e.target.value)}
                  disabled={disabled}
                />
              </div>
            )}

            {typeof (step as any).cssSelector !== 'undefined' && (
              <div>
                <Label className={`capitalize ${theme === 'dark' ? 'text-white' : ''}`}>cssSelector</Label>
                <Input
                  placeholder={'e.g., [data-testid="primaryColumn"] button[aria-label="Copy text"]'}
                  value={(step.cssSelector as any) ?? ''}
                  onChange={(e) => onUpdate(index, 'cssSelector', e.target.value)}
                  disabled={disabled}
                />
              </div>
            )}

            {typeof (step as any).timeoutMs !== 'undefined' && (
              <div>
                <Label className={`capitalize ${theme === 'dark' ? 'text-white' : ''}`}>timeoutMs</Label>
                <Input
                  type="number"
                  inputMode="numeric"
                  value={(step as any).timeoutMs ?? ''}
                  onChange={(e) => {
                    const raw = e.target.value;
                    const parsed = raw === '' ? null : Number.parseInt(raw, 10);
                    onUpdate(index, 'timeoutMs' as keyof Step, (Number.isNaN(parsed) ? null : parsed) as any);
                  }}
                  disabled={disabled}
                />
              </div>
            )}

            {/* Render any remaining optional fields dynamically except core ones */}
            {Object.keys(step).map((key) => {
              const value = step[key as keyof Step];
              if (
                [
                  'type',
                  'description',
                  'timestamp',
                  'tabId',
                  'output',
                  'content',
                  'cssSelector',
                  'timeoutMs',
                ].includes(key)
              ) return null;

              return (
                <div key={key}>
                  <Label className={`capitalize ${theme === 'dark' ? 'text-white' : ''}`}>{key}</Label>
                  <Input
                    value={(value as any) ?? ''}
                    onChange={(e) => onUpdate(index, key as keyof Step, e.target.value)}
                    disabled={disabled}
                  />
                </div>
              );
            })}
          </div>
        </div>

        <div className="pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className={`w-full ${
              theme === 'dark' 
                ? 'hover:bg-gray-800 text-white border-gray-600' 
                : 'hover:bg-gray-100'
            }`}
          >
            {isExpanded ? 'Show Less' : 'Show More'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
