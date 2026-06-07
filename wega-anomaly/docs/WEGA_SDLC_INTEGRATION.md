# WEGA-SDLC Integration Guide

**Platform:** Ubuntu 22.04 LTS (AWS EC2)  
**Last Updated:** 2026-04-29

This document lists all changes required in the `wega-sdlc` frontend to integrate the Anomaly Agent with Dashboard + Chatbot UI.

---

## Summary of Required Changes

| File/Folder | Action | Description |
|-------------|--------|-------------|
| `src/services/anomalyAgentApi.ts` | **CREATE** | API client for Anomaly Agent |
| `src/components/AnomalyAgent/` | **CREATE** | New component folder |
| `src/components/AnomalyAgent/AnomalyDashboard.tsx` | **CREATE** | Dashboard component |
| `src/components/AnomalyAgent/AnomalyChatbot.tsx` | **CREATE** | Chatbot component |
| `src/components/AnomalyAgent/index.ts` | **CREATE** | Export barrel |
| `src/App.tsx` | **MODIFY** | Add route for Anomaly Agent |
| `src/components/Header.tsx` | **MODIFY** | Add navigation link |
| `.env` and `.env.example` | **MODIFY** | Add Anomaly Agent URL |

---

## Quick Setup Commands (Ubuntu)

```bash
cd ~/wega-projects/wega-sdlc

# 1. Create the API service
cat > src/services/anomalyAgentApi.ts << 'EOF'
# (Content provided in Section 1 below)
EOF

# 2. Create component folder
mkdir -p src/components/AnomalyAgent

# 3. Create components
cat > src/components/AnomalyAgent/AnomalyDashboard.tsx << 'EOF'
# (Content provided in Section 2 below)
EOF

cat > src/components/AnomalyAgent/AnomalyChatbot.tsx << 'EOF'
# (Content provided in Section 3 below)
EOF

cat > src/components/AnomalyAgent/index.ts << 'EOF'
export { AnomalyDashboard } from './AnomalyDashboard';
export { AnomalyChatbot } from './AnomalyChatbot';
EOF

# 4. Update environment
echo "VITE_ANOMALY_AGENT_URL=http://localhost:8080" >> .env
echo "VITE_ANOMALY_AGENT_URL=http://localhost:8080" >> .env.example

# 5. Manual edits required for App.tsx and Header.tsx (see sections below)
```

---

## 1. Create API Service

**File:** `src/services/anomalyAgentApi.ts`

```typescript
/**
 * Anomaly Agent API Client
 * Communicates with the WEGA Anomaly Agent container
 */

import { apiFetch } from './apiClient';

const ANOMALY_AGENT_URL = import.meta.env.VITE_ANOMALY_AGENT_URL || '/anomaly-agent';

// ==================== TYPES ====================

export interface KubernetesAction {
  action_type: 'scale_up' | 'scale_down' | 'restart' | 'rollback' | 'none';
  target_replicas: number | null;
  rationale: string;
}

export interface AnalyzeResponse {
  request_id: string;
  confidence_score: number;
  pipeline_decision: 'PROCEED_AUTOMATION' | 'HUMAN_REVIEW' | 'MONITORING_ONLY' | 'TRANSIENT_RESOLVED';
  automation_approved: boolean;
  recommended_action: KubernetesAction;
  root_cause_analysis: string;
  executive_summary: string;
  risk_assessment: string;
  transient_resolved: boolean;
  original_alert_value: number | null;
  current_value_after_wait: number | null;
  analysis_timestamp: string;
  ai_provider: string;
  ai_model: string;
  latency_ms: number;
}

export interface RemediateRequest {
  action: 'scale_up' | 'scale_down' | 'restart' | 'rollback' | 'none';
  target_replicas?: number;
  deployment: string;
  namespace: string;
  request_id?: string;
  force?: boolean;
}

export interface RemediateResponse {
  request_id: string;
  status: 'pending' | 'in_progress' | 'success' | 'failed' | 'skipped';
  action_performed: string;
  previous_replicas: number | null;
  new_replicas: number | null;
  message: string;
  execution_time_ms: number;
  timestamp: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface ChatResponse {
  conversation_id: string;
  response: string;
  suggested_actions: string[];
  references: Array<{ title: string; url: string }>;
  timestamp: string;
}

export interface AlertHistoryItem {
  alert_id: string;
  title: string;
  timestamp: string;
  severity: string;
  decision: string;
  remediation_status: string;
  confidence_score: number;
}

export interface SystemStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  uptime_seconds: number;
  last_alert_time: string | null;
  total_alerts_processed: number;
  total_remediations: number;
  ai_provider: string;
  ai_provider_healthy: boolean;
  monitoring_adapter: string;
  monitoring_adapter_healthy: boolean;
}

export interface StatusResponse {
  system: SystemStatus;
  recent_alerts: AlertHistoryItem[];
  configuration: Record<string, unknown>;
}

// ==================== API FUNCTIONS ====================

export async function analyzeAlert(alertPayload: Record<string, unknown>): Promise<AnalyzeResponse> {
  const response = await apiFetch(`${ANOMALY_AGENT_URL}/api/v1/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alert_payload: alertPayload }),
  });
  
  if (!response.ok) {
    throw new Error(`Analysis failed: ${response.statusText}`);
  }
  
  return response.json();
}

