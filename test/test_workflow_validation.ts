import { workflowSchema } from '@/types/workflow-layout.types';

// TODO: Add more tests for Step Types.
export const testClickToCopySchema = () => {
  console.log('🧪 Testing click_to_copy step schema');
  const workflow = {
    workflow_analysis: 'Test analysis',
    name: 'Test Workflow',
    description: 'A workflow to test click_to_copy',
    version: '1.0.0',
    steps: [
      {
        description: 'Click Copy and capture clipboard',
        output: 'copiedText',
        timestamp: null,
        tabId: null,
        type: 'click_to_copy',
        cssSelector: '[data-testid="primaryColumn"] button[aria-label="Copy text"]',
        timeoutMs: 4000,
      },
    ],
    input_schema: [],
  };

  try {
    const parsed = workflowSchema.parse(workflow);
    console.log('✅ click_to_copy schema accepted:', parsed.steps[0]);
  } catch (e) {
    console.error('❌ click_to_copy schema rejected:', e);
  }
};

if (import.meta.env.MODE !== 'test') {
  // Allow manual run via node/ts-node or bundler
  testClickToCopySchema();
}


