import { useState, useEffect } from 'react';

interface SDLCJourneyProps {
  onStageClick?: (stageName: string) => void;
}

const stages = [
  {
    name: 'Planning',
    icon: '📋',
    gradientFrom: '#3b82f6',
    gradientTo: '#06b6d4',
    borderColor: '#3b82f6',
    bgColor: 'rgba(59, 130, 246, 0.1)',
    description: 'Define scope and objectives',
  },
  {
    name: 'Analysis & Design',
    icon: '🎨',
    gradientFrom: '#a855f7',
    gradientTo: '#ec4899',
    borderColor: '#a855f7',
    bgColor: 'rgba(168, 85, 247, 0.1)',
    description: 'Architect the solution',
  },
  {
    name: 'Build',
    icon: '⚡',
    gradientFrom: '#f97316',
    gradientTo: '#eab308',
    borderColor: '#f97316',
    bgColor: 'rgba(249, 115, 22, 0.1)',
    description: 'Build the application',
  },
  {
    name: 'Testing',
    icon: '🔍',
    gradientFrom: '#22c55e',
    gradientTo: '#10b981',
    borderColor: '#22c55e',
    bgColor: 'rgba(34, 197, 94, 0.1)',
    description: 'Validate quality',
  },
  {
    name: 'Deployment',
    icon: '🚀',
    gradientFrom: '#6366f1',
    gradientTo: '#3b82f6',
    borderColor: '#6366f1',
    bgColor: 'rgba(99, 102, 241, 0.1)',
    description: 'Release to production',
  },
  {
    name: 'Reliability',
    icon: '📊',
    gradientFrom: '#ec4899',
    gradientTo: '#f43f5e',
    borderColor: '#ec4899',
    bgColor: 'rgba(236, 72, 153, 0.1)',
    description: 'Observability & monitoring',
  },
  {
    name: 'Security',
    icon: '🔒',
    gradientFrom: '#14b8a6',
    gradientTo: '#06b6d4',
    borderColor: '#14b8a6',
    bgColor: 'rgba(20, 184, 166, 0.1)',
    description: 'Security & vulnerability',
  },
  {
    name: 'Governance',
    icon: '🛡️',
    gradientFrom: '#f43f5e',
    gradientTo: '#ef4444',
    borderColor: '#f43f5e',
    bgColor: 'rgba(244, 63, 94, 0.1)',
    description: 'Monitor and maintain',
  },
];

