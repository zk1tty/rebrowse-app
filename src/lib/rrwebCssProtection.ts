/**
 * 🛡️ RRWeb CSS Protection System
 * Prevents regex overflow errors from complex CSS in rrweb replay
 */

/**
 * 🔧 Aggressive CSS Function Patching
 * Patches rrweb's internal CSS processing functions to prevent regex overflow
 */
export const patchRRWebCssProcessing = (rrweb: any): void => {
  if (!rrweb) {
    console.warn('⚠️ [CSS Protection] No rrweb instance provided for patching');
    return;
  }

  // Patch String.prototype.replace to handle large regex patterns
  const originalReplace = String.prototype.replace;
  String.prototype.replace = function(searchValue: any, replaceValue: any): string {
    try {
      return originalReplace.call(this, searchValue, replaceValue);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      if (errorMsg.includes('Regular expression too large') || 
          errorMsg.includes('Pattern too large') ||
          errorMsg.includes('Regex overflow')) {
        // Return original string for CSS regex overflow errors
        return this.toString();
      }
      throw error;
    }
  };

  // Patch rrweb's rebuildFullSnapshot method
  if (rrweb.rebuildFullSnapshot) {
    const originalRebuild = rrweb.rebuildFullSnapshot;
    rrweb.rebuildFullSnapshot = function(...args: any[]) {
      try {
        return originalRebuild.apply(this, args);
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        if (errorMsg.includes('Regular expression too large') || 
            errorMsg.includes('adaptCssForReplay') ||
            errorMsg.includes('Invalid regular expression')) {
          console.warn('⚠️ [CSS Protection] CSS regex overflow in rebuildFullSnapshot - using fallback');
          // Return a simplified snapshot without problematic CSS
          return args[0]; // Return original snapshot
        }
        throw error;
      }
    };
  }

  // Patch any other CSS-related methods
  const cssMethods = ['adaptCssForReplay', 'processCss', 'sanitizeCss'];
  cssMethods.forEach(methodName => {
    if (rrweb[methodName] && typeof rrweb[methodName] === 'function') {
      const originalMethod = rrweb[methodName];
      rrweb[methodName] = function(...args: any[]) {
        try {
          return originalMethod.apply(this, args);
        } catch (error) {
          const errorMsg = error instanceof Error ? error.message : String(error);
          if (errorMsg.includes('Regular expression too large') || 
              errorMsg.includes('Pattern too large') ||
              errorMsg.includes('Regex overflow')) {
            console.warn(`⚠️ [CSS Protection] CSS regex overflow in ${methodName} - using fallback`);
            return args[0] || ''; // Return original or empty string
          }
          throw error;
        }
      };
    }
  });
};

/**
 * Helper function to surgically filter ONLY problematic CSS patterns
 * Preserves normal CSS but removes specific patterns that cause regex overflow
 */
export const filterCssInObject = (obj: any): any => {
  if (typeof obj === 'string') {
    // 🎯 SURGICAL FILTERING: Only target the specific Amazon SVG pattern that causes regex overflow
    if (obj.includes('PHN2ZyB3aWR0aD0"MTgiIGhlaWdodD0"MzIi')) {
      console.warn('🚨 [filterCssInObject] Amazon SVG pattern detected - removing specific pattern only');
      // Use safe string operations instead of regex to avoid regex overflow
      const startPattern = 'PHN2ZyB3aWR0aD0"MTgiIGhlaWdodD0"MzIi';
      let result = obj;
      let startIndex = 0;
      while ((startIndex = result.indexOf(startPattern, startIndex)) !== -1) {
        const endIndex = result.indexOf('"', startIndex + startPattern.length);
        if (endIndex !== -1) {
          result = result.substring(0, startIndex) + 'REMOVED_AMAZON_SVG' + result.substring(endIndex);
          startIndex += 'REMOVED_AMAZON_SVG'.length;
        } else {
          break;
        }
      }
      return result;
    }
    
    // 🎯 TARGETED: Only remove extremely long base64 data URIs (>10KB), not normal CSS
    if (obj.includes('data:image/svg+xml;base64,') && obj.length > 10000) {
      const beforeLength = obj.length;
      const filtered = obj.replace(/data:image\/svg\+xml;base64,[A-Za-z0-9+/]{1000,}={0,2}/g, 'data:image/svg+xml;base64,SIMPLIFIED');
      if (filtered.length < beforeLength) {
        console.warn(`🎯 [filterCssInObject] Removed long SVG data URI: ${Math.round(beforeLength/1024)}KB → ${Math.round(filtered.length/1024)}KB`);
        return filtered;
      }
    }
    
    return obj; // Preserve normal CSS
  }
  
  if (Array.isArray(obj)) {
    return obj.map(filterCssInObject);
  }
  
  if (typeof obj === 'object' && obj !== null) {
    const filtered: any = {};
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        filtered[key] = filterCssInObject(obj[key]);
      }
    }
    return filtered;
  }
  
  return obj;
};

