export type BrandKit = {
  id: string;
  name: string;
  tagline: string;
  tone: string;
  primary: string;
  secondary: string;
  accent: string;
  text_on_primary: string;
  logo: string | null;
  logo_url?: string;
  font_display: string | null;
  font_body: string | null;
  default_template: string;
  supported_templates: string[];
};

export type Template = {
  id: string;
  name: string;
  display_name: string | null;
  thumbnail: string | null;
  thumbnail_url?: string;
  brands: string[];
  description: string;
  copy_zone: string | null;
};

export type GalleryItem = {
  id: string;
  theme: string;
  final_url: string;
  raw_url: string | null;
  spec: Record<string, unknown> | null;
  cost_usd: number | null;
};

export type Estimate = {
  min: number;
  expected: number;
  max: number;
  per_image: number;
};

export type SingleJobRequest = {
  prompt: string;
  copy: string;
  brand_kit_id: string;
  template_id?: string | null;
  provider?: "openai" | "local";
  quality?: "low" | "medium" | "high" | "auto";
  max_iterations?: number;
  seed?: number | null;
  cost_cap_usd?: number | null;
};

export type JobSummary = {
  id: string;
  status:
    | "queued"
    | "running"
    | "done"
    | "error"
    | "cancelled"
    | "cost_capped";
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
  request: Record<string, unknown>;
  total_cost_usd: number;
  error: string | null;
  final_url: string | null;
  raw_url: string | null;
  spec_url: string | null;
  parent_id: string | null;
  child_ids: string[];
};

// SSE event shapes (matches backend/app/services/jobs.py serializer).
export type PipelineEvent =
  | { type: "gen_start"; iteration: number; max: number; prompt: string }
  | { type: "gen_done"; iteration: number; image_b64: string; cost_so_far: number }
  | { type: "critique_start"; iteration: number }
  | {
      type: "critique_done";
      iteration: number;
      critique: {
        severity: "acceptable" | "minor" | "moderate" | "severe";
        is_acceptable: boolean;
        issues: string[];
        refined_prompt: string | null;
        reasoning: string;
      };
      cost_so_far: number;
    }
  | { type: "critique_failed"; iteration: number; message: string }
  | { type: "max_iterations_reached"; iteration: number; warning: string }
  | { type: "placement_start" }
  | {
      type: "placement_done";
      spec: Record<string, unknown>;
      image_b64: string;
      cost_so_far: number;
    }
  | {
      type: "render_done";
      final_b64: string;
      raw_b64: string;
      spec: Record<string, unknown>;
      critiques: Array<Record<string, unknown>>;
      final_prompt: string;
      total_cost: number;
    }
  | { type: "cost_cap_hit"; iteration: number; cost_so_far: number; cap: number }
  | { type: "cancelled"; iteration: number }
  | { type: "error"; stage: string; message: string; exception_type: string }
  | {
      type: "job_finalized";
      status: JobSummary["status"];
      total_cost: number;
      final_url: string | null;
      raw_url: string | null;
      spec_url: string | null;
      summary_url: string;
    }
  | { type: "child_queued"; child_id: string; index: number; total: number }
  | { type: "child_terminal"; child_id: string }
  | { type: "batch_done"; total: number };
