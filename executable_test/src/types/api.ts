/**
 * Core API & Domain Type Definitions for CvSU Document Generator
 */

export interface ScheduleMetadata {
  instructor: string;
  college: string;
  semester_ay: string;
  classes: ScheduleClass[];
}

export interface ScheduleClass {
  course_section: string;
  subject: string;
  schedule_code: string;
  time_days_room: string;
  has_lab: boolean;
  student_count?: number;
  roster_file?: string;
}

export interface ClassValidation {
  course_section: string;
  schedule_code: string;
  subject: string;
  roster_file: string;
  roster_path: string;
  student_count: number;
  status: 'paired' | 'unpaired' | 'missing';
  has_lab: boolean;
}

export interface ClassConfig {
  has_lab: boolean;
  manual_roster_path?: string;
}

export type RosterConfigMap = Record<string, ClassConfig>;

export interface PrefixMetadata {
  name: string;
  dept: string;
  dept_code: string;
  icon: string;
  badge: string;
}

export interface ParserConfig {
  ceit_prefix_map: Record<string, PrefixMetadata>;
  known_lab_subjects: string[];
  program_aliases: Record<string, string>;
  roster_keywords: {
    name_tokens: string[];
    id_tokens: string[];
  };
  schedule_config: {
    fallback_instructor: string;
    fallback_college: string;
    fallback_semester: string;
  };
}

export interface CustomTemplate {
  id: string;
  title: string;
  suffix: string;
  filename: string;
  file_path: string;
  enabled: boolean;
  recipe: TemplateRecipe;
  created_at?: string;
}

export interface TemplateRecipe {
  title: string;
  suffix: string;
  template_file: string;
  confidence: number;
  header_bindings: Array<{
    field: string;
    type: string;
    table_index?: number;
    row_index?: number;
    cell_index?: number;
    para_index?: number;
    shrink_threshold: number;
    label_found: string;
  }>;
  roster_table?: {
    table_index: number;
    header_row_index: number;
    template_row_index: number;
    index_col: number | null;
    name_col: number | null;
    id_col: number | null;
    signature_col: number | null;
    total_cols: number;
    header_labels: string[];
  } | null;
  placeholders?: Array<{
    tag: string;
    raw_token: string;
    field: string;
  }>;
  summary: {
    roster_table_found: boolean;
    roster_columns: {
      index_col: number | null;
      name_col: number | null;
      id_col: number | null;
      signature_col: number | null;
    };
    detected_fields: string[];
    total_tables: number;
    total_paragraphs: number;
  };
}

export interface GenerationOptions {
  schedule_path: string;
  rosters: string[];
  output_dir: string;
  start_date?: string;
  end_date?: string;
  class_configs?: RosterConfigMap;
}

export interface FileEstimate {
  total_files: number;
  sections_count: number;
  ceit_forms_count: number;
  attendance_sheets_count: number;
  grade_sheets_count: number;
}

export interface GenerationSummary {
  total_documents: number;
  sections_processed: number;
  output_directory: string;
  generated_files?: string[];
}

export interface ToastMessage {
  id: string;
  type: 'success' | 'warning' | 'error' | 'info';
  title: string;
  message: string;
}
