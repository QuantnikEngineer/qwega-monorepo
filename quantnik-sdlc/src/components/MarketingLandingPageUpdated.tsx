import { useState } from 'react';
import { 
  ArrowRight, 
  CheckCircle, 
  Code, 
  Cloud, 
  Shield, 
  Zap, 
  Users, 
  BarChart3, 
  GitBranch, 
  Rocket,
  Star,
  Target,
  TrendingUp,
  Clock,
  Mail,
  Phone,
  MapPin,
  Send,
  Play,
  Award,
  Globe,
  Settings,
  Lock,
  Gauge,
  X,
  Grid,
  Maximize2
} from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Separator } from './ui/separator';
import { Dialog, DialogContent, DialogTrigger, DialogTitle, DialogDescription } from './ui/dialog';
import { ImageWithFallback } from './figma/ImageWithFallback';
import buildIQFramework from "figma:asset/75b62d8ca62266f1dc0d03dc053408726ad749cb.png";
import heroImage from "figma:asset/3a6715133ddab9f24952e945a1541705e1b62f24.png";
import mcpCatalogGrid from "figma:asset/c53cae069fb3afd2b24f3c01b327f0f6e0b32781.png";
import img05HowTheRolesAreChanging1 from "figma:asset/1d4d6ffdca8238ab019b9d66c0a15ecbfd4a66e4.png";
import Roadmap from "../imports/Roadmap";
import BuildIqLayers from "../imports/BuildIqLayers";
import VibeProgrammer from "../imports/VibeProgrammer";
import LifeVibeProgrammer from "../imports/LifeVibeProgrammer";
import ModernEngineeringMetrics from "../imports/ModernEngineeringMetrics";
import HowTheRolesAreChanging from "../imports/HowTheRolesAreChanging";

interface MarketingLandingPageProps {
  onNavigateToCodeRepo?: () => void;
  onNavigateToPipelines?: () => void;
  onScrollToSignup?: () => void;
  isDarkMode?: boolean;
}

