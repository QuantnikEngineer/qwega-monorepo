import React, { useState, useCallback } from 'react';
import { GripVertical, RotateCcw, Settings, Move } from 'lucide-react';
import { QuickActions } from './QuickActions';
import { RecentProjects } from './RecentProjects';
import { Analytics } from './Analytics';
import { LauncherSection } from './LauncherSection';
import { Button } from './ui/button';

interface DashboardSection {
  id: string;
  title: string;
  component: React.ComponentType<any>;
  colorScheme: string;
}

interface DraggableSectionProps {
  section: DashboardSection;
  index: number;
  moveSection: (dragIndex: number, hoverIndex: number) => void;
  isRearrangeMode: boolean;
  onNavigateToCodeRepo?: () => void;
  onNavigateToPipelines?: () => void;
}

const DraggableSection: React.FC<DraggableSectionProps> = ({
  section,
  index,
  moveSection,
  isRearrangeMode,
  onNavigateToCodeRepo,
  onNavigateToPipelines
}) => {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragStart = (e: React.DragEvent) => {
    if (!isRearrangeMode) return;
    setIsDragging(true);
    e.dataTransfer.setData('text/plain', index.toString());
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragEnd = () => {
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    if (!isRearrangeMode) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e: React.DragEvent) => {
    if (!isRearrangeMode) return;
    e.preventDefault();
    const dragIndex = parseInt(e.dataTransfer.getData('text/plain'));
    const hoverIndex = index;

    if (dragIndex !== hoverIndex) {
      moveSection(dragIndex, hoverIndex);
    }
  };

  const Component = section.component;

  return (
    <div
      draggable={isRearrangeMode}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      className={`relative transition-all duration-200 ${section.colorScheme} ${
        isDragging ? 'opacity-50 scale-95' : 'opacity-100'
      } ${isRearrangeMode ? 'ring-2 ring-blue-200 dark:ring-blue-500 ring-offset-2 rounded-lg cursor-move' : ''}`}
    >
      {isRearrangeMode && (
        <div
          className="absolute top-4 right-4 z-10 p-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors pointer-events-none"
          title={`Drag to rearrange ${section.title}`}
        >
          <GripVertical className="w-4 h-4 text-gray-600 dark:text-gray-400" />
        </div>
      )}
      {section.id === 'launcher' ? (
        <Component 
          onNavigateToCodeRepo={onNavigateToCodeRepo}
          onNavigateToPipelines={onNavigateToPipelines}
        />
      ) : (
        <Component />
      )}
    </div>
  );
};

interface RearrangeableDashboardProps {
  onNavigateToCodeRepo?: () => void;
  onNavigateToPipelines?: () => void;
  isDarkMode?: boolean;
}

export function RearrangeableDashboard({ onNavigateToCodeRepo, onNavigateToPipelines, isDarkMode }: RearrangeableDashboardProps) {
  const defaultSections: DashboardSection[] = [
    { 
      id: 'quick-actions', 
      title: 'Quick Actions', 
      component: (props: any) => <QuickActions {...props} isDarkMode={isDarkMode} />,
      colorScheme: 'bg-gray-50/90 dark:bg-gray-800/60'
    },
    { 
      id: 'recent-projects', 
      title: 'Recent Projects', 
      component: (props: any) => <RecentProjects {...props} isDarkMode={isDarkMode} />,
      colorScheme: 'bg-gray-100/80 dark:bg-gray-700/70'
    },
    { 
      id: 'analytics', 
      title: 'Analytics', 
      component: (props: any) => <Analytics {...props} isDarkMode={isDarkMode} />,
      colorScheme: 'bg-gray-50/90 dark:bg-gray-800/60'
    },
    { 
      id: 'launcher', 
      title: 'Platform Launcher', 
      component: (props: any) => <LauncherSection {...props} isDarkMode={isDarkMode} onNavigateToCodeRepo={onNavigateToCodeRepo} onNavigateToPipelines={onNavigateToPipelines} />,
      colorScheme: 'bg-gray-100/80 dark:bg-gray-700/70'
    },
  ];

  const [sections, setSections] = useState<DashboardSection[]>(defaultSections);
  const [isRearrangeMode, setIsRearrangeMode] = useState(false);

  const moveSection = useCallback((dragIndex: number, hoverIndex: number) => {
    setSections((prevSections) => {
      const newSections = [...prevSections];
      const draggedSection = newSections[dragIndex];
      newSections.splice(dragIndex, 1);
      newSections.splice(hoverIndex, 0, draggedSection);
      return newSections;
    });
  }, []);

  const resetToDefault = () => {
    setSections(defaultSections);
    setIsRearrangeMode(false);
  };

  const toggleRearrangeMode = () => {
    setIsRearrangeMode(!isRearrangeMode);
  };

  const moveSectionUp = (index: number) => {
    if (index > 0) {
      moveSection(index, index - 1);
    }
  };

  const moveSectionDown = (index: number) => {
    if (index < sections.length - 1) {
      moveSection(index, index + 1);
    }
  };

  return (
    <div className="relative">
      {/* Rearrange Controls */}
      {isRearrangeMode && (
        <div className="sticky top-0 z-20 bg-blue-50 dark:bg-gray-800 border-b border-blue-200 dark:border-gray-700 px-6 py-4 mb-0">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-3 h-3 bg-blue-500 dark:bg-blue-400 rounded-full animate-pulse"></div>
              <div>
                <p className="text-sm font-medium text-blue-900 dark:text-blue-100">Rearrange Mode Active</p>
                <p className="text-xs text-blue-700 dark:text-blue-300">Drag sections or use the arrow buttons to reorder them</p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={resetToDefault}
                className="text-blue-700 dark:text-blue-300 border-blue-200 dark:border-gray-600 hover:bg-blue-100 dark:hover:bg-gray-700"
              >
                <RotateCcw className="w-4 h-4 mr-2" />
                Reset
              </Button>
              <Button
                size="sm"
                onClick={toggleRearrangeMode}
                className="bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600"
              >
                Done
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Dashboard Sections */}
      <div className="space-y-0">
        {sections.map((section, index) => (
          <div key={section.id} className="relative">
            <DraggableSection
              section={section}
              index={index}
              moveSection={moveSection}
              isRearrangeMode={isRearrangeMode}
              onNavigateToCodeRepo={onNavigateToCodeRepo}
              onNavigateToPipelines={onNavigateToPipelines}
            />
            
            {/* Additional controls for non-drag environments */}
            {isRearrangeMode && (
              <div className="absolute top-4 right-16 z-10 flex space-x-1">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => moveSectionUp(index)}
                  disabled={index === 0}
                  className="p-1 h-auto"
                  title="Move up"
                >
                  <svg className="w-3 h-3 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                  </svg>
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => moveSectionDown(index)}
                  disabled={index === sections.length - 1}
                  className="p-1 h-auto"
                  title="Move down"
                >
                  <svg className="w-3 h-3 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Floating Rearrange Button */}
      {!isRearrangeMode && (
        <Button
          variant="outline"
          size="lg"
          onClick={toggleRearrangeMode}
          className="fixed bottom-20 left-6 p-3 rounded-full shadow-lg hover:shadow-xl z-10 bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700"
          title="Rearrange dashboard sections"
        >
          <Move className="w-5 h-5" />
        </Button>
      )}
    </div>
  );
}