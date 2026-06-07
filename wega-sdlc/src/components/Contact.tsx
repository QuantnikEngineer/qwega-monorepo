import { ArrowLeft, Mail, Phone, MapPin, Linkedin, Twitter, Globe, Send } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';

interface ContactProps {
  onBack: () => void;
  isDarkMode: boolean;
}

export function Contact({ onBack, isDarkMode }: ContactProps) {
  const contactInfo = [
    {
      icon: Mail,
      title: 'Email',
      details: 'wega-support@wipro.com',
      subDetails: 'General inquiries',
      color: '#3498B3',
    },
    {
      icon: Phone,
      title: 'Phone',
      details: '+1 (888) WEGA-HELP',
      subDetails: 'Mon-Fri, 8AM-8PM EST',
      color: '#355493',
    },
    {
      icon: MapPin,
      title: 'Headquarters',
      details: 'East Brunswick, NJ',
      subDetails: 'Wipro Limited',
      color: '#746FA7',
    },
  ];

  const offices = [
    { region: 'North America', city: 'East Brunswick, NJ', contact: '+1 (888) WEGA-HELP' },
    { region: 'Europe', city: 'London, UK', contact: '+44 20 XXXX XXXX' },
    { region: 'Asia Pacific', city: 'Bangalore, India', contact: '+91 80 XXXX XXXX' },
    { region: 'Latin America', city: 'São Paulo, Brazil', contact: '+55 11 XXXX XXXX' },
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
          <h1 className="text-foreground mb-4">Contact Us</h1>
          <p className="text-muted-foreground max-w-3xl">
            Have questions about WEGA? We're here to help. Reach out to our team for sales inquiries, 
            technical support, partnership opportunities, or general information about our AI-powered 
            software engineering platform.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-12">
          {/* Contact Methods */}
          {contactInfo.map((method, index) => (
            <Card
              key={index}
              className="p-6 bg-card border border-border hover:border-[#3498B3] transition-all"
            >
              <div
                className="p-3 rounded-lg w-fit mb-4"
                style={{ backgroundColor: `${method.color}20` }}
              >
                <method.icon className="w-6 h-6" style={{ color: method.color }} />
              </div>
              <h3 className="text-foreground mb-2">{method.title}</h3>
              <p className="text-foreground mb-1">{method.details}</p>
              <p className="text-muted-foreground text-sm">{method.subDetails}</p>
            </Card>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-12">
          {/* Contact Form */}
          <div>
            <h2 className="text-foreground mb-6">Send Us a Message</h2>
            <Card className="p-6 bg-card border border-border">
              <form className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="first-name" className="text-foreground">First Name *</Label>
                    <Input
                      id="first-name"
                      type="text"
                      placeholder="John"
                      className="bg-input-background text-foreground border-border"
                    />
                  </div>
                  <div>
                    <Label htmlFor="last-name" className="text-foreground">Last Name *</Label>
                    <Input
                      id="last-name"
                      type="text"
                      placeholder="Doe"
                      className="bg-input-background text-foreground border-border"
                    />
                  </div>
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
                  <Label htmlFor="company" className="text-foreground">Company</Label>
                  <Input
                    id="company"
                    type="text"
                    placeholder="Your Company Name"
                    className="bg-input-background text-foreground border-border"
                  />
                </div>
                <div>
                  <Label htmlFor="phone" className="text-foreground">Phone Number</Label>
                  <Input
                    id="phone"
                    type="tel"
                    placeholder="+1 (555) 123-4567"
                    className="bg-input-background text-foreground border-border"
                  />
                </div>
                <div>
                  <Label htmlFor="inquiry-type" className="text-foreground">Inquiry Type *</Label>
                  <Input
                    id="inquiry-type"
                    type="text"
                    placeholder="e.g., Sales, Support, Partnership"
                    className="bg-input-background text-foreground border-border"
                  />
                </div>
                <div>
                  <Label htmlFor="message" className="text-foreground">Message *</Label>
                  <Textarea
                    id="message"
                    placeholder="Tell us how we can help you..."
                    rows={5}
                    className="bg-input-background text-foreground border-border resize-none"
                  />
                </div>
                <Button
                  type="submit"
                  className="w-full bg-[#351A55] text-white hover:bg-[#2a1444] border-[#351A55]"
                >
                  <Send className="w-4 h-4 mr-2" />
                  Send Message
                </Button>
                <p className="text-xs text-muted-foreground">
                  By submitting this form, you agree to our privacy policy. We'll respond within 24 hours.
                </p>
              </form>
            </Card>
          </div>

          {/* Global Offices & Social */}
          <div>
            <h2 className="text-foreground mb-6">Global Offices</h2>
            <Card className="p-6 bg-card border border-border mb-6">
              <div className="space-y-4">
                {offices.map((office, index) => (
                  <div
                    key={index}
                    className="pb-4 border-b border-border last:border-0 last:pb-0"
                  >
                    <h3 className="text-foreground mb-1">{office.region}</h3>
                    <p className="text-sm text-muted-foreground mb-1">{office.city}</p>
                    <p className="text-sm text-[#3498B3]">{office.contact}</p>
                  </div>
                ))}
              </div>
            </Card>

            <h2 className="text-foreground mb-6">Connect With Us</h2>
            <Card className="p-6 bg-card border border-border">
              <div className="space-y-3">
                <Button
                  variant="outline"
                  className="w-full justify-start hover:bg-[#0077B5] hover:text-white hover:border-[#0077B5]"
                >
                  <Linkedin className="w-5 h-5 mr-3" />
                  Follow us on LinkedIn
                </Button>
                <Button
                  variant="outline"
                  className="w-full justify-start hover:bg-[#1DA1F2] hover:text-white hover:border-[#1DA1F2]"
                >
                  <Twitter className="w-5 h-5 mr-3" />
                  Follow us on Twitter
                </Button>
                <Button
                  variant="outline"
                  className="w-full justify-start hover:bg-[#3498B3] hover:text-white hover:border-[#3498B3]"
                >
                  <Globe className="w-5 h-5 mr-3" />
                  Visit Wipro.com
                </Button>
              </div>
            </Card>
          </div>
        </div>

        {/* Business Hours Notice */}
        <Card className="p-6 bg-card border border-[#3498B3]">
          <div className="flex items-start space-x-4">
            <div className="p-3 rounded-lg bg-[#3498B3]/20">
              <Mail className="w-6 h-6 text-[#3498B3]" />
            </div>
            <div>
              <h3 className="text-foreground mb-2">Business Hours</h3>
              <p className="text-muted-foreground text-sm">
                Our team is available Monday through Friday, 8:00 AM to 8:00 PM EST. For urgent technical 
                support outside business hours, please use our emergency support line or email support@wega.ai 
                with "URGENT" in the subject line.
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}