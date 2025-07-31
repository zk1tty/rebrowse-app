/**
 * Simple tests for workflow validation utilities
 * These can be run manually in the browser console for debugging
 */

import { isValidWorkflowId, hasValidWorkflowId, getWorkflowIdentifier, isValidWorkflow } from './workflowValidation';

// Test cases for validation functions
export const testWorkflowValidation = () => {
  console.log('🧪 Testing Workflow Validation Utilities');
  
  // Test isValidWorkflowId
  console.log('📋 Testing isValidWorkflowId:');
  console.log('  Valid UUID:', isValidWorkflowId('123e4567-e89b-12d3-a456-426614174000')); // true
  console.log('  undefined:', isValidWorkflowId(undefined)); // false
  console.log('  "undefined":', isValidWorkflowId('undefined')); // false
  console.log('  null:', isValidWorkflowId(null)); // false
  console.log('  empty string:', isValidWorkflowId('')); // false
  console.log('  whitespace:', isValidWorkflowId('   ')); // false
  
  // Test hasValidWorkflowId
  console.log('📋 Testing hasValidWorkflowId:');
  console.log('  Valid workflow:', hasValidWorkflowId({ id: '123e4567-e89b-12d3-a456-426614174000', name: 'Test' })); // true
  console.log('  No ID:', hasValidWorkflowId({ name: 'Test' })); // false
  console.log('  undefined ID:', hasValidWorkflowId({ id: undefined, name: 'Test' })); // false
  console.log('  "undefined" ID:', hasValidWorkflowId({ id: 'undefined', name: 'Test' })); // false
  
  // Test getWorkflowIdentifier
  console.log('📋 Testing getWorkflowIdentifier:');
  console.log('  Full workflow:', getWorkflowIdentifier({ id: '123', name: 'Test Workflow' })); // "Test Workflow (123)"
  console.log('  Name only:', getWorkflowIdentifier({ name: 'Test Workflow' })); // "Test Workflow"
  console.log('  ID only:', getWorkflowIdentifier({ id: '123' })); // "123"
  console.log('  Empty object:', getWorkflowIdentifier({})); // "unnamed workflow"
  console.log('  null:', getWorkflowIdentifier(null)); // "unknown"
  
  // Test isValidWorkflow
  console.log('📋 Testing isValidWorkflow:');
  console.log('  Valid workflow:', isValidWorkflow({ name: 'Test Workflow', id: '123' })); // true
  console.log('  No name:', isValidWorkflow({ id: '123' })); // false
  console.log('  Empty name:', isValidWorkflow({ name: '', id: '123' })); // false
  console.log('  Whitespace name:', isValidWorkflow({ name: '   ', id: '123' })); // false
  console.log('  null:', isValidWorkflow(null)); // false
  
  console.log('✅ Workflow validation tests completed');
}; 