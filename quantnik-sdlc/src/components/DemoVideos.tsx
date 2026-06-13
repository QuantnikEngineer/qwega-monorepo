import { ArrowLeft, ExternalLink } from "lucide-react";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import thumbnailImage from "figma:asset/e3fe725b6d9415cbec27ac8bcfc3e0757a86c732.png";

interface DemoVideosProps {
  onBack: () => void;
  isDarkMode?: boolean;
  onNavigateToVideo: (videoTitle: string, videoUrl: string) => void;
}

interface VideoItem {
  id: string;
  title: string;
  description: string;
  thumbnail: string;
  videoUrl: string;
}

// Uniform thumbnail for all videos using the provided coding image
const uniformThumbnail = thumbnailImage;

const demoVideos: VideoItem[] = [
  {
    id: "user-story-generation-2",
    title: "QUANTNIK Demo Video",
    description:
      "Experience how AI converts requirements into user stories, post on ADO board, automates CI/CD, generates code based on ADO work items, and delivers a live portal, end-to-end.",
    thumbnail: uniformThumbnail,
    videoUrl:
      "https://wipro365.sharepoint.com/:v:/r/sites/BuildIQ/Shared%20Documents/General%20Stuff/Videos/BuildAI%20Videos/BuildIQFoundry-Full%20Demo.mp4?csf=1&web=1&e=ZZSU7V&nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJTdHJlYW1XZWJBcHAiLCJyZWZlcnJhbFZpZXciOiJTaGFyZURpYWxvZy1MaW5rIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXcifX0%3D",
  },
  {
    id: "quantnik-ai-agents",
    title: "QUANTNIK-AI Agents",
    description:
      "Experience the power of AI-driven development agents that automate code generation, testing, and deployment processes while maintaining enterprise-grade security and compliance standards.",
    thumbnail: uniformThumbnail,
    videoUrl:
      "https://wipro365.sharepoint.com/:v:/s/TriangularOffering-Wipro-Harness-GCP/ESu7tXniHaxAiGBYf1kppi4B52jd3wEW7Cy7X-Qbz-hCUA?email=vishnuprasad.jahagirdar%40wipro.com&e=MeEHmR",
  },
  {
    id: "quantnik-cicd",
    title: "QUANTNIK CI/CD",
    description:
      "Streamline your continuous integration and deployment pipelines with intelligent automation, real-time monitoring, and seamless integration across multi-cloud environments.",
    thumbnail: uniformThumbnail,
    videoUrl:
      "https://wipro365.sharepoint.com/:v:/s/TriangularOffering-Wipro-Harness-GCP/EdTQ327YBe5KrcUZzpmw7PQB1XCDDZwrgjH7zR62MgD5Rw?email=vishnuprasad.jahagirdar%40wipro.com&e=cuB3s4",
  },
  {
    id: "quantnik-intro-short",
    title: "QUANTNIK Intro - Short",
    description:
      "Get a quick overview of QUANTNIK platform capabilities and see how it revolutionizes enterprise software development with integrated AI-powered tools and automated workflows.",
    thumbnail: uniformThumbnail,
    videoUrl:
      "https://wipro365.sharepoint.com/:v:/r/sites/BuildIQ/Shared%20Documents/General%20Stuff/Videos/BuildAI%20Videos/BuildIQ%20Intro.mp4?csf=1&web=1&e=74P1lr",
  },
  {
    id: "quantnik-intro-long",
    title: "QUANTNIK Intro - Long",
    description:
      "Dive deep into the comprehensive QUANTNIK ecosystem, exploring advanced features, enterprise integrations, and real-world implementation scenarios that drive digital transformation.",
    thumbnail: uniformThumbnail,
    videoUrl:
      "https://wipro365.sharepoint.com/:v:/s/TriangularOffering-Wipro-Harness-GCP/EdYAlJWX765Ft4uBtG-ljRMBejqne_khCaAcoGG9_UMdbQ?email=vishnuprasad.jahagirdar%40wipro.com&e=1J1HiU",
  },
  {
    id: "harness-idp",
    title: "Harness - IDP",
    description:
      "Explore the Internal Developer Platform that empowers teams with self-service capabilities, standardized workflows, and reduced cognitive load for faster, more reliable software delivery.",
    thumbnail: uniformThumbnail,
    videoUrl:
      "https://wipro365.sharepoint.com/:v:/s/TriangularOffering-Wipro-Harness-GCP/EWE9ARraGDJJuaQcDm0L9u8Bwgdw6RzK-lxZJxRlyCB0PA?email=vishnuprasad.jahagirdar%40wipro.com&e=tHogcf",
  },
  {
    id: "harness-ai-pipeline",
    title: "Harness AI Pipeline",
    description:
      "Witness how AI-enhanced pipelines optimize deployment strategies, predict potential issues, and automatically remediate problems to ensure continuous service reliability.",
    thumbnail: uniformThumbnail,
    videoUrl:
      "https://wipro365.sharepoint.com/:v:/s/TriangularOffering-Wipro-Harness-GCP/EUBQiax_dJFOk6JLnFHv4OYB4LTe9lCFA8I58P7hk_ctpg?email=vishnuprasad.jahagirdar%40wipro.com&e=uiVLWH",
  },
  {
    id: "user-story-generation",
    title: "User Story Generation",
    description:
      "See how AI transforms requirements into detailed user stories with acceptance criteria, streamlining agile development processes and improving project planning accuracy.",
    thumbnail: uniformThumbnail,
    videoUrl:
      "https://wipro365.sharepoint.com/:v:/s/TriangularOffering-Wipro-Harness-GCP/EWCKcYGStMtDiUtwdt1dIWUBgJo38-5b6nPukQijwGuYHw?email=vishnuprasad.jahagirdar%40wipro.com&e=xA9ADI",
  },
  {
    id: "devops-sei",
    title: "DevOps SEI",
    description:
      "Discover how Software Engineering Intelligence transforms development workflows with advanced analytics, performance insights, and automated quality assurance to deliver exceptional software faster.",
    thumbnail: uniformThumbnail,
    videoUrl:
      "https://wipro365.sharepoint.com/:v:/s/TriangularOffering-Wipro-Harness-GCP/ERw-cQ6KEzNAp4xDTze4QV4BpnebFah8BHwmt474mQOhLQ?email=vishnuprasad.jahagirdar%40wipro.com&e=CsLssJ",
  },
];

