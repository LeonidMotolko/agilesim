import type {
  Board,
  CardFlow,
  GameEvent,
  GameSession,
  JoinResponse,
  MoveResult,
  SpendResult,
  Team,
  TeamResult,
  TokenResponse,
  WorkStage,
  StageCode,
} from "../types/api";
import { request } from "./http";

const get = <T>(path: string, signal?: AbortSignal) => request<T>("GET", path, { signal });
const post = <T>(path: string, body?: unknown, auth = true) =>
  request<T>("POST", path, { body, auth });

export interface Credentials {
  email: string;
  password: string;
}

export interface Registration extends Credentials {
  display_name: string;
}

/** One typed function per endpoint of the backend (see docs/frontend.md). */
export const api = {
  register: (body: Registration) => post<TokenResponse>("/auth/register", body, false),
  login: (body: Credentials) => post<TokenResponse>("/auth/login", body, false),

  listSessions: (signal?: AbortSignal) => get<GameSession[]>("/sessions", signal),
  createSession: (name: string) => post<GameSession>("/sessions", { name }),
  getSession: (id: string, signal?: AbortSignal) => get<GameSession>(`/sessions/${id}`, signal),
  listTeams: (sessionId: string, signal?: AbortSignal) =>
    get<Team[]>(`/sessions/${sessionId}/teams`, signal),
  createTeam: (sessionId: string, name: string) =>
    post<Team>(`/sessions/${sessionId}/teams`, { name }),

  teamsByJoinCode: (code: string, signal?: AbortSignal) =>
    get<Team[]>(`/join/${encodeURIComponent(code)}/teams`, signal),
  join: (body: { join_code: string; display_name: string; team_id: string; consent: boolean }) =>
    post<JoinResponse>("/join", body, false),
  rejoin: (rejoinToken: string) =>
    post<JoinResponse>("/rejoin", { rejoin_token: rejoinToken }, false),

  startGame: (sessionId: string) => post<GameSession>(`/sessions/${sessionId}/start`),
  nextDay: (sessionId: string) => post<GameSession>(`/sessions/${sessionId}/next-day`),
  results: (sessionId: string, signal?: AbortSignal) =>
    get<TeamResult[]>(`/sessions/${sessionId}/results`, signal),

  listEvents: (sessionId: string, signal?: AbortSignal) =>
    get<GameEvent[]>(`/sessions/${sessionId}/events`, signal),
  createEvent: (sessionId: string, body: { title: string; description: string }) =>
    post<GameEvent>(`/sessions/${sessionId}/events`, body),
  applyEvent: (sessionId: string, eventId: string) =>
    post<GameEvent>(`/sessions/${sessionId}/events/${eventId}/apply`),
  dismissEvent: (sessionId: string, eventId: string) =>
    post<GameEvent>(`/sessions/${sessionId}/events/${eventId}/dismiss`),

  board: (teamId: string, signal?: AbortSignal) => get<Board>(`/teams/${teamId}/board`, signal),
  flow: (teamId: string, signal?: AbortSignal) => get<CardFlow[]>(`/teams/${teamId}/flow`, signal),
  rollDie: (teamId: string, stage: WorkStage) =>
    post<{ stage: string; day: number; value: number; points_left: number }>(
      `/teams/${teamId}/dice`,
      { stage },
    ),
  spend: (
    teamId: string,
    body: { card_id: string; source_stage: WorkStage; points: number; request_id: string },
  ) => post<SpendResult>(`/teams/${teamId}/spend`, body),
  moveCard: (teamId: string, cardId: string, body: { to_stage: StageCode; request_id: string }) =>
    post<MoveResult>(`/teams/${teamId}/cards/${cardId}/move`, body),
};
