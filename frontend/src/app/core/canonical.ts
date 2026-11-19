export interface TemplateField {
  code: string;
  label: string;
  name_es?: string;
  type: 'number'|'string'|'text'|'boolean';
  unit: string;
  required?: boolean;
  min?: number;
  max?: number;
  enum?: (string|number|boolean)[];
  display_group?: string;
}
export interface SubsystemTemplate {
  code: string;
  subsystem_id: string;
  version: number;
  fields: TemplateField[];
}
export interface CanonicalValue {
  value: string|number|boolean|null;
  unit: string;
  source_type: 'SOURCE_DECLARED'|'DEMO_SIMULATED'|'CALCULATED'|'MISSING';
  status: string;
}
export interface CanonicalSolution {
  schema_version: string;
  template: SubsystemTemplate;
  functional_unit: string|null;
  properties: Record<string, CanonicalValue>;
}

export interface TemplateHighlight extends CanonicalValue {label:string}
