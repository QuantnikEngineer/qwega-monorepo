import { Home } from 'lucide-react';
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from './ui/breadcrumb';

interface FinalBreadcrumbProps {
  pipelineName: string;
  onBackToDashboard: () => void;
  onBackToPipelines: () => void;
}

export function FinalBreadcrumb({ pipelineName, onBackToDashboard, onBackToPipelines }: FinalBreadcrumbProps) {
  return (
    <div className="bg-card border-b border-border px-6 py-4">
      <div className="max-w-7xl mx-auto">
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink 
                href="#" 
                onClick={(e) => {
                  e.preventDefault();
                  onBackToDashboard();
                }}
                className="flex items-center space-x-1 cursor-pointer"
              >
                <Home className="w-4 h-4 dark:brightness-200" />
                <span>Dashboard</span>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbLink 
                href="#" 
                onClick={(e) => {
                  e.preventDefault();
                  onBackToPipelines();
                }}
                className="cursor-pointer"
              >
                Pipelines
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbPage>Configure</BreadcrumbPage>
          </BreadcrumbList>
        </Breadcrumb>
        
        {/* Page Title */}
        <div className="mt-4">
          <h1 className="text-2xl font-semibold text-foreground">{pipelineName}</h1>
        </div>
      </div>
    </div>
  );
}