export function SDLCJourney({ onStageClick }: SDLCJourneyProps) {
  const [activeStage, setActiveStage] = useState(0);
  const [completedStages, setCompletedStages] = useState<number[]>([]);

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStage((prev) => {
        const next = (prev + 1) % stages.length;
        if (next === 0) {
          setCompletedStages([]);
        } else {
          setCompletedStages((completed) => [...completed, prev]);
        }
        return next;
      });
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  const progressPercent = (activeStage / (stages.length - 1)) * 100;

  return (
    <div
      style={{
        padding: '24px 16px',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Background gradient effects */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'linear-gradient(to bottom, transparent, rgba(59,130,246,0.05), transparent)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'radial-gradient(ellipse at center, rgba(59,130,246,0.1), transparent 70%)',
        }}
      />

      <div
        style={{
          maxWidth: '1100px',
          margin: '0 auto',
          position: 'relative',
          zIndex: 10,
        }}
      >
        {/* Header */}
        {/* <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <h2
            style={{
              fontSize: '1.5rem',
              fontWeight: 700,
              color: '#fff',
              marginBottom: '8px',
              lineHeight: 1.2,
            }}
          >
            Your SDLC Journey with{' '}
            <span
              style={{
                background: 'linear-gradient(to right, #60a5fa, #c084fc)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}
            >
              QUANTNIK AI
            </span>
          </h2>
          <p
            style={{
              color: '#9ca3af',
              fontSize: '0.8rem',
              maxWidth: '36rem',
              margin: '0 auto',
              lineHeight: 1.4,
            }}
          >
            Experience seamless software development lifecycle automation powered
            by intelligent AI agents
          </p>
        </div> */}

        {/* Desktop Journey Path */}
        <div style={{ position: 'relative' }}>
          {/* Connection Line */}
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: 0,
              right: 0,
              height: '3px',
              transform: 'translateY(-50%)',
              zIndex: 0,
            }}
          >
            <div
              style={{
                position: 'relative',
                width: '100%',
                height: '100%',
                background:
                  'linear-gradient(to right, #1f2937, #374151, #1f2937)',
                borderRadius: '9999px',
                overflow: 'hidden',
              }}
            >
              {/* Animated progress line */}
              <div
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  height: '100%',
                  background:
                    'linear-gradient(to right, #3b82f6, #a855f7, #ec4899)',
                  borderRadius: '9999px',
                  width: `${progressPercent}%`,
                  boxShadow: '0 0 12px rgba(59, 130, 246, 0.5)',
                  transition: 'width 1s ease-out',
                }}
              />
              {/* Flowing dot */}
              <div
                style={{
                  position: 'absolute',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  left: `${progressPercent}%`,
                  width: '8px',
                  height: '8px',
                  background: '#fff',
                  borderRadius: '9999px',
                  boxShadow:
                    '0 0 10px rgba(255,255,255,0.8), 0 0 20px rgba(59,130,246,0.6)',
                  transition: 'left 1s ease-out',
                  animation: 'sdlcPulse 2s ease-in-out infinite',
                }}
              />
            </div>
          </div>

          {/* Stage Cards */}
          <div
            style={{
              position: 'relative',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              paddingTop: '20px',
              zIndex: 1,
            }}
          >
            {stages.map((stage, index) => {
              const isActive = index === activeStage;
              const isCompleted = completedStages.includes(index);

              return (
                <div
                  key={stage.name}
                  style={{
                    position: 'relative',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    width: `${100 / stages.length}%`,
                  }}
                >
                  {/* Stage Circle */}
                  <div
                    onClick={() => onStageClick?.(stage.name)}
                    style={{
                      position: 'relative',
                      width: isActive ? '56px' : '46px',
                      height: isActive ? '56px' : '46px',
                      borderRadius: '9999px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: isActive ? '1.5rem' : '1.2rem',
                      cursor: 'pointer',
                      transition: 'all 0.5s ease',
                      transform: isActive
                        ? 'scale(1.15) translateY(-18px)'
                        : isCompleted
                        ? 'scale(1)'
                        : 'scale(0.9)',
                      opacity: isActive || isCompleted ? 1 : 0.5,
                      background: isActive
                        ? stage.bgColor
                        : 'rgba(31, 41, 55, 0.5)',
                      border: isActive
                        ? `3px solid ${stage.borderColor}`
                        : `2px solid ${isCompleted ? '#22c55e' : '#374151'}`,
                      boxShadow: isActive
                        ? '0 0 16px rgba(59,130,246,0.6), 0 0 30px rgba(147,51,234,0.3)'
                        : isCompleted
                        ? '0 0 10px rgba(34,197,94,0.4)'
                        : 'none',
                    }}
                  >
                    {isCompleted && !isActive ? (
                      <svg
                        width="28"
                        height="28"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#22c55e"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                        <polyline points="22 4 12 14.01 9 11.01" />
                      </svg>
                    ) : (
                      <span>{stage.icon}</span>
                    )}

                    {/* Pulsing ring for active */}
                    {isActive && (
                      <>
                        <div
                          style={{
                            position: 'absolute',
                            inset: 0,
                            borderRadius: '9999px',
                            border: `3px solid ${stage.borderColor}`,
                            animation:
                              'sdlcPing 1.5s cubic-bezier(0,0,0.2,1) infinite',
                          }}
                        />
                        <div
                          style={{
                            position: 'absolute',
                            inset: 0,
                            borderRadius: '9999px',
                            border: `2px solid ${stage.gradientTo}`,
                            animation: 'sdlcPulse 2s ease-in-out infinite',
                          }}
                        />
                      </>
                    )}
                  </div>

                  {/* Stage Info */}
                  <div
                    onClick={() => onStageClick?.(stage.name)}
                    style={{
                      marginTop: '16px',
                      textAlign: 'center',
                      cursor: 'pointer',
                      transition: 'all 0.5s ease',
                      transform: isActive
                        ? 'translateY(0)'
                        : 'translateY(8px)',
                      opacity: isActive ? 1 : 0.6,
                    }}
                  >
                    <h3
                      style={{
                        fontWeight: 700,
                        fontSize: '0.8rem',
                        marginBottom: '2px',
                        transition: 'color 0.5s ease',
                        ...(isActive
                          ? {
                              background: `linear-gradient(to right, ${stage.gradientFrom}, ${stage.gradientTo})`,
                              WebkitBackgroundClip: 'text',
                              WebkitTextFillColor: 'transparent',
                              backgroundClip: 'text',
                            }
                          : { color: '#9ca3af' }),
                      }}
                    >
                      {stage.name}
                    </h3>
                    <p
                      style={{
                        fontSize: '0.7rem',
                        color: isActive ? '#d1d5db' : '#6b7280',
                      }}
                    >
                      {stage.description}
                    </p>
                  </div>

                  {/* Orbiting particles for active stage */}
                  {isActive && (
                    <svg
                      style={{
                        position: 'absolute',
                        inset: 0,
                        width: '100%',
                        height: '100%',
                        pointerEvents: 'none',
                        top: '-30px',
                      }}
                    >
                      {Array.from({ length: 6 }).map((_, i) => {
                        const angle = (i * 360) / 6;
                        return (
                          <circle
                            key={`particle-${i}`}
                            cx="50%"
                            cy="50"
                            r="2"
                            fill={stage.gradientFrom}
                            opacity="0.8"
                          >
                            <animateTransform
                              attributeName="transform"
                              type="rotate"
                              from={`${angle} 50 50`}
                              to={`${angle + 360} 50 50`}
                              dur="3s"
                              repeatCount="indefinite"
                            />
                            <animateTransform
                              attributeName="transform"
                              type="translate"
                              values="0,0; 25,0; 0,0"
                              dur="3s"
                              repeatCount="indefinite"
                              additive="sum"
                            />
                          </circle>
                        );
                      })}
                    </svg>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Progress indicator */}
        <div style={{ marginTop: '20px', textAlign: 'center' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              background: 'rgba(31, 41, 55, 0.5)',
              borderRadius: '9999px',
              border: '1px solid #374151',
            }}
          >
            <div style={{ display: 'flex', gap: '5px' }}>
              {stages.map((_, index) => (
                <div
                  key={index}
                  style={{
                    height: '6px',
                    borderRadius: '9999px',
                    transition: 'all 0.5s ease',
                    ...(index === activeStage
                      ? {
                          width: '20px',
                          background:
                            'linear-gradient(to right, #3b82f6, #a855f7)',
                        }
                      : {
                          width: '6px',
                          background: '#4b5563',
                        }),
                  }}
                />
              ))}
            </div>
            <span
              style={{
                color: '#9ca3af',
                fontSize: '0.75rem',
                marginLeft: '6px',
              }}
            >
              {stages[activeStage].name}
            </span>
          </div>
        </div>
      </div>

      {/* Animated background particles */}
      <svg
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          opacity: 0.3,
        }}
        xmlns="http://www.w3.org/2000/svg"
      >
        {Array.from({ length: 12 }).map((_, i) => {
          const x = Math.random() * 100;
          const y = Math.random() * 100;
          const duration = 3 + Math.random() * 4;
          const delay = Math.random() * 3;
          return (
            <circle
              key={`bg-particle-${i}`}
              cx={`${x}%`}
              cy={`${y}%`}
              r="2"
              fill={i % 2 === 0 ? '#60a5fa' : '#a855f7'}
              opacity="0"
            >
              <animate
                attributeName="opacity"
                values="0;0.6;0"
                dur={`${duration}s`}
                begin={`${delay}s`}
                repeatCount="indefinite"
              />
              <animate
                attributeName="r"
                values="2;4;2"
                dur={`${duration}s`}
                begin={`${delay}s`}
                repeatCount="indefinite"
              />
            </circle>
          );
        })}
      </svg>
    </div>
  );
}
