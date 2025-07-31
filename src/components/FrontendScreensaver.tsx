import React from 'react';

interface FrontendScreensaverProps {
  /** Whether to show the screensaver (true) or hide it (false) */
  isVisible: boolean;
  /** Custom logo URL - defaults to /rebrowse.png */
  logoUrl?: string;
  /** Custom gradient colors */
  gradientFrom?: string;
  gradientTo?: string;
}

export const FrontendScreensaver: React.FC<FrontendScreensaverProps> = ({
  isVisible,
  logoUrl = "/rebrowse.png",
  gradientFrom = "#667eea",
  gradientTo = "#764ba2"
}) => {
  if (!isVisible) return null;

  return (
    <>
      {/* 🎬 FRONTEND SCREENSAVER: CSS Animations */}
      <style dangerouslySetInnerHTML={{
        __html: `
          @keyframes bounce {
            0% { 
              left: 5%; 
              top: 5%; 
              transform: rotate(0deg) scale(1); 
            }
            12.5% { 
              left: calc(50% - 50px); 
              top: 5%; 
              transform: rotate(45deg) scale(1.1); 
            }
            25% { 
              left: calc(95% - 100px); 
              top: 5%; 
              transform: rotate(90deg) scale(1); 
            }
            37.5% { 
              left: calc(95% - 100px); 
              top: calc(50% - 50px); 
              transform: rotate(135deg) scale(0.9); 
            }
            50% { 
              left: calc(95% - 100px); 
              top: calc(95% - 100px); 
              transform: rotate(180deg) scale(1); 
            }
            62.5% { 
              left: calc(50% - 50px); 
              top: calc(95% - 100px); 
              transform: rotate(225deg) scale(1.1); 
            }
            75% { 
              left: 5%; 
              top: calc(95% - 100px); 
              transform: rotate(270deg) scale(1); 
            }
            87.5% { 
              left: 5%; 
              top: calc(50% - 50px); 
              transform: rotate(315deg) scale(0.9); 
            }
            100% { 
              left: 5%; 
              top: 5%; 
              transform: rotate(360deg) scale(1); 
            }
          }
          
          @keyframes colorShift {
            0%, 100% { 
              filter: drop-shadow(0 6px 12px rgba(0,0,0,0.3)) hue-rotate(0deg);
              box-shadow: 0 0 20px rgba(102,126,234,0.4);
            }
            25% { 
              filter: drop-shadow(0 6px 12px rgba(102,126,234,0.4)) hue-rotate(90deg);
              box-shadow: 0 0 25px rgba(118,75,162,0.5);
            }
            50% { 
              filter: drop-shadow(0 6px 12px rgba(118,75,162,0.4)) hue-rotate(180deg);
              box-shadow: 0 0 30px rgba(168,85,247,0.6);
            }
            75% { 
              filter: drop-shadow(0 6px 12px rgba(168,85,247,0.4)) hue-rotate(270deg);
              box-shadow: 0 0 25px rgba(102,126,234,0.5);
            }
          }
          
          @keyframes sparkle {
            0%, 100% { opacity: 0; transform: scale(0); }
            50% { opacity: 1; transform: scale(1); }
          }
          
          @keyframes pulseGradient {
            0%, 100% { background: linear-gradient(135deg, ${gradientFrom} 0%, ${gradientTo} 100%); }
            50% { background: linear-gradient(135deg, ${gradientTo} 0%, ${gradientFrom} 100%); }
          }
        `
      }} />
      
      {/* 🎬 SCREENSAVER CONTAINER */}
      <div className="frontend-screensaver" style={{
        width: '100%',
        height: '100%',
        background: `linear-gradient(135deg, ${gradientFrom} 0%, ${gradientTo} 100%)`,
        position: 'absolute',
        top: 0,
        left: 0,
        overflow: 'hidden',
        borderRadius: '8px',
        border: '1px solid #e5e7eb',
        animation: 'pulseGradient 6s ease-in-out infinite',
        zIndex: 1
      }}>
        {/* 🎯 BOUNCING LOGO */}
        <div className="bouncing-logo" style={{
          position: 'absolute',
          width: '100px',
          height: '100px',
          borderRadius: '12px',
          animation: 'bounce 10s ease-in-out infinite, colorShift 3s ease-in-out infinite',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <img 
            src={logoUrl} 
            alt="Rebrowse Logo"
            style={{
              width: '100%', 
              height: '100%',
              borderRadius: '12px',
              objectFit: 'cover'
            }}
          />
        </div>
        
        {/* ✨ SPARKLE EFFECTS */}
        <div className="sparkles" style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none'
        }}>
          {[...Array(20)].map((_, i) => (
            <div
              key={i}
              className="sparkle"
              style={{
                position: 'absolute',
                top: `${Math.random() * 100}%`,
                left: `${Math.random() * 100}%`,
                width: '4px',
                height: '4px',
                background: 'white',
                borderRadius: '50%',
                animation: `sparkle ${2 + Math.random() * 3}s linear infinite`,
                animationDelay: `${Math.random() * 2}s`
              }}
            />
          ))}
        </div>
        
        {/* 🎪 LOADING TEXT */}
        <div style={{
          position: 'absolute',
          bottom: '20%',
          left: '50%',
          transform: 'translateX(-50%)',
          color: 'white',
          textAlign: 'center',
          fontSize: '18px',
          fontWeight: '600',
          textShadow: '0 2px 4px rgba(0,0,0,0.3)',
          animation: 'sparkle 2s ease-in-out infinite'
        }}>
          🎬 Preparing Visual Stream...
        </div>
      </div>
    </>
  );
};

export default FrontendScreensaver; 