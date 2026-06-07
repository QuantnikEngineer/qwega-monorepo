// llmConfig.ts
// Central config for LLM providers and models
export const PROVIDERS = [
  { key: "aws_bedrock", label: "AWS Bedrock", default: true },
];

export const LLM_MODELS = [
  // AWS Bedrock models
  { key: "anthropic.claude-3-7-sonnet-20250219-v1:0", label: "Claude 3.7 Sonnet", provider: "aws_bedrock", default: true },
  { key: "amazon.nova-pro-v1:0", label: "Amazon Nova Pro", provider: "aws_bedrock", default: false },
];