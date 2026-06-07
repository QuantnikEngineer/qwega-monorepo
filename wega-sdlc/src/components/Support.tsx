import { ArrowLeft, MessageSquare, Mail, Phone, Search, Clock, CheckCircle, AlertCircle } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Input } from './ui/input';
import { Badge } from './ui/badge';

interface SupportProps {
  onBack: () => void;
  isDarkMode: boolean;
}

export function Support({ onBack, isDarkMode }: SupportProps) {
  const supportChannels = [
    {
      title: 'Live Chat Support',
      description: 'Get instant help from our support team during business hours.',
      icon: MessageSquare,
      availability: 'Mon-Fri, 9AM-6PM EST',
      responseTime: 'Instant',
      color: '#3498B3',
    },
    {
      title: 'Email Support',
      description: 'Send us detailed questions and receive comprehensive responses.',
      icon: Mail,
      availability: '24/7',
      responseTime: '< 4 hours',
      color: '#355493',
    },
    {
      title: 'Phone Support',
      description: 'Speak directly with our technical experts for urgent issues.',
      icon: Phone,
      availability: 'Mon-Fri, 8AM-8PM EST',
      responseTime: 'Immediate',
      color: '#746FA7',
    },
  ];

  const commonIssues = [
    {
      title: 'How do I configure my first AI agent?',
      category: 'Getting Started',
      status: 'Resolved',
      views: '1.2K',
    },
    {
      title: 'Integration with existing CI/CD pipelines',
      category: 'Integration',
      status: 'Resolved',
      views: '856',
    },
    {
      title: 'Setting up SSO authentication',
      category: 'Security',
      status: 'Resolved',
      views: '743',
    },
    {
      title: 'Understanding AI agent orchestration',
      category: 'Advanced',
      status: 'Resolved',
      views: '621',
    },
  ];

  const systemStatus = [
    { service: 'WEGA Platform', status: 'Operational', color: 'green' },
    { service: 'AI Agent Services', status: 'Operational', color: 'green' },
    { service: 'API Gateway', status: 'Operational', color: 'green' },
    { service: 'Authentication', status: 'Operational', color: 'green' },
  ];

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Back Button */}
        <Button
          variant="ghost"
          onClick={onBack}
          className="mb-6 text-foreground hover:text-[#3498B3]"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Home
        </Button>

        {/* Header */}
        <div className="mb-12">
          <h1 className="text-foreground mb-4">Support Center</h1>
          <p className="text-muted-foreground max-w-3xl">
            Get help when you need it. Our dedicated support team is here to ensure your success with the 
            WEGA platform. Access documentation, contact support, or check system status.
          </p>
        </div>

        {/* Search Bar */}
        <div className="mb-12">
          <Card className="p-6 bg-card border border-border">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-5 h-5" />
              <Input
                type="text"
                placeholder="Search for help articles, FAQs, or documentation..."
                className="pl-12 bg-input-background text-foreground border-border h-12"
              />
            </div>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-12">
          {/* Support Channels */}
          <div className="lg:col-span-2">
            <h2 className="text-foreground mb-6">Contact Support</h2>
            <div className="space-y-4">
              {supportChannels.map((channel, index) => (
                <Card
                  key={index}
                  className="p-6 bg-card border border-border hover:border-[#3498B3] transition-all"
                >
                  <div className="flex items-start space-x-4">
                    <div
                      className="p-3 rounded-lg"
                      style={{ backgroundColor: `${channel.color}20` }}
                    >
                      <channel.icon className="w-6 h-6" style={{ color: channel.color }} />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-foreground mb-2">{channel.title}</h3>
                      <p className="text-muted-foreground text-sm mb-4">{channel.description}</p>
                      <div className="flex items-center space-x-4 text-xs text-muted-foreground mb-4">
                        <div className="flex items-center">
                          <Clock className="w-4 h-4 mr-1" />
                          {channel.availability}
                        </div>
                        <div>Response: {channel.responseTime}</div>
                      </div>
                      <Button variant="outline" size="sm" className="hover:bg-[#3498B3] hover:text-white hover:border-[#3498B3]">
                        Contact via {channel.title.split(' ')[0]}
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>

          {/* System Status */}
          <div>
            <h2 className="text-foreground mb-6">System Status</h2>
            <Card className="p-6 bg-card border border-border">
              <div className="flex items-center space-x-2 mb-4">
                <CheckCircle className="w-5 h-5 text-green-500" />
                <span className="text-foreground">All Systems Operational</span>
              </div>
              <div className="space-y-3">
                {systemStatus.map((item, index) => (
                  <div key={index} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                    <span className="text-sm text-muted-foreground">{item.service}</span>
                    <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/30">
                      {item.status}
                    </Badge>
                  </div>
                ))}
              </div>
              <Button variant="ghost" className="w-full mt-4 text-[#3498B3] hover:bg-[#3498B3]/10">
                View Status Page
              </Button>
            </Card>
          </div>
        </div>

        {/* Common Issues */}
        <div>
          <h2 className="text-foreground mb-6">Common Questions</h2>
          <Card className="bg-card border border-border">
            <div className="divide-y divide-border">
              {commonIssues.map((issue, index) => (
                <div
                  key={index}
                  className="p-4 hover:bg-muted/50 cursor-pointer transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h3 className="text-foreground mb-2">{issue.title}</h3>
                      <div className="flex items-center space-x-3 text-xs text-muted-foreground">
                        <Badge variant="outline" className="text-xs">
                          {issue.category}
                        </Badge>
                        <span>{issue.views} views</span>
                      </div>
                    </div>
                    <CheckCircle className="w-5 h-5 text-green-500 ml-4" />
                  </div>
                </div>
              ))}
            </div>
            <div className="p-4 border-t border-border">
              <Button variant="ghost" className="w-full text-[#3498B3] hover:bg-[#3498B3]/10">
                Browse All Articles
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}