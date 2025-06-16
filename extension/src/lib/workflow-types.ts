// --- Workflow Format ---

export interface Workflow {
  steps: Step[];
  name: string; // Consider how to populate these fields
  description: string; // Consider how to populate these fields
  version: string; // Consider how to populate these fields
  input_schema: [];
}

export type Step =
  | NavigationStep
  | ClickStep
  | InputStep
  | KeyPressStep
  | ScrollStep;
// Add other step types here as needed, e.g., SelectStep, TabCreatedStep etc.

export interface BaseStep {
  type: string;
  timestamp: number;
  tabId: number;
  url?: string; // Made optional as not all original events have it directly
}

export interface NavigationStep extends BaseStep {
  type: "navigation";
  url: string; // Navigation implies a URL change
  screenshot?: string; // Optional in source
}

export interface ClickStep extends BaseStep {
  type: "click";
  url: string;
  frameUrl: string;
  xpath: string;
  cssSelector?: string; // Optional in source
  elementTag: string;
  elementText: string;
  screenshot?: string; // Optional in source
}

export interface InputStep extends BaseStep {
  type: "input";
  url: string;
  frameUrl: string;
  xpath: string;
  cssSelector?: string; // Optional in source
  elementTag: string;
  value: string;
  screenshot?: string; // Optional in source
}

export interface KeyPressStep extends BaseStep {
  type: "key_press";
  url?: string; // Can be missing if key press happens without element focus? Source is optional.
  frameUrl?: string; // Might be missing
  key: string;
  xpath?: string; // Optional in source
  cssSelector?: string; // Optional in source
  elementTag?: string; // Optional in source
  screenshot?: string; // Optional in source
}

export interface ScrollStep extends BaseStep {
  type: "scroll"; // Changed from scroll_update for simplicity
  targetId: number; // The rrweb ID of the element being scrolled
  scrollX: number;
  scrollY: number;
  // Note: url might be missing if scroll happens on initial load before meta event?
}

// Potential future step types based on StoredEvent
// export interface SelectStep extends BaseStep { ... }
// export interface TabCreatedStep extends BaseStep { ... }
// export interface TabActivatedStep extends BaseStep { ... }
// export interface TabRemovedStep extends BaseStep { ... }
