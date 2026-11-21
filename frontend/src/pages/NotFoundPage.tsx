import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <section>
      <h1>Page not found</h1>
      <p>There is nothing at this address.</p>
      <Link to="/">Back to the start</Link>
    </section>
  );
}
