import React from 'react';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from './ui/dialog';
import { ArrowDownRight, Sparkles, CheckCircle } from 'lucide-react';

interface AgentOption {
  name: string;
  description: string;
  icon: any;
  color: string;
}

interface AgentCardProps {
  agent: {
    name: string;
    description: string;
    icon: any;
    color: string;
  };
  index: number;
  hasOptions?: AgentOption[];
  selectedOption?: AgentOption | null;
  onSelectOption?: (option: AgentOption) => void;
  showArrow?: boolean;
}

export function AgentCard({ 
  agent, 
  index, 
  hasOptions, 
  selectedOption, 
  onSelectOption,
  showArrow = false 
}: AgentCardProps) {
  const [isDialogOpen, setIsDialogOpen] = React.useState(false);
  const Icon = selectedOption ? selectedOption.icon : agent.icon;
  const displayAgent = selectedOption || agent;

  const handleSelectOption = (option: AgentOption) => {
    onSelectOption?.(option);
    setIsDialogOpen(false);
  };

  return (
    <>
      <div className="relative">
        {showArrow && (
          <div className="absolute left-8 -top-4 flex flex-col items-center">
            <ArrowDownRight className="w-6 h-6 text-muted-foreground" />
          </div>
        )}
        <div className="flex items-start gap-4 p-4 bg-card border-2 border-border rounded-xl hover:border-primary/50 transition-all hover:shadow-md">
          <div 
            className="w-14 h-14 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ backgroundColor: displayAgent.color }}
          >
            <Icon className="w-7 h-7 text-white" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1">
              <Badge variant="outline" className="bg-primary/10">
                Step {index + 1}
              </Badge>
              <h4 className="font-semibold text-lg text-card-foreground">
                {displayAgent.name}
              </h4>
              {hasOptions && !selectedOption && (
                <Badge variant="secondary" className="bg-yellow-500/10 text-yellow-700 dark:text-yellow-400 border-yellow-500/20">
                  {hasOptions.length} options
                </Badge>
              )}
            </div>
            <p className="text-muted-foreground mb-2">
              {displayAgent.description}
            </p>
            {hasOptions && (
              <Button 
                size="sm" 
                variant="outline"
                onClick={() => setIsDialogOpen(true)}
                className="mt-2"
              >
                <Sparkles className="w-4 h-4 mr-2" />
                {selectedOption ? 'Change Tool' : 'Choose Tool'} ({hasOptions.length} options)
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Options Selection Dialog */}
      {hasOptions && (
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogContent className="max-w-2xl">
            <DialogTitle>Choose AI Agent Tool</DialogTitle>
            <DialogDescription>
              Select which tool you'd like to use for {agent.name}
            </DialogDescription>

            <div className="grid gap-4 mt-6">
              {hasOptions.map((option, idx) => {
                const OptionIcon = option.icon;
                const isSelected = selectedOption?.name === option.name;
                
                return (
                  <button
                    key={idx}
                    onClick={() => handleSelectOption(option)}
                    className={`flex items-start gap-4 p-4 rounded-xl border-2 text-left transition-all ${
                      isSelected
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:border-primary/50 hover:bg-muted/50'
                    }`}
                  >
                    <div 
                      className="w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: option.color }}
                    >
                      <OptionIcon className="w-6 h-6 text-white" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-semibold text-card-foreground">
                          {option.name}
                        </h4>
                        {isSelected && (
                          <CheckCircle className="w-5 h-5 text-primary" />
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {option.description}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}
