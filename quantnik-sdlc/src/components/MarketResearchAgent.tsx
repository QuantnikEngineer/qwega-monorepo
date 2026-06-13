import { useState, useRef } from 'react';
import { ArrowLeft, Send, Bot, Library, Settings, Sparkles, User, Paperclip, X, File, Image as ImageIcon, TrendingUp } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { ScrollArea } from './ui/scroll-area';
import { Separator } from './ui/separator';
import { Badge } from './ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Slider } from './ui/slider';
import { Switch } from './ui/switch';

interface MarketResearchAgentProps {
  onBack: () => void;
  isDarkMode: boolean;
}

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  url: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  files?: UploadedFile[];
}

interface PromptTemplate {
  id: string;
  title: string;
  content: string;
}

export function MarketResearchAgent({ onBack, isDarkMode }: MarketResearchAgentProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Hello! I\'m QUANTNIK\'s Market Research Agent. I can help you analyze markets, identify opportunities, research competitors, understand customer segments, and gather market intelligence. How can I assist you today?',
      timestamp: new Date(),
    },
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [selectedLLM, setSelectedLLM] = useState('gpt-4');
  const [temperature, setTemperature] = useState([0.7]);
  const [maxTokens, setMaxTokens] = useState([2048]);
  const [enableStreaming, setEnableStreaming] = useState(true);
  const [attachedFiles, setAttachedFiles] = useState<UploadedFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const promptTemplates: PromptTemplate[] = [
    {
      id: '1',
      title: 'Market Opportunity Analysis',
      content: 'Analyze the market opportunity for [product/service] in [target market/region]. Include market size, growth trends, and key opportunities.',
    },
    {
      id: '2',
      title: 'Competitive Analysis',
      content: 'Conduct a competitive analysis for [company/product] comparing against [competitors]. Include strengths, weaknesses, market positioning, and differentiators.',
    },
    {
      id: '3',
      title: 'Customer Segmentation',
      content: 'Create customer segments for [product/service] including demographics, psychographics, behaviors, and pain points for each segment.',
    },
    {
      id: '4',
      title: 'Market Trends Research',
      content: 'Research current and emerging trends in the [industry/market] with focus on [specific area]. Include trend drivers, timeline, and impact assessment.',
    },
    {
      id: '5',
      title: 'SWOT Analysis',
      content: 'Perform a SWOT analysis for [company/product] in the context of [market/industry]. Include internal strengths/weaknesses and external opportunities/threats.',
    },
    {
      id: '6',
      title: 'Total Addressable Market (TAM)',
      content: 'Calculate the Total Addressable Market (TAM), Serviceable Addressable Market (SAM), and Serviceable Obtainable Market (SOM) for [product/service].',
    },
    {
      id: '7',
      title: 'Customer Persona Development',
      content: 'Develop detailed customer personas for [product/service] including goals, challenges, buying behavior, decision criteria, and influencing factors.',
    },
    {
      id: '8',
      title: 'Pricing Strategy Research',
      content: 'Research pricing strategies for [product/service] including competitor pricing, value-based pricing, market sensitivity, and optimal price points.',
    },
    {
      id: '9',
      title: 'Market Entry Strategy',
      content: 'Develop a market entry strategy for [product/service] in [new market/region]. Include barriers to entry, go-to-market approach, and success metrics.',
    },
    {
      id: '10',
      title: 'Voice of Customer Analysis',
      content: 'Analyze customer feedback and reviews for [product/category] to identify key themes, pain points, satisfaction drivers, and improvement opportunities.',
    },
    {
      id: '11',
      title: 'Industry Benchmark Report',
      content: 'Create an industry benchmark report for [metric/KPI] in the [industry]. Include industry averages, top performers, and best practices.',
    },
    {
      id: '12',
      title: 'Product-Market Fit Assessment',
      content: 'Assess product-market fit for [product] by analyzing customer adoption, satisfaction, retention, and market demand signals.',
    },
    {
      id: '13',
      title: 'Market Positioning Analysis',
      content: 'Analyze market positioning for [product/brand] including perceptual mapping, competitive positioning, and differentiation strategies.',
    },
    {
      id: '14',
      title: 'Buyer Journey Mapping',
      content: 'Map the buyer journey for [product/service] including awareness, consideration, decision stages, touchpoints, and conversion opportunities.',
    },
    {
      id: '15',
      title: 'Emerging Market Analysis',
      content: 'Analyze emerging markets for [industry/technology] including adoption rates, regulatory environment, key players, and growth projections.',
    },
  ];

  const handleSendMessage = () => {
    if (!inputMessage.trim() && attachedFiles.length === 0) return;

    const newMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputMessage,
      timestamp: new Date(),
      files: attachedFiles.length > 0 ? [...attachedFiles] : undefined,
    };

    setMessages([...messages, newMessage]);
    setInputMessage('');
    setAttachedFiles([]);

    // Simulate AI response
    setTimeout(() => {
      const fileInfo = newMessage.files ? ` I've received ${newMessage.files.length} file(s) for analysis.` : '';
      const responseMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `I've received your market research request.${fileInfo} I'll analyze this using the ${selectedLLM} model with focus on market insights, competitive intelligence, and strategic opportunities. This is a simulated response in the pre-launch version of QUANTNIK.`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, responseMessage]);
    }, 1000);
  };

  const handlePromptSelect = (prompt: PromptTemplate) => {
    setInputMessage(prompt.content);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      const newFiles: UploadedFile[] = Array.from(files).map(file => ({
        id: Date.now().toString(),
        name: file.name,
        size: file.size,
        type: file.type,
        url: URL.createObjectURL(file),
      }));
      setAttachedFiles([...attachedFiles, ...newFiles]);
    }
  };

  const handleRemoveFile = (fileId: string) => {
    setAttachedFiles(attachedFiles.filter(file => file.id !== fileId));
  };

  return (
    <div className="bg-background">
      <div className="max-w-[1800px] mx-auto px-6 py-8 pb-32">
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
        <div className="mb-8">
          <div className="flex items-center space-x-3 mb-3">
            <div className="p-3 rounded-xl bg-gradient-to-br from-[#351A55] to-[#3498B3]">
              <TrendingUp className="w-8 h-8 text-white" />
            </div>
            <div>
              <h1 className="text-foreground mb-1">Market Research Agent</h1>
              <p className="text-muted-foreground">
                Analyze markets, competitors, customers, and identify strategic opportunities
              </p>
            </div>
          </div>
        </div>

        {/* Two Column Layout */}
        <div className="grid grid-cols-12 gap-6" style={{ minHeight: '700px' }}>
          {/* Left Column - Prompt Library Only */}
          <div className="col-span-3">
            <ScrollArea className="h-full pr-4">
              <div className="space-y-6">
                {/* Prompt Library */}
                <Card className="bg-card border border-border p-4">
                  <div className="flex items-center mb-4">
                    <Library className="w-5 h-5 mr-2 text-[#746FA7]" />
                    <h3 className="text-foreground">Prompt Library</h3>
                  </div>

                  <div className="space-y-2">
                    {promptTemplates.map((prompt) => (
                      <div
                        key={prompt.id}
                        onClick={() => handlePromptSelect(prompt)}
                        className="p-3 rounded-lg border border-border hover:border-[#746FA7] cursor-pointer transition-all group"
                      >
                        <p className="text-sm text-foreground group-hover:text-[#746FA7] mb-2">
                          {prompt.title}
                        </p>
                        <p className="text-xs text-muted-foreground line-clamp-2">
                          {prompt.content}
                        </p>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>
            </ScrollArea>
          </div>

          {/* Middle Column - Chat Interface */}
          <div className="col-span-6 flex flex-col">
            <Card className="bg-card border border-border flex-1 flex flex-col">
              {/* Chat Header */}
              <div className="p-4 border-b border-border">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 rounded-lg bg-[#3498B3]/10">
                      <TrendingUp className="w-5 h-5 text-[#3498B3]" />
                    </div>
                    <div>
                      <h3 className="text-foreground">Market Research Agent</h3>
                      <p className="text-xs text-muted-foreground">
                        AI-powered market intelligence
                      </p>
                    </div>
                  </div>
                  <Badge variant="outline" className="border-green-500 text-green-500">
                    Connected
                  </Badge>
                </div>
              </div>

              {/* Messages Area */}
              <ScrollArea className="flex-1 p-4">
                <div className="space-y-4">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${
                        message.role === 'user' ? 'justify-end' : 'justify-start'
                      }`}
                    >
                      <div
                        className={`flex items-start space-x-2 max-w-[80%] ${
                          message.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''
                        }`}
                      >
                        <div
                          className={`p-2 rounded-full ${
                            message.role === 'user'
                              ? 'bg-[#3498B3]/10'
                              : 'bg-[#746FA7]/10'
                          }`}
                        >
                          {message.role === 'user' ? (
                            <User className="w-4 h-4 text-[#3498B3]" />
                          ) : (
                            <TrendingUp className="w-4 h-4 text-[#746FA7]" />
                          )}
                        </div>
                        <div
                          className={`p-3 rounded-lg ${
                            message.role === 'user'
                              ? 'bg-[#3498B3] text-white'
                              : 'bg-muted text-foreground'
                          }`}
                        >
                          {message.content && (
                            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                          )}
                          
                          {/* Display attached files in message */}
                          {message.files && message.files.length > 0 && (
                            <div className={`mt-2 space-y-1 ${message.content ? 'pt-2 border-t' : ''} ${
                              message.role === 'user' ? 'border-white/20' : 'border-border'
                            }`}>
                              {message.files.map((file) => (
                                <div
                                  key={file.id}
                                  className={`flex items-center space-x-2 px-2 py-1.5 rounded ${
                                    message.role === 'user'
                                      ? 'bg-white/10'
                                      : 'bg-background'
                                  }`}
                                >
                                  {file.type.startsWith('image/') ? (
                                    <ImageIcon className="w-3 h-3" />
                                  ) : (
                                    <File className="w-3 h-3" />
                                  )}
                                  <span className="text-xs truncate max-w-[200px]">{file.name}</span>
                                  <span className={`text-xs ${
                                    message.role === 'user' ? 'text-white/60' : 'text-muted-foreground'
                                  }`}>
                                    ({(file.size / 1024).toFixed(1)} KB)
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                          
                          <p
                            className={`text-xs mt-2 ${
                              message.role === 'user'
                                ? 'text-white/70'
                                : 'text-muted-foreground'
                            }`}
                          >
                            {message.timestamp.toLocaleTimeString()}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>

              {/* Input Area */}
              <div className="p-4 border-t border-border">
                {/* Attached Files Preview */}
                {attachedFiles.length > 0 && (
                  <div className="mb-3 flex flex-wrap gap-2">
                    {attachedFiles.map((file) => (
                      <div
                        key={file.id}
                        className="flex items-center space-x-2 bg-muted px-3 py-2 rounded-lg border border-border"
                      >
                        {file.type.startsWith('image/') ? (
                          <ImageIcon className="w-4 h-4 text-[#3498B3]" />
                        ) : (
                          <File className="w-4 h-4 text-[#746FA7]" />
                        )}
                        <span className="text-xs text-foreground max-w-[150px] truncate">
                          {file.name}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          ({(file.size / 1024).toFixed(1)} KB)
                        </span>
                        <button
                          onClick={() => handleRemoveFile(file.id)}
                          className="text-muted-foreground hover:text-destructive"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                
                <div className="flex items-end space-x-2">
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => fileInputRef.current?.click()}
                    className="hover:bg-[#3498B3]/10 hover:border-[#3498B3]"
                  >
                    <Paperclip className="w-4 h-4" />
                  </Button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    className="hidden"
                    onChange={handleFileUpload}
                    accept=".pdf,.doc,.docx,.txt,.csv,.xls,.xlsx,.json,.xml,.png,.jpg,.jpeg,.gif"
                  />
                  <div className="flex-1">
                    <Input
                      placeholder="Type your message... (Press Enter to send, Shift+Enter for new line)"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={handleKeyPress}
                      className="resize-none bg-background"
                    />
                  </div>
                  <Button
                    onClick={handleSendMessage}
                    className="bg-[#3498B3] hover:bg-[#3498B3]/90 text-white"
                    disabled={!inputMessage.trim() && attachedFiles.length === 0}
                  >
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </Card>
          </div>

          {/* Right Column - LLM Settings */}
          <div className="col-span-3 space-y-6">
            <Card className="bg-card border border-border p-4">
              <div className="flex items-center mb-4">
                <Settings className="w-5 h-5 mr-2 text-[#BE266A]" />
                <h3 className="text-foreground">AI Settings</h3>
              </div>

              <div className="space-y-6">
                {/* LLM Selection */}
                <div className="space-y-2">
                  <Label htmlFor="llm-select">Language Model</Label>
                  <Select value={selectedLLM} onValueChange={setSelectedLLM}>
                    <SelectTrigger id="llm-select" className="bg-background">
                      <SelectValue placeholder="Select LLM" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="gpt-4">GPT-4</SelectItem>
                      <SelectItem value="gpt-4-turbo">GPT-4 Turbo</SelectItem>
                      <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
                      <SelectItem value="claude-3-opus">Claude 3 Opus</SelectItem>
                      <SelectItem value="claude-3-sonnet">Claude 3 Sonnet</SelectItem>
                      <SelectItem value="gemini-pro">Gemini Pro</SelectItem>
                      <SelectItem value="llama-2-70b">LLaMA 2 70B</SelectItem>
                      <SelectItem value="mixtral-8x7b">Mixtral 8x7B</SelectItem>
                      <SelectItem value="glm-5">GLM-5</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Currently using {selectedLLM}
                  </p>
                </div>

                <Separator />

                {/* Temperature */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Temperature</Label>
                    <span className="text-sm text-muted-foreground">{temperature[0]}</span>
                  </div>
                  <Slider
                    value={temperature}
                    onValueChange={setTemperature}
                    min={0}
                    max={1}
                    step={0.1}
                    className="w-full"
                  />
                  <p className="text-xs text-muted-foreground">
                    Controls randomness. Lower = focused, Higher = creative
                  </p>
                </div>

                <Separator />

                {/* Max Tokens */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Max Tokens</Label>
                    <span className="text-sm text-muted-foreground">{maxTokens[0]}</span>
                  </div>
                  <Slider
                    value={maxTokens}
                    onValueChange={setMaxTokens}
                    min={256}
                    max={4096}
                    step={256}
                    className="w-full"
                  />
                  <p className="text-xs text-muted-foreground">
                    Maximum length of the response
                  </p>
                </div>

                <Separator />

                {/* Streaming */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Enable Streaming</Label>
                      <p className="text-xs text-muted-foreground mt-1">
                        Stream responses in real-time
                      </p>
                    </div>
                    <Switch
                      checked={enableStreaming}
                      onCheckedChange={setEnableStreaming}
                    />
                  </div>
                </div>

                <Separator />

                {/* Context Window */}
                <div className="space-y-2">
                  <Label>Context Window</Label>
                  <div className="text-sm text-muted-foreground bg-muted p-3 rounded-lg">
                    <div className="flex justify-between mb-1">
                      <span>Messages in context:</span>
                      <span className="text-foreground">{messages.length}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Estimated tokens:</span>
                      <span className="text-foreground">~{messages.length * 150}</span>
                    </div>
                  </div>
                </div>

                <Separator />

                {/* Model Info */}
                <div className="space-y-2">
                  <Label>Model Information</Label>
                  <div className="text-xs text-muted-foreground bg-muted p-3 rounded-lg space-y-1">
                    <div className="flex justify-between">
                      <span>Provider:</span>
                      <span className="text-foreground">OpenAI</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Max Context:</span>
                      <span className="text-foreground">128K tokens</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Training Data:</span>
                      <span className="text-foreground">Up to Apr 2023</span>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
