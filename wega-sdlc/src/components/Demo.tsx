import { ArrowLeft, Play, Calendar, Users, Clock } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';

interface DemoProps {
  onBack: () => void;
  isDarkMode: boolean;
}

export function Demo({ onBack, isDarkMode }: DemoProps) {
  const demoOptions = [
    {
      title: 'Live Platform Demo',
      description: 'Interactive walkthrough of WEGA\'s AI-powered engineering capabilities with a product expert.',
      icon: Play,
      duration: '45 minutes',
      participants: 'Up to 10',
      color: '#3498B3',
    },
    {
      title: 'Custom Use Case Demo',
      description: 'Tailored demonstration focused on your specific engineering challenges and requirements.',
      icon: Users,
      duration: '60 minutes',
      participants: 'Custom',
      color: '#355493',
    },
    {
      title: 'Technical Deep Dive',
      description: 'In-depth technical session covering architecture, integrations, and advanced features.',
      icon: Clock,
      duration: '90 minutes',
      participants: 'Technical team',
      color: '#746FA7',
    },
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
          <h1 className="text-foreground mb-4">Request a Demo</h1>
          <p className="text-muted-foreground max-w-3xl">
            Experience the power of WEGA's AI-driven software engineering platform. Schedule a personalized 
            demonstration to see how our platform can transform your development workflow and accelerate 
            your engineering outcomes.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Demo Options */}
          <div>
            <h2 className="text-foreground mb-6">Choose Your Demo Type</h2>
            <div className="space-y-4">
              {demoOptions.map((option, index) => (
                <Card
                  key={index}
                  className="p-6 bg-card border border-border hover:border-[#3498B3] transition-all cursor-pointer"
                >
                  <div className="flex items-start space-x-4">
                    <div
                      className="p-3 rounded-lg"
                      style={{ backgroundColor: `${option.color}20` }}
                    >
                      <option.icon className="w-6 h-6" style={{ color: option.color }} />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-foreground mb-2">{option.title}</h3>
                      <p className="text-muted-foreground text-sm mb-4">{option.description}</p>
                      <div className="flex items-center space-x-4 text-xs text-muted-foreground">
                        <div className="flex items-center">
                          <Clock className="w-4 h-4 mr-1" />
                          {option.duration}
                        </div>
                        <div className="flex items-center">
                          <Users className="w-4 h-4 mr-1" />
                          {option.participants}
                        </div>
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>

          {/* Request Form */}
          <div>
            <Card className="p-6 bg-card border border-border">
              <h2 className="text-foreground mb-6">Schedule Your Demo</h2>
              <form className="space-y-4">
                <div>
                  <Label htmlFor="name" className="text-foreground">Full Name *</Label>
                  <Input
                    id="name"
                    type="text"
                    placeholder="John Doe"
                    className="bg-input-background text-foreground border-border"
                  />
                </div>
                <div>
                  <Label htmlFor="email" className="text-foreground">Work Email *</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="john.doe@company.com"
                    className="bg-input-background text-foreground border-border"
                  />
                </div>
                <div>
                  <Label htmlFor="company" className="text-foreground">Company *</Label>
                  <Input
                    id="company"
                    type="text"
                    placeholder="Your Company Name"
                    className="bg-input-background text-foreground border-border"
                  />
                </div>
                <div>
                  <Label htmlFor="role" className="text-foreground">Job Title</Label>
                  <Input
                    id="role"
                    type="text"
                    placeholder="e.g., Engineering Manager"
                    className="bg-input-background text-foreground border-border"
                  />
                </div>
                <div>
                  <Label htmlFor="team-size" className="text-foreground">Team Size</Label>
                  <Input
                    id="team-size"
                    type="text"
                    placeholder="e.g., 50-100 engineers"
                    className="bg-input-background text-foreground border-border"
                  />
                </div>
                <div>
                  <Label htmlFor="use-case" className="text-foreground">What are you looking to solve?</Label>
                  <Textarea
                    id="use-case"
                    placeholder="Tell us about your engineering challenges and what you'd like to see in the demo..."
                    rows={4}
                    className="bg-input-background text-foreground border-border resize-none"
                  />
                </div>
                <div>
                  <Label htmlFor="preferred-date" className="text-foreground">Preferred Date/Time</Label>
                  <Input
                    id="preferred-date"
                    type="text"
                    placeholder="e.g., Next week, Tuesday afternoon"
                    className="bg-input-background text-foreground border-border"
                  />
                </div>
                <Button
                  type="submit"
                  className="w-full bg-[#351A55] text-white hover:bg-[#2a1444] border-[#351A55]"
                >
                  <Calendar className="w-4 h-4 mr-2" />
                  Request Demo
                </Button>
                <p className="text-xs text-muted-foreground text-center">
                  By submitting, you agree to our terms and privacy policy. A WEGA representative will contact you within 24 hours.
                </p>
              </form>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}