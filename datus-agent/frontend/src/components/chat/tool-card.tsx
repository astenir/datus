import { CheckCircle2, ChevronDown, TerminalSquare, XCircle } from "lucide-react";

import { stringifyContent } from "@/lib/chat";
import { displayValueForTool, sqlFromToolValue, sqlKeys, summarizeValue, tableFromToolValue, toolResultStatus } from "@/lib/tool-display";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

export function ToolCard({
  mode,
  toolName,
  value,
  duration,
  shortDesc
}: {
  mode: "call" | "result";
  toolName: string;
  value: unknown;
  duration?: number;
  shortDesc?: string;
}) {
  const payload = stringifyContent(value);
  const displayValue = displayValueForTool(mode, value);
  const displayPayload = stringifyContent(displayValue);
  const hasValue = displayValue !== undefined && displayValue !== null && displayPayload !== "";
  const payloadLabel = mode === "call" ? "参数" : "返回";
  const resultStatus = mode === "result" ? toolResultStatus(value) : "unknown";
  const statusLabel = mode === "call" ? "Tool call" : resultStatus === "error" ? "Tool result failed" : "Tool result";
  const sqlText = sqlFromToolValue(displayValue);
  const table = tableFromToolValue(displayValue, { omitKeys: sqlText ? sqlKeys : undefined });
  const valueKind = table?.sourceLabel ?? summarizeValue(displayValue);

  return (
    <Collapsible defaultOpen={mode === "result"} className={`toolCard ${mode} ${mode === "result" ? resultStatus : ""}`}>
      <CollapsibleTrigger asChild>
        <div className="toolHeader" role="button" tabIndex={0}>
          <span className="toolChevron" aria-hidden="true">
            <ChevronDown size={16} />
          </span>
          <span className="toolStatusIcon" aria-hidden="true">
            {mode === "call" ? <TerminalSquare size={15} /> : resultStatus === "error" ? <XCircle size={15} /> : <CheckCircle2 size={15} />}
          </span>
          <span className="toolHeading">
            <span className="toolBadge">{statusLabel}</span>
            <span className="toolName">{toolName}</span>
          </span>
          <span className="toolMetaGroup">
            <span className="toolMeta">{valueKind}</span>
            {duration !== undefined && <span className="toolMeta">{duration.toFixed(2)}s</span>}
          </span>
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="toolBody">
          {shortDesc && <div className="toolSummary">{shortDesc}</div>}
          {hasValue ? (
            <>
              {sqlText && (
                <section className="toolSqlBlock" aria-label="SQL 语句">
                  <div className="toolSqlHeader">
                    <span>SQL 语句</span>
                  </div>
                  <pre className="toolSqlCode">{sqlText}</pre>
                </section>
              )}
              {table && (
                <div className="toolTableWrap">
                  <table className="toolTable">
                    <thead>
                      <tr>
                        {table.columns.map((column) => (
                          <th key={column}>{column}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {table.rows.map((row, rowIndex) => (
                        <tr key={rowIndex}>
                          {row.map((cell, cellIndex) => (
                            <td key={`${rowIndex}-${cellIndex}`} title={cell}>
                              {cell}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <details className="toolRawBlock" open={!table}>
                <summary>
                  <span>{table ? `查看原始${payloadLabel}` : payloadLabel}</span>
                  <span>{valueKind}</span>
                </summary>
                <pre className="toolPayload">{table ? payload : displayPayload}</pre>
              </details>
            </>
          ) : (
            <div className="toolEmpty">没有可展示的{payloadLabel}</div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
