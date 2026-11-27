import { useLayoutEffect, useRef } from "react";

import { STAGES, WORK_STAGES, nextStage, stageLabel } from "../constants";
import type { Board, Card, WipCounter } from "../types/api";

interface BoardViewProps {
  board: Board;
  /** Cards get action buttons when these are given (players only). */
  onMove?: (card: Card, target: string) => void;
  onSelect?: (card: Card) => void;
  selectedCardId?: string | null;
  busy?: boolean;
}

const MAX_SQUARES = 5;
const LANDING_MS = 520;

function isWorkStage(code: string): boolean {
  return WORK_STAGES.some((stage) => stage === code);
}

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}

/**
 * Plays a short landing animation on a card that has just arrived in another column. The first
 * render, and cards that did not change column, stay still.
 */
function useLandingAnimation(board: Board) {
  const boardRef = useRef<HTMLDivElement>(null);
  const previous = useRef<Map<string, string> | null>(null);

  useLayoutEffect(() => {
    const before = previous.current;
    const now = new Map<string, string>(board.cards.map((card) => [card.id, card.stage]));
    previous.current = now;
    const root = boardRef.current;
    if (before === null || root === null || prefersReducedMotion()) {
      return;
    }
    root.querySelectorAll<HTMLElement>("[data-card-id]").forEach((element) => {
      const id = element.dataset.cardId;
      const was = id === undefined ? undefined : before.get(id);
      if (id === undefined || was === undefined || was === now.get(id)) {
        return;
      }
      if (typeof element.animate === "function") {
        element.animate(
          [
            { transform: "translateX(-34px) scale(0.94)", opacity: 0.15 },
            { transform: "translateX(4px) scale(1.02)", opacity: 1, offset: 0.7 },
            { transform: "none", opacity: 1 },
          ],
          { duration: LANDING_MS, easing: "cubic-bezier(0.2, 0.9, 0.3, 1)" },
        );
      }
    });
  }, [board.cards]);

  return boardRef;
}

function squaresOf(card: Card, stage: string) {
  const left = card.squares_left[stage];
  return left === undefined ? null : left;
}

function WorkSquares({ card }: { card: Card }) {
  return (
    <ul className="squares" aria-label="Work left">
      {WORK_STAGES.map((stage) => {
        const left = squaresOf(card, stage);
        // With more than MAX_SQUARES left the row shows one box less and a "+n" for the rest,
        // so it still fits into a narrow column.
        const shown = left !== null && left > MAX_SQUARES ? MAX_SQUARES - 1 : (left ?? 0);
        return (
          <li key={stage} className={`stage-${stage}`}>
            <span>{stageLabel(stage)}</span>
            <span className="sq-boxes">
              {left === null ? (
                "–"
              ) : left === 0 ? (
                <span className="sq-done">
                  <span aria-hidden="true">✓</span>
                  <span className="visually-hidden">finished</span>
                </span>
              ) : (
                <>
                  {Array.from({ length: shown }, (_, index) => (
                    <i key={index} />
                  ))}
                  {left > MAX_SQUARES ? <span className="sq-more">+{left - shown}</span> : null}
                  <span className="visually-hidden">{left} left</span>
                </>
              )}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function CardTile({
  card,
  onMove,
  onSelect,
  selected,
  busy,
}: {
  card: Card;
  onMove?: (card: Card, target: string) => void;
  onSelect?: (card: Card) => void;
  selected: boolean;
  busy: boolean;
}) {
  const target = nextStage(card.stage);
  const label = target === null ? null : stageLabel(target);
  const classes = ["card", `stage-${card.stage}`];
  if (selected) {
    classes.push("card-selected");
  }
  if (card.is_emergency) {
    classes.push("card-urgent");
  }
  if (card.is_blocked) {
    classes.push("card-blocked");
  }
  return (
    <li className={classes.join(" ")} data-card-id={card.id}>
      <div className="card-head">
        <strong>ID-{card.number}</strong>
        <span className="card-value">${card.value}</span>
      </div>
      <p className="card-title">{card.title}</p>
      {isWorkStage(card.stage) ? <WorkSquares card={card} /> : null}
      <p className="card-badges">
        {card.is_blocked ? <span className="badge badge-danger">Blocked</span> : null}
        {card.is_emergency ? <span className="badge badge-danger">Emergency</span> : null}
        {card.state === "ready" ? <span className="badge badge-ok">Ready</span> : null}
      </p>
      {onMove !== undefined ? (
        <div className="card-actions">
          {onSelect !== undefined && isWorkStage(card.stage) ? (
            <button type="button" className="secondary" onClick={() => onSelect(card)}>
              Work on it
            </button>
          ) : null}
          {target !== null && label !== null ? (
            <button
              type="button"
              className={`move stage-${target}`}
              disabled={busy}
              onClick={() => onMove(card, target)}
            >
              Move to {label}
            </button>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

function CountBadge({
  counter,
  fallback,
  enforced,
}: {
  counter: WipCounter | undefined;
  fallback: number;
  enforced: boolean;
}) {
  if (counter === undefined || counter.limit === null) {
    return <span className="column-count">{fallback}</span>;
  }
  const over = enforced && counter.count > counter.limit;
  return (
    <span
      className={`wip${over ? " wip-over" : ""}`}
      title={enforced ? "Work in progress limit" : "Limit starts on day 5"}
    >
      <span>
        {counter.count}/{counter.limit}
      </span>
      <span className="wip-seg" aria-hidden="true">
        {Array.from({ length: counter.limit }, (_, index) => (
          <i key={index} className={index < counter.count ? "on" : undefined} />
        ))}
      </span>
    </span>
  );
}

export function BoardView({
  board,
  onMove,
  onSelect,
  selectedCardId,
  busy = false,
}: BoardViewProps) {
  const boardRef = useLandingAnimation(board);
  return (
    <div className="board" aria-label="Board" ref={boardRef}>
      {STAGES.map((stage) => {
        const cards = board.cards.filter((card) => card.stage === stage.code);
        const counter = board.wip.find((item) => item.stage === stage.code);
        return (
          <section
            key={stage.code}
            className={`column stage-${stage.code}`}
            aria-label={stage.label}
          >
            <div className="column-head">
              <h3>{stage.label}</h3>
              <CountBadge
                counter={counter}
                fallback={cards.length}
                enforced={board.wip_limits_enabled}
              />
            </div>
            <ul className="column-body">
              {cards.length === 0 ? <li className="column-empty">Nothing here yet</li> : null}
              {cards.map((card) => (
                <CardTile
                  key={card.id}
                  card={card}
                  onMove={onMove}
                  onSelect={onSelect}
                  selected={selectedCardId === card.id}
                  busy={busy}
                />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