export function MarketingLandingPage({ onNavigateToCodeRepo, onNavigateToPipelines, onScrollToSignup, isDarkMode }: MarketingLandingPageProps) {
  const [contactForm, setContactForm] = useState({
    name: '',
    email: '',
    company: '',
    message: ''
  });
  
  const [isImageDialogOpen, setIsImageDialogOpen] = useState(false);

  const handleContactSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Handle contact form submission
    console.log('Contact form submitted:', contactForm);
    // Reset form
    setContactForm({ name: '', email: '', company: '', message: '' });
  };

  const features = [
    {
      icon: Code,
      title: "AI-Enhanced DevEX",
      description: "Intelligent developer experience with AI-powered code repositories, smart pipelines, and predictive insights.",
      color: "#351A55"
    },
    {
      icon: Cloud,
      title: "Smart Infrastructure",
      description: "AI-driven infrastructure automation, intelligent cost optimization, and predictive scaling with enterprise security.",
      color: "#355493"
    },
    {
      icon: Shield,
      title: "Intelligent Testing",
      description: "AI-powered test generation, automated quality assurance, and intelligent defect prediction for comprehensive testing.",
      color: "#3498B3"
    },
    {
      icon: Rocket,
      title: "AI-Driven Releases",
      description: "Intelligent deployment pipelines with AI-powered risk assessment, automated rollbacks, and smart approval workflows.",
      color: "#351A55"
    },
    {
      icon: BarChart3,
      title: "Predictive Analytics",
      description: "Advanced AI analytics platform with intelligent anomaly detection, predictive insights, and automated optimization.",
      color: "#746FA7"
    },
    {
      icon: Zap,
      title: "AI Asset Library",
      description: "Intelligent templates, AI-powered development agents, and smart accelerators that adapt to your workflow patterns.",
      color: "#BE266A"
    }
  ];

  const benefits = [
    {
      icon: TrendingUp,
      title: "80% Faster Development (Projected)",
      description: "Our early testing shows significant acceleration in development lifecycle with automated workflows"
    },
    {
      icon: Clock,
      title: "50% Reduced Time-to-Market (Target)",
      description: "Designed to dramatically reduce product delivery time with streamlined processes"
    },
    {
      icon: Target,
      title: "99.9% Platform Reliability (Goal)",
      description: "Built with enterprise-grade reliability, automated monitoring and self-healing capabilities"
    },
    {
      icon: Users,
      title: "Unified Developer Experience",
      description: "One platform for all development, testing, and deployment needs - coming soon"
    }
  ];

  const stats = [
    { number: "2024", label: "Launch Year" },
    { number: "8", label: "Integrated Modules" },
    { number: "50+", label: "Beta Partners" },
    { number: "95%", label: "Development Complete" }
  ];

  const testimonials = [
    {
      name: "Sarah Chen",
      role: "CTO, Design Partner",
      company: "Fortune 500 Technology Company",
      quote: "We're excited to be part of BuildIQ's development journey. The early previews show tremendous potential for transforming enterprise development workflows.",
      rating: 5
    },
    {
      name: "Michael Rodriguez",
      role: "VP Engineering, Beta Partner",
      company: "High-Growth SaaS Startup",
      quote: "The vision for AI-powered insights and unified development experience is exactly what the industry needs. Can't wait for the full launch.",
      rating: 5
    },
    {
      name: "David Kumar",
      role: "Lead DevOps, Early Adopter",
      company: "Global Financial Services",
      quote: "Based on our early access sessions, BuildIQ will set a new standard for enterprise development platforms. The security-first approach is impressive.",
      rating: 5
    }
  ];

  return (
    <div className="flex flex-col">
      {/* Hero Section */}
      <section className="relative bg-gradient-to-br from-[#351A55] via-[#355493] to-[#3498B3] text-white overflow-hidden">
        <div className="absolute inset-0 bg-black/50" />
        <div className="relative max-w-7xl mx-auto px-6 py-20 lg:py-32">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-8">
              <div className="space-y-4">
                <Badge variant="secondary" className="bg-white/20 text-white border-white/30 hover:bg-white/30">
                  <Star className="w-3 h-3 mr-1" />
                  Coming Soon - Early Access Available
                </Badge>
                <h1 className="font-bold leading-tight text-[48px]">
                  Enterprise <span className="bg-gradient-to-r from-yellow-400 to-orange-500 bg-clip-text text-transparent">Software Engineering</span>
                  <br />Platform <span className="bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent font-light">infused by AI</span>
                </h1>
                <p className="text-xl text-white/90 max-w-2xl">
                  BuildIQ transforms enterprise software engineering with AI-powered automation, intelligent insights, and unified development workflows. Experience the next-generation platform that seamlessly integrates development, testing, infrastructure, and deployment into one powerful AI-enhanced ecosystem.
                </p>
              </div>
              
              <div className="flex flex-col sm:flex-row gap-4">
                <Button 
                  size="lg" 
                  className="bg-slate-700 text-white hover:bg-slate-800 dark:bg-slate-600 dark:hover:bg-slate-700 text-lg px-8 py-3 text-[14px]"
                >
                  Request Demo
                  <ArrowRight className="w-5 h-5 ml-2" />
                </Button>
                <Button 
                  size="lg" 
                  className="bg-slate-700 text-white hover:bg-slate-800 dark:bg-slate-600 dark:hover:bg-slate-700 text-lg px-8 py-3 text-[14px]"
                >
                  <Play className="w-5 h-5 mr-2" />
                  See Preview
                </Button>
              </div>

            </div>
            
            <div className="relative">
              <div className="relative rounded-2xl overflow-hidden shadow-2xl">
                <div className="w-full h-96 relative overflow-hidden rounded-lg bg-gradient-to-br from-[#351A55] via-[#355493] to-[#3498B3] flex items-center justify-center">
                  <img 
                    src={heroImage} 
                    alt="BuildIQ Platform Overview" 
                    className="absolute inset-0 w-full h-full object-cover"
                  />

                  <div className="absolute bottom-4 right-4 text-white/60 text-sm">Enterprise Software Engineering Platform</div>
                </div>
              </div>
              <div className="absolute -bottom-6 -left-6 bg-card text-foreground p-4 rounded-xl shadow-lg border border-border">
                <div className="flex items-center space-x-2">
                  <Award className="w-6 h-6 text-[#BE266A]" />
                  <div>
                    <div className="font-semibold">Coming Soon</div>
                    <div className="text-sm text-muted-foreground">Q3 2025 Early Access</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* About Section */}
      <section className="py-20 bg-card">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl lg:text-4xl font-bold text-card-foreground mb-4">
              Introducing BuildIQ
            </h2>
            <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
              BuildIQ is Wipro's AI-powered enterprise software engineering platform designed to transform how organizations approach development, testing, and deployment through intelligent automation and unified workflows.
            </p>
          </div>

          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-6">
              <h3 className="text-2xl font-semibold text-card-foreground">
                AI-Powered Engineering Excellence
              </h3>
              <p className="text-muted-foreground leading-relaxed">
                BuildIQ leverages advanced artificial intelligence to unify eight comprehensive modules into a single, intelligent platform. Every aspect of your software engineering lifecycle is enhanced with AI-driven insights, automated workflows, and predictive capabilities that optimize for speed, quality, and enterprise scale.
              </p>
              
              <div className="space-y-4">
                <div className="flex items-start space-x-3">
                  <CheckCircle className="w-5 h-5 text-blue-500 mt-1" />
                  <div>
                    <h4 className="font-medium text-card-foreground">AI-Powered Automation</h4>
                    <p className="text-sm text-muted-foreground">Intelligent workflows that will learn and adapt to your team's patterns</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <CheckCircle className="w-5 h-5 text-blue-500 mt-1" />
                  <div>
                    <h4 className="font-medium text-card-foreground">Enterprise Security</h4>
                    <p className="text-sm text-muted-foreground">Bank-grade security with compliance frameworks built-in from day one</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <CheckCircle className="w-5 h-5 text-blue-500 mt-1" />
                  <div>
                    <h4 className="font-medium text-card-foreground">Global Scale</h4>
                    <p className="text-sm text-muted-foreground">Architected to handle enterprise workloads across multiple regions</p>
                  </div>
                </div>
              </div>
            </div>
            
            <div className="relative">
              <div className="w-full h-96 relative overflow-hidden rounded-2xl shadow-lg bg-muted/50">
                <Dialog open={isImageDialogOpen} onOpenChange={setIsImageDialogOpen}>
                  <DialogTrigger asChild>
                    <div className="relative group cursor-pointer h-full">
                      <img 
                        src={buildIQFramework}
                        alt="BuildIQ Framework"
                        className="w-full h-full object-contain hover:opacity-90 transition-opacity"
                      />
                      {/* Expand Icon Button */}
                      <div className="absolute top-4 right-4 bg-black/50 backdrop-blur-sm rounded-lg p-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                        <Maximize2 className="w-5 h-5 text-white" />
                      </div>
                      {/* Hover overlay */}
                      <div className="absolute inset-0 bg-black/10 opacity-0 group-hover:opacity-100 transition-opacity duration-200 rounded-2xl" />
                    </div>
                  </DialogTrigger>
                  <DialogContent className="!w-[1200px] !h-[912px] !max-w-none !max-h-none p-0 overflow-hidden">
                    <DialogTitle className="sr-only">BuildIQ Framework</DialogTitle>
                    <DialogDescription className="sr-only">
                      Expanded view of the BuildIQ AI-powered enterprise software engineering platform framework
                    </DialogDescription>
                    <div className="relative">
                      <img 
                        src={buildIQFramework}
                        alt="BuildIQ Framework"
                        className="w-full h-auto"
                      />
                    </div>
                  </DialogContent>
                </Dialog>
              </div>
              
              {/* Framework Title */}
              <div className="mt-4 text-center">
                <h4 className="text-lg font-semibold text-card-foreground mb-1">
                  BuildIQ Framework
                </h4>
                <p className="text-sm text-muted-foreground">
                  Click to expand and explore our comprehensive platform architecture
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Rest of the sections remain the same... */}
      {/* Use Cases and Integration Roadmap Section */}
      <section className="py-20 bg-muted/30">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl lg:text-4xl font-bold text-card-foreground mb-4">
              Use Cases and Integration Roadmap
            </h2>
            <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
              Discover how BuildIQ transforms enterprise workflows and see our strategic integration timeline for comprehensive platform deployment
            </p>
          </div>

          <div className="flex justify-center">
            <div className="relative w-full max-w-[1200px] h-[625px] rounded-2xl overflow-hidden shadow-xl">
              <Roadmap />
            </div>
          </div>
        </div>
      </section>

      {/* Contact Section */}
      <section id="signup-section" className="py-20 bg-card">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid lg:grid-cols-2 gap-16">
            {/* Contact Information */}
            <div className="space-y-8">
              <div>
                <h2 className="text-3xl font-bold text-card-foreground mb-4">
                  Be First in Line for BuildIQ
                </h2>
                <p className="text-xl text-muted-foreground leading-relaxed">
                  Join our early access program and be among the first to experience BuildIQ when it launches. Get priority access, exclusive updates, and influence the final product features.
                </p>
              </div>

              <div className="space-y-6">
                <div className="flex items-start space-x-4">
                  <div className="w-10 h-10 bg-[#351A55] rounded-lg flex items-center justify-center">
                    <Mail className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-card-foreground">Get Updates</h3>
                    <p className="text-muted-foreground">abhinav.krishna@wipro.com</p>
                    <p className="text-sm text-muted-foreground">Early access updates & launch notifications</p>
                  </div>
                </div>

                <div className="flex items-start space-x-4">
                  <div className="w-10 h-10 bg-[#3498B3] rounded-lg flex items-center justify-center">
                    <Phone className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-card-foreground">Schedule Demo</h3>
                    <p className="text-muted-foreground">+91 98860 41268</p>
                    <p className="text-sm text-muted-foreground">Book your preview session</p>
                  </div>
                </div>

                <div className="flex items-start space-x-4">
                  <div className="w-10 h-10 bg-[#BE266A] rounded-lg flex items-center justify-center">
                    <Globe className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-card-foreground">Launch Timeline</h3>
                    <p className="text-muted-foreground">Q3 2025 - Early Access</p>
                    <p className="text-sm text-muted-foreground">General availability Q4 2025</p>
                  </div>
                </div>
              </div>

              <div className="relative rounded-xl overflow-hidden">
                <ImageWithFallback
                  src="https://images.unsplash.com/photo-1608222351212-18fe0ec7b13b?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxidXNpbmVzcyUyMGFuYWx5dGljcyUyMGRhc2hib2FyZHxlbnwxfHx8fDE3NTc3NDUwMDV8MA&ixlib=rb-4.1.0&q=80&w=1080"
                  alt="Business Analytics Dashboard"
                  className="w-full h-48 object-cover"
                />
              </div>
            </div>

            {/* Contact Form */}
            <Card className="h-fit">
              <CardHeader>
                <CardTitle>Request a Demo</CardTitle>
                <CardDescription>
                  Get an exclusive preview of BuildIQ before the official launch
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleContactSubmit} className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Input
                        placeholder="Full Name"
                        value={contactForm.name}
                        onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
                        required
                      />
                    </div>
                    <div>
                      <Input
                        type="email"
                        placeholder="Work Email"
                        value={contactForm.email}
                        onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })}
                        required
                      />
                    </div>
                  </div>
                  <div>
                    <Input
                      placeholder="Company Name"
                      value={contactForm.company}
                      onChange={(e) => setContactForm({ ...contactForm, company: e.target.value })}
                      required
                    />
                  </div>
                  <div>
                    <Textarea
                      placeholder="Tell us about your use case and how BuildIQ could help your organization..."
                      rows={4}
                      value={contactForm.message}
                      onChange={(e) => setContactForm({ ...contactForm, message: e.target.value })}
                      required
                    />
                  </div>
                  <Button type="submit" className="w-full">
                    <Send className="w-4 h-4 mr-2" />
                    Request Demo Access
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>
    </div>
  );
}