import React from 'react';
import { Box } from '@mui/material';

interface ResizerProps {
  onResize: (delta: number) => void;
  isVertical?: boolean;
}

const Resizer: React.FC<ResizerProps> = ({ onResize, isVertical = true }) => {
  const [isDragging, setIsDragging] = React.useState(false);
  const startPosRef = React.useRef<number>(0);

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    startPosRef.current = isVertical ? e.clientX : e.clientY;
    document.body.style.cursor = isVertical ? 'col-resize' : 'row-resize';
    document.body.style.userSelect = 'none';
  };

  React.useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      
      const currentPos = isVertical ? e.clientX : e.clientY;
      const delta = currentPos - startPosRef.current;
      
      if (Math.abs(delta) > 0) {
        onResize(delta);
        startPosRef.current = currentPos;
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, onResize, isVertical]);

  return (
    <Box
      onMouseDown={handleMouseDown}
      sx={{
        width: isVertical ? '6px' : '100%',
        height: isVertical ? '100%' : '6px',
        backgroundColor: 'transparent',
        cursor: isVertical ? 'col-resize' : 'row-resize',
        position: 'relative',
        zIndex: 10,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        // Default visible light grey partition line
        '&::before': {
          content: '""',
          position: 'absolute',
          left: isVertical ? '50%' : 0,
          top: isVertical ? 0 : '50%',
          transform: isVertical ? 'translateX(-50%)' : 'translateY(-50%)',
          width: isVertical ? '1px' : '100%',
          height: isVertical ? '100%' : '1px',
          backgroundColor: '#e0e0e0', // Light grey color
          transition: 'background-color 0.15s ease',
        },
        // Hover effect - slightly darker and wider
        '&:hover': {
          backgroundColor: 'rgba(25, 118, 210, 0.05)',
          '&::before': {
            backgroundColor: '#bdbdbd', // Darker grey on hover
            width: isVertical ? '2px' : '100%',
            height: isVertical ? '100%' : '2px',
          },
          '& > *': {
            // Icon hover effect
            backgroundColor: '#bdbdbd',
            opacity: 1,
          },
        },
        // Active/dragging state
        ...(isDragging && {
          backgroundColor: 'rgba(25, 118, 210, 0.1)',
          '&::before': {
            backgroundColor: 'rgba(25, 118, 210, 0.6)', // Blue when dragging
            width: isVertical ? '2px' : '100%',
            height: isVertical ? '100%' : '2px',
          },
        }),
      }}
    >
      {/* Resizer Icon - Oval button with dots */}
      <Box
        sx={{
          position: 'absolute',
          left: isVertical ? '50%' : '50%',
          top: isVertical ? '50%' : '50%',
          transform: 'translate(-50%, -50%)',
          width: isVertical ? '18px' : '32px',
          height: isVertical ? '28px' : '18px',
          backgroundColor: '#e0e0e0', // Light grey oval
          borderRadius: isVertical ? '9px' : '9px',
          display: 'flex',
          flexDirection: isVertical ? 'row' : 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '2px',
          padding: isVertical ? '3px 1px' : '1px 3px',
          transition: 'background-color 0.15s ease, opacity 0.15s ease',
          opacity: 0.9,
          zIndex: 11,
          pointerEvents: 'none', // Allow clicks to pass through to parent
          // Hover effect (inherited from parent)
          ...(isDragging && {
            backgroundColor: 'rgba(25, 118, 210, 0.25)',
            opacity: 1,
          }),
        }}
      >
        {/* Dots grid - 2 columns, 3 rows for vertical resizer */}
        {isVertical ? (
          // Vertical layout: 2 columns, 3 rows
          <>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
              <Box
                sx={{
                  width: '2.5px',
                  height: '2.5px',
                  borderRadius: '50%',
                  backgroundColor: '#757575', // Dark grey dots
                }}
              />
              <Box
                sx={{
                  width: '2.5px',
                  height: '2.5px',
                  borderRadius: '50%',
                  backgroundColor: '#757575',
                }}
              />
              <Box
                sx={{
                  width: '2.5px',
                  height: '2.5px',
                  borderRadius: '50%',
                  backgroundColor: '#757575',
                }}
              />
            </Box>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
              <Box
                sx={{
                  width: '2.5px',
                  height: '2.5px',
                  borderRadius: '50%',
                  backgroundColor: '#757575',
                }}
              />
              <Box
                sx={{
                  width: '2.5px',
                  height: '2.5px',
                  borderRadius: '50%',
                  backgroundColor: '#757575',
                }}
              />
              <Box
                sx={{
                  width: '2.5px',
                  height: '2.5px',
                  borderRadius: '50%',
                  backgroundColor: '#757575',
                }}
              />
            </Box>
          </>
        ) : (
          // Horizontal layout: 3 columns, 2 rows
          <>
            <Box sx={{ display: 'flex', gap: '2px' }}>
              <Box
                sx={{
                  width: '2.5px',
                  height: '2.5px',
                  borderRadius: '50%',
                  backgroundColor: '#757575',
                }}
              />
              <Box
                sx={{
                  width: '2.5px',
                  height: '2.5px',
                  borderRadius: '50%',
                  backgroundColor: '#757575',
                }}
              />
              <Box
                sx={{
                  width: '2.5px',
                  height: '2.5px',
                  borderRadius: '50%',
                  backgroundColor: '#757575',
                }}
              />
            </Box>
            <Box sx={{ display: 'flex', gap: '2px' }}>
              <Box
                sx={{
                  width: '2.5px',
                  height: '2.5px',
                  borderRadius: '50%',
                  backgroundColor: '#757575',
                }}
              />
              <Box
                sx={{
                  width: '2.5px',
                  height: '2.5px',
                  borderRadius: '50%',
                  backgroundColor: '#757575',
                }}
              />
              <Box
                sx={{
                  width: '2.5px',
                  height: '2.5px',
                  borderRadius: '50%',
                  backgroundColor: '#757575',
                }}
              />
            </Box>
          </>
        )}
      </Box>
    </Box>
  );
};

export default Resizer;
