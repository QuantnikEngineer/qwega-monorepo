import { Avatar, AvatarImage, AvatarFallback } from "../components/ui/avatar";
import { Badge } from "../components/ui/badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../components/ui/card";
import { MapPin, Mail, Linkedin, Github, Code, Server, Brain, Wrench, Database, Cloud, Users, Globe, GitBranch, Briefcase } from "lucide-react";

export default function VibeProgrammer() {
  const imageUrl = "https://images.unsplash.com/photo-1762522927402-f390672558d8?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxidXNpbmVzcyUyMHByb2Zlc3Npb25hbCUyMGhlYWRzaG90JTIwd2hpdGUlMjBiYWNrZ3JvdW5kfGVufDF8fHx8MTc2Mjc4OTM5NHww&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral";
  
  const skillCategories = [
    {
      title: "AI & MCP",
      icon: Brain,
      color: "#BE266A",
      skills: ["AI Agents", "Model Context Protocol", "LangChain", "OpenAI", "Claude API", "Autonomous Workflows"]
    },
    {
      title: "WEGA Platform",
      icon: Database,
      color: "#3498B3",
      skills: ["Platform Architecture", "SDLC Automation", "Workflow Orchestration", "Integration Services", "Analytics Engine"]
    },
    {
      title: "DevOps & Infrastructure",
      icon: Cloud,
      color: "#355493",
      skills: ["AWS", "Azure", "GCP", "Kubernetes", "Docker", "Terraform", "CI/CD Pipelines", "GitOps"]
    },
    {
      title: "Development AI",
      icon: Code,
      color: "#746FA7",
      skills: ["Code Generation", "AI-Assisted Development", "Copilot Integration", "Smart Refactoring", "Test Generation"]
    },
    {
      title: "SDLC Integrations",
      icon: GitBranch,
      color: "#3498B3",
      skills: ["GitHub/GitLab", "Jira", "Jenkins", "CircleCI", "Datadog", "Slack", "Custom MCP Connectors"]
    },
    {
      title: "Industry Expertise",
      icon: Briefcase,
      color: "#351A55",
      skills: ["FinTech", "Enterprise SaaS", "E-commerce", "Healthcare Tech", "AI/ML Products", "Platform Engineering"]
    }
  ];
  
  return (
    <div className="space-y-6">
      <div className="bg-card text-card-foreground p-8 rounded-lg border border-border">
        <div className="flex flex-col md:flex-row gap-6 items-start md:items-center">
          <Avatar className="h-32 w-32 border-4 border-border overflow-hidden bg-white">
            <AvatarImage src={imageUrl} alt="Alex Chen" className="object-cover scale-150 object-[center_25%] bg-white" />
            <AvatarFallback className="bg-white">AC</AvatarFallback>
          </Avatar>
          
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-3 mb-2">
              <h1>Alex Chen</h1>
              <Badge variant="secondary" className="bg-[#3498B3] hover:bg-[#3498B3]/90 text-white">
                MLOps Engineer - WEGA
              </Badge>
            </div>
            
            <p className="text-muted-foreground mb-4 max-w-2xl">
              Specialized in implementing WEGA's AI-powered SDLC platform. 
              I deploy advanced AI Agents and MCP (Model Context Protocol) integrations to transform 
              software development teams into intelligent, autonomous organizations with AI-driven code 
              generation, testing, and deployment capabilities.
            </p>
            
            <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4" />
                <span>San Francisco Bay Area</span>
              </div>
              <div className="flex items-center gap-2">
                <Mail className="h-4 w-4" />
                <span>alex.chen@company.com</span>
              </div>
              <div className="flex items-center gap-2">
                <Linkedin className="h-4 w-4" />
                <span>linkedin.com/in/alexchen</span>
              </div>
              <div className="flex items-center gap-2">
                <Github className="h-4 w-4" />
                <span>github.com/alexchen</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-card-foreground text-[20px]">Technical Skills & Expertise</CardTitle>
          <CardDescription className="text-muted-foreground">
            AI-powered WEGA platform with MCP integration and SDLC intelligence
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-2 pb-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {skillCategories.map((category) => {
              const Icon = category.icon;
              return (
                <div key={category.title} className="space-y-4">
                  <div className="flex items-center gap-3">
                    <div 
                      className="w-9 h-9 rounded-md flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: category.color }}
                    >
                      <Icon className="h-5 w-5 text-white" />
                    </div>
                    <h4 className="text-card-foreground">{category.title}</h4>
                  </div>
                  <div className="flex flex-wrap gap-2 ml-12">
                    {category.skills.map((skill) => (
                      <Badge key={skill} variant="outline" className="bg-muted/50 border-border text-foreground hover:bg-muted">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}