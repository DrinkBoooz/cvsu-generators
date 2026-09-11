import {
  ScheduleMetadata,
  ClassValidation,
  ParserConfig,
  CustomTemplate,
  TemplateRecipe,
  GenerationOptions,
  FileEstimate,
  RosterConfigMap,
} from '../types/api';

const isDesktop = () => typeof window !== 'undefined' && !!window.pywebview?.api;

// Realistic Mock Data for Web Development / Testing
let mockSchedulePath = '';
let mockScheduleMetadata: ScheduleMetadata | null = null;
let mockRosters: string[] = [];
let mockOutputDir = 'C:\\CvSU_Generated_Documents';
let mockCustomTemplates: CustomTemplate[] = [
  {
    id: 'consultation_log',
    title: 'Student Consultation Sheet',
    suffix: 'CONSULTATION_LOG',
    filename: 'consultation_log.docx',
    file_path: 'C:\\Users\\faculty\\templates\\consultation_log.docx',
    enabled: true,
    recipe: {
      title: 'Student Consultation Sheet',
      suffix: 'CONSULTATION_LOG',
      template_file: 'consultation_log.docx',
      confidence: 95,
      header_bindings: [
        { field: 'instructor', type: 'table_cell', table_index: 0, row_index: 0, cell_index: 1, shrink_threshold: 30, label_found: 'Instructor:' },
        { field: 'course_section', type: 'table_cell', table_index: 0, row_index: 1, cell_index: 1, shrink_threshold: 0, label_found: 'Course & Section:' }
      ],
      roster_table: {
        table_index: 1,
        header_row_index: 0,
        template_row_index: 1,
        index_col: 0,
        name_col: 2,
        id_col: 1,
        signature_col: 3,
        total_cols: 4,
        header_labels: ['No.', 'Student Number', 'Name of Student', 'Signature']
      },
      summary: {
        roster_table_found: true,
        roster_columns: { index_col: 0, name_col: 2, id_col: 1, signature_col: 3 },
        detected_fields: ['instructor', 'course_section', 'subject', 'schedule_code'],
        total_tables: 2,
        total_paragraphs: 4
      }
    },
    created_at: new Date().toISOString()
  }
];

let mockConfig: ParserConfig = {
  ceit_prefix_map: {
    COSC: { name: 'Computer Science', dept: 'Department of Information Technology', dept_code: 'DIT', icon: '🖥️', badge: '🖥️ DIT' },
    DCIT: { name: 'Information Technology', dept: 'Department of Information Technology', dept_code: 'DIT', icon: '💻', badge: '💻 DIT' },
    CENG: { name: 'Civil Engineering', dept: 'Department of Civil Engineering', dept_code: 'DCE', icon: '🏛️', badge: '🏛️ DCE' },
  },
  known_lab_subjects: ['DCIT21', 'DCIT22', 'COSC55', 'ITEC50'],
  program_aliases: {
    'CS 1-1': 'BSCS 1-1',
    'IT 2-1': 'BSIT 2-1',
  },
  roster_keywords: {
    name_tokens: ['name', 'student', 'pangalan'],
    id_tokens: ['student number', 'id number', 'stud no', 'lrn'],
  },
  schedule_config: {
    fallback_instructor: 'DAN JOSEPH A. ORTEGA',
    fallback_college: 'COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY',
    fallback_semester: 'First Semester, A.Y. 2026-2027',
  },
};

