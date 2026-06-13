import { ArrowLeft, MapPin, Mail, Github, Linkedin, Coffee, Code, Monitor, Calendar, Plane, Target, Users, Lightbulb, Zap, CreditCard, ShoppingCart, Building2, Home, TrendingUp, CheckCircle } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { ImageWithFallback } from './figma/ImageWithFallback';

interface MLOpsWorkspaceProps {
  onBack: () => void;
  isDarkMode?: boolean;
}

export function MLOpsWorkspace({ onBack, isDarkMode }: MLOpsWorkspaceProps) {
  return (
    <div className="min-h-screen bg-background">
      {/* Hero Section with Profile */}
      <section className="bg-gradient-to-br from-[#1e293b] via-[#334155] to-[#475569] text-white py-16">
        <div className="max-w-7xl mx-auto px-6">
          <Button
            variant="ghost"
            onClick={onBack}
            className="text-white hover:bg-white/10 mb-8"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Home
          </Button>
          
          <div className="flex items-start gap-8">
            {/* Profile Image */}
            <div className="flex-shrink-0">
              <div className="w-32 h-32 rounded-full bg-gradient-to-br from-[#351A55] to-[#746FA7] p-1">
                <div className="w-full h-full rounded-full bg-white overflow-hidden">
                  <ImageWithFallback 
                    src="https://images.unsplash.com/photo-1762522927402-f390672558d8?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxidXNpbmVzcyUyMHByb2Zlc3Npb25hbCUyMGhlYWRzaG90JTIwd2hpdGUlMjBiYWNrZ3JvdW5kfGVufDF8fHx8MTc2Mjc4OTM5NHww&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral"
                    alt="Alex Chen - MLOps Engineer"
                    className="w-full h-full object-cover"
                  />
                </div>
              </div>
            </div>
            
            {/* Profile Info */}
            <div className="flex-1">
              <div className="mb-4">
                <h1 className="text-4xl mb-2">Alex Chen</h1>
                <Badge className="bg-[#3498B3] text-white border-none">
                  MLOps Engineer - QUANTNIK
                </Badge>
              </div>
              
              <p className="text-lg text-white/90 leading-relaxed mb-6 max-w-4xl">
                Specialized in implementing QUANTNIK's AI-powered SDLC platform. I deploy advanced AI Agents and MCP (Model Context Protocol) integrations to transform software development teams into intelligent, autonomous organizations with AI-driven code generation, testing, and deployment capabilities.
              </p>
              
              {/* Contact Info */}
              <div className="flex flex-wrap gap-6 text-white/80">
                <div className="flex items-center gap-2">
                  <MapPin className="w-4 h-4" />
                  <span>San Francisco Bay Area</span>
                </div>
                <div className="flex items-center gap-2">
                  <Mail className="w-4 h-4" />
                  <span>alex.chen@company.com</span>
                </div>
                <div className="flex items-center gap-2">
                  <Linkedin className="w-4 h-4" />
                  <span>linkedin.com/in/alexchen</span>
                </div>
                <div className="flex items-center gap-2">
                  <Github className="w-4 h-4" />
                  <span>github.com/alexchen</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Technical Skills & Expertise */}
      <section className="py-16 bg-card">
        <div className="max-w-7xl mx-auto px-6">
          <h2 className="text-3xl text-card-foreground mb-3">Technical Skills & Expertise</h2>
          <p className="text-muted-foreground mb-8">
            AI-powered QUANTNIK platform with MCP integration and SDLC intelligence
          </p>
          
          <div className="grid md:grid-cols-2 gap-8">
            {/* AI & MCP */}
            <Card className="bg-background border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-card-foreground">
                  <div className="w-8 h-8 bg-[#351A55] rounded flex items-center justify-center">
                    <Code className="w-4 h-4 text-white" />
                  </div>
                  AI & MCP
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">AI Agent Orchestration</Badge>
                  <Badge variant="secondary">Model Context Protocol (MCP)</Badge>
                  <Badge variant="secondary">LLM Integration</Badge>
                  <Badge variant="secondary">Code Generation AI</Badge>
                  <Badge variant="secondary">Autonomous Development</Badge>
                </div>
              </CardContent>
            </Card>

            {/* QUANTNIK Platform */}
            <Card className="bg-background border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-card-foreground">
                  <div className="w-8 h-8 bg-[#3498B3] rounded flex items-center justify-center">
                    <Monitor className="w-4 h-4 text-white" />
                  </div>
                  QUANTNIK Platform
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">QUANTNIK SDLC APIs</Badge>
                  <Badge variant="secondary">AI-Powered Code Review</Badge>
                  <Badge variant="secondary">Automated Testing</Badge>
                  <Badge variant="secondary">Deployment Intelligence</Badge>
                  <Badge variant="secondary">Developer Analytics</Badge>
                </div>
              </CardContent>
            </Card>

            {/* DevOps & Infrastructure */}
            <Card className="bg-background border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-card-foreground">
                  <div className="w-8 h-8 bg-[#355493] rounded flex items-center justify-center">
                    <Zap className="w-4 h-4 text-white" />
                  </div>
                  DevOps & Infrastructure
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">CI/CD Pipelines</Badge>
                  <Badge variant="secondary">Kubernetes</Badge>
                  <Badge variant="secondary">AWS/Azure/GCP</Badge>
                  <Badge variant="secondary">Infrastructure as Code</Badge>
                  <Badge variant="secondary">GitOps</Badge>
                  <Badge variant="secondary">Observability</Badge>
                </div>
              </CardContent>
            </Card>

            {/* Development AI */}
            <Card className="bg-background border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-card-foreground">
                  <div className="w-8 h-8 bg-[#746FA7] rounded flex items-center justify-center">
                    <Users className="w-4 h-4 text-white" />
                  </div>
                  Development AI
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">Code Quality Agents</Badge>
                  <Badge variant="secondary">Bug Detection AI</Badge>
                  <Badge variant="secondary">Test Generation</Badge>
                  <Badge variant="secondary">Security Scanning</Badge>
                  <Badge variant="secondary">Performance Optimization AI</Badge>
                </div>
              </CardContent>
            </Card>

            {/* SDLC Integrations */}
            <Card className="bg-background border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-card-foreground">
                  <div className="w-8 h-8 bg-[#BE266A] rounded flex items-center justify-center">
                    <Target className="w-4 h-4 text-white" />
                  </div>
                  SDLC Integrations
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">GitHub/GitLab</Badge>
                  <Badge variant="secondary">Jira</Badge>
                  <Badge variant="secondary">Jenkins</Badge>
                  <Badge variant="secondary">CircleCI</Badge>
                  <Badge variant="secondary">Datadog</Badge>
                  <Badge variant="secondary">Slack</Badge>
                  <Badge variant="secondary">Custom MCP Connectors</Badge>
                </div>
              </CardContent>
            </Card>

            {/* Industry Expertise */}
            <Card className="bg-background border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-card-foreground">
                  <div className="w-8 h-8 bg-[#3498B3] rounded flex items-center justify-center">
                    <Lightbulb className="w-4 h-4 text-white" />
                  </div>
                  Industry Expertise
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">FinTech</Badge>
                  <Badge variant="secondary">Enterprise SaaS</Badge>
                  <Badge variant="secondary">E-commerce</Badge>
                  <Badge variant="secondary">Healthcare Tech</Badge>
                  <Badge variant="secondary">AI/ML Products</Badge>
                  <Badge variant="secondary">Platform Engineering</Badge>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Work Philosophy */}
      <section className="py-16 bg-background">
        <div className="max-w-7xl mx-auto px-6">
          <h2 className="text-3xl text-card-foreground mb-3">Work Philosophy</h2>
          <p className="text-muted-foreground mb-8">
            Guiding principles for AI-powered SDLC transformation
          </p>
          
          <div className="grid md:grid-cols-2 gap-6">
            {/* AI in Real Dev Workflows */}
            <Card className="bg-card border-border">
              <CardContent className="pt-6">
                <div className="flex gap-4">
                  <div className="flex-shrink-0">
                    <div className="w-12 h-12 bg-blue-500/10 rounded-lg flex items-center justify-center">
                      <Target className="w-6 h-6 text-blue-500" />
                    </div>
                  </div>
                  <div>
                    <h3 className="text-card-foreground mb-2">AI in Real Dev Workflows</h3>
                    <p className="text-muted-foreground">
                      AI Agents must integrate seamlessly into existing development workflows. No disruption to developer productivity—enhance it with intelligent automation.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Autonomous SDLC */}
            <Card className="bg-card border-border">
              <CardContent className="pt-6">
                <div className="flex gap-4">
                  <div className="flex-shrink-0">
                    <div className="w-12 h-12 bg-blue-500/10 rounded-lg flex items-center justify-center">
                      <Zap className="w-6 h-6 text-blue-500" />
                    </div>
                  </div>
                  <div>
                    <h3 className="text-card-foreground mb-2">Autonomous SDLC</h3>
                    <p className="text-muted-foreground">
                      Leverage QUANTNIK's AI Agents to automate code review, testing, and deployment. Let developers focus on architecture and business logic while AI handles repetitive tasks.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Developer-AI Partnership */}
            <Card className="bg-card border-border">
              <CardContent className="pt-6">
                <div className="flex gap-4">
                  <div className="flex-shrink-0">
                    <div className="w-12 h-12 bg-blue-500/10 rounded-lg flex items-center justify-center">
                      <Users className="w-6 h-6 text-blue-500" />
                    </div>
                  </div>
                  <div>
                    <h3 className="text-card-foreground mb-2">Developer-AI Partnership</h3>
                    <p className="text-muted-foreground">
                      The best code comes from developers and AI working together. AI suggests, developers decide. Build trust through transparency and explainable AI recommendations.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* MCP-Driven SDLC */}
            <Card className="bg-card border-border">
              <CardContent className="pt-6">
                <div className="flex gap-4">
                  <div className="flex-shrink-0">
                    <div className="w-12 h-12 bg-blue-500/10 rounded-lg flex items-center justify-center">
                      <Lightbulb className="w-6 h-6 text-blue-500" />
                    </div>
                  </div>
                  <div>
                    <h3 className="text-card-foreground mb-2">MCP-Driven SDLC</h3>
                    <p className="text-muted-foreground">
                      Use Model Context Protocol to unify the entire development toolchain—from IDE to production—creating an intelligent, context-aware development ecosystem.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* A Day in the Life */}
      <section className="py-16 bg-card">
        <div className="max-w-7xl mx-auto px-6">
          <h2 className="text-3xl text-card-foreground mb-3">A Day in the Life</h2>
          <p className="text-muted-foreground mb-8">
            How I spend my time deploying QUANTNIK AI for software development teams
          </p>
          
          <div className="space-y-4">
            {/* AI Agent Performance Review */}
            <Card className="bg-background border-border">
              <CardContent className="pt-6">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0">
                    <div className="w-12 h-12 bg-slate-100 dark:bg-slate-800 rounded-lg flex items-center justify-center">
                      <Coffee className="w-6 h-6 text-slate-600 dark:text-slate-400" />
                    </div>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <h3 className="text-card-foreground">AI Agent Performance Review</h3>
                        <p className="text-sm text-muted-foreground">Morning</p>
                      </div>
                      <Badge className="bg-blue-500 text-white">15%</Badge>
                    </div>
                    <p className="text-muted-foreground">
                      Review overnight AI-generated code reviews, check agent performance metrics, validate automated test results, and sync with engineering leadership on priorities.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* QUANTNIK Implementation */}
            <Card className="bg-background border-border">
              <CardContent className="pt-6">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0">
                    <div className="w-12 h-12 bg-slate-100 dark:bg-slate-800 rounded-lg flex items-center justify-center">
                      <Code className="w-6 h-6 text-slate-600 dark:text-slate-400" />
                    </div>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <h3 className="text-card-foreground">QUANTNIK Implementation</h3>
                        <p className="text-sm text-muted-foreground">Mid-Morning</p>
                      </div>
                      <Badge className="bg-blue-500 text-white">40%</Badge>
                    </div>
                    <p className="text-muted-foreground">
                      Deploy AI Agents for code review and test generation, configure MCP connectors to GitHub/Jira, fine-tune LLM prompts for team-specific coding standards.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Developer Enablement */}
            <Card className="bg-background border-border">
              <CardContent className="pt-6">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0">
                    <div className="w-12 h-12 bg-slate-100 dark:bg-slate-800 rounded-lg flex items-center justify-center">
                      <Monitor className="w-6 h-6 text-slate-600 dark:text-slate-400" />
                    </div>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <h3 className="text-card-foreground">Developer Enablement</h3>
                        <p className="text-sm text-muted-foreground">Afternoon</p>
                      </div>
                      <Badge className="bg-blue-500 text-white">25%</Badge>
                    </div>
                    <p className="text-muted-foreground">
                      Hands-on workshops with development teams on AI-assisted coding, demonstrate QUANTNIK capabilities, gather feedback on AI suggestions, build developer trust.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Model & Workflow Optimization */}
            <Card className="bg-background border-border">
              <CardContent className="pt-6">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0">
                    <div className="w-12 h-12 bg-slate-100 dark:bg-slate-800 rounded-lg flex items-center justify-center">
                      <Calendar className="w-6 h-6 text-slate-600 dark:text-slate-400" />
                    </div>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <h3 className="text-card-foreground">Model & Workflow Optimization</h3>
                        <p className="text-sm text-muted-foreground">Late Afternoon</p>
                      </div>
                      <Badge className="bg-blue-500 text-white">15%</Badge>
                    </div>
                    <p className="text-muted-foreground">
                      Fine-tune AI models based on developer feedback, optimize MCP data flows, improve agent accuracy, coordinate with QUANTNIK product team on custom features.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Customer Engagements */}
            <Card className="bg-background border-border">
              <CardContent className="pt-6">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0">
                    <div className="w-12 h-12 bg-slate-100 dark:bg-slate-800 rounded-lg flex items-center justify-center">
                      <Plane className="w-6 h-6 text-slate-600 dark:text-slate-400" />
                    </div>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <h3 className="text-card-foreground">Customer Engagements</h3>
                        <p className="text-sm text-muted-foreground">Ongoing</p>
                      </div>
                      <Badge className="bg-blue-500 text-white">50% of weeks</Badge>
                    </div>
                    <p className="text-muted-foreground">
                      Travel to customer sites for QUANTNIK implementations, AI Agent deployments, and SDLC transformation initiatives. Laptop + technical expertise required.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Key QUANTNIK AI Deployments */}
      <section className="py-16 bg-background">
        <div className="max-w-7xl mx-auto px-6">
          <h2 className="text-3xl text-card-foreground mb-3">Key QUANTNIK AI Deployments</h2>
          <p className="text-muted-foreground mb-8">
            Real-world implementations of AI-powered SDLC transformation
          </p>
          
          <div className="grid md:grid-cols-2 gap-6">
            {/* Stripe */}
            <Card className="bg-card border-border">
              <CardHeader>
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-[#635BFF]/10 rounded-lg flex items-center justify-center">
                      <CreditCard className="w-6 h-6 text-[#635BFF]" />
                    </div>
                    <div>
                      <h3 className="text-card-foreground">Stripe</h3>
                      <p className="text-sm text-muted-foreground">9 months</p>
                    </div>
                  </div>
                  <Badge className="bg-green-500 text-white border-none">
                    Live
                  </Badge>
                </div>
                <CardTitle className="text-lg text-card-foreground">
                  AI-Powered Payment Platform SDLC Transformation
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-muted-foreground">
                  Deployed QUANTNIK AI Agents to automate code review, testing, and deployment for Stripe's payment processing infrastructure. MCP integration with GitHub and Jira enabled seamless SDLC intelligence.
                </p>
                
                <div>
                  <p className="text-sm text-card-foreground mb-2">Technologies</p>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary">QUANTNIK AI Agents</Badge>
                    <Badge variant="secondary">MCP GitHub/Jira</Badge>
                    <Badge variant="secondary">GPT-4 Code Review</Badge>
                    <Badge variant="secondary">Automated Testing</Badge>
                    <Badge variant="secondary">CI/CD Intelligence</Badge>
                  </div>
                </div>
                
                <div className="border-t border-border pt-4">
                  <p className="text-sm text-card-foreground mb-3">Impact</p>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-muted-foreground">60% faster code review cycles</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-muted-foreground">45% reduction in production bugs</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-muted-foreground">30% faster deployment cycles</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Shopify */}
            <Card className="bg-card border-border">
              <CardHeader>
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-[#96BF48]/10 rounded-lg flex items-center justify-center">
                      <ShoppingCart className="w-6 h-6 text-[#96BF48]" />
                    </div>
                    <div>
                      <h3 className="text-card-foreground">Shopify</h3>
                      <p className="text-sm text-muted-foreground">7 months</p>
                    </div>
                  </div>
                  <Badge className="bg-orange-500 text-white border-none">
                    Pilot
                  </Badge>
                </div>
                <CardTitle className="text-lg text-card-foreground">
                  E-commerce Platform - Autonomous Testing & Deployment
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-muted-foreground">
                  Implemented AI-powered test generation and deployment automation for Shopify's e-commerce platform. QUANTNIK SDLC APIs enabled intelligent performance monitoring and release optimization.
                </p>
                
                <div>
                  <p className="text-sm text-card-foreground mb-2">Technologies</p>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary">QUANTNIK SDLC APIs</Badge>
                    <Badge variant="secondary">AI Test Generation</Badge>
                    <Badge variant="secondary">Deployment Bots</Badge>
                    <Badge variant="secondary">Performance Monitoring AI</Badge>
                  </div>
                </div>
                
                <div className="border-t border-border pt-4">
                  <p className="text-sm text-card-foreground mb-3">Impact</p>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-muted-foreground">70% increase in test coverage</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-muted-foreground">50% faster release cycles</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-muted-foreground">40% reduction in production incidents</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Goldman Sachs */}
            <Card className="bg-card border-border">
              <CardHeader>
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-[#0033A1]/10 rounded-lg flex items-center justify-center">
                      <Building2 className="w-6 h-6 text-[#0033A1]" />
                    </div>
                    <div>
                      <h3 className="text-card-foreground">Goldman Sachs</h3>
                      <p className="text-sm text-muted-foreground">12 months</p>
                    </div>
                  </div>
                  <Badge className="bg-green-500 text-white border-none">
                    Live in Production
                  </Badge>
                </div>
                <CardTitle className="text-lg text-card-foreground">
                  FinTech SDLC - AI Code Quality & Compliance
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-muted-foreground">
                  Deployed enterprise-grade QUANTNIK compliance AI for financial services. Automated security scanning and regulatory code review ensure 100% compliance with financial industry standards.
                </p>
                
                <div>
                  <p className="text-sm text-card-foreground mb-2">Technologies</p>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary">QUANTNIK Compliance AI</Badge>
                    <Badge variant="secondary">Security Scanning</Badge>
                    <Badge variant="secondary">MCP Enterprise</Badge>
                    <Badge variant="secondary">Regulatory Code Review</Badge>
                  </div>
                </div>
                
                <div className="border-t border-border pt-4">
                  <p className="text-sm text-card-foreground mb-3">Impact</p>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-muted-foreground">100% compliance audit pass rate</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-muted-foreground">55% faster security reviews</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-muted-foreground">Zero critical vulnerabilities in production</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Airbnb */}
            <Card className="bg-card border-border">
              <CardHeader>
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-[#FF5A5F]/10 rounded-lg flex items-center justify-center">
                      <Home className="w-6 h-6 text-[#FF5A5F]" />
                    </div>
                    <div>
                      <h3 className="text-card-foreground">Airbnb</h3>
                      <p className="text-sm text-muted-foreground">6 months</p>
                    </div>
                  </div>
                  <Badge className="bg-green-500 text-white border-none">
                    Live
                  </Badge>
                </div>
                <CardTitle className="text-lg text-card-foreground">
                  Full-Stack AI Development Assistant
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-muted-foreground">
                  Implemented QUANTNIK AI Copilot for full-stack development teams. Context-aware code generation and MCP Slack/IDE integration created an intelligent development ecosystem.
                </p>
                
                <div>
                  <p className="text-sm text-card-foreground mb-2">Technologies</p>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary">QUANTNIK AI Copilot</Badge>
                    <Badge variant="secondary">Context-Aware Code Gen</Badge>
                    <Badge variant="secondary">MCP Slack/IDE</Badge>
                    <Badge variant="secondary">Developer Analytics</Badge>
                  </div>
                </div>
                
                <div className="border-t border-border pt-4">
                  <p className="text-sm text-card-foreground mb-3">Impact</p>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-muted-foreground">35% developer productivity boost</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-muted-foreground">80% AI suggestion acceptance rate</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-muted-foreground">25% faster developer onboarding</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Call to Action */}
      <section className="py-16 bg-gradient-to-br from-[#351A55] via-[#355493] to-[#3498B3] text-white">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <h2 className="text-4xl mb-6">
            Ready to Transform Your SDLC with AI?
          </h2>
          <p className="text-xl text-white/90 mb-8 leading-relaxed">
            Discover how QUANTNIK's MLOps engineers can help your team implement AI-powered development workflows.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button 
              size="lg" 
              className="bg-white text-[#351A55] hover:bg-white/90"
            >
              Request a Demo
            </Button>
            <Button 
              size="lg" 
              variant="outline" 
              className="border-white text-white hover:bg-white/10"
            >
              Contact Sales
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