export function DemoVideos({
  onBack,
  isDarkMode,
  onNavigateToVideo,
}: DemoVideosProps) {
  const handleExploreVideo = (videoTitle: string, videoUrl: string) => {
    onNavigateToVideo(videoTitle, videoUrl);
  };

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
              Back to Home
            </Button>

            {/* Hero Content */}
            <div className="text-center text-white">
              <h1 className="text-display mb-6">Demo Videos</h1>
              <p className="text-body-large max-w-3xl mx-auto text-white/90">
                Explore QUANTNIK platform capabilities through
                comprehensive demos showcasing enterprise-grade
                software engineering solutions powered by AI
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Videos Grid */}
      <div className="px-6 py-16">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {demoVideos.map((video) => (
              <Card
                key={video.id}
                className="group overflow-hidden hover:shadow-lg transition-all duration-300 border-border"
              >
                <div className="relative overflow-hidden">
                  {/* Thumbnail */}
                  <div className="aspect-video relative bg-muted">
                    <img
                      src={video.thumbnail}
                      alt={video.title}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  </div>
                </div>

                <CardContent className="p-6">
                  {/* Title */}
                  <h3 className="text-subtitle mb-3 text-foreground">
                    {video.title}
                  </h3>

                  {/* Description */}
                  <p className="text-body-small text-muted-foreground mb-6 line-clamp-4">
                    {video.description}
                  </p>

                  {/* Explore Button */}
                  <Button
                    onClick={() =>
                      handleExploreVideo(video.title, video.videoUrl)
                    }
                    className="w-full bg-[#351A55] hover:bg-[#2a1444] text-white transition-colors"
                  >
                    <ExternalLink className="w-4 h-4 mr-2" />
                    Explore
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Additional CTA */}
          <div className="text-center mt-16">
            <div className="max-w-2xl mx-auto">
              <h2 className="text-title mb-4 text-foreground">
                Ready to Transform Your Development Process?
              </h2>
              <p className="text-body text-muted-foreground mb-8">
                These demos showcase just a fraction of
                QUANTNIK's capabilities. Contact us to see how
                our enterprise software engineering platform can
                revolutionize your organization's development
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