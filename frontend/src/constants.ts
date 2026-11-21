import type { StageCode, WorkStage } from "./types/api";

export const STAGES: { code: StageCode; label: string }[] = [
  { code: "backlog", label: "Backlog" },
  { code: "analysis", label: "Analysis" },
  { code: "development", label: "Development" },
  { code: "testing", label: "Testing" },
  { code: "done", label: "Done" },
];

export const WORK_STAGES: WorkStage[] = ["analysis", "development", "testing"];

export const GAME_DAYS = 8;
export const POLL_MS = 3000;

export function stageLabel(code: string): string {
  return STAGES.find((stage) => stage.code === code)?.label ?? code;
}

/** The column a card moves to next, or null when it is already in Done. */
export function nextStage(code: string): StageCode | null {
  const index = STAGES.findIndex((stage) => stage.code === code);
  const next = index >= 0 ? STAGES[index + 1] : undefined;
  return next?.code ?? null;
}
