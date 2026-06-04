import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { SelectOption } from "@/types";

const emptySelectValue = "__datus_empty__";

function toSelectValue(value: string) {
  return value || emptySelectValue;
}

function fromSelectValue(value: string) {
  return value === emptySelectValue ? "" : value;
}

export function AppSelect({
  value,
  onChange,
  options,
  disabled,
  placeholder = "请选择"
}: {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  disabled?: boolean;
  placeholder?: string;
}) {
  return (
    <Select value={toSelectValue(value)} onValueChange={(next) => onChange(fromSelectValue(next))} disabled={disabled}>
      <SelectTrigger className="appSelectTrigger" aria-label={placeholder}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent className="appSelectContent" position="popper" sideOffset={6}>
        {options.map((option) => (
          <SelectItem className="appSelectItem" key={`${option.value}-${option.label}`} value={toSelectValue(option.value)}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