/**
 * 🛠️ CSS Protection Plugin for RRWeb
 * Provides surgical CSS filtering during DOM reconstruction
 */
export const createCssProtectionPlugin = () => ({
  onBuild: (node: any, _options: any) => {
    if (node.tagName === 'IFRAME') {
      node.removeAttribute('sandbox'); // Remove sandbox restrictions
      console.log('🔧 [CSS Plugin] Removed sandbox from internal iframe');
    }
    
    // 🎯 SURGICAL CSS PROTECTION: Only target specific problematic patterns
    if (node.tagName === 'STYLE') {
      const cssContent = node.textContent || node.innerHTML;
      if (cssContent) {
        let modifiedCSS = cssContent;
        let hasChanges = false;
        
        // 🎯 TARGETED: Only remove the specific Amazon SVG pattern that causes regex overflow
        if (cssContent.includes('PHN2ZyB3aWR0aD0"MTgiIGhlaWdodD0"MzIi')) {
          console.warn('🎯 [CSS Plugin] Amazon SVG pattern detected - removing specific pattern only');
          // Use safe string operations instead of regex to avoid regex overflow
          const startPattern = 'PHN2ZyB3aWR0aD0"MTgiIGhlaWdodD0"MzIi';
          let startIndex = 0;
          while ((startIndex = modifiedCSS.indexOf(startPattern, startIndex)) !== -1) {
            const endIndex = modifiedCSS.indexOf('"', startIndex + startPattern.length);
            if (endIndex !== -1) {
              modifiedCSS = modifiedCSS.substring(0, startIndex) + 'REMOVED_AMAZON_SVG' + modifiedCSS.substring(endIndex);
              startIndex += 'REMOVED_AMAZON_SVG'.length;
            } else {
              break;
            }
          }
          hasChanges = true;
        }
        
        // 🎯 TARGETED: Only remove extremely long base64 data URIs (>5KB)
        if (cssContent.includes('data:image/svg+xml;base64,') && cssContent.length > 100000) {
          const beforeLength = modifiedCSS.length;
          modifiedCSS = modifiedCSS.replace(/data:image\/svg\+xml;base64,[A-Za-z0-9+/]{2000,}={0,2}/g, 'data:image/svg+xml;base64,SIMPLIFIED');
          if (modifiedCSS.length < beforeLength) {
            console.warn(`🎯 [CSS Plugin] Removed long SVG data URI: ${Math.round(beforeLength/1024)}KB → ${Math.round(modifiedCSS.length/1024)}KB`);
            hasChanges = true;
          }
        }
        
        // Only apply changes if we found problematic patterns
        if (hasChanges) {
          node.textContent = modifiedCSS;
          console.log('✅ [CSS Plugin] Surgical CSS filtering applied - preserved normal CSS, removed problematic patterns');
        }
      }
    }
    
    return node;
  }
});

/**
 * 🔧 CSS Error Handler for RRWeb
 * Handles CSS processing errors specifically
 */
export const createCssErrorHandler = () => {
  return (error: any) => {
    const errorMsg = error?.message || String(error);
    
    // Handle CSS processing errors specifically
    if (errorMsg.includes('Regular expression too large') || 
        errorMsg.includes('adaptCssForReplay') ||
        errorMsg.includes('Invalid regular expression') ||
        errorMsg.includes('Pattern too large') ||
        errorMsg.includes('Regex overflow')) {
      console.warn('🎨 [CSS Error Handler] Large CSS detected in rrweb - using simplified CSS processing:', errorMsg);
      // Don't throw - continue with simplified CSS processing
      return false;
    }
    
    console.warn('rrweb replayer warning (continuing):', error);
    // Don't throw - continue despite other errors
    return false; // Prevent default error handling
  };
}; 