import { Clock, Users } from 'lucide-react';
import { Button } from './ui/button';

interface RecentProjectsProps {
  isDarkMode?: boolean;
}

export function RecentProjects({ isDarkMode }: RecentProjectsProps) {
  const projects = [
    {
      name: "E-Commerce Platform",
      description: "React-based shopping application",
      lastUpdate: "2 hours ago",
      status: "Active",
      contributors: 5
    },
    {
      name: "Payment Gateway API",
      description: "Node.js microservice for payments",
      lastUpdate: "1 day ago", 
      status: "In Review",
      contributors: 3
    },
    {
      name: "Analytics Dashboard",
      description: "Real-time metrics visualization",
      lastUpdate: "3 days ago",
      status: "Deployed",
      contributors: 4
    },
    {
      name: "Mobile App Backend",
      description: "REST API for mobile application",
      lastUpdate: "1 week ago",
      status: "Testing",
      contributors: 6
    }
  ];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Active': return 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400 border-green-200 dark:border-green-800';
      case 'In Review': return 'bg-yellow-50 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 border-yellow-200 dark:border-yellow-800';
      case 'Deployed': return 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-800';
      case 'Testing': return 'bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 border-purple-200 dark:border-purple-800';
      default: return 'bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700';
    }
  };

  return (
    <div className="px-6 py-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-foreground">Recent Projects</h2>
            <p className="text-muted-foreground mt-1">Your recently active development projects</p>
          </div>
          <div className="flex items-center space-x-2">
            <Button variant="outline" size="sm">
              View All
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {projects.map((project, index) => (
            <div 
              key={index}
              className="bg-card border border-border rounded-lg p-4 hover:shadow-sm hover:border-accent-foreground/20 transition-all duration-200 cursor-pointer"
            >
              <div className="space-y-3">
                <div>
                  <h4 className="text-sm text-card-foreground font-medium mb-1">
                    {project.name}
                  </h4>
                  <p className="text-sm text-muted-foreground">
                    {project.description}
                  </p>
                </div>
                
                <div className="flex items-center justify-between">
                  <span 
                    className={`px-2 py-1 rounded-md border text-xs ${getStatusColor(project.status)}`}
                  >
                    {project.status}
                  </span>
                  <div className="flex items-center space-x-1 text-muted-foreground">
                    <Users className="w-3 h-3" />
                    <span className="text-xs">{project.contributors}</span>
                  </div>
                </div>
                
                <div className="flex items-center text-muted-foreground">
                  <Clock className="w-3 h-3 mr-1" />
                  <span className="text-xs">{project.lastUpdate}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}