import {
  ScheduleMetadata,
  ClassValidation,
  ParserConfig,
  CustomTemplate,
  TemplateRecipe,
  FileEstimate,
  RosterConfigMap,
  DetectedClass,
  RosterValidationReport,
} from '../types/api';

const isDesktop = () => typeof window !== 'undefined' && !!window.pywebview?.api;

// Realistic Mock Data for Web Development / Testing
let mockSchedulePath = '';
let mockScheduleMetadata: ScheduleMetadata | null = null;
let mockRosters: string[] = [];
let mockOutputDir = 'C:\\CvSU_Generated_Documents';
let mockDetectedClasses: DetectedClass[] = [
  {
    id: 'BSCS1-4_202612040',
    course_sec: 'BSCS 1-4',
    schedule_code: '202612040',
    subject_name: 'DCIT 21 - INTRODUCTION TO COMPUTING',
    schedule_desc: '07:00AM-10:00AM / M / LEC: ITC 404',
    has_lab: false,
    detected_type: 'lecture_only',
    roster_file: 'BSCS1-4 List of Students for 202612040-DCIT 21.xlsx',
    ceit_metadata: { prefix: 'DCIT', department_code: 'DIT', department_name: 'Department of Information Technology' },
  },
  {
    id: 'BSCS2-1_202612041',
    course_sec: 'BSCS 2-1',
    schedule_code: '202612041',
    subject_name: 'DCIT 25 - DATA STRUCTURES AND ALGORITHMS',
    schedule_desc: '07:00AM-09:00AM, 01:00PM-03:00PM / Th / LAB: CCL 204, LEC: ITC 404',
    has_lab: true,
    detected_type: 'lecture_lab',
    roster_file: 'BSCS2-1 List of Students for 202612041-DCIT 25.xlsx',
    ceit_metadata: { prefix: 'DCIT', department_code: 'DIT', department_name: 'Department of Information Technology' },
  },
  {
    id: 'BSIT3-2_202612042',
    course_sec: 'BSIT 3-2',
    schedule_code: '202612042',
    subject_name: 'ITEC 85 - ADVANCED WEB DEVELOPMENT',
    schedule_desc: '10:00AM-01:00PM / F / LAB: CL 3',
    has_lab: true,
    detected_type: 'lecture_lab',
    roster_file: 'BSIT3-2 List of Students for 202612042-ITEC 85.xlsx',
    ceit_metadata: { prefix: 'ITEC', department_code: 'DIT', department_name: 'Department of Information Technology' },
  },
];

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
        { field: 'course_section', type: 'table_cell', table_index: 0, row_index: 1, cell_index: 1, shrink_threshold: 0, label_found: 'Course & Section:' },
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
        header_labels: ['No.', 'Student Number', 'Name of Student', 'Signature'],
      },
      summary: {
        roster_table_found: true,
        roster_columns: { index_col: 0, name_col: 2, id_col: 1, signature_col: 3 },
        detected_fields: ['instructor', 'course_section', 'subject', 'schedule_code'],
        total_tables: 2,
        total_paragraphs: 4,
      },
    },
    created_at: new Date().toISOString(),
  },
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

  async browseSchedule() {
    if (isDesktop()) {
      return window.pywebview!.api.browse_schedule();
    }
    mockSchedulePath = 'C:\\Users\\faculty\\ORTEGA_SCHEDULE_2026.xls';
    mockScheduleMetadata = {
      instructor: 'DAN JOSEPH A. ORTEGA',
      college: 'COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY',
      semester: 'First Semester, A.Y. 2026-2027',
      semester_ay: 'First Semester, A.Y. 2026-2027',
      total_slots: 18,
      detected_sections: ['BSCS 1-4', 'BSCS 2-1', 'BSIT 3-2'],
    };
    return {
      path: mockSchedulePath,
      metadata: mockScheduleMetadata,
      validation: this.getMockValidation(),
    };
  },

  async handleDroppedSchedule(filename: string, originalPath?: string, base64Data?: string) {
    if (isDesktop()) {
      return window.pywebview!.api.handle_dropped_schedule(
        filename,
        base64Data || null,
        originalPath || null
      );
    }
    mockSchedulePath = originalPath || `C:\\Users\\faculty\\${filename}`;
    mockScheduleMetadata = {
      instructor: 'DAN JOSEPH A. ORTEGA',
      college: 'COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY',
      semester: 'First Semester, A.Y. 2026-2027',
      semester_ay: 'First Semester, A.Y. 2026-2027',
      total_slots: 18,
      detected_sections: ['BSCS 1-4', 'BSCS 2-1', 'BSIT 3-2'],
    };
    return {
      path: mockSchedulePath,
      metadata: mockScheduleMetadata,
      validation: this.getMockValidation(),
    };
  },

  async browseRosters(rosterConfigs?: RosterConfigMap) {
    if (isDesktop()) {
      return window.pywebview!.api.browse_rosters(rosterConfigs || null);
    }
    mockRosters = [
      'C:\\Users\\faculty\\BSCS1-4 List of Students for 202612040-DCIT 21.xlsx',
      'C:\\Users\\faculty\\BSCS2-1 List of Students for 202612041-DCIT 25.xlsx',
      'C:\\Users\\faculty\\BSIT3-2 List of Students for 202612042-ITEC 85.xlsx',
    ];
    return {
      count: mockRosters.length,
      rosters: mockRosters,
      validation: this.getMockValidation(),
    };
  },

  async handleDroppedRosters(
    files: Array<{ filename: string; path?: string | null; data?: string | null }>,
    rosterConfigs?: RosterConfigMap
  ) {
    if (isDesktop()) {
      return window.pywebview!.api.handle_dropped_rosters(files, rosterConfigs || null);
    }
    files.forEach((f) => {
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
      return window.pywebview!.api.remove_roster(pathOrIndex, rosterConfigs || null);
    }
    if (typeof pathOrIndex === 'number') {
      mockRosters.splice(pathOrIndex, 1);
    } else {
      mockRosters = mockRosters.filter((r) => r !== pathOrIndex);
    }
    return {
      count: mockRosters.length,
      rosters: mockRosters,
      validation: this.getMockValidation(),
    };
  },

  async clearRosters() {
    if (isDesktop()) {
      return window.pywebview!.api.clear_rosters();
    }
    mockRosters = [];
    return { count: 0, rosters: [], validation: [] };
  },

  async browseOutputDir() {
    if (isDesktop()) {
      const path = await window.pywebview!.api.browse_output();
      return { path: path || '' };
    }
    mockOutputDir = 'C:\\Users\\faculty\\Documents\\CvSU_Output_2026';
    return { path: mockOutputDir };
  },

  async openOutputFolder(folderPath?: string) {
    if (isDesktop()) {
      return window.pywebview!.api.open_output_folder(folderPath);
    }
    return { status: 'success' };
  },

  async openFile(filePath: string) {
    if (isDesktop()) {
      return window.pywebview!.api.open_file(filePath);
    }
    return { status: 'success' };
  },

  async detectClasses(rosterConfigs?: RosterConfigMap): Promise<DetectedClass[]> {
    if (isDesktop()) {
      return window.pywebview!.api.detect_classes(rosterConfigs || null);
    }
    return mockDetectedClasses;
  },

  async validateRosters(rosterConfigs?: RosterConfigMap): Promise<RosterValidationReport[]> {
    if (isDesktop()) {
      return window.pywebview!.api.validate_rosters(rosterConfigs || null);
    }
    return this.getMockValidation();
  },

  async inspectRoster(pathOrFilename: string, overrides?: any) {
    if (isDesktop()) {
      return window.pywebview!.api.inspect_roster(pathOrFilename, overrides);
    }
    return {
      status: 'success',
      filename: pathOrFilename,
      column_count: 2,
      columns: ['Name', 'Student Number'],
      sample_rows: [
        ['DELA CRUZ, JUAN A.', '202210101'],
        ['SANTOS, MARIA B.', '202210102'],
      ],
      total_students: 42,
    };
  },

  async runGeneration(
    typeOverrides?: Record<string, string>,
    dateOverrides?: { start_date?: string; end_date?: string },
    classFilter?: string[],
    engineFilter?: { attendance: boolean; ceit: boolean; grades: boolean },
    rosterConfigs?: RosterConfigMap
  ) {
    if (isDesktop()) {
      return window.pywebview!.api.run_generation(
        typeOverrides || null,
        dateOverrides || null,
        classFilter || null,
        engineFilter || null,
        rosterConfigs || null
      );
    }
    // Browser Mock Simulation
    let step = 0;
    const total = 28;
    const interval = setInterval(() => {
      step += 2;
      const pct = Math.min(100, Math.round((step / total) * 100));
      window.onGenerationProgress?.({
        percent: pct,
        current_class: 'BSCS 1-4',
        current_task: `Compiling document ${step} of ${total}`,
        step,
        total_steps: total,
      });
      if (step >= total) {
        clearInterval(interval);
        window.onGenerationComplete?.({
          status: 'success',
          message: `Generation complete! ${total} files generated successfully.`,
          stats: { generated: total, errors: 0, skipped: 0 },
          output_dir: mockOutputDir,
        });
      }
    }, 150);
    return null;
  },

  async cancelGeneration() {
    if (isDesktop()) {
      return window.pywebview!.api.cancel_generation();
    }
    window.onGenerationComplete?.({
      status: 'cancelled',
      message: 'Generation cancelled by user.',
      stats: { generated: 4, errors: 0, skipped: 0 },
      output_dir: mockOutputDir,
    });
    return { status: 'success' };
  },

  async getRecentLogs(lines: number = 120) {
    if (isDesktop()) {
      return window.pywebview!.api.get_recent_logs(lines);
    }
    return '[Mock Log] CVSU Document Generator active.';
  },

  async openLogFolder() {
    if (isDesktop()) {
      return window.pywebview!.api.open_log_folder();
    }
    return { status: 'success' };
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

  async handleDroppedCustomTemplate(filename: string, originalPath?: string, base64Data?: string) {
    if (isDesktop()) {
      return window.pywebview!.api.handle_dropped_custom_template(
        filename,
        base64Data || null,
        originalPath || null
      );
    }
    return { path: originalPath || `C:\\Users\\faculty\\${filename}` };
  },

  async inspectCustomTemplate(targetPath: string) {
    if (isDesktop()) {
      return window.pywebview!.api.inspect_custom_template(targetPath);
    }
    return {
      status: 'success',
      recipe: mockCustomTemplates[0].recipe,
      file_path: targetPath,
    };
  },

  async saveCustomTemplate(sourcePath: string, title: string, suffix: string, recipe: TemplateRecipe) {
    if (isDesktop()) {
      return window.pywebview!.api.save_custom_template(sourcePath, title, suffix, recipe);
    }
    const newTmpl: CustomTemplate = {
      id: suffix.toLowerCase(),
      title,
      suffix,
      filename: `${suffix.toLowerCase()}.docx`,
      file_path: sourcePath,
      enabled: true,
      recipe,
      created_at: new Date().toISOString(),
    };
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
    const item = mockCustomTemplates.find((t) => t.id === templateId);
    if (item) item.enabled = enabled;
    return { status: 'success' };
  },

  async deleteCustomTemplate(templateId: string) {
    if (isDesktop()) {
      return window.pywebview!.api.delete_custom_template(templateId);
    }
    mockCustomTemplates = mockCustomTemplates.filter((t) => t.id !== templateId);
    return { status: 'success', deleted_id: templateId };
  },

  /**
   * Deterministic client-side File Estimate calculation matching executable/ui.html
   */
  calculateFileEstimate(
    selectedClassCount: number,
    engines: { attendance: boolean; ceit: boolean; grades: boolean },
    customTemplatesCount: number,
    startDate?: string,
    endDate?: string
  ): FileEstimate | null {
    if (selectedClassCount === 0) return null;

    const ceitCount = engines.ceit ? 7 + customTemplatesCount : 0;
    const gradesCount = engines.grades ? 1 : 0;

    let monthsCount = 5;
    if (startDate && endDate) {
      const d1 = new Date(startDate);
      const d2 = new Date(endDate);
      if (!isNaN(d1.getTime()) && !isNaN(d2.getTime()) && d2 >= d1) {
        monthsCount = Math.max(
          1,
          (d2.getFullYear() - d1.getFullYear()) * 12 + (d2.getMonth() - d1.getMonth()) + 1
        );
      }
    }
    const attCount = engines.attendance ? monthsCount : 0;
    const perClass = ceitCount + gradesCount + attCount;
    const totalFiles = selectedClassCount * perClass;

    return {
      total_files: totalFiles,
      sections_count: selectedClassCount,
      ceit_forms_count: selectedClassCount * ceitCount,
      attendance_sheets_count: selectedClassCount * attCount,
      grade_sheets_count: selectedClassCount * gradesCount,
    };
  },

  getMockValidation(): RosterValidationReport[] {
    return [
      {
        filename: 'BSCS1-4 List of Students for 202612040-DCIT 21.xlsx',
        path: 'C:\\Users\\faculty\\BSCS1-4 List of Students for 202612040-DCIT 21.xlsx',
        student_count: 42,
        status: 'valid',
        ceit_metadata: { prefix: 'DCIT', department_code: 'DIT', department_name: 'Department of Information Technology' },
      },
      {
        filename: 'BSCS2-1 List of Students for 202612041-DCIT 25.xlsx',
        path: 'C:\\Users\\faculty\\BSCS2-1 List of Students for 202612041-DCIT 25.xlsx',
        student_count: 38,
        status: 'valid',
        ceit_metadata: { prefix: 'DCIT', department_code: 'DIT', department_name: 'Department of Information Technology' },
      },
      {
        filename: 'BSIT3-2 List of Students for 202612042-ITEC 85.xlsx',
        path: 'C:\\Users\\faculty\\BSIT3-2 List of Students for 202612042-ITEC 85.xlsx',
        student_count: 35,
        status: 'valid',
        ceit_metadata: { prefix: 'ITEC', department_code: 'DIT', department_name: 'Department of Information Technology' },
      },
    ];
  },
};
