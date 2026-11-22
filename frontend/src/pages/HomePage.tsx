import { Link } from "react-router-dom";

const STEPS = [
  {
    title: "Roll the dice",
    text: "Each stage rolls its own die. That is the work your team has today.",
  },
  {
    title: "Spend the points",
    text: "Cross out squares on a card. Help from another stage counts half.",
  },
  {
    title: "Move finished cards",
    text: "A card moves one column at a time, and only when its work is done.",
  },
];

/** A decorative board where one card travels to Done, once, when the page opens. */
function MiniBoard() {
  const columns = [
    { name: "Backlog", stage: "backlog", ghosts: 2 },
    { name: "Analysis", stage: "analysis", ghosts: 1 },
    { name: "Development", stage: "development", ghosts: 1 },
    { name: "Done", stage: "done", ghosts: 0 },
  ];
  return (
    <div className="mini-board" aria-hidden="true">
      {columns.map((column) => (
        <div key={column.stage} className={`mini-column stage-${column.stage}`}>
          <b>{column.name}</b>
          {Array.from({ length: column.ghosts }, (_, index) => (
            <div key={index} className="mini-ghost" />
          ))}
        </div>
      ))}
      <div className="mini-card">
        ID-104
        <span>Pricing page</span>
      </div>
    </div>
  );
}

export function HomePage() {
  return (
    <>
      <section className="hero">
        <div>
          <h1>Run a startup on a Kanban board</h1>
          <p className="lead">
            Teams pull cards through Analysis, Development and Testing, roll dice for the work and
            handle surprises for eight days. The facilitator sets the pace.
          </p>
          <div className="hero-actions">
            <Link className="button" to="/join">
              Join a game
            </Link>
            <Link className="button secondary" to="/login">
              Facilitator sign in
            </Link>
          </div>
        </div>
        <MiniBoard />
      </section>
      <ol className="steps" aria-label="How a day works">
        {STEPS.map((step, index) => (
          <li key={step.title}>
            <b aria-hidden="true">{index + 1}</b>
            <h2>{step.title}</h2>
            <p>{step.text}</p>
          </li>
        ))}
      </ol>
    </>
  );
}