export async function executeRemediation(request: RemediateRequest): Promise<RemediateResponse> {
  const response = await apiFetch(`${ANOMALY_AGENT_URL}/api/v1/remediate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    throw new Error(`Remediation failed: ${response.statusText}`);
  }
  
  return response.json();
}

export async function sendChatMessage(
  message: string,
  conversationId?: string
): Promise<ChatResponse> {
  const response = await apiFetch(`${ANOMALY_AGENT_URL}/api/v1/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
    }),
  });
  
  if (!response.ok) {
    throw new Error(`Chat failed: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getAnomalyStatus(): Promise<StatusResponse> {
  const response = await apiFetch(`${ANOMALY_AGENT_URL}/api/v1/status`);
  
  if (!response.ok) {
    throw new Error(`Status check failed: ${response.statusText}`);
  }
  
  return response.json();
}

export async function healthCheck(): Promise<{ status: string; components: Record<string, boolean> }> {
  const response = await apiFetch(`${ANOMALY_AGENT_URL}/health`);
  
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.statusText}`);
  }
  
  return response.json();
}
```

---

## 2. Create AnomalyDashboard Component

**File:** `src/components/AnomalyAgent/AnomalyDashboard.tsx`

See the complete code in `IMPLEMENTATION_GUIDE.md` Section 9.4.

**Key Features:**
- System status card with health indicator
- Metrics overview (alerts processed, remediations, success rate)
- Recent alerts table with severity and decision badges
- Configuration display panel
- Chatbot toggle button

**Dependencies used:**
- `@tanstack/react-query` for data fetching
- UI components from `../ui/` (Card, Table, Badge, Button)
- `lucide-react` for icons

---

## 3. Create AnomalyChatbot Component

**File:** `src/components/AnomalyAgent/AnomalyChatbot.tsx`

See the complete code in `IMPLEMENTATION_GUIDE.md` Section 9.5.

**Key Features:**
- Sliding panel chat interface
- Message history with user/assistant bubbles
- Suggested actions as quick-reply buttons
- Loading state during AI response
- Conversation persistence via conversation_id

---

## 4. Create Index Export

**File:** `src/components/AnomalyAgent/index.ts`

```typescript
export { AnomalyDashboard } from './AnomalyDashboard';
export { AnomalyChatbot } from './AnomalyChatbot';
```

---

## 5. Modify App.tsx

**File:** `src/App.tsx`

### Changes Required:

**1. Add import** (near the top with other imports):
```typescript
import { AnomalyDashboard, AnomalyChatbot } from './components/AnomalyAgent';
```

**2. Add state** (inside AppContent function, with other useState):
```typescript
const [isAnomalyChatbotOpen, setIsAnomalyChatbotOpen] = useState(false);
```

**3. Add navigation function** (with other navigate functions):
```typescript
const navigateToAnomalyAgent = () => {
  navigate('/anomaly-agent');
  window.scrollTo(0, 0);
};
```

**4. Add route** (inside `<Routes>`, after other routes):
```typescript
<Route
  path="/anomaly-agent"
  element={withAuthGuard(
    <>
      <AnomalyDashboard 
        isDarkMode={isDarkMode}
        onOpenChatbot={() => setIsAnomalyChatbotOpen(true)}
        onBack={navigateToDashboard}
      />
      <AnomalyChatbot
        isDarkMode={isDarkMode}
        isOpen={isAnomalyChatbotOpen}
        onClose={() => setIsAnomalyChatbotOpen(false)}
      />
    </>,
    { requiredCapability: 'sdlc:execute' }
  )}
/>
```

**5. Update Header props**:
```typescript
<Header 
  // ... existing props
  onNavigateToAnomalyAgent={navigateToAnomalyAgent}
