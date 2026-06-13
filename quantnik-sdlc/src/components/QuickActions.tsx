import { Plus, GitBranch, Server, Bug, Rocket, FileText, Clock } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';

interface QuickActionsProps {
  isDarkMode?: boolean;
}

export function QuickActions({ isDarkMode }: QuickActionsProps) {
  const actions = [
    {
      title: "New Project",
      description: "Create a new development project",
      icon: Plus
    },
    {
      title: "Deploy Pipeline",
      description: "Deploy code to environment",
      icon: Rocket
    },
    {
      title: "Create Branch",
      description: "Create new git branch",
      icon: GitBranch
    },
    {
      title: "Provision Infra",
      description: "Spin up new infrastructure",
      icon: Server
    },
    {
      title: "Report Issue",
      description: "Create bug report or ticket",
      icon: Bug
    },
    {
      title: "Documentation",
      description: "Access project documentation",
      icon: FileText
    },
    {
      title: "View Logs",
      description: "Check application logs",
      icon: Clock
    }
  ];

  return (
    <div className="px-6 py-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-foreground">Quick Actions</h2>
            <p className="text-muted-foreground mt-1">Frequently used actions and shortcuts</p>
          </div>
          <div className="flex items-center space-x-2">
            <Button variant="outline" size="sm">
              Customize
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
          {actions.map((action, index) => {
            const Icon = action.icon;
            return (
              <div 
                key={index} 
                className="bg-card border border-border rounded-lg hover:shadow-md hover:border-accent-foreground/20 transition-all duration-200 cursor-pointer group h-[120px]"
              >
                <div className="p-4 h-full flex flex-col items-center justify-center text-center space-y-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 bg-[#5379E8]/20 dark:bg-[#5379E8]/40 dark:brightness-150 dark:saturate-125">
                    <Icon className="w-4 h-4 text-[#5379E8] dark:brightness-300 dark:saturate-200" />
                  </div>
                  <div className="flex-1 flex flex-col justify-center">
                    <p className="text-sm text-card-foreground leading-tight">{action.title}</p>
                    <p className="text-xs text-muted-foreground mt-1 leading-tight">{action.description}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}