import { Github, Linkedin, Twitter, Mail, Phone, MapPin, ExternalLink } from 'lucide-react';
import { Button } from './ui/button';

interface FooterProps {
  isDarkMode?: boolean;
  onNavigateToDemoVideos?: () => void;
}

export function Footer({ isDarkMode, onNavigateToDemoVideos }: FooterProps) {
  return (
    <footer className="bg-card border-t border-border mt-auto">
      <div className="px-6 py-12">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            {/* Company Info */}
            <div className="space-y-4">
              <div className="flex items-center space-x-2">

                <div>
                  <h3 className="text-card-foreground">Wipro WEGA</h3>
                  <p className="text-muted-foreground">Enterprise Software Engineering Platform infused by AI</p>
                </div>
              </div>
              <p className="text-muted-foreground">
                Empowering digital transformation through innovative development platforms and solutions.
              </p>
              <div className="flex space-x-3">
                <Button variant="ghost" size="sm" className="p-2 text-muted-foreground opacity-50" disabled>
                  <Github className="w-4 h-4" />
                </Button>
                <Button variant="ghost" size="sm" className="p-2 text-muted-foreground opacity-50" disabled>
                  <Linkedin className="w-4 h-4" />
                </Button>
                <Button variant="ghost" size="sm" className="p-2 text-muted-foreground opacity-50" disabled>
                  <Twitter className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {/* Platform */}
            <div className="space-y-4">
              <h4 className="text-card-foreground">Platform</h4>
              <ul className="space-y-2 text-muted-foreground">
                <li><span className="opacity-50">Developer Experience</span></li>
                <li><span className="opacity-50">Infrastructure</span></li>
                <li><span className="opacity-50">Analytics</span></li>
                <li><span className="opacity-50">Security</span></li>
                <li><span className="opacity-50">Release Management</span></li>
              </ul>
            </div>

            {/* Resources */}
            <div className="space-y-4">
              <h4 className="text-card-foreground">Resources</h4>
              <ul className="space-y-2 text-muted-foreground">
                <li>
                  <button 
                    onClick={onNavigateToDemoVideos}
                    className="hover:text-foreground flex items-center space-x-1 text-left cursor-pointer"
                  >
                    <span>Demo Videos (of features)</span>
                    <ExternalLink className="w-3 h-3" />
                  </button>
                </li>
                <li><span className="opacity-50">Documentation</span></li>
                <li><span className="opacity-50">API Reference</span></li>
                <li><span className="opacity-50">Tutorials</span></li>
                <li><span className="opacity-50">Best Practices</span></li>
                <li><span className="opacity-50">Support</span></li>
              </ul>
            </div>

            {/* Contact */}
            <div className="space-y-4">
              <h4 className="text-card-foreground">Contact</h4>
              <div className="space-y-2 text-muted-foreground">
                <div className="flex items-center space-x-2">
                  <Mail className="w-4 h-4" />
                  <span>abhinav.krishna@wipro.com</span>
                </div>
                <div className="flex items-center space-x-2">
                  <Phone className="w-4 h-4" />
                  <span>+91 98860 41268</span>
                </div>

              </div>
            </div>
          </div>

          {/* Bottom Bar */}
          <div className="border-t border-border mt-8 pt-8 flex flex-col md:flex-row justify-between items-center">
            <p className="text-muted-foreground">
              © {new Date().getFullYear()} Wipro Limited. All rights reserved.
            </p>
            <div className="flex space-x-6 mt-4 md:mt-0">
              <span className="text-muted-foreground opacity-50">Privacy Policy</span>
              <span className="text-muted-foreground opacity-50">Terms of Service</span>
              <span className="text-muted-foreground opacity-50">Cookie Policy</span>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}