export const pywebviewService = {
  isDesktop,

  async browseSchedule(targetPath?: string) {
    if (isDesktop()) {
      return window.pywebview!.api.browse_schedule(targetPath);
    }
    // Mock implementation
    mockSchedulePath = targetPath || 'C:\\Users\\faculty\\ORTEGA_SCHEDULE_2026.xls';
    mockScheduleMetadata = {
      instructor: 'DAN JOSEPH A. ORTEGA',
      college: 'COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY',
      semester_ay: 'First Semester, A.Y. 2026-2027',
      classes: [
        { course_section: 'BSCS 1-4', subject: 'DCIT 21 - INTRODUCTION TO COMPUTING', schedule_code: '202612040', time_days_room: '07:00AM-10:00AM / M / LEC: ITC 404', has_lab: false },
        { course_section: 'BSCS 2-1', subject: 'DCIT 25 - DATA STRUCTURES AND ALGORITHMS', schedule_code: '202612041', time_days_room: '07:00AM-09:00AM, 01:00PM-03:00PM / Th / LAB: CCL 204, LEC: ITC 404', has_lab: true },
        { course_section: 'BSIT 3-2', subject: 'ITEC 85 - ADVANCED WEB DEVELOPMENT', schedule_code: '202612042', time_days_room: '10:00AM-01:00PM / F / LAB: CL 3', has_lab: true },
      ],
    };
    return {
      path: mockSchedulePath,
      metadata: mockScheduleMetadata,
      validation: this.getMockValidation(),
    };
  },

  async handleDroppedSchedule(filePayload: { filename: string; path?: string; data?: string }) {
    if (isDesktop()) {
      return window.pywebview!.api.handle_dropped_schedule(filePayload);
    }
    return this.browseSchedule(filePayload.path || `C:\\Users\\faculty\\${filePayload.filename}`);
  },

  async browseRosters(rosterConfigs?: RosterConfigMap) {
    if (isDesktop()) {
      return window.pywebview!.api.browse_rosters(rosterConfigs);
    }
    mockRosters = [
      'C:\\Users\\faculty\\BSCS1-4 List of Students for 202612040-DCIT 21.xlsx',
      'C:\\Users\\faculty\\BSCS2-1 List of Students for 202612041-DCIT 25.xlsx',
    ];
    return {
      count: mockRosters.length,
      rosters: mockRosters,
      validation: this.getMockValidation(),
    };
  },

  async handleDroppedRosters(files: Array<{ filename: string; path?: string; data?: string }>, rosterConfigs?: RosterConfigMap) {
    if (isDesktop()) {
      return window.pywebview!.api.handle_dropped_rosters(files, rosterConfigs);
    }
    files.forEach(f => {
      const p = f.path || `C:\\Users\\faculty\\${f.filename}`;
      if (!mockRosters.includes(p)) mockRosters.push(p);
    });
    return {
      count: mockRosters.length,
      rosters: mockRosters,
      validation: this.getMockValidation(),
    };
  },

  async removeRoster(pathOrIndex: string | number, rosterConfigs?: RosterConfigMap) {
    if (isDesktop()) {
      return window.pywebview!.api.remove_roster(pathOrIndex, rosterConfigs);
    }
    if (typeof pathOrIndex === 'number') {
      mockRosters.splice(pathOrIndex, 1);
    } else {
      mockRosters = mockRosters.filter(r => r !== pathOrIndex);
    }
    return {
      count: mockRosters.length,
      rosters: mockRosters,
      validation: this.getMockValidation(),
    };
  },

  async browseOutputDir() {
    if (isDesktop()) {
      return window.pywebview!.api.browse_output_dir();
    }
    mockOutputDir = 'C:\\Users\\faculty\\Documents\\CvSU_Output_2026';
    return { path: mockOutputDir };
  },

  async openOutputFolder() {
    if (isDesktop() && (window.pywebview!.api as any).open_output_folder) {
      return (window.pywebview!.api as any).open_output_folder();
    }
    console.log('[Mock] Opening output folder:', mockOutputDir);
    return { status: 'success' };
  },

  async validateRosters(rosterConfigs?: RosterConfigMap) {
    if (isDesktop()) {
      return window.pywebview!.api.validate_rosters(rosterConfigs);
    }
    return this.getMockValidation();
  },

  async getFileEstimate(options: GenerationOptions): Promise<FileEstimate> {
    if (isDesktop()) {
      return window.pywebview!.api.get_file_estimate(options);
    }
    const numClasses = mockScheduleMetadata?.classes.length || 3;
    const customCount = mockCustomTemplates.filter(t => t.enabled).length;
    const ceitCount = 7 + customCount;
    const attCount = 5; // standard semester months
    return {
      total_files: numClasses * (ceitCount + attCount + 1),
      sections_count: numClasses,
      ceit_forms_count: numClasses * ceitCount,
      attendance_sheets_count: numClasses * attCount,
      grade_sheets_count: numClasses * 1,
    };
  },

  async startGeneration(options: GenerationOptions) {
    if (isDesktop()) {
      return window.pywebview!.api.start_generation(options);
    }
    // Simulate generation loop for browser dev
    let step = 0;
    const total = 42;
    const timer = setInterval(() => {
      step += 3;
      const pct = Math.min(100, Math.round((step / total) * 100));
      window.updateProgress?.(pct, `Generating document ${step} of ${total}...`, step, total);
      if (step >= total) {
        clearInterval(timer);
        window.generationComplete?.({
          total_documents: total,
          sections_processed: 3,
          output_directory: options.output_dir || mockOutputDir,
          generated_files: ['BSCS1-4_SYLLABUS.docx', 'BSCS2-1_GRADING_SHEET.xlsx'],
        });
      }
    }, 200);
    return { status: 'started' };
  },

  async cancelGeneration() {
    if (isDesktop()) {
      return window.pywebview!.api.cancel_generation();
    }
    window.updateProgress?.(0, 'Generation cancelled by user', 0, 0);
    return { status: 'cancelled' };
  },

  async getParserConfig() {
    if (isDesktop()) {
      return window.pywebview!.api.get_parser_config();
    }
    return mockConfig;
  },

  async saveParserConfig(newConfig: ParserConfig) {
    if (isDesktop()) {
      return window.pywebview!.api.save_parser_config(newConfig);
    }
    mockConfig = newConfig;
    return { status: 'success', validation: this.getMockValidation() };
  },

  async resetParserConfig() {
    if (isDesktop()) {
      return window.pywebview!.api.reset_parser_config();
    }
    return { status: 'success', config: mockConfig, validation: this.getMockValidation() };
  },

  async exportParserConfig() {
    if (isDesktop()) {
      return window.pywebview!.api.export_parser_config();
    }
    return { status: 'success' };
  },

  async importParserConfig() {
    if (isDesktop()) {
      return window.pywebview!.api.import_parser_config();
    }
    return { status: 'success', validation: this.getMockValidation() };
  },

  async browseCustomTemplate() {
    if (isDesktop()) {
      return window.pywebview!.api.browse_custom_template();
    }
    return { path: 'C:\\Users\\faculty\\template_consultation_log.docx' };
  },

  async handleDroppedCustomTemplate(filePayload: { filename: string; path?: string; data?: string }) {
    if (isDesktop()) {
      return window.pywebview!.api.handle_dropped_custom_template(filePayload);
    }
    return { path: filePayload.path || `C:\\Users\\faculty\\${filePayload.filename}` };
  },

  async inspectCustomTemplate(targetPath?: string) {
    if (isDesktop()) {
      return window.pywebview!.api.inspect_custom_template(targetPath);
    }
    const recipe: TemplateRecipe = {
      title: 'Faculty Advising Record',
      suffix: 'ADVISING_RECORD',
      template_file: targetPath ? targetPath.split('\\').pop() || 'template.docx' : 'template.docx',
      confidence: 95,
      header_bindings: [
        { field: 'instructor', type: 'table_cell', table_index: 0, row_index: 0, cell_index: 2, shrink_threshold: 30, label_found: 'Faculty Member' },
        { field: 'course_section', type: 'table_cell', table_index: 0, row_index: 1, cell_index: 2, shrink_threshold: 0, label_found: 'Degree Program & Section' },
        { field: 'schedule_code', type: 'table_cell', table_index: 0, row_index: 2, cell_index: 2, shrink_threshold: 0, label_found: 'Class Schedule Code' },
        { field: 'subject', type: 'table_cell', table_index: 0, row_index: 3, cell_index: 2, shrink_threshold: 35, label_found: 'Subject Code & Title' },
      ],
      roster_table: {
        table_index: 1,
        header_row_index: 0,
        template_row_index: 1,
        index_col: 0,
        name_col: 2,
        id_col: 1,
        signature_col: 3,
        total_cols: 5,
        header_labels: ['Item', 'Student ID', 'Student Name', 'Concern', 'Action Taken'],
      },
      summary: {
        roster_table_found: true,
        roster_columns: { index_col: 0, name_col: 2, id_col: 1, signature_col: 3 },
        detected_fields: ['instructor', 'course_section', 'schedule_code', 'subject'],
        total_tables: 2,
        total_paragraphs: 3,
      },
    };
    return { status: 'success', recipe, file_path: targetPath || 'C:\\template.docx' };
  },

  async saveCustomTemplate(sourcePath: string, title: string, suffix: string, recipe: TemplateRecipe, enabled: boolean) {
    if (isDesktop()) {
      return window.pywebview!.api.save_custom_template(sourcePath, title, suffix, recipe, enabled);
    }
    const newTmpl: CustomTemplate = {
      id: suffix.toLowerCase(),
      title,
      suffix,
      filename: `${suffix.toLowerCase()}.docx`,
      file_path: sourcePath,
      enabled,
      recipe,
      created_at: new Date().toISOString(),
    };
    mockCustomTemplates = mockCustomTemplates.filter(t => t.id !== newTmpl.id);
    mockCustomTemplates.push(newTmpl);
    return { status: 'success', template: newTmpl };
  },

  async getCustomTemplates(): Promise<CustomTemplate[]> {
    if (isDesktop()) {
      return window.pywebview!.api.get_custom_templates();
    }
    return mockCustomTemplates;
  },

  async toggleCustomTemplate(templateId: string, enabled: boolean) {
    if (isDesktop()) {
      return window.pywebview!.api.toggle_custom_template(templateId, enabled);
    }
    const item = mockCustomTemplates.find(t => t.id === templateId);
    if (item) item.enabled = enabled;
    return { status: 'success' };
  },

  async deleteCustomTemplate(templateId: string) {
    if (isDesktop()) {
      return window.pywebview!.api.delete_custom_template(templateId);
    }
    mockCustomTemplates = mockCustomTemplates.filter(t => t.id !== templateId);
    return { status: 'success', deleted_id: templateId };
  },

  getMockValidation(): ClassValidation[] {
    return [
      {
        course_section: 'BSCS 1-4',
        schedule_code: '202612040',
        subject: 'DCIT 21 - INTRODUCTION TO COMPUTING',
        roster_file: 'BSCS1-4 List of Students for 202612040-DCIT 21.xlsx',
        roster_path: 'C:\\Users\\faculty\\BSCS1-4 List of Students for 202612040-DCIT 21.xlsx',
        student_count: 42,
        status: 'paired',
        has_lab: false,
      },
      {
        course_section: 'BSCS 2-1',
        schedule_code: '202612041',
        subject: 'DCIT 25 - DATA STRUCTURES AND ALGORITHMS',
        roster_file: 'BSCS2-1 List of Students for 202612041-DCIT 25.xlsx',
        roster_path: 'C:\\Users\\faculty\\BSCS2-1 List of Students for 202612041-DCIT 25.xlsx',
        student_count: 38,
        status: 'paired',
        has_lab: true,
      },
      {
        course_section: 'BSIT 3-2',
        schedule_code: '202612042',
        subject: 'ITEC 85 - ADVANCED WEB DEVELOPMENT',
        roster_file: '',
        roster_path: '',
        student_count: 0,
        status: 'missing',
        has_lab: true,
      },
    ];
  },
};
