import { Database, Loader2, RefreshCw, Server, Settings2 } from "lucide-react";

import { AppSelect } from "@/components/app-select";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import type { ConfigSummary, ConnectionState } from "@/types";

export function SettingsDrawer({
  apiBase,
  connection,
  connectionLabel,
  config,
  language,
  permissionMode,
  planMode,
  onApiBaseChange,
  onCheckConnection,
  onLanguageChange,
  onPermissionModeChange,
  onPlanModeChange,
  onClose
}: {
  apiBase: string;
  connection: ConnectionState;
  connectionLabel: string;
  config: ConfigSummary | null;
  language: string;
  permissionMode: string;
  planMode: boolean;
  onApiBaseChange: (value: string) => void;
  onCheckConnection: () => void;
  onLanguageChange: (value: string) => void;
  onPermissionModeChange: (value: string) => void;
  onPlanModeChange: (value: boolean) => void;
  onClose: () => void;
}) {
  return (
    <Sheet open onOpenChange={(open) => {
      if (!open) onClose();
    }}>
      <SheetContent className="settingsDrawer" side="right" showCloseButton={false} aria-label="设置">
        <SheetHeader className="settingsHeader">
          <div>
            <p className="eyebrow">
              <Settings2 size={14} />
              控制台
            </p>
            <SheetTitle>设置</SheetTitle>
          </div>
        </SheetHeader>

        <section className="settingsSection">
          <div className="panelTitle">
            <Server size={16} />
            <span>服务连接</span>
          </div>
          <label>
            API 地址
            <Input value={apiBase} onChange={(event) => onApiBaseChange(event.target.value)} placeholder="同源代理或 http://localhost:8000" />
          </label>
          <Button className="secondaryButton" variant="outline" onClick={onCheckConnection} type="button">
            {connection === "checking" ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
            {connectionLabel}
          </Button>
        </section>

        <section className="settingsSection">
          <div className="panelTitle">
            <Settings2 size={16} />
            <span>高级参数</span>
          </div>
          <div className="twoCols">
            <label>
              语言
              <AppSelect
                value={language}
                onChange={onLanguageChange}
                options={[
                  { value: "zh", label: "中文" },
                  { value: "en", label: "English" }
                ]}
              />
            </label>
            <label>
              权限
              <AppSelect
                value={permissionMode}
                onChange={onPermissionModeChange}
                options={[
                  { value: "normal", label: "normal" },
                  { value: "auto", label: "auto" },
                  { value: "dangerous", label: "dangerous" }
                ]}
              />
            </label>
          </div>
          <Label className="checkRow">
            <Checkbox checked={planMode} onCheckedChange={(checked) => onPlanModeChange(!!checked)} />
            Plan mode
          </Label>
        </section>

        <section className="settingsSection summaryPanel">
          <div className="panelTitle">
            <Database size={16} />
            <span>当前配置</span>
          </div>
          <dl>
            <dt>模型</dt>
            <dd>{config?.target || "-"}</dd>
            <dt>数据源</dt>
            <dd>{config?.current_datasource || "-"}</dd>
            <dt>Home</dt>
            <dd title={config?.home}>{config?.home || "-"}</dd>
          </dl>
        </section>
      </SheetContent>
    </Sheet>
  );
}
