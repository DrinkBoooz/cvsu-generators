import {
  ScheduleMetadata,
  ClassValidation,
  ParserConfig,
  CustomTemplate,
  TemplateRecipe,
  GenerationOptions,
  FileEstimate,
  GenerationSummary,
  RosterConfigMap,
  DetectedClass,
  RosterValidationReport,
} from './api';

declare global {
  interface Window {
    pywebview?: {
      api: {
        browse_schedule(): Promise<{
          path: string;
          metadata: ScheduleMetadata | null;
          validation: RosterValidationReport[];
        }>;
        handle_dropped_schedule(
          filename: string,
          base64_data?: string | null,
          original_path?: string | null
        ): Promise<{
          path: string;
          metadata: ScheduleMetadata | null;
          validation: RosterValidationReport[];
        }>;
        browse_rosters(roster_configs?: any): Promise<{
          count: number;
          rosters: string[];
          validation: RosterValidationReport[];
        }>;
        handle_dropped_rosters(
          files_payload: Array<{ filename: string; path?: string | null; data?: string | null }>,
          roster_configs?: any
        ): Promise<{
          count: number;
          rosters: string[];
          validation: RosterValidationReport[];
        }>;
        remove_roster(
          path_or_index: string | number,
          roster_configs?: any
        ): Promise<{
          count: number;
          rosters: string[];
          validation: RosterValidationReport[];
        }>;
        clear_rosters(): Promise<{
          count: number;
          rosters: string[];
          validation: RosterValidationReport[];
        }>;
        browse_output(): Promise<string>;
        open_output_folder(folder_path?: string): Promise<{ status: string; message?: string }>;
        open_file(file_path: string): Promise<{ status: string; message?: string }>;
        get_recent_logs(lines?: number): Promise<string>;
        open_log_folder(): Promise<{ status: string; message?: string }>;
        detect_classes(roster_configs?: any): Promise<DetectedClass[]>;
        run_generation(
          type_overrides?: any,
          date_overrides?: any,
          class_filter?: any,
          engine_filter?: any,
          roster_configs?: any
        ): Promise<any>;
        cancel_generation(): Promise<{ status: string; message?: string }>;
        validate_rosters(roster_configs?: any): Promise<RosterValidationReport[]>;
        inspect_roster(path_or_filename: string, overrides?: any): Promise<any>;
        get_parser_config(): Promise<ParserConfig & { default_config?: any }>;
        save_parser_config(new_config: ParserConfig): Promise<{
          status: string;
          message?: string;
          validation?: RosterValidationReport[];
          detected_classes?: DetectedClass[];
        }>;
        reset_parser_config(): Promise<{
          status: string;
          message?: string;
          config?: ParserConfig;
          validation?: RosterValidationReport[];
          detected_classes?: DetectedClass[];
        }>;
        export_parser_config(): Promise<{ status: string; message?: string }>;
        import_parser_config(): Promise<{
          status: string;
          message?: string;
          validation?: RosterValidationReport[];
          detected_classes?: DetectedClass[];
        }>;
        browse_custom_template(): Promise<any>;
        handle_dropped_custom_template(
          filename: string,
          base64_data?: string | null,
          original_path?: string | null
        ): Promise<any>;
        inspect_custom_template(file_path: string): Promise<{
          status: string;
          recipe?: TemplateRecipe;
          message?: string;
          file_path?: string;
        }>;
        save_custom_template(
          file_path: string,
          title: string,
          suffix: string,
          recipe: TemplateRecipe
        ): Promise<{ status: string; message?: string }>;
        get_custom_templates(): Promise<CustomTemplate[]>;
        toggle_custom_template(template_id: string, enabled: boolean): Promise<{ status: string; message?: string }>;
        delete_custom_template(template_id: string): Promise<{ status: string; deleted_id?: string; message?: string }>;
      };
    };

    // Global bridge callbacks evaluated by Python backend
    onScheduleLoaded?: (res: {
      path: string;
      metadata: ScheduleMetadata | null;
      validation: RosterValidationReport[];
    }) => void;
    onRostersLoaded?: (res: {
      count: number;
      rosters: string[];
      validation: RosterValidationReport[];
    }) => void;
    onGenerationProgress?: (info: {
      percent: number;
      current_class?: string;
      current_task?: string;
      step: number;
      total_steps: number;
    }) => void;
    onGenerationComplete?: (payload: {
      status: string;
      message: string;
      stats?: {
        generated: number;
        errors: number;
        skipped: number;
      };
      details?: any;
      output_dir?: string;
    }) => void;
    onGenerationError?: () => void;
  }
}

export {};
