import { TrendingUp, TrendingDown, Activity, Users, Code, Zap } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Progress } from './ui/progress';
import { Button } from './ui/button';

interface AnalyticsProps {
  isDarkMode?: boolean;
}

export function Analytics({ isDarkMode }: AnalyticsProps) {
  // First row - Whole numbers
  const metrics = [
    {
      title: "Active Repositories",
      value: "12",
      icon: Code,
      color: "#351A55",
      bgColor: "#351A5520"
    },
    {
      title: "Code Reviews Pending",
      value: "8",
      icon: Users,
      color: "#3498B3",
      bgColor: "#3498B320"
    },
    {
      title: "Deployments This Week",
      value: "15",
      icon: Activity,
      color: "#355493",
      bgColor: "#35549320"
    },
    {
      title: "Open Pull Requests",
      value: "6",
      icon: TrendingUp,
      color: "#BE266A",
      bgColor: "#BE266A20"
    }
  ];

  // Second row - Percentages
  const insights = [
    {
      title: "Development Velocity",
      value: "87%",
      icon: Zap,
      color: "#351A55",
      bgColor: "#351A5520"
    },
    {
      title: "Code Quality Health",
      value: "92%",
      icon: Code,
      color: "#3498B3",
      bgColor: "#3498B320"
    },
    {
      title: "Sprint Progress",
      value: "76%",
      icon: Activity,
      color: "#355493",
      bgColor: "#35549320"
    },
    {
      title: "Team Collaboration",
      value: "84%",
      icon: Users,
      color: "#BE266A",
      bgColor: "#BE266A20"
    }
  ];

  return (
    <div className="px-6 py-8 border-t-0">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-foreground">Analytics & Insights</h2>
            <p className="text-sm text-muted-foreground mt-1">Real-time metrics and performance indicators</p>
          </div>
          <div className="flex items-center space-x-2">
            <Button variant="outline" size="sm">
              Customize
            </Button>
          </div>
        </div>

        {/* Analytics Cards - 4x2 Layout */}
        <div className="grid grid-cols-4 gap-4">
          {/* First Row - Whole Numbers */}
          {metrics.map((metric, index) => {
            const Icon = metric.icon;
            return (
              <div 
                key={`metric-${index}`} 
                className="bg-card border border-border rounded-lg p-4 transition-all duration-200 group h-[70px] hover:shadow-md"
              >
                <div className="flex items-center space-x-4 h-full">
                  <div 
                    className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-all duration-200 dark:brightness-150 dark:saturate-125"
                    style={{ backgroundColor: `${metric.color}40` }}
                  >
                    <Icon 
                      className="w-4 h-4 dark:brightness-300 dark:saturate-200" 
                      style={{ color: metric.color }} 
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm text-card-foreground font-medium truncate">{metric.title}</h4>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-xl font-bold text-card-foreground">{metric.value}</p>
                  </div>
                </div>
              </div>
            );
          })}
          
          {/* Second Row - Percentages */}
          {insights.map((insight, index) => {
            const Icon = insight.icon;
            return (
              <div 
                key={`insight-${index}`} 
                className="bg-card border border-border rounded-lg p-4 transition-all duration-200 group h-[70px] hover:shadow-md"
              >
                <div className="flex items-center space-x-4 h-full">
                  <div 
                    className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-all duration-200 dark:brightness-150 dark:saturate-125"
                    style={{ backgroundColor: `${insight.color}40` }}
                  >
                    <Icon 
                      className="w-4 h-4 dark:brightness-300 dark:saturate-200" 
                      style={{ color: insight.color }} 
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-card-foreground font-medium truncate">{insight.title}</p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-xl font-bold text-card-foreground">{insight.value}</p>
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