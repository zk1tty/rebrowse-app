/**
 * Chrome Storage Adapter for Supabase Auth
 * 
 * Supabase expects a storage interface with synchronous-like methods (getItem, setItem, removeItem)
 * but Chrome's storage API is async. This adapter bridges that gap.
 */

export interface SupabaseStorage {
  getItem(key: string): string | null | Promise<string | null>;
  setItem(key: string, value: string): void | Promise<void>;
  removeItem(key: string): void | Promise<void>;
}

/**
 * Creates a storage adapter that makes chrome.storage.local compatible 
 * with Supabase's expected storage interface
 */
export function createChromeStorageAdapter(): SupabaseStorage {
  return {
    async getItem(key: string): Promise<string | null> {
      try {
        const result = await chrome.storage.local.get([key]);
        return result[key] || null;
      } catch (error) {
        console.error('ChromeStorageAdapter.getItem error:', error);
        return null;
      }
    },

    async setItem(key: string, value: string): Promise<void> {
      try {
        await chrome.storage.local.set({ [key]: value });
      } catch (error) {
        console.error('ChromeStorageAdapter.setItem error:', error);
        throw error;
      }
    },

    async removeItem(key: string): Promise<void> {
      try {
        await chrome.storage.local.remove([key]);
      } catch (error) {
        console.error('ChromeStorageAdapter.removeItem error:', error);
        throw error;
      }
    }
  };
} 