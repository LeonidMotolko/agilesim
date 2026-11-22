import { STAGES, nextStage, stageLabel } from "../constants";
import type { Board, Card } from "../types/api";

interface BoardViewProps {
  board: Board;
  /** Cards get action buttons when these are given (players only). */
  onMove?: (card: Card, target: string) => void;
  onSelect?: (card: Card) => void;
  selectedCardId?: string | null;
  busy?: boolean;
}

function squaresText(card: Card): string {
  const parts = Object.entries(card.squares_left)
    .filter(([, left]) => left > 0)
    .map(([stage, left]) => `${stageLabel(stage)} ${left}`);
  return parts.length > 0 ? `Left: ${parts.join(", ")}` : "All work done";
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
  return (
    <li
      className={`card${selected ? " card-selected" : ""}${card.is_emergency ? " card-urgent" : ""}`}
    >
      <div className="card-head">
        <strong>ID-{card.number}</strong>
        <span className="card-value">${card.value}</span>
      </div>
      <p className="card-title">{card.title}</p>
      {card.stage !== "backlog" && card.stage !== "done" ? (
        <p className="card-meta">{squaresText(card)}</p>
      ) : null}
      <p className="card-badges">
        {card.is_blocked ? <span className="badge badge-danger">Blocked</span> : null}
        {card.is_emergency ? <span className="badge badge-danger">Emergency</span> : null}
        {card.state === "ready" ? <span className="badge badge-ok">Ready</span> : null}
      </p>
      {onMove !== undefined && target !== null && label !== null ? (
        <div className="card-actions">
          {onSelect !== undefined && card.stage !== "backlog" ? (
            <button type="button" className="secondary" onClick={() => onSelect(card)}>
              Work on it
            </button>
          ) : null}
          <button type="button" disabled={busy} onClick={() => onMove(card, target)}>
            Move to {label}
          </button>
        </div>
      ) : null}
    </li>
  );
}

export function BoardView({
  board,
  onMove,
  onSelect,
  selectedCardId,
  busy = false,
}: BoardViewProps) {
  return (
    <div className="board" aria-label="Board">
      {STAGES.map((stage) => {
        const cards = board.cards.filter((card) => card.stage === stage.code);
        const counter = board.wip.find((item) => item.stage === stage.code);
        return (
          <section key={stage.code} className="column" aria-label={stage.label}>
            <h3>
              {stage.label}
              <span className="column-count">
                {counter !== undefined && counter.limit !== null
                  ? ` ${counter.count}/${counter.limit}`
                  : ` ${cards.length}`}
              </span>
            </h3>
            <ul>
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