/>
```

---

## 6. Modify Header.tsx

**File:** `src/components/Header.tsx`

### Changes Required:

**1. Add to interface**:
```typescript
interface HeaderProps {
  // ... existing props
  onNavigateToAnomalyAgent?: () => void;
}
```

**2. Add to function parameters**:
```typescript
export function Header({ 
  // ... existing params
  onNavigateToAnomalyAgent 
}: HeaderProps) {
```

**3. Add menu item** (in navigation section):
```typescript
<button 
  onClick={onNavigateToAnomalyAgent}
  className="text-sm font-medium hover:text-primary"
>
  Anomaly Agent
</button>
```

---

## 7. Update Environment Variables

**Files:** `.env` and `.env.example`

```bash
# Add to both files:
VITE_ANOMALY_AGENT_URL=http://localhost:8080
```

For production, update to the actual Anomaly Agent URL:
```bash
VITE_ANOMALY_AGENT_URL=https://anomaly-agent.your-domain.com
```

---

## 8. API Gateway Configuration (If Applicable)

If using the gateway pattern (per `apiClient.ts`), update the route resolution:

**Option A: Add route to gateway**
```typescript
// In gateway configuration:
'/anomaly-agent': 'http://wega-anomaly-agent.wega-system.svc.cluster.local'
```

**Option B: Update resolveGatewayUrl in apiClient.ts**
```typescript
const isGatewayRoute = /^\/(api|auth|health|anomaly-agent)\b/.test(normalized)
```

---

## 9. Component Folder Structure

```
src/components/AnomalyAgent/
├── index.ts                    # Export barrel
├── AnomalyDashboard.tsx        # Main dashboard
├── AnomalyChatbot.tsx          # Chat interface
└── (optional future components)
    ├── StatusCard.tsx          # System status display
    ├── AlertsTable.tsx         # Recent alerts table
    ├── MetricsOverview.tsx     # Charts/metrics
    └── ConfigurationPanel.tsx  # Settings display
```

---

## 10. Testing the Integration

```bash
# 1. Start the Anomaly Agent backend (or port-forward from K8s)
kubectl port-forward svc/wega-anomaly-agent -n wega-system 8080:80 &

# 2. Start the frontend
cd ~/wega-projects/wega-sdlc
npm run dev

# 3. Open browser
# Navigate to http://localhost:5173/anomaly-agent

# 4. Verify:
#    - Dashboard loads without errors
#    - Status cards show data
#    - Chatbot opens and responds
```

---

## 11. Developer Checklist

- [ ] Create `src/services/anomalyAgentApi.ts`
- [ ] Create `src/components/AnomalyAgent/` folder
- [ ] Create `AnomalyDashboard.tsx`
- [ ] Create `AnomalyChatbot.tsx`
- [ ] Create `index.ts` barrel export
- [ ] Modify `App.tsx` - add import, state, route
- [ ] Modify `Header.tsx` - add prop and menu item
- [ ] Update `.env` with `VITE_ANOMALY_AGENT_URL`
- [ ] Update `.env.example` with `VITE_ANOMALY_AGENT_URL`
- [ ] Test integration with running Anomaly Agent
- [ ] Commit and push changes

---

## 12. Design Reference

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ANOMALY AGENT                               │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐ │
│  │ System       │  │ Alerts       │  │ Remediations │  │ Success │ │
│  │ HEALTHY      │  │     42       │  │      15      │  │  96%    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  RECENT ALERTS                                    [Open Chatbot]    │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Alert Title          │ Severity │ Decision  │ Status   │ Time  ││
│  ├─────────────────────────────────────────────────────────────────┤│
│  │ CPU High - pod-xyz   │ CRITICAL │ AUTO      │ SUCCESS  │ 5m    ││
│  │ Memory Alert - svc-a │ HIGH     │ REVIEW    │ PENDING  │ 15m   ││
│  │ Transient Spike      │ MEDIUM   │ RESOLVED  │ SKIPPED  │ 1h    ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  CONFIGURATION                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Monitoring: Datadog  │ AI: Gemini  │ Auto-threshold: 80%       ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### Chatbot Panel

```
┌─────────────────────────────────┐
│ Anomaly Agent Chat          [X] │
├─────────────────────────────────┤
│                                 │
│ [User]: What's the current      │
│ system status?                  │
│                                 │
│ [Agent]: The system is healthy. │
│ 42 alerts processed today with  │
│ 15 auto-remediations at 96%     │
│ success rate.                   │
│                                 │
│ Suggested:                      │
│ [View alerts] [Check config]    │
│                                 │
├─────────────────────────────────┤
│ Type your message...     [Send] │
└─────────────────────────────────┘
```

---

**End of Document**
