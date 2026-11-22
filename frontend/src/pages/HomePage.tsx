import { Link } from "react-router-dom";

export function HomePage() {
  return (
    <section>
      <h1>AgileSim</h1>
      <p className="lead">
        Learn Kanban by playing it: teams pull cards across the board, roll dice for the work and
        meet the surprises of Startup Flow, while the facilitator guides the day.
      </p>
      <div className="choices">
        <article className="panel">
          <h2>I run the game</h2>
          <p>Create a session, add teams and lead the eight days.</p>
          <Link className="button" to="/login">
            Facilitator sign in
          </Link>
        </article>
        <article className="panel">
          <h2>I am a player</h2>
          <p>Enter the join code from your facilitator and pick your team.</p>
          <Link className="button" to="/join">
            Join a game
          </Link>
        </article>
      </div>
    </section>
  );
}
