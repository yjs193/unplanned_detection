
export interface TicketFact {
  plan_id: string
  ticket_no?: string
  ticket_title?: string
  source_file_name?: string
  source_consistency?: { matched: boolean; source_file_name?: string; ticket_title?: string; message?: string }
  project_name: string
  city?: string
  district?: string
  contractor?: string
  plan_time_range: { start: string; end: string }
  risk_level: string
  initial_risk_level?: string
  recheck_risk_level?: string
  plan_status: string
  execution_status: string
  work_leader: string
  video_control_enabled: boolean
  work_location: string
  work_content_raw: string
  work_content_summary?: string
  work_areas?: string[]
  work_actions?: string[]
  equipment_targets?: string[]
  special_operations?: string[]
  construction_plan_name?: string
  requires_power_outage?: boolean | null
  in_running_area_or_near_electric?: boolean | null
  main_hazards?: string[]
  required_tools?: string[]
  medium_high_risk_items?: string[]
  risk_control_section?: string
  risk_control_measures?: Array<{ risk_name: string; control_measure: string }>
  site_assessment_items?: Array<{ category: string; question: string; answer: string; checked: boolean }>
  supplemental_controls?: { change_description?: string; supplemental_measure?: string }
  personnel_approval?: Record<string, any>
  work_scope: string[]
  person_count?: number | null
  source_type: string
  normalized_work_types: string[]
  scene_tags: string[]
}

export interface WorkTicket {
  id: string
  plan_id: string
  ticket_no?: string
  ticket_title?: string
  source_file_name?: string
  source_consistency?: { matched: boolean; source_file_name?: string; ticket_title?: string; message?: string }
  project_name: string
  district: string
  work_location: string
  work_content_raw: string
  plan_status: string
  execution_status: string
  risk_level: string
  work_leader: string
  contractor: string
  video_control_enabled: boolean
  plan_start: string
  plan_end: string
  raw_text: string
  ticket_fact: TicketFact
  media_query_task: Record<string, any>
  validation_result: Record<string, any>
  agent_analysis?: Record<string, any>
  created_at: string
  updated_at: string
}

export interface ParseRecord {
  id: string
  ticket_id?: string
  created_at: string
  source_type: string
  summary: string
  raw_text?: string
  ocr_result?: {
    success?: boolean
    text?: string
    engine?: string
    language?: string
    filename?: string
    score?: number
    error?: string
    image_size?: { width: number; height: number }
  }
  pdf_result?: {
    success?: boolean
    text?: string
    engine?: string
    filename?: string
    page_count?: number
    pages?: Array<{ page: number; chars: number; method: string }>
    error?: string
  }
  ticket_fact: TicketFact
  work_content_items: string[]
  normalized_work_types: string[]
  validation_result: {
    missing_fields: string[]
    warnings: string[]
    requires_human_review: boolean
    confidence: number
  }
  media_query_task: Record<string, any>
  media_manifest: Array<Record<string, any>>
  agent_trace: Array<{ node: string; name: string; status: string }>
  agent_analysis?: {
    agent_name: string
    risk_judgement: string
    key_findings: string[]
    dispatch_suggestion: string
    review_required: boolean
    model_provider: string
    field_quality?: Record<string, any>
    control_focus?: string[]
    media_binding_requirements?: Record<string, any>
    work_content_understanding?: Record<string, any>
    site_assessment_summary?: Record<string, any>
    inspection_rules?: string[]
    llm_error?: string
    agent_report?: string
    vision_checklist?: Array<Record<string, any>>
    matching_rules?: string[]
    violation_detection_rules?: string[]
    model_name?: string
    llm_used?: boolean
  }
}

export interface SampleTicket {
  id: string
  name: string
  source_type: string
  raw_text: string
  ticket?: WorkTicket
}

export interface AgentPromptSetting {
  agent_id: string
  agent_name: string
  category: string
  description: string
  required_output: string
  variables: string[]
  tools?: Array<{ name: string; type?: string; purpose?: string }>
  knowledge_bases?: Array<{ name: string; source?: string; usage?: string }>
  manuals?: Array<{ title: string; path?: string; summary?: string }>
  data_sources?: Array<{ name: string; path?: string; status?: string }>
  default_prompt: string
  prompt: string
  is_custom: boolean
  updated_at: string
  prompt_length: number
}

