import { query } from '@anthropic-ai/claude-agent-sdk';
import fs from 'node:fs';
import { db } from '../db.js';

export async function runTurn({ project, userMessage, onEvent, requestPermission }) {
  const repoPaths = db
    .prepare('SELECT path FROM project_repos WHERE project_id = ?')
    .all(project.id)
    .map((r) => r.path)
    .filter((p) => fs.existsSync(p));

  const iter = query({
    prompt: userMessage,
    options: {
      cwd: project.path,
      model: project.model || 'claude-opus-4-7',
      permissionMode: project.permission_mode || 'bypassPermissions',
      allowDangerouslySkipPermissions: true,
      settingSources: ['user', 'project', 'local'],
      sandbox: { enabled: false },
      additionalDirectories: repoPaths,
      canUseTool: async (toolName, input, opts) => {
        const decision = await requestPermission({
          toolName,
          input,
          title: opts.title,
          displayName: opts.displayName,
          decisionReason: opts.decisionReason,
          blockedPath: opts.blockedPath,
          suggestions: opts.suggestions || [],
        });
        if (decision.decision === 'deny') {
          return { behavior: 'deny', message: decision.message || 'Denied by user' };
        }
        const result = { behavior: 'allow', updatedInput: input };
        if (decision.decision === 'allow_always' && opts.suggestions?.length) {
          result.updatedPermissions = opts.suggestions;
        }
        return result;
      },
      ...(project.last_session_id ? { resume: project.last_session_id } : {}),
    },
  });

  let sessionId = project.last_session_id || null;

  for await (const msg of iter) {
    if (msg.type === 'system' && msg.subtype === 'init') {
      if (msg.session_id) sessionId = msg.session_id;
      onEvent({
        type: 'session',
        sessionId,
        tools: msg.tools || [],
        mcpServers: msg.mcp_servers || [],
        agents: msg.agents || [],
        model: msg.model,
        cwd: msg.cwd,
      });
      continue;
    }

    if (msg.type === 'assistant' && msg.message?.content) {
      for (const block of msg.message.content) {
        if (block.type === 'text') {
          onEvent({ type: 'assistant_text', text: block.text });
        } else if (block.type === 'tool_use') {
          onEvent({ type: 'tool_use', id: block.id, name: block.name, input: block.input });
        }
      }
      continue;
    }

    if (msg.type === 'user' && msg.message?.content) {
      for (const block of msg.message.content) {
        if (block.type === 'tool_result') {
          onEvent({
            type: 'tool_result',
            id: block.tool_use_id,
            content: block.content,
            isError: !!block.is_error,
          });
        }
      }
      continue;
    }

    if (msg.type === 'result') {
      onEvent({
        type: 'result',
        subtype: msg.subtype,
        durationMs: msg.duration_ms,
        totalCostUsd: msg.total_cost_usd,
        usage: msg.usage,
      });
    }
  }

  return { sessionId };
}
