/** Shapes of the JSON bodies of the AgileSim API (mirror of backend/agilesim/schemas). */

export type Role = "facilitator" | "participant";

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: string;
}

export interface Participant {
  id: string;
  session_id: string;
  team_id: string | null;
  display_name: string;
  role: "player" | "scrum_master";
}

export interface JoinResponse {
  access_token: string;
  token_type: string;
  rejoin_token: string;
  participant: Participant;
}

export type SessionStatus = "lobby" | "running" | "paused" | "finished";

export interface GameSession {
  id: string;
  name: string;
  join_code: string;
  status: SessionStatus;
  current_day: number;
  wip_limits_enabled: boolean;
  lead_time_convention: "inclusive" | "difference";
  started_at: string | null;
  finished_at: string | null;
}

export interface Team {
  id: string;
  session_id: string;
  name: string;
}

export type WorkStage = "analysis" | "development" | "testing";
export type StageCode = "backlog" | WorkStage | "done";

export interface Card {
  id: string;
  number: number;
  title: string;
  value: number;
  is_emergency: boolean;
  stage: string;
  state: "in_progress" | "ready" | null;
  is_blocked: boolean;
  squares_left: Record<string, number>;
}

export interface WipCounter {
  stage: string;
  count: number;
  limit: number | null;
}

export interface Dice {
  stage: string;
  day: number;
  value: number;
  points_left: number;
}

export interface Board {
  team_id: string;
  day: number;
  wip_limits_enabled: boolean;
  cards: Card[];
  wip: WipCounter[];
  dice: Dice[];
}

export interface MoveResult {
  card: Card;
  replayed: boolean;
}

export interface SpendResult {
  card: Card;
  points_spent: number;
  squares_crossed: number;
  points_lost_to_rounding: number;
  points_left: number;
  replayed: boolean;
}

export interface TeamResult {
  team_id: string;
  team_name: string;
  done_cards: number;
  money_earned: number;
  avg_lead_time_days: number | null;
  money_rank: number;
}

export interface CardFlow {
  card_number: number;
  title: string;
  value: number;
  pulled_day: number | null;
  done_day: number | null;
  lead_time_days: number | null;
}

export type EventStatus = "proposed" | "confirmed" | "applied" | "dismissed";

export interface GameEvent {
  id: string;
  day: number;
  title: string;
  description: string;
  source: "template" | "ai" | "manual";
  status: EventStatus;
  effect: string | null;
  effect_amount: number | null;
  applied_at: string | null;
}
