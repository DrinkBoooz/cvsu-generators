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
} from './api';

declare global {
  interface Window {
    pywebview?: {
      api: {
        browse_schedule(target_path?: string): Promise<{
          path: string;
          metadata: ScheduleMetadata | null;
          validation: ClassValidation[];
        }>;
        handle_dropped_schedule(file_payload: {
          filename: string;
          path?: string;
          data?: string;
        }): Promise<{
          path: string;
          metadata: ScheduleMetadata | null;
          validation: ClassValidation[];
        }>;
        browse_rosters(roster_configs?: RosterConfigMap): Promise<{
          count: number;
          rosters: string[];
          validation: ClassValidation[];
        }>;
        handle_dropped_rosters(
          files_payload: Array<{ filename: string; path?: string; data?: string }>,
          roster_configs?: RosterConfigMap
        ): Promise<{
          count: number;
          rosters: string[];
          validation: ClassValidation[];
        }>;
        remove_roster(
          path_or_index: string | number,
          roster_configs?: RosterConfigMap
        ): Promise<{
          count: number;
          rosters: string[];
          validation: ClassValidation[];
        }>;
        browse_output_dir(): Promise<{ path: string }>;
        validate_rosters(roster_configs?: RosterConfigMap): Promise<ClassValidation[]>;
        get_file_estimate(options: GenerationOptions): Promise<FileEstimate>;
        start_generation(options: GenerationOptions): Promise<{ status: string; message?: string }>;
        cancel_generation(): Promise<{ status: string; message?: string }>;
        get_parser_config(): Promise<ParserConfig & { default_config?: any }>;
        save_parser_config(new_config: ParserConfig): Promise<{ status: string; message?: string; validation?: ClassValidation[] }>;
        reset_parser_config(): Promise<{ status: string; message?: string; config?: ParserConfig; validation?: ClassValidation[] }>;
        export_parser_config(): Promise<{ status: string; message?: string }>;
        import_parser_config(): Promise<{ status: string; message?: string; validation?: ClassValidation[] }>;
        browse_custom_template(): Promise<{ path?: string; cancelled?: boolean }>;
        handle_dropped_custom_template(file_payload: {
          filename: string;
          path?: string;
          data?: string;
        }): Promise<{ path: string }>;
        inspect_custom_template(target_path?: string): Promise<{
          status: string;
          recipe?: TemplateRecipe;
          message?: string;
          file_path?: string;
        }>;
        save_custom_template(
          source_path: string,
          title: string,
          suffix: string,
          recipe: TemplateRecipe,
          enabled: boolean
        ): Promise<{ status: string; template?: CustomTemplate; message?: string }>;
        get_custom_templates(): Promise<CustomTemplate[]>;
        toggle_custom_template(template_id: string, enabled: boolean): Promise<{ status: string; message?: string }>;
        delete_custom_template(template_id: string): Promise<{ status: string; deleted_id?: string; message?: string }>;
      };
    };

    // Global callbacks invoked by Python backend via PyWebView evaluate_js
    updateProgress?: (percent: number, statusText: string, currentStep: number, totalSteps: number) => void;
    generationComplete?: (summary: GenerationSummary) => void;
    generationError?: (errMessage: string) => void;
  }
}

export {};