export interface SiteMediaFrame {
  media_id: string
  media_type: string
  camera_id: string
  camera_name: string
  capture_time: string
  file_path: string
  thumbnail_path: string
  status: string
  minute_index: number
  work_location?: string
  source_asset?: string
  source_page?: string
  source_title?: string
  dedupe_key?: string
  display_label?: string
}

export interface VisionBinding {
  project_label: string
  workbook: string
  ticket_no: string
  weekly_plan: string
  ticket_name: string
  plan_time_range: string
  execution_status: string
  risk_level: string
  task_category: string
  task_name: string
  site_leader: string
  matched: boolean
  video_count: number
  videos: Array<{ filename: string; weekly_plan: string; camera_id: string; start_token: string; end_token: string; size_mb: number; url: string }>
}

export interface VisionAnalysisResult {
  success: boolean
  error?: string
  analysis_id?: string
  source?: string
  model_name?: string
  fallback_reason?: string
  final_decision_allowed?: boolean
  output_boundary?: string
  ticket_summary?: Partial<WorkTicket>
  binding?: VisionBinding | null
  video?: { filename: string; weekly_plan: string; camera_id: string; start_token: string; end_token: string; size_mb: number; url: string } | null
  frame_count: number
  frames: Array<{ frame_index: number; display_label: string; image_url: string; evidence_text: string; facts?: Array<Record<string, any>> }>
  aggregates: Record<string, any>
  evidence_text: string
  media_manifest: SiteMediaFrame[]
}

export interface InspectionRecord {
  id: string
  ticket_id?: string
  created_at: string
  operator: string
  mode: string
  ticket: string
  location: string
  status: string
  risk: string
  updated_at: string
  ticket_fact: TicketFact
  media_manifest: SiteMediaFrame[]
  report: {
    conclusion: string
    risk_level: string
    evidence: string[]
    next_actions: string[]
  }
  timeline: Array<{ time: string; event: string }>
}

export interface DashboardData {
  stats: {
    total_tickets: number
    active_tickets: number
    pending_match_tickets: number
    high_risk_tickets: number
    video_control_tickets: number
    key_active_tickets: number
    human_review: number
    media_tasks: number
    video_control_rate: number
  }
  by_status: Array<{ name: string; value: number }>
  by_risk: Array<{ name: string; value: number }>
  by_district: Array<{ name: string; value: number }>
  recent_tickets: WorkTicket[]
}

export interface PilotWorkflowResult {
  success: boolean
  project: string
  ticket_created?: boolean
  parse_record?: ParseRecord | Record<string, any>
  ticket: WorkTicket
  media_manifest: SiteMediaFrame[]
  vision_result: {
    model_name: string
    model_assumption?: string
    inference_pipeline?: Array<Record<string, any>>
    detectors?: string[]
    expected_profile?: Record<string, any>
    frame_count: number
    aggregates: Record<string, any>
    frames: Array<Record<string, any>>
  }
  violation_result: {
    conclusion: string
    risk_level: string
    anomaly_count: number
    anomalies: Array<Record<string, any>>
    matched_rules?: Array<Record<string, any>>
    dimension_comparison?: Array<Record<string, any>>
    workflow_stages?: Array<Record<string, any>>
    rulebook_summary?: Record<string, any>
    report_md?: string
    rules: string[]
  }
  inspection: InspectionRecord & { vision_result?: Record<string, any>; violation_result?: Record<string, any> }
  data_sources: Array<{ title: string; source_page: string; filename: string }>
}

export interface ViolationDetectionResult {
  success: boolean
  match_id?: string
  created_at?: string
  provider?: string
  model?: string
  llm_used?: boolean
  risk_level?: string
  token_probability?: number | null
  avg_token_probability?: number | null
  token_probability_count?: number | null
  token_probability_available?: boolean
  probability_threshold?: number
  probability_thresholds?: Record<string, any>
  result?: {
    match_result: string
    task_match_score: number
    matched_work: string[]
    unmatched_work: Array<{ ticket_side: string; video_side: string; evidence: string; confidence: number }>
    need_second_video_reasoning: boolean
    reason: string
  }
  first_pass?: Record<string, any>
  second_pass?: Record<string, any>
  final_decision_source?: string
  result_conflict?: boolean
  manual_review_required?: boolean
  auto_flow_stopped?: boolean
  manual_review_reason?: string
  review_trace?: Record<string, any>
  metrics?: Record<string, any>
  ticket_summary?: Partial<WorkTicket> | null
  ticket_task_text?: string
  video_evidence_text?: string
  evidence_source?: string
  vision_result?: VisionAnalysisResult
  capability_scope?: string
  error?: string
}
