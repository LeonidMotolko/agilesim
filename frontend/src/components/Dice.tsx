import { useEffect, useRef, useState } from "react";

import { stageLabel } from "../constants";
import type { Dice, WorkStage } from "../types/api";

/** Which of the nine grid cells hold a pip for each face. */
const PIPS: Record<number, number[]> = {
  1: [4],
  2: [0, 8],
  3: [0, 4, 8],
  4: [0, 2, 6, 8],
  5: [0, 2, 4, 6, 8],
  6: [0, 2, 3, 5, 6, 8],
};

const CELLS = [0, 1, 2, 3, 4, 5, 6, 7, 8];
const ROLL_SETTLE_MS = 1500;

export function DieFace({ value }: { value: number }) {
  const filled = PIPS[value];
  if (filled === undefined) {
    return <b aria-hidden="true">{value}</b>;
  }
  return (
    <span className="die-face" aria-hidden="true">
      {CELLS.map((cell) => (
        <span key={cell} className={filled.includes(cell) ? "pip pip-on" : "pip"} />
      ))}
    </span>
  );
}

/** One square per point of the roll; the squares still unspent are filled. */
export function PointMeter({ total, left }: { total: number; left: number }) {
  const squares = Array.from({ length: Math.min(total, 12) }, (_, index) => index);
  return (
    <span className="meter" role="img" aria-label={`${left} of ${total} points left`}>
      {squares.map((index) => (
        <i key={index} className={index < left ? "on" : undefined} />
      ))}
    </span>
  );
}

interface DieTrayProps {
  stage: WorkStage;
  die: Dice | undefined;
  disabled: boolean;
  /** Resolves to true when the roll went through. */
  onRoll: (stage: WorkStage) => Promise<boolean>;
}

/** The die of one stage: a dashed die to press until it is rolled, then the rolled face. */
export function DieTray({ stage, die, disabled, onRoll }: DieTrayProps) {
  const [rolling, setRolling] = useState(false);
  const settleTimer = useRef<number | undefined>(undefined);
  const label = stageLabel(stage);

  useEffect(() => () => window.clearTimeout(settleTimer.current), []);

  const roll = () => {
    setRolling(true);
    void onRoll(stage).then((rolled) => {
      if (rolled) {
        settleTimer.current = window.setTimeout(() => setRolling(false), ROLL_SETTLE_MS);
      } else {
        setRolling(false);
      }
    });
  };

  return (
    <li className={`die-tray stage-${stage}`}>
      {die !== undefined ? (
        <span
          key={die.value}
          className={`die${rolling ? " die-land" : ""}`}
          role="img"
          aria-label={`${label} die shows ${die.value}`}
        >
          <DieFace value={die.value} />
        </span>
      ) : (
        <button
          type="button"
          className={`die die-empty${rolling ? " die-rolling" : ""}`}
          disabled={disabled || rolling}
          onClick={roll}
          aria-label={`Roll the ${label} die`}
        >
          ?
        </button>
      )}
      <span className="die-name">{label}</span>
      {die !== undefined ? (
        <PointMeter total={die.value} left={die.points_left} />
      ) : (
        <span className="die-hint">{rolling ? "Rolling" : "Press to roll"}</span>
      )}
    </li>
  );
}
