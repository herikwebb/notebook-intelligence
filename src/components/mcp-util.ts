// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { TranslationBundle } from '@jupyterlab/translation';
import { MCPServerStatus } from '../tokens';

export function mcpServerStatusTitle(
  trans: TranslationBundle,
  status: MCPServerStatus
): string {
  switch (status) {
    case MCPServerStatus.FailedToUpdateToolList:
      return trans.__('Tool refresh failed. Reload MCP servers to retry.');
    case MCPServerStatus.FailedToUpdatePromptList:
      return trans.__('Prompt refresh failed. Reload MCP servers to retry.');
    case MCPServerStatus.FailedToConnect:
      return trans.__('Connection failed. Reload MCP servers to retry.');
    case MCPServerStatus.NotConnected:
      return trans._p('MCP server status', 'not connected');
    case MCPServerStatus.Connecting:
      return trans._p('MCP server status', 'connecting');
    case MCPServerStatus.Disconnecting:
      return trans._p('MCP server status', 'disconnecting');
    case MCPServerStatus.Connected:
      return trans._p('MCP server status', 'connected');
    case MCPServerStatus.UpdatingToolList:
      return trans._p('MCP server status', 'updating tool list');
    case MCPServerStatus.UpdatedToolList:
      return trans._p('MCP server status', 'updated tool list');
    case MCPServerStatus.UpdatingPromptList:
      return trans._p('MCP server status', 'updating prompt list');
    case MCPServerStatus.UpdatedPromptList:
      return trans._p('MCP server status', 'updated prompt list');
    default: {
      // A status this build does not know yet, shown as the server sent it.
      const unknownStatus: never = status;
      return unknownStatus;
    }
  }
}

export function mcpServerSettingsToEnabledState(
  mcpServers: any,
  mcpServerSettings: any
) {
  const mcpServerEnabledState = new Map<string, Set<string>>();
  for (const server of mcpServers) {
    const mcpServerToolEnabledState = mcpServerSettingsToServerToolEnabledState(
      mcpServers,
      mcpServerSettings,
      server.id
    );
    if (mcpServerToolEnabledState) {
      mcpServerEnabledState.set(server.id, mcpServerToolEnabledState);
    }
  }

  return mcpServerEnabledState;
}

export function mcpServerSettingsToServerToolEnabledState(
  mcpServers: any,
  mcpServerSettings: any,
  serverId: string
) {
  const server = mcpServers.find((server: any) => server.id === serverId);

  let mcpServerToolEnabledState: Set<string> | null = null;

  if (!server) {
    return mcpServerToolEnabledState;
  }

  if (mcpServerSettings[server.id]) {
    const serverSettings = mcpServerSettings[server.id];
    if (!serverSettings.disabled) {
      mcpServerToolEnabledState = new Set<string>();
      for (const tool of server.tools) {
        if (!serverSettings.disabled_tools?.includes(tool.name)) {
          mcpServerToolEnabledState.add(tool.name);
        }
      }
    }
  } else {
    mcpServerToolEnabledState = new Set<string>();
    for (const tool of server.tools) {
      mcpServerToolEnabledState.add(tool.name);
    }
  }

  return mcpServerToolEnabledState;
}
