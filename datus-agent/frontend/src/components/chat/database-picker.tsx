import { ChevronDown, Database } from "lucide-react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { schemaOptionsForDatabase } from "@/lib/chat";
import type { CatalogRecord, SelectOption } from "@/types";

export function DatabasePicker({
  open,
  onOpenChange,
  disabled,
  selectedLabel,
  database,
  schema,
  databaseOptions,
  catalogEntries,
  expandedDatabases,
  onSelect,
  onToggleDatabase
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  disabled?: boolean;
  selectedLabel: string;
  database: string;
  schema: string;
  databaseOptions: SelectOption[];
  catalogEntries: CatalogRecord[];
  expandedDatabases: Set<string>;
  onSelect: (databaseName: string, schemaName: string, closePicker?: boolean) => void;
  onToggleDatabase: (databaseName: string) => void;
}) {
  return (
    <div className="quickField dbPickerField">
      <span className="controlIcon" title="数据库 / Schema" aria-hidden="true">
        <Database size={13} />
      </span>
      <Popover open={open} onOpenChange={onOpenChange}>
        <PopoverTrigger asChild>
          <button
            className={`dbPickerButton ${open ? "open" : ""}`}
            type="button"
            disabled={disabled}
            title={selectedLabel}
            aria-label={`选择数据库和 Schema，当前为 ${selectedLabel}`}
          >
            <span>{selectedLabel}</span>
            <ChevronDown size={14} />
          </button>
        </PopoverTrigger>
        <PopoverContent className="dbPickerMenu" align="end" side="top" sideOffset={8}>
          <button className={`dbPickerNone ${!database ? "selected" : ""}`} type="button" onClick={() => onSelect("", "")}>
            不指定
          </button>
          {database && !databaseOptions.some((option) => option.value === database) && (
            <div className="dbPickerGroup">
              <button className="dbPickerDatabase selected" type="button" onClick={() => onToggleDatabase(database)}>
                <span>{database}</span>
                <ChevronDown className={expandedDatabases.has(database) ? "expanded" : ""} size={14} />
              </button>
              {expandedDatabases.has(database) && (
                <div className="dbPickerSchemas">
                  <button className={!schema ? "selected" : ""} type="button" onClick={() => onSelect(database, "")}>
                    不指定 schema
                  </button>
                  {schema && (
                    <button className="selected" type="button" onClick={() => onSelect(database, schema)}>
                      {schema}
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
          {databaseOptions.map((option) => {
            const schemas = schemaOptionsForDatabase(catalogEntries, option.value);
            const isExpanded = expandedDatabases.has(option.value);
            const isSelectedDatabase = database === option.value;
            return (
              <div className="dbPickerGroup" key={option.value}>
                <button
                  className={`dbPickerDatabase ${isSelectedDatabase ? "selected" : ""}`}
                  type="button"
                  onClick={() => onToggleDatabase(option.value)}
                >
                  <span>{option.label}</span>
                  <ChevronDown className={isExpanded ? "expanded" : ""} size={14} />
                </button>
                {isExpanded && (
                  <div className="dbPickerSchemas">
                    <button
                      className={isSelectedDatabase && !schema ? "selected" : ""}
                      type="button"
                      onClick={() => onSelect(option.value, "")}
                    >
                      不指定 schema
                    </button>
                    {schemas.map((schemaOption) => (
                      <button
                        className={isSelectedDatabase && schema === schemaOption.value ? "selected" : ""}
                        key={`${option.value}-${schemaOption.value}`}
                        type="button"
                        onClick={() => onSelect(option.value, schemaOption.value)}
                      >
                        {schemaOption.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </PopoverContent>
      </Popover>
    </div>
  );
}
