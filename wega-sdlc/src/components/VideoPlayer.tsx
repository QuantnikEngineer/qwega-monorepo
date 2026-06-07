import { ArrowLeft } from "lucide-react";
import { Button } from "./ui/button";

interface VideoPlayerProps {
  videoTitle: string;
  videoUrl: string;
  onBack: () => void;
  isDarkMode?: boolean;
}

export function VideoPlayer({
  videoTitle,
  videoUrl,
  onBack,
  isDarkMode,
}: VideoPlayerProps) {
  // Convert SharePoint share links to embed URLs if possible
  const getEmbedUrl = (url: string): string => {
    // For SharePoint video links, try to extract and convert to embed format
    if (url.includes('wipro365.sharepoint.com')) {
      // If it's already an embed URL, return it
      if (url.includes('_layouts/15/embed.aspx')) {
        return url;
      }
      
      // For the specific WEGA demo video
      if (url.includes('BuildIQFoundry-Full%20Demo.mp4')) {
        return 'https://wipro365.sharepoint.com/sites/BuildIQ/_layouts/15/embed.aspx?UniqueId=e97ecc06-098e-4a72-b685-f15e01cb20b5&embed=%7B%22ust%22%3Atrue%2C%22hv%22%3A%22CopyEmbedCode%22%7D&referrer=StreamWebApp&referrerScenario=EmbedDialog.Create';
      }
      
      // For the BuildIQ Intro video
      if (url.includes('BuildIQ%20Intro.mp4')) {
        return 'https://wipro365.sharepoint.com/sites/BuildIQ/_layouts/15/embed.aspx?UniqueId=68c3b687-4aae-436d-945c-512857139844&embed=%7B%22ust%22%3Afalse%2C%22hv%22%3A%22CopyEmbedCode%22%7D&referrer=StreamWebApp&referrerScenario=EmbedDialog.Create';
      }
      
      // For other SharePoint links, return the original URL
      // The iframe will try to display it
      return url;
    }
    
    return url;
  };

  const embedUrl = getEmbedUrl(videoUrl);

  return (
    <div className="min-h-screen bg-background">
      {/* Hero Banner */}
      <div className="relative overflow-hidden">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-[#351A55] via-[#355493] to-[#3498B3]" />

        {/* Content */}
        <div className="relative px-6 py-16">
          <div className="max-w-7xl mx-auto">
            {/* Back Button */}
            <Button
              variant="ghost"
              onClick={onBack}
              className="mb-8 text-white/80 hover:text-white hover:bg-white/10 transition-colors"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Demo Videos
            </Button>

            {/* Hero Content */}
            <div className="text-center text-white">
              <h1 className="text-display mb-6">{videoTitle}</h1>
              <p className="text-body-large max-w-3xl mx-auto text-white/90">
                Watch this comprehensive demonstration of WEGA platform
                capabilities
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Video Player Section */}
      <div className="px-6 py-16">
        <div className="max-w-7xl mx-auto">
          {/* Video Container */}
          <div className="bg-card rounded-lg shadow-lg overflow-hidden border border-border">
            <div className="aspect-video bg-black flex items-center justify-center">
              <iframe
                src={embedUrl}
                className="w-full h-full"
                frameBorder="0"
                scrolling="no"
                allowFullScreen
                title={videoTitle}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              />
            </div>
          </div>

          {/* Additional Information */}
          <div className="mt-12 text-center">
            <div className="max-w-2xl mx-auto">
              <h2 className="text-title mb-4 text-foreground">
                Interested in Learning More?
              </h2>
              <p className="text-body text-muted-foreground mb-8">
                This demo showcases WEGA's capabilities in transforming
                enterprise software development. Contact us to see how our
                AI-powered platform can revolutionize your organization's
                workflows.
              </p>
              <Button
                size="lg"
                className="bg-[#351A55] hover:bg-[#2a1444] text-white px-8 py-3"
              >
                Request Demo
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
