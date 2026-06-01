import { FormEvent } from "react";
import { Bot, Cpu, ListChecks, Loader2 } from "lucide-react";

import { AppSelect } from "@/components/app-select";
import { DatabasePicker } from "@/components/chat/database-picker";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { CatalogRecord, SelectOption } from "@/types";

export function ChatComposer({
  agentOptions,
  catalogEntries,
  database,
  databaseOptions,
  expandedDatabases,
  isDatabasePickerOpen,
  isLoadingOptions,
  isStreaming,
  message,
  model,
  modelOptions,
  planMode,
  schema,
  selectedAgent,
  selectedDatabaseLabel,
  onDatabasePickerOpenChange,
  onMessageChange,
  onModelChange,
  onPlanModeChange,
  onSelectAgent,
  onSelectDatabaseSchema,
  onSubmit,
  onToggleDatabaseExpansion
}: {
  agentOptions: SelectOption[];
  catalogEntries: CatalogRecord[];
  database: string;
  databaseOptions: SelectOption[];
  expandedDatabases: Set<string>;
  isDatabasePickerOpen: boolean;
  isLoadingOptions: boolean;
  isStreaming: boolean;
  message: string;
  model: string;
  modelOptions: SelectOption[];
  planMode: boolean;
  schema: string;
  selectedAgent: string;
  selectedDatabaseLabel: string;
  onDatabasePickerOpenChange: (open: boolean) => void;
  onMessageChange: (value: string) => void;
  onModelChange: (value: string) => void;
  onPlanModeChange: (value: boolean) => void;
  onSelectAgent: (value: string) => void;
  onSelectDatabaseSchema: (databaseName: string, schemaName: string, closePicker?: boolean) => void;
  onSubmit: () => void;
  onToggleDatabaseExpansion: (databaseName: string) => void;
}) {
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <form className="composer" onSubmit={submit}>
      <Textarea
        value={message}
        onChange={(event) => onMessageChange(event.target.value)}
        placeholder="输入要交给 Datus Agent 处理的问题..."
        rows={2}
        onKeyDown={(event) => {
          if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
            event.preventDefault();
            onSubmit();
          }
        }}
      />
      <div className="quickControls">
        <div className="quickControlsLeft">
          <label aria-label="子 Agent">
            <span className="controlIcon" title="子 Agent" aria-hidden="true">
              <Bot size={13} />
            </span>
            <AppSelect value={selectedAgent} onChange={onSelectAgent} options={agentOptions} placeholder="默认 chat" />
          </label>
          <DatabasePicker
            open={isDatabasePickerOpen}
            onOpenChange={onDatabasePickerOpenChange}
            disabled={isLoadingOptions}
            selectedLabel={selectedDatabaseLabel}
            database={database}
            schema={schema}
            databaseOptions={databaseOptions}
            catalogEntries={catalogEntries}
            expandedDatabases={expandedDatabases}
            onSelect={onSelectDatabaseSchema}
            onToggleDatabase={onToggleDatabaseExpansion}
          />
          <label className="planModeSwitch" htmlFor="plan-mode-switch">
            <ListChecks size={13} />
            <span>规划</span>
            <Switch id="plan-mode-switch" checked={planMode} onCheckedChange={onPlanModeChange} aria-label="规划模式" />
          </label>
        </div>
        <div className="quickControlsRight">
          <label aria-label="模型">
            <span className="controlIcon" title="模型" aria-hidden="true">
              <Cpu size={13} />
            </span>
            <AppSelect value={model} onChange={onModelChange} options={modelOptions} disabled={isLoadingOptions} placeholder="默认模型" />
          </label>
          <Button className="primaryButton" type="submit" aria-label="发送消息" disabled={!message.trim() || isStreaming}>
            {isStreaming ? (
              <Loader2 className="spin" size={17} />
            ) : (
              <svg className="sendSolidIcon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z" />
                <path d="m21.854 2.147-10.94 10.939" />
              </svg>
            )}
            发送
          </Button>
        </div>
      </div>
    </form>
  );
}
