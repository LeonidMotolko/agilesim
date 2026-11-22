import { GAME_DAYS } from "../constants";

/** Where the game is: one segment per day, the passed days filled. */
export function DayStrip({
  day,
  total = GAME_DAYS,
  note,
}: {
  day: number;
  total?: number;
  note?: string;
}) {
  const days = Array.from({ length: total }, (_, index) => index + 1);
  return (
    <div className="day-strip">
      <p>
        <strong>{day === 0 ? "Waiting to start" : `Day ${day} of ${total}`}</strong>
        {note !== undefined && note !== "" ? <span className="muted">{note}</span> : null}
      </p>
      <ol aria-hidden="true">
        {days.map((number) => (
          <li
            key={number}
            className={number < day ? "passed" : number === day ? "current" : undefined}
          />
        ))}
      </ol>
    </div>
  );
